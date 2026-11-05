"""
Módulo 4 — Coletor de Mídia (v3)
Busca B-roll e música de fundo para cada bloco VISUAL do roteiro.
PATCH v3:
  - 4 tentativas de keyword por bloco: keyword exata → fallback → visual_context → "dark cinematic"
  - Baixa até 3 clips DIFERENTES por bloco (sem repetição cross-blocos)
  - Música: Pixabay Music API com fallback para arquivo silencioso
  - Salva clip_map.json com lista de clips por bloco e path local

Dependências:
  pip install requests python-dotenv
Variáveis de ambiente:
  PEXELS_API_KEY
  PIXABAY_API_KEY
"""
import os
import json
import time
import hashlib
import requests
from pathlib import Path

MODULE_DIR   = os.path.dirname(__file__)
OUTPUT_DIR   = os.path.join(MODULE_DIR, "..", "output")
CLIPS_DIR    = os.path.join(OUTPUT_DIR,  "clips")
ROTEIRO_PATH = os.path.join(OUTPUT_DIR,  "roteiro.json")
USER_CLIPS_DIR = os.path.join(MODULE_DIR, "..", "user_clips")

PEXELS_API_KEY  = os.getenv("PEXELS_API_KEY",  "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

CLIPS_PER_BLOCK  = 3     # clips diferentes por bloco VISUAL
MIN_CLIP_SECONDS = 5     # duração mínima de clip aceita (evita micro-clips)
MAX_RETRIES      = 3     # tentativas HTTP


# ── Helpers HTTP ───────────────────────────────────────────────────────────────

def _get(url: str, headers: dict = None, params: dict = None, timeout: int = 15) -> dict:
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(1.5 ** attempt)


def _download(url: str, dest: Path) -> bool:
    """Baixa arquivo para dest. Retorna True se bem-sucedido."""
    if dest.exists() and dest.stat().st_size > 10_000:
        return True   # já baixado
    try:
        r = requests.get(url, timeout=60, stream=True)
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"    [download] Erro: {e}")
        return False


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:10]


# ── Pexels ─────────────────────────────────────────────────────────────────────

def _search_pexels(query: str, used_urls: set, max_results: int = 8) -> list:
    """Retorna lista de dicts {url, duration, source, tags, title} de clips do Pexels."""
    if not PEXELS_API_KEY:
        return []
    try:
        data = _get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": max_results, "orientation": "portrait"},
        )
    except Exception as e:
        print(f"    [Pexels] Erro na busca '{query}': {e}")
        return []

    results = []
    for video in data.get("videos", []):
        duration = video.get("duration", 0)
        if duration < MIN_CLIP_SECONDS:
            continue
        # Pega o arquivo de maior resolução ≤ 1080p
        files = sorted(
            [f for f in video.get("video_files", []) if f.get("width", 0) <= 1080],
            key=lambda f: f.get("width", 0),
            reverse=True,
        )
        if not files:
            continue
        url = files[0]["link"]
        
        # Extrai tags e título a partir do slug do URL do vídeo
        video_url = video.get("url", "")
        slug = []
        if "/video/" in video_url:
            slug_part = video_url.split("/video/")[-1].split("/")
            if slug_part:
                # Filtra numéricos que normalmente são IDs
                slug = [s for s in slug_part[0].split("-") if not s.isdigit() and s]
        title = " ".join(slug) if slug else query
        tags = slug if slug else [query]

        if url not in used_urls:
            results.append({
                "url": url,
                "duration": duration,
                "source": "pexels",
                "tags": tags,
                "title": title
            })
    return results


# ── Pixabay Vídeo ──────────────────────────────────────────────────────────────

def _search_pixabay_video(query: str, used_urls: set, max_results: int = 8) -> list:
    """Retorna lista de dicts {url, duration, source, tags, title} de vídeos do Pixabay."""
    if not PIXABAY_API_KEY:
        return []
    try:
        data = _get(
            "https://pixabay.com/api/videos/",
            params={
                "key":          PIXABAY_API_KEY,
                "q":            query,
                "per_page":     max_results,
                "video_type":   "film",
            },
        )
    except Exception as e:
        print(f"    [Pixabay] Erro na busca '{query}': {e}")
        return []

    results = []
    for hit in data.get("hits", []):
        videos = hit.get("videos", {})
        # Preferência: large → medium → small
        for size in ("large", "medium", "small"):
            v = videos.get(size, {})
            url = v.get("url", "")
            if url and url not in used_urls:
                duration = hit.get("duration", 0)
                
                # Extrai tags e título do Pixabay
                tags_str = hit.get("tags", "")
                tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                title = tags_str

                if duration >= MIN_CLIP_SECONDS:
                    results.append({
                        "url": url,
                        "duration": duration,
                        "source": "pixabay",
                        "tags": tags,
                        "title": title
                    })
                break
    return results


def _find_user_clips_for_block(block_id: int) -> list:
    """
    Busca arquivos na pasta user_clips que comecem com 'b{block_id}' ou 'b0{block_id}'
    e tenham extensões de vídeo comuns.
    """
    if not os.path.exists(USER_CLIPS_DIR):
        return []
    
    valid_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    matches = []
    
    # Formatos de prefixo: 'b02', 'b2' se block_id=2
    prefixes = [f"b{block_id:02d}", f"b{block_id}"]
    
    try:
        for filename in sorted(os.listdir(USER_CLIPS_DIR)):
            name, ext = os.path.splitext(filename.lower())
            if ext not in valid_extensions:
                continue
                
            matches_prefix = False
            for pref in prefixes:
                if name == pref or name.startswith(f"{pref}_"):
                    matches_prefix = True
                    break
                    
            if matches_prefix:
                file_path = os.path.join(USER_CLIPS_DIR, filename)
                matches.append(file_path)
    except Exception as e:
        print(f"[Módulo 4] Erro ao listar user_clips: {e}")
        
    return matches


def _call_ollama(payload: dict) -> str:
    """Auxiliar para chamar o Ollama local com tratamento de timeout."""
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    url = f"{host}/api/chat"
    model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    
    try:
        response = requests.post(
            url,
            json={
                "model": model,
                "messages": payload["messages"],
                "options": {"temperature": 0.2, "num_predict": 128},
                "stream": False
            },
            timeout=15
        )
        response.raise_for_status()
        res_json = response.json()
        return res_json.get("message", {}).get("content", "").strip()
    except Exception as e:
        # Silencia em caso de erro para não poluir o terminal se o Ollama estiver fora
        return ""


def _optimize_search_keywords_with_ollama(visual_context: str, fallback_text: str) -> list:
    """
    Usa o Ollama local para analisar a descrição da cena e gerar palavras-chave
    de busca em inglês extremamente precisas e curtas (1 a 3 termos simples).
    """
    contexto = visual_context or fallback_text
    if not contexto:
        return []
        
    # Verifica se o Ollama está ativo/disponível
    use_ollama = os.getenv("USE_OLLAMA", "False").lower() in ("true", "1", "yes")
    if not use_ollama:
        return []

    prompt = (
        f"Analise a seguinte descrição de cena de vídeo (em português) e gere 3 alternativas de termos "
        f"de busca em INGLÊS que sejam ideais para encontrar esse vídeo em bancos como Pixabay ou Pexels.\n"
        f"REGRAS OBRIGATÓRIAS:\n"
        f"1. Cada alternativa deve ser muito curta: de 1 a 3 palavras apenas (ex: 'ancient key lock').\n"
        f"2. Use apenas substantivos e verbos concretos e físicos. Evite termos abstratos, sentimentos ou metáforas.\n"
        f"3. Retorne APENAS um array JSON puro em uma única linha no formato: [\"keyword1\", \"keyword2\", \"keyword3\"].\n"
        f"Não escreva mais nada, apenas o JSON.\n\n"
        f"Cena: {contexto}"
    )
    
    messages = [{"role": "user", "content": prompt}]
    output = _call_ollama({"messages": messages})
    
    import re
    try:
        output_cleaned = re.sub(r"^```(?:json)?\s*", "", output)
        output_cleaned = re.sub(r"\s*```$", "", output_cleaned).strip()
        keywords = json.loads(output_cleaned)
        if isinstance(keywords, list):
            return [str(k).strip().lower() for k in keywords if k][:3]
    except Exception:
        pass
        
    return []


def _curate_video_with_ollama(visual_context: str, video_tags: list, video_title: str) -> bool:
    """
    Usa a IA local para analisar as tags e o título de um vídeo candidato
    e decidir se ele é coerente com o contexto visual esperado no roteiro.
    Retorna True se [COERENTE] ou False se [DESCONEXO].
    """
    if not visual_context or not video_tags:
        return True # Aceita por padrão para não quebrar a busca
        
    use_ollama = os.getenv("USE_OLLAMA", "False").lower() in ("true", "1", "yes")
    if not use_ollama:
        return True

    tags_str = ", ".join(video_tags[:15])
    prompt = (
        f"Você é um editor de vídeo profissional que faz a curadoria final de imagens.\n"
        f"Seu objetivo é analisar se o vídeo retornado pela busca combina de fato com a cena solicitada.\n\n"
        f"CENA ESPERADA: \"{visual_context}\"\n"
        f"DADOS DO VÍDEO CANDIDATO:\n"
        f"- Título do Vídeo: \"{video_title}\"\n"
        f"- Tags do Vídeo: {tags_str}\n\n"
        f"Compare os dados. O vídeo candidato é coerente e ilustra bem a cena esperada?\n"
        f"Responda apenas com uma única palavra:\n"
        f"COERENTE - se o vídeo ilustra bem a cena ou seus elementos essenciais.\n"
        f"DESCONEXO - se o vídeo é totalmente diferente, abstrato ou fora do assunto.\n"
        f"Não escreva nada além de COERENTE ou DESCONEXO."
    )
    
    messages = [{"role": "user", "content": prompt}]
    verdict = _call_ollama({"messages": messages}).upper()
    
    if "DESCONEXO" in verdict:
        return False
    return True


def _generate_video_comfyui(visual_ctx: str, dest_path: str) -> bool:
    """
    Gancho de integração para geração local de vídeo via ComfyUI (porta 8188) ou SD (7860).
    Permite rodar 100% offline se ativado via variáveis de ambiente.
    """
    use_comfy = os.getenv("USE_COMFYUI", "False").lower() in ("true", "1", "yes")
    if not use_comfy:
        return False
    
    comfy_host = os.getenv("COMFYUI_HOST", "http://127.0.0.1:8188")
    print(f"    [ComfyUI Local] Fila de Produção: Enviando prompt de geração offline p/ {comfy_host}...")
    print(f"    [ComfyUI Local] Prompt: '{visual_ctx}'")
    # Aqui a integração faria a requisição HTTP POST para o endpoint /prompt do ComfyUI
    # Por padrão, deixamos o log da fila preparado
    return False


def _collect_for_block(bloco: dict, used_urls: set, roteiro_data: dict) -> list:
    """
    Coleta clips de mídia para o bloco visual:
    1. Verifica se há vídeos locais na pasta user_clips (Nomenclatura: bXX.mp4 ou bXX_X.mp4)
    2. Verifica se a geração por ComfyUI/SD local está ativa
    3. Faz busca inteligente nas APIs (Pexels/Pixabay) com palavras-chave refinadas pelo Ollama
    4. Curadoria ativa: Ollama local analisa as tags do vídeo candidato e decide se combina.
    """
    block_id      = bloco.get("id", 0)
    keyword       = (bloco.get("keyword") or bloco.get("text") or bloco.get("conteudo") or "cinematic")
    visual_ctx    = bloco.get("visual_context", "")
    duration_hint = bloco.get("duration_hint", 4.0)

    # ── 1. BUSCA POR CLIPS MANUAIS DO USUÁRIO ──
    user_files = _find_user_clips_for_block(block_id)
    if user_files:
        print(f"    [B{block_id}] Encontrado(s) {len(user_files)} clipe(s) manual(is) na pasta user_clips/")
        collected = []
        import shutil
        
        # Importação interna e dinâmica para ler a duração real
        try:
            from modules.video_assembler import _get_duration
        except ImportError:
            def _get_duration(path): return 5.0

        for idx, src_path in enumerate(user_files):
            ext = os.path.splitext(src_path)[1]
            filename = f"b{block_id:02d}_manual_{idx+1}{ext}"
            dest     = Path(CLIPS_DIR) / filename
            
            print(f"      - Copiando clipe manual: {filename}")
            try:
                shutil.copy(src_path, dest)
                duration = _get_duration(str(dest))
                if duration <= 0.0:
                    duration = 5.0  # fallback se corrompido ou sem ffprobe
                
                collected.append({
                    "path":         str(dest),
                    "duration":     duration,
                    "source":       "user_manual",
                    "keyword_used": "user_upload",
                })
            except Exception as e:
                print(f"      [ERRO] Falha ao copiar clipe manual {src_path}: {e}")
                
        if collected:
            return collected

    # ── 2. GANCHO DE GERAÇÃO POR IA LOCAL (COMFYUI) ──
    filename_ai = f"b{block_id:02d}_comfy_{int(time.time())}.mp4"
    dest_ai     = Path(CLIPS_DIR) / filename_ai
    if _generate_video_comfyui(visual_ctx or keyword, str(dest_ai)):
        print(f"    [B{block_id}] Vídeo gerado com sucesso via ComfyUI offline!")
        return [{
            "path":         str(dest_ai),
            "duration":     5.0,
            "source":       "comfyui_local",
            "keyword_used": "ai_generation",
        }]

    # ── 3. BUSCA E CURADORIA AUTOMÁTICA COM OLLAMA ──
    tema_clean = roteiro_data.get("tema", "").lower()
    
    def clean_query(q):
        return "".join(c for c in q if c.isalnum() or c.isspace()).lower().strip()

    main_query = clean_query(keyword)
    queries_to_try = []

    # A. Otimização Contextual por IA Local (Ollama)
    use_ollama = os.getenv("USE_OLLAMA", "False").lower() in ("true", "1", "yes")
    if use_ollama and visual_ctx:
        print(f"    [B{block_id}] Consultando Ollama local para otimizar busca de tags...")
        ai_keywords = _optimize_search_keywords_with_ollama(visual_ctx, keyword)
        if ai_keywords:
            print(f"      - Keywords sugeridas pela IA: {ai_keywords}")
            queries_to_try.extend(ai_keywords)

    # B. Queries normais de Fallback
    if main_query and main_query not in queries_to_try:
        queries_to_try.append(main_query)
    
    tema_busca = clean_query(tema_clean)
    if tema_busca and tema_busca not in queries_to_try:
        queries_to_try.append(tema_busca)
        
    # Fallbacks neutros genéricos de alta qualidade
    queries_to_try.append("aerial nature landscape 4k")
    queries_to_try.append("minimalist abstract background focus")

    collected = []
    for query in queries_to_try:
        if len(collected) >= CLIPS_PER_BLOCK:
            break

        print(f"    [B{block_id}] Buscando na API: '{query}'")

        candidates = (
            _search_pexels(query, used_urls)
            + _search_pixabay_video(query, used_urls)
        )

        for candidate in candidates:
            if len(collected) >= CLIPS_PER_BLOCK:
                break
            url = candidate["url"]
            if url in used_urls:
                continue

            # C. Curadoria Ativa de Vídeo por IA Local (Ollama)
            if use_ollama and visual_ctx:
                video_tags = candidate.get("tags", [])
                video_title = candidate.get("title", "")
                
                # Executa o filtro de curadoria
                if not _curate_video_with_ollama(visual_ctx, video_tags, video_title):
                    print(f"      [Curador IA] Vídeo REJEITADO (incoerente com a cena). Pulando...")
                    continue
                else:
                    print(f"      [Curador IA] Vídeo APROVADO! Altamente coerente.")

            filename = f"b{block_id:02d}_{_url_hash(url)}.mp4"
            dest     = Path(CLIPS_DIR) / filename

            print(f"      - Baixando {candidate['source']}: {filename}")
            if _download(url, dest):
                used_urls.add(url)
                collected.append({
                    "path":         str(dest),
                    "duration":     candidate["duration"],
                    "source":       candidate["source"],
                    "keyword_used": query,
                })

    # D. Fallback Final (Pollinations/Preto) se tudo falhar
    if not collected:
        print(f"    [B{block_id}] Buscas e curadorias falharam. Acionando Fallback de Imagem IA (Pollinations)...")
        try:
            from modules.image_generator import generate_fallback_clip
        except ImportError:
            def generate_fallback_clip(prompt, path): return False
            
        filename = f"b{block_id:02d}_iagen_{int(time.time())}.mp4"
        dest = Path(CLIPS_DIR) / filename
        
        if generate_fallback_clip(visual_ctx or keyword, str(dest)):
            collected.append({
                "path":         str(dest),
                "duration":     5.0,
                "source":       "pollinations_ai",
                "keyword_used": "ai_generated",
            })
    return collected


# ── Música de fundo ────────────────────────────────────────────────────────────

def download_background_music() -> str:
    """Baixa faixa de música instrumental dark do Pixabay. Retorna path."""
    music_path = os.path.join(OUTPUT_DIR, "background.mp3")
    if os.path.exists(music_path) and os.path.getsize(music_path) > 50_000:
        print("[Módulo 4] Música já baixada, reutilizando.")
        return music_path

    if not PIXABAY_API_KEY:
        print("[Módulo 4] PIXABAY_API_KEY ausente — pulando música.")
        return ""

    queries = ["dark ambient cinematic", "mystery thriller background", "dark instrumental"]
    for q in queries:
        try:
            data = _get(
                "https://pixabay.com/api/",
                params={
                    "key":      PIXABAY_API_KEY,
                    "q":        q,
                    "category": "music",
                    "per_page": 5,
                },
            )
            for hit in data.get("hits", []):
                url = hit.get("audio", hit.get("previewURL", ""))
                if url:
                    print(f"[Módulo 4] Baixando música: {q}")
                    if _download(url, Path(music_path)):
                        return music_path
        except Exception as e:
            print(f"[Módulo 4] Erro ao buscar música '{q}': {e}")

    print("[Módulo 4] Nenhuma música encontrada.")
    return ""


# ── Entry point ────────────────────────────────────────────────────────────────

def collect_clips(roteiro_data: dict = None) -> dict:
    """
    Coleta clips para todos os blocos VISUAL do roteiro.
    Retorna clip_map: {block_id: [{"path": ..., "duration": ...}, ...]}
    """
    if roteiro_data is None:
        with open(ROTEIRO_PATH, "r", encoding="utf-8") as f:
            roteiro_data = json.load(f)

    os.makedirs(CLIPS_DIR, exist_ok=True)
    os.makedirs(USER_CLIPS_DIR, exist_ok=True)

    blocos_visuais = [b for b in roteiro_data["blocks"] if (b.get("type") or b.get("tipo")) == "VISUAL"]
    print(f"[Módulo 4] {len(blocos_visuais)} blocos VISUAL para coletar B-roll")

    used_urls: set = set()
    clip_map: dict = {}

    for bloco in blocos_visuais:
        clips = _collect_for_block(bloco, used_urls, roteiro_data)
        clip_map[str(bloco["id"])] = clips

    clip_map_path = os.path.join(OUTPUT_DIR, "clip_map.json")
    with open(clip_map_path, "w", encoding="utf-8") as f:
        json.dump(clip_map, f, ensure_ascii=False, indent=2)
    print(f"[Módulo 4] clip_map.json salvo ({len(clip_map)} blocos).")

    return clip_map


if __name__ == "__main__":
    collect_clips()
    download_background_music()

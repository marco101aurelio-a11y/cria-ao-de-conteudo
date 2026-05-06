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
    """Retorna lista de dicts {url, duration} de clips do Pexels."""
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
        if url not in used_urls:
            results.append({"url": url, "duration": duration, "source": "pexels"})
    return results


# ── Pixabay Vídeo ──────────────────────────────────────────────────────────────

def _search_pixabay_video(query: str, used_urls: set, max_results: int = 8) -> list:
    """Retorna lista de dicts {url, duration} de vídeos do Pixabay."""
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
                if duration >= MIN_CLIP_SECONDS:
                    results.append({"url": url, "duration": duration, "source": "pixabay"})
                break
    return results


# ── Coleta por bloco ───────────────────────────────────────────────────────────

def _collect_for_block(bloco: dict, used_urls: set, roteiro_data: dict) -> list:
    """
    Tenta 4 queries em ordem até ter CLIPS_PER_BLOCK clips únicos.
    Retorna lista de dicts com path local e duração.
    """
    block_id      = bloco.get("id", 0)
    # Aceita 'keyword', 'text' ou 'conteudo'
    keyword       = (bloco.get("keyword") or bloco.get("text") or bloco.get("conteudo") or "dark cinematic")
    keyword_fb    = bloco.get("keyword_fallback", "dark cinematic")
    visual_ctx    = bloco.get("visual_context", "")
    duration_hint = bloco.get("duration_hint", 4.0)

    # Gera uma query a partir do visual_context (primeiras 4 palavras relevantes)
    # PRIORIDADE: Garantir que o tema principal esteja na busca
    tema_clean = roteiro_data.get("tema", "dark cinematic")
    
    # Se a keyword for em português ou curta, vamos tentar injetar o tema
    def clean_query(q):
        # Remove caracteres especiais e garante minúsculas
        return "".join(c for c in q if c.isalnum() or c.isspace()).lower().strip()

    main_query = clean_query(keyword)
    
    # Lista de tentativas inteligentes
    queries_to_try = []
    
    # 1. Keyword exata (se o LLM fez o trabalho certo em inglês)
    queries_to_try.append(main_query)
    
    # 2. Keyword + Tema (Garante contexto)
    if len(main_query.split()) < 3:
        queries_to_try.append(f"{main_query} {tema_clean}")

    # 3. Contexto Visual (Primeiras palavras)
    if visual_ctx:
        ctx_words = clean_query(visual_ctx).split()
        queries_to_try.append(" ".join(ctx_words[:5]))
        
    # 4. Tema Puro + Cinematic (Última chance de ser relevante)
    queries_to_try.append(f"{tema_clean} cinematic mystery")
    queries_to_try.append("dark cinematic mystery")

    collected = []
    for query in queries_to_try:
        if len(collected) >= CLIPS_PER_BLOCK:
            break

        print(f"    [B{block_id}] Buscando: '{query}'")

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

    if not collected:
        print(f"    [B{block_id}] Pexels e Pixabay falharam. Acionando Fallback de Imagem IA (Pollinations)...")
        from modules.image_generator import generate_fallback_clip
        import time
        
        filename = f"b{block_id:02d}_iagen_{int(time.time())}.mp4"
        dest = Path(CLIPS_DIR) / filename
        
        # Passamos o visual_context, ou a keyword caso não tenha contexto
        if generate_fallback_clip(visual_ctx or keyword, str(dest)):
            collected.append({
                "path":         str(dest),
                "duration":     5.0,  # O script gerador cria MP4 de 5 segundos
                "source":       "pollinations_ai",
                "keyword_used": "ai_generated",
            })
        else:
            print(f"    [B{block_id}] AVISO FATAL: Todas as fontes falharam. Bloco terá tela preta.")

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

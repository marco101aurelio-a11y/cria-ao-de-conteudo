"""
Módulo 1 — Gerador de Roteiros (Motor V3.1)
Gera roteiros JSON otimizados para vídeos curtos (Dark Videos).
Inclui suporte a RAG (Supabase) e Multi-Camadas (OpenRouter -> Gemini).

SCHEMA ESPERADO:
{
  "tema": "...",
  "titulo_sugerido": "...",
  "blocks": [
    { "type": "NARRACAO", "text": "...", "duration_hint": 4.5 },
    { "type": "VISUAL",   "text": "...", "visual_context": "..." }
  ]
}
"""
import os
import json
import re
import requests
from supabase import create_client, Client
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

MODULE_DIR  = os.path.dirname(__file__)
OUTPUT_DIR  = os.path.join(MODULE_DIR, "..", "output")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "roteiro.json")
MANUAL_JSON_PATH = os.path.join(MODULE_DIR, "..", "roteiro_manual.json")

def get_config(key, default=None):
    return os.getenv(key, default)
 
SYSTEM_PROMPT = """
Você é um experiente roteirista profissional para plataformas digitais multicanais (TikTok, Shorts, Reels).
Seu objetivo é criar um roteiro em JSON que se conecte com o público e prenda a atenção do início ao fim usando o framework CAPVI:

FRAMEWORK DE RETENÇÃO:
1. HOOK (Gancho): Os primeiros 3 segundos DEVEM ser magnéticos e prender a atenção com base direta no tema solicitado.
2. PROMESSA: Apresente o assunto principal do vídeo claramente.
3. PROVA/CORPO: Desenvolva o tema com ritmo envolvente e fluidez.
4. CTA (Chamada): Crie um direcionamento amigável e natural condizente com o tema.

ESTRUTURA TÉCNICA OBRIGATÓRIA:
1. Alterne blocos de NARRACAO (fala) e VISUAL (descrição da cena).
2. O tom e a atmosfera do vídeo DEVEM se adaptar 100% ao tema enviado. NUNCA aplique atmosferas escuras, tristes ou sombrias, a menos que o tema peça isso explicitamente.
3. VISUAL ("text"): Use palavras-chave CURTAS em INGLÊS. Elas devem descrever de forma limpa e precisa as imagens do que está sendo narrado.
4. CONTEXTO VISUAL: Descreva em português de maneira clara, realista e sem adjetivos desnecessários como a cena deve parecer.
5. Conexão Visual Rígida: Cada imagem visualizada DEVE ser uma ilustração direta do assunto falado.

RETORNE APENAS O JSON PURO.
"""

USER_PROMPT_TEMPLATE = """
TEMA DO VÍDEO: {tema}

{contexto_referencia}

Gere um roteiro GRANDE com 8 a 12 blocos de narração densos e repletos de mistério. 
O tempo total deve ser entre 50 a 80 segundos. O texto da narração deve ser bem detalhado para o vídeo não ficar muito curto.
"""

def _get_references_context(tema: str) -> str:
    """Busca referências no Supabase para injetar no prompt (RAG)."""
    url = get_config("SUPABASE_URL")
    key = get_config("SUPABASE_KEY")
    if not url or not key:
        return ""

    try:
        supabase: Client = create_client(url, key)
        
        # Verifica se a tabela tem algo antes de buscar
        count_res = supabase.table("viral_references").select("*", count="exact").limit(1).execute()
        if not count_res.count or count_res.count == 0:
            return ""

        print(f"[Modulo 1] Buscando referencias virais para RAG...")
        # Busca referências que batam com o tema (ou genéricas se não achar)
        response = supabase.table("viral_references")\
            .select("*")\
            .order("views", desc=True)\
            .limit(2)\
            .execute()
        
        refs = response.data
        if not refs:
            return ""

        context = "USE ESTAS REFERENCIAS VIRAIS COMO INSPIRACAO DE ESTRUTURA E TOM:\n"
        for i, r in enumerate(refs):
            context += f"Ref {i+1} ({r.get('views', 0)} views): {r.get('transcript', '')[:200]}...\n"
        
        return context + "\n"
    except Exception as e:
        print(f"[Modulo 1] Falha ao buscar RAG no Supabase: {e}")
        return ""


def _call_openrouter(tema: str) -> dict:
    """Chama a API do OpenRouter tentando múltiplos modelos gratuitos em cascata."""
    api_key = get_config("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY nao definida no .env")

    # Lista de modelos gratuitos para tentar em sequência
    # Prioridade: Melhores/Mais estáveis primeiro
    free_models = [
        get_config("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
        "tencent/hy3-preview:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "z-ai/glm-4.5-air:free",
        "minimax/minimax-m2.5:free",
        "mistralai/mistral-7b-instruct:free",
        "google/gemma-2-9b-it:free"
    ]

    # Remove duplicatas mantendo a ordem
    free_models = list(dict.fromkeys(free_models))

    contexto = _get_references_context(tema)
    user_prompt = USER_PROMPT_TEMPLATE.format(tema=tema, contexto_referencia=contexto)
    last_error = None

    for model in free_models:
        try:
            print(f"[Modulo 1] Tentando OpenRouter com modelo: {model}...")
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 2048,
            }

            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "https://darkvideopipeline.local",
                },
                json=payload,
                timeout=60,
            )
            
            if response.status_code == 429:
                print(f"  > Modelo {model} atingiu limite (429). Tentando próximo...")
                continue
                
            response.raise_for_status()
            res_json = response.json()
            
            # Garante que a resposta tenha conteúdo
            choices = res_json.get("choices", [])
            if not choices:
                print(f"  > Modelo {model} retornou resposta vazia. Tentando próximo...")
                continue
                
            content = choices[0].get("message", {}).get("content")
            if content is None:
                print(f"  > Modelo {model} retornou conteúdo nulo. Tentando próximo...")
                continue

            raw = content.strip()

            # Limpeza de Markdown
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$",          "", raw)

            return json.loads(raw)
            
        except Exception as e:
            last_error = e
            print(f"  > Falha com {model}: {e}")
            continue

    raise last_error


def _validate_and_fix(roteiro: any, tema: str) -> dict:
    """Garante que o roteiro tenha os campos obrigatórios e mapeia variações de nomes."""
    
    # Se o modelo retornou uma lista direta em vez de um dicionário
    if isinstance(roteiro, list):
        roteiro = {"blocks": roteiro}
    
    if not isinstance(roteiro, dict):
        roteiro = {"blocks": []}

    roteiro.setdefault("tema", tema)
    roteiro.setdefault("titulo_sugerido", tema)

    # Mapeia 'blocos' para 'blocks' se o modelo retornar em português
    if "blocos" in roteiro and not roteiro.get("blocks"):
        roteiro["blocks"] = roteiro["blocos"]

    # Adaptador de Formato Unificado: Se os blocos contêm "narracao" e "visual" diretamente
    # Ex: [{"narracao": "...", "visual": {"keywords": [...], "contexto": "..."}}]
    # Vamos converter em blocos intercalados de NARRACAO e VISUAL
    if roteiro.get("blocks") and isinstance(roteiro.get("blocks"), list) and any(isinstance(b, dict) and ("narracao" in b or "narracão" in b) and "visual" in b for b in roteiro["blocks"]):
        print("[Módulo 1] Adaptador de Formato Unificado ativo: Convertendo blocos unificados para blocos intercalados...")
        new_blocks = []
        for i, b in enumerate(roteiro["blocks"]):
            if not isinstance(b, dict):
                continue
            narr = b.get("narracao") or b.get("narracão") or b.get("text") or b.get("texto")
            vis = b.get("visual")
            duracao = b.get("duration_hint") or b.get("duracao") or b.get("duracao_segundos")
            
            if narr:
                new_blocks.append({
                    "id": len(new_blocks) + 1,
                    "type": "NARRACAO",
                    "text": narr,
                    "duration_hint": float(duracao) if duracao else max(4.0, len(str(narr).split()) * 0.35)
                })
            
            if vis:
                vis_text = ""
                vis_ctx = ""
                if isinstance(vis, dict):
                    kw = vis.get("keywords")
                    if isinstance(kw, list):
                        vis_text = ", ".join(kw)
                    elif isinstance(kw, str):
                        vis_text = kw
                    else:
                        vis_text = vis.get("text") or vis.get("texto") or ""
                        
                    vis_ctx = vis.get("contexto") or vis.get("context") or vis.get("visual_context") or ""
                elif isinstance(vis, str):
                    vis_text = vis
                    vis_ctx = vis
                
                new_blocks.append({
                    "id": len(new_blocks) + 1,
                    "type": "VISUAL",
                    "text": vis_text,
                    "visual_context": vis_ctx
                })
        roteiro["blocks"] = new_blocks

    # Adaptador de Formato: Converte do formato do Braço 1 FastAPI ("cenas") para "blocks"
    # Campos do Braço 1: titulo, gancho, cenas, call_to_action, hashtags
    # Cada cena: numero, duracao_segundos, narração, visual_sugerido, efeito_sonoro
    if "cenas" in roteiro and not roteiro.get("blocks"):
        print("[Módulo 1] Adaptador Braço 1 ativo: Convertendo 'cenas' em 'blocks'...")
        blocks = []
        
        # 1. Gancho como o primeiro bloco de NARRACAO
        gancho = roteiro.get("gancho")
        if gancho:
            blocks.append({
                "type": "NARRACAO",
                "text": gancho,
                "duration_hint": max(3.0, len(gancho.split()) * 0.35)
            })
            
        # 2. Iterar sobre as cenas e intercalar NARRACAO e VISUAL
        for i, cena in enumerate(roteiro["cenas"]):
            if not isinstance(cena, dict):
                continue
            narração = cena.get("narração") or cena.get("narracao") or cena.get("texto")
            visual = cena.get("visual_sugerido") or cena.get("visual") or cena.get("visual_context")
            duracao = cena.get("duracao_segundos") or cena.get("duracao") or cena.get("duration_hint") or 5.0
            
            if narração:
                blocks.append({
                    "type": "NARRACAO",
                    "text": narração,
                    "duration_hint": float(duracao)
                })
            if visual:
                blocks.append({
                    "type": "VISUAL",
                    "text": visual,
                    "visual_context": visual
                })
                
        # 3. Call to Action como último bloco de NARRACAO
        cta = roteiro.get("call_to_action") or roteiro.get("cta")
        if cta:
            blocks.append({
                "type": "NARRACAO",
                "text": cta,
                "duration_hint": max(4.0, len(cta.split()) * 0.35)
            })
            
        roteiro["blocks"] = blocks
        if "titulo" in roteiro:
            roteiro["titulo_sugerido"] = roteiro["titulo"]

    # Mapeia 'blocos' para 'blocks' se o modelo retornar em português
    if "blocos" in roteiro and not roteiro.get("blocks"):
        roteiro["blocks"] = roteiro["blocos"]

    if not isinstance(roteiro.get("blocks"), list):
        roteiro["blocks"] = []

    for i, bloco in enumerate(roteiro["blocks"]):
        # Garante ID
        if "id" not in bloco:
            bloco["id"] = i + 1
        
        # Mapeia variações de Tipo
        if "tipo" in bloco and "type" not in bloco:
            bloco["type"] = bloco["tipo"]
        
        # Mapeia variações de Texto/Conteúdo
        if "conteudo" in bloco and "text" not in bloco:
            bloco["text"] = bloco["conteudo"]
        if "texto" in bloco and "text" not in bloco:
            bloco["text"] = bloco["texto"]

        # Mapeia variações de Duração
        if "duracao" in bloco and "duration_hint" not in bloco:
            bloco["duration_hint"] = bloco["duracao"]

    return roteiro


def _extract_blocks_from_raw_string(content: str) -> list:
    """Extrai blocos estruturados diretamente da string usando expressões regulares de forma ultra-robusta."""
    blocks = []
    
    # Encontra objetos JSON individuais entre chaves que possuem "type" como "NARRACAO" ou "VISUAL"
    matches = re.finditer(r'\{[^{}]*\}', content, re.DOTALL)
    
    for m in matches:
        block_str = m.group(0)
        # Verifica se o bloco se parece com um bloco válido do pipeline
        if any(keyword in block_str.upper() for keyword in ["NARRACAO", "VISUAL", "NARRACÃO"]):
            try:
                block_data = json.loads(block_str)
                blocks.append(block_data)
            except Exception:
                try:
                    # Fallback manual em caso de falha de parser JSON rígido (ex: aspas soltas)
                    type_match = re.search(r'"(?:type|tipo)"\s*:\s*"([^"]+)"', block_str, re.IGNORECASE)
                    text_match = re.search(r'"(?:text|texto|conteudo)"\s*:\s*"([^"]+)"', block_str, re.IGNORECASE)
                    dur_match = re.search(r'"(?:duration_hint|duracao|duracao_segundos)"\s*:\s*([0-9.]+)', block_str, re.IGNORECASE)
                    ctx_match = re.search(r'"(?:visual_context|visual_sugerido)"\s*:\s*"([^"]+)"', block_str, re.IGNORECASE)
                    
                    block_data = {}
                    if type_match:
                        block_data["type"] = type_match.group(1).upper()
                    if text_match:
                        block_data["text"] = text_match.group(1)
                    if dur_match:
                        block_data["duration_hint"] = float(dur_match.group(1))
                    if ctx_match:
                        block_data["visual_context"] = ctx_match.group(1)
                        
                    if block_data.get("type"):
                        blocks.append(block_data)
                except Exception:
                    pass
    return blocks


def _call_ollama_direct(tema: str) -> dict:
    """Chama a API local do Ollama na porta 11434 retornando o roteiro estruturado JSON."""
    host = get_config("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = get_config("OLLAMA_MODEL", "llama3.2:3b")
    url = f"{host}/api/chat"
    
    contexto = _get_references_context(tema)
    user_prompt = USER_PROMPT_TEMPLATE.format(tema=tema, contexto_referencia=contexto)
    
    ollama_system_prompt = """Você é um roteirista sênior de vídeos virais e 'Dark Channel' de alta retenção (TikTok/Shorts/Reels).
Seu objetivo é criar um roteiro em JSON que seja ALTAMENTE viciante, dramático e prenda a atenção do início ao fim usando técnicas avançadas de storytelling.

Você DEVE retornar EXATAMENTE um objeto JSON no seguinte formato:
{
  "tema": "Tema do vídeo",
  "titulo_sugerido": "Título viral magnético (ex: O SEGREDO BIZARRO QUE...)",
  "blocks": [
    {
      "type": "NARRACAO",
      "text": "Texto falado impactante. Comece com um HOOK (Gancho) impossível de ignorar nos primeiros 3 segundos.",
      "duration_hint": 4.5
    },
    {
      "type": "VISUAL",
      "text": "Keywords em inglês que representam o que foi narrado (ex: dark forest fog mystery)",
      "visual_context": "Descrição da cena em português que ilustra com precisão o bloco narrado"
    }
  ]
}

REGRAS DE OURO PARA ROTEIROS VIRAIS:
1. Alterne blocos de NARRACAO (fala) e VISUAL (descrição da cena).
2. O roteiro DEVE ser LONGO e DETALHADO. Retorne de 16 a 24 blocos no total na lista "blocks" (sendo metade narração, metade visual). Cada bloco de narração deve ter cerca de 15 a 30 palavras para o vídeo chegar a ~60 segundos e não ficar tosco e curto.
3. RITMO E TOM: Use um tom MUITO misterioso, investigativo e sombrio. Você precisa GERAR CURIOSIDADE EXTREMA no espectador. O conteúdo não pode ser superficial, traga detalhes chocantes e fatos bizarros sobre o tema.
4. HOOK INICIAL: O primeiro bloco de narração DEVE ser uma pergunta perturbadora ou um fato que quebre as crenças do espectador nos primeiros 3 segundos.
5. CONECTIVIDADE: O bloco VISUAL deve ilustrar EXATAMENTE o assunto do bloco NARRACAO anterior.
6. NO VISUAL "text": USE NO MÁXIMO 3 PALAVRAS EM INGLÊS puras (ex: "pyramid desert night").
7. RETORNE APENAS O JSON PURO. NENHUM TEXTO ANTES OU DEPOIS.
"""
    print(f"[Módulo 1] Tentando Ollama Direct ({host}) com o modelo: {model}...")
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": ollama_system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "options": {
            "temperature": 0.7,
            "num_predict": 2048,
        },
        "stream": False,
        "format": "json"
    }
    
    response = requests.post(url, json=payload, timeout=300)
    response.raise_for_status()
    res_json = response.json()
    
    content = res_json.get("message", {}).get("content", "").strip()
    
    # Limpeza de markdown caso o LLM insira mesmo com formato JSON
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$",          "", content)
    
    roteiro = None
    try:
        roteiro = json.loads(content)
        # Se contiver blocks duplicados (comum em LLMs locais), re-extraímos de forma robusta
        if "blocks" in content and len(roteiro.get("blocks", [])) <= 2:
            print("[Módulo 1] Detetada possível duplicação ou estrutura parcial de 'blocks'. Iniciando extrator robusto...")
            extracted_blocks = _extract_blocks_from_raw_string(content)
            if len(extracted_blocks) > len(roteiro.get("blocks", [])):
                roteiro["blocks"] = extracted_blocks
    except Exception:
        print("[Módulo 1] Falha ao ler JSON bruto. Iniciando extrator robusto de emergência...")
        extracted_blocks = _extract_blocks_from_raw_string(content)
        roteiro = {
            "tema": tema,
            "titulo_sugerido": tema,
            "blocks": extracted_blocks
        }
        
    return roteiro

def _call_braco1_fastapi(tema: str) -> dict:
    """Chama o servidor FastAPI Braço 1 na porta 8001 para obter o roteiro."""
    braco_url = get_config("BRACO1_URL", "http://localhost:8001").rstrip("/")
    url = f"{braco_url}/gerar-roteiro"
    
    print(f"[Módulo 1] Tentando Braço 1 FastAPI ({braco_url})...")
    
    payload = {
        "tema": tema,
        "duracao_segundos": 60,
        "estilo": "dark",
        "num_cenas": 5
    }
    
    response = requests.post(url, json=payload, timeout=90)
    response.raise_for_status()
    res_json = response.json()
    
    # O endpoint retorna {"sucesso": True, "roteiro": {...}}
    if res_json.get("sucesso") and "roteiro" in res_json:
        return res_json["roteiro"]
        
    raise ValueError("Servidor Braço 1 retornou uma resposta sem sucesso ou sem campo 'roteiro'.")


def _refine_hook(roteiro: dict) -> dict:
    """
    Auto-Refinamento de Hook (Skill de Retenção Viral).
    Aplica gatilhos mentais se o hook original for fraco.
    """
    if not roteiro.get("blocks"):
        return roteiro

    first_narr = next((b for b in roteiro["blocks"] if (b.get("type") or b.get("tipo")) == "NARRACAO"), None)
    if first_narr:
        text = first_narr.get("text", "").strip()
        
        # Gatilhos de Curiosidade e Urgência
        triggers = [
            "O que ninguém te contou sobre",
            "Pare de ignorar isto:",
            "A verdade chocante que",
            "Você foi enganado sobre",
            "O segredo para dominar"
        ]
        
        # Se o hook não tiver impacto (curto ou sem pontuação forte)
        if len(text.split()) < 5 or ("?" not in text and "!" not in text):
            import random
            trigger = random.choice(triggers)
            first_narr["text"] = f"{trigger} {text[0].lower() + text[1:]}"
            print(f"[Módulo 1] Hook refinado para: {first_narr['text']}")
    
    return roteiro


def _is_similar_theme(tema_a: str, tema_b: str) -> bool:
    if not tema_a or not tema_b:
        return False
        
    import unicodedata
    def clean(s):
        s = str(s).lower()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^\w\s]", "", s)
        return s.strip()
        
    clean_a = clean(tema_a)
    clean_b = clean(tema_b)
    
    if not clean_a or not clean_b:
        return False
        
    if clean_a in clean_b or clean_b in clean_a:
        return True
        
    # Verifica interseção de palavras significativas (comprimento > 3)
    words_a = {w for w in clean_a.split() if len(w) > 3}
    words_b = {w for w in clean_b.split() if len(w) > 3}
    
    if not words_a or not words_b:
        return False
        
    intersection = words_a.intersection(words_b)
    # Se compartilham pelo menos 2 palavras significativas
    if len(intersection) >= 2:
        return True
        
    return False


def generate_script(tema: str) -> dict:
    """Fluxo principal de geracao de roteiro."""
    roteiro = None
    last_error = None

    # --- CAMADA 0: ROTEIRO MANUAL (JSON) ---
    if os.path.exists(MANUAL_JSON_PATH):
        print(f"[Módulo 1] Roteiro manual detectado em: {MANUAL_JSON_PATH}")
        try:
            with open(MANUAL_JSON_PATH, "r", encoding="utf-8") as f:
                roteiro_raw = json.load(f)
            roteiro = _validate_and_fix(roteiro_raw, tema)
            print(f"[Módulo 1] Roteiro manual carregado e validado com sucesso ({len(roteiro.get('blocks', []))} blocos).")
        except Exception as e:
            print(f"[Módulo 1] AVISO: Erro ao carregar roteiro manual: {e}. Caindo para geração automática...")

    # --- CAMADA 1: OLLAMA / BRAÇO 1 (LOCAL LLM) ---
    use_ollama = get_config("USE_OLLAMA", "False").lower() in ("true", "1", "yes")
    provider = get_config("LLM_PROVIDER", "ollama").lower()
    
    if use_ollama:
        print(f"[Módulo 1] Gerando roteiro localmente para: '{tema}' (Provedor primário: {provider})")
        
        # Tentativa 1: Tenta o provedor preferencial configurado
        try:
            if provider == "braco1":
                roteiro_raw = _call_braco1_fastapi(tema)
            else:
                roteiro_raw = _call_ollama_direct(tema)
            roteiro = _validate_and_fix(roteiro_raw, tema)
        except Exception as e:
            last_error = e
            print(f"[Módulo 1] Falha com provedor primário '{provider}': {e}. Tentando fallback local...")
            
            # Tentativa 2: Fallback local alternativo
            try:
                if provider == "braco1":
                    roteiro_raw = _call_ollama_direct(tema)
                else:
                    roteiro_raw = _call_braco1_fastapi(tema)
                roteiro = _validate_and_fix(roteiro_raw, tema)
            except Exception as e2:
                last_error = e2
                print(f"[Módulo 1] Falha total na geração local: {e2}. Prosseguindo para APIs externas se configuradas...")

    # --- CAMADA 2: OPENROUTER ---
    if not roteiro:
        api_key = get_config("OPENROUTER_API_KEY")
        if api_key:
            print(f"[Módulo 1] Iniciando Camada 2: OpenRouter...")
            for attempt in range(3):
                try:
                    roteiro_raw = _call_openrouter(tema)
                    roteiro = _validate_and_fix(roteiro_raw, tema)
                    break
                except Exception as e:
                    last_error = e
                    print(f"[Módulo 1] OpenRouter Tentativa {attempt+1}/3 falhou: {e}")
        else:
            print("[Módulo 1] OpenRouter ignorado (chave ausente no .env).")

    # --- CAMADA 3: FALHA TOTAL ---
    if not roteiro:
        print("======================================================================")
        print(" [ALERTA] TODAS AS APIs DE ROTEIRO FALHARAM ")
        print("======================================================================")
        print("1. O Ollama local e Braço 1 falharam (ou não estavam rodando).")
        print("2. O OpenRouter falhou (chave inválida, limite estourado ou fora do ar).")
        print("")
        print(" SOLUCAO DE EMERGENCIA (A Rota Antigravity):")
        print("   Copie o seu tema e peca para mim (sua IA) aqui mesmo no chat:")
        print(f"   'Antigravity, crie um roteiro JSON sobre: {tema}'")
        print("")
        print("   Depois, cole a resposta manualmente no arquivo: output/roteiro.json")
        print("   E rode o resto do pipeline! A gente nao para nunca.")
        print("======================================================================")
        raise ValueError(f"[Módulo 1] Geracao de roteiro falhou. Ultimo erro: {last_error}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Auto-Refinamento do Hook (Plano #2)
    roteiro = _refine_hook(roteiro)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(roteiro, f, ensure_ascii=False, indent=2)

    n_narracao = sum(1 for b in roteiro["blocks"] if (b.get("type") or b.get("tipo")) == "NARRACAO")
    n_visual   = sum(1 for b in roteiro["blocks"] if (b.get("type") or b.get("tipo")) == "VISUAL")
    print(f"[Módulo 1] Roteiro salvo: {n_narracao} blocos NARRACAO, {n_visual} blocos VISUAL")

    return roteiro

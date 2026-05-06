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

def get_config(key, default=None):
    return os.getenv(key, default)

SYSTEM_PROMPT = """
Você é um roteirista sênior de vídeos virais (estilo Dark Channel) e especialista em Growth Marketing.
Seu objetivo é criar um roteiro em JSON que prenda a atenção do início ao fim usando o framework CAPVI:

FRAMEWORK DE RETENÇÃO:
1. HOOK (Gancho): Os primeiros 3 segundos DEVEM parar o scroll. Use curiosidade, dor extrema ou quebra de padrão.
2. PROMESSA: Declare um benefício claro e imediato.
3. PROVA/CORPO: Entregue o conteúdo com ritmo rápido e autoridade.
4. CTA (Chamada): Direcione para uma ação específica.

ESTRUTURA TÉCNICA OBRIGATÓRIA:
1. Alterne blocos de NARRACAO (fala) e VISUAL (descrição da cena).
2. VISUAL: Use palavras-chave CURTAS e OBJETIVAS em INGLÊS (ex: 'ancient egypt pyramid', 'pharaoh face close up'). 
3. CONTEXTO VISUAL: Descreva a cena em português para guiar o tom do vídeo.
4. Tom: Misterioso, épico ou de revelação.
5. CONEXÃO: Cada VISUAL deve ilustrar EXATAMENTE o que a NARRACAO anterior ou seguinte está dizendo.

RETORNE APENAS O JSON PURO.
"""

USER_PROMPT_TEMPLATE = """
TEMA DO VÍDEO: {tema}

{contexto_referencia}

Gere um roteiro com 5 a 8 blocos de narração. 
O tempo total deve ser entre 30 a 50 segundos.
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
            raw = response.json()["choices"][0]["message"]["content"].strip()

            # Limpeza de Markdown
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$",          "", raw)

            return json.loads(raw)
            
        except Exception as e:
            last_error = e
            print(f"  > Falha com {model}: {e}")
            continue

    raise last_error


def _validate_and_fix(roteiro: dict, tema: str) -> dict:
    """Garante que o roteiro tenha os campos obrigatórios e mapeia variações de nomes."""
    roteiro.setdefault("tema", tema)
    roteiro.setdefault("titulo_sugerido", tema)
    
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


def _call_gemini(tema: str) -> dict:
    """Chama a API do Gemini via AI Studio e retorna o roteiro como dict."""
    api_key = get_config("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY nao definida no .env")
    
    # Tenta múltiplos modelos como fallback
    models = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.0-pro"]
    last_error = None

    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            # Adiciona contexto RAG se disponível
            contexto = _get_references_context(tema)
            prompt_completo = f"{SYSTEM_PROMPT}\n\n{USER_PROMPT_TEMPLATE.format(tema=tema, contexto_referencia=contexto)}"

            payload = {
                "contents": [{
                    "parts": [{"text": prompt_completo}]
                }]
            }

            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()

            data = response.json()
            raw = data['candidates'][0]['content']['parts'][0]['text'].strip()

            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$",          "", raw)

            return json.loads(raw)
        except Exception as e:
            last_error = e
            print(f"[Modulo 1] Tentativa com {model} falhou: {e}")
            continue
    
    raise last_error


def _refine_hook(roteiro: dict) -> dict:
    """
    Auto-Refinamento de Hook (Skill de Retenção Viral).
    Aplica gatilhos mentais se o hook original for fraco.
    """
    if not roteiro.get("blocks"):
        return roteiro

    first_narr = next((b for b in roteiro["blocks"] if b.get("type") == "NARRACAO"), None)
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
            print(f"[Modulo 1] Hook refinado para: {first_narr['text']}")
    
    return roteiro


def generate_script(tema: str) -> dict:
    """Fluxo principal de geracao de roteiro."""
    roteiro = None
    last_error = None

    # --- CAMADA 0: MANUAL (Prioridade Maxima) ---
    if os.path.exists(OUTPUT_PATH):
        print("[Modulo 1] Roteiro manual detectado! Lendo output/roteiro.json...")
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                roteiro_manual = json.load(f)
                # Verifica se o roteiro no arquivo e para o mesmo tema (opcional)
                # Se quiser forçar a geracao de um novo, apague o arquivo.
                roteiro = _validate_and_fix(roteiro_manual, tema)
                # Salva a versão corrigida para que os próximos módulos (TTS, etc) funcionem
                with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                    json.dump(roteiro, f, ensure_ascii=False, indent=2)
                print("[Modulo 1] Usando roteiro manual corrigido e salvo no disco.")
                return roteiro
        except Exception as e:
            print(f"[Modulo 1] Erro ao ler roteiro manual: {e}. Tentando APIs...")

    # --- CAMADA 1: OPENROUTER ---
    print(f"[Modulo 1] Gerando roteiro para: '{tema}'")
    for attempt in range(3):
        try:
            roteiro_raw = _call_openrouter(tema)
            roteiro = _validate_and_fix(roteiro_raw, tema)
            break
        except Exception as e:
            last_error = e
            print(f"[Modulo 1] OpenRouter Tentativa {attempt+1}/3 falhou: {e}")

    # --- CAMADA 2: GEMINI (FALLBACK) ---
    if not roteiro:
        print("\n[Modulo 1] Iniciando Camada 2: Google AI Studio (Gemini)...")
        try:
            roteiro_raw = _call_gemini(tema)
            roteiro = _validate_and_fix(roteiro_raw, tema)
        except Exception as e:
            last_error = e
            print(f"[Modulo 1] Falha na Camada 2 (Gemini): {e}")

    # --- CAMADA 3: FALHA TOTAL ---
    if not roteiro:
        print("======================================================================")
        print(" [ALERTA] TODAS AS APIs DE ROTEIRO FALHARAM ")
        print("======================================================================")
        print("1. O OpenRouter falhou (chave invalida, limite estourado ou fora do ar).")
        print("2. O Google AI Studio falhou (ou a chave nao foi configurada).")
        print("")
        print(" SOLUCAO DE EMERGENCIA (A Rota Antigravity):")
        print("   Copie o seu tema e peca para mim (sua IA) aqui mesmo no chat:")
        print(f"   'Antigravity, crie um roteiro JSON sobre: {tema}'")
        print("")
        print("   Depois, cole a resposta manualmente no arquivo: output/roteiro.json")
        print("   E rode o resto do pipeline! A gente nao para nunca.")
        print("======================================================================")
        raise ValueError(f"[Modulo 1] Geracao de roteiro falhou. Ultimo erro: {last_error}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Auto-Refinamento do Hook (Plano #2)
    roteiro = _refine_hook(roteiro)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(roteiro, f, ensure_ascii=False, indent=2)

    n_narracao = sum(1 for b in roteiro["blocks"] if (b.get("type") or b.get("tipo")) == "NARRACAO")
    n_visual   = sum(1 for b in roteiro["blocks"] if (b.get("type") or b.get("tipo")) == "VISUAL")
    print(f"[Modulo 1] Roteiro salvo: {n_narracao} blocos NARRACAO, {n_visual} blocos VISUAL")

    return roteiro

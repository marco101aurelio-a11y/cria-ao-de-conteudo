"""
Módulo 1 — Gerador de Roteiro (v3)
Gera roteiro em blocos NARRACAO/VISUAL via OpenRouter.
PATCH v3: keywords ultra-específicas por bloco + campo visual_context
           para o media_collector usar na busca semântica.

Schema de saída (roteiro.json):
{
  "tema": str,
  "titulo_sugerido": str,
  "blocks": [
    {
      "id": int,
      "type": "NARRACAO" | "VISUAL",
      "text": str,           // só em NARRACAO
      "keyword": str,        // só em VISUAL — palavra-chave principal (en)
      "keyword_fallback": str, // só em VISUAL — fallback mais genérico (en)
      "visual_context": str, // só em VISUAL — descrição curta do que deve aparecer
      "duration_hint": float // só em VISUAL — duração estimada em segundos
    },
    ...
  ]
}
"""
import os
import json
import re
import requests

MODULE_DIR  = os.path.dirname(__file__)
OUTPUT_DIR  = os.path.join(MODULE_DIR, "..", "output")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "roteiro.json")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL   = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

# ── Prompt de sistema ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Você é um roteirista especialista em dark videos virais para TikTok/Reels.
Sua tarefa: dado um tema, gerar um roteiro estruturado em JSON com blocos alternados de
NARRACAO e VISUAL.

REGRAS ABSOLUTAS:
1. Retorne SOMENTE o JSON. Nenhum texto antes ou depois. Nenhum markdown.
2. Alterne blocos: NARRACAO, VISUAL, NARRACAO, VISUAL... (mínimo 6 blocos, máximo 14).
3. Cada NARRACAO deve ter entre 1 e 3 frases curtas e de alto impacto.
4. Cada VISUAL deve ter:
   - "keyword": 2-4 palavras em INGLÊS extremamente específicas para busca em stock video.
     ERRADO: "dark mystery", "secret"
     CERTO: "vatican library ancient scrolls", "nuclear explosion test desert", "dark forest fog night"
   - "keyword_fallback": versão mais genérica em inglês (ex: "library old books", "explosion smoke")
   - "visual_context": 1 frase descrevendo o que deve aparecer visualmente (em português)
   - "duration_hint": número de segundos estimado para esse bloco (entre 2.0 e 6.0)
5. O tom deve ser sério, intrigante, levemente conspiratório — sem sensacionalismo vazio.
6. A estrutura deve começar com um HOOK forte na primeira NARRACAO.

Exemplo de bloco VISUAL correto:
{
  "id": 2,
  "type": "VISUAL",
  "keyword": "vatican secret archive underground",
  "keyword_fallback": "library ancient manuscripts",
  "visual_context": "Interior de arquivo secreto com documentos antigos empilhados",
  "duration_hint": 4.0
}
"""

USER_PROMPT_TEMPLATE = """Tema: {tema}

Gere o roteiro JSON completo seguindo as regras do sistema.
O JSON deve ter exatamente esta estrutura:
{{
  "tema": "{tema}",
  "titulo_sugerido": "...",
  "blocks": [ ... ]
}}"""


def _call_openrouter(tema: str) -> dict:
    """Chama a API do OpenRouter e retorna o roteiro como dict."""
    if not OPENROUTER_API_KEY:
        raise EnvironmentError("OPENROUTER_API_KEY não definida no .env")

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": USER_PROMPT_TEMPLATE.format(tema=tema)},
        ],
        "temperature": 0.7,
        "max_tokens": 2048,
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://darkvideopipeline.local",
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()

    raw = response.json()["choices"][0]["message"]["content"].strip()

    # Remove possíveis cercas de markdown que o modelo insira por engano
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$",          "", raw)

    return json.loads(raw)


def _validate_and_fix(roteiro: dict, tema: str) -> dict:
    """Garante que o roteiro tenha os campos obrigatórios."""
    roteiro.setdefault("tema", tema)
    roteiro.setdefault("titulo_sugerido", tema)
    roteiro.setdefault("blocks", [])

    for i, bloco in enumerate(roteiro["blocks"]):
        bloco.setdefault("id", i + 1)
        if bloco.get("type") == "VISUAL":
            bloco.setdefault("keyword",         tema[:30])
            bloco.setdefault("keyword_fallback", "dark cinematic")
            bloco.setdefault("visual_context",   "Imagem relacionada ao tema")
            bloco.setdefault("duration_hint",    4.0)
        if bloco.get("type") == "NARRACAO":
            bloco.setdefault("text", "")

    return roteiro


def generate_script(tema: str, max_retries: int = 3) -> dict:
    """
    Gera o roteiro e salva em output/roteiro.json.
    Retorna o roteiro como dict.
    """
    print(f"[Módulo 1] Gerando roteiro para: '{tema}'")

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            roteiro = _call_openrouter(tema)
            roteiro = _validate_and_fix(roteiro, tema)
            break
        except (json.JSONDecodeError, KeyError) as e:
            last_error = e
            print(f"[Módulo 1] Tentativa {attempt}/{max_retries} falhou (parse): {e}")
        except requests.HTTPError as e:
            last_error = e
            print(f"[Módulo 1] Tentativa {attempt}/{max_retries} falhou (HTTP): {e}")
            if attempt == max_retries:
                raise
    else:
        raise ValueError(f"[Módulo 1] Falhou após {max_retries} tentativas. Último erro: {last_error}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(roteiro, f, ensure_ascii=False, indent=2)

    n_narracao = sum(1 for b in roteiro["blocks"] if b["type"] == "NARRACAO")
    n_visual   = sum(1 for b in roteiro["blocks"] if b["type"] == "VISUAL")
    print(f"[Módulo 1] Roteiro salvo: {n_narracao} blocos NARRACAO, {n_visual} blocos VISUAL")

    return roteiro


if __name__ == "__main__":
    import sys
    tema = " ".join(sys.argv[1:]) or "O segredo que o Vaticano escondeu por séculos"
    r = generate_script(tema)
    print(json.dumps(r, ensure_ascii=False, indent=2))

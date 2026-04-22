"""
Módulo 1 — Gerador de Roteiro
Usa o OpenRouter (Llama 3.3 70B gratuito) para criar roteiros virais
no estilo dark video / TikTok negócios.

Rota do Flask: POST /api/module1/generate_script
Body JSON: { "tema": "seu tema aqui" }   (opcional — tem um padrão)
"""

import os
import json
import requests
from dotenv import load_dotenv

# Carrega as chaves do backend/.env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── Configuração ──────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"

# Modelos gratuitos em ordem de prioridade — se um der 429, tenta o próximo
MODELS_FALLBACK = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-4-31b-it:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "roteiro.json")

# ── System Prompt — Framework Staage ─────────────────────────
SYSTEM_PROMPT = """
Você é um roteirista especializado em dark videos virais para TikTok e Reels.
Seu estilo segue o Framework Staage: Hook dramático + Promessa + Prova + CTA.

Regras obrigatórias:
- Responda SOMENTE com um JSON válido, sem texto adicional e sem markdown.
- O JSON deve seguir exatamente este schema:

{
  "title": "string (título do vídeo)",
  "blocks": [
    { "type": "NARRACAO", "text": "string (máximo 2 frases curtas, tom dramático)" },
    { "type": "VISUAL",   "keyword": "string (palavra-chave em inglês para busca de vídeo stock)" }
  ]
}

Estrutura narrativa obrigatória:
1. Bloco NARRACAO: Hook com dado surpreendente ou pergunta provocativa
2. Bloco VISUAL: cena que reforça o gancho
3. Bloco NARRACAO: Promessa — o que o espectador vai descobrir
4. Bloco VISUAL: cena de tensão ou mistério
5. Bloco NARRACAO: Prova — dado, história ou reviravolta
6. Bloco VISUAL: cena de impacto
7. Bloco NARRACAO: Segundo nível de revelação (plot twist)
8. Bloco VISUAL: cena emocional
9. Bloco NARRACAO: Lição de moral ou insight de negócios
10. Bloco VISUAL: cena de resolução
11. Bloco NARRACAO: CTA — convite sutil para seguir ou comentar
12. Bloco VISUAL: cena final marcante

Regras de estilo:
- Tom: narrativo, dramático, insider — como se estivesse revelando um segredo
- Cada NARRACAO: máximo 2 frases curtas (30-50 palavras no total)
- Cada VISUAL: 1 a 3 palavras em inglês (ex: "dark office", "money rain", "city night")
- Total de blocos: entre 10 e 14
- NÃO use markdown, NÃO use blocos de código — apenas o JSON puro
""".strip()


def generate_script(tema: str) -> dict:
    """
    Gera um roteiro viral a partir de um tema.

    Args:
        tema: O assunto do vídeo (ex: "O segredo que os milionários escondem")

    Returns:
        dict com 'title' e 'blocks' — também salvo em output/roteiro.json
    """

    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY não encontrada no .env")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://dark-video-pipeline.local",
        "X-Title":       "Dark Video Pipeline V2",
    }

    # Tenta cada modelo da lista — se der 429 passa pro próximo
    for modelo in MODELS_FALLBACK:
        print(f"[Módulo 1] Tentando modelo: {modelo}")

        payload = {
            "model": modelo,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": f"Crie um roteiro dark video sobre: {tema}"},
            ],
        }

        try:
            response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)

            if response.status_code == 429:
                print(f"[Módulo 1] Modelo {modelo} com limite atingido (429). Tentando proximo...")
                continue

            if response.status_code == 404:
                print(f"[Módulo 1] Modelo {modelo} nao encontrado (404). Tentando proximo...")
                continue

            response.raise_for_status()

            raw_content = response.json()["choices"][0]["message"]["content"].strip()

            # Remove possíveis blocos de markdown (```json ... ```)
            if raw_content.startswith("```"):
                raw_content = raw_content.split("```")[1]
                if raw_content.startswith("json"):
                    raw_content = raw_content[4:]

            roteiro = json.loads(raw_content)

            # Validação mínima
            assert "title"  in roteiro, "Campo 'title' ausente"
            assert "blocks" in roteiro, "Campo 'blocks' ausente"
            assert len(roteiro["blocks"]) >= 8, f"Poucos blocos: {len(roteiro['blocks'])}"

            # Validação da alternância NARRACAO / VISUAL
            tipos = [b["type"] for b in roteiro["blocks"]]
            for i in range(len(tipos) - 1):
                assert tipos[i] != tipos[i + 1], f"Blocos do mesmo tipo em sequencia na posicao {i}"

            # Salva o resultado em output/roteiro.json
            os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(roteiro, f, ensure_ascii=False, indent=2)

            print(f"[Módulo 1] Roteiro gerado com {modelo}! {len(roteiro['blocks'])} blocos.")
            print(f"[Módulo 1] Salvo em: {OUTPUT_PATH}")
            return roteiro

        except (json.JSONDecodeError, AssertionError, KeyError) as e:
            print(f"[Módulo 1] Resposta invalida do modelo {modelo}: {e}")
            continue

    raise RuntimeError("[Módulo 1] Todos os modelos falharam. Verifique sua chave OpenRouter.")

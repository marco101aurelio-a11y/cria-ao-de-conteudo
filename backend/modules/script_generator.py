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

Regra de Ouro (Humanização, Coesão e Retenção Psicológica): 
1. Fluidez Narrativa (MUITO IMPORTANTE): O texto de todas as narrações juntas deve formar uma única história coesa, lógica e contínua. Uma fala deve se conectar perfeitamente com a próxima. Não use jargões repetitivos ou frases desconexas (não "fale coisa com coisa").
2. Tom de Especialista Revelador: A NARRACAO deve soar como um insider da indústria conversando naturalmente com o espectador.
3. Sofisticação e Naturalidade: Elimine qualquer gíria forçada ou estrutura robótica. A linguagem deve ser inteligente e conversacional.
4. Engenharia de Pausas: Use vírgulas e pontos finais para ditar o ritmo natural. Use reticências (...) APENAS para pausas de grande impacto (máximo 1 ou 2 vezes). O excesso de reticências confunde o TTS e quebra a fluidez da voz.
5. Cadência: Vá direto ao ponto. Uma frase deve puxar a outra.

Regras obrigatórias:
- Responda SOMENTE com um JSON válido, sem texto adicional e sem markdown.
- O JSON deve seguir exatamente este schema:

{
  "title": "string (título do vídeo)",
  "blocks": [
    { "type": "NARRACAO", "text": "string (texto contínuo e fluido)" },
    { "type": "VISUAL",   "keyword": "string (palavra-chave em inglês para busca de vídeo stock)" }
  ]
}

Estrutura narrativa fluida (mantenha a conexão lógica entre os blocos NARRACAO!):
1. Bloco NARRACAO: Hook (Gancho) focado em uma revelação surpreendente, direto ao ponto.
2. Bloco VISUAL: cena que reforça o gancho
3. Bloco NARRACAO: Desenvolvimento lógico que explica o gancho de forma fluida (continuando a frase anterior).
4. Bloco VISUAL: cena de desenvolvimento
5. Bloco NARRACAO: Evidência ou dado que comprove o que foi dito, sem quebrar o raciocínio.
6. Bloco VISUAL: cena de impacto
7. Bloco NARRACAO: O "grande detalhe" ou twist que amarra tudo.
8. Bloco VISUAL: cena reflexiva
9. Bloco NARRACAO: Conclusão rápida do pensamento.
10. Bloco VISUAL: cena de resolução
11. Bloco NARRACAO: CTA rápido e natural, fechando a história orgânicamente.
12. Bloco VISUAL: cena final marcante

Regras de estilo:
- Tom: natural, lógico e sem cortes abruptos. 
- Cada NARRACAO: deve ser a continuação exata da NARRACAO anterior. Se lermos todas as narrações em sequência, tem que soar como um texto de locução perfeito.
- Cada VISUAL: 2 a 4 palavras em inglês. MUITO IMPORTANTE: A palavra-chave DEVE refletir o contexto histórico ou temático da fala. Se a fala for sobre o passado (ex: século 20), inclua modificadores como "vintage", "black and white", ou "historical". Se for futuro, "futuristic". Seja literal e descritivo (ex: "vintage city black and white", "business team", "laptop working"). EVITE conceitos abstratos ou filosóficos.
- Total de blocos: entre 10 e 14
- NÃO use markdown, NÃO use blocos de código — apenas o JSON puro.
""".strip()


def generate_script(tema: str) -> dict:
    """
    Gera um roteiro viral a partir de um tema com sistema de 3 camadas de Fallback:
    1. OpenRouter
    2. Google AI Studio (Gemini 1.5 Flash)
    3. Antigravity (Aviso visual para o usuário pedir no chat)
    """
    raw_content = None

    # ==========================================
    # CAMADA 1: OPENROUTER
    # ==========================================
    if OPENROUTER_API_KEY and OPENROUTER_API_KEY.startswith("sk-or"):
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://dark-video-pipeline.local",
            "X-Title":       "Dark Video Pipeline V2",
        }

        for modelo in MODELS_FALLBACK:
            print(f"[Módulo 1] Tentando OpenRouter ({modelo})...")
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

                if response.status_code == 401:
                    print(f"[Módulo 1] [ERRO] Chave OpenRouter inválida (Erro 401)!")
                    break # Pula para a próxima API

                if response.status_code in [400, 404, 429]:
                    print(f"[Módulo 1] Modelo {modelo} falhou (Código {response.status_code}). Tentando próximo...")
                    continue

                response.raise_for_status()
                raw_content = response.json()["choices"][0]["message"]["content"].strip()
                print(f"[Módulo 1] Roteiro gerado com sucesso via OpenRouter ({modelo})!")
                break # Sucesso, sai do loop

            except Exception as e:
                print(f"[Módulo 1] Falha de conexão no OpenRouter: {e}")
                continue
    else:
        print("[Módulo 1] Chave OpenRouter ausente ou inválida. Pulando para Camada 2...")

    # ==========================================
    # CAMADA 2: GOOGLE AI STUDIO (GEMINI)
    # ==========================================
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not raw_content and GEMINI_API_KEY:
        print("\n[Módulo 1] Iniciando Camada 2: Google AI Studio (gemini-1.5-flash)...")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        # O Gemini requer que o texto seja passado como texto normal
        prompt_completo = f"{SYSTEM_PROMPT}\n\nCrie um roteiro dark video sobre: {tema}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt_completo}]}],
            "generationConfig": {"temperature": 0.7}
        }
        
        try:
            response = requests.post(url, json=payload, timeout=60)
            if response.status_code == 200:
                raw_content = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                print(f"[Módulo 1] Roteiro gerado com sucesso via Google AI Studio!")
            else:
                print(f"[Módulo 1] Google AI Studio falhou. Código: {response.status_code}")
                print(f"[Módulo 1] Detalhe: {response.text}")
        except Exception as e:
            print(f"[Módulo 1] Falha de conexão no Google AI Studio: {e}")
    elif not raw_content:
        print("[Módulo 1] Chave GEMINI_API_KEY ausente. Pulando para Camada 3...")

    # ==========================================
    # CAMADA 3: ANTIGRAVITY (FALLBACK FINAL)
    # ==========================================
    if not raw_content:
        print("\n" + "="*70)
        print("🚨 [ALERTA VERMELHO] TODAS AS APIs DE ROTEIRO FALHARAM 🚨")
        print("="*70)
        print("1. O OpenRouter falhou (chave inválida, limite estourado ou fora do ar).")
        print("2. O Google AI Studio falhou (ou a chave não foi configurada).")
        print("\n👉 SOLUÇÃO DE EMERGÊNCIA (A Rota Antigravity 🤭):")
        print("   Copie o seu tema e peça para mim (sua IA) aqui mesmo no chat:")
        print(f"   'Antigravity, crie um roteiro JSON sobre: {tema}'")
        print("   ")
        print("   Depois, cole a resposta manualmente no arquivo: output/roteiro.json")
        print("   E rode o resto do pipeline! A gente não para nunca.")
        print("="*70 + "\n")

        # Fallback Automático Antigravity
        if os.path.exists(OUTPUT_PATH):
            print("🚀 Roteiro manual detectado! Lendo o arquivo existente em output/roteiro.json...")
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)

        raise RuntimeError("Geração de Roteiro falhou. Leia as instruções acima.")

    # ==========================================
    # PROCESSAMENTO FINAL DO JSON
    # ==========================================
    try:
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

        # Salva o resultado em output/roteiro.json
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(roteiro, f, ensure_ascii=False, indent=2)

        print(f"[Módulo 1] Roteiro salvo em: {OUTPUT_PATH}")
        return roteiro

    except Exception as e:
        print(f"[Módulo 1] Erro fatal ao processar o JSON gerado pela IA: {e}")
        raise RuntimeError("O JSON gerado pela IA é inválido.")

"""
Módulo 2 — Gerador de Áudio (TTS)
Converte o roteiro em áudio usando Edge TTS (vozes neurais gratuitas da Microsoft).
É muito superior ao Kokoro para português (pt-BR) e não requer download de modelos pesados.

Voz escolhida: pt-BR-AntonioNeural (Tom sério/masculino ideal para dark videos)
"""

import os
import json
import asyncio
import edge_tts

# ── Configuração ──────────────────────────────────────────────
MODULE_DIR = os.path.dirname(__file__)
ROTEIRO_PATH = os.path.join(MODULE_DIR, "..", "output", "roteiro.json")
OUTPUT_AUDIO = os.path.join(MODULE_DIR, "..", "output", "narration.mp3")

# Vozes pt-BR disponíveis no Edge TTS:
# pt-BR-AntonioNeural (Masculino - ideal para dark video)
# pt-BR-FranciscaNeural (Feminina)
# pt-BR-ThalitaNeural (Feminina)
VOICE = "pt-BR-AntonioNeural"


async def async_generate_audio(roteiro_data: dict) -> str:
    """Função assíncrona que processa o roteiro e chama o Edge TTS."""
    print("[Módulo 2] Extraindo falas do roteiro...")
    
    falas = []
    for bloco in roteiro_data.get("blocks", []):
        if bloco.get("type") == "NARRACAO":
            # Removemos quebras de linha para a fala ficar fluida
            texto = bloco.get("text", "").replace("\n", " ").strip()
            if texto:
                # Garante que o bloco termine com pontuação para o TTS fazer a pausa correta
                if texto[-1] not in ".!?,;...":
                    texto += "."
                falas.append(texto)
    
    if not falas:
        raise ValueError("Nenhum bloco 'NARRACAO' encontrado no roteiro.")

    # Junta todas as falas
    texto_completo = " ".join(falas)
    
    print(f"[Módulo 2] Texto final montado ({len(texto_completo)} caracteres).")
    print(f"[Módulo 2] Gerando áudio com a voz: {VOICE}...")

    # Instancia o TTS ajustando o rate (velocidade). 
    # Dark videos costumam ter locução ligeiramente mais rápida (+5% a +10%)
    communicate = edge_tts.Communicate(texto_completo, VOICE, rate="+5%")
    
    os.makedirs(os.path.dirname(OUTPUT_AUDIO), exist_ok=True)
    await communicate.save(OUTPUT_AUDIO)
    
    print(f"[Módulo 2] Audio salvo com sucesso em: {OUTPUT_AUDIO}")
    return OUTPUT_AUDIO


def generate_audio(roteiro_data: dict = None) -> dict:
    """
    Função síncrona wrapper (para ser chamada pelo Flask / server.py).
    
    Args:
        roteiro_data: dict contendo o roteiro. Se None, lê do roteiro.json.
    """
    if roteiro_data is None:
        if not os.path.exists(ROTEIRO_PATH):
            raise FileNotFoundError(f"Roteiro não encontrado em: {ROTEIRO_PATH}")
        with open(ROTEIRO_PATH, "r", encoding="utf-8") as f:
            roteiro_data = json.load(f)

    # Executa o loop assíncrono
    caminho_final = asyncio.run(async_generate_audio(roteiro_data))
    
    return {
        "audio_path": caminho_final,
        "voice": VOICE,
        "status": "success"
    }

if __name__ == "__main__":
    # Teste isolado do módulo
    try:
        generate_audio()
    except Exception as e:
        print(f"Erro no teste isolado: {e}")

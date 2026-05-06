"""
Módulo 2 — Gerador de Áudio (TTS) — v3
Converte o roteiro em narração usando Edge TTS (vozes neurais gratuitas da Microsoft).
Superior ao Kokoro para pt-BR — não requer download de modelos pesados.

Voz padrão: pt-BR-AntonioNeural (masculino, sério — ideal para dark video)
Outras opções: pt-BR-FranciscaNeural, pt-BR-ThalitaNeural

Dependências:
  pip install edge-tts
Variáveis de ambiente:
  TTS_ENGINE   = "local" (edge-tts, default) | "api" (ElevenLabs)
  ELEVENLABS_API_KEY  (só necessário se TTS_ENGINE=api)
  ELEVENLABS_VOICE_ID (default: "pNInz6obpgDQGcFmaJgB" — Adam)
  TTS_VOICE    sobrescreve a voz Edge TTS padrão
  TTS_RATE     velocidade, ex: "+5%", "0%", "-10%"  (default: "+5%")
"""
import os
import json
import asyncio
from pathlib import Path

MODULE_DIR   = os.path.dirname(__file__)
OUTPUT_DIR   = os.path.join(MODULE_DIR, "..", "output")
ROTEIRO_PATH = os.path.join(OUTPUT_DIR, "roteiro.json")
OUTPUT_AUDIO = os.path.join(OUTPUT_DIR, "narration.mp3")

TTS_ENGINE = os.getenv("TTS_ENGINE", "local")
TTS_VOICE  = os.getenv("TTS_VOICE",  "pt-BR-AntonioNeural")
TTS_RATE   = os.getenv("TTS_RATE",   "+5%")


# ── Edge TTS (local, grátis) ──────────────────────────────────────────────────

async def _edge_tts(texto: str, output_path: str) -> None:
    import edge_tts  # pip install edge-tts
    communicate = edge_tts.Communicate(texto, TTS_VOICE, rate=TTS_RATE)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    await communicate.save(output_path)


# ── ElevenLabs (API paga) ─────────────────────────────────────────────────────

def _elevenlabs_tts(texto: str, output_path: str) -> None:
    import requests
    api_key  = os.getenv("ELEVENLABS_API_KEY", "")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
    if not api_key:
        raise EnvironmentError("ELEVENLABS_API_KEY não definida no .env")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    r = requests.post(
        url,
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": texto,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=60,
    )
    r.raise_for_status()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(r.content)


# ── Extração de texto do roteiro ───────────────────────────────────────────────

def _extract_narracao(roteiro_data: dict) -> str:
    falas = []
    for bloco in roteiro_data.get("blocks", []):
        if bloco.get("type") == "NARRACAO":
            texto = bloco.get("text", "").replace("\n", " ").strip()
            if texto:
                if texto[-1] not in ".!?,;…":
                    texto += "."
                falas.append(texto)
    if not falas:
        raise ValueError("[Módulo 2] Nenhum bloco NARRACAO encontrado no roteiro.")
    return " ".join(falas)


# ── Entry point ────────────────────────────────────────────────────────────────

def generate_audio(roteiro_data: dict = None) -> dict:
    """
    Gera narration.mp3 a partir do roteiro.
    Retorna dict com audio_path e status.
    """
    if roteiro_data is None:
        if not Path(ROTEIRO_PATH).exists():
            raise FileNotFoundError(f"Roteiro não encontrado: {ROTEIRO_PATH}")
        with open(ROTEIRO_PATH, "r", encoding="utf-8") as f:
            roteiro_data = json.load(f)

    texto = _extract_narracao(roteiro_data)
    print(f"[Módulo 2] Texto extraído ({len(texto)} chars). Engine: {TTS_ENGINE}")

    if TTS_ENGINE == "api":
        print(f"[Módulo 2] Usando ElevenLabs...")
        _elevenlabs_tts(texto, OUTPUT_AUDIO)
    else:
        print(f"[Módulo 2] Usando Edge TTS (voz: {TTS_VOICE}, rate: {TTS_RATE})...")
        asyncio.run(_edge_tts(texto, OUTPUT_AUDIO))

    print(f"[Módulo 2] Áudio salvo: {OUTPUT_AUDIO}")
    return {"audio_path": OUTPUT_AUDIO, "engine": TTS_ENGINE, "status": "success"}


if __name__ == "__main__":
    generate_audio()

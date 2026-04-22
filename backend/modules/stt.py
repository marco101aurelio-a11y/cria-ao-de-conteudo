"""
Módulo 3 — Speech-to-Text (STT) e Timestamps
Usa o OpenAI Whisper (local) para transcrever o áudio gerado no Módulo 2
e extrair os timestamps precisos de cada palavra.
Isso é essencial para a animação das legendas estilo Hormozi.
"""

import os
import json
import warnings
import whisper

# Ignora os warnings do Whisper/Torch sobre FP16 em CPU
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")

# ── Configuração ──────────────────────────────────────────────
MODULE_DIR = os.path.dirname(__file__)
AUDIO_PATH = os.path.join(MODULE_DIR, "..", "output", "narration.mp3")
OUTPUT_JSON = os.path.join(MODULE_DIR, "..", "output", "timestamps.json")


def generate_timestamps(audio_path: str = None) -> dict:
    if audio_path is None:
        audio_path = AUDIO_PATH

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Áudio não encontrado em: {audio_path}")

    print("[Módulo 3] Carregando modelo Whisper (base)...")
    # Usa o modelo 'base' que é rápido e ótimo para extração de tempo
    # quando o áudio já é muito claro (que é o caso de vozes TTS)
    model = whisper.load_model("base")
    
    print("[Módulo 3] Transcrevendo e alinhando palavras...")
    
    # 'word_timestamps=True' é o segredo para ter o tempo exato de cada palavra
    result = model.transcribe(audio_path, word_timestamps=True, language="pt")

    words_data = []
    
    # Extrai os timestamps palavra por palavra
    for segment in result.get("segments", []):
        for word in segment.get("words", []):
            words_data.append({
                "word": word["word"].strip(),
                "start": word["start"],
                "end": word["end"]
            })

    output_data = {
        "text": result["text"],
        "words": words_data
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"[Módulo 3] Transcrição concluída! {len(words_data)} palavras mapeadas.")
    print(f"[Módulo 3] Timestamps salvos em: {OUTPUT_JSON}")

    return output_data

if __name__ == "__main__":
    try:
        generate_timestamps()
    except Exception as e:
        print(f"Erro no teste isolado: {e}")

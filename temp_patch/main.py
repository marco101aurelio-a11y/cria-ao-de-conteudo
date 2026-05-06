"""
main.py — Orquestrador do Pipeline Dark Video
PATCH v2: integra clip_map multi-clip e stt com merge de tokens

Uso:
  python main.py --tema "O segredo que o Vaticano escondeu por séculos"
  python main.py --tema "..." --tts-engine api        # usa ElevenLabs
  python main.py --tema "..." --device cuda           # Whisper com GPU
"""

import argparse
import os
import sys

from dotenv import load_dotenv
load_dotenv()


def check_env():
    """Valida variáveis obrigatórias antes de iniciar."""
    required = ["OPENROUTER_API_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"[ERRO] Variáveis de ambiente ausentes no .env: {', '.join(missing)}")
        sys.exit(1)

    tts = os.getenv("TTS_ENGINE", "local")
    if tts == "api" and not os.getenv("ELEVENLABS_API_KEY"):
        print("[ERRO] TTS_ENGINE=api requer ELEVENLABS_API_KEY no .env")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Pipeline Dark Video com Narração")
    parser.add_argument("--tema", required=True, help="Tema do vídeo")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                        help="Device para Whisper STT (default: cpu)")
    parser.add_argument("--tts-engine", default=None, choices=["local", "api"],
                        help="Sobrescreve ENV TTS_ENGINE")
    args = parser.parse_args()

    if args.tts_engine:
        os.environ["TTS_ENGINE"] = args.tts_engine

    check_env()
    os.makedirs("output/clips", exist_ok=True)

    print("\n" + "═" * 50)
    print(f"  DARK VIDEO PIPELINE — v2")
    print(f"  Tema: {args.tema}")
    print(f"  TTS:  {os.getenv('TTS_ENGINE', 'local')}")
    print(f"  STT:  whisper ({args.device})")
    print("═" * 50 + "\n")

    # ── MÓDULO 1: Roteiro ────────────────────────────────────────────────────
    print("▶ MÓDULO 1 — Gerando roteiro via OpenRouter...")
    from modules.script_generator import generate_script
    roteiro = generate_script(tema=args.tema)
    print(f"  Roteiro gerado: {len(roteiro['blocks'])} blocos\n")

    # ── MÓDULO 2: TTS ────────────────────────────────────────────────────────
    print("▶ MÓDULO 2 — Gerando narração (TTS)...")
    from modules.tts import generate_audio
    generate_audio()
    print("  narration.mp3 salvo\n")

    # ── MÓDULO 3: STT + Timestamps ───────────────────────────────────────────
    print("▶ MÓDULO 3 — Transcrevendo e gerando timestamps...")
    from modules.stt import transcribe, build_srt
    transcribe(device=args.device)
    build_srt()
    print("  timestamps.json e subtitles.srt salvos\n")

    # ── MÓDULO 4: B-Roll ─────────────────────────────────────────────────────
    print("▶ MÓDULO 4 — Coletando B-Roll e música...")
    from modules.media_collector import collect_clips, download_background_music
    import json
    clip_map = collect_clips()
    download_background_music()
    with open("output/clip_map.json", "w") as f:
        json.dump(clip_map, f, indent=2)
    print("  clip_map.json e background.mp3 salvos\n")

    # ── MÓDULO 5: Montagem ───────────────────────────────────────────────────
    print("▶ MÓDULO 5 — Montando vídeo final...")
    from modules.video_assembler import assemble
    output_path = assemble()

    print("\n" + "═" * 50)
    print(f"  ✅ CONCLUÍDO: {output_path}")
    print("═" * 50 + "\n")


if __name__ == "__main__":
    main()

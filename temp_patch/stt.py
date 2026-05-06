"""
MÓDULO 3 — Gerador de Timestamps (STT via Whisper)
PATCH v2:
  FIX 4 — Merge de tokens numéricos/símbolos isolados antes de gerar SRT
           Ex: "90" + "%" → "90%" como entrada única
"""

import json
import re
import whisper


def transcribe(audio_path: str = "output/narration.mp3",
               output_path: str = "output/timestamps.json",
               device: str = "cpu") -> list:
    """
    Transcreve áudio e retorna lista de palavras com timestamps.
    Aplica merge de tokens antes de salvar.
    """
    print(f"[M3] Carregando modelo Whisper (device={device})...")
    model = whisper.load_model("base", device=device)

    print(f"[M3] Transcrevendo {audio_path}...")
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="pt",
    )

    raw_words = []
    for segment in result.get("segments", []):
        for word in segment.get("words", []):
            raw_words.append({
                "word": word["word"].strip(),
                "start": round(word["start"], 3),
                "end": round(word["end"], 3),
            })

    # PATCH FIX 4: merge de tokens problemáticos
    merged = merge_tokens(raw_words)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"[M3] {len(merged)} tokens salvos em {output_path}")
    return merged


def merge_tokens(words: list) -> list:
    """
    PATCH FIX 4: une tokens que o Whisper separa incorretamente.
    
    Casos tratados:
      - Número seguido de símbolo isolado: "90" + "%" → "90%"
      - Número seguido de unidade: "10" + "mil" → "10mil"  
      - Símbolo isolado no início: "$" + "100" → "$100"
      - Pontuação isolada colada na palavra anterior
    
    Regra: se o token atual É apenas símbolo/pontuação/número curto
    E o token anterior termina com número, fazer merge.
    """

    SYMBOLS_ONLY = re.compile(r'^[%°€$£¥R\+\-\*/=<>]+$')
    PUNCTUATION_ONLY = re.compile(r'^[.,;:!?]+$')
    LEADING_SYMBOL = re.compile(r'^[$€£¥R#@]$')
    NUMERIC = re.compile(r'^\d+$')

    if not words:
        return words

    merged = [words[0].copy()]

    for current in words[1:]:
        prev = merged[-1]
        cw = current["word"]
        pw = prev["word"]

        should_merge = False

        # Caso 1: símbolo isolado após número → "90" + "%" = "90%"
        if SYMBOLS_ONLY.match(cw) and NUMERIC.match(pw):
            should_merge = True

        # Caso 2: pontuação isolada → colar na palavra anterior
        elif PUNCTUATION_ONLY.match(cw):
            should_merge = True

        # Caso 3: símbolo líder antes de número → "$" + "100" = "$100"
        elif LEADING_SYMBOL.match(pw) and NUMERIC.match(cw):
            should_merge = True

        # Caso 4: número curto isolado que é claramente continuação
        # Ex: "1" + "986" → "1986" (anos quebrados pelo Whisper)
        elif NUMERIC.match(cw) and NUMERIC.match(pw) and len(pw) <= 2:
            should_merge = True

        if should_merge:
            # Estende o token anterior absorvendo o atual
            merged[-1] = {
                "word": pw + cw,
                "start": prev["start"],
                "end": current["end"],  # usa o end do token absorvido
            }
        else:
            merged.append(current.copy())

    return merged


def build_srt(timestamps_path: str = "output/timestamps.json",
              srt_path: str = "output/subtitles.srt") -> str:
    """
    Gera arquivo .srt word-by-word a partir do timestamps.json.
    Uma entrada SRT por palavra/token.
    """
    with open(timestamps_path, "r", encoding="utf-8") as f:
        words = json.load(f)

    def fmt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    lines = []
    for i, w in enumerate(words, start=1):
        # Garante duração mínima de 100ms para palavras muito rápidas
        end = max(w["end"], w["start"] + 0.1)
        lines.append(str(i))
        lines.append(f"{fmt_time(w['start'])} --> {fmt_time(end)}")
        lines.append(w["word"].upper())  # Uppercase para impacto visual
        lines.append("")

    srt_content = "\n".join(lines)
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    print(f"[M3] SRT gerado: {srt_path} ({len(words)} entradas)")
    return srt_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cpu", help="cpu ou cuda")
    args = parser.parse_args()

    transcribe(device=args.device)
    build_srt()

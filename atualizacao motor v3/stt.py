"""
Módulo 3 — STT + Gerador de Legendas (v3)
Transcreve narration.mp3 com Whisper e gera subtitles.ass (karaoke word-by-word).

PATCH v3:
  - merge_tokens(): une tokens quebrados (90 + % → 90%, 1 + 986 → 1986, pontuação isolada)
  - build_ass(): gera arquivo ASS com estilo karaoke
      palavra ATUAL: amarelo bold + fundo semitransparente
      palavras anteriores: branco normal
  - Posição: terço inferior da tela (MarginV alto)
  - FontSize: 24 (legível em mobile)

Dependências:
  pip install openai-whisper
Variáveis de ambiente:
  WHISPER_MODEL  (default: base)
"""
import os
import json
import re
from pathlib import Path

MODULE_DIR      = os.path.dirname(__file__)
OUTPUT_DIR      = os.path.join(MODULE_DIR, "..", "output")
AUDIO_PATH      = os.path.join(OUTPUT_DIR, "narration.mp3")
TIMESTAMPS_PATH = os.path.join(OUTPUT_DIR, "timestamps.json")
ASS_PATH        = os.path.join(OUTPUT_DIR, "subtitles.ass")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")


# ── Merge de tokens ────────────────────────────────────────────────────────────

_PUNCT = re.compile(r"^[.,!?;:…]+$")
_DIGIT = re.compile(r"^\d+$")
_SYMBL = re.compile(r"^[%$€£°]+$")


def merge_tokens(words: list) -> list:
    """
    Une tokens que o Whisper divide incorretamente.
    Ex: ["90", "%"] → ["90%"]
        ["1", "986"] → ["1986"]
        ["Hello", ","] → ["Hello,"]
    """
    if not words:
        return words

    merged = [words[0].copy()]

    for token in words[1:]:
        prev  = merged[-1]
        pw    = prev["word"]
        tw    = token["word"]

        should_merge = (
            # pontuação isolada cola na palavra anterior
            _PUNCT.match(tw.strip())
            # símbolo (%, $, °) logo após dígito
            or (_SYMBL.match(tw.strip()) and _DIGIT.match(pw.strip()))
            # dois segmentos de dígitos formam número único
            or (_DIGIT.match(tw.strip()) and _DIGIT.match(pw.strip()) and len(pw) <= 3)
        )

        if should_merge:
            prev["word"] = pw + tw
            prev["end"]  = token["end"]
        else:
            merged.append(token.copy())

    return merged


# ── Transcrição ────────────────────────────────────────────────────────────────

def transcribe(device: str = "cpu") -> list:
    """
    Transcreve AUDIO_PATH com Whisper.
    Salva timestamps.json e retorna lista de word-dicts.
    """
    import whisper  # importação lazy — não falha se não instalado no momento do import

    print(f"[Módulo 3] Carregando Whisper '{WHISPER_MODEL}' no dispositivo '{device}'...")
    model = whisper.load_model(WHISPER_MODEL, device=device)

    print(f"[Módulo 3] Transcrevendo {AUDIO_PATH}...")
    result = model.transcribe(
        AUDIO_PATH,
        word_timestamps=True,
        language="pt",
    )

    # Extrai todos os words de todos os segmentos
    words = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            words.append({
                "word":  w["word"].strip(),
                "start": round(w["start"], 3),
                "end":   round(w["end"],   3),
            })

    words = merge_tokens(words)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(TIMESTAMPS_PATH, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

    print(f"[Módulo 3] timestamps.json salvo ({len(words)} tokens após merge).")
    return words


# ── Geração ASS ────────────────────────────────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    """Converte segundos para formato ASS: H:MM:SS.cc"""
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    cs = int(round((seconds % 1) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# Quantas palavras mostrar por "linha" na tela
WORDS_PER_LINE = 5


def build_ass(timestamps_path: str = None, output_path: str = None) -> str:
    """
    Gera arquivo ASS com efeito karaoke:
      - Mostra grupo de WORDS_PER_LINE palavras por vez
      - Palavra atual: amarelo + bold
      - Palavras do grupo já ditas: branco normal
      - Próximo grupo aparece quando começa sua primeira palavra

    Retorna path do arquivo ASS gerado.
    """
    ts_path  = timestamps_path or TIMESTAMPS_PATH
    out_path = output_path     or ASS_PATH

    with open(ts_path, "r", encoding="utf-8") as f:
        words = json.load(f)

    if not words:
        raise ValueError("[Módulo 3] timestamps.json está vazio.")

    # ── Cabeçalho ASS ──────────────────────────────────────────────────────────
    header = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Rounded MT Bold,26,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,-1,0,0,0,100,100,0,0,3,2,0,2,60,60,240,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines_ass = []

    # Divide em grupos de WORDS_PER_LINE
    groups = [words[i:i + WORDS_PER_LINE] for i in range(0, len(words), WORDS_PER_LINE)]

    for group in groups:
        group_start = group[0]["start"]
        group_end   = group[-1]["end"]

        # Para cada palavra do grupo, gera uma linha ASS
        for focus_idx, focus_word in enumerate(group):
            seg_start = focus_word["start"]
            seg_end   = focus_word["end"]

            # Constrói o texto da linha com highlight na palavra atual
            parts = []
            for i, w in enumerate(group):
                text = w["word"].upper()
                if i < focus_idx:
                    # já dita — branco normal
                    parts.append(f"{{\\c&HFFFFFF&\\b0}}{text}")
                elif i == focus_idx:
                    # atual — amarelo bold
                    parts.append(f"{{\\c&H00FFFF&\\b1}}{text}")
                else:
                    # futura — cinza esmaecido
                    parts.append(f"{{\\c&H888888&\\b0}}{text}")

            line_text = " ".join(parts)
            t_start   = _fmt_time(seg_start)
            t_end     = _fmt_time(seg_end)
            lines_ass.append(
                f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{line_text}"
            )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(lines_ass))
        f.write("\n")

    print(f"[Módulo 3] subtitles.ass salvo ({len(lines_ass)} linhas).")
    return out_path


if __name__ == "__main__":
    transcribe()
    build_ass()

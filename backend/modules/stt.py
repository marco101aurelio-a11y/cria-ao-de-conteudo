"""
Módulo 3 — STT + Gerador de Legendas (v3)
Transcreve narration.mp3 com Faster-Whisper e gera:
  - timestamps.json  (palavras + timestamps word-by-word)
  - silences.json    (pontos de silêncio >= 300ms para corte orgânico)
  - subtitles.ass    (legendas karaoke word-by-word)

PATCH v3.1 (Corte no Respiro):
  - Extrai silêncios naturais entre palavras (gaps >= 0.3s)
  - Salva silences.json para uso pelo video_assembler.py
  - Permite cortes de clipe sincronizados com as pausas da narração

Dependências:
  pip install faster-whisper
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
SILENCES_PATH   = os.path.join(OUTPUT_DIR, "silences.json")
ASS_PATH        = os.path.join(OUTPUT_DIR, "subtitles.ass")

# Pausa mínima entre palavras para ser considerada um "respiro" (em segundos)
SILENCE_THRESHOLD = 0.30

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
    Transcreve AUDIO_PATH com Faster-Whisper (4x mais rápido).
    Salva timestamps.json e retorna lista de word-dicts.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError("faster-whisper não instalado. Rode: pip install faster-whisper")

    # Para CPU, compute_type="int8" é muito mais rápido e usa menos memória
    compute_type = "float16" if device == "cuda" else "int8"
    
    print(f"[Módulo 3] Carregando Faster-Whisper '{WHISPER_MODEL}' no dispositivo '{device}' (compute={compute_type})...")
    model = WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type)

    print(f"[Módulo 3] Transcrevendo {AUDIO_PATH}...")
    segments, info = model.transcribe(
        AUDIO_PATH,
        language="pt",
        word_timestamps=True,
    )

    # Extrai todos os words de todos os segmentos
    # segments é um generator, precisamos iterar sobre ele
    words = []
    for segment in segments:
        for w in segment.words:
            words.append({
                "word":  w.word.strip(),
                "start": round(w.start, 3),
                "end":   round(w.end,   3),
            })

    words = merge_tokens(words)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(TIMESTAMPS_PATH, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

    # ── Extrai silêncios (gaps entre palavras >= SILENCE_THRESHOLD) ────────────
    silences = []
    for i in range(1, len(words)):
        gap_start = words[i - 1]["end"]
        gap_end   = words[i]["start"]
        gap_dur   = round(gap_end - gap_start, 3)
        if gap_dur >= SILENCE_THRESHOLD:
            silences.append({
                "start":    gap_start,
                "end":      gap_end,
                "duration": gap_dur,
            })

    with open(SILENCES_PATH, "w", encoding="utf-8") as f:
        json.dump(silences, f, ensure_ascii=False, indent=2)

    print(f"[Módulo 3] timestamps.json salvo ({len(words)} tokens após merge).")
    print(f"[Módulo 3] silences.json salvo ({len(silences)} respiros detectados >= {SILENCE_THRESHOLD}s).")
    return words


# ── Ground Truth Alignment ─────────────────────────────────────────────────────────────────────────

def build_ass_ground_truth(roteiro_data: dict, output_path: str = None) -> str:
    """
    Gera o arquivo ASS usando o texto EXATO do roteiro (Ground Truth) como legenda,
    mas aproveitando os timestamps do Whisper como régua de tempo.

    Vantagem: Elimina 100% dos erros de português do Whisper na tela.
    Método: mapeamento proporcional de palavras do roteiro -> slots de tempo do Whisper.
    """
    out_path = output_path or ASS_PATH

    # Carrega timestamps do Whisper (só usamos para extrair o ritmo de tempo)
    if not os.path.exists(TIMESTAMPS_PATH):
        raise FileNotFoundError("[Módulo 3] timestamps.json não encontrado. Rode transcribe() primeiro.")

    with open(TIMESTAMPS_PATH, "r", encoding="utf-8") as f:
        whisper_words = json.load(f)

    if not whisper_words:
        raise ValueError("[Módulo 3] timestamps.json está vazio.")

    # Extrai texto limpo do roteiro (blocos NARRACAO)
    script_words = []
    for bloco in roteiro_data.get("blocks", []):
        tipo = bloco.get("type") or bloco.get("tipo")
        if tipo == "NARRACAO":
            texto = (bloco.get("text") or bloco.get("conteudo") or "").strip()
            if texto:
                # Separa palavras preservando pontuação colada
                palavras = texto.split()
                script_words.extend(palavras)

    if not script_words:
        # Fallback: se não tiver roteiro, usa o Whisper mesmo
        print("[Módulo 3] Roteiro sem NARRACAO - fallback para Whisper puro.")
        return build_ass(output_path=out_path)

    # Mapeia palavras do roteiro para slots de tempo do Whisper por proporção
    # Ex: roteiro tem 100 palavras, Whisper tem 95 slots -> mapeamento linear
    n_script  = len(script_words)
    n_whisper = len(whisper_words)

    aligned_words = []
    for i, word in enumerate(script_words):
        # Índice proporcional no array do Whisper
        w_idx = min(int(i * n_whisper / n_script), n_whisper - 1)
        wh    = whisper_words[w_idx]

        # Se for a última palavra do grupo, usa o end do próximo slot se disponível
        w_next = whisper_words[min(w_idx + 1, n_whisper - 1)]

        aligned_words.append({
            "word":  word,
            "start": wh["start"],
            "end":   w_next["start"] if w_idx < n_whisper - 1 else wh["end"],
        })

    print(f"[Módulo 3] Ground Truth: {n_script} palavras do roteiro alinhadas com {n_whisper} slots Whisper.")

    # Gera o ASS com o mesmo estilo karaoke, mas usando as palavras limpas
    return _generate_ass_from_words(aligned_words, out_path)


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


def _generate_ass_from_words(words: list, out_path: str) -> str:
    """Gera o arquivo ASS a partir de uma lista de word-dicts {word, start, end}."""
    # ── Cabeçalho ASS ─────────────────────────────────────────────────────────────────────────
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
    groups = [words[i:i + WORDS_PER_LINE] for i in range(0, len(words), WORDS_PER_LINE)]

    for group in groups:
        for focus_idx, focus_word in enumerate(group):
            seg_start = focus_word["start"]
            seg_end   = focus_word["end"]

            parts = []
            for i, w in enumerate(group):
                text = w["word"].upper()
                if i < focus_idx:
                    parts.append(f"{{\\c&HFFFFFF&\\b0}}{text}")
                elif i == focus_idx:
                    parts.append(f"{{\\c&H00FFFF&\\b1}}{text}")
                else:
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


def build_ass(timestamps_path: str = None, output_path: str = None) -> str:
    """
    Gera arquivo ASS usando timestamps do Whisper diretamente.
    Mantido como fallback para compatibilidade.
    """
    ts_path  = timestamps_path or TIMESTAMPS_PATH
    out_path = output_path     or ASS_PATH

    with open(ts_path, "r", encoding="utf-8") as f:
        words = json.load(f)

    if not words:
        raise ValueError("[Módulo 3] timestamps.json está vazio.")

    return _generate_ass_from_words(words, out_path)

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

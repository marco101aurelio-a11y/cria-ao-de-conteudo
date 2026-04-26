"""
MÓDULO 5 — Montador de Vídeo
PATCH v2:
  FIX 1 — Aceita clip_map.json com múltiplos clips por bloco (cortes internos)
  FIX 2 — Legenda posicionada no terço inferior (MarginV=200)
  FIX 3 — FontSize aumentado para 24
"""

import os
import json
import subprocess
from pathlib import Path


OUTPUT_DIR = "output"
CLIPS_DIR = f"{OUTPUT_DIR}/clips"
CLIP_MAP = f"{OUTPUT_DIR}/clip_map.json"
TIMESTAMPS = f"{OUTPUT_DIR}/timestamps.json"
NARRATION = f"{OUTPUT_DIR}/narration.mp3"
BACKGROUND = f"{OUTPUT_DIR}/background.mp3"
SRT = f"{OUTPUT_DIR}/subtitles.srt"  # Mantido caso precise de fallback, mas usaremos ASS
ASS = f"{OUTPUT_DIR}/subtitles.ass"
FINAL = f"{OUTPUT_DIR}/final_output.mp4"
RESOLUTION = "1080:1920"

# Removido SUBTITLE_STYLE pois o estilo agora vem embutido no arquivo .ass

def run(cmd: list, label: str = "") -> None:
    """Executa comando ffmpeg e lança erro se falhar."""
    print(f"[M5] {label}..." if label else f"[M5] {' '.join(cmd[:4])}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERRO] {label}\n{result.stderr}")
        raise RuntimeError(f"FFmpeg falhou em: {label}")


def load_clip_map() -> dict:
    with open(CLIP_MAP, "r") as f:
        return json.load(f)


def load_timestamps() -> list:
    with open(TIMESTAMPS, "r", encoding="utf-8") as f:
        return json.load(f)


def get_block_durations(roteiro_path: str = "output/roteiro.json",
                         timestamps: list = None) -> dict:
    """
    Calcula a duração de áudio de cada bloco NARRACAO
    usando os timestamps gerados pelo Whisper.
    Retorna: { bloco_visual_index: duracao_segundos }
    
    Lógica: cada bloco VISUAL corresponde ao bloco NARRACAO imediatamente anterior.
    A duração do NARRACAO é mapeada nos timestamps por posição no texto.
    """
    with open(roteiro_path, "r", encoding="utf-8") as f:
        roteiro = json.load(f)

    blocks = roteiro.get("blocks", [])
    total_audio_duration = timestamps[-1]["end"] if timestamps else 30.0

    # Mapeia blocos NARRACAO e sua proporção do texto total
    narration_blocks = [b for b in blocks if b["type"] == "NARRACAO"]
    visual_blocks_indices = [i for i, b in enumerate(blocks) if b["type"] == "VISUAL"]

    total_chars = sum(len(b["text"]) for b in narration_blocks)
    if total_chars == 0:
        total_chars = 1

    # Distribui a duração proporcional ao tamanho do texto de cada bloco
    durations = {}
    for vi, block_idx in enumerate(visual_blocks_indices):
        if vi < len(narration_blocks):
            narr = narration_blocks[vi]
            proportion = len(narr["text"]) / total_chars
            dur = total_audio_duration * proportion
            # Removemos o limite máximo de 15s para não cortar o final do vídeo (o áudio ficava maior que o vídeo)
            durations[str(block_idx)] = max(3.0, dur)
        else:
            durations[str(block_idx)] = 5.0

    return durations


def trim_and_scale_clip(src: str, dest: str, duration: float) -> None:
    """
    Escala clip para 1080x1920 (portrait), faz crop central e corta na duração.
    """
    # O zoompan aplica o efeito Ken Burns (movimento constante de zoom in).
    # d=1 garante que ele processe vídeo corretamente frame a frame.
    vf_filters = (
        f"scale={RESOLUTION}:force_original_aspect_ratio=increase,"
        f"crop={RESOLUTION},"
        "zoompan=z='min(zoom+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920,"
        "fps=30,"
        "format=yuv420p"
    )

    run([
        "ffmpeg", "-y",
        "-stream_loop", "-1",  # Loopa o clip caso ele seja mais curto que a duration requerida
        "-i", src,
        "-t", str(duration),
        "-vf", vf_filters,
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-video_track_timescale", "90000",
        "-an",  # sem áudio no clip
        dest,
    ], label=f"Trim+Scale+Zoom {os.path.basename(src)}")


def assemble(roteiro_path: str = "output/roteiro.json") -> str:
    """
    Pipeline completo de montagem.
    PATCH FIX 1: usa clip_map com múltiplos clips por bloco.
    """
    import random
    clip_map = load_clip_map()
    timestamps = load_timestamps()
    block_durations = get_block_durations(roteiro_path, timestamps)

    trimmed_dir = f"{OUTPUT_DIR}/trimmed"
    os.makedirs(trimmed_dir, exist_ok=True)

    # ── PASSO 5.1: Trim e scale de cada clip ─────────────────────────────────
    all_trimmed = []
    for block_idx, clips in sorted(clip_map.items(), key=lambda x: int(x[0])):
        if not clips:
            continue

        total_block_dur = block_durations.get(block_idx, 5.0)
        num_clips = len(clips)
        
        # Cortes Assimétricos: Em vez de dividir exatamente igual, gera durações orgânicas
        proportions = [random.uniform(0.7, 1.3) for _ in range(num_clips)]
        total_prop = sum(proportions)
        
        for ci, src_path in enumerate(clips):
            dest_path = os.path.join(trimmed_dir, f"b{block_idx}_c{ci}_trimmed.mp4")
            if not os.path.exists(src_path):
                print(f"[M5] Clip não encontrado: {src_path}, pulando.")
                continue
                
            clip_dur = total_block_dur * (proportions[ci] / total_prop)
            clip_dur = max(1.5, clip_dur) # mínimo de 1.5s por cena
            
            trim_and_scale_clip(src_path, dest_path, clip_dur)
            all_trimmed.append(dest_path)

    if not all_trimmed:
        raise RuntimeError("Nenhum clip trimado disponível para montagem.")

    # ── PASSO 5.2: Concatenar todos os clips ─────────────────────────────────
    concat_list = f"{OUTPUT_DIR}/concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for path in all_trimmed:
            safe_path = os.path.abspath(path).replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

    video_base = f"{OUTPUT_DIR}/video_base.mp4"
    run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        video_base,
    ], label="Concatenar clips")

    # ── PASSO 5.3: Mix de áudio (narração + música) ───────────────────────────
    mixed_audio = f"{OUTPUT_DIR}/mixed_audio.mp3"
    if os.path.exists(BACKGROUND):
        run([
            "ffmpeg", "-y",
            "-i", NARRATION,
            "-i", BACKGROUND,
            "-filter_complex",
            "[0:a]volume=1.0[a1];[1:a]volume=0.15[a2];[a1][a2]amix=inputs=2:duration=first[aout]",
            "-map", "[aout]",
            mixed_audio,
        ], label="Mix áudio narração+música")
    else:
        print("[M5] Música de fundo não encontrada. Usando apenas narração.")
        import shutil
        shutil.copy(NARRATION, mixed_audio)

    # ── PASSO 5.4 e 5.5: Render final com legenda dinâmica (.ASS) ────────────
    ass_safe = ASS.replace("\\", "/")

    run([
        "ffmpeg", "-y",
        "-i", video_base,
        "-i", mixed_audio,
        "-vf", f"ass={ass_safe}",
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        FINAL,
    ], label="Render final com legendas")

    print(f"\n[M5] VIDEO GERADO: {FINAL}")
    return FINAL


if __name__ == "__main__":
    assemble()

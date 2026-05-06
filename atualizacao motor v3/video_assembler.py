"""
Módulo 5 — Montador de Vídeo (v3)
Usa FFmpeg para montar o vídeo final a partir de:
  - clip_map.json  (múltiplos clips por bloco VISUAL)
  - narration.mp3  (narração gerada pelo TTS)
  - subtitles.ass  (legendas karaoke word-by-word)
  - background.mp3 (música de fundo)
  - roteiro.json   (para saber a duração de cada bloco)

PATCH v3:
  - Múltiplos clips por bloco: cada bloco VISUAL distribui seus N clips pela duration_hint
  - Ken Burns em todos os clips (zoom lento)
  - Legenda no terço inferior, FontSize 24, fundo semitransparente
  - Music ducking: música com -20dB durante narração
  - Transição de fade entre clips (0.3s)
  - Output: 1080x1920 @ 30fps, H.264, AAC

Dependências:
  pip install ffmpeg-python
  ffmpeg deve estar no PATH do sistema
"""
import os
import json
import subprocess
import tempfile
from pathlib import Path

MODULE_DIR      = os.path.dirname(__file__)
OUTPUT_DIR      = os.path.join(MODULE_DIR, "..", "output")
CLIPS_DIR       = os.path.join(OUTPUT_DIR,  "clips")
ROTEIRO_PATH    = os.path.join(OUTPUT_DIR,  "roteiro.json")
CLIP_MAP_PATH   = os.path.join(OUTPUT_DIR,  "clip_map.json")
AUDIO_PATH      = os.path.join(OUTPUT_DIR,  "narration.mp3")
MUSIC_PATH      = os.path.join(OUTPUT_DIR,  "background.mp3")
SUBTITLES_PATH  = os.path.join(OUTPUT_DIR,  "subtitles.ass")
OUTPUT_VIDEO    = os.path.join(OUTPUT_DIR,  "final_output.mp4")

CANVAS_W  = 1080
CANVAS_H  = 1920
FPS       = 30
FADE_DUR  = 0.3   # segundos de fade entre clips


# ── Helpers FFmpeg ─────────────────────────────────────────────────────────────

def _run(cmd: list, step: str) -> None:
    """Executa comando FFmpeg e lança RuntimeError se falhar."""
    print(f"  [FFmpeg:{step}] {' '.join(cmd[:6])}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"[{step}] FFmpeg erro:\n{result.stderr[-2000:]}")


def _get_duration(path: str) -> float:
    """Retorna duração de arquivo de mídia em segundos via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        path,
    ]
    out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
    return float(out) if out else 0.0


# ── Ken Burns em clip individual ───────────────────────────────────────────────

def _apply_ken_burns(src: str, dest: str, duration: float) -> None:
    """
    Recorta `duration` segundos do src, aplica Ken Burns (zoom 1→1.08)
    e formata para 1080x1920 (portrait), 30fps.
    """
    frames = max(int(duration * FPS), 1)
    # zoompan: zoom de 1.0 a 1.08 ao longo de `frames` frames
    vf = (
        f"scale=2*{CANVAS_W}:2*{CANVAS_H}:force_original_aspect_ratio=increase,"
        f"crop={CANVAS_W}:{CANVAS_H},"
        f"zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={CANVAS_W}x{CANVAS_H}:fps={FPS},"
        f"setsar=1"
    )
    cmd = [
        "ffmpeg", "-y",
        "-ss", "0",
        "-i", src,
        "-t", str(duration),
        "-vf", vf,
        "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-r", str(FPS),
        dest,
    ]
    _run(cmd, "ken_burns")


# ── Fade in/out num clip ───────────────────────────────────────────────────────

def _add_fade(src: str, dest: str, duration: float) -> None:
    fade = min(FADE_DUR, duration / 3)
    fo   = max(duration - fade, 0)
    vf   = f"fade=t=in:st=0:d={fade},fade=t=out:st={fo}:d={fade}"
    cmd  = [
        "ffmpeg", "-y", "-i", src,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-an", dest,
    ]
    _run(cmd, "fade")


# ── Montagem principal ─────────────────────────────────────────────────────────

def assemble(
    roteiro_data: dict = None,
    clip_map: dict = None,
    output_path: str = None,
) -> str:
    """
    Monta o vídeo final.
    Retorna path do arquivo gerado.
    """
    # Carrega dados necessários
    if roteiro_data is None:
        with open(ROTEIRO_PATH, "r", encoding="utf-8") as f:
            roteiro_data = json.load(f)

    if clip_map is None:
        with open(CLIP_MAP_PATH, "r", encoding="utf-8") as f:
            clip_map = json.load(f)

    out = output_path or OUTPUT_VIDEO
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Obtém duração total da narração
    narration_duration = _get_duration(AUDIO_PATH)
    print(f"[Módulo 5] Duração da narração: {narration_duration:.2f}s")

    # ── Passo 1: processa cada bloco VISUAL ────────────────────────────────────
    blocos_visuais = [b for b in roteiro_data["blocks"] if b["type"] == "VISUAL"]

    # Distribui duração total pelos blocos proporcionalmente
    total_hint = sum(b.get("duration_hint", 4.0) for b in blocos_visuais) or 1
    scale      = narration_duration / total_hint

    processed_clips = []  # paths de clips já processados prontos para concat

    with tempfile.TemporaryDirectory() as tmpdir:

        for bloco in blocos_visuais:
            block_id      = str(bloco["id"])
            duration_hint = bloco.get("duration_hint", 4.0)
            block_dur     = duration_hint * scale
            clips_info    = clip_map.get(block_id, [])

            if not clips_info:
                # Tela preta de fallback
                black = os.path.join(tmpdir, f"black_{block_id}.mp4")
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "lavfi",
                    "-i", f"color=c=black:s={CANVAS_W}x{CANVAS_H}:r={FPS}:d={block_dur}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    black,
                ]
                _run(cmd, f"black_b{block_id}")
                processed_clips.append(black)
                continue

            # Divide block_dur igualmente entre os clips disponíveis
            n_clips    = len(clips_info)
            per_clip   = block_dur / n_clips

            for sub_idx, clip_info in enumerate(clips_info):
                src_path = clip_info.get("path", "")
                if not src_path or not Path(src_path).exists():
                    continue

                clip_dur    = min(per_clip, _get_duration(src_path))
                kb_path     = os.path.join(tmpdir, f"kb_{block_id}_{sub_idx}.mp4")
                faded_path  = os.path.join(tmpdir, f"fade_{block_id}_{sub_idx}.mp4")

                _apply_ken_burns(src_path, kb_path, clip_dur)
                _add_fade(kb_path, faded_path, clip_dur)
                processed_clips.append(faded_path)

        if not processed_clips:
            raise RuntimeError("[Módulo 5] Nenhum clip processado — verifique clip_map.json")

        # ── Passo 2: concatena todos os clips de vídeo ─────────────────────────
        concat_list = os.path.join(tmpdir, "concat.txt")
        with open(concat_list, "w") as f:
            for p in processed_clips:
                f.write(f"file '{p}'\n")

        raw_video = os.path.join(tmpdir, "raw_video.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-r", str(FPS),
            raw_video,
        ]
        _run(cmd, "concat")

        # ── Passo 3: adiciona narração + música com ducking ────────────────────
        has_music = Path(MUSIC_PATH).exists() and Path(MUSIC_PATH).stat().st_size > 10_000

        if has_music:
            # narração em volume normal, música com ducking (-20dB)
            audio_filter = (
                "[1:a]volume=1.0[narr];"
                "[2:a]volume=0.15[music];"
                "[narr][music]amix=inputs=2:duration=first:dropout_transition=3[aout]"
            )
            audio_step_out = os.path.join(tmpdir, "with_audio.mp4")
            cmd = [
                "ffmpeg", "-y",
                "-i", raw_video,
                "-i", AUDIO_PATH,
                "-i", MUSIC_PATH,
                "-filter_complex", audio_filter,
                "-map", "0:v:0",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                audio_step_out,
            ]
        else:
            audio_step_out = os.path.join(tmpdir, "with_audio.mp4")
            cmd = [
                "ffmpeg", "-y",
                "-i", raw_video,
                "-i", AUDIO_PATH,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                audio_step_out,
            ]
        _run(cmd, "audio_mix")

        # ── Passo 4: queima legendas ASS ───────────────────────────────────────
        has_subs = Path(SUBTITLES_PATH).exists()

        if has_subs:
            # Escapa o path para o filtro ass do FFmpeg
            ass_escaped = SUBTITLES_PATH.replace("\\", "/").replace(":", "\\:")
            cmd = [
                "ffmpeg", "-y",
                "-i", audio_step_out,
                "-vf", f"ass='{ass_escaped}'",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "copy",
                out,
            ]
        else:
            import shutil
            shutil.copy(audio_step_out, out)
            print("[Módulo 5] subtitles.ass não encontrado — vídeo sem legendas.")
            return out

        _run(cmd, "subtitles")

    print(f"[Módulo 5] Vídeo final: {out}")
    return out


if __name__ == "__main__":
    assemble()

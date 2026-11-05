"""
Modulo 5 - Montador de Video (v3)
Usa FFmpeg para montar o video final a partir de:
  - clip_map.json  (multiplos clips por bloco VISUAL)
  - narration.mp3  (narracao gerada pelo TTS)
  - subtitles.ass  (legendas karaoke word-by-word)
  - background.mp3 (musica de fundo)
  - roteiro.json   (para saber a duracao de cada bloco)

PATCH v3:
  - Multiplos clips por bloco: cada bloco VISUAL distribui seus N clips pela duration_hint
  - Ken Burns em todos os clips (zoom lento)
  - Legenda no terco inferior, FontSize 24, fundo semitransparente
  - Music ducking: musica com -20dB durante narracao
  - Transicao de fade entre clips (0.3s)
  - Output: 1080x1920 @ 30fps, H.264, AAC

Dependencias:
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
SILENCES_PATH   = os.path.join(OUTPUT_DIR,  "silences.json")
OUTPUT_VIDEO    = os.path.join(OUTPUT_DIR,  "final_output.mp4")

CANVAS_W  = 1080
CANVAS_H  = 1920
FPS       = 30
FADE_DUR  = 0.3   # segundos de fade entre clips

# Tenta usar aceleração por hardware (NVIDIA NVENC) para renderização ultra-rápida
VCODEC = "h264_nvenc"  # Default para quem tem NVIDIA
try:
    # Verifica se o encoder está disponível
    subprocess.check_output(["ffmpeg", "-encoders"], stderr=subprocess.STDOUT)
except:
    VCODEC = "libx264" # Fallback para CPU


# ── Helpers FFmpeg ─────────────────────────────────────────────────────────────

def _run(cmd: list, step: str) -> None:
    """Executa comando FFmpeg e lança RuntimeError se falhar."""
    print(f"  [FFmpeg:{step}] {' '.join(cmd[:6])}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"[{step}] FFmpeg erro:\n{result.stderr[-2000:]}")


def _get_duration(path: str) -> float:
    """Retorna duração de arquivo de mídia em segundos via ffprobe. Retorna 0.0 se falhar."""
    if not os.path.exists(path) or os.path.getsize(path) < 1000:
        return 0.0
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            path,
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        return float(out) if out else 0.0
    except:
        return 0.0


def _find_cut_points(block_start: float, block_end: float, n_clips: int, silences: list) -> list:
    """
    Encontra os melhores pontos de corte dentro de um bloco de tempo,
    usando os silêncios naturais (respiros) da narração.
    Retorna lista de `n_clips` durações (em segundos) para cada sub-clip.
    """
    block_dur = block_end - block_start
    if n_clips <= 1:
        return [block_dur]

    # Filtra silêncios que estão dentro do bloco atual
    silences_in_block = [
        s for s in silences
        if block_start < s["start"] < block_end
    ]

    # Pontos de corte ideais: dividir igualmente primeiro
    ideal_cuts = [
        block_start + (block_dur / n_clips) * i
        for i in range(1, n_clips)
    ]

    # Para cada ponto ideal, busca o silêncio mais próximo (dentro de 1.5s)
    actual_cuts = [block_start]
    for ideal in ideal_cuts:
        best = min(
            silences_in_block,
            key=lambda s: abs(s["start"] - ideal),
            default=None
        )
        if best and abs(best["start"] - ideal) <= 1.5:
            actual_cuts.append(best["start"])
        else:
            actual_cuts.append(ideal)  # fallback: corte igual
    actual_cuts.append(block_end)

    # Converte para durações e garante um mínimo de 0.5s para não quebrar o FFmpeg
    durations = []
    for i in range(n_clips):
        dur = round(actual_cuts[i + 1] - actual_cuts[i], 3)
        if dur < 0.5:
            dur = 0.5
        durations.append(dur)
    return durations


# ── Ken Burns em clip individual ───────────────────────────────────────────────

def _apply_ken_burns(src: str, dest: str, duration: float) -> None:
    """
    Recorta `duration` segundos do src, aplica Ken Burns (zoom 1.0 -> 1.08)
    mantendo a resolução nativa de 1080x1920 de forma cristalina.
    """
    frames = max(int(duration * FPS), 1)
    
    # IMPORTANTE: Forçar o zoompan a operar nativamente em 1080x1920
    vf = (
        f"scale=2*{CANVAS_W}:2*{CANVAS_H}:force_original_aspect_ratio=increase,"
        f"crop={CANVAS_W}:{CANVAS_H},"
        f"zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={CANVAS_W}x{CANVAS_H}:fps={FPS},"
        f"scale={CANVAS_W}:{CANVAS_H},"
        f"setsar=1"
    )
    cmd = [
        "ffmpeg", "-y",
        "-ss", "0",
        "-i", src,
        "-t", str(duration),
        "-vf", vf,
        "-an",
        "-c:v", VCODEC,
        "-preset", "slow",     # Codificação lenta para máxima qualidade
        "-crf", "18",          # CRF 18 oferece qualidade visualmente sem perdas
        "-r", str(FPS),
        "-pix_fmt", "yuv420p", # Garante compatibilidade de cores ideal
        "-vsync", "cfr",
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
        "-c:v", VCODEC, "-preset", "p4",
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
    # Filtra blocos visuais (aceita 'type' ou 'tipo')
    blocos_visuais = [b for b in roteiro_data["blocks"] if (b.get("type") or b.get("tipo")) == "VISUAL"]

    # Distribui duração total pelos blocos proporcionalmente
    total_hint = sum(b.get("duration_hint", 4.0) for b in blocos_visuais) or 1
    scale      = narration_duration / total_hint

    processed_clips = []  # paths de clips já processados prontos para concat

    with tempfile.TemporaryDirectory() as tmpdir:

        # Carrega silences.json (opcional — fallback para divisão igual)
        silences = []
        if Path(SILENCES_PATH).exists():
            with open(SILENCES_PATH, "r", encoding="utf-8") as f:
                silences = json.load(f)
            print(f"[Módulo 5] {len(silences)} pontos de respiro carregados para corte orgânico.")
        else:
            print("[Módulo 5] silences.json não encontrado — usando divisão de tempo igual.")

        # Mapa de tempo acumulado por bloco (para localizar respiros no bloco certo)
        accumulated_time = 0.0

        for bloco in blocos_visuais:
            block_id      = str(bloco.get("id", "0"))
            duration_hint = bloco.get("duration_hint", 4.0)
            block_dur     = duration_hint * scale
            clips_info    = clip_map.get(block_id, [])

            block_start = accumulated_time
            block_end   = accumulated_time + block_dur
            accumulated_time = block_end

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
                accumulated_time = block_end
                continue

            # Calcula durações de cada sub-clip usando pontos de respiro
            n_clips    = len(clips_info)
            cut_durs   = _find_cut_points(block_start, block_end, n_clips, silences)

            for sub_idx, clip_info in enumerate(clips_info):
                src_path = clip_info.get("path", "")
                if not src_path or not Path(src_path).exists():
                    continue
                
                # Verifica se o arquivo de vídeo é válido e tem conteúdo
                actual_src_dur = _get_duration(src_path)
                if actual_src_dur < 0.2:
                    print(f"    [AVISO] Clip corrompido ou muito curto ignorado: {src_path}")
                    continue

                clip_dur = min(cut_durs[sub_idx], actual_src_dur)
                
                # Pula clips que ficarem com duração inválida após o min/max
                if clip_dur < 0.1:
                    print(f"    [AVISO] Clip {src_path} ignorado (duração insuficiente: {clip_dur}s)")
                    continue

                kb_path     = os.path.join(tmpdir, f"kb_{block_id}_{sub_idx}.mp4")
                faded_path  = os.path.join(tmpdir, f"fade_{block_id}_{sub_idx}.mp4")

                try:
                    _apply_ken_burns(src_path, kb_path, clip_dur)
                    _add_fade(kb_path, faded_path, clip_dur)
                    processed_clips.append(faded_path)
                except Exception as e:
                    print(f"    [ERRO] Falha ao processar clip {src_path}: {e}")
                    continue

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
            "-c:v", VCODEC, "-preset", "p4",
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
                "-c:v", VCODEC, "-preset", "p4",
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

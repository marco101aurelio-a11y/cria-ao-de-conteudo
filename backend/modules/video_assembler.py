"""
Módulo 5 — Montagem Final (Video Assembler)
Junta os vídeos (clips), o áudio (narration.mp3) e os timestamps (SRT/ASS)
usando FFmpeg para gerar o vídeo final 1080x1920 com legendas dinâmicas.
"""

import os
import json
import subprocess
import glob
import math

MODULE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(MODULE_DIR, "..", "output")
CLIPS_DIR = os.path.join(OUTPUT_DIR, "clips")

AUDIO_PATH = os.path.join(OUTPUT_DIR, "narration.mp3")
TIMESTAMPS_PATH = os.path.join(OUTPUT_DIR, "timestamps.json")
FINAL_VIDEO = os.path.join(OUTPUT_DIR, "final_output.mp4")
TEMP_VIDEO = os.path.join(OUTPUT_DIR, "temp_no_audio.mp4")
SUBS_PATH = os.path.join(OUTPUT_DIR, "subtitles.srt")


def get_audio_duration(audio_path):
    """Obtém a duração do áudio usando ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"[Módulo 5] Erro ao obter duração do áudio: {e}")
        return 15.0


def format_srt_time(seconds):
    """Formata segundos para o formato do SRT (HH:MM:SS,mmm)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"


def create_dynamic_srt():
    """
    Cria um arquivo SRT a partir do timestamps.json.
    Estilo 'Hormozi': exibe 1 a 3 palavras por vez no centro da tela.
    """
    if not os.path.exists(TIMESTAMPS_PATH):
        print("[Módulo 5] timestamps.json não encontrado.")
        return False

    with open(TIMESTAMPS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    words = data.get("words", [])
    if not words:
        print("[Módulo 5] Nenhuma palavra encontrada nos timestamps.")
        return False

    with open(SUBS_PATH, "w", encoding="utf-8") as f:
        for i, w in enumerate(words):
            start = w["start"]
            end = w["end"]
            
            # Se a palavra for muito curta, dá um padding minimo para não piscar
            if end - start < 0.1:
                end = start + 0.1
            
            # Formata a palavra atual em amarelo e MAIÚSCULA
            word_text = w["word"].upper()
            
            f.write(f"{i+1}\n")
            f.write(f"{format_srt_time(start)} --> {format_srt_time(end)}\n")
            f.write(f"<font color=\"#FFD700\"><b>{word_text}</b></font>\n\n")

    print(f"[Módulo 5] Legendas dinâmicas (SRT) geradas em: {SUBS_PATH}")
    return True


def render_video():
    """
    Junta tudo via FFmpeg:
    1. Redimensiona/corta os clips para 1080x1920
    2. Concatena os clips
    3. Adiciona a legenda SRT
    4. Adiciona a narração MP3
    """
    if not os.path.exists(AUDIO_PATH):
        raise FileNotFoundError("Áudio da narração não encontrado.")

    # 1. Pega os vídeos baixados
    clips = sorted(glob.glob(os.path.join(CLIPS_DIR, "*.mp4")))
    if not clips:
        raise FileNotFoundError("Nenhum clipe de vídeo encontrado na pasta clips/.")

    duration = get_audio_duration(AUDIO_PATH)
    clip_duration = duration / len(clips)
    
    print(f"[Módulo 5] Duração total: {duration:.2f}s | Cada clipe terá ~{clip_duration:.2f}s")
    
    # 2. Cria arquivo list.txt para o ffmpeg concat
    list_path = os.path.join(OUTPUT_DIR, "list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for clip in clips:
            # O path precisa ser absoluto e com barras normais para o ffmpeg
            safe_path = clip.replace("\\", "/")
            f.write(f"file '{safe_path}'\n")
    
    # 3. Cria as legendas
    create_dynamic_srt()
    
    print("[Módulo 5] Iniciando renderização do vídeo base (FFmpeg)...")
    
    # Prepara o filtro de vídeo: Crop 1080x1920, recorta no tempo certo
    # Como são vários vídeos de tamanhos diferentes, o jeito mais seguro é reencodar tudo pra 1080x1920.
    
    # Vamos primeiro concatenar e forçar a resolução usando filter_complex
    filter_complex = ""
    for i in range(len(clips)):
        filter_complex += f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,trim=duration={clip_duration},setpts=PTS-STARTPTS[v{i}];"
    
    concat_str = "".join([f"[v{i}]" for i in range(len(clips))])
    filter_complex += f"{concat_str}concat=n={len(clips)}:v=1:a=0[vout]"

    # Comando para montar o vídeo (sem áudio, sem legenda)
    inputs = []
    for clip in clips:
        inputs.extend(["-i", clip])

    cmd_video = [
        "ffmpeg", "-y"
    ] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        TEMP_VIDEO
    ]
    
    subprocess.run(cmd_video, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("[Módulo 5] Vídeo base renderizado com sucesso.")

    print("[Módulo 5] Adicionando legendas e áudio...")
    
    # 4. Adiciona as legendas e o áudio final
    # Atenção: O ffmpeg no windows exige escaping de path para o filtro de legenda
    safe_sub_path = SUBS_PATH.replace("\\", "/").replace(":", "\\:")
    
    cmd_final = [
        "ffmpeg", "-y",
        "-i", TEMP_VIDEO,
        "-i", AUDIO_PATH,
        "-vf", f"subtitles='{safe_sub_path}':force_style='FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=3,Outline=3,Shadow=0,MarginV=150,Alignment=2'",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        FINAL_VIDEO
    ]

    subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Limpeza
    try:
        os.remove(TEMP_VIDEO)
        os.remove(list_path)
    except:
        pass

    print(f"[Módulo 5] Sucesso! O video viral esta pronto em: {FINAL_VIDEO}")
    return {"status": "success", "video_path": FINAL_VIDEO}


if __name__ == "__main__":
    try:
        render_video()
    except Exception as e:
        print(f"Erro no Módulo 5: {e}")

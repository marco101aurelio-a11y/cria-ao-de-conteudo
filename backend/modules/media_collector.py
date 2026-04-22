"""
Módulo 4 — Coletor de Mídia (B-Roll)
Lê o roteiro, extrai as palavras-chave visuais e faz o download
de vídeos gratuitos (vertical) do Pexels API.
"""

import os
import json
import requests
from dotenv import load_dotenv

# Carrega as variáveis de ambiente
load_dotenv()
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

MODULE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(MODULE_DIR, "..", "output")
ROTEIRO_PATH = os.path.join(OUTPUT_DIR, "roteiro.json")
CLIPS_DIR = os.path.join(OUTPUT_DIR, "clips")


def search_pexels_video(keyword: str) -> str:
    """Busca um vídeo vertical no Pexels e retorna a URL de download."""
    if not PEXELS_API_KEY or PEXELS_API_KEY == "sua_chave_do_pexels_aqui":
        print("[Módulo 4] AVISO: PEXELS_API_KEY não configurada.")
        return None

    url = f"https://api.pexels.com/videos/search?query={keyword}&orientation=portrait&per_page=3"
    headers = {"Authorization": PEXELS_API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("videos"):
            print(f"[Módulo 4] Nenhum vídeo encontrado para: '{keyword}'")
            return None
            
        # Pega o primeiro vídeo
        video_data = data["videos"][0]
        
        # Procura a versão HD (alta qualidade)
        best_link = None
        for file in video_data.get("video_files", []):
            if file.get("quality") == "hd":
                best_link = file.get("link")
                break
                
        # Se não achou HD, pega o primeiro link
        if not best_link and video_data.get("video_files"):
            best_link = video_data["video_files"][0].get("link")
            
        return best_link

    except Exception as e:
        print(f"[Módulo 4] Erro na API do Pexels para '{keyword}': {e}")
        return None


def download_video(url: str, filepath: str):
    """Faz o download do arquivo de vídeo."""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"[Módulo 4] Falha ao baixar vídeo: {e}")
        return False


def collect_media(roteiro_data: dict = None) -> dict:
    if roteiro_data is None:
        if not os.path.exists(ROTEIRO_PATH):
            raise FileNotFoundError(f"Roteiro não encontrado em: {ROTEIRO_PATH}")
        with open(ROTEIRO_PATH, "r", encoding="utf-8") as f:
            roteiro_data = json.load(f)

    os.makedirs(CLIPS_DIR, exist_ok=True)
    
    downloaded_clips = []
    
    print("[Módulo 4] Iniciando coleta de B-Roll (Pexels)...")
    
    # Itera sobre os blocos e busca vídeos para os blocos 'VISUAL'
    for i, bloco in enumerate(roteiro_data.get("blocks", [])):
        if bloco.get("type") == "VISUAL":
            keyword = bloco.get("keyword")
            print(f"\n[Módulo 4] Buscando vídeo para: '{keyword}'")
            
            video_url = search_pexels_video(keyword)
            
            if video_url:
                clip_path = os.path.join(CLIPS_DIR, f"visual_{i}.mp4")
                print(f"[Módulo 4] Baixando: {video_url[:50]}...")
                
                if download_video(video_url, clip_path):
                    print(f"[Módulo 4] Video salvo: visual_{i}.mp4")
                    downloaded_clips.append(clip_path)
                else:
                    print(f"[Módulo 4] Erro ao salvar visual_{i}.mp4")
            else:
                # Se não achar nada, tenta uma palavra-chave genérica de dark video
                print(f"[Módulo 4] Tentando palavra-chave genérica (fallback)...")
                fallback_url = search_pexels_video("dark aesthetic")
                if fallback_url:
                    clip_path = os.path.join(CLIPS_DIR, f"visual_{i}.mp4")
                    if download_video(fallback_url, clip_path):
                        print(f"[Módulo 4] Video fallback salvo: visual_{i}.mp4")
                        downloaded_clips.append(clip_path)

    print(f"\n[Módulo 4] Coleta concluída! {len(downloaded_clips)} vídeos baixados na pasta 'output/clips'.")
    print(f"[Módulo 4] NOTA: A API de áudio do Pixabay está bloqueada. Para a música de fundo,")
    print(f"[Módulo 4] adicione um arquivo 'background.mp3' manualmente na pasta 'output/'.")

    return {
        "status": "success",
        "clips_downloaded": len(downloaded_clips),
        "clips": downloaded_clips
    }

if __name__ == "__main__":
    try:
        collect_media()
    except Exception as e:
        print(f"Erro no teste isolado: {e}")

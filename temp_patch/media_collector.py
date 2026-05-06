"""
MÓDULO 4 — Coletor de Mídia (B-Roll)
PATCH v2: baixa clips distintos por bloco VISUAL, com corte a cada 3-5s
"""

import os
import json
import random
import requests
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

HEADERS_PEXELS = {"Authorization": PEXELS_API_KEY}
CLIPS_DIR = "output/clips"
FALLBACK_KEYWORD = "dark mystery"

# PATCH FIX 1: número de clipes por bloco aumentado para 3
# Isso garante variação visual dentro de cada bloco de narração
CLIPS_PER_BLOCK = 3


def search_pexels(keyword: str, per_page: int = 10) -> list:
    """Busca clipes no Pexels para uma keyword. Retorna lista de URLs."""
    url = "https://api.pexels.com/videos/search"
    params = {
        "query": keyword,
        "per_page": per_page,
        "orientation": "portrait",
    }
    response = requests.get(url, headers=HEADERS_PEXELS, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    videos = data.get("videos", [])

    results = []
    for video in videos:
        # Filtra apenas clipes entre 3 e 12 segundos
        duration = video.get("duration", 0)
        if not (3 <= duration <= 12):
            continue
        # Pega o arquivo de maior qualidade disponível em HD
        files = video.get("video_files", [])
        hd_files = [f for f in files if f.get("quality") in ("hd", "sd")]
        if not hd_files:
            continue
        # Ordena por largura descendente e pega o melhor
        hd_files.sort(key=lambda f: f.get("width", 0), reverse=True)
        results.append({
            "url": hd_files[0]["link"],
            "duration": duration,
            "keyword": keyword,
        })
        if len(results) >= per_page:
            break

    return results


def download_clip(url: str, dest_path: str) -> bool:
    """Faz download de um clipe e salva em dest_path. Retorna True se OK."""
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"[ERRO] Download falhou: {url} — {e}")
        return False


def collect_clips(roteiro_path: str = "output/roteiro.json") -> dict:
    """
    Para cada bloco VISUAL do roteiro, baixa CLIPS_PER_BLOCK clipes distintos.
    Retorna mapa: { "bloco_index": ["output/clips/b0_c0.mp4", ...] }
    
    PATCH FIX 1: em vez de 1 clip por bloco, agora baixa N clips por bloco
    permitindo cortes internos e maior variação visual.
    """
    os.makedirs(CLIPS_DIR, exist_ok=True)

    with open(roteiro_path, "r", encoding="utf-8") as f:
        roteiro = json.load(f)

    blocks = roteiro.get("blocks", [])
    visual_blocks = [
        (i, b) for i, b in enumerate(blocks) if b["type"] == "VISUAL"
    ]

    clip_map = {}
    used_urls = set()  # Evita baixar o mesmo clipe duas vezes

    for block_idx, block in visual_blocks:
        keyword = block.get("keyword", FALLBACK_KEYWORD)
        print(f"[M4] Buscando clips para bloco {block_idx}: '{keyword}'")

        results = search_pexels(keyword, per_page=15)

        # Fallback se não encontrar nada
        if not results:
            print(f"[M4] Sem resultado para '{keyword}', usando fallback.")
            results = search_pexels(FALLBACK_KEYWORD, per_page=15)

        # Filtra URLs já usadas para garantir clips distintos
        results = [r for r in results if r["url"] not in used_urls]

        # Embaralha para variedade
        random.shuffle(results)

        downloaded = []
        for clip_num in range(CLIPS_PER_BLOCK):
            if not results:
                print(f"[M4] Clips esgotados para bloco {block_idx}.")
                break

            clip_data = results.pop(0)
            dest = os.path.join(CLIPS_DIR, f"b{block_idx}_c{clip_num}.mp4")

            print(f"[M4]   Baixando clip {clip_num+1}/{CLIPS_PER_BLOCK}...")
            ok = download_clip(clip_data["url"], dest)
            if ok:
                downloaded.append(dest)
                used_urls.add(clip_data["url"])

        clip_map[str(block_idx)] = downloaded
        print(f"[M4] Bloco {block_idx}: {len(downloaded)} clips baixados.")

    return clip_map


def download_background_music(dest: str = "output/background.mp3") -> bool:
    """Baixa uma faixa de música dark cinematic do Pixabay."""
    url = "https://pixabay.com/api/"
    params = {
        "key": PIXABAY_API_KEY,
        "q": "dark cinematic",
        "category": "music",
        "per_page": 10,
    }
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    hits = response.json().get("hits", [])

    if not hits:
        print("[M4] Nenhuma música encontrada no Pixabay.")
        return False

    music_url = hits[0].get("previewURL") or hits[0].get("url")
    return download_clip(music_url, dest)


if __name__ == "__main__":
    clip_map = collect_clips()
    download_background_music()

    # Salva mapa de clips para uso no Módulo 5
    with open("output/clip_map.json", "w") as f:
        json.dump(clip_map, f, indent=2)

    print("[M4] Concluído. clip_map.json salvo.")

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
    
    # Randomiza a página só para palavras-chave curtas. Buscas longas perdem muito sentido na página 2+
    page_num = 1 if len(keyword.split()) > 2 else random.randint(1, 2)
    
    params = {
        "query": keyword,
        "per_page": per_page,
        "orientation": "portrait",
        "page": page_num,
    }
    
    print(f"[M4] Pesquisando '{keyword}' (Página {page_num})")
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


def search_pixabay(keyword: str, per_page: int = 15) -> list:
    """Busca clipes no Pixabay para uma keyword. Retorna lista de URLs."""
    if not PIXABAY_API_KEY:
        return []
        
    url = "https://pixabay.com/api/videos/"
    params = {
        "key": PIXABAY_API_KEY,
        "q": keyword,
        "per_page": per_page,
    }
    
    print(f"[M4] Pesquisando '{keyword}' no Pixabay...")
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        hits = data.get("hits", [])
        
        results = []
        for hit in hits:
            duration = hit.get("duration", 0)
            if not (3 <= duration <= 15):
                continue
            
            # Pega o video mp4 com maior qualidade
            videos = hit.get("videos", {})
            best_url = None
            for size in ["large", "medium", "small"]:
                if size in videos and videos[size].get("url"):
                    best_url = videos[size]["url"]
                    break
                    
            if best_url:
                results.append({
                    "url": best_url,
                    "duration": duration,
                    "keyword": keyword,
                })
                if len(results) >= per_page:
                    break
        return results
    except Exception as e:
        print(f"[ERRO] Pixabay API falhou: {e}")
        return []


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

        results_pexels = search_pexels(keyword, per_page=15)
        results_pixabay = search_pixabay(keyword, per_page=15)
        results = results_pexels + results_pixabay

        # Fallback se não encontrar nada em nenhum dos dois
        if not results:
            fallback_kw = " ".join(keyword.split()[:2])
            print(f"[M4] Sem resultado para '{keyword}', tentando fallback parcial: '{fallback_kw}'")
            results_pexels = search_pexels(fallback_kw, per_page=15)
            results_pixabay = search_pixabay(fallback_kw, per_page=15)
            results = results_pexels + results_pixabay
            
            if not results:
                print(f"[M4] Sem resultado para fallback parcial, usando fallback geral.")
                results_pexels = search_pexels("cinematic dark", per_page=15)
                results_pixabay = search_pixabay("cinematic dark", per_page=15)
                results = results_pexels + results_pixabay

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
    """Baixa uma faixa de música dark cinematic usando a Jamendo API."""
    client_id = os.getenv("JAMENDO_CLIENT_ID")
    
    if not client_id:
        print("[M4] ⚠️ AVISO: JAMENDO_CLIENT_ID não configurado no .env.")
        print("[M4] 👉 Crie uma conta grátis em developer.jamendo.com para gerar o Client ID e adicione ao .env.")
        print("[M4] Ignorando música de fundo automatizada.")
        return False

    url = "https://api.jamendo.com/v3.0/tracks/"
    params = {
        "client_id": client_id,
        "format": "json",
        "tags": "dark,cinematic",
        "limit": 10,
        "order": "popularity_month"
    }
    
    print("[M4] Buscando trilha sonora na Jamendo API...")
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if not results:
            print("[M4] Nenhuma música encontrada.")
            return False
            
        # Pega uma música aleatória do top 10 do mês para não repetir
        track = random.choice(results)
        audio_url = track.get("audiodownload")
        
        if not audio_url:
            print("[M4] Faixa sem permissão de download.")
            return False
            
        print(f"[M4] Baixando trilha: {track.get('name')} (por {track.get('artist_name')})...")
        
        ok = download_clip(audio_url, dest)
        if ok:
            print("[M4] ✅ Música de fundo baixada com sucesso!")
            return True
        return False
        
    except Exception as e:
        print(f"[ERRO] Falha ao baixar música do Jamendo: {e}")
        return False


if __name__ == "__main__":
    clip_map = collect_clips()
    download_background_music()

    # Salva mapa de clips para uso no Módulo 5
    with open("output/clip_map.json", "w") as f:
        json.dump(clip_map, f, indent=2)

    print("[M4] Concluído. clip_map.json salvo.")

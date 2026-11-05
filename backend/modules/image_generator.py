"""
Módulo 4.1 — Image Generator Fallback
Gera uma imagem via Pollinations.ai a partir do visual_context e converte em clipe B-Roll (mp4).
"""
import os
import requests
import subprocess
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

def optimize_prompt(visual_context: str) -> str:
    """Usa Ollama local ou OpenRouter para traduzir e otimizar o contexto visual para um prompt de IA."""
    use_ollama = os.getenv("USE_OLLAMA", "False").lower() in ("true", "1", "yes")
    
    system_prompt = (
        "You are an expert midjourney prompt engineer. "
        "The user will give you a scene description in Portuguese. "
        "Convert it into a highly descriptive, comma-separated English prompt for an AI image generator. "
        "Keep it under 30 words. Focus on subjects and environment."
    )

    if use_ollama:
        try:
            host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
            model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
            url = f"{host}/api/chat"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": visual_context}
                ],
                "stream": False
            }
            print(f"    [ImageGen] Otimizando prompt localmente via Ollama ({model})...")
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            raw = response.json()["message"]["content"].strip()
            raw = raw.replace('"', '').replace("`", "")
            return raw
        except Exception as e:
            print(f"    [ImageGen] Erro ao otimizar prompt com Ollama: {e}. Usando fallbacks...")

    # Fallback para OpenRouter
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    if not OPENROUTER_API_KEY:
        return visual_context

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "google/gemini-2.0-flash-lite-preview-02-05:free", # Free fallback model
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": visual_context}
        ]
    }
    
    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()
        # Clean up possible markdown or quotes
        raw = raw.replace('"', '').replace("`", "")
        return raw
    except Exception as e:
        print(f"    [ImageGen] Erro ao otimizar prompt via OpenRouter: {e}")
        # Fallback to the portuguese context if API fails
        return visual_context

def generate_fallback_clip(visual_context: str, dest_path: str) -> bool:
    """
    1. Otimiza prompt
    2. Baixa JPG do Pollinations
    3. Converte para MP4 de 5 segundos com Pan & Scan (Ken Burns)
    """
    print(f"    [ImageGen] Criando clip IA para: '{visual_context[:30]}...'")
    
    base_prompt = optimize_prompt(visual_context)
    # Refatorado: Removemos 'dark atmosphere' para dar lugar a composições neutras e de altíssima qualidade
    full_prompt = base_prompt + ", highly detailed, cinematic composition, professional photography, natural lighting, 8k, photorealistic, no text, no watermark"
    
    encoded_prompt = urllib.parse.quote(full_prompt)
    
    # Random seed to get variety if called multiple times
    import random
    seed = random.randint(1, 9999)
    
    pollinations_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&seed={seed}&nologo=true"
    
    jpg_path = dest_path.replace(".mp4", ".jpg")
    
    try:
        # 1. Download JPG
        print(f"      - Baixando imagem do Pollinations...")
        r = requests.get(pollinations_url, timeout=45)
        r.raise_for_status()
        
        with open(jpg_path, "wb") as f:
            f.write(r.content)
            
        # 2. Convert to MP4 with FFmpeg (Pan & Scan)
        print(f"      - Convertendo imagem em video (Pan & Scan)...")
      # Refatorado: Zoompan de alta definição
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", jpg_path,
            "-vf", "scale=1080:1920,zoompan=z='min(zoom+0.001,1.1)':d=150:s=1080x1920:fps=30,scale=1080:1920",
            "-t", "5", 
            "-c:v", "libx264", 
            "-preset", "slow", 
            "-crf", "18", 
            "-pix_fmt", "yuv420p", 
            "-loglevel", "error",
            dest_path
        ]
        subprocess.run(cmd, check=True)
        
        # Cleanup JPG
        if os.path.exists(jpg_path):
            os.remove(jpg_path)
            
        return True
        
    except Exception as e:
        print(f"    [ImageGen] Falha na geração: {e}")
        if os.path.exists(jpg_path):
            os.remove(jpg_path)
        return False

if __name__ == "__main__":
    # Test
    generate_fallback_clip("arquivo secreto com documentos antigos", "test_ia_clip.mp4")

"""
Módulo 0 — Viral Hunter (Sprint BÔNUS)
Simula um Web Scraper que varre o TikTok atrás de vídeos virais,
extrai as transcrições deles e salva tudo em um banco de dados Supabase
para o Módulo 1 usar de inspiração na hora de criar o roteiro.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def run_hunter(niche: str = "#marketing #darkvideo"):
    """
    Simula a varredura e a gravação de referências no Supabase.
    """
    print(f"\n[Módulo 0] Iniciando Viral Hunter para o nicho: {niche}")
    
    # Simulação de scraping (na vida real usaríamos Playwright no TikTok)
    found_videos = [
        {"url": "tiktok.com/@fulano/video/1", "views": 1500000, "transcript": "Você nunca vai ficar rico assim..."},
        {"url": "tiktok.com/@sicrano/video/2", "views": 850000, "transcript": "O segredo do algoritmo é..."}
    ]
    
    print(f"[Módulo 0] 🕷️ Playwright varreu o TikTok e achou {len(found_videos)} vídeos virais.")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[Módulo 0] ⚠️ Chaves do Supabase não configuradas no .env!")
        print("[Módulo 0] ⚠️ O hunter achou as referências, mas não pôde salvá-las no Banco de Dados.")
        return {
            "status": "warning", 
            "msg": "Vídeos encontrados, mas Supabase não configurado.",
            "data": found_videos
        }

    print("[Módulo 0] 💾 Conectando ao Supabase para salvar referências...")
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Insere os vídeos encontrados na tabela real
        data_to_insert = []
        for v in found_videos:
            data_to_insert.append({
                "niche": niche,
                "url": v["url"],
                "views": v["views"],
                "transcript": v["transcript"]
            })
        
        response = supabase.table("viral_references").insert(data_to_insert).execute()
        
        print(f"[Módulo 0] ✅ {len(data_to_insert)} referências salvas no Supabase!")
        return {"status": "success", "data": found_videos}
        
    except Exception as e:
        print(f"[Módulo 0] ❌ Erro ao conectar no Supabase: {e}")
        return {"status": "error", "msg": str(e)}

if __name__ == "__main__":
    run_hunter()

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")

def setup_db():
    if not URL or not KEY:
        print("❌ Erro: Chaves do Supabase não encontradas no .env")
        return

    print(f"Connecting to: {URL}")
    try:
        supabase: Client = create_client(URL, KEY)
        
        print("Testing connection...")
        response = supabase.table("viral_references").select("*").limit(1).execute()
        print("Success: Connection established!")
        
    except Exception as e:
        if "relation \"public.viral_references\" does not exist" in str(e):
            print("Notice: Connection OK, but table 'viral_references' does not exist yet.")
            print("Action: Please run the SQL in your Supabase dashboard.")
        else:
            print(f"Error: {e}")

if __name__ == "__main__":
    setup_db()

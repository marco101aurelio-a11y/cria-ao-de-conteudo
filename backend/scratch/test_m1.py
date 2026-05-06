import sys
import os

# Adiciona o diretório atual ao path para importar modules
sys.path.append(os.getcwd())

from modules.script_generator import generate_script
from dotenv import load_dotenv

load_dotenv()

try:
    print("Testando Módulo 1...")
    # Deletar roteiro.json antigo para forçar geração
    if os.path.exists("output/roteiro.json"):
        os.remove("output/roteiro.json")
        print("Removido roteiro.json antigo para teste.")
    
    tema = "As 3 maiores curiosidades sobre o Antigo Egito"
    roteiro = generate_script(tema)
    print("\nSUCESSO!")
    print(f"Tema: {roteiro.get('tema')}")
    print(f"Blocos: {len(roteiro.get('blocks', []))}")
except Exception as e:
    print(f"\nERRO: {e}")

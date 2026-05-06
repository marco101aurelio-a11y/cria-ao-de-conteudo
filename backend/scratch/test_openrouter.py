import os
import requests
from dotenv import load_dotenv

load_dotenv()

KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "meta-llama/llama-3.1-8b-instruct:free"

def test():
    print(f"Testing OpenRouter with model: {MODEL}")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "hi"}]
    }
    try:
        r = requests.post(url, headers=headers, json=payload)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()

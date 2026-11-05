# 🎬 Dark Video Pipeline V3 — Automação de Vídeos & Criativos com IA

Pipeline modular em Python para criação automatizada de vídeos verticais (**TikTok, Reels, YouTube Shorts**) e criativos de alta retenção, combinando **LLMs locais (Ollama / Llama 3.2) ou Cloud (OpenRouter)**, síntese de voz neural (**Kokoro TTS local / ElevenLabs**), transcrição e sincronização palavra a palavra (**Faster-Whisper STT**), coleta inteligente de B-Roll (**Pexels / Pixabay**) e montagem acelerada via **FFmpeg / MoviePy**.

---

## 🏗️ Arquitetura do Pipeline (`backend/`)

1. **Módulo 0 — Viral Hunter (`viral_hunter.py`):** Pesquisa e validação de ângulos e temas de alto engajamento com cache em Supabase.
2. **Módulo 1 — Geração de Roteiro (`script_generator.py`):** Engenharia de prompts para ganchos visuais nos 3 primeiros segundos, retenção narrativa e marcação automática de cenas (*clip mapping*), suportando **Ollama local (`llama3.2`)** ou **OpenRouter**.
3. **Módulo 2 — Síntese de Voz (`tts_generator.py`):** Narração natural via **Kokoro TTS (100% local e gratuito)** ou **ElevenLabs API**.
4. **Módulo 3 — Sincronização & Legendas (`stt_aligner.py`):** Alinhamento temporal de precisão com **Whisper STT** e merge inteligente de tokens para legendas dinâmicas.
5. **Módulo 4 — Curadoria Visual & Áudio (`media_collector.py` & `image_generator.py`):** Download automatizado de múltiplos takes B-Roll no Pexels e trilhas sonoras no Pixabay.
6. **Módulo 5 — Renderização Final (`video_assembler.py`):** Composição 9:16 com *color grading*, mixagem de áudio (*ducking*), efeitos de transição e tipografia dinâmica.

---

## 🚀 Como Executar

1. **Configure as variáveis de ambiente:**
   Copie `backend/.env.example` para `backend/.env` e preencha suas chaves (`PEXELS_API_KEY`, `PIXABAY_API_KEY`, `USE_OLLAMA=True` ou `OPENROUTER_API_KEY`).

2. **Instale as dependências e execute o pipeline:**
   ```bash
   cd backend
   pip install -r requirements.txt
   python main.py --tema "Como a IA e o MCP estão transformando o Marketing Digital"
   ```

3. **Opções avançadas de linha de comando:**
   ```bash
   python main.py --tema "Seu tema aqui" --hunter          # Ativa o Viral Hunter antes do roteiro
   python main.py --tema "Seu tema aqui" --tts-engine api  # Usa ElevenLabs no lugar do TTS local
   python main.py --tema "Seu tema aqui" --device cuda     # Aceleração GPU para o Whisper STT
   ```

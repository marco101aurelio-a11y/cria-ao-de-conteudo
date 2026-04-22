# Plano de Execução Externa (Deploy do Dark Video Pipeline V2)

Este documento foi criado para que você (ou outro Agente de IA) possa instalar, configurar e rodar todo o ecossistema "Dark Video Pipeline Inovado" em uma **máquina externa** (seja um servidor na nuvem, uma VPS Ubuntu, outro Mac ou um PC Windows).

A arquitetura atualizada já inclui o Módulo 0 (Viral Hunter com Supabase) e o Módulo 5 (Renderização de legendas CSS via Playwright + FFmpeg).

---

## 1. Pré-Requisitos do Sistema Operacional

Independentemente de onde for rodar, a máquina deve ter instalados a nível de sistema (e configurados nas Variáveis de Ambiente/PATH):

* **Python 3.10 ou superior:** Necessário para rodar o Flask e os submódulos de ML.
* **FFmpeg:** Obrigatório. É o motor de edição de vídeo subjacente.
    * *No Ubuntu:* `sudo apt install ffmpeg`
    * *No Mac:* `brew install ffmpeg`
    * *No Windows:* Usar `winget install ffmpeg` ou baixar os binários.
* **Node.js (Opcional, mas recomendado):** O Playwright para Python baixa seu próprio binário de navegador, mas ter Node ajuda se decidirmos usar Puppeteer no futuro.

---

## 2. Configuração do Banco de Dados (Supabase)

O cérebro do sistema não vive na máquina, vive no Supabase. Antes de rodar o código na máquina externa, garanta que seu projeto Supabase tenha estas duas tabelas:

1. `viral_references` (Usada pelo Módulo 0 e 1)
   * Colunas: `id` (uuid), `tiktok_url` (text), `views` (int), `transcription_text` (text), `created_at` (timestamp).
2. `broll_library` (Usada pelo Módulo 4)
   * Colunas: `id` (uuid), `pexels_id` (text), `download_url` (text), `theme_keyword` (text), `created_at` (timestamp).

---

## 3. Instalação do Ambiente (Passo a Passo na Máquina Externa)

Quando acessar a máquina, execute os seguintes comandos no terminal:

```bash
# 1. Clone o repositório ou copie a pasta 'dark-video-pipeline'
git clone <seu-repositorio> dark-video-pipeline
cd dark-video-pipeline

# 2. Crie e ative o ambiente virtual Python
python3 -m venv venv
source venv/bin/activate  # No windows: venv\Scripts\activate

# 3. Instale as dependências robustas
pip install flask requests python-dotenv supabase openai-whisper playwright pydub

# 4. Instale os navegadores fantasmas para o Módulo 0 e Módulo 5 (Crítico)
playwright install chromium
```

---

## 4. Variáveis de Ambiente (`.env`)

Crie um arquivo `.env` na raiz do projeto (`dark-video-pipeline/.env`) na máquina externa. Ele DEVE conter as chaves de acesso:

```env
# Módulo 0 e 4: Supabase
SUPABASE_URL="sua_url_aqui"
SUPABASE_KEY="sua_anon_key_aqui"

# Módulo 1: OpenRouter (Geração de Script)
OPENROUTER_API_KEY="sk-or-v1-sua_chave_openrouter_aqui"

# Módulo 4: Coleta de B-Roll e Música (Somente para quando o BD falhar)
PEXELS_API_KEY="sua_chave_pexels"
PIXABAY_API_KEY="sua_chave_pixabay"

# Módulo 2: Opcional (Se for usar voz Premium em vez do Kokoro local)
ELEVENLABS_API_KEY="sua_chave_elevenlabs"
```

---

## 5. Estrutura de Diretórios Esperada (Checklist)

A máquina externa deve conter esta árvore de arquivos para que o sistema orquestre os vídeos perfeitamente:

```text
dark-video-pipeline/
├── .env
├── server.py                  # Servidor Flask e Orquestrador
├── requirements.txt
├── modules/
│   ├── module0_hunter.py      # Playwright + TikTok -> Supabase
│   ├── script_generator.py    # Supabase -> OpenRouter (Hook+Copy)
│   ├── tts.py                 # Gera Voz
│   ├── stt.py                 # Whisper (Timestamps)
│   ├── media_collector.py     # Pexels API + Supabase Cache
│   ├── video_assembler.py     # Playwright (HTML Legenda Alpha) + FFmpeg
│   └── templates/
│       └── subtitles.html     # HTML e CSS das legendas pulando (Módulo 5)
└── output/                    # Onde os vídeos MP4 finais serão salvos
```

---

## 6. Como Inicializar e Executar (Passo a Passo por Módulo)

O Orquestrador Flask permite que você rode a pipeline inteira de uma vez, mas para controle total (ou debug), a máquina externa pode executar os módulos individualmente.

**A. Subir o Servidor Mestre:**
No terminal da máquina externa, inicie o servidor:
```bash
python server.py
```
*(O servidor rodará em `http://localhost:5000`)*

**B. Executando os Módulos Separadamente (O Fluxo Completo):**

* **Módulo 0 (Viral Hunter):** Raspa o TikTok e popula o Supabase.
  ```bash
  curl -X POST http://localhost:5000/api/module0/hunt \
       -H "Content-Type: application/json" \
       -d '{"niche": "#marketing #negocios"}'
  ```

* **Módulo 1 (Script Generator):** Puxa o viral do banco e a IA (OpenRouter) reescreve no formato Hook+Copy. Salva `roteiro.json`.
  ```bash
  curl -X POST http://localhost:5000/api/module1/generate_script
  ```

* **Módulo 2 (TTS - Voz):** Lê o `roteiro.json` e gera o áudio da narração em `narration.mp3`.
  ```bash
  curl -X POST http://localhost:5000/api/module2/generate_audio
  ```

* **Módulo 3 (STT - Timestamps):** O Whisper local escuta `narration.mp3` e gera a minutagem exata de cada palavra em `timestamps.json`.
  ```bash
  curl -X POST http://localhost:5000/api/module3/generate_timestamps
  ```

* **Módulo 4 (Media Vault):** Analisa o roteiro, procura vídeos no banco Supabase ou baixa no Pexels e salva na máquina.
  ```bash
  curl -X POST http://localhost:5000/api/module4/collect_media
  ```

* **Módulo 5 (Video Assembler):** A mágica final. O Playwright renderiza as legendas em HTML animado e o FFmpeg junta voz, vídeos e legendas em um arquivo único.
  ```bash
  curl -X POST http://localhost:5000/api/module5/render_video
  ```

**C. Comando Mestre (Rodar Tudo Automaticamente):**
Em produção, você só precisa chamar a rota mestre que executará do 1 ao 5 em sequência:
```bash
curl -X POST http://localhost:5000/api/run_pipeline
```
Ao término, o `final_video_1.mp4` estará pronto na pasta `/output`.

# AGENT INSTRUCTIONS — Dark Video Pipeline (Local Server)

## Contexto de Execução

Você é um agente de vibe coding rodando no Antigravity (VS Code com agente integrado).
Seu objetivo é implementar um pipeline local completo que recebe um **tema** e produz um **arquivo `.mp4`** pronto para TikTok/Reels.

**Ambiente:**
- IDE: Antigravity (VS Code com agente AI)
- Linguagem: Python 3.10+
- Servidor: Flask rodando em `http://localhost:5000`
- Sistema: macOS ou Linux
- FFmpeg: instalado via `brew install ffmpeg` (macOS) ou `apt install ffmpeg` (Linux)

**Regra de execução:**
Implemente um módulo por vez. Teste cada módulo isoladamente antes de avançar para o próximo. Não pule etapas.

---

## Estrutura de Diretórios a Criar

```
dark-video-pipeline/
├── server.py
├── .env
├── requirements.txt
├── modules/
│   ├── __init__.py
│   ├── script_generator.py
│   ├── tts.py
│   ├── stt.py
│   ├── media_collector.py
│   └── video_assembler.py
└── output/
    └── clips/
```

**Comando para criar estrutura:**
```bash
mkdir -p dark-video-pipeline/modules dark-video-pipeline/output/clips
cd dark-video-pipeline
touch server.py .env requirements.txt
touch modules/__init__.py modules/script_generator.py modules/tts.py modules/stt.py modules/media_collector.py modules/video_assembler.py
```

---

## Arquivo: `.env`

```
OPENROUTER_API_KEY=
PEXELS_API_KEY=
PIXABAY_API_KEY=
ELEVENLABS_API_KEY=
```

**Regra:** Nunca colocar valores reais no código. Sempre ler via `os.getenv()`.

---

## Arquivo: `requirements.txt`

```
flask
flask-cors
requests
python-dotenv
openai-whisper
soundfile
numpy
```

**Instalar com:**
```bash
pip install -r requirements.txt
pip install kokoro-onnx --break-system-packages
```

---

## MÓDULO 1 — `modules/script_generator.py`

**Responsabilidade:** Receber tema (string), chamar OpenRouter API, retornar JSON estruturado.

**Endpoint que vai expor:** `POST /api/module1/generate-script`

**Implementação:**

```python
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "meta-llama/llama-3.3-70b-instruct:free"

SYSTEM_PROMPT = """Você é um roteirista especializado em dark videos para TikTok.
Responda SOMENTE com um JSON válido, sem texto adicional, sem markdown.
O JSON deve seguir exatamente este schema:
{
  "title": "string",
  "blocks": [
    { "type": "NARRACAO", "text": "string" },
    { "type": "VISUAL", "keyword": "string (em inglês, para busca de stock footage)" }
  ]
}
Regras:
- Alterne sempre NARRACAO > VISUAL > NARRACAO > VISUAL
- Cada bloco NARRACAO: máximo 2 frases curtas, tom narrativo e dramático
- Cada bloco VISUAL: uma palavra-chave ou frase curta em inglês (ex: "dark laboratory", "old documents", "city night rain")
- Total de blocos: entre 8 e 14
- Não use markdown, não use blocos de código, retorne apenas o JSON"""


def generate_script(tema: str) -> dict:
    """
    Chama OpenRouter e retorna roteiro estruturado.
    Tenta até 3 vezes com temperatura crescente em caso de falha de parse.
    """
    temperatures = [0.7, 0.4, 0.2]

    for attempt, temp in enumerate(temperatures):
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "temperature": temp,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": tema}
                ]
            },
            timeout=30
        )

        response.raise_for_status()
        raw_text = response.json()["choices"][0]["message"]["content"].strip()

        # Remover markdown se o modelo ignorou a instrução
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        try:
            roteiro = json.loads(raw_text)
        except json.JSONDecodeError:
            if attempt < 2:
                continue
            raise ValueError(f"OpenRouter retornou JSON inválido após 3 tentativas: {raw_text[:200]}")

        # Validar estrutura
        if "blocks" not in roteiro:
            raise ValueError("JSON retornado não contém campo 'blocks'")
        if len(roteiro["blocks"]) < 8:
            raise ValueError(f"Roteiro tem apenas {len(roteiro['blocks'])} blocos. Mínimo: 8")

        # Salvar em disco
        output_path = "output/roteiro.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(roteiro, f, ensure_ascii=False, indent=2)

        return {"status": "ok", "roteiro": roteiro, "saved_to": output_path}

    raise RuntimeError("Falha ao gerar roteiro após 3 tentativas")
```

**Teste isolado (rodar antes de avançar):**
```python
# test_module1.py
from modules.script_generator import generate_script
resultado = generate_script("O experimento secreto que o governo escondeu por décadas")
print(f"Blocos gerados: {len(resultado['roteiro']['blocks'])}")
print(f"Título: {resultado['roteiro']['title']}")
```

**Critério de aprovação:**
- `roteiro.json` existe em `output/`
- `blocks` tem entre 8 e 14 itens
- Tipos alternam entre `NARRACAO` e `VISUAL`

---

## MÓDULO 2 — `modules/tts.py`

**Responsabilidade:** Ler `roteiro.json`, extrair texto dos blocos NARRACAO, converter para `narration.mp3`.

**Endpoint que vai expor:** `POST /api/module2/generate-audio`

**Implementação (Kokoro TTS — local, gratuito):**

```python
import os
import json
import subprocess
import soundfile as sf
from dotenv import load_dotenv

load_dotenv()


def generate_audio_kokoro(roteiro_path: str = "output/roteiro.json") -> dict:
    """
    Extrai narração do roteiro e gera narration.mp3 via Kokoro TTS.
    """
    with open(roteiro_path, "r", encoding="utf-8") as f:
        roteiro = json.load(f)

    # Extrair apenas blocos NARRACAO
    narration_blocks = [
        block["text"]
        for block in roteiro["blocks"]
        if block["type"] == "NARRACAO"
    ]
    full_text = " ".join(narration_blocks)

    if not full_text.strip():
        raise ValueError("Nenhum bloco NARRACAO encontrado no roteiro")

    # Gerar áudio com Kokoro
    try:
        from kokoro_onnx import Kokoro
        kokoro = Kokoro("kokoro-v0_19.onnx", "voices.bin")
        samples, sample_rate = kokoro.create(
            full_text,
            voice="af_bella",
            speed=1.0,
            lang="pt"
        )
        wav_path = "output/narration.wav"
        sf.write(wav_path, samples, sample_rate)
    except ImportError:
        raise ImportError("kokoro-onnx não instalado. Execute: pip install kokoro-onnx")

    # Converter WAV para MP3
    mp3_path = "output/narration.mp3"
    subprocess.run([
        "ffmpeg", "-y",
        "-i", wav_path,
        "-ab", "192k",
        mp3_path
    ], check=True, capture_output=True)

    # Verificar duração
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        mp3_path
    ], capture_output=True, text=True)
    duration = float(result.stdout.strip())

    return {
        "status": "ok",
        "saved_to": mp3_path,
        "duration_seconds": round(duration, 2),
        "character_count": len(full_text)
    }


def generate_audio_elevenlabs(roteiro_path: str = "output/roteiro.json") -> dict:
    """
    Alternativa paga: ElevenLabs API.
    Usar apenas se Kokoro TTS não estiver disponível.
    """
    import requests

    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel (PT-BR compatível)

    with open(roteiro_path, "r", encoding="utf-8") as f:
        roteiro = json.load(f)

    narration_blocks = [b["text"] for b in roteiro["blocks"] if b["type"] == "NARRACAO"]
    full_text = " ".join(narration_blocks)

    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "text": full_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        },
        timeout=60
    )
    response.raise_for_status()

    mp3_path = "output/narration.mp3"
    with open(mp3_path, "wb") as f:
        f.write(response.content)

    return {"status": "ok", "saved_to": mp3_path}
```

**Teste isolado:**
```python
# test_module2.py
from modules.tts import generate_audio_kokoro
resultado = generate_audio_kokoro()
print(f"Duração: {resultado['duration_seconds']}s")
assert resultado['duration_seconds'] > 20, "Áudio muito curto"
```

**Critério de aprovação:**
- `narration.mp3` existe em `output/`
- Duração maior que 20 segundos

---

## MÓDULO 3 — `modules/stt.py`

**Responsabilidade:** Processar `narration.mp3` com Whisper e gerar `timestamps.json` com timestamps por palavra.

**Endpoint que vai expor:** `POST /api/module3/generate-timestamps`

**Implementação:**

```python
import json
import whisper


def generate_timestamps(audio_path: str = "output/narration.mp3") -> dict:
    """
    Transcreve áudio com Whisper e extrai timestamps por palavra.
    """
    print("Carregando modelo Whisper (base)...")
    model = whisper.load_model("base")

    print(f"Transcrevendo {audio_path}...")
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="pt"
    )

    # Extrair timestamps por palavra
    words = []
    for segment in result["segments"]:
        for word in segment.get("words", []):
            words.append({
                "word": word["word"].strip(),
                "start": round(word["start"], 3),
                "end": round(word["end"], 3)
            })

    if len(words) < 30:
        raise ValueError(f"Whisper extraiu apenas {len(words)} palavras. Mínimo esperado: 30")

    output_path = "output/timestamps.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

    return {
        "status": "ok",
        "saved_to": output_path,
        "word_count": len(words),
        "first_word": words[0],
        "last_word": words[-1]
    }
```

**Teste isolado:**
```python
# test_module3.py
from modules.stt import generate_timestamps
resultado = generate_timestamps()
print(f"Palavras encontradas: {resultado['word_count']}")
assert resultado['word_count'] >= 30
```

**Critério de aprovação:**
- `timestamps.json` existe em `output/`
- Tem pelo menos 30 entradas
- Cada entrada tem `word`, `start`, `end`

---

## MÓDULO 4 — `modules/media_collector.py`

**Responsabilidade:** Para cada bloco VISUAL do roteiro, baixar 1 clipe de stock footage do Pexels. Baixar 1 música de fundo do Pixabay.

**Endpoint que vai expor:** `POST /api/module4/collect-media`

**Implementação:**

```python
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
FALLBACK_KEYWORD = "dark mystery"


def download_file(url: str, dest_path: str) -> bool:
    """Download de arquivo com timeout e verificação de tamanho."""
    try:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return os.path.getsize(dest_path) > 10000  # > 10KB
    except Exception as e:
        print(f"Erro ao baixar {url}: {e}")
        return False


def find_clip_for_keyword(keyword: str) -> str | None:
    """
    Busca clipe no Pexels para keyword.
    Tenta keyword original, depois fallback.
    Retorna URL do vídeo mais adequado (5-15s) ou None.
    """
    for kw in [keyword, FALLBACK_KEYWORD]:
        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": kw, "per_page": 5, "orientation": "portrait"},
            timeout=15
        )
        if response.status_code != 200:
            continue

        videos = response.json().get("videos", [])
        for video in videos:
            duration = video.get("duration", 0)
            if 5 <= duration <= 20:  # Aceita até 20s (trimmar depois)
                # Pegar arquivo de maior resolução
                files = sorted(
                    video.get("video_files", []),
                    key=lambda f: f.get("height", 0),
                    reverse=True
                )
                if files:
                    return files[0]["link"]

    return None


def collect_media(roteiro_path: str = "output/roteiro.json") -> dict:
    """
    Baixa clips para cada bloco VISUAL e 1 música de fundo.
    """
    with open(roteiro_path, "r", encoding="utf-8") as f:
        roteiro = json.load(f)

    visual_blocks = [b for b in roteiro["blocks"] if b["type"] == "VISUAL"]
    downloaded_clips = []
    failed_clips = []

    os.makedirs("output/clips", exist_ok=True)

    for idx, block in enumerate(visual_blocks):
        keyword = block.get("keyword", FALLBACK_KEYWORD)
        dest_path = f"output/clips/clip_{idx}.mp4"

        print(f"Buscando clip {idx}: '{keyword}'...")
        clip_url = find_clip_for_keyword(keyword)

        if clip_url:
            success = download_file(clip_url, dest_path)
            if success:
                downloaded_clips.append({"index": idx, "keyword": keyword, "path": dest_path})
                print(f"  ✓ Clip {idx} baixado")
            else:
                failed_clips.append({"index": idx, "keyword": keyword, "reason": "download_failed"})
                print(f"  ✗ Falha no download do clip {idx}")
        else:
            failed_clips.append({"index": idx, "keyword": keyword, "reason": "no_results"})
            print(f"  ✗ Nenhum clipe encontrado para '{keyword}' nem para fallback")

    # Baixar música de fundo (Pixabay)
    bg_music_path = None
    pixabay_url = (
        f"https://pixabay.com/api/videos/"
        f"?key={PIXABAY_API_KEY}&category=music&q=dark+cinematic&per_page=5"
    )
    try:
        px_response = requests.get(pixabay_url, timeout=15)
        px_response.raise_for_status()
        hits = px_response.json().get("hits", [])
        if hits:
            music_url = hits[0].get("videos", {}).get("medium", {}).get("url")
            if music_url:
                bg_music_path = "output/background.mp3"
                download_file(music_url, bg_music_path)
                print("✓ Música de fundo baixada")
    except Exception as e:
        print(f"Aviso: Falha ao baixar música de fundo: {e}")

    return {
        "status": "ok",
        "clips_downloaded": len(downloaded_clips),
        "clips_failed": len(failed_clips),
        "clips": downloaded_clips,
        "failed": failed_clips,
        "background_music": bg_music_path
    }
```

**Teste isolado:**
```python
# test_module4.py
from modules.media_collector import collect_media
resultado = collect_media()
print(f"Clips baixados: {resultado['clips_downloaded']}")
print(f"Clips com falha: {resultado['clips_failed']}")
```

**Critério de aprovação:**
- Pelo menos 70% dos clips baixados com sucesso
- `output/clips/` tem pelo menos 4 arquivos `.mp4`

---

## MÓDULO 5 — `modules/video_assembler.py`

**Responsabilidade:** Montar vídeo final 1080x1920 com narração, B-roll, legendas e música de fundo.

**Endpoint que vai expor:** `POST /api/module5/assemble-video`

**Implementação:**

```python
import os
import json
import subprocess


def get_video_duration(path: str) -> float:
    """Retorna duração em segundos de um arquivo de mídia."""
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ], capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def get_block_timestamps(roteiro: dict, timestamps: list) -> list:
    """
    Associa cada bloco NARRACAO com seus timestamps de palavra.
    Retorna lista de dicts com start/end de cada bloco.
    """
    narration_texts = [b["text"] for b in roteiro["blocks"] if b["type"] == "NARRACAO"]
    total_words = len(timestamps)

    # Estimar distribuição de palavras por bloco pelo tamanho do texto
    block_word_counts = []
    for text in narration_texts:
        word_count = len(text.split())
        block_word_counts.append(word_count)

    total_estimated = sum(block_word_counts)
    block_ranges = []
    cursor = 0

    for count in block_word_counts:
        proportion = count / total_estimated
        n_words = max(1, round(proportion * total_words))
        end_cursor = min(cursor + n_words, total_words - 1)
        block_ranges.append({
            "start": timestamps[cursor]["start"],
            "end": timestamps[end_cursor]["end"]
        })
        cursor = end_cursor + 1

    return block_ranges


def normalize_clip(input_path: str, output_path: str, target_duration: float) -> bool:
    """
    Trimma e redimensiona clip para 1080x1920.
    Se clip é mais curto, usa loop.
    """
    native_duration = get_video_duration(input_path)

    if native_duration >= target_duration:
        # Trimmar para duração exata
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-t", str(target_duration),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-c:v", "libx264", "-crf", "23", "-preset", "veryfast",
            "-an",
            output_path
        ]
    else:
        # Loop para preencher duração
        loops_needed = int(target_duration / native_duration) + 1
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(loops_needed),
            "-i", input_path,
            "-t", str(target_duration),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-c:v", "libx264", "-crf", "23", "-preset", "veryfast",
            "-an",
            output_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def create_srt(timestamps: list, output_path: str = "output/subtitles.srt") -> str:
    """
    Gera arquivo SRT com 1 entrada por palavra.
    """
    def fmt_time(seconds: float) -> str:
        h = int(seconds) // 3600
        m = (int(seconds) % 3600) // 60
        s = int(seconds) % 60
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    with open(output_path, "w", encoding="utf-8") as f:
        for idx, word_data in enumerate(timestamps, 1):
            f.write(f"{idx}\n")
            f.write(f"{fmt_time(word_data['start'])} --> {fmt_time(word_data['end'])}\n")
            f.write(f"{word_data['word']}\n\n")

    return output_path


def assemble_video(
    roteiro_path: str = "output/roteiro.json",
    narration_path: str = "output/narration.mp3",
    timestamps_path: str = "output/timestamps.json",
    clips_dir: str = "output/clips",
    background_path: str = "output/background.mp3",
    output_path: str = "output/final_output.mp4"
) -> dict:
    """
    Orquestra os 5 passos de montagem do vídeo final.
    """
    # Carregar artefatos
    with open(roteiro_path, "r", encoding="utf-8") as f:
        roteiro = json.load(f)
    with open(timestamps_path, "r", encoding="utf-8") as f:
        timestamps = json.load(f)

    visual_blocks = [b for b in roteiro["blocks"] if b["type"] == "VISUAL"]
    narration_duration = get_video_duration(narration_path)
    block_timestamps = get_block_timestamps(roteiro, timestamps)

    # PASSO 1: Normalizar clips
    print("[1/5] Normalizando clips...")
    normalized_clips = []
    for idx in range(len(visual_blocks)):
        input_clip = f"{clips_dir}/clip_{idx}.mp4"
        output_clip = f"{clips_dir}/clip_{idx}_norm.mp4"

        if not os.path.exists(input_clip):
            print(f"  ⚠ Clip {idx} não encontrado, pulando")
            continue

        block_duration = block_timestamps[idx]["end"] - block_timestamps[idx]["start"]
        block_duration = max(block_duration, 1.0)  # Mínimo 1 segundo

        success = normalize_clip(input_clip, output_clip, block_duration)
        if success:
            normalized_clips.append(output_clip)
            print(f"  ✓ Clip {idx} normalizado ({block_duration:.1f}s)")
        else:
            print(f"  ✗ Falha ao normalizar clip {idx}")

    if not normalized_clips:
        raise RuntimeError("Nenhum clip disponível para montagem")

    # PASSO 2: Concatenar clips
    print("[2/5] Concatenando clips...")
    concat_list_path = "output/concat_list.txt"
    with open(concat_list_path, "w") as f:
        for clip_path in normalized_clips:
            f.write(f"file '{os.path.abspath(clip_path)}'\n")

    video_base_path = "output/video_base.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list_path,
        "-c:v", "libx264", "-crf", "23", "-preset", "veryfast",
        "-an",
        video_base_path
    ], check=True, capture_output=True)
    print("  ✓ Video base criado")

    # PASSO 3: Mixar áudio
    print("[3/5] Mixando áudio...")
    mixed_audio_path = "output/mixed_audio.mp3"
    bg_volume = "0.12" if os.path.exists(background_path) else "0"

    if os.path.exists(background_path):
        subprocess.run([
            "ffmpeg", "-y",
            "-i", narration_path,
            "-i", background_path,
            "-filter_complex",
            f"[0:a]volume=1.0[a1];[1:a]volume={bg_volume}[a2];[a1][a2]amix=inputs=2:duration=first[aout]",
            "-map", "[aout]",
            "-c:a", "aac", "-b:a", "192k",
            mixed_audio_path
        ], check=True, capture_output=True)
    else:
        # Sem música de fundo
        subprocess.run([
            "ffmpeg", "-y", "-i", narration_path,
            "-c:a", "aac", "-b:a", "192k",
            mixed_audio_path
        ], check=True, capture_output=True)
    print("  ✓ Áudio mixado")

    # PASSO 4: Gerar SRT
    print("[4/5] Gerando legendas SRT...")
    srt_path = create_srt(timestamps)
    print(f"  ✓ SRT gerado com {len(timestamps)} entradas")

    # PASSO 5: Renderização final
    print("[5/5] Renderizando vídeo final...")
    subtitle_style = (
        "FontName=Arial,FontSize=28,Bold=1,Alignment=2,"
        "PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
        "Outline=2,Shadow=1,MarginV=60"
    )
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_base_path,
        "-i", mixed_audio_path,
        "-vf", f"subtitles={srt_path}:force_style='{subtitle_style}'",
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path
    ], check=True, capture_output=True)

    final_duration = get_video_duration(output_path)
    final_size = os.path.getsize(output_path)

    return {
        "status": "ok",
        "saved_to": output_path,
        "duration_seconds": round(final_duration, 2),
        "file_size_mb": round(final_size / (1024 * 1024), 2),
        "clips_used": len(normalized_clips)
    }
```

**Critério de aprovação:**
- `final_output.mp4` existe em `output/`
- Duração compatível com duração da narração (±2s)
- Resolução verificada: `ffprobe -v error -select_streams v:0 -show_entries stream=width,height output/final_output.mp4`

---

## SERVIDOR — `server.py`

**Responsabilidade:** Expor todos os módulos como endpoints HTTP. Permitir execução individual ou pipeline completo.

```python
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)  # Permite chamadas do Antigravity (outro origin)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "server": "dark-video-pipeline"})


@app.route("/api/module1/generate-script", methods=["POST"])
def api_generate_script():
    try:
        data = request.get_json()
        if not data or "tema" not in data:
            return jsonify({"error": "Campo 'tema' obrigatório"}), 400

        from modules.script_generator import generate_script
        result = generate_script(data["tema"])
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/module2/generate-audio", methods=["POST"])
def api_generate_audio():
    try:
        from modules.tts import generate_audio_kokoro, generate_audio_elevenlabs
        data = request.get_json() or {}
        use_elevenlabs = data.get("use_elevenlabs", False)

        if use_elevenlabs:
            result = generate_audio_elevenlabs()
        else:
            result = generate_audio_kokoro()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/module3/generate-timestamps", methods=["POST"])
def api_generate_timestamps():
    try:
        from modules.stt import generate_timestamps
        result = generate_timestamps()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/module4/collect-media", methods=["POST"])
def api_collect_media():
    try:
        from modules.media_collector import collect_media
        result = collect_media()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/module5/assemble-video", methods=["POST"])
def api_assemble_video():
    try:
        from modules.video_assembler import assemble_video
        result = assemble_video()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pipeline/run", methods=["POST"])
def api_run_pipeline():
    """
    Endpoint que executa o pipeline completo em sequência.
    Retorna status de cada etapa.
    """
    data = request.get_json()
    if not data or "tema" not in data:
        return jsonify({"error": "Campo 'tema' obrigatório"}), 400

    tema = data["tema"]
    steps = []

    try:
        print(f"\n=== INICIANDO PIPELINE: {tema} ===\n")

        print("[1/5] Gerando roteiro...")
        from modules.script_generator import generate_script
        r1 = generate_script(tema)
        steps.append({"step": 1, "name": "script", "status": "ok", "data": r1})

        print("[2/5] Gerando áudio...")
        from modules.tts import generate_audio_kokoro
        r2 = generate_audio_kokoro()
        steps.append({"step": 2, "name": "audio", "status": "ok", "data": r2})

        print("[3/5] Gerando timestamps...")
        from modules.stt import generate_timestamps
        r3 = generate_timestamps()
        steps.append({"step": 3, "name": "timestamps", "status": "ok", "data": r3})

        print("[4/5] Coletando mídia...")
        from modules.media_collector import collect_media
        r4 = collect_media()
        steps.append({"step": 4, "name": "media", "status": "ok", "data": r4})

        print("[5/5] Montando vídeo...")
        from modules.video_assembler import assemble_video
        r5 = assemble_video()
        steps.append({"step": 5, "name": "video", "status": "ok", "data": r5})

        print(f"\n=== PIPELINE CONCLUÍDO: {r5['saved_to']} ===\n")

        return jsonify({
            "status": "ok",
            "tema": tema,
            "steps": steps,
            "output": r5["saved_to"]
        })

    except Exception as e:
        steps.append({"status": "error", "error": str(e)})
        return jsonify({"status": "error", "steps": steps, "error": str(e)}), 500


if __name__ == "__main__":
    os.makedirs("output/clips", exist_ok=True)
    print("Dark Video Pipeline - Servidor iniciado em http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
```

**Iniciar servidor:**
```bash
cd dark-video-pipeline
python server.py
```

---

## VERIFICAÇÃO FINAL

Após implementar todos os módulos, execute este teste de integração completo:

```bash
curl -X POST http://localhost:5000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"tema": "O dia em que a internet quase acabou"}'
```

**Checklist de aprovação do pipeline:**

```
[ ] server.py inicia sem erro em localhost:5000
[ ] GET /health retorna {"status": "ok"}
[ ] roteiro.json tem 8-14 blocos alternados
[ ] narration.mp3 tem duração > 20s
[ ] timestamps.json tem pelo menos 30 entradas
[ ] output/clips/ tem pelo menos 4 arquivos .mp4
[ ] final_output.mp4 existe
[ ] ffprobe final_output.mp4 mostra resolução 1080x1920
[ ] ffprobe final_output.mp4 mostra duração compatível com narração
[ ] Reproduzir manual: áudio audível, legendas sincronizadas, clipes coerentes
```

---

## TRATAMENTO DE ERROS COMUNS

| Erro | Causa | Solução |
|------|-------|---------|
| `kokoro-onnx not found` | Não instalado | `pip install kokoro-onnx` |
| `ffmpeg not found` | FFmpeg não no PATH | `brew install ffmpeg` ou `apt install ffmpeg` |
| `JSON decode error` | OpenRouter retornou markdown | Módulo 1 já tem limpeza automática, verificar logs |
| `Clip muito curto` | Pexels sem resultado | Fallback `dark mystery` já implementado |
| `CORS error` | Flask sem CORS | `flask-cors` já instalado e configurado |
| `Port 5000 in use` | Outro processo | `lsof -i :5000` e matar processo, ou mudar para `:5001` |

---

## NOTAS PARA O AGENTE

1. **Implemente um módulo por vez** e teste antes de avançar
2. **Não remova os `print()`** — eles são o log de progresso visível no terminal
3. **Não altere os nomes dos arquivos de output** (`roteiro.json`, `narration.mp3`, etc.) — os módulos seguintes dependem desses nomes
4. **Se Kokoro TTS falhar** (modelo `.onnx` não encontrado), mude automaticamente para ElevenLabs passando `use_elevenlabs: true` no body da requisição do módulo 2
5. **O CORS está habilitado globalmente** — necessário para o Antigravity chamar o servidor local de outro contexto

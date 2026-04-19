# Plano de Implementação: Pipeline Dark Video com Narração (TikTok / Reels)

## Contexto e Objetivo

Construir um pipeline local, executável via linha de comando, que receba um **tema** como input e produza um **arquivo `.mp4` finalizado** com: narração em voz off, legendas sincronizadas word-by-word, B-roll de stock footage e música de fundo. O output é um vídeo pronto para upload no TikTok ou Instagram Reels.

Não há dependência de plataformas externas pagas no caminho crítico. Todas as etapas de geração de conteúdo usam ferramentas open-source ou APIs com plano gratuito.

---

## Arquitetura do Pipeline

O pipeline é composto por **5 módulos sequenciais**. Cada módulo recebe um artefato do módulo anterior e produz um artefato de saída bem definido.

```
INPUT: tema (string)
  │
  ▼
[MÓDULO 1] Gerador de Roteiro
  OUTPUT: roteiro.json
  │
  ▼
[MÓDULO 2] Gerador de Áudio (TTS)
  OUTPUT: narration.mp3
  │
  ▼
[MÓDULO 3] Gerador de Timestamps (STT)
  OUTPUT: timestamps.json
  │
  ▼
[MÓDULO 4] Coletor de Mídia (B-Roll)
  OUTPUT: /clips/*.mp4, background.mp3
  │
  ▼
[MÓDULO 5] Montador de Vídeo
  OUTPUT: final_output.mp4
```

---

## Módulo 1 — Gerador de Roteiro

**Responsabilidade:** Receber o tema e retornar o roteiro estruturado em blocos alternados de `[NARRACAO]` e `[VISUAL]`.

**Ferramenta:** OpenRouter API  
**Modelo:** `meta-llama/llama-3.3-70b-instruct:free`  
**Endpoint:** `POST https://openrouter.ai/api/v1/chat/completions`

**System Prompt (fixo):**
```
Você é um roteirista especializado em dark videos para TikTok.
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
- Cada bloco VISUAL: uma palavra-chave ou frase curta em inglês para busca de vídeo (ex: "dark laboratory", "old documents", "city night rain")
- Total de blocos: entre 8 e 14
- Não use markdown, não use blocos de código, retorne apenas o JSON
```

**Input para a API:** `{ "role": "user", "content": "<tema recebido>" }`

**Validação do output:**
- Fazer parse do JSON retornado
- Verificar que `blocks` existe e tem pelo menos 8 itens
- Verificar que os tipos alternam entre `NARRACAO` e `VISUAL`
- Se a validação falhar: repetir a chamada com temperatura 0.2 (máximo 3 tentativas)

**Artefato de saída:** `roteiro.json`

---

## Módulo 2 — Gerador de Áudio (TTS)

**Responsabilidade:** Extrair todos os blocos `NARRACAO` do `roteiro.json`, concatená-los em um único texto e converter para arquivo de áudio.

**Ferramenta (opção A, gratuita):** Kokoro TTS  
**Instalação:** `pip install kokoro-onnx soundfile`  
**Comando:**
```python
from kokoro_onnx import Kokoro
kokoro = Kokoro("kokoro-v0_19.onnx", "voices.bin")
samples, sample_rate = kokoro.create(full_narration_text, voice="af_bella", speed=1.0, lang="pt")
soundfile.write("narration.wav", samples, sample_rate)
```
Converter para mp3: `ffmpeg -i narration.wav -ab 192k narration.mp3`

**Ferramenta (opção B, paga):** ElevenLabs API  
**Endpoint:** `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`  
**Headers:** `xi-api-key: {ELEVENLABS_API_KEY}`  
**Body:** `{ "text": "<texto_completo>", "model_id": "eleven_multilingual_v2" }`  
**Output:** salvar binário como `narration.mp3`

**Artefato de saída:** `narration.mp3`

---

## Módulo 3 — Gerador de Timestamps (STT)

**Responsabilidade:** Processar `narration.mp3` e retornar os timestamps de início e fim de cada palavra para sincronizar a legenda.

**Ferramenta:** OpenAI Whisper (open-source, roda local)  
**Instalação:** `pip install openai-whisper`  
**Comando:**
```python
import whisper, json
model = whisper.load_model("base")
result = model.transcribe("narration.mp3", word_timestamps=True, language="pt")
words = []
for segment in result["segments"]:
    for word in segment.get("words", []):
        words.append({ "word": word["word"].strip(), "start": word["start"], "end": word["end"] })
with open("timestamps.json", "w") as f:
    json.dump(words, f)
```

**Artefato de saída:** `timestamps.json`  
**Schema:** `[{ "word": "string", "start": float, "end": float }]`

---

## Módulo 4 — Coletor de Mídia (B-Roll)

**Responsabilidade:** Para cada bloco `VISUAL` do `roteiro.json`, buscar e baixar um clipe de stock footage correspondente. Baixar também uma faixa de música de fundo.

### 4.1 — Clipes de Vídeo

**Ferramenta:** Pexels API  
**Endpoint:** `GET https://api.pexels.com/videos/search?query={keyword}&per_page=3&orientation=portrait`  
**Header:** `Authorization: {PEXELS_API_KEY}`  
**Lógica de seleção:** usar o primeiro resultado com duração entre 5 e 15 segundos  
**Download:** salvar como `/clips/clip_{index}.mp4`

**Fallback:** se Pexels retornar 0 resultados para a keyword, usar keyword genérica `dark mystery` antes de falhar.

### 4.2 — Música de Fundo

**Fonte:** Pixabay Music API (gratuita, sem autenticação)  
**Endpoint:** `GET https://pixabay.com/api/videos/?key={PIXABAY_KEY}&category=music&q=dark+cinematic&per_page=5`  
**Seleção:** primeiro resultado da lista  
**Download:** salvar como `background.mp3`

**Artefato de saída:** `/clips/clip_0.mp4` ... `/clips/clip_N.mp4`, `background.mp3`

---

## Módulo 5 — Montador de Vídeo

**Responsabilidade:** Sincronizar todos os artefatos em um único arquivo `.mp4` vertical (9:16) com legenda animada word-by-word.

**Ferramenta:** FFmpeg (CLI) + Python subprocess  
**Resolução de saída:** 1080x1920 (TikTok / Reels)

**Pipeline de montagem:**

**Passo 5.1 — Normalizar duração dos clipes**
Cada clipe de vídeo deve ter a duração exata do bloco de narração correspondente. Usar o tempo total entre o primeiro timestamp da primeira palavra do bloco e o último timestamp da última palavra do bloco.

```bash
ffmpeg -i clip_N.mp4 -t {duracao_bloco} -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" clip_N_trimmed.mp4
```

**Passo 5.2 — Concatenar todos os clipes trimados**
Gerar `concat_list.txt` e executar:
```bash
ffmpeg -f concat -safe 0 -i concat_list.txt -c copy video_base.mp4
```

**Passo 5.3 — Mixar áudio de narração + música de fundo**
Volume da narração: 1.0 | Volume da música: 0.15
```bash
ffmpeg -i narration.mp3 -i background.mp3 -filter_complex "[0:a]volume=1.0[a1];[1:a]volume=0.15[a2];[a1][a2]amix=inputs=2:duration=first[aout]" -map "[aout]" mixed_audio.mp3
```

**Passo 5.4 — Gerar arquivo de legendas SRT com timestamps**
Construir um `.srt` a partir do `timestamps.json` onde cada entrada contém 1 palavra. Usar os campos `start` e `end` diretamente.

**Passo 5.5 — Renderização final**
```bash
ffmpeg -i video_base.mp4 -i mixed_audio.mp3 \
  -vf "subtitles=subtitles.srt:force_style='FontName=Arial,FontSize=18,Bold=1,Alignment=2,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Shadow=1'" \
  -c:v libx264 -crf 23 -preset fast -c:a aac -b:a 192k \
  -shortest final_output.mp4
```

**Artefato de saída:** `final_output.mp4`

---

## Estrutura de Arquivos do Projeto

```
dark-video-pipeline/
├── main.py                  # Orquestrador principal (chama módulos em sequência)
├── modules/
│   ├── script_generator.py  # Módulo 1
│   ├── tts.py               # Módulo 2
│   ├── stt.py               # Módulo 3
│   ├── media_collector.py   # Módulo 4
│   └── video_assembler.py   # Módulo 5
├── .env                     # Variáveis de ambiente (não versionar)
├── requirements.txt
└── output/                  # Todos os artefatos intermediários e o final
    ├── roteiro.json
    ├── narration.mp3
    ├── timestamps.json
    ├── clips/
    ├── background.mp3
    ├── subtitles.srt
    └── final_output.mp4
```

---

## Variáveis de Ambiente (.env)

```
OPENROUTER_API_KEY=
PEXELS_API_KEY=
PIXABAY_API_KEY=
ELEVENLABS_API_KEY=          # Opcional, apenas se usar opção B no Módulo 2
```

---

## Dependências (requirements.txt)

```
requests
python-dotenv
kokoro-onnx
soundfile
openai-whisper
moviepy
ffmpeg-python
```

Requisito de sistema: `ffmpeg` instalado e disponível no PATH.

---

## Execução

```bash
python main.py --tema "O experimento secreto que o governo escondeu por décadas"
```

Output esperado: `output/final_output.mp4` pronto para upload.

---

## Open Questions

> [!WARNING]
> 1. **Voz:** Confirmar se usará Kokoro TTS (local, gratuito, qualidade menor) ou ElevenLabs (API paga, qualidade alta). A escolha define a implementação do Módulo 2.
> 2. **GPU local:** O Whisper no Módulo 3 roda em CPU mas é mais lento. Se houver GPU disponível, adicionar flag `--device cuda` para acelerar.
> 3. **Idioma da legenda:** O `language="pt"` no Whisper foi assumido como português. Confirmar se o conteúdo será sempre em PT-BR.

---

## Plano de Verificação

### Testes Automatizados
- Executar `main.py` com tema de teste: `"O dia em que a internet quase acabou"`
- Verificar que `roteiro.json` contém entre 8 e 14 blocos e alterna os tipos corretamente
- Verificar que `narration.mp3` tem duração maior que 20 segundos
- Verificar que `timestamps.json` tem pelo menos 30 entradas
- Verificar que `final_output.mp4` existe, tem resolução 1080x1920 e duração compatível com o áudio

### Verificação Manual
- Reproduzir `final_output.mp4` e confirmar: áudio audível, música de fundo presente no volume correto, legendas aparecendo word-by-word em sincronia com a voz, clipes de vídeo coerentes com o tema narrado.

# Módulo 5 — Análise Profunda da Complexidade

## 1. Visão Geral

O Módulo 5 é onde **tudo tem que funcionar juntos**. Você tem:
- **5-10 clipes de vídeo** com durações diferentes
- **1 narração em áudio** (30-40s)
- **Timestamps de cada palavra** (síncronização word-by-word)
- **Música de fundo** que precisa rodar junto
- **Resolução 1080x1920** (vertical, como TikTok)
- **Legendas sincronizadas palavra por palavra**

Qualquer erro em 1 dos 5 passos quebra tudo ou gera artefatos visuais/áudio ruins.

---

## 2. OS 5 PASSOS E SEUS PROBLEMAS

### **Passo 1: Normalizar Duração dos Clipes** ⚠️ CRÍTICO

**O que precisa acontecer:**
```
Bloco NARRACAO 1: "Tem um segredo que o governo..."
└─ Duração: 4.2s (timestamps[0].start até timestamps[5].end)
└─ Clip 1 (dark_laboratory.mp4): duração nativa = 7.8s
└─ Problema: Clip é 7.8s, mas narração é 4.2s
└─ Solução: Trimmar ou esticar para exatamente 4.2s
```

**Primeira abordagem (simples, ERRADA):**
```bash
ffmpeg -i clip_1.mp4 -t 4.2 -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" clip_1_trimmed.mp4
```

**Por quê está errado:**
- ✓ O vídeo fica com 4.2s
- ✗ **Mas e se o clip original fosse 2.5s?** Você não pode "esticar" um vídeo de 2.5s para 4.2s apenas com `-t`. Ele para na marca 2.5s. Fim do vídeo. A tela fica preta por 1.7s.
- ✗ Isso acontece frequentemente com B-roll de stock footage

**Solução correta (DIFÍCIL):**
```python
import subprocess

def normalize_clip_duration(input_clip, target_duration):
    # Passo 1: Descobrir duração nativa
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1:nokey=1",
        input_clip
    ]
    native_duration = float(subprocess.check_output(probe_cmd).decode().strip())
    
    # Passo 2: Decidir se precisa esticar, encurtar ou deixar como está
    ratio = target_duration / native_duration
    
    if ratio > 1.1:  # Precisa esticar mais de 10%
        # OPÇÃO A: Desacelerar tudo (áudio fica estranho)
        # OPÇÃO B: Loop o clip (mais profissional)
        print(f"⚠️ Clip {input_clip} é muito curto ({native_duration:.1f}s, precisa {target_duration}s)")
        print(f"    Solução: fazer loop ou usar clip alternativo")
        return None  # Falha — não tem solução fácil
    
    elif ratio < 0.95:  # Pode encurtar
        # Trimmar é seguro
        filter_str = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        cmd = [
            "ffmpeg", "-i", input_clip,
            "-t", str(target_duration),
            "-vf", filter_str,
            "-c:v", "libx264", "-crf", "23", "-preset", "veryfast",
            "-c:a", "copy",
            f"{input_clip}_norm.mp4"
        ]
        subprocess.run(cmd, check=True)
        return f"{input_clip}_norm.mp4"
    
    else:  # Muito próximo, deixar como está ou ajuste fino
        return input_clip
```

**Problemas reais que acontecem:**
1. **Clip é mais curto que a narração** → tela preta no final
2. **Clip é muito mais longo** → você trimma e perde a parte mais bonita
3. **Ratio de aspecto do clip é 16:9, não 9:16** → crop distorce a imagem
4. **A síncronização entre narração e B-roll não combina** → "O cara está falando sobre focos, mas o vídeo mostra um relógio"

---

### **Passo 2: Concatenar Clipes** 🔴 PROBLEMAS VISUAIS

**Comando simples:**
```bash
echo "file 'clip_1.mp4'" > concat_list.txt
echo "file 'clip_2.mp4'" >> concat_list.txt
echo "file 'clip_3.mp4'" >> concat_list.txt

ffmpeg -f concat -safe 0 -i concat_list.txt -c copy final.mp4
```

**Problemas:**
1. **Transições:** Quando clip_1 termina e clip_2 começa, há um frame preto ou artifato visual de ~100ms
   - Solução: usar `-vf "scale=..."` para re-encodar (lento), ou programar uma fade transition (complexo)

2. **Áudio sincronizado com vídeo:** Se você usar `-c copy`, mantém o codec original. Se os clipes têm codecs diferentes, FFmpeg pode reclamar.

3. **Duração incorreta:** Se algum clip foi normalizado para 4.2s mas o FFmpeg tem um erro off-by-one, pode sair 4.199s ou 4.201s. Multiplica para 8-10 clipes → até 0.08s de desvio acumulado. Suficiente para quebrar a sincronização de legendas.

**Solução robusta (CARA em processamento):**
```bash
ffmpeg -f concat -safe 0 -i concat_list.txt \
  -vf "fps=30,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" \
  -c:v libx264 -crf 23 -preset veryfast \
  -c:a aac -b:a 192k \
  video_concatenated.mp4
```

**Custo:**
- ⏱️ Re-encode de ~30-40s de vídeo = **5-8 minutos** em CPU single-core
- 🔴 Perda de qualidade (CRF 23 é razoável, mas não perfeito)

---

### **Passo 3: Mixar Áudio** 🟡 MODERADO

**Comando:**
```bash
ffmpeg -i narration.mp3 -i background.mp3 \
  -filter_complex "[0:a]volume=1.0[a1];[1:a]volume=0.15[a2];[a1][a2]amix=inputs=2:duration=first[aout]" \
  -map "[aout]" -c:a aac -b:a 192k mixed_audio.mp3
```

**Problemas:**
1. **Volume estático 0.15 é genérico:** Se a narração tem pausas longas, a música fica audível. Se a narração é muito alta, a música desaparece.
   - Solução: usar "dynamic range compression" (FFmpeg tem `-filter_complex "acompressor"`)
   - Custo: complexidade + 30% mais processamento

2. **Duração:** `duration=first` usa a duração do primeiro arquivo (narração). Se background.mp3 é mais curto, não há problema. Se for mais longo, é truncado — você pode perder o final da música.

3. **Mono vs Estéreo:** Se narration.mp3 é mono e background.mp3 é estéreo, o mix pode sair em estéreo com narração só no canal L ou R. Precisa de `-ac 2` para garantir estéreo balanceado.

**Solução robusta:**
```bash
ffmpeg -i narration.mp3 -i background.mp3 \
  -filter_complex "
    [0:a]volume=1.0,compressor=threshold=0.1:ratio=4:attack=0.05:release=0.1[a1];
    [1:a]volume=0.15[a2];
    [a1][a2]amix=inputs=2:duration=longest[aout]
  " \
  -map "[aout]" -c:a aac -b:a 192k -ac 2 \
  mixed_audio.mp3
```

**Custo:** ⏱️ ~5-10s (mais rápido que vídeo)

---

### **Passo 4: Gerar Legendas SRT** 🟡 MODERADO

**Entrada:** `timestamps.json`
```json
[
  { "word": "tem", "start": 0.0, "end": 0.35 },
  { "word": "um", "start": 0.35, "end": 0.58 },
  { "word": "segredo", "start": 0.58, "end": 1.2 },
  ...
]
```

**Saída esperada:** `subtitles.srt`
```srt
1
00:00:00,000 --> 00:00:00,350
tem

2
00:00:00,350 --> 00:00:00,580
um

3
00:00:00,580 --> 00:00:01,200
segredo
```

**Problemas:**
1. **Formação do SRT:** Cada entrada é 1 palavra, 3-5 linhas. 50 palavras = 150-250 linhas. Não é complexo, mas é tedioso.
2. **Sincronização:** Os timestamps precisam ser **exatamente** sincronizados com o áudio/vídeo. Se Whisper errou 0.1s em uma palavra, a legenda está 0.1s atrasada. Visível e irritante.

**Solução simples:**
```python
import json

def create_srt(timestamps_file, output_srt):
    with open(timestamps_file, 'r') as f:
        words = json.load(f)
    
    with open(output_srt, 'w', encoding='utf-8') as f:
        for idx, word in enumerate(words, 1):
            start = format_timecode(word['start'])  # "00:00:00,350"
            end = format_timecode(word['end'])
            f.write(f"{idx}\n{start} --> {end}\n{word['word']}\n\n")

def format_timecode(seconds):
    hours = int(seconds) // 3600
    minutes = (int(seconds) % 3600) // 60
    secs = int(seconds) % 60
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
```

**Custo:** ⏱️ < 1s

---

### **Passo 5: Renderizar Vídeo Final + Legendas** 🔴 O MAIS COMPLEXO

#### **Opção A: FFmpeg com subtitles.srt (Simples mas Limitado)**

```bash
ffmpeg -i video_base.mp4 -i mixed_audio.mp3 \
  -vf "subtitles=subtitles.srt:force_style='FontName=Arial,FontSize=18,Bold=1,Alignment=2,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Shadow=1'" \
  -c:v libx264 -crf 23 -preset veryfast \
  -c:a aac -b:a 192k \
  -shortest \
  final_output.mp4
```

**Problemas CRÍTICOS:**
1. **Font size 18px é PEQUENO demais em 1080x1920**
   - Na tela, 18px é quase ilegível
   - Precisa 28-32px no mínimo
   - Mas 32px text só mostra ~15 caracteres por linha
   - Palavras longas (ex: "profissionalismo") não cabem

2. **FontName=Arial pode não existir no servidor**
   - FFmpeg pode silenciosamente ignorar e usar fonte default
   - Resultado: você acha que está usando Arial Bold, mas está usando a fonte padrão feia

3. **Cores hardcoded em ABGR hexadecimal** (&HFFFFFF = branco, &H000000 = preto)
   - Se o fundo do clipe for branco, texto branco desaparece
   - Se o fundo for preto, precisa cor clara
   - Não há solução automática — cada bloco de narração precisa de cor adaptativa (impossível com FFmpeg libass)

4. **Word-by-word desaparece**
   - O FFmpeg libass renderiza **cada entrada SRT inteira**, não fade-in/fade-out suave
   - Uma palavra aparece, fica 200ms, desaparece de repente
   - Parece amador

5. **Re-encode:** O `-vf subtitles=...` força re-encode completo
   - Custo: **15-30 minutos** para ~40s de vídeo 1080x1920

#### **Opção B: OpenCV + Python (Complexo mas Profissional)**

Renderizar legendas manualmente, frame a frame:

```python
import cv2
import json
import numpy as np

def render_subtitles_on_video(video_path, audio_path, timestamps_json, output_path):
    # Passo 1: Carregar vídeo
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Passo 2: Carregar timestamps
    with open(timestamps_json, 'r') as f:
        words = json.load(f)
    
    # Passo 3: Preparar VideoWriter (re-encode necessário)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # Passo 4: Iterar frames
    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # Passo 5: Descobrir qual palavra deve aparecer AGORA
        current_time = frame_idx / fps
        current_word = None
        
        for word_data in words:
            if word_data['start'] <= current_time < word_data['end']:
                current_word = word_data
                break
        
        # Passo 6: Renderizar texto
        if current_word:
            text = current_word['word']
            
            # COMPLEXIDADE AQUI: onde colocar? que cor? que tamanho?
            # Opção simples: centro inferior
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.2
            color = (255, 255, 255)  # branco
            thickness = 2
            
            # Calcular tamanho do texto para centralizar
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            text_x = (width - text_size[0]) // 2
            text_y = height - 100
            
            # Renderizar com outline (para contraste)
            # Outline: desenhar o texto em preto 5x, depois em branco por cima
            for px in range(-2, 3):
                for py in range(-2, 3):
                    if px != 0 or py != 0:
                        cv2.putText(frame, text, 
                                   (text_x + px, text_y + py),
                                   font, font_scale, (0, 0, 0), thickness)
            
            cv2.putText(frame, text, 
                       (text_x, text_y),
                       font, font_scale, color, thickness)
        
        out.write(frame)
        frame_idx += 1
    
    cap.release()
    out.release()
```

**Vantagens:**
- ✓ Controle 100% sobre posição, cor, tamanho, efeitos
- ✓ Pode fazer fade-in/fade-out de palavras
- ✓ Pode adaptar cor dinamicamente (detectar fundo escuro/claro)
- ✓ Pode adicionar sombra, outline, glow

**Desvantagens:**
- ✗ Python + OpenCV é lento (frame-by-frame)
- ✗ Custo: **45-90 minutos** para ~40s de vídeo (vs 15-30 min com FFmpeg)
- ✗ Precisa re-encode completo mesmo assim
- ✗ Requer GPU CUDA para acelerar (nem sempre disponível)

#### **Opção C: MoviePy (Middle Ground)**

```python
from moviepy.editor import VideoFileClip, CompositeVideoClip, TextClip
import json

def add_subtitles_with_moviepy(video_path, audio_path, timestamps_json, output_path):
    video = VideoFileClip(video_path)
    
    with open(timestamps_json, 'r') as f:
        words = json.load(f)
    
    # Criar clips de texto para cada palavra
    text_clips = []
    for word_data in words:
        txt_clip = TextClip(
            word_data['word'],
            fontsize=32,
            color='white',
            font='Arial-Bold',
            method='caption',  # word wrap
            size=(width * 0.9, None),  # 90% da largura
            stroke_color='black',
            stroke_width=2
        ).set_position('bottom').set_duration(
            word_data['end'] - word_data['start']
        ).set_start(word_data['start'])
        
        text_clips.append(txt_clip)
    
    # Compor vídeo com texto
    final = CompositeVideoClip([video] + text_clips)
    final.write_videofile(output_path, codec='libx264', audio=audio_path)
```

**Custo:** ⏱️ ~40-60 minutos (semelhante ao OpenCV, mas interface mais simples)

---

## 3. TABELA COMPARATIVA DOS 3 APPROACHES DE LEGENDAS

| Aspecto | FFmpeg libass | OpenCV | MoviePy |
|---------|---|---|---|
| **Tempo de renderização (40s vídeo)** | 15-20 min | 60-90 min | 40-60 min |
| **Customização de cor** | Hardcoded, limitado | Dinâmica, ilimitada | Moderada |
| **Fade/efeitos de texto** | Não | Sim | Sim |
| **Detecção de fundo (auto-contraste)** | Não | Sim | Não |
| **Qualidade de fonte** | Depende do sistema | OpenCV é básico | Melhor (PIL) |
| **Debugging** | Difícil | Fácil (frames salvos) | Moderado |
| **Dependências** | FFmpeg | opencv-python + numpy | moviepy |

---

## 4. RESUMO: TEMPO TOTAL DE PROCESSAMENTO

Para um vídeo de **~35 segundos** de narração (8-10 blocos de vídeo):

| Passo | Tempo | Notas |
|-------|-------|-------|
| 1. Normalizar clips | 2-4 min | Depende de quantos clips precisam ser re-encode |
| 2. Concatenar clips | 5-8 min | Se re-encodar |
| 3. Mixar áudio | 0.5-1 min | Rápido |
| 4. Gerar SRT | < 1 seg | Negligenciável |
| 5a. Legendas (FFmpeg) | 15-20 min | ⚠️ Re-encode final |
| 5b. Legendas (OpenCV) | 60-90 min | 🔴 Muito lento |
| 5c. Legendas (MoviePy) | 40-60 min | 🟡 Meio termo |
| **TOTAL (A)** | **~25-35 min** | **FFmpeg é o mais rápido** |
| **TOTAL (B)** | **~70-100 min** | **Muita qualidade, muito tempo** |
| **TOTAL (C)** | **~50-70 min** | **Bom compromisso** |

---

## 5. RECOMENDAÇÃO PRÁTICA

### **Para MVP (primeiro mês):**
- Use **FFmpeg libass** (Opção A)
- Legendas em blocos inteiros, não word-by-word
- Font size 24-28px
- Aceite que não será perfeito

### **Próxima iteração (semana 3-4):**
- Mude para **MoviePy** (Opção C)
- Word-by-word com fade-in/out suave
- Detecção de cor dinâmica para contraste

### **Polish final (semana 5+):**
- **OpenCV com GPU CUDA** se tiver acesso
- Efeitos avançados: shadow, blur, glow
- Auto-detect posição ideal de legenda (topo se clipe tem ação embaixo)

---

## 6. CÓDIGO ESQUELETO DO MÓDULO 5 (MVP)

```python
import subprocess
import json
import os

class VideoAssembler:
    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
    
    def run_pipeline(self, roteiro_json, narration_mp3, timestamps_json, 
                     clips_dir, background_mp3):
        """Orquestra os 5 passos."""
        
        print("[1/5] Normalizando duração dos clips...")
        normalized_clips = self.normalize_clips(clips_dir, roteiro_json, timestamps_json)
        
        print("[2/5] Concatenando clips...")
        video_base = self.concatenate_clips(normalized_clips)
        
        print("[3/5] Mixando áudio...")
        mixed_audio = self.mix_audio(narration_mp3, background_mp3)
        
        print("[4/5] Gerando SRT...")
        srt_file = self.create_srt(timestamps_json)
        
        print("[5/5] Renderizando vídeo final...")
        final_video = self.render_final(video_base, mixed_audio, srt_file)
        
        print(f"✓ Concluído: {final_video}")
        return final_video
    
    def normalize_clips(self, clips_dir, roteiro_json, timestamps_json):
        """Passo 1: Ajustar duração de cada clip para a narração correspondente."""
        with open(roteiro_json) as f:
            roteiro = json.load(f)
        with open(timestamps_json) as f:
            timestamps = json.load(f)
        
        normalized = []
        # ... (lógica complexa aqui)
        return normalized
    
    def concatenate_clips(self, clip_files):
        """Passo 2: Juntar todos em um arquivo."""
        # ... (gera concat_list.txt, roda ffmpeg)
        pass
    
    def mix_audio(self, narration, background):
        """Passo 3: Misturar áudio."""
        # ... (amix com volumes corretos)
        pass
    
    def create_srt(self, timestamps_json):
        """Passo 4: Gerar arquivo de legendas."""
        # ... (itera timestamps, cria SRT)
        pass
    
    def render_final(self, video, audio, srt):
        """Passo 5: Legendas + áudio + vídeo = saída final."""
        # ... (ffmpeg com filtro de legendas)
        pass
```

---

## 7. OPEN QUESTIONS & TRADE-OFFS

1. **GPU disponível?** Se sim, use NVIDIA NVENC em vez de libx264 (10-15× mais rápido)
2. **Qualidade vs. tempo?** CRF 23 (padrão) vs CRF 18 (melhor, mais lento)
3. **Resolução final?** 1080x1920 é bom para TikTok. Se quiser 4K, multiplique tempo por 4-6×
4. **Legendas word-by-word ou bloco inteiro?** Word-by-word é impressionante mas 2-3× mais lento
5. **Fonte customizada?** Arial/Helvetica vs fontes estranhas — pode não renderizar no servidor


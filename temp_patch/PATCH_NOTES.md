# PATCH v2 — Dark Video Pipeline

## O que mudou nessa versão

### FIX 1 — Variedade de B-Roll (media_collector.py)
**Problema:** O mesmo clipe repetia em todo o vídeo.  
**Solução:** `CLIPS_PER_BLOCK = 3` — agora são baixados 3 clips distintos por bloco VISUAL.
O Módulo 5 divide a duração total do bloco entre os clips e os corta em sequência.
Um set `used_urls` garante que o mesmo clip nunca aparece duas vezes.

### FIX 2 — Posição da legenda (video_assembler.py)
**Problema:** Legenda centralizada cobria área de interesse do vídeo.  
**Solução:** `MarginV=200` no parâmetro `force_style` do FFmpeg.
A legenda agora fica no terço inferior da tela, fora dos botões do TikTok.

### FIX 3 — Tamanho da fonte (video_assembler.py)
**Problema:** Fonte pequena (18px) difícil de ler em mobile.  
**Solução:** `FontSize=24` — mais legível sem tomar muito espaço.

### FIX 4 — Merge de tokens numéricos/símbolos (stt.py)
**Problema:** Whisper separava "90" e "%" em dois tokens, gerando legenda piscante com símbolo isolado.  
**Solução:** Função `merge_tokens()` no stt.py que detecta e une:
- Número + símbolo: `"90"` + `"%"` → `"90%"`
- Símbolo líder + número: `"$"` + `"100"` → `"$100"`
- Pontuação isolada: colada na palavra anterior
- Anos quebrados: `"1"` + `"986"` → `"1986"`

---

## Arquivos alterados

```
patches/
├── main.py                        # Orquestrador atualizado
└── modules/
    ├── media_collector.py          # FIX 1: multi-clip por bloco
    ├── stt.py                      # FIX 4: merge_tokens + build_srt
    └── video_assembler.py          # FIX 1+2+3: montagem, legenda, fonte
```

## Como aplicar

Copie os arquivos da pasta `patches/modules/` para `dark-video-pipeline/modules/`
e o `patches/main.py` para `dark-video-pipeline/main.py`.

```bash
cp patches/modules/media_collector.py dark-video-pipeline/modules/
cp patches/modules/stt.py dark-video-pipeline/modules/
cp patches/modules/video_assembler.py dark-video-pipeline/modules/
cp patches/main.py dark-video-pipeline/
```

Rode normalmente:
```bash
python main.py --tema "O experimento que o governo escondeu"
```

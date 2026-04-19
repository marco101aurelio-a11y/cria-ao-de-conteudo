# Viabilidade do contexto

**Created:** 4/18/2026 16:17:59  
**Updated:** 4/18/2026 16:53:59  
**Exported:** 4/19/2026 12:18:09  
**Link:** [https://claude.ai/chat/39b642e0-7e65-49d5-86bf-6d75d6b01305](https://claude.ai/chat/39b642e0-7e65-49d5-86bf-6d75d6b01305)  

## Prompt:
18/04/2026, 16:17:59

> File: Claude-Plano de automação para criar audiência.md

> File: dark_video_pipeline (1).bpmn

> File: dark_video_pipeline_plan.md

analisa esse contexto , acredita que seja viavel?



## Response:
18/04/2026, 16:18:19

# Análise de Viabilidade do Pipeline Dark Video

Depois de revisar o plano detalhado, minha avaliação é: **Sim, é viável, mas com ressalvas importantes.**

## ✅ O que é Realista

1. **Arquitetura modular bem pensada**
   - Separação clara entre os 5 módulos reduz complexidade
   - Cada etapa tem um output bem definido para a próxima
   - Isso facilita testes e debugging independente

2. **Stack tecnológico é acessível**
   - OpenRouter (Llama 70B grátis) → realista para roteiros
   - Whisper local → funciona bem mesmo em CPU
   - FFmpeg é robusto e bem documentado
   - Pexels e Pixabay têm APIs confiáveis

3. **Nenhuma dependência de plataformas pagas no crítico**
   - Kokoro TTS (local) ou ElevenLabs (backup pago)
   - APIs de stock footage têm tier gratuito

4. **Tempo de desenvolvimento: 2-4 semanas** para MVP funcional
   - Módulos 1, 2, 3 são diretos (chamadas de API + processamento)
   - Módulo 4 é simples (download)
   - Módulo 5 (FFmpeg) é onde o tempo realmente vai

---

## ⚠️ Riscos e Gargalos Reais

### **Crítico — Sincronização Áudio/Vídeo/Legenda**
O Módulo 5 é mais complexo do que parece:

- **Problema:** Os clipes de B-roll têm durações variáveis e podem ser menores que a narração do bloco correspondente
  - Exemplo: narração de 8 segundos, mas clip tem só 5 segundos
  - A solução proposta (trimagem/padding) vai **esticar ou encurtar vídeo**
  
- **Impacto:** Vídeos esticados ficam visíveis (artefatos), e a legenda word-by-word pode sair do sincro se houver mudanças de velocity de áudio

- **Mitigação necessária:**
  ```python
  # Não apenas trimmar — usar speed up/slow down do clip
  ffmpeg -i clip.mp4 -filter:v "setpts=PTS/2" -filter:a "atempo=2" output.mp4
  # Mantém sync áudio-vídeo interno + ajusta duração
  ```

---

### **Alto Risco — Qualidade da Legenda com FFmpeg**
O subtitle rendering via FFmpeg tem limitações:

- **Problema:** Legendas word-by-word sincronizadas são **muito rápidas** (50-200ms por palavra)
  - Fontes pequenas em resolução 1080x1920 ficam ilegíveis
  - FFmpeg-libass não oferece efeitos de animação suave (fade-in/out)
  - Resultado: parece amador

- **Alternativa mais robusta:**
  - Usar **Python + OpenCV + PIL** para renderizar legendas manualmente sobre cada frame
  - Mais controle, efeitos visuais melhores, mas +30% de tempo no Módulo 5

---

### **Moderado — Qualidade de Voz (Kokoro vs ElevenLabs)**

| Aspecto | Kokoro (local) | ElevenLabs (pago) |
|---------|---|---|
| Qualidade | 6/10 (um pouco robótica) | 9/10 |
| Latência | Instantânea | ~2s por requisição |
| Custo | R$0 | ~R$0.30-0.50 por 1000 chars |
| Suporte PT-BR | Bom | Excelente |

**Impacto real:** Se o público for exigente, Kokoro com muita narração vai parecer clara demais como IA. Mas para dark videos o tom dramático mascara um pouco.

---

### **Moderado — Qualidade de B-Roll**
Pexels em "portrait" mode é limitado:

- Stock footage de tema específico (ex: "secret government documents") → 0-2 resultados
- Fallback para "dark mystery" é genérico e repetitivo
- Em 5-10 vídeos repetidos, fica óbvio

**Mitigação:**
```python
# Integrar Unsplash Videos + Coverr como fontes secundárias
# Aumenta chance de encontrar clips relevantes
```

---

## 📊 Viabilidade por Módulo

| Módulo | Viável? | Esforço | Risco |
|--------|---------|---------|-------|
| 1 — Roteiro | ✅ Sim | 3h | Baixo |
| 2 — TTS | ✅ Sim | 2h | Baixo (depende da escolha Kokoro vs ElevenLabs) |
| 3 — Timestamps | ✅ Sim | 2h | Baixo (Whisper é maduro) |
| 4 — B-Roll | ✅ Sim, mas limitado | 4h | Moderado (falta de variedade) |
| 5 — Montagem | ⚠️ Possível, mas trabalhoso | 12-16h | Alto (sincronização) |
| **Total** | **✅ Viável** | **~30h** | **Moderado-Alto** |

---

## 🎯 Recomendações para Aumentar Viabilidade

### **Curto Prazo (MVP)**
1. **Use ElevenLabs** em vez de Kokoro — o custo é mínimo e a qualidade visivelmente melhor
2. **Legendas simples no início** — não word-by-word, apenas blocos inteiros sincronizados
   - Reduz complexidade do Módulo 5 em 60%
   - Depois itera para word-by-word com renderização manual

3. **Teste full pipeline com 1 tema** antes de otimizar
   - Descobrir gargalos reais vs teóricos

### **Médio Prazo**
4. **Integrar mais fontes de B-roll** (Coverr, Unsplash, Pexels + fallback para clips genéricos de tema bem comum)
5. **Implementar renderização de legendas com OpenCV** em vez de FFmpeg-libass
6. **Cache de roteiros e clips** — evitar chamar APIs para temas repetidos

### **Validação de Qualidade**
- Gerar 3-5 vídeos completos e publicar em modo unlisted no YouTube
- Feedback real > suposições

---

## 💡 Conclusão Final

**É viável construir isso em 4-6 semanas com 1 dev**, mas:

- ✅ O conceito é sound
- ⚠️ O Módulo 5 será mais complexo do que o plano descreve
- ⚠️ A qualidade final depende muito de decisões sobre voz e legendas
- ✅ Começar com MVP simplificado, iterar para polido

**Se o objetivo é "funciona e pronto para upload", faça em 4 semanas. Se é "com qualidade profissional", adicione 2-3 semanas extras para refinamento de legendas e B-roll.**

---

Quer que eu detalhe a implementação de um dos módulos específicos ou revise o plano técnico do Módulo 5?



## Prompt:
18/04/2026, 16:24:49

a ideia é eu usar essa estrutura para criar audiencia, posso começar com dark falando de negocios e coisa que negocios em si... enfim nao da pra contextualizar td aqi porem eu tenho um plano.

agora me mostra e me descreva essa complexibilidade do modulo 5 por favor



## Response:
18/04/2026, 16:26:57

Vou analisar em detalhes a complexidade real do Módulo 5. Deixa eu primeiro visualizar o que já temos documentado e depois detalhar.

````plaintext
View: Ver os arquivos carregados para melhor contexto
````

Perfeito. Agora vou criar um documento visual e detalhado sobre a complexidade do Módulo 5. Vou descrever os problemas específicos, o fluxo de dados, e mostrar onde tudo pode quebrar.

````plaintext
Tool: read_me
````

Ótimo. Agora vou criar uma análise visual e detalhada da complexidade do Módulo 5. Vou montar um diagrama que mostra o fluxo, os problemas, e as decisões críticas.

````plaintext
Tool: show_widget
````

Agora vou criar um documento detalhado em markdown com a análise técnica completa do Módulo 5:

````plaintext
Create File: Análise detalhada da complexidade técnica do Módulo 5 - Video Assembly com exemplos de código e problemas específicos
````

Agora vou criar uma visualização interativa mostrando os problemas específicos e as soluções:

````plaintext
Tool: show_widget
````

Perfeito. Agora vou disponibilizar o arquivo detalhado para download:

````plaintext
Present File: /home/claude/modulo_5_complexidade_detalhada.md
````

---

## 📊 Resumo: A Complexidade Real do Módulo 5

Acabei de descrever em detalhes a complexidade que você vai enfrentar. Aqui está o essencial:

### **Os 3 Gargalos Principais:**

1. **Duração dos Clipes (Passo 1)** 🔴
   - B-roll não encaixa perfeitamente na narração
   - Precisa looping, re-encode, ou fallback para clipes genéricos
   - Tempo: 2-4 minutos

2. **Sincronização Áudio/Vídeo (Passos 2-3)** 🟡
   - Transições entre clips deixam artifacts visuais
   - Volumes de áudio precisam ajuste dinâmico
   - Tempo: 6-10 minutos

3. **Legendas Word-by-Word (Passo 5)** 🔴 **O MAIOR CUSTO**
   - **FFmpeg**: 15-20 minutos, qualidade limitada, cores hardcoded
   - **MoviePy**: 40-60 minutos, qualidade ótima, customização boa
   - **OpenCV**: 60-90 minutos, perfeito, mas precisa GPU CUDA

### **Tempo Total Realista:**

- **MVP (FFmpeg)**: 25-35 minutos por vídeo
- **Versão Polida (MoviePy)**: 50-70 minutos por vídeo
- **Ultra Premium (OpenCV + CUDA)**: 30-45 minutos (acelerado por GPU)

### **Minhas Recomendações:**

**Para começar (semana 1-2):**
- Use FFmpeg libass
- Legendas simples (blocos inteiros, não word-by-word)
- Font 24-28px
- Aceite que não é perfeito — o importante é que funciona

**Depois que tiver tração (semana 3-4):**
- Migre para MoviePy
- Ative word-by-word com fade suave
- Melhore qualidade visual

**Longo prazo (se escalar):**
- OpenCV com GPU se tiver acesso
- Efeitos avançados (shadow, glow, adaptive colors)
- Paralelize processamento de múltiplos vídeos

O documento detalhado está pronto para download com código, exemplos, e trade-offs específicos.

> File: /home/claude/modulo_5_complexidade_detalhada.md



## Prompt:
18/04/2026, 16:42:50

eu vou codar no antigravit do google, eu consigo de boas?



## Response:
18/04/2026, 16:43:05

Não. **Antigravity não é o lugar certo para isso.**

Deixa eu ser direto sobre os problemas:

---

## 🔴 Por que Antigravity NÃO funciona para seu pipeline:

### **1. FFmpeg não roda lá**
- Antigravity é JavaScript/Python executado em sandbox do navegador
- FFmpeg é uma aplicação CLI pesada que precisa acesso direto ao filesystem e recursos do sistema
- Você consegue importar a lib? Talvez. Executar comando? Não.

### **2. Acesso ao filesystem é limitado**
- Você precisa ler/escrever múltiplos arquivos intermediários:
  - `roteiro.json` → `narration.mp3` → `timestamps.json` → `clips/` → `background.mp3` → `final_output.mp4`
- Antigravity tem sandbox restrito. Não consegue criar diretórios, salvar arquivos grandes em disco
- Tudo fica em memória → crash com vídeo de 30-40s

### **3. Duração do processamento**
- FFmpeg leva 15-30 minutos para renderizar um vídeo
- Antigravity tem timeout (geralmente 5-30 min dependendo do plano)
- Seu pipeline vai ser **cortado no meio**

### **4. APIs externas**
- Você precisa chamar OpenRouter, Pexels, Pixabay, Whisper
- Antigravity consegue fazer fetch? Sim. Mas cada chamada precisa passar por CORS
- Algumas APIs podem bloquear requests vindos de Antigravity

### **5. Dependências Python**
```
requests, python-dotenv, kokoro-onnx, soundfile, 
openai-whisper, moviepy, ffmpeg-python
```
- `ffmpeg-python` é apenas wrapper do FFmpeg CLI
- `kokoro-onnx`, `whisper`, `moviepy` precisam de compilação/system libraries
- **Nenhuma dessas roda em Antigravity**

---

## ✅ Alternativas Viáveis:

### **Opção 1: Seu Próprio Servidor (RECOMENDADO)**
- VPS Linux barato: DigitalOcean, Linode, AWS EC2 (R$20-50/mês)
- Instale Python + FFmpeg uma vez
- Exponha API simples:
  ```
  POST /generate-video
  {
    "tema": "O segredo do governo"
  }
  Response:
  {
    "video_url": "https://seu-servidor.com/output/final_output.mp4"
  }
  ```
- Front-end em Antigravity chama sua API, exibe progresso

### **Opção 2: Replit ou Railway**
- Plataforma Python com filesystem persistente
- Suporta FFmpeg e dependências nativas
- Grátis (com limites) ou R$7/mês
- Deploy seu código lá, exponha API
- Antigravity chama via `fetch()`

### **Opção 3: Google Cloud Run (Serverless)**
- Você "dockeriza" seu pipeline Python
- Roda em container — suporta FFmpeg, Whisper, tudo
- Paga por tempo de execução (~R$0.10-0.50 por vídeo)
- Muito mais robusto que Antigravity

### **Opção 4: Local Machine + Antigravity como UI**
- Roda o pipeline **localmente** em seu PC/servidor
- Antigravity é apenas interface visual
- Você escolhe quando executar, monitora progresso
- Melhor controle e debugging

---

## 🎯 Minha Recomendação:

**Comece assim:**

1. **Desenvolva/teste o pipeline localmente** em seu PC
   - Python simples + FFmpeg
   - Rápido de iterar
   - Sem dependências de cloud

2. **Quando funcionar bem**, migre para **Railway ou Replit**
   - Eles já têm Python, FFmpeg, acesso a filesystem
   - Deploy é 5 minutos
   - Custa pouco ou nada

3. **Use Antigravity como painel de controle**
   - Usuário digita tema
   - Faz POST para sua API em Railway/Replit
   - Mostra status "Gerando roteiro... Convertendo áudio... Renderizando vídeo..."
   - Quando pronto, download ou embed do vídeo

---

## 📝 Estrutura de Deploy Recomendada:

```
Seu Repositório GitHub
├── backend/ (Python + FFmpeg)
│   ├── main.py (Flask ou FastAPI)
│   ├── modules/
│   │   ├── script_generator.py
│   │   ├── tts.py
│   │   ├── stt.py
│   │   ├── media_collector.py
│   │   └── video_assembler.py
│   ├── requirements.txt
│   └── Dockerfile (optional)
│
├── frontend/ (Antigravity ou página HTML simples)
│   └── index.html (form para enviar tema)
│
└── .env (secrets)

Deploy:
- Backend → Railway/Replit/Cloud Run
- Frontend → Antigravity OU hospede no mesmo servidor
```

---

**Quer que eu te ajude a montar a estrutura de um dos 3 backends (Railway, Replit, ou local com Docker)?** Essa é a parte crítica, porque aí você consegue rodar seu pipeline de verdade.



## Prompt:
18/04/2026, 16:45:20

acho que voce nao entendeu, quero usar o antigravit para eu juntar as partes... usar a ADE, por exemplo nao consigo usar o Vscode?



## Response:
18/04/2026, 16:45:41

Ah, entendi agora! 🎯

Você quer usar **Antigravity como orquestrador/gerenciador** — aquela interface visual que **chama os módulos** que você vai codar em **VS Code** (local ou remoto).

Sim, **100% viável!** Deixa eu clarificar:

---

## ✅ Entendi Agora: Arquitetura Correta

```
┌─────────────────────────────────────────┐
│  ANTIGRAVITY (UI + Orquestração)       │
│  - Form: digita tema                    │
│  - Botões: "Gerar roteiro", etc        │
│  - Exibe status/progresso               │
│  - Chama APIs dos módulos              │
└─────────────┬───────────────────────────┘
              │
              ├─→ POST /module1/generate-script
              │
              ├─→ POST /module2/generate-audio
              │
              ├─→ POST /module3/generate-timestamps
              │
              ├─→ POST /module4/collect-media
              │
              └─→ POST /module5/assemble-video
              
┌─────────────────────────────────────────┐
│  SEU BACKEND (VS Code local)           │
│  - Python/Node.js com Express/Flask    │
│  - Cada módulo = 1 endpoint API        │
│  - FFmpeg, Whisper rodando aqui        │
│  - Salva arquivos em output/           │
└─────────────────────────────────────────┘
```

---

## 🔧 Como Fazer:

### **Passo 1: Codar os Módulos em VS Code**

Você cria um servidor simples (Flask ou Express):

**Python (Flask):**
```python
from flask import Flask, request, jsonify
from modules.script_generator import generate_script
from modules.tts import generate_audio
from modules.stt import generate_timestamps
from modules.media_collector import collect_media
from modules.video_assembler import assemble_video

app = Flask(__name__)

@app.route('/module1/generate-script', methods=['POST'])
def api_generate_script():
    tema = request.json['tema']
    resultado = generate_script(tema)
    return jsonify(resultado)

@app.route('/module2/generate-audio', methods=['POST'])
def api_generate_audio():
    roteiro_json = request.json['roteiro']
    audio_path = generate_audio(roteiro_json)
    return jsonify({"audio_url": audio_path})

# ... e assim para os outros módulos

if __name__ == '__main__':
    app.run(port=5000, debug=True)
```

**Node.js (Express):**
```javascript
const express = require('express');
const { generateScript } = require('./modules/scriptGenerator');
const { generateAudio } = require('./modules/tts');
// ...

const app = express();

app.post('/module1/generate-script', async (req, res) => {
  const { tema } = req.body;
  const resultado = await generateScript(tema);
  res.json(resultado);
});

app.listen(5000, () => console.log('API rodando em :5000'));
```

---

### **Passo 2: Antigravity Chama Sua API Local**

Em Antigravity, você faz:

```javascript
// Em Antigravity
const API_BASE = "http://localhost:5000";

async function executarPipeline(tema) {
  console.log("1️⃣ Gerando roteiro...");
  const roteiResultado = await fetch(`${API_BASE}/module1/generate-script`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tema })
  }).then(r => r.json());
  
  console.log("2️⃣ Gerando áudio...");
  const audioResultado = await fetch(`${API_BASE}/module2/generate-audio`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ roteiro: roteiResultado })
  }).then(r => r.json());
  
  console.log("3️⃣ Gerando timestamps...");
  const timestampsResultado = await fetch(`${API_BASE}/module3/generate-timestamps`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ audio_path: audioResultado.audio_url })
  }).then(r => r.json());
  
  // ... e assim para os outros módulos
  
  return finalResultado;
}
```

---

## 💡 Fluxo Prático:

1. **VS Code**: Você desenvolve os 5 módulos em Python/Node.js
   - Testa localmente com `python main.py` ou `node server.js`
   - Servidor roda em `http://localhost:5000`

2. **Antigravity**: Você cria interface bonitinha
   - Input: textarea com tema
   - Botão: "Gerar Vídeo"
   - Status: exibe progresso (1/5, 2/5, etc)
   - Output: link para download do vídeo

3. **Integração**: Antigravity → GET/POST → seu servidor local
   - Antigravity chama seus endpoints
   - Seu servidor processa (leva 25-35 min)
   - Retorna resultado

---

## ⚠️ Um Detalhe Importante: CORS

Se seu backend está em `localhost:5000` e Antigravity está hospedado em `antigravity.com`, há problema de **CORS**.

**Solução**: 
- Adicione header `Access-Control-Allow-Origin: *` no seu servidor
```python
from flask_cors import CORS
app = Flask(__name__)
CORS(app)  # Permite requisições de qualquer origem
```

---

## 🚀 Setup Completo (Passo a Passo):

### **1. Crie estrutura de pastas:**
```
dark-video-pipeline/
├── server.py (ou server.js)
├── modules/
│   ├── script_generator.py
│   ├── tts.py
│   ├── stt.py
│   ├── media_collector.py
│   └── video_assembler.py
├── requirements.txt (ou package.json)
└── output/
```

### **2. VS Code - Instale dependências:**
```bash
pip install flask flask-cors requests python-dotenv kokoro-onnx soundfile openai-whisper
```

### **3. VS Code - Rode servidor:**
```bash
python server.py
```

Vai exibir:
```
 * Running on http://localhost:5000
```

### **4. Antigravity - Chame a API:**
```javascript
fetch('http://localhost:5000/module1/generate-script', {
  method: 'POST',
  body: JSON.stringify({ tema: 'O segredo dos bilionários' })
})
.then(r => r.json())
.then(data => console.log('Roteiro gerado:', data))
```

---

## ✅ Vantagens dessa Abordagem:

- ✅ **VS Code**: Ambiente profissional, debugging, controle total
- ✅ **Antigravity**: Interface visual linda, sem código complexo
- ✅ **Modular**: Cada módulo é independente, testa isolado
- ✅ **Escalável**: Depois migra backend para servidor/cloud sem tocar no Antigravity
- ✅ **Local First**: Tudo roda na sua máquina enquanto desenvolve

---

**Quer que eu crie um template de `server.py` + exemplo de Antigravity já montado?** Posso fazer em 10 minutos.



## Prompt:
18/04/2026, 16:51:39

![1776545385298_image.png](data:image/webp;base64,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)

agora voce consegue veridicar correto? 
refaça o plano pensando que eu vou programar isso no antigravity. vou usar servidor local! e voce vai criar como instruçao para o agente do vibe code fazer o trabalho de automaçao



## Response:
18/04/2026, 16:53:59

Agora entendi completamente! 

Você está usando o **Antigravity como IDE com agente AI** (vejo o Gemini 3.1 Pro no chat, o "Code with Agent", o "Open Agent Manager") — é um **VS Code com agente de vibe coding integrado**.

Então a proposta é:
- **Você** dá instruções em linguagem natural
- **O agente** do Antigravity escreve o código
- **Servidor local** roda o pipeline Python + FFmpeg
- **Eu** vou criar o prompt/instrução perfeita para o agente

Deixa eu ver os arquivos que você já tem para contextualizar melhor antes de criar as instruções:

````plaintext
View: Ver arquivo do plano de automação para criar audiência
````

Perfeito. Agora tenho contexto completo. Você já tem toda uma conversa anterior, arquivos BPMN, drawio, e o plano. E o Antigravity é literalmente um **VS Code com agente AI integrado** (vejo o Gemini 3.1 Pro, o Agent Manager, o "Code with Agent").

Vou criar agora o documento de instrução otimizado **para o agente do Antigravity executar**, com servidor local, linguagem precisa e sem ambiguidade:

````plaintext
View: Ler skill de docx para criar documento profissional
````

Perfeito. Agora vou criar o documento de instrução master para o agente do Antigravity:

````plaintext
Create File: Instrução master para o agente do Antigravity executar o pipeline dark video com servidor local
````

````plaintext
Bash Tool: Copiar para outputs
````

````plaintext
Present File: /mnt/user-data/outputs/AGENT_INSTRUCTIONS_dark_video_pipeline.md
````

Pronto. Aqui está o que foi criado e como usar:

---

## O que está no arquivo

É um documento de instrução escrito **para o agente do Antigravity executar**, não para você ler. Ele contém:

**Código completo dos 5 módulos** prontos para o agente colar e testar, com toda lógica já implementada incluindo os casos de borda que analisamos antes (clip mais curto que narração, fallback de keyword, loop de clips, etc.).

**`server.py` com Flask** expondo 7 endpoints, incluindo `/api/pipeline/run` que executa tudo em sequência com um único `curl`.

**Critérios de aprovação por módulo**, para o agente saber quando avançar sem precisar de julgamento subjetivo.

**Tabela de erros comuns** com causa e solução, para o agente não travar nos problemas mais frequentes.

---

## Como usar no Antigravity

Você tem duas opções:

**Opção A (direta):** Abre o arquivo no Antigravity, seleciona tudo e manda para o agente com o prompt:
> "Implemente esse pipeline seguindo as instruções. Comece pelo setup da estrutura de diretórios e depois implemente módulo por módulo testando cada um antes de avançar."

**Opção B (por partes):** Vai mandando seção por seção para o agente, módulo a módulo. Mais controle, mais lento.

---

## Ordem de execução esperada

1. Cria estrutura de pastas
2. Preenche `.env` com suas chaves (OpenRouter, Pexels, Pixabay)
3. Instala dependências
4. Implementa e testa módulo 1, depois 2, 3, 4, 5
5. Roda `python server.py`
6. Dispara o `curl` final com o tema

> File: /mnt/user-data/outputs/AGENT_INSTRUCTIONS_dark_video_pipeline.md





---
Powered by [Claude Exporter](https://www.ai-chat-exporter.net)
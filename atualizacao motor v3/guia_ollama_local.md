# 🤖 Guia de Uso: Ollama & Llama 3.2 Local

Você configurou o seu pipeline para rodar com o **Llama 3.2 (3B)** rodando localmente! Isso é excelente porque elimina custos de API e garante privacidade. No entanto, em computadores com **8GB de RAM e placa de vídeo de 4GB (como a GTX 1650)**, o uso local exige alguns cuidados específicos para evitar travamentos, lentidão ("bugs") e falhas de conexão.

Abaixo está o passo a passo completo para entender o funcionamento, resolver os erros e otimizar o seu sistema.

---

## 🔍 O Diagnóstico do Erro Atual
Fizemos um teste interno de conexão com o seu servidor local e o erro retornado foi:
`[WinError 10061] Nenhuma conexão pôde ser feita porque a máquina de destino as recusou ativamente`

**O que isso significa?**
O seu pipeline tentou se conectar ao Ollama na porta `11434`, mas o **servidor do Ollama não está iniciado** ou o comando digitado no terminal foi incorreto.

---

## 🛠️ Passo 1: Como Iniciar o Ollama Corretamente

O comando correto para rodar o Ollama é `ollama serve` (com **O** e dois **L**s, tudo em minúsculo). Se você digitar `Lamaa serve`, o terminal não reconhecerá o comando.

### Como ligar o Ollama:
1. Abra um terminal comum (PowerShell ou CMD).
2. Execute o comando:
   ```powershell
   ollama serve
   ```
   > [!TIP]
   > No Windows, o Ollama normalmente já inicia junto com o sistema e fica rodando silenciosamente na **barra de tarefas** (próximo ao relógio, com um ícone de lhama cinza). Se o ícone estiver lá, o servidor já está ativo!

3. Abra um **segundo terminal** e certifique-se de que o modelo está baixado no seu computador executando:
   ```powershell
   ollama pull llama3.2:3b
   ```
   *Se você não rodar o `pull` primeiro, o pipeline falhará porque o Ollama não encontrará o modelo.*

---

## 💡 Passo 2: Direct Ollama vs. Braços (Economizando Memória)

No seu projeto, existem duas formas de usar o Llama 3.2 local:
1. **OLLAMA DIRECT (Recomendado para o seu PC)**: O pipeline fala diretamente com o Ollama.
2. **BRAÇOS (FastAPI)**: Roda 3 servidores FastAPI locais em segundo plano (`start_all.ps1`).

No seu arquivo de configurações `backend/.env`, a opção ativa é:
```env
LLM_PROVIDER=ollama
USE_OLLAMA=True
```

### O que isso significa para o seu hardware (8GB RAM)?
Como você configurou o `LLM_PROVIDER=ollama`, o pipeline do Dark Video acessa o Ollama **diretamente**. 
* **Você NÃO precisa rodar o script `.\start_all.ps1`!**
* Rodar o `start_all.ps1` vai abrir 3 servidores FastAPI adicionais em segundo plano, consumindo cerca de **1.5 GB a 2 GB da sua valiosa memória RAM**. 
* **Economize recursos**: Apenas abra o Ollama (`ollama serve`) e execute o pipeline diretamente.

---

## 🚀 Passo 3: Rodando o Pipeline sem Travamentos

Com a sua configuração de hardware (**8GB RAM + 4GB VRAM**), o Windows e o Ollama vão disputar recursos. Para rodar o pipeline liso, siga estas diretrizes:

### 1. Feche programas pesados
Antes de rodar o pipeline, feche navegadores (Chrome, Edge), Discord e outros programas que consomem muita memória RAM.

### 2. Otimização do Whisper (Módulo de Legendas)
O Whisper (transcrição de áudio) pode rodar no processador (`cpu`) ou na placa de vídeo (`cuda`).
* Se rodar em **CPU**, o processador irá a 100%, podendo travar o computador momentaneamente.
* Se rodar em **CUDA**, ele usará a placa de vídeo. Como o Ollama também usa a placa de vídeo, rodar os dois ao mesmo tempo pode estourar os 4GB de VRAM.
* **A boa notícia**: O pipeline roda em etapas! O Ollama roda no **Módulo 1** e o Whisper roda no **Módulo 3**. Quando o Whisper iniciar, o Ollama estará ocioso, então a memória será liberada automaticamente.

Para rodar o pipeline com Whisper acelerado por GPU (se você tiver o PyTorch com CUDA instalado):
```powershell
python main.py --tema "SEU_TEMA_AQUI" --device cuda
```
Se der erro de memória na GPU, use o padrão:
```powershell
python main.py --tema "SEU_TEMA_AQUI" --device cpu
```

---

## 📋 Checklist de Execução Segura

Siga esta sequência exata sempre que for criar um novo vídeo:

```mermaid
flowchart TD
    A[1. Certificar que Ollama está ativo na barra de tarefas ou rodar 'ollama serve'] --> B[2. Executar 'ollama pull llama3.2:3b' no terminal se for a 1ª vez]
    B --> C[3. Fechar Chrome/programas pesados para liberar RAM]
    C --> D[4. Navegar até a pasta 'backend']
    D --> E[5. Executar 'python main.py --tema \"Seu Tema\"']
```

### Comandos úteis para o terminal:
```powershell
# 1. Entre na pasta do backend
cd "c:\Users\jpsec\Downloads\Projeto antigravty\criação de conteudo\backend"

# 2. Ative o ambiente virtual (caso use um)
.\venv\Scripts\Activate.ps1

# 3. Execute o gerador
python main.py --tema "O mistério por trás das pirâmides do Egito"
```

---

## 🛠️ Como Validar se o Ollama está Pronto?

Você tem um script de teste na sua pasta do servidor local. Vamos rodá-lo com a codificação correta para verificar o status:

1. Abra o terminal na pasta correspondente.
2. Execute o comando de teste:
   ```powershell
   $env:PYTHONIOENCODING="utf-8"; python "llama3.2 servidor  local/test_ollama.py"
   ```
   *(Este comando define o terminal para UTF-8, evitando erros de exibição com os emojis do script de teste).*

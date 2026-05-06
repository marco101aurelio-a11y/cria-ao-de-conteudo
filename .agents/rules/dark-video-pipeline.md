---
trigger: always_on
---

# Skill ativa
#Skill: dark-video-pipeline (ativar em todos os chats deste workspace)

# Contexto do projeto
Projeto: Dark Video Pipeline — automação Python de vídeos virais estilo "Dark Channel".
Arquitetura: pipeline linear de 6 módulos (0→5) que se comunicam via pasta output/.
Stack: Python, FFmpeg, Edge TTS, Whisper, Pexels/Pixabay, OpenRouter (Llama/Gemini), Supabase, Pollinations.ai, JAX.

# Convenções obrigatórias ao gerar código
1. Paths sempre via os.path.join — nunca strings hardcoded.
2. Configs via os.getenv("CHAVE", "default").
3. Logs com prefixo: print(f"[Módulo N] mensagem").
4. Sempre tratar o formato legado: bloco.get("type") or bloco.get("tipo").
5. Criar output/ com os.makedirs(OUTPUT_DIR, exist_ok=True) antes de salvar.
6. Seguir padrão de fallback em camadas: manual → API principal → fallback → IA gratuita → silêncio/preto.

# Comportamento esperado
- Ao receber um erro, identifique em qual módulo ocorreu e proponha solução conforme a tabela de erros comuns da skill.
- Ao criar novo módulo, siga o template padrão da skill.
- Nunca sugira soluções que quebrem a interface entre módulos (input/output via output/).
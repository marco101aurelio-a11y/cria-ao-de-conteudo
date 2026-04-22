# Fluxograma de Operação (Dark Video Pipeline V2)

> [!NOTE]
> Como o arquivo `.drawio` apresentou problema de leitura no seu VS Code, criei esta versão nativa em **Mermaid**. Você pode visualizá-la perfeitamente abrindo o **Preview** deste arquivo Markdown no VS Code.

```mermaid
graph TD
    %% Estilos Globais
    classDef module0 fill:#f9d0c4,stroke:#b85450,stroke-width:2px,color:#000
    classDef module123 fill:#e2f0d9,stroke:#82b366,stroke-width:2px,color:#000
    classDef module4 fill:#dae8fc,stroke:#6c8ebf,stroke-width:2px,color:#000
    classDef module5 fill:#fff2cc,stroke:#d6b656,stroke-width:2px,color:#000
    classDef database fill:#e1d5e7,stroke:#9673a6,stroke-width:2px,color:#000,shape:cylinder
    classDef startend fill:#d5e8d4,stroke:#82b366,stroke-width:4px,color:#000,shape:circle

    Start((Início)):::startend

    subgraph M0["MÓDULO 0 (Viral Hunter)"]
        Scrape["TikTok Scraper<br>(Playwright / API)"]:::module0
        Whisper0["Whisper STT<br>(Transcreve Áudio)"]:::module0
        DB1[("Supabase DB<br>(viral_references)")]:::database
    end

    subgraph M123["MÓDULO 1, 2 e 3 (Roteiro e Áudio)"]
        LLM["M1: OpenRouter<br>(Hook + Copy)"]:::module123
        JSON_Roteiro>["roteiro.json"]
        TTS["M2: Kokoro/ElevenLabs<br>(Voz Off)"]:::module123
        STT3["M3: Whisper<br>(timestamps.json)"]:::module123
    end

    subgraph M4["MÓDULO 4 (Smart Media Vault)"]
        CheckDB{"Tem no<br>Banco?"}
        Pexels["API Pexels<br>(Baixa Vídeo)"]:::module4
        Cache["Usa Vídeo<br>em Cache"]:::module4
        DB2[("Supabase DB<br>(broll_library)")]:::database
    end

    subgraph M5["MÓDULO 5 (Video Assembler)"]
        Playwright["Playwright HTML/CSS<br>(Grava Legendas Animadas)"]:::module5
        FFmpeg["FFmpeg Mix<br>(Cenas + Legenda Alpha + Áudio)"]:::module5
    end

    End((Vídeo<br>Pronto!)):::startend

    %% Conexões
    Start --> Scrape
    Scrape --> Whisper0
    Whisper0 -- "Salva Dados" --> DB1

    DB1 -- "Injeta Transcrição" --> LLM
    LLM --> JSON_Roteiro
    
    JSON_Roteiro --> TTS
    TTS --> STT3

    JSON_Roteiro -- "Lê Keywords" --> CheckDB
    CheckDB -- "Não" --> Pexels
    CheckDB -- "Sim" --> Cache
    Pexels -- "Salva Novo" -.-> DB2
    DB2 -. "Consulta" .-> CheckDB

    STT3 -- "Passa Timestamps" --> Playwright
    Playwright -- "Vídeo Alpha" --> FFmpeg
    
    Pexels -- "Passa MP4" --> FFmpeg
    Cache -- "Passa MP4" --> FFmpeg
    TTS -- "Passa Áudio" --> FFmpeg

    FFmpeg --> End
```

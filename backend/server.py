vamo"""
Dark Video Pipeline V2 — Servidor Flask Principal
Orquestrador de todos os módulos via endpoints REST.

Como rodar:
    python server.py

Servidor disponível em: http://localhost:5000
"""

import os
import json
from flask import Flask, jsonify, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Garante que a pasta de output existe ao iniciar
os.makedirs("output/clips", exist_ok=True)
os.makedirs("modules/templates", exist_ok=True)


# ─────────────────────────────────────────────────────────────
# ROTA DE STATUS — Verifica se o servidor está vivo
# ─────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def status():
    return jsonify({
        "status": "online",
        "projeto": "Dark Video Pipeline V2",
        "modulos": {
            "module0_hunter":     "Sprint BONUS",
            "script_generator":   "Sprint 2",
            "tts":                "Sprint 3",
            "stt":                "Sprint 4",
            "media_collector":    "Sprint 5",
            "video_assembler":    "Sprint 6",
        }
    })


# ─────────────────────────────────────────────────────────────
# MÓDULO 0 — Viral Hunter (Sprint BÔNUS)
# ─────────────────────────────────────────────────────────────
@app.route("/api/module0/hunt", methods=["POST"])
def module0_hunt():
    try:
        from modules.module0_hunter import run_hunter
        data = request.get_json() or {}
        niche = data.get("niche", "#marketing #negocios")
        result = run_hunter(niche)
        return jsonify({"status": "ok", "result": result})
    except ImportError:
        return jsonify({"status": "not_implemented", "msg": "Módulo 0 ainda não foi criado. Aguarde o Sprint BÔNUS."}), 501
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# MÓDULO 1 — Gerador de Roteiro (Sprint 2)
# ─────────────────────────────────────────────────────────────
@app.route("/api/module1/generate_script", methods=["POST"])
def module1_generate_script():
    try:
        from modules.script_generator import generate_script
        data = request.get_json() or {}
        tema = data.get("tema", "O segredo que os milionários escondem")
        roteiro = generate_script(tema)
        return jsonify({"status": "ok", "roteiro": roteiro})
    except ImportError:
        return jsonify({"status": "not_implemented", "msg": "Módulo 1 ainda não foi criado. Aguarde o Sprint 2."}), 501
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# MÓDULO 2 — Gerador de Áudio / TTS (Sprint 3)
# ─────────────────────────────────────────────────────────────
@app.route("/api/module2/generate_audio", methods=["POST"])
def module2_generate_audio():
    try:
        from modules.tts import generate_audio
        roteiro_path = "output/roteiro.json"
        if not os.path.exists(roteiro_path):
            return jsonify({"status": "error", "msg": "roteiro.json não encontrado. Rode o Módulo 1 primeiro."}), 400
        with open(roteiro_path, "r", encoding="utf-8") as f:
            roteiro = json.load(f)
        result = generate_audio(roteiro)
        return jsonify({"status": "ok", "result": result})
    except ImportError:
        return jsonify({"status": "not_implemented", "msg": "Módulo 2 ainda não foi criado. Aguarde o Sprint 3."}), 501
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# MÓDULO 3 — Timestamps / STT (Sprint 4)
# ─────────────────────────────────────────────────────────────
@app.route("/api/module3/generate_timestamps", methods=["POST"])
def module3_generate_timestamps():
    try:
        from modules.stt import transcribe, build_srt
        audio_path = "output/narration.mp3"
        if not os.path.exists(audio_path):
            return jsonify({"status": "error", "msg": "narration.mp3 não encontrado. Rode o Módulo 2 primeiro."}), 400
        result = transcribe()
        build_srt()
        return jsonify({"status": "ok", "result": "Timestamps e SRT gerados via Patch V1"})
    except ImportError:
        return jsonify({"status": "not_implemented", "msg": "Módulo 3 ainda não foi criado. Aguarde o Sprint 4."}), 501
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# MÓDULO 4 — Coletor de Mídia / B-Roll (Sprint 5)
# ─────────────────────────────────────────────────────────────
@app.route("/api/module4/collect_media", methods=["POST"])
def module4_collect_media():
    try:
        from modules.media_collector import collect_clips, download_background_music
        roteiro_path = "output/roteiro.json"
        if not os.path.exists(roteiro_path):
            return jsonify({"status": "error", "msg": "roteiro.json não encontrado. Rode o Módulo 1 primeiro."}), 400
        result = collect_clips()
        download_background_music()
        with open("output/clip_map.json", "w") as f:
            json.dump(result, f, indent=2)
        return jsonify({"status": "ok", "result": result})
    except ImportError:
        return jsonify({"status": "not_implemented", "msg": "Módulo 4 ainda não foi criado. Aguarde o Sprint 5."}), 501
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# MÓDULO 5 — Montador de Vídeo (Sprint 6)
# ─────────────────────────────────────────────────────────────
@app.route("/api/module5/render_video", methods=["POST"])
def module5_render_video():
    try:
        from modules.video_assembler import assemble

        # Verifica dependências obrigatórias antes de renderizar
        required = ["output/roteiro.json", "output/narration.mp3",
                    "output/timestamps.json", "output/clip_map.json"]
        for path in required:
            if not os.path.exists(path):
                return jsonify({
                    "status": "error",
                    "msg": f"Arquivo '{path}' não encontrado. Execute os módulos anteriores primeiro."
                }), 400

        result = assemble()
        return jsonify({"status": "ok", "result": result})
    except ImportError:
        return jsonify({"status": "not_implemented", "msg": "Módulo 5 ainda não foi criado. Aguarde o Sprint 6."}), 501
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# PIPELINE COMPLETO — Roda todos os módulos em sequência
# ─────────────────────────────────────────────────────────────
@app.route("/api/run_pipeline", methods=["POST"])
def run_pipeline():
    try:
        data = request.get_json() or {}
        tema = data.get("tema", "O segredo que os milionários escondem")
        log = []

        # M1 — Roteiro
        from modules.script_generator import generate_script
        log.append("✅ Módulo 1: Roteiro gerado")
        roteiro = generate_script(tema)

        # M2 — Áudio
        from modules.tts import generate_audio
        generate_audio(roteiro)
        log.append("✅ Módulo 2: Áudio gerado")

        # M3 — Timestamps
        from modules.stt import transcribe, build_srt
        transcribe()
        build_srt()
        log.append("✅ Módulo 3: Timestamps gerados")

        # M4 — B-Roll
        from modules.media_collector import collect_clips, download_background_music
        clip_map = collect_clips()
        download_background_music()
        with open("output/clip_map.json", "w") as f:
            json.dump(clip_map, f, indent=2)
        log.append("✅ Módulo 4: Mídia coletada")

        # M5 — Vídeo Final
        from modules.video_assembler import assemble
        result = assemble()
        log.append("✅ Módulo 5: Vídeo renderizado via Patch V1")

        return jsonify({"status": "ok", "log": log, "output": result})

    except ImportError as e:
        return jsonify({
            "status": "not_implemented",
            "msg": f"Pipeline incompleto: {str(e)}. Complete os Sprints primeiro."
        }), 501
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("Dark Video Pipeline V2")
    print("Servidor rodando em http://localhost:5000")
    print("Pressione Ctrl+C para parar")
    print("=" * 50)
    app.run(debug=True, port=5000)

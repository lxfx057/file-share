from flask import Flask, jsonify, render_template, request
from pathlib import Path
import secrets
import time

ROOT = Path(__file__).resolve().parent.parent
app = Flask(
    __name__,
    template_folder=str(ROOT / "templates"),
    static_folder=str(ROOT / "static"),
    static_url_path="/static",
)

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "service": "File Share 98",
        "backend": "Python / Flask",
        "transfer": "WebRTC DataChannel",
        "signaling": "MQTT over WebSocket",
        "timestamp": int(time.time()),
    })

@app.post("/api/session")
def create_session():
    # PIN generation happens on the Python backend. No file contents or
    # personal data are stored by this endpoint.
    pin = str(secrets.randbelow(90_000_000) + 10_000_000)
    return jsonify({"ok": True, "pin": pin, "expires_in": 600})

@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Endpoint non trovato"}), 404
    return "Pagina non trovata", 404

@app.errorhandler(500)
def server_error(_error):
    return jsonify({"ok": False, "error": "Errore interno del server Python"}), 500

from flask import Flask, jsonify, render_template, request, send_from_directory
from pathlib import Path
import secrets
import time

ROOT = Path(__file__).resolve().parent
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
    pin = str(secrets.randbelow(90_000_000) + 10_000_000)
    return jsonify({"ok": True, "pin": pin, "expires_in": 600})

# Vercel rewrites requests to this function and forwards the original path
# in the __path query parameter.
@app.route("/api/index.py", methods=["GET", "POST"])
def vercel_dispatch():
    path = request.args.get("__path", "").strip("/")
    if path in ("", "index.html"):
        return home()
    if path == "api/health" and request.method == "GET":
        return health()
    if path == "api/session" and request.method == "POST":
        return create_session()
    if path.startswith("static/") and request.method == "GET":
        return send_from_directory(ROOT / "static", path[len("static/"):])
    return jsonify({"ok": False, "error": "Endpoint non trovato"}), 404

@app.errorhandler(404)
def not_found(_error):
    return jsonify({"ok": False, "error": "Endpoint non trovato"}), 404

@app.errorhandler(500)
def server_error(_error):
    return jsonify({"ok": False, "error": "Errore interno del server Python"}), 500

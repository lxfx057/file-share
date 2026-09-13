from flask import Flask, request, jsonify, render_template_string
import json

app = Flask(__name__)

# Memoria temporanea condivisa sul serverless
SHARED_FILES = []

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Win98 Vercel Hub</title>
<style>
    body { background-color: #008080; font-family: 'MS Sans Serif', Tahoma, sans-serif; font-size: 11px; margin: 10px; color: #000; }
    .window { background-color: #c0c0c0; border: 2px solid; border-color: #dfdfdf #404040 #404040 #dfdfdf; width: 100%; max-width: 600px; margin: auto; box-shadow: 4px 4px 10px rgba(0,0,0,0.6); }
    .title-bar { background: linear-gradient(90deg, #000080, #1084d0); color: white; padding: 4px 6px; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }
    .menu-bar { background: #c0c0c0; padding: 2px 4px; border-bottom: 1px solid #808080; display: flex; gap: 15px; }
    .menu-item { padding: 2px 6px; cursor: pointer; }
    .menu-item:hover { background: #000080; color: white; }
    .content { padding: 10px; }
    .form-group { margin-bottom: 10px; }
    label { display: block; margin-bottom: 3px; font-weight: bold; }
    select, input[type="password"] { width: 100%; padding: 4px; background: white; border: 2px inset #808080; font-family: inherit; box-sizing: border-box; }
    .btn { background-color: #c0c0c0; border: 2px solid; border-color: #dfdfdf #404040 #404040 #dfdfdf; padding: 4px 10px; cursor: pointer; font-family: inherit; font-weight: bold; }
    .btn:active { border-color: #404040 #dfdfdf #dfdfdf #404040; padding: 5px 9px 3px 11px; }
    .explorer-view { border: 2px inset #808080; background: white; height: 320px; margin-top: 5px; overflow-y: auto; padding: 5px; }
    .file-table { width: 100%; border-collapse: collapse; text-align: left; }
    .file-table th { background: #c0c0c0; border: 1px solid #808080; padding: 4px; font-size: 11px; }
    .file-table td { padding: 6px; border-bottom: 1px dotted #e0e0e0; font-size: 11px; }
    .file-table tr:hover { background: #000080; color: white; }
    .help-box { background: #ffffe0; border: 1px solid #808080; padding: 8px; margin-bottom: 10px; font-size: 11px; line-height: 1.4; }
    .error-box { background: #800000; color: white; padding: 12px; border: 2px inset #ff0000; font-weight: bold; text-align: center; }
    .status-bar { background: #c0c0c0; border-top: 1px solid #808080; padding: 3px 6px; margin-top: 8px; display: flex; justify-content: space-between; font-size: 10px; }
    .progress-container { background: white; border: 2px inset #808080; height: 16px; width: 100%; margin-top: 6px; position: relative; overflow: hidden; }
    .progress-bar { background: #000080; height: 100%; width: 0%; transition: width 0.1s linear; }
    .progress-text { position: absolute; width: 100%; text-align: center; top: 0; left: 0; font-size: 10px; font-weight: bold; mix-blend-mode: difference; color: #fff; }
    .hidden { display: none; }
</style>
</head>
<body>

<div class="window">
    <div class="title-bar">
        <span id="win-title">📁 Esplora risorse - Root C:\\Hub</span>
        <span>[X]</span>
    </div>
    <div class="menu-bar">
        <div class="menu-item">File</div>
        <div class="menu-item">Modifica</div>
        <div class="menu-item">Visualizza</div>
        <div class="menu-item" onclick="exitApp()">Esci</div>
    </div>
    <div class="content">
        
        <!-- ACCESSO PROTETTO -->
        <div id="step-connect">
            <div class="help-box">
                <b>🔒 ACCESSO VERCEL PYTHON:</b><br>
                Inserisci la password <b>admin2027</b> e seleziona il tuo ruolo. I file caricati confluiranno nella cartella principale.
            </div>

            <div class="form-group">
                <label>1. Ruolo Dispositivo:</label>
                <select id="hub-role">
                    <option value="" disabled selected>-- Seleziona ruolo --</option>
                    <option value="sender">Inviante (Carica file)</option>
                    <option value="receiver">Ricevente (Visualizza, Salva ed Elimina)</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>2. Parola d'ordine:</label>
                <input type="password" id="hub-password" placeholder="admin2027">
            </div>
            
            <button class="btn" style="width:100%; margin-top:5px;" onclick="authenticateHub()">Connetti</button>
        </div>

        <!-- ERRORE 604 -->
        <div id="step-error" class="hidden">
            <div class="error-box">
                ERROR 604<br>
                Accesso Negato / Password Errata.<br><br>
                <span style="font-size:11px; font-weight:normal;">La parola d'ordine inserita non è corretta. Connessione rifiutata.</span>
            </div>
            <button class="btn" style="margin-top: 15px; width:100%;" onclick="exitApp()">Riprova / Esci</button>
        </div>

        <!-- DASHBOARD INVIANTE -->
        <div id="dashboard-sender" class="hidden">
            <div class="help-box" style="background:#e8f4f8;">
                <b>📤 CARICAMENTO ROOT:</b> Seleziona i file dal dispositivo.
            </div>
            <div class="form-group">
                <label>Seleziona file da inviare:</label>
                <input type="file" id="sender-file-input" multiple onchange="uploadFilesToCloud(event)">
            </div>
            <div class="progress-container">
                <div class="progress-bar" id="sender-progress"></div>
                <div class="progress-text" id="sender-progress-text">Pronto per l'invio</div>
            </div>
            <div style="font-size:11px; margin-top:8px; font-weight:bold; color:#000080;" id="sender-time-info"></div>
            <button class="btn" style="width:100%; margin-top:15px; background:#d0d0d0;" onclick="exitApp()">Esci</button>
        </div>

        <!-- DASHBOARD RICEVENTE -->
        <div id="dashboard-receiver" class="hidden">
            <div style="font-size: 11px; margin-bottom: 5px; font-weight: bold;">Indirizzo: <span style="background:white; padding:2px 8px; border:1px inset #808080; display:inline-block; width:75%;">C:\\Hub\\Root</span></div>
            
            <div class="explorer-view">
                <table class="file-table">
                    <thead>
                        <tr>
                            <th>Nome File</th>
                            <th>Dimensione</th>
                            <th>Azioni (Salva / Elimina)</th>
                        </tr>
                    </thead>
                    <tbody id="file-table-body">
                        <tr><td colspan="3" style="text-align:center; color:gray; padding-top:40px;">Caricamento file in corso...</td></tr>
                    </tbody>
                </table>
            </div>

            <div class="progress-container" style="margin-top: 6px;">
                <div class="progress-bar" id="receiver-progress" style="width: 100%; background: #008000;"></div>
                <div class="progress-text" id="receiver-progress-text">Sincronizzazione Attiva</div>
            </div>

            <div class="status-bar">
                <span id="status-items-count">0 oggetto(i)</span>
                <span><button class="btn" style="padding:1px 6px; background:#d0d0d0;" onclick="exitApp()">Esci</button></span>
            </div>
        </div>

    </div>
</div>

<script>
    function exitApp() {
        location.reload();
    }

    function authenticateHub() {
        const role = document.getElementById('hub-role').value;
        const pass = document.getElementById('hub-password').value.trim();

        if (!role || pass !== "admin2027") {
            document.getElementById('step-connect').classList.add('hidden');
            document.getElementById('step-error').classList.remove('hidden');
            document.getElementById('win-title').innerText = "❌ Errore 604";
            return;
        }

        document.getElementById('step-connect').classList.add('hidden');
        if (role === 'sender') {
            document.getElementById('dashboard-sender').classList.remove('hidden');
            document.getElementById('win-title').innerText = "📁 Esplora risorse - [INVIANTE ROOT]";
        } else {
            document.getElementById('dashboard-receiver').classList.remove('hidden');
            document.getElementById('win-title').innerText = "📁 Esplora risorse - [RICEVENTE ROOT]";
            fetchFiles();
            setInterval(fetchFiles, 2000); // Aggiornamento automatico ogni 2 secondi
        }
    }

    function uploadFilesToCloud(event) {
        const files = event.target.files;
        if (!files.length) return;

        let total = files.length;
        let processed = 0;
        let start = Date.now();

        const bar = document.getElementById('sender-progress');
        const text = document.getElementById('sender-progress-text');
        const info = document.getElementById('sender-time-info');

        for (let i = 0; i < files.length; i++) {
            let f = files[i];
            let reader = new FileReader();

            reader.onprogress = (e) => {
                if (e.lengthComputable) {
                    let p = Math.round((e.loaded / e.total) * 100);
                    bar.style.width = p + '%';
                    text.innerText = `Caricamento ${f.name}: ${p}%`;
                }
            };

            reader.onload = async (e) => {
                let filePayload = {
                    name: f.name,
                    size: f.size,
                    data: e.target.result
                };

                await fetch('/api/index', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'upload', file: filePayload })
                });

                processed++;
                let elapsed = (Date.now() - start) / 1000;
                let rem = Math.max(0, Math.ceil((elapsed / processed) * total - elapsed));
                info.innerText = `⏱️ Trascorso: ${elapsed.toFixed(1)}s — Rimasto: ${rem}s`;

                if (processed === total) {
                    bar.style.width = '100%';
                    text.innerText = 'Caricamento completato!';
                }
            };

            reader.readAsDataURL(f);
        }
    }

    async function fetchFiles() {
        try {
            let res = await fetch('/api/index');
            let files = await res.json();
            renderFiles(files);
        } catch(err) {
            console.error(err);
        }
    }

    function renderFiles(files) {
        let tbody = document.getElementById('file-table-body');
        document.getElementById('status-items-count').innerText = `${files.length} oggetto(i)`;

        tbody.innerHTML = '';
        if (files.length === 0) {
            tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; color:gray; padding-top:40px;">Nessun file presente nella root.</td></tr>`;
            return;
        }

        files.forEach((file, idx) => {
            let size = (file.size > 1024*1024) ? (file.size / (1024*1024)).toFixed(2) + ' MB' : (file.size / 1024).toFixed(1) + ' KB';
            
            let act = `
                <button class="btn" style="padding:2px 8px; background:#000080; color:white;" onclick="saveFile(${idx}, '${encodeURIComponent(file.name)}', '${file.data}')">Salva</button>
                <button class="btn" style="padding:2px 8px; background:#ff8080;" onclick="deleteFile(${idx})">Elimina</button>
            `;

            tbody.innerHTML += `
                <tr>
                    <td>📄 ${file.name}</td>
                    <td>${size}</td>
                    <td>${act}</td>
                </tr>
            `;
        });
    }

    function saveFile(idx, name, data) {
        let decodedName = decodeURIComponent(name);
        document.getElementById('receiver-progress-text').innerText = `Salvato nei Download: ${decodedName}`;
        
        let a = document.createElement('a');
        a.href = data;
        a.download = decodedName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    async function deleteFile(idx) {
        await fetch('/api/index', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'delete', index: idx })
        });
        fetchFiles();
    }
</script>

</body>
</html>
"""

@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def catch_all(path):
    global SHARED_FILES
    if request.method == "POST":
        data = request.get_json()
        if data and data.get("action") == "upload":
            SHARED_FILES.append(data.get("file"))
            return jsonify({"status": "success"})
        elif data and data.get("action") == "delete":
            idx = data.get("index")
            if 0 <= idx < len(SHARED_FILES):
                SHARED_FILES.pop(idx)
            return jsonify({"status": "success"})
    
    return render_template_string(HTML_TEMPLATE)

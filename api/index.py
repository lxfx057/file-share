import base64, os, re, uuid, hmac
from urllib.parse import quote
import boto3
from botocore.config import Config
from flask import Flask, jsonify, render_template_string, request, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=True, MAX_CONTENT_LENGTH=2*1024*1024)
MAX_FILE_SIZE = 3*1000*1000*1000
PART_SIZE = 64*1024*1024

def storage_configured():
    return all(os.environ.get(k) for k in ("R2_ENDPOINT","R2_BUCKET","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY"))

def s3():
    return boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto", config=Config(signature_version="s3v4", s3={"addressing_style":"path"}))

def err(message, code=400):
    return jsonify({"error":message}), code

def protect():
    if not session.get("authenticated"): return err("Sessione scaduta. Accedi di nuovo.",401)
    if not storage_configured(): return err("Storage R2 non configurato su Vercel.",503)
    return None

def safe_name(value):
    name=os.path.basename(str(value or "file").replace("\\","/"))
    name=re.sub(r"[\x00-\x1f\x7f]","_",name).strip(" .")
    return (name or "file")[:180]

@app.get("/")
def home(): return render_template_string(HTML)

@app.get("/api/status")
def status():
    return jsonify({"authenticated":bool(session.get("authenticated")),"storage_configured":storage_configured(),"max_file_size":MAX_FILE_SIZE})

@app.post("/api/login")
def login():
    data=request.get_json(silent=True) or {}; password=os.environ.get("HUB_PASSWORD")
    if not password or not app.secret_key: return err("Configura HUB_PASSWORD e FLASK_SECRET_KEY su Vercel.",503)
    if not hmac.compare_digest(str(data.get("password","")),password): return err("Password non corretta.",401)
    session.clear(); session["authenticated"]=True
    return jsonify({"ok":True})

@app.post("/api/logout")
def logout(): session.clear(); return jsonify({"ok":True})

@app.before_request
def guard():
    if request.path.startswith("/api/") and request.path not in ("/api/login","/api/status","/api/logout"):
        return protect()

@app.get("/api/files")
def files():
    client=s3(); out=[]
    page=client.get_paginator("list_objects_v2")
    for batch in page.paginate(Bucket=os.environ["R2_BUCKET"],Prefix="uploads/"):
        for obj in batch.get("Contents",[]):
            key=obj["Key"]
            try:
                meta=client.head_object(Bucket=os.environ["R2_BUCKET"],Key=key).get("Metadata",{})
                encoded=meta.get("original-name","")
                name=base64.urlsafe_b64decode(encoded+"="*(-len(encoded)%4)).decode("utf-8") if encoded else key.rsplit("/",1)[-1]
                out.append({"id":key,"name":name,"size":obj["Size"],"modified":obj["LastModified"].isoformat()})
            except Exception: continue
    out.sort(key=lambda x:x["modified"],reverse=True)
    return jsonify(out)

@app.post("/api/multipart/create")
def multipart_create():
    data=request.get_json(silent=True) or {}; name=safe_name(data.get("name")); size=data.get("size")
    if not isinstance(size,int) or size<1 or size>MAX_FILE_SIZE: return err("Il file deve essere compreso tra 1 byte e 3 GB.")
    count=(size+PART_SIZE-1)//PART_SIZE
    key="uploads/"+str(uuid.uuid4())+"/"+name
    encoded=base64.urlsafe_b64encode(name.encode()).decode().rstrip("=")
    client=s3(); created=client.create_multipart_upload(Bucket=os.environ["R2_BUCKET"],Key=key,ContentType=str(data.get("content_type") or "application/octet-stream")[:150],Metadata={"original-name":encoded})
    upload_id=created["UploadId"]; urls=[]
    try:
        for number in range(1,count+1):
            urls.append(client.generate_presigned_url("upload_part",Params={"Bucket":os.environ["R2_BUCKET"],"Key":key,"UploadId":upload_id,"PartNumber":number},ExpiresIn=3600))
    except Exception:
        client.abort_multipart_upload(Bucket=os.environ["R2_BUCKET"],Key=key,UploadId=upload_id); raise
    return jsonify({"key":key,"upload_id":upload_id,"part_size":PART_SIZE,"parts":urls})

@app.post("/api/multipart/complete")
def multipart_complete():
    data=request.get_json(silent=True) or {}; key=data.get("key"); upload_id=data.get("upload_id"); parts=data.get("parts")
    if not isinstance(key,str) or not key.startswith("uploads/") or not isinstance(upload_id,str) or not isinstance(parts,list): return err("Richiesta di completamento non valida.")
    normalized=[]
    for p in parts:
        if not isinstance(p,dict) or not isinstance(p.get("ETag"),str) or not isinstance(p.get("PartNumber"),int): return err("Elenco blocchi non valido.")
        normalized.append({"ETag":p["ETag"],"PartNumber":p["PartNumber"]})
    try:
        normalized.sort(key=lambda p:p["PartNumber"])
        result=s3().complete_multipart_upload(Bucket=os.environ["R2_BUCKET"],Key=key,UploadId=upload_id,MultipartUpload={"Parts":normalized})
        return jsonify({"ok":True,"key":key,"etag":result.get("ETag")})
    except Exception as exc: return err("Completamento fallito: "+str(exc),500)

@app.post("/api/multipart/abort")
def multipart_abort():
    d=request.get_json(silent=True) or {}; key=d.get("key"); uid=d.get("upload_id")
    if not isinstance(key,str) or not key.startswith("uploads/") or not isinstance(uid,str): return err("Richiesta non valida.")
    s3().abort_multipart_upload(Bucket=os.environ["R2_BUCKET"],Key=key,UploadId=uid)
    return jsonify({"ok":True})

@app.post("/api/download")
def download():
    key=(request.get_json(silent=True) or {}).get("key")
    if not isinstance(key,str) or not key.startswith("uploads/"): return err("File non valido.")
    client=s3(); head=client.head_object(Bucket=os.environ["R2_BUCKET"],Key=key); encoded=head.get("Metadata",{}).get("original-name","")
    name=base64.urlsafe_b64decode(encoded+"="*(-len(encoded)%4)).decode("utf-8") if encoded else key.rsplit("/",1)[-1]
    url=client.generate_presigned_url("get_object",Params={"Bucket":os.environ["R2_BUCKET"],"Key":key,"ResponseContentDisposition":"attachment; filename*=UTF-8''"+quote(name)},ExpiresIn=900)
    return jsonify({"url":url})

@app.post("/api/delete")
def delete_file():
    key=(request.get_json(silent=True) or {}).get("key")
    if not isinstance(key,str) or not key.startswith("uploads/"): return err("File non valido.")
    s3().delete_object(Bucket=os.environ["R2_BUCKET"],Key=key)
    return jsonify({"ok":True})

HTML = "<!doctype html><html lang=\"it\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\"><meta name=\"theme-color\" content=\"#008080\"><title>File Share 98</title>\n<style>\n*{box-sizing:border-box}body{margin:0;padding:14px;background:#008080;font:13px Tahoma,Arial;color:#111;min-height:100vh}.window{max-width:850px;margin:12px auto;background:#c0c0c0;border:2px solid;border-color:#fff #404040 #404040 #fff;box-shadow:2px 2px #111}.titlebar{height:30px;margin:3px 3px 0;padding:5px 8px;background:linear-gradient(90deg,#000080,#1084d0);color:#fff;font-weight:bold;display:flex;justify-content:space-between}.sysbtn{display:inline-block;width:20px;height:18px;background:#c0c0c0;color:#111;border:2px solid;border-color:#fff #404040 #404040 #fff;text-align:center}.menubar{display:flex;gap:18px;padding:6px 10px;border-bottom:1px solid #888}.content{padding:14px}.panel{border:2px groove #fff;padding:12px;margin-bottom:12px}h2{font-size:14px;margin:0 0 10px}.muted{color:#444;font-size:12px;line-height:1.5}.btn{min-height:38px;padding:7px 13px;border:2px solid;border-color:#fff #404040 #404040 #fff;background:#c0c0c0;font:bold 13px Tahoma;cursor:pointer}.btn.primary{background:#000080;color:#fff}.btn.danger{background:#e0b0b0}input[type=password]{width:100%;min-height:40px;padding:8px;border:2px inset #888;font:16px Tahoma}.drop{border:2px dashed #777;background:#eee;padding:22px 12px;text-align:center;margin:10px 0}.drop strong{display:block;margin-bottom:8px;font-size:15px}.filepick{display:inline-block;position:relative;overflow:hidden}.filepick input{position:absolute;inset:0;opacity:0;width:100%;height:100%}.toolbar{display:flex;gap:8px;flex-wrap:wrap}.progress{height:20px;background:#fff;border:2px inset #888;position:relative;margin:8px 0}.progress>div{height:100%;width:0;background:repeating-linear-gradient(90deg,#000080 0 12px,#2040a0 12px 16px)}.progress span{position:absolute;inset:2px;text-align:center;font-size:11px;font-weight:bold}.status{padding:8px;background:#ddd;border:1px inset #888;min-height:34px;font-size:12px}.tablewrap{overflow-x:auto;background:#fff;border:2px inset #888}table{width:100%;border-collapse:collapse;min-width:480px;text-align:left}th{background:#c0c0c0;border:1px solid #888;padding:8px}td{padding:8px;border-bottom:1px dotted #ccc;overflow-wrap:anywhere}.actions{display:flex;gap:6px;flex-wrap:wrap}.actions .btn{min-height:32px;padding:4px 8px;font-size:12px}.hidden{display:none!important}.error{color:#900;font-weight:bold}.footer{display:flex;justify-content:space-between;padding:6px;border-top:1px solid #888;font-size:11px}@media(max-width:560px){body{padding:4px}.window{margin:2px auto}.content{padding:9px}.panel{padding:9px}.drop{padding:18px 8px}}\n</style></head><body><div class=\"window\"><div class=\"titlebar\"><span>🖥️ FILE SHARE 98 - Esplora risorse</span><span><i class=\"sysbtn\">_</i><i class=\"sysbtn\">□</i><i class=\"sysbtn\">X</i></span></div><div class=\"menubar\"><span>File</span><span>Modifica</span><span>Visualizza</span><span>?</span></div><main class=\"content\">\n<section id=\"login\" class=\"panel hidden\"><h2>🔐 Connessione al computer remoto</h2><p class=\"muted\">Inserisci la password per accedere al tuo archivio privato.</p><input id=\"password\" type=\"password\" autocomplete=\"current-password\" placeholder=\"Password di accesso\"><button class=\"btn primary\" style=\"width:100%;margin-top:10px\" id=\"loginBtn\">Connetti</button><p id=\"loginError\" class=\"error\"></p></section>\n<section id=\"setup\" class=\"panel hidden\"><h2>⚙️ Storage non configurato</h2><p class=\"muted\">Aggiungi le variabili Cloudflare R2 e le credenziali di sessione su Vercel. Consulta README.md.</p></section>\n<div id=\"app\" class=\"hidden\"><section class=\"panel\"><h2>📤 Trasferimento file</h2><p class=\"muted\">Invia da Android o iPhone. Foto, video e documenti fino a <b>3 GB per singolo file</b>. Upload a blocchi direttamente verso lo storage.</p><div class=\"drop\"><strong>📁 Seleziona foto o file da inviare</strong><span class=\"muted\">Apri Foto, File o la memoria del dispositivo</span><div style=\"margin-top:12px\"><label class=\"btn primary filepick\">Scegli file<input id=\"picker\" type=\"file\" multiple></label></div></div><div id=\"queue\" class=\"muted\">Nessun trasferimento in corso.</div><div class=\"progress\"><div id=\"bar\"></div><span id=\"progressText\">Pronto</span></div><div id=\"transferStatus\" class=\"status\" aria-live=\"polite\">In attesa di file.</div><div class=\"toolbar\" style=\"margin-top:10px\"><button id=\"cancelBtn\" class=\"btn danger\" disabled>Annulla trasferimento</button><button id=\"refreshBtn\" class=\"btn\">Aggiorna archivio</button></div></section>\n<section class=\"panel\"><h2>📂 Archivio condiviso</h2><p class=\"muted\">I file caricati sono disponibili da tutti i dispositivi autorizzati.</p><div class=\"tablewrap\"><table><thead><tr><th>Nome file</th><th>Dimensione</th><th>Data</th><th>Azioni</th></tr></thead><tbody id=\"files\"><tr><td colspan=\"4\">Caricamento archivio...</td></tr></tbody></table></div></section></div></main><div class=\"footer\"><span id=\"footerLeft\">FILE SHARE 98</span><span>Android ⇄ iOS · Max 3 GB</span></div></div>\n<script>\nconst MAX=3*1024*1024*1024;let active=false,cancelRequested=false,currentUpload=null,currentInit=null;const $=id=>document.getElementById(id);\nasync function api(url,body){const r=await fetch(url,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});let d={};try{d=await r.json()}catch(e){}if(!r.ok)throw new Error(d.error||'Errore HTTP '+r.status);return d}\nfunction fmt(n){if(n>=1073741824)return(n/1073741824).toFixed(2)+' GB';if(n>=1048576)return(n/1048576).toFixed(1)+' MB';if(n>=1024)return(n/1024).toFixed(1)+' KB';return n+' B'}\nfunction setProgress(p,label){$('bar').style.width=Math.max(0,Math.min(100,p))+'%';$('progressText').textContent=label||Math.round(p)+'%'}\nfunction status(s){$('transferStatus').textContent=s}\nasync function boot(){try{const s=await api('/api/status');if(!s.storage_configured){$('setup').classList.remove('hidden');return}if(s.authenticated){$('app').classList.remove('hidden');loadFiles()}else $('login').classList.remove('hidden')}catch(e){$('setup').classList.remove('hidden')}}\n$('loginBtn').onclick=async()=>{try{await api('/api/login',{password:$('password').value});$('login').classList.add('hidden');$('app').classList.remove('hidden');loadFiles()}catch(e){$('loginError').textContent=e.message}};\n$('password').addEventListener('keydown',e=>{if(e.key==='Enter')$('loginBtn').click()});$('refreshBtn').onclick=loadFiles;\nasync function loadFiles(){try{const list=await api('/api/files'),tbody=$('files');tbody.replaceChildren();if(!list.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=4;td.textContent='Archivio vuoto. Invia il primo file!';tr.append(td);tbody.append(tr)}for(const f of list){const tr=document.createElement('tr');[f.name,fmt(f.size),new Date(f.modified).toLocaleString()].forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.append(td)});const td=document.createElement('td'),actions=document.createElement('div');actions.className='actions';const dl=document.createElement('button');dl.className='btn';dl.textContent='Scarica';dl.onclick=()=>downloadFile(f.id);const del=document.createElement('button');del.className='btn danger';del.textContent='Elimina';del.onclick=()=>deleteFile(f.id,f.name);actions.append(dl,del);td.append(actions);tr.append(td);tbody.append(tr)}$('footerLeft').textContent=list.length+' file nell’archivio'}catch(e){status(e.message)}}\nasync function downloadFile(key){try{const d=await api('/api/download',{key});location.href=d.url}catch(e){status(e.message)}}\nasync function deleteFile(key,name){if(!confirm('Eliminare \"'+name+'\"?'))return;try{await api('/api/delete',{key});loadFiles()}catch(e){status(e.message)}}\nfunction putPart(url,blob,onProgress){return new Promise((resolve,reject)=>{const x=new XMLHttpRequest();x.open('PUT',url);x.upload.onprogress=e=>{if(e.lengthComputable)onProgress(e.loaded)};x.onload=()=>{if(x.status>=200&&x.status<300){const etag=x.getResponseHeader('ETag');if(!etag)return reject(new Error('ETag non disponibile: verifica CORS di R2.'));resolve(etag)}else reject(new Error('Upload blocco fallito: HTTP '+x.status))};x.onerror=()=>reject(new Error('Connessione interrotta.'));x.onabort=()=>reject(new Error('Trasferimento annullato.'));x.send(blob);currentUpload=x})}\nasync function uploadOne(file,index,total){if(file.size>MAX)throw new Error(file.name+' supera il limite di 3 GB.');if(!file.size)throw new Error(file.name+' è vuoto.');const init=await api('/api/multipart/create',{name:file.name,size:file.size,content_type:file.type||'application/octet-stream'});currentInit=init;const parts=[],count=init.parts.length;let uploaded=0;for(let i=0;i<count;i++){if(cancelRequested)throw new Error('Trasferimento annullato.');const start=i*init.part_size,blob=file.slice(start,Math.min(file.size,start+init.part_size));const etag=await putPart(init.parts[i],blob,loaded=>{const pct=((index+(uploaded+loaded)/file.size)/total)*100;setProgress(pct,Math.floor(pct)+'%')});parts.push({PartNumber:i+1,ETag:etag});uploaded+=blob.size;setProgress(((index+1)/total)*100,Math.round(((index+1)/total)*100)+'%')}if(cancelRequested)throw new Error('Trasferimento annullato.');await api('/api/multipart/complete',{key:init.key,upload_id:init.upload_id,parts});currentInit=null}\n$('picker').onchange=async e=>{const selected=Array.from(e.target.files||[]);e.target.value='';if(!selected.length||active)return;active=true;cancelRequested=false;$('cancelBtn').disabled=false;$('picker').disabled=true;$('queue').textContent=selected.map(f=>f.name+' ('+fmt(f.size)+')').join(' · ');try{for(let i=0;i<selected.length;i++){if(cancelRequested)break;status('Invio '+(i+1)+'/'+selected.length+': '+selected[i].name);await uploadOne(selected[i],i,selected.length);status('Completato: '+selected[i].name)}if(!cancelRequested){setProgress(100,'Completato');status('Tutti i file sono stati trasferiti.');await loadFiles()}}catch(e){status(e.message);setProgress(0,'Interrotto')}finally{active=false;currentUpload=null;currentInit=null;$('cancelBtn').disabled=true;$('picker').disabled=false}};\n$('cancelBtn').onclick=async()=>{cancelRequested=true;if(currentUpload)currentUpload.abort();if(currentInit){try{await api('/api/multipart/abort',{key:currentInit.key,upload_id:currentInit.upload_id})}catch(e){}}status('Annullamento in corso…')};boot();\n</script></body></html>"

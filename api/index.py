from flask import Flask, Response

app = Flask(__name__)

HTML = r"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#008080"><script src="https://unpkg.com/mqtt/dist/mqtt.min.js" onerror="this.onerror=null;this.src='https://cdn.jsdelivr.net/npm/mqtt/dist/mqtt.min.js'"></script><title>File Share 98 - PIN</title>
<style>
*{box-sizing:border-box}body{margin:0;padding:12px;background:#008080;font:14px Tahoma,Arial;color:#111;min-height:100vh}.window{max-width:760px;margin:18px auto;background:#c0c0c0;border:2px solid;border-color:#fff #404040 #404040 #fff;box-shadow:2px 2px #111}.title{margin:3px 3px 0;padding:8px;background:linear-gradient(90deg,#000080,#1084d0);color:white;font-weight:bold}.content{padding:14px}.panel{border:2px groove white;padding:12px;margin:0 0 12px}h2{font-size:15px;margin:0 0 10px}.muted{font-size:12px;color:#444;line-height:1.5}.btn{padding:10px 14px;min-height:42px;border:2px solid;border-color:white #404040 #404040 white;background:#c0c0c0;font:bold 14px Tahoma;cursor:pointer}.primary{background:#000080;color:white}.danger{background:#e4baba}.row{display:flex;gap:8px;flex-wrap:wrap}.row>*{flex:1}.pin{font:bold 34px "Courier New";letter-spacing:7px;text-align:center;background:#fff;border:2px inset #888;padding:12px;margin:12px 0}.field{width:100%;padding:12px;font:22px "Courier New";letter-spacing:5px;text-align:center;border:2px inset #888}.status{background:#eee;border:2px inset #888;padding:10px;min-height:42px;margin-top:10px;font-size:12px}.progress{height:20px;background:white;border:2px inset #888;margin:8px 0}.progress div{height:100%;width:0;background:#000080}.hidden{display:none!important}.file{display:block;margin:12px 0;max-width:100%}@media(max-width:520px){body{padding:4px}.window{margin:3px auto}.content{padding:9px}.panel{padding:9px}.pin{font-size:28px;letter-spacing:4px}}
</style></head><body><div class="window"><div class="title">🖥 FILE SHARE 98 — Trasferimento diretto</div><main class="content">
<section class="panel"><h2>🔒 Nessun archivio cloud</h2><p class="muted">Inserisci lo stesso PIN su entrambi i telefoni. I file viaggiano direttamente tra i dispositivi; il servizio di collegamento pubblico riceve solo i dati tecnici WebRTC. Nessuna registrazione.</p></section>
<section class="panel"><h2>📤 Invia da questo dispositivo</h2><button id="create" class="btn primary">Crea PIN temporaneo</button><div id="pinBox" class="hidden"><div class="pin" id="pin">--------</div><p class="muted">Inserisci questo PIN sul secondo dispositivo.</p><label class="btn file">Scegli file<input id="files" type="file" multiple hidden disabled></label></div></section>
<section class="panel"><h2>📥 Ricevi su questo dispositivo</h2><input id="joinPin" class="field" inputmode="numeric" maxlength="8" placeholder="PIN 8 CIFRE"><button id="join" class="btn primary" style="width:100%;margin-top:8px">Collega e ricevi</button><div id="received"></div></section>
<section class="panel"><h2>📊 Trasferimento</h2><div class="progress"><div id="bar"></div></div><div id="status" class="status" aria-live="polite">In attesa di connessione.</div><button id="close" class="btn danger" style="margin-top:8px" disabled>Chiudi sessione</button></section>
<p class="muted">File Share 98 · Android ⇄ iPhone · Fino a 3 GB per file (limite applicativo; la memoria del browser e la rete possono limitare i trasferimenti molto grandi).</p>
</main></div>
<script>
const MQTT_URL = 'wss://broker.emqx.io:8084/mqtt';
const MAX_FILE = 3000000000, CHUNK = 48 * 1024;
let pc=null, channel=null, roomPin=null, role=null, mqtt=null, receiveParts=[], receiveMeta=null, receivedBytes=0, busy=false, nativeFile=false;
const $=id=>document.getElementById(id);
function say(s){$('status').textContent=s}
function progress(p){$('bar').style.width=Math.max(0,Math.min(100,p))+'%'}
function topic(pin,kind='signal'){return 'fileshare98/v1/'+pin+'/'+kind}
function makeMqtt(){return new Promise((resolve,reject)=>{if(!window.mqtt){reject(Error('Libreria di collegamento non disponibile. Ricarica la pagina.'));return}mqtt=window.mqtt.connect(MQTT_URL,{clientId:'fs98_'+Math.random().toString(16).slice(2),clean:true,protocolVersion:4,connectTimeout:20000,keepalive:30,reconnectPeriod:0});const timer=setTimeout(()=>reject(Error('Servizio PIN non raggiungibile. Riprova.')),13000);mqtt.once('connect',()=>{clearTimeout(timer);resolve()});mqtt.once('error',e=>{clearTimeout(timer);reject(Error('Connessione PIN non riuscita: '+e.message))})})}
function publishSignal(kind,sdp){mqtt.publish(topic(roomPin,kind),JSON.stringify({kind,sdp,at:Date.now()}),{qos:1,retain:true})}
function waitIce(){return new Promise(resolve=>{if(pc.iceGatheringState==='complete')return resolve();const done=()=>{if(pc.iceGatheringState==='complete'){pc.removeEventListener('icegatheringstatechange',done);resolve()}};pc.addEventListener('icegatheringstatechange',done);setTimeout(resolve,25000)})}
function setupPeer(sender){pc=new RTCPeerConnection({iceServers:[{urls:'stun:stun.l.google.com:19302'}]});pc.onconnectionstatechange=()=>{say('Connessione: '+pc.connectionState);if(pc.connectionState==='failed')say('Connessione diretta non riuscita su questa rete. Prova con entrambi i telefoni sulla stessa Wi-Fi.')};if(sender){channel=pc.createDataChannel('files',{ordered:true});wireChannel()}else pc.ondatachannel=e=>{channel=e.channel;wireChannel()}}
function wireChannel(){channel.binaryType='arraybuffer';channel.onopen=()=>{say('Dispositivi collegati. Pronto al trasferimento.');$('close').disabled=false;if(role==='receiver')say('Collegato! Attendo i file…');else $('files').disabled=false};channel.onmessage=onData;channel.onerror=()=>say('Errore nel canale di trasferimento.')}
async function createRoom(){roomPin=String(10000000+(crypto.getRandomValues(new Uint32Array(1))[0]%90000000));role='sender';$('pin').textContent=roomPin;$('pinBox').classList.remove('hidden');say('Connessione al servizio PIN…');await makeMqtt();await new Promise((resolve,reject)=>mqtt.subscribe(topic(roomPin,'answer'),{qos:1},e=>e?reject(e):resolve()));setupPeer(true);const offer=await pc.createOffer();await pc.setLocalDescription(offer);await waitIce();mqtt.on('message',async(t,payload)=>{if(t!==topic(roomPin,'answer')||role!=='sender')return;try{const m=JSON.parse(payload.toString());if(m.kind==='answer'&&Date.now()-m.at<600000&&pc.signalingState==='have-local-offer'){await pc.setRemoteDescription({type:'answer',sdp:m.sdp});say('Risposta ricevuta. Connessione in corso…')}}catch(e){say('Errore di collegamento: '+e.message)}});publishSignal('offer',pc.localDescription.sdp);say('PIN creato. In attesa del dispositivo ricevente…');$('files').disabled=true;$('close').disabled=false}
async function joinRoom(){const pin=$('joinPin').value.replace(/\D/g,'');if(!/^\d{8}$/.test(pin))throw Error('Inserisci un PIN di 8 cifre.');roomPin=pin;role='receiver';say('Connessione al servizio PIN…');await makeMqtt();await new Promise((resolve,reject)=>{let done=false;const timer=setTimeout(()=>{if(!done){done=true;reject(Error('PIN non trovato o scaduto.'))}},30000);mqtt.subscribe(topic(pin,'offer'),{qos:1},e=>{if(e&&!done){done=true;clearTimeout(timer);reject(e)}});mqtt.on('message',async(t,payload)=>{if(t!==topic(pin,'offer')||done)return;try{const m=JSON.parse(payload.toString());if(m.kind!=='offer'||!m.sdp||Date.now()-m.at>600000)return;done=true;clearTimeout(timer);setupPeer(false);await pc.setRemoteDescription({type:'offer',sdp:m.sdp});const answer=await pc.createAnswer();await pc.setLocalDescription(answer);await waitIce();publishSignal('answer',pc.localDescription.sdp);$('close').disabled=false;say('PIN riconosciuto. Collegamento in corso…');resolve()}catch(err){done=true;clearTimeout(timer);reject(err)}})})}
function waitDrain(){if(channel.bufferedAmount<1024*1024)return Promise.resolve();return new Promise(resolve=>{channel.bufferedAmountLowThreshold=256*1024;channel.onbufferedamountlow=()=>{channel.onbufferedamountlow=null;resolve()}})}
async function sendFiles(list){if(!channel||channel.readyState!=='open')throw Error('Prima collega il secondo dispositivo.');if(busy)return;busy=true;$('files').disabled=true;try{for(const file of list){if(file.size>MAX_FILE)throw Error(file.name+' supera 3 GB.');channel.send(JSON.stringify({kind:'meta',name:file.name,size:file.size,type:file.type||'application/octet-stream'}));let sent=0;while(sent<file.size){await waitDrain();const part=file.slice(sent,Math.min(sent+CHUNK,file.size));channel.send(await part.arrayBuffer());sent+=part.size;progress(sent/file.size*100);say('Invio '+file.name+' — '+Math.round(sent/file.size*100)+'%')}channel.send(JSON.stringify({kind:'end'}));say('Inviato: '+file.name)}say('Trasferimento completato.')}finally{busy=false;$('files').disabled=false}}
function toBase64(buffer){let binary='';const bytes=new Uint8Array(buffer);for(let i=0;i<bytes.length;i++)binary+=String.fromCharCode(bytes[i]);return btoa(binary)}
function onData(e){
 if(typeof e.data==='string'){
  let m;try{m=JSON.parse(e.data)}catch{return}
  if(m.kind==='meta'){
   if(receiveMeta){say('Trasferimento precedente incompleto: sessione interrotta.');receiveParts=[];receiveMeta=null;receivedBytes=0}
   if(typeof m.name!=='string'||!Number.isSafeInteger(m.size)||m.size<0||m.size>MAX_FILE){
    say('File rifiutato: nome o dimensione non validi.');return
   }
   const safeName=Array.from(m.name).filter(ch=>ch.charCodeAt(0)>=32&&ch!=='/'&&ch!==String.fromCharCode(92)).join('').slice(0,180)||'received-file';
   receiveMeta={name:safeName,size:m.size,type:typeof m.type==='string'?m.type:'application/octet-stream'};
   receiveParts=[];receivedBytes=0;
   nativeFile=!!(window.AndroidFileBridge&&window.AndroidFileBridge.beginFile);
   try{if(nativeFile)window.AndroidFileBridge.beginFile(receiveMeta.name,receiveMeta.type,receiveMeta.size)}
   catch(error){receiveMeta=null;nativeFile=false;say('Impossibile preparare il salvataggio Android: '+error.message);return}
   progress(0);say('Ricezione '+receiveMeta.name+' ('+(receiveMeta.size/1073741824).toFixed(2)+' GB)')
  }else if(m.kind==='end'&&receiveMeta){
   if(receivedBytes!==receiveMeta.size){
    say('File incompleto: dimensione ricevuta diversa da quella dichiarata.');
    receiveParts=[];receiveMeta=null;receivedBytes=0;progress(0);return
   }
   if(nativeFile){
    try{window.AndroidFileBridge.finishFile();say('Ricevuto e salvato nei Download: '+receiveMeta.name)}
    catch(error){say('Errore nel salvataggio Android: '+error.message)}
   }else{
    const blob=new Blob(receiveParts,{type:receiveMeta.type}),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download=receiveMeta.name;a.textContent='Scarica '+receiveMeta.name+' ('+(blob.size/1048576).toFixed(1)+' MB)';a.className='btn primary file';
    a.addEventListener('click',()=>setTimeout(()=>URL.revokeObjectURL(url),60000),{once:true});
    $('received').append(a);say('Ricevuto '+receiveMeta.name+'. Tocca Scarica per salvarlo.')
   }
   receiveParts=[];receiveMeta=null;receivedBytes=0;progress(100)
  }
  return
 }
 if(receiveMeta&&e.data instanceof ArrayBuffer){
  if(receivedBytes+e.data.byteLength>receiveMeta.size||receivedBytes+e.data.byteLength>MAX_FILE){
   say('Trasferimento interrotto: il mittente ha inviato più dati del previsto.');
   receiveParts=[];receiveMeta=null;receivedBytes=0;if(channel)channel.close();progress(0);return
  }
  try{
   if(nativeFile)window.AndroidFileBridge.appendChunk(toBase64(e.data));else receiveParts.push(e.data)
   receivedBytes+=e.data.byteLength;
   progress(receiveMeta.size?receivedBytes/receiveMeta.size*100:100);
   say('Ricezione in corso: '+(receiveMeta.size?Math.round(receivedBytes/receiveMeta.size*100):100)+'%')
  }catch(error){say('Errore durante la ricezione: '+error.message);receiveParts=[];receiveMeta=null;receivedBytes=0}
 }
}function closeSession(){if(channel)channel.close();if(pc)pc.close();if(mqtt){if(roomPin)mqtt.publish(topic(roomPin,'offer'),'',{retain:true,qos:1});mqtt.publish(topic(roomPin,'answer'),'',{retain:true,qos:1});mqtt.end(true)}pc=null;channel=null;mqtt=null;roomPin=null;role=null;$('close').disabled=true;$('files').disabled=true;say('Sessione chiusa.');progress(0)}
$('create').onclick=()=>createRoom().catch(e=>say(e.message));
$('join').onclick=()=>joinRoom().catch(e=>{say(e.message);if(pc)pc.close()});
$('files').onchange=e=>{const files=Array.from(e.target.files||[]);e.target.value='';sendFiles(files).catch(e=>say(e.message))};
$('close').onclick=closeSession;
window.addEventListener('pagehide',()=>{if(mqtt&&roomPin){try{mqtt.publish(topic(roomPin,'offer'),'',{retain:true,qos:1});mqtt.publish(topic(roomPin,'answer'),'',{retain:true,qos:1})}catch(e){}}});
</script></body></html>"""

@app.get("/")
def home():
    return Response(HTML, mimetype="text/html")

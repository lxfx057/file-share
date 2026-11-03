(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = { mqtt:null, pc:null, channel:null, pin:null, role:null, wasm:null, received:[], meta:null, receivedBytes:0, pendingCrc:null, busy:false };
  const CHUNK = 48 * 1024;
  const MAX_FILE = 3_000_000_000;
  const MQTT_URL = "wss://broker.emqx.io:8084/mqtt";

  function status(message, kind="normal") {
    const line = $("status");
    line.lastElementChild.textContent = message;
    const dot = line.querySelector(".status-dot");
    dot.className = "status-dot" + (kind==="good" ? " good" : kind==="bad" ? " bad" : "");
  }
  function setProgress(value) {
    const p = Math.max(0, Math.min(100, value));
    $("bar").style.width = p + "%";
    $("percent").textContent = Math.round(p) + "%";
  }
  function connection(text, online=false) {
    $("connection-label").textContent = text;
    $("connection-led").classList.toggle("online", online);
  }
  function roomTopic(pin, type) { return "fileshare98/v2/" + pin + "/" + type; }
  function bytes(...parts) {
    const out = new Uint8Array(parts.reduce((n,p)=>n+p.length,0));
    let offset=0; for(const p of parts){out.set(p,offset);offset+=p.length;} return out;
  }
  function encodeRemaining(n) {
    const out=[]; do { let d=n%128; n=Math.floor(n/128); if(n>0)d|=128; out.push(d); } while(n>0); return new Uint8Array(out);
  }
  function utf8(s) { return new TextEncoder().encode(s); }
  function mqttPacket(header, body) { return bytes(new Uint8Array([header]),encodeRemaining(body.length),body); }

  // Small MQTT 3.1.1 WebSocket client: no external CDN script is required.
  class TinyMqtt {
    constructor(url) { this.url=url; this.ws=null; this.id=1; this.handlers=new Map(); this.onmessage=()=>{}; this.keepalive=null; this.buffer=new Uint8Array(0); }
    connect() {
      return new Promise((resolve,reject)=>{
        let settled=false;
        try { this.ws=new WebSocket(this.url,["mqtt"]); this.ws.binaryType="arraybuffer"; }
        catch(e){reject(new Error("Il browser non consente il collegamento MQTT: "+e.message));return;}
        const timer=setTimeout(()=>{if(!settled){settled=true;this.close();reject(new Error("Il servizio PIN non risponde. Riprova tra poco."));}},16000);
        this.ws.onopen=()=>{
          const client="fs98_"+Math.random().toString(16).slice(2,14);
          const name=utf8("MQTT");
          const body=bytes(new Uint8Array([0,name.length]),name,new Uint8Array([4,2,0,30,0,client.length]),utf8(client));
          this.ws.send(mqttPacket(0x10,body));
        };
        this.ws.onerror=()=>{if(!settled){settled=true;clearTimeout(timer);reject(new Error("Connessione al servizio PIN non riuscita."));}};
        this.ws.onclose=()=>{if(!settled){settled=true;clearTimeout(timer);reject(new Error("Il servizio PIN ha chiuso la connessione."));} };
        this.ws.onmessage=(ev)=>this.parse(ev.data,()=>{
          if(!settled){settled=true;clearTimeout(timer);this.keepalive=setInterval(()=>{if(this.ws&&this.ws.readyState===1)this.ws.send(new Uint8Array([0xc0,0]));},20000);resolve();}
        });
      });
    }
    send(header,body){if(!this.ws||this.ws.readyState!==1)throw new Error("Connessione PIN interrotta.");this.ws.send(mqttPacket(header,body));}
    subscribe(topic){
      const id=this.id++, t=utf8(topic), body=bytes(new Uint8Array([id>>8,id&255,t.length>>8,t.length&255]),t,new Uint8Array([0]));
      this.send(0x82,body);
    }
    publish(topic,payload,retain=true){
      const t=utf8(topic), p=utf8(payload), body=bytes(new Uint8Array([t.length>>8,t.length&255]),t,p);
      this.send(retain?0x31:0x30,body);
    }
    parse(data,onConnected){
      let incoming;
      if(data instanceof ArrayBuffer)incoming=new Uint8Array(data);else return;
      this.buffer=bytes(this.buffer,incoming);
      while(this.buffer.length>=2){
        let multiplier=1,remaining=0,pos=1,digit;
        do{if(pos>=this.buffer.length)return;digit=this.buffer[pos++];remaining+=(digit&127)*multiplier;multiplier*=128;}while(digit&128);
        if(this.buffer.length<pos+remaining)return;
        const packet=this.buffer.slice(0,pos+remaining);this.buffer=this.buffer.slice(pos+remaining);
        const type=packet[0]>>4, body=packet.slice(pos);
        if(type===2){if(body.length<2||body[1]!==0)throw new Error("Il broker ha rifiutato la connessione.");onConnected();}
        else if(type===3){
          if(body.length<2)continue;const len=(body[0]<<8)|body[1];if(body.length<2+len)continue;
          const topic=new TextDecoder().decode(body.slice(2,2+len));let offset=2+len;const qos=(packet[0]>>1)&3;if(qos>0)offset+=2;
          this.onmessage(topic,new TextDecoder().decode(body.slice(offset)));
        }
      }
    }
    close(){if(this.keepalive)clearInterval(this.keepalive);if(this.ws){try{this.ws.close();}catch(_){}}this.ws=null;}
  }

  async function initRust(){
    try{
      const mod=await import("/static/wasm/fileshare_core.js");
      await mod.default();
      state.wasm=mod;
      $("rust-state").textContent="WASM attivo";
    }catch(_){$("rust-state").textContent="fallback JS";}
  }
  function crc32Fallback(buffer){
    let crc=0xffffffff;const data=new Uint8Array(buffer);
    for(const b of data){crc^=b;for(let k=0;k<8;k++)crc=(crc>>>1)^((crc&1)?0xedb88320:0);}
    return (crc^0xffffffff)>>>0;
  }
  function checksum(buffer){return state.wasm?state.wasm.crc32(new Uint8Array(buffer)):crc32Fallback(buffer);}
  async function backendHealth(){
    try{
      const r=await fetch("/api/health",{cache:"no-store"});
      if(!r.ok)throw new Error("HTTP "+r.status);
      const j=await r.json();
      if(!j.ok)throw new Error("Backend non pronto");
      $("backend-state").textContent="Backend Python: online";
    }catch(e){$("backend-state").textContent="Backend Python: errore";status("Il backend Python non risponde: "+e.message,"bad");}
  }
  function waitIce(){
    return new Promise(resolve=>{
      if(state.pc.iceGatheringState==="complete"){resolve();return;}
      let done=false;const finish=()=>{if(done)return;done=true;state.pc.removeEventListener("icegatheringstatechange",check);clearTimeout(timer);resolve();};
      const check=()=>{if(state.pc.iceGatheringState==="complete")finish();};
      const timer=setTimeout(finish,12000);
      state.pc.addEventListener("icegatheringstatechange",check);
    });
  }
  function setupPeer(sender){
    state.pc=new RTCPeerConnection({iceServers:[{urls:"stun:stun.l.google.com:19302"},{urls:"stun:stun.cloudflare.com:3478"}]});
    state.pc.onconnectionstatechange=()=>{
      const s=state.pc.connectionState;
      connection(s==="connected"?"Collegato":s==="connecting"?"Connessione…":s==="failed"?"Connessione fallita":s==="disconnected"?"Disconnesso":"In attesa",s==="connected");
      if(s==="failed")status("Connessione diretta non riuscita. Prova entrambi i telefoni sulla stessa rete Wi-Fi oppure riprova.","bad");
    };
    if(sender){state.channel=state.pc.createDataChannel("files",{ordered:true});wireChannel();}
    else state.pc.ondatachannel=e=>{state.channel=e.channel;wireChannel();};
  }
  function wireChannel(){
    const ch=state.channel;ch.binaryType="arraybuffer";
    ch.onopen=()=>{connection("Dispositivi collegati",true);status("Collegamento riuscito. Ora puoi trasferire i file.","good");$("files").disabled=state.role!=="sender";$("copy-pin").disabled=false;};
    ch.onclose=()=>connection("Canale chiuso",false);
    ch.onerror=()=>status("Errore nel canale file.","bad");
    ch.onmessage=onData;
  }
  async function createRoom(){
    if(state.busy)return;state.busy=true;$("create").disabled=true;
    try{
      status("Creo un PIN dal backend Python…");
      const r=await fetch("/api/session",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
      if(!r.ok)throw new Error("Il backend non ha creato il PIN (HTTP "+r.status+").");
      const data=await r.json();if(!data.ok||!/^\d{8}$/.test(data.pin))throw new Error("Risposta PIN non valida.");
      state.pin=data.pin;state.role="sender";$("pin").textContent=state.pin;$("pinBox").classList.remove("hidden");$("copy-pin").disabled=false;$("close").disabled=false;
      connection("Connessione al servizio PIN…");status("Apro il canale di segnalazione…");
      state.mqtt=new TinyMqtt(MQTT_URL);await state.mqtt.connect();
      state.mqtt.subscribe(roomTopic(state.pin,"answer"));
      state.mqtt.onmessage=async(topic,payload)=>{
        if(topic!==roomTopic(state.pin,"answer"))return;
        try{
          const m=JSON.parse(payload);if(m.kind!=="answer"||Date.now()-m.at>600000||!state.pc||state.pc.signalingState!=="have-local-offer")return;
          await state.pc.setRemoteDescription({type:"answer",sdp:m.sdp});
          status("Risposta ricevuta. Apro il collegamento diretto…");connection("Connessione WebRTC…");
        }catch(e){status("Errore nella risposta WebRTC: "+e.message,"bad");}
      };
      setupPeer(true);const offer=await state.pc.createOffer();await state.pc.setLocalDescription(offer);await waitIce();
      state.mqtt.publish(roomTopic(state.pin,"offer"),JSON.stringify({kind:"offer",sdp:state.pc.localDescription.sdp,at:Date.now()}));
      status("PIN pronto: "+state.pin+". Inseriscilo sul dispositivo ricevente.");connection("In attesa del secondo dispositivo");
    }finally{state.busy=false;$("create").disabled=false;}
  }
  async function joinRoom(){
    if(state.busy)return;state.busy=true;$("join").disabled=true;
    try{
      const pin=$("joinPin").value.replace(/\D/g,"");if(!/^\d{8}$/.test(pin))throw new Error("Inserisci un PIN di 8 cifre.");
      state.pin=pin;state.role="receiver";$("close").disabled=false;status("Contatto il servizio PIN…");connection("Connessione al servizio PIN…");
      state.mqtt=new TinyMqtt(MQTT_URL);await state.mqtt.connect();state.mqtt.subscribe(roomTopic(pin,"offer"));
      const offer=await new Promise((resolve,reject)=>{
        let settled=false;const timer=setTimeout(()=>{if(!settled){settled=true;reject(new Error("PIN non trovato o scaduto. Controlla il codice e riprova."));}},35000);
        state.mqtt.onmessage=(topic,payload)=>{
          if(topic!==roomTopic(pin,"offer")||settled)return;
          try{const m=JSON.parse(payload);if(m.kind!=="offer"||!m.sdp||Date.now()-m.at>600000)return;settled=true;clearTimeout(timer);resolve(m);}
          catch(_){}
        };
      });
      setupPeer(false);await state.pc.setRemoteDescription({type:"offer",sdp:offer.sdp});
      const answer=await state.pc.createAnswer();await state.pc.setLocalDescription(answer);await waitIce();
      state.mqtt.publish(roomTopic(pin,"answer"),JSON.stringify({kind:"answer",sdp:state.pc.localDescription.sdp,at:Date.now()}));
      status("PIN riconosciuto. Connessione diretta in corso…");
    }finally{state.busy=false;$("join").disabled=false;}
  }
  function waitDrain(){
    const ch=state.channel;if(!ch||ch.readyState!=="open")return Promise.reject(new Error("Il dispositivo si è disconnesso."));
    if(ch.bufferedAmount<512*1024)return Promise.resolve();
    return new Promise(resolve=>{ch.bufferedAmountLowThreshold=128*1024;ch.addEventListener("bufferedamountlow",resolve,{once:true});});
  }
  async function sendFiles(files){
    if(state.busy)return;if(!state.channel||state.channel.readyState!=="open")throw new Error("Prima collega il dispositivo ricevente.");
    state.busy=true;$("files").disabled=true;
    try{
      for(const file of files){
        if(file.size>MAX_FILE)throw new Error(file.name+" supera il limite applicativo di 3 GB.");
        state.channel.send(JSON.stringify({kind:"meta",name:file.name,size:file.size,type:file.type||"application/octet-stream"}));
        let sent=0;
        while(sent<file.size){
          await waitDrain();const part=await file.slice(sent,Math.min(sent+CHUNK,file.size)).arrayBuffer();
          state.channel.send(JSON.stringify({kind:"chunk",crc:checksum(part)}));state.channel.send(part);
          sent+=part.byteLength;setProgress(file.size?sent/file.size*100:100);
          status("Invio "+file.name+" · "+Math.round(sent/file.size*100)+"%");
        }
        state.channel.send(JSON.stringify({kind:"end"}));status("File inviato: "+file.name,"good");
      }
    }finally{state.busy=false;$("files").disabled=state.role!=="sender";}
  }
  function onData(event){
    if(typeof event.data==="string"){
      let m;try{m=JSON.parse(event.data);}catch(_){return;}
      if(m.kind==="meta"){
        if(!Number.isSafeInteger(m.size)||m.size<0||m.size>MAX_FILE||typeof m.name!=="string"){status("File rifiutato: dati non validi.","bad");return;}
        state.meta={name:m.name.replace(/[\\/\u0000-\u001f]/g,"_").slice(0,180)||"file-ricevuto",size:m.size,type:m.type||"application/octet-stream"};
        state.received=[];state.receivedBytes=0;state.pendingCrc=null;setProgress(0);
        status("Ricezione: "+state.meta.name);
      }else if(m.kind==="chunk"){state.pendingCrc=m.crc;}
      else if(m.kind==="end"&&state.meta){
        if(state.receivedBytes!==state.meta.size){status("File incompleto: dimensione non corrispondente.","bad");state.meta=null;state.received=[];return;}
        const blob=new Blob(state.received,{type:state.meta.type}),url=URL.createObjectURL(blob),a=document.createElement("a");
        a.href=url;a.download=state.meta.name;a.textContent="⬇ Scarica "+state.meta.name+" ("+(blob.size/1048576).toFixed(1)+" MB)";a.className="win-button";
        a.addEventListener("click",()=>setTimeout(()=>URL.revokeObjectURL(url),60000),{once:true});$("received").append(a);
        status("Ricevuto: "+state.meta.name+". Tocca Scarica per salvarlo.","good");setProgress(100);state.meta=null;state.received=[];
      }
      return;
    }
    if(!(event.data instanceof ArrayBuffer)||!state.meta)return;
    if(state.receivedBytes+event.data.byteLength>state.meta.size){status("Dati oltre la dimensione dichiarata: trasferimento interrotto.","bad");state.meta=null;state.received=[];return;}
    const actual=checksum(event.data);
    if(state.pendingCrc!==null&&actual!==state.pendingCrc){status("Controllo integrità fallito: blocco scartato.","bad");state.meta=null;state.received=[];return;}
    state.pendingCrc=null;state.received.push(event.data);state.receivedBytes+=event.data.byteLength;
    setProgress(state.meta.size?state.receivedBytes/state.meta.size*100:100);
    status("Ricezione "+Math.round(state.meta.size?state.receivedBytes/state.meta.size*100:100)+"%");
  }
  function closeSession(){
    if(state.channel)state.channel.close();if(state.pc)state.pc.close();
    if(state.mqtt&&state.pin){try{state.mqtt.publish(roomTopic(state.pin,"offer"),"");state.mqtt.publish(roomTopic(state.pin,"answer"),"");}catch(_){}state.mqtt.close();}
    state.channel=null;state.pc=null;state.mqtt=null;state.pin=null;state.role=null;state.meta=null;state.received=[];
    $("files").disabled=true;$("copy-pin").disabled=true;$("close").disabled=true;connection("Non connesso",false);setProgress(0);status("Sessione chiusa. Puoi crearne una nuova.");
  }
  $("create").addEventListener("click",()=>createRoom().catch(e=>{status(e.message,"bad");connection("Errore",false);}));
  $("join").addEventListener("click",()=>joinRoom().catch(e=>{status(e.message,"bad");connection("Errore",false);}));
  $("files").addEventListener("change",e=>{const files=Array.from(e.target.files||[]);e.target.value="";sendFiles(files).catch(err=>status(err.message,"bad"));});
  $("close").addEventListener("click",closeSession);
  $("copy-pin").addEventListener("click",async()=>{try{await navigator.clipboard.writeText(state.pin);status("PIN copiato negli appunti.","good");}catch(_){status("Seleziona e copia il PIN manualmente.");}});
  $("joinPin").addEventListener("input",e=>{e.target.value=e.target.value.replace(/\D/g,"").slice(0,8);});
  $("clock").textContent=new Intl.DateTimeFormat("it-IT",{hour:"2-digit",minute:"2-digit"}).format(new Date());
  setInterval(()=>$("clock").textContent=new Intl.DateTimeFormat("it-IT",{hour:"2-digit",minute:"2-digit"}).format(new Date()),30000);
  window.addEventListener("pagehide",()=>{if(state.mqtt)state.mqtt.close();});
  backendHealth();initRust();
})();
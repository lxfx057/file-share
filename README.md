# File Share 98 — Android ⇄ iPhone

Interfaccia Windows 98 per inviare file direttamente tra due dispositivi tramite un PIN temporaneo.

## Come funziona

1. Apri il sito sul dispositivo che invia e premi **Crea PIN temporaneo**.
2. Sul dispositivo che riceve apri lo stesso sito, inserisci il PIN a 8 cifre e premi **Collega e ricevi**.
3. Quando i dispositivi sono collegati, scegli i file sul mittente.
4. Il destinatario riceve i dati via WebRTC DataChannel e può scaricarli.
5. La stanza di segnalazione scade automaticamente dopo 10 minuti. Chiudendo la sessione viene anche richiesta la cancellazione immediata.

**I file non vengono caricati su Vercel, Cloudflare o un archivio cloud.** Il servizio Cloudflare Worker conserva soltanto per pochi minuti il PIN e le descrizioni tecniche WebRTC (offer/answer), necessarie per mettere in contatto i due browser. Il trasferimento dei file è peer-to-peer.

## Configurazione gratuita del servizio PIN

Il sito principale può restare su Vercel. Il servizio di segnalazione usa Cloudflare Workers + Workers KV sul piano Free.

1. Crea un account Cloudflare e apri Workers & Pages.
2. Crea un namespace KV chiamato `ROOMS`.
3. Copia l'ID del namespace in `cloudflare-worker/wrangler.toml`, sostituendo `INSERISCI_KV_NAMESPACE_ID`.
4. Dalla cartella `cloudflare-worker`, installa Wrangler (`npm install -D wrangler`) e pubblica con `npx wrangler deploy`.
5. Copia l'URL `https://...` del Worker e inseriscilo nella costante `SIGNAL_URL` in `api/index.py`, al posto di `INSERISCI_URL_WORKER_CLOUDFLARE`.
6. Pubblica nuovamente il progetto Vercel.

Workers Free documenta limiti gratuiti giornalieri; al raggiungimento dei limiti le richieste possono fallire. Non attivare un piano a pagamento o un metodo di pagamento per questo progetto. Verifica sempre che il pannello mostri il piano Free.

## Limiti tecnici importanti

- Il limite applicativo è 3.000.000.000 byte per file; **non è una garanzia che ogni iPhone riesca a ricevere un file da 3 GB**. Safari iOS può avere limiti di memoria e spazio temporaneo quando ricompone il file per il download.
- Il collegamento usa STUN ma non un server TURN a pagamento. Alcune reti mobili, NAT o firewall possono impedire il collegamento diretto. In quel caso prova entrambi i dispositivi sulla stessa rete Wi-Fi.
- Non è richiesto IMEI, MAC address, account o password.
- Il PIN è un codice casuale a 8 cifre, temporaneo. Non condividerlo pubblicamente.
- La stanza scade automaticamente dopo 10 minuti dall'ultima scrittura di segnalazione, anche se la pagina viene chiusa in modo anomalo.
- Il sito non conserva un archivio dei file. Dopo il trasferimento il file esiste soltanto sui dispositivi e nella destinazione scelta dal destinatario.

## Stato

Questa è una prima implementazione da testare su dispositivi reali. Prima di considerarla pronta per file importanti o da 3 GB, verificare connessione, interruzioni, memoria Safari e download su iOS e Android.

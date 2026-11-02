# File Share 98

Sito web per trasferire file tra iPhone e Android in entrambe le direzioni, usando il browser e un PIN temporaneo.

## Come si usa

1. Apri il sito su entrambi i telefoni.
2. Sul telefono che deve inviare premi **Crea PIN temporaneo**.
3. Sul telefono che deve ricevere inserisci quel PIN e premi **Collega e ricevi**.
4. Quando i dispositivi risultano collegati, seleziona uno o più file sul mittente.
5. Il ricevente scarica i file sul proprio telefono.

Per invertire la direzione basta creare il PIN dal telefono che questa volta deve inviare. Non serve installare APK o app: iPhone usa Safari e Android usa il proprio browser.

## Pubblicazione su Vercel

Il progetto è una web app Python/Flask. Il file `vercel.json` instrada le richieste a `api/index.py`; `requirements.txt` contiene le dipendenze Python. Importa il repository in Vercel e pubblica il progetto senza dover configurare database, KV, R2 o credenziali applicative.

## Collegamento temporaneo PIN

La segnalazione usa il broker pubblico MQTT-over-WebSocket Secure `broker.emqx.io`, senza account. I messaggi di segnalazione sono temporanei e scadono dopo 10 minuti. Il broker trasporta soltanto le informazioni necessarie a negoziare WebRTC; i byte dei file passano direttamente tra i dispositivi attraverso un DataChannel WebRTC cifrato.

Il broker è un servizio di terzi: disponibilità, limiti e continuità non sono garantiti. I topic PIN sono pubblici e il PIN non va considerato una credenziale per proteggere informazioni sensibili.

## Limiti tecnici

- Il limite applicativo è 3.000.000.000 byte per file; non garantisce che ogni browser o telefono riesca a gestire file di quelle dimensioni.
- Su iPhone il ricevitore web accumula attualmente i blocchi in memoria prima di creare il download. Safari può quindi non riuscire con file molto grandi, in particolare vicino a 3 GB.
- La connessione WebRTC usa STUN, senza relay TURN. Alcune reti mobili, NAT o firewall possono impedire il collegamento diretto; provare entrambi i dispositivi sulla stessa Wi-Fi può aiutare.
- Entrambe le pagine devono restare aperte durante il trasferimento.
- Questa versione non archivia i file su un cloud e non richiede registrazioni aggiuntive.

## Stato

Codice web predisposto per la pubblicazione su Vercel. Prima di considerarlo pronto all'uso quotidiano occorre completare test reali su iPhone e Android, su reti differenti e con file di grandi dimensioni.

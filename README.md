# File Share 98 — Android ⇄ iPhone

Trasferimento di file tra iPhone e Android tramite PIN, con interfaccia Windows 98.

## Uso previsto

1. Apri File Share 98 su uno dei due telefoni.
2. Premi **Crea PIN temporaneo**: il dispositivo entra in modalità INVIO.
3. Sul secondo telefono apri File Share 98, inserisci lo stesso PIN e premi **Collega e ricevi**.
4. Quando compare la connessione, seleziona i file sul dispositivo mittente.
5. Il ricevente scarica i file: su Android l'app li salva direttamente in **Download/File Share 98**; su iPhone Safari propone il download e il salvataggio nell'app File.

La direzione è libera: Android può inviare a iPhone e iPhone può inviare ad Android.

## APK Android

Il progetto Android è in `android/`. A ogni modifica del progetto Android, GitHub Actions esegue la build dell'APK Debug.

Per scaricarlo:
1. Apri la scheda **Actions** del repository.
2. Apri l'ultima esecuzione riuscita di **Build Android APK**.
3. Scarica l'artifact **File-Share-98-Android-APK**.
4. Estrai lo ZIP e installa `app-debug.apk` su Android.

L'APK contiene la stessa interfaccia Windows 98 e usa il selettore file Android. I file ricevuti vengono scritti progressivamente nella cartella Download, senza accumulare l'intero file nella RAM.

## Collegamento PIN senza registrazione

Il collegamento usa il broker MQTT pubblico `broker.emqx.io` via WebSocket Secure, senza account o credenziali. Non è un servizio gestito da questo progetto e la sua disponibilità non è garantita.

Il broker riceve soltanto il PIN e le descrizioni tecniche WebRTC (offer/answer). **I contenuti dei file non vengono inviati al broker**: viaggiano direttamente tra i dispositivi tramite WebRTC DataChannel, cifrato dal protocollo WebRTC. Il broker pubblico è comunque un'infrastruttura di terzi e i messaggi tecnici di segnalazione non vanno considerati privati.

Non viene creato un archivio cloud e non viene richiesta una nuova registrazione. Il progetto non usa Cloudflare KV, R2 o un database esterno.

## Limiti e note importanti

- Limite applicativo: 3.000.000.000 byte per file. È un tetto software, non una garanzia universale: velocità, spazio libero, browser e rete possono limitare file molto grandi.
- Su Android il ricevitore nativo scrive a blocchi in Download. Su iPhone il browser gestisce il download; Safari può avere limiti di memoria/spazio temporaneo per file molto grandi.
- La connessione diretta WebRTC usa STUN ma non un relay TURN. Alcune reti mobili, NAT o firewall possono impedire il collegamento; in quel caso prova con entrambi i telefoni sulla stessa Wi-Fi.
- Il broker MQTT pubblico può essere indisponibile, limitare il traffico o cambiare servizio. Se accade, il PIN non potrà collegare i dispositivi finché non si sceglie un altro sistema di segnalazione.
- Tieni aperte le schermate di entrambi i dispositivi per tutta la durata del trasferimento.
- Il PIN è temporaneo e va condiviso solo con il destinatario previsto.

## Stato

Implementazione in sviluppo. La build APK automatica e il trasferimento reale devono ancora essere verificati su dispositivi fisici iOS e Android, inclusi file di grandi dimensioni. Non considerarlo pronto per dati importanti finché i test non sono completati.

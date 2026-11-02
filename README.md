# File Share 98 — Android ⇄ iOS

Interfaccia Windows 98 per trasferire file tra Android e iPhone, con upload multipart fino a **3 GB per singolo file**.

## Architettura
I file non transitano attraverso la funzione serverless Vercel: il backend genera URL S3 prefirmati e il browser invia i blocchi direttamente a Cloudflare R2. Non si usa Base64 né /tmp. Gli oggetti restano in R2.

## Configurazione obbligatoria
1. Crea un bucket Cloudflare R2.
2. Crea credenziali API R2 con permessi Object Read & Write limitati a quel bucket.
3. In Vercel → Project → Settings → Environment Variables configura:
   - R2_ENDPOINT = https://ACCOUNT_ID.r2.cloudflarestorage.com
   - R2_BUCKET = nome del bucket
   - R2_ACCESS_KEY_ID = access key R2
   - R2_SECRET_ACCESS_KEY = secret key R2
   - HUB_PASSWORD = password lunga e unica
   - FLASK_SECRET_KEY = stringa casuale crittograficamente robusta
4. Configura CORS sul bucket R2 (sostituisci l'origine col dominio Vercel):
```json
[{"AllowedOrigins":["https://TUO-PROGETTO.vercel.app"],"AllowedMethods":["GET","PUT","HEAD"],"AllowedHeaders":["*"],"ExposeHeaders":["ETag"],"MaxAgeSeconds":3600}]
```
5. Esegui un nuovo deploy Vercel.

## Trasferimenti
- Limite applicativo: 3 GiB per file.
- Blocchi da 64 MiB caricati direttamente dal browser a R2.
- Download tramite URL prefirmati temporanei.
- Annullamento del multipart in corso.
- L'autenticazione è una password condivisa con sessione Flask.

## Note
- R2 è un servizio esterno: controlla quote, costi e limiti del tuo account.
- Safari iOS usa il normale flusso di download (File/Download).
- Configura una regola lifecycle R2 per abortire i multipart incompleti dopo 1 giorno.
- L'app non può completare trasferimenti finché le variabili R2 non sono configurate su Vercel.

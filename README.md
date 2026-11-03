# File Share 98

A Windows 98-inspired web app for direct browser-to-browser file transfer between iPhone, Android and desktop.

## Stack
- **Python / Flask**: serves the application, exposes a health endpoint and generates temporary 8-digit PINs.
- **CSS**: separate Windows 98-style desktop, title bar, taskbar, panels and controls.
- **Rust + WebAssembly**: CRC-32 integrity checks for transfer chunks. GitHub Actions compiles the Rust crate to `api/static/wasm`.
- **WebRTC DataChannel**: encrypted peer-to-peer file bytes.
- **MQTT over WSS**: signaling only; file contents never pass through the broker.

## Run locally
```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
flask --app api.index run
```

Open http://127.0.0.1:5000.

## Transfer
1. Open the site on both devices.
2. On the sender, select **Crea PIN**.
3. On the receiver, enter the 8-digit PIN and select **Collega e ricevi**.
4. Wait for the connected state, then choose files on the sender.
5. Tap the download link on the receiver.

## Technical notes
- No account, APK or cloud file storage is required.
- The public EMQX MQTT-over-WebSocket broker is used for temporary signaling. It is a third-party service and availability is not guaranteed.
- WebRTC uses public STUN servers only. Some mobile networks, NATs or firewalls may prevent direct connections; a TURN relay would improve reliability but requires a relay service.
- The 3 GB app limit is not a guarantee that every mobile browser can handle files that large. iOS Safari may need substantial memory for large downloads.
- Keep both browser tabs open during transfer.
- The PIN is a short-lived rendezvous code, not a credential for sensitive data.

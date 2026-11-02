const ROOM_TTL = 600;
const PIN_LENGTH = 8;
const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "access-control-allow-origin": "*", "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS", "access-control-allow-headers": "content-type" }
});
const pin = () => Array.from(crypto.getRandomValues(new Uint8Array(PIN_LENGTH)), b => String(b % 10)).join("");
const validPin = p => /^\\d{8}$/.test(p);
export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { headers: { "access-control-allow-origin": "*", "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS", "access-control-allow-headers": "content-type" } });
    const url = new URL(request.url);
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts[0] !== "rooms") return json({ error: "Not found" }, 404);
    if (request.method === "POST" && parts.length === 1) {
      for (let i = 0; i < 8; i++) {
        const code = pin();
        if (!await env.ROOMS.get(code)) {
          await env.ROOMS.put(code, JSON.stringify({ created: Date.now(), offer: null, answer: null }), { expirationTtl: ROOM_TTL });
          return json({ pin: code, expires_in: ROOM_TTL });
        }
      }
      return json({ error: "Impossibile creare un PIN, riprova." }, 503);
    }
    const code = parts[1];
    if (!validPin(code)) return json({ error: "PIN non valido." }, 400);
    const raw = await env.ROOMS.get(code);
    if (!raw) return json({ error: "PIN scaduto o inesistente." }, 404);
    if (request.method === "GET" && parts.length === 2) return json(JSON.parse(raw));
    if (request.method === "PUT" && parts.length === 3 && ["offer", "answer"].includes(parts[2])) {
      let body;
      try { body = await request.json(); } catch { return json({ error: "Payload non valido." }, 400); }
      if (!body || typeof body.sdp !== "string" || body.sdp.length > 100000) return json({ error: "Descrizione WebRTC non valida." }, 400);
      const room = JSON.parse(raw);
      room[parts[2]] = { type: parts[2] === "offer" ? "offer" : "answer", sdp: body.sdp };
      await env.ROOMS.put(code, JSON.stringify(room), { expirationTtl: ROOM_TTL });
      return json({ ok: true });
    }
    if (request.method === "DELETE" && parts.length === 2) {
      await env.ROOMS.delete(code);
      return json({ ok: true });
    }
    return json({ error: "Not found" }, 404);
  }
};
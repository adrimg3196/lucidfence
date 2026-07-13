// Headless screenshot vía Chrome DevTools Protocol (Node 22 WebSocket global).
// Setea la cookie de sesión directamente (CDP Network.setCookie) para evitar
// el auto-login lento, luego espera a que el DOM de la vista tenga datos.
import http from 'node:http';
import fs from 'node:fs';
const WebSocket = globalThis.WebSocket;

const TARGET = process.argv[2] || 'http://127.0.0.1:8765/#overview';
const OUT = process.argv[3] || '/tmp/shots/view.png';
const READY = process.argv[4] || '#content';
const WAIT_MS = parseInt(process.argv[5] || '20000', 10);
const TOKEN = process.argv[6] || fs.readFileSync('/tmp/token.txt', 'utf8').trim();
const ORG = process.argv[7] || 'org_c40aa88904';

function getJSON(path, method = 'GET', body = null) {
  return new Promise((res) => {
    const req = http.request(`http://127.0.0.1:9222${path}`, { method }, r => {
      let d = ''; r.on('data', c => d += c); r.on('end', () => { try { res(JSON.parse(d)); } catch (e) { res({}); } });
    });
    if (body) req.write(body);
    req.on('error', () => res({})); req.end();
  });
}
const tab = await getJSON('/json/new?' + encodeURIComponent(TARGET), 'PUT');
const ws = new WebSocket(tab.webSocketDebuggerUrl);
let id = 0; const pending = new Map();
function send(method, params = {}) { return new Promise((res) => { const mid = ++id; pending.set(mid, res); ws.send(JSON.stringify({ id: mid, method, params })); }); }
ws.addEventListener('message', m => { const msg = JSON.parse(m.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg.result); pending.delete(msg.id); } });
await new Promise(r => ws.addEventListener('open', r));
await send('Network.enable');
await send('Page.enable'); await send('Runtime.enable');
// Setear cookie de sesión (evita auto-login)
await send('Network.setCookie', { name: 'gf_session', value: TOKEN, domain: '127.0.0.1', path: '/', httpOnly: true, sameSite: 'Lax' });
await send('Network.setCookie', { name: 'gf_org', value: ORG, domain: '127.0.0.1', path: '/', httpOnly: true, sameSite: 'Lax' });
await send('Page.navigate', { url: TARGET });

const start = Date.now();
let ready = false;
while (Date.now() - start < WAIT_MS) {
  const r = await send('Runtime.evaluate', {
    expression: `(() => { const el = document.querySelector(${JSON.stringify(READY)}); const auth = document.getElementById('authScreen'); const authVisible = auth && !auth.classList.contains('hidden'); return { hasChildren: !!el && el.children.length > 0, authVisible }; })()`,
    returnByValue: true,
  });
  const v = r && r.result && r.result.value;
  if (v && v.hasChildren && !v.authVisible) { ready = true; break; }
  await new Promise(r => setTimeout(r, 400));
}
console.log('ready=' + ready + ' after ' + (Date.now() - start) + 'ms');
await new Promise(r => setTimeout(r, 5000));
const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
fs.writeFileSync(OUT, Buffer.from(shot.data, 'base64'));
console.log('saved ' + OUT);
ws.close();
setTimeout(() => process.exit(0), 300);

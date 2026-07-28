import http from 'node:http';
import fs from 'node:fs';
const WebSocket = globalThis.WebSocket;
const TARGET = 'http://127.0.0.1:8765/#routes';
function getJSON(path, method = 'GET', body = null) {
  return new Promise((res) => {
    const req = http.request(`http://127.0.0.1:9222${path}`, { method }, r => {
      let d = ''; r.on('data', c => d += c); r.on('end', () => { try { res(JSON.parse(d)); } catch (e) { res({}); } });
    });
    if (body) req.write(body); req.on('error', () => res({})); req.end();
  });
}
const tab = await getJSON('/json/new?' + encodeURIComponent(TARGET), 'PUT');
const ws = new WebSocket(tab.webSocketDebuggerUrl);
let id = 0; const pending = new Map();
function send(method, params = {}) { return new Promise((res) => { const mid = ++id; pending.set(mid, res); ws.send(JSON.stringify({ id: mid, method, params })); }); }
const logs = [];
ws.addEventListener('message', m => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg.result); pending.delete(msg.id); }
  if (msg.method === 'Runtime.exceptionThrown') logs.push('EXC: ' + (msg.params.exceptionDetails?.exception?.description || msg.params.exceptionDetails?.text));
  if (msg.method === 'Runtime.consoleAPICalled') logs.push('C:' + (msg.params.args||[]).map(a=>a.value||a.description||'').join(' '));
});
await new Promise(r => ws.addEventListener('open', r));
await send('Page.enable'); await send('Runtime.enable');
await send('Page.navigate', { url: TARGET });
await new Promise(r => setTimeout(r, 4000));
const d = await send('Runtime.evaluate', {
  expression: `(async () => {
    const out = {};
    out.L = typeof L;
    out.routeList = (document.querySelector('#route-list')||{}).innerHTML ? document.querySelector('#route-list').innerHTML.slice(0,120) : 'NO-EL';
    try {
      const r = await fetch('/api/routes', { credentials: 'same-origin' });
      out.routesStatus = r.status;
      out.routesCT = r.headers.get('content-type');
      const j = await r.json();
      out.routesLen = (j.routes||[]).length;
      out.firstRoute = j.routes && j.routes[0] ? JSON.stringify(j.routes[0]).slice(0,160) : 'none';
    } catch(e) { out.routesErr = e.message; }
    return JSON.stringify(out);
  })()`,
  returnByValue: true,
  awaitPromise: true,
});
console.log('DIAG:', d.result.value);
console.log('LOGS:', logs.slice(0,8).join(' | '));
ws.close(); setTimeout(()=>process.exit(0), 300);

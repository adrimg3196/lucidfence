/* Manual interactivo bilingüe (ES/EN). Los pasos comparten capturas; el idioma
   se elige con el botón del header, se recuerda en localStorage y arranca del
   idioma del navegador. Sin dependencias, sin red: viaja con el producto. */
const STEPS = {
es: [
 {t:"Qué es LucidFence", h:`
  <p><strong>El complemento de geofencing y postura sobre el UEM que ya tienes</strong>
  (Intune, Jamf, Applivery, Fleet…): lee tu flota, correlaciona ubicación y señales,
  <em>explica</em> el riesgo y solo actúa a través de tu UEM cuando tú lo decides.</p>
  <div class="tip">100% local y gratis (Apache-2.0): tus datos no salen de tu máquina.
  Sin telemetría. Sin nube de terceros.</div>
  <p>Arranca con <code>lucidfence quickstart</code> (o <code>python3 saas_server.py</code>)
  y abre <code>http://127.0.0.1:8765/</code>. Sin credenciales entras en
  <strong>modo demo</strong>: flota de ejemplo, cero riesgo, todo explorable.</p>`},
 {t:"El Command Center", img:"manual/01-dashboard.png", h:`
  <p>Tu pantalla de guardia: dispositivos dentro/fuera de geovalla, incumplimientos,
  CVEs en apps de la flota, mapa en vivo y donut de conformidad (exportable a PDF).</p>
  <div class="tip">La banda amarilla te recuerda que ves datos de ejemplo; desaparece
  al conectar tu UEM.</div>`},
 {t:"Mapa de flota", img:"manual/02-mapa.png", h:`
  <p>Cada punto es un dispositivo, coloreado por estado: dentro, fuera o desconocido.</p>
  <div class="tip">¿Prefieres un fondo real estilo Google Maps? Pulsa <strong>Mapa
  detallado</strong> (abajo a la derecha del mapa): carga calles y ciudades de
  OpenStreetMap. Es opt-in con aviso: las teselas se descargan de un tercero, que
  ve la zona del visor — tus dispositivos y datos jamás se envían. El defecto
  sigue siendo el mapa local con cero peticiones.</div>
  <div class="tip">¿Portátiles sin GPS? Declara tu red (CIDR de salida, SSID de la
  oficina) y LucidFence los posiciona de forma gruesa y honesta — red-fencing sin
  hardware nuevo.</div>`},
 {t:"Dispositivos", img:"manual/03-dispositivos.png", h:`
  <p>La tabla operativa. Clic en cualquier fila para la ficha del dispositivo:
  última posición, postura (cifrado, Lockdown Mode, supervisión, salud de hardware),
  apps con CVE y las acciones disponibles <em>a través de tu UEM</em>.</p>`},
 {t:"Riesgo explicable", img:"manual/04-riesgo.png", h:`
  <p>Nada de caja negra: cada score lleva <strong>sus razones</strong> y un sello que
  distingue señal real de ausencia de señal.</p>
  <div class="tip">Regla de honestidad: <strong>lo desconocido nunca penaliza</strong>.
  Un dato que tu UEM no reporta jamás inventa riesgo.</div>`},
 {t:"Geovallas", img:"manual/05-geovallas.png", h:`
  <p>Círculos (centro + radio) o polígonos. Un dispositivo queda dentro, fuera o
  desconocido — nunca se adivina.</p>
  <div class="tip">¿Config como código? Mantén <code>fences.json</code> en git y
  aplícalo con <code>lucidfence apply</code>: valida, enseña el diff y <em>simula el
  impacto</em> contra tu histórico antes de escribir nada.</div>`},
 {t:"Incidentes y alertas", img:"manual/06-incidentes.png", h:`
  <p>Lo que merece atención (salidas de geovalla, incumplimientos), con contexto.
  Las alertas salen por Slack, Teams, webhook firmado o ntfy.</p>`},
 {t:"Workflows", img:"manual/07-workflows.png", h:`
  <p>Automatizaciones comunes ya montadas ("si sale de la geovalla, notifica") o la
  tuya propia con disparador + condición + acción, sin tocar JSON.</p>`},
 {t:"Conectar tu UEM", img:"manual/08-conectores.png", h:`
  <p>El asistente te guía por fabricante pidiendo el <strong>mínimo privilegio</strong>
  real (en observe basta solo-lectura). La matriz de ubicación de la documentación
  dice qué entrega de verdad cada UEM — sin prometer de más.</p>`},
 {t:"El control es tuyo", img:"manual/09-ajustes.png", h:`
  <p>La seguridad del rollout, por diseño:</p>
  <p>1 · <strong>observe</strong> (por defecto): todo se calcula y audita, nada se
  ejecuta — el dry-run viene activado.<br>
  2 · <strong>enforce</strong>: solo si tú lo activas por tenant, con allow-list por acción.<br>
  3 · <strong>wipe con doble llave</strong>: <code>allow_wipe</code> <em>y</em> el
  dispositivo en <code>wipe_allowlist</code>.</p>
  <div class="tip warn">LucidFence nunca actúa sobre un dispositivo real por su
  cuenta: ejecuta la política que tú escribiste, con esos frenos.</div>
  <p>¿Y lo que NO ves? <code>GET /api/coverage</code> enseña tus puntos ciegos:
  dispositivos sin señal, los que dejaron de reportar y geovallas vacías.</p>`}
],
en: [
 {t:"What is LucidFence", h:`
  <p><strong>The geofencing and posture companion for the UEM you already run</strong>
  (Intune, Jamf, Applivery, Fleet…): it reads your fleet, correlates location with
  signals, <em>explains</em> risk, and only acts through your UEM when you decide.</p>
  <div class="tip">100% local and free (Apache-2.0): your data never leaves your
  machine. No telemetry. No third-party cloud.</div>
  <p>Start with <code>lucidfence quickstart</code> (or <code>python3 saas_server.py</code>)
  and open <code>http://127.0.0.1:8765/</code>. With no credentials you land in
  <strong>demo mode</strong>: a sample fleet, zero risk, everything explorable.</p>`},
 {t:"The Command Center", img:"manual/01-dashboard.png", h:`
  <p>Your on-call screen: devices inside/outside geofences, compliance breaches,
  CVEs in fleet apps, a live map and the compliance donut (exportable to PDF).</p>
  <div class="tip">The yellow banner reminds you these are sample data; it goes away
  once you connect your UEM.</div>`},
 {t:"Fleet map", img:"manual/02-mapa.png", h:`
  <p>Every dot is a device, colored by state: inside, outside or unknown.</p>
  <div class="tip">Prefer a real Google-Maps-style background? Click <strong>Mapa
  detallado</strong> (bottom right of the map): it loads streets and cities from
  OpenStreetMap. It is opt-in with a notice: tiles are downloaded from a third
  party, which sees the viewport area — your devices and data are never sent. The
  default remains the local map with zero requests.</div>
  <div class="tip">Laptops without GPS? Declare your network (egress CIDR, office
  SSID) and LucidFence positions them coarsely and honestly — network-fencing with
  no new hardware.</div>`},
 {t:"Devices", img:"manual/03-dispositivos.png", h:`
  <p>The operational table. Click any row for the device sheet: last position,
  posture (encryption, Lockdown Mode, supervision, hardware health), apps with
  CVEs, and the actions available <em>through your UEM</em>.</p>`},
 {t:"Explainable risk", img:"manual/04-riesgo.png", h:`
  <p>No black box: every score carries <strong>its reasons</strong> and a seal that
  distinguishes real signal from absence of signal.</p>
  <div class="tip">Honesty rule: <strong>the unknown never penalizes</strong>. A
  datum your UEM does not report never invents risk.</div>`},
 {t:"Geofences", img:"manual/05-geovallas.png", h:`
  <p>Circles (center + radius) or polygons. A device is inside, outside or unknown
  — it is never guessed.</p>
  <div class="tip">Config as code? Keep <code>fences.json</code> in git and apply it
  with <code>lucidfence apply</code>: it validates, shows the diff and <em>simulates
  the impact</em> against your history before writing anything.</div>`},
 {t:"Incidents & alerts", img:"manual/06-incidentes.png", h:`
  <p>What deserves attention (geofence exits, compliance breaches), with context.
  Alerts go out via Slack, Teams, signed webhook or ntfy.</p>`},
 {t:"Workflows", img:"manual/07-workflows.png", h:`
  <p>Common automations ready to enable ("on geofence exit, notify") or build your
  own with trigger + condition + action, without touching JSON.</p>`},
 {t:"Connect your UEM", img:"manual/08-conectores.png", h:`
  <p>The wizard guides you per vendor asking for the real <strong>least
  privilege</strong> (in observe, read-only is enough). The location matrix in the
  docs states what each UEM truly delivers — no overpromising.</p>`},
 {t:"You stay in control", img:"manual/09-ajustes.png", h:`
  <p>Rollout safety, by design:</p>
  <p>1 · <strong>observe</strong> (default): everything is computed and audited,
  nothing executes — dry-run comes enabled.<br>
  2 · <strong>enforce</strong>: only if you enable it per tenant, with a per-action
  allow-list.<br>
  3 · <strong>wipe needs a double key</strong>: <code>allow_wipe</code> <em>and</em>
  the device in <code>wipe_allowlist</code>.</p>
  <div class="tip warn">LucidFence never acts on a real device on its own: it runs
  the policy you wrote, with those brakes.</div>
  <p>And what you do NOT see? <code>GET /api/coverage</code> shows your blind spots:
  devices without signal, devices that stopped reporting, and empty geofences.</p>`}
]};
const UI = {
  es:{step:"Paso", of:"de", prev:"← Anterior", next:"Siguiente →", title:"Manual de LucidFence",
      sub:"Interactivo · con capturas reales del producto · ←/→ para navegar", toggle:"EN"},
  en:{step:"Step", of:"of", prev:"← Previous", next:"Next →", title:"LucidFence User Guide",
      sub:"Interactive · real product screenshots · use ←/→ to navigate", toggle:"ES"}
};
let lang = (()=>{ try{ const s=localStorage.getItem("lf_manual_lang"); if(s) return s; }catch(_e){}
  return (navigator.language||"").toLowerCase().startsWith("es") ? "es" : "en"; })();
const nav=document.getElementById("nav"),cont=document.getElementById("content"),
      pos=document.getElementById("pos"),fill=document.getElementById("fill"),
      prev=document.getElementById("prev"),next=document.getElementById("next"),
      langBtn=document.getElementById("lang"),titleEl=document.getElementById("title"),
      subEl=document.getElementById("sub");
let i=Math.max(0,Math.min(STEPS.es.length-1,parseInt(location.hash.slice(1))||0));
function S(){ return STEPS[lang]; }
function buildNav(){ nav.innerHTML="";
  S().forEach((s,k)=>{const b=document.createElement("button");b.textContent=(k+1)+" · "+s.t;
    b.onclick=()=>go(k);nav.appendChild(b);}); }
function applyLang(){ const u=UI[lang];
  document.documentElement.lang=lang; titleEl.textContent=u.title; subEl.textContent=u.sub;
  prev.textContent=u.prev; next.textContent=u.next; langBtn.textContent=u.toggle;
  buildNav(); go(i); }
function go(k){i=Math.max(0,Math.min(S().length-1,k));const s=S()[i];const u=UI[lang];
  cont.innerHTML=`<div class="step-n">${u.step} ${i+1} ${u.of} ${S().length}</div><h2>${s.t}</h2>`+
    (s.img?`<img src="${s.img}" alt="${s.t}" onclick="this.classList.toggle('zoom')">`:"")+s.h;
  [...nav.children].forEach((b,k2)=>b.classList.toggle("on",k2===i));
  pos.textContent=(i+1)+" / "+S().length;fill.style.transform="scaleX("+((i+1)/S().length)+")";
  prev.disabled=i===0;next.disabled=i===S().length-1;
  location.hash=i;cont.scrollTop=0;}
langBtn.onclick=()=>{ lang = lang==="es" ? "en" : "es";
  try{ localStorage.setItem("lf_manual_lang", lang); }catch(_e){}
  applyLang(); };
prev.onclick=()=>go(i-1);next.onclick=()=>go(i+1);
addEventListener("keydown",e=>{if(e.key==="ArrowRight")go(i+1);if(e.key==="ArrowLeft")go(i-1);});
applyLang();

const S = [
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
];
const nav=document.getElementById("nav"),cont=document.getElementById("content"),
      pos=document.getElementById("pos"),fill=document.getElementById("fill"),
      prev=document.getElementById("prev"),next=document.getElementById("next");
let i=Math.max(0,Math.min(S.length-1,parseInt(location.hash.slice(1))||0));
S.forEach((s,k)=>{const b=document.createElement("button");b.textContent=(k+1)+" · "+s.t;
  b.onclick=()=>go(k);nav.appendChild(b);});
function go(k){i=Math.max(0,Math.min(S.length-1,k));const s=S[i];
  cont.innerHTML=`<div class="step-n">Paso ${i+1} de ${S.length}</div><h2>${s.t}</h2>`+
    (s.img?`<img src="${s.img}" alt="${s.t}" onclick="this.classList.toggle('zoom')">`:"")+s.h;
  [...nav.children].forEach((b,k2)=>b.classList.toggle("on",k2===i));
  pos.textContent=(i+1)+" / "+S.length;fill.style.width=((i+1)/S.length*100)+"%";
  prev.disabled=i===0;next.disabled=i===S.length-1;
  location.hash=i;cont.scrollTop=0;}
prev.onclick=()=>go(i-1);next.onclick=()=>go(i+1);
addEventListener("keydown",e=>{if(e.key==="ArrowRight")go(i+1);if(e.key==="ArrowLeft")go(i-1);});
go(i);

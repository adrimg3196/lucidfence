/* ============================================================
   LucidFence — Command Center  (app.js)
   UI tipo Linear + IA/MoA + workflows + rutas + geovallas
   ============================================================ */
"use strict";

const App = {
  status: null,        // último /api/status
  org: null,           // /api/org
  aiProviders: [],     // /api/ai/providers
  view: "overview",
  devFilter: "all",
  devSearch: "",
  devSort: "name",
  map: null, mapMarkers: {}, trailLayer: null, complianceChart: null,
  pollTimer: null,
};

/* ---------- helpers ---------- */
const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));
const el = (t, c, h) => { const e=document.createElement(t); if(c)e.className=c; if(h!=null)e.innerHTML=h; return e; };
function fmtDur(sec){
  sec = Math.max(0, Math.floor(Number(sec)||0));
  if(sec < 60) return sec+"s";
  const m = Math.floor(sec/60), s = sec%60;
  if(m < 60) return (s? m+"m "+s+"s" : m+"m");
  const h = Math.floor(m/60), mm = m%60;
  if(h < 24) return (mm? h+"h "+mm+"m" : h+"h");
  const d = Math.floor(h/24), hh = h%24;
  return (hh? d+"d "+hh+"h" : d+"d");
}
const esc = (s) => String(s==null?"":s).replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function parseTime(ts){
  if(ts==null || ts==="") return null;
  if(ts instanceof Date) return Number.isNaN(ts.getTime())?null:ts;
  if(typeof ts === "number"){
    const ms = ts > 1e12 ? ts : ts * 1000;
    const d = new Date(ms); return Number.isNaN(d.getTime())?null:d;
  }
  const numeric = Number(ts);
  if(String(ts).trim()!=="" && Number.isFinite(numeric)){
    const d = new Date(numeric > 1e12 ? numeric : numeric * 1000);
    return Number.isNaN(d.getTime())?null:d;
  }
  const d = new Date(ts); return Number.isNaN(d.getTime())?null:d;
}
const fmt = {
  time: (ts) => { const d=parseTime(ts); return d?d.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}):"—"; },
  date: (ts) => { const d=parseTime(ts); return d?d.toLocaleString():"—"; },
  ago: (ts) => {
    const d=parseTime(ts); if(!d) return "—";
    const s = Math.max(0, Math.floor((Date.now()-d.getTime())/1000));
    if(s<60) return "hace "+s+"s";
    if(s<3600) return "hace "+Math.floor(s/60)+"m";
    if(s<86400) return "hace "+Math.floor(s/3600)+"h";
    return "hace "+Math.floor(s/86400)+"d";
  },
  n: (x, d=0) => (x==null?"—":Number(x).toLocaleString("es", {maximumFractionDigits:d})),
};

function avatarColor(id){ const h=([...String(id)].reduce((a,c)=>a+c.charCodeAt(0),0))%360; return `hsl(${h} 55% 45%)`; }
function avatarText(name){ return (name||"?").split(" ").map(w=>w[0]).join("").slice(0,2).toUpperCase(); }
const PLAT_ICON = {
  ios:     reicon("mobile"),
  android: reicon("devices"),
  windows: reicon("cpu"),
  macos:   reicon("laptop-download"),
  chromeos:reicon("globe"),
};
function platformIcon(p){
  p=(p||"").toLowerCase();
  for(const k in PLAT_ICON) if(p.includes(k)) return PLAT_ICON[k];
  return reicon("devices");
}
function hydrateReicons(root=document){
  root.querySelectorAll("[data-reicon]:not([data-reicon-ready])").forEach(node=>{
    node.innerHTML = reicon(node.dataset.reicon, {size:Number(node.dataset.size||16)});
    node.dataset.reiconReady = "1";
  });
}

/* ---------- toasts ---------- */
function toast(title, sub, kind="info"){
  const t = el("div", "toast "+kind);
  t.innerHTML = `<b>${esc(title)}</b>${sub?`<small>${esc(sub)}</small>`:""}`;
  $("#toasts").appendChild(t);
  setTimeout(()=>{ t.style.opacity="0"; t.style.transform="translateX(20px)"; setTimeout(()=>t.remove(),200); }, 3600);
}

/* ---------- API ---------- */
async function api(path, opts={}){
  const r = await fetch(path, opts);
  if(r.status === 401){
    // Sin sesión (o expiró). Mostramos el modal de login REAL del SaaS
    // multi-tenant en lugar de un auto-login demo: el backend gestiona la
    // sesión vía cookie httpOnly y no exponemos contraseñas en el cliente.
    showAuthModal();
    throw new Error("no autenticado");
  }
  if(!r.ok){ const e=await r.json().catch(()=>({})); throw new Error(e.error||("HTTP "+r.status)); }
  return r.json();
}

/* ---------- autenticación SaaS real (multi-tenant, 100% local) ---------- */
// El backend ya setea la cookie de sesión (httpOnly) vía Set-Cookie en
// signup/login/logout; el navegador la envía solo (same-origin). Solo hacemos
// fetch. NUNCA guardamos ni hardcodeamos tokens/secrets en el cliente.
async function ensureAuth(){
  try{
    const me = await api("/api/auth/me");
    App.user = me.user; App.orgs = me.orgs||[];
    await refreshOrg();      // rellena App.org (nombre/plan) y la UI lateral
    updateUserUI();
    return true;
  }catch(e){
    showAuthModal();
    return false;
  }
}
async function refreshOrg(){
  try{ const o = await api("/api/org"); App.org = o; }catch(e){}
  if(App.org && App.org.org){
    $("#orgName").textContent = App.org.org.name||"";
    if(App.org.org.plan) $("#planPill").textContent = String(App.org.org.plan).toUpperCase();
  }
}
function updateUserUI(){
  const u = App.user; if(!u) return;
  const su = $("#sideUser"); if(su) su.style.display="flex";
  const av = $("#sideAv"); if(av) av.textContent = avatarText(u.email||u.name||"?");
  const em = $("#sideEmail"); if(em) em.textContent = u.email||"";
  const org = (App.org && App.org.org && App.org.org.name) || (App.orgs&&App.orgs[0]&&App.orgs[0].name) || "";
  const ro = $("#sideOrg"); if(ro) ro.textContent = org || "";
}
function showAuthModal(){
  const m = $("#authModal"), ov = $("#authOvl");
  if(!m) return;
  setAuthTab(App._authTab||"login");
  m.classList.add("show"); ov.classList.add("show");
  const e = $("#authEmail"); if(e) setTimeout(()=>e.focus(), 30);
}
function hideAuthModal(){
  const m = $("#authModal"), ov = $("#authOvl");
  if(m) m.classList.remove("show"); if(ov) ov.classList.remove("show");
  const res = $("#authResult"); if(res){ res.className="test-result"; res.textContent=""; }
}
function setAuthTab(tab){
  App._authTab = tab;
  $$("#authTabs button").forEach(b=>b.classList.toggle("active", b.dataset.t===tab));
  const orgField = $("#authOrgField"); if(orgField) orgField.style.display = tab==="signup"?"block":"none";
  const title = $("#authTitle"); if(title) title.textContent = tab==="signup"?"Crea tu organización":"Accede a LucidFence";
  const sub = $("#authSub"); if(sub) sub.textContent = tab==="signup"?"Registro rápido · 100% local":"Gestiona tu flota de forma segura";
  const btn = $("#authSubmit"); if(btn) btn.textContent = tab==="signup"?"Crear cuenta":"Entrar";
  const res = $("#authResult"); if(res){ res.className="test-result"; res.textContent=""; }
}
async function submitAuth(){
  const tab = App._authTab||"login";
  const email = ($("#authEmail").value||"").trim();
  const pass = ($("#authPass").value||"");
  const org = ($("#authOrg").value||"").trim();
  const res = $("#authResult");
  if(!email || !pass){ res.className="test-result bad show"; res.textContent="Email y contraseña son obligatorios."; return; }
  if(tab==="signup" && !org){ res.className="test-result bad show"; res.textContent="El nombre de la organización es obligatorio."; return; }
  const body = tab==="signup" ? {email, password:pass, org_name:org, name:email} : {email, password:pass};
  const btn = $("#authSubmit"); if(btn) btn.disabled=true;
  try{
    const r = await fetch("/api/auth/"+tab, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
    const data = await r.json().catch(()=>({}));
    if(!r.ok || !data.ok){
      res.className="test-result bad show"; res.textContent = data.error||("Error "+r.status); return;
    }
    App.user = data.user; App.orgs = data.orgs || (data.org?[data.org]:[]);
    await refreshOrg();
    updateUserUI();
    hideAuthModal();
    startApp();   // arranca/refresca el dashboard ya autenticado
    toast("Sesión iniciada", (App.org&&App.org.org&&App.org.org.name)||email, "ok");
  }catch(e){
    res.className="test-result bad show"; res.textContent = e.message||"No se pudo conectar";
  }finally{
    if(btn) btn.disabled=false;
  }
}
async function logout(){
  try{ await api("/api/auth/logout", {method:"POST"}); }catch(e){}
  App.user=null; App.orgs=null; App.org=null; App._riskMap=null; App._started=false;
  stopPolling();
  const su = $("#sideUser"); if(su) su.style.display="none";
  $("#orgName").textContent=""; $("#planPill").textContent="FREE";
  ["overview","map","devices","riesgo","inventory","ai","events","incidents","soar","actions","alerts","fences","routes","workflows","goals","settings"].forEach(v=>{ const n=$("#view-"+v); if(n) n.innerHTML=""; });
  showAuthModal();
}
function startApp(){
  renderNav();
  refresh(true).then(()=>{ goView(App.view||"overview"); App._started=true; startPolling(); }).catch(()=>{});
}
function startPolling(){ stopPolling(); App.pollTimer = setInterval(()=>refresh(false), 60000); }
function stopPolling(){ if(App.pollTimer){ clearInterval(App.pollTimer); App.pollTimer=null; } }

/* ---------- navegación (iconos reicon: github.com/dqev/reicon) ---------- */
const NAV = [
  {id:"overview",   label:"Resumen",     icon:"grid"},
  {id:"map",        label:"Mapa",        icon:"map"},
  {id:"devices",    label:"Dispositivos",icon:"devices"},
  {id:"inventory",  label:"Inventario",  icon:"box"},
  {id:"riesgo",     label:"Riesgo",       icon:"shield-alert"},
  {id:"ai",         label:"IA · MoA",    icon:"cpu"},
  {id:"events",     label:"Eventos",     icon:"calendar"},
  {id:"incidents",  label:"Incidentes",  icon:"alert-triangle2"},
  {id:"soar",       label:"SOAR · CVE",  icon:"shield-alert"},
  {id:"actions",    label:"Acciones",    icon:"bolt"},
  {id:"alerts",     label:"Alertas",     icon:"bell"},
  {id:"fences",     label:"Geovallas",   icon:"shield"},
  {id:"routes",     label:"Rutas",       icon:"route"},
  {id:"workflows",  label:"Workflows",   icon:"sitemap-4"},
  {id:"goals",      label:"Objetivos",   icon:"target"},
  {id:"settings",   label:"Ajustes",     icon:"settings"},
];

function renderNav(){
  const n = $("#nav"); n.innerHTML="";
  NAV.forEach(item=>{
    const a = el("a", App.view===item.id?"active":"");
    let badge="";
    if(item.id==="incidents" && App._openIncidents){
      badge = ` <span class="nav-badge">${App._openIncidents}</span>`;
    }
    const ic = reicon(item.icon, {size:18, className:"nav-ic"});
    a.innerHTML = `${ic}<span>${item.label}</span>${badge}`;
    a.onclick = ()=>goView(item.id);
    n.appendChild(a);
  });
}
function goView(id){
  App.view = id;
  renderNav();
  $$(".view").forEach(v=>v.classList.add("hidden"));
  const v = $("#view-"+id); v.classList.remove("hidden");
  const label = NAV.find(x=>x.id===id).label;
  $("#crumbC").textContent = label;
  if(id==="overview") renderOverview();
  if(id==="map") renderMapView();
  if(id==="devices") renderDevices();
  if(id==="inventory") renderInventory();
  if(id==="riesgo") renderRisk();
  if(id==="ai") renderAI();
  if(id==="events") renderEvents();
  if(id==="incidents") renderIncidents();
  if(id==="soar") renderSoar();
  if(id==="actions") renderActions();
  if(id==="alerts") renderAlerts();
  if(id==="fences") renderFences();
  if(id==="routes") renderRoutes();
  if(id==="workflows") renderWorkflows();
  if(id==="goals") renderGoals();
  if(id==="settings") renderSettings();
}

/* ---------- boot ---------- */
async function boot(){
  hydrateReicons();
  bindGlobal();
  const ok = await ensureAuth();   // decide login modal vs dashboard
  if(!ok){ return; }               // login modal visible; startApp() tras login
  startApp();
}
async function refresh(initial){
  const before = App.status;
  try{
    const [st, org] = await Promise.all([api("/api/status"), api("/api/org").catch(()=>null)]);
    App.status = st; App.org = org;
    // org llega como {org:{id,name,plan}, role, plan:<limits>}. El nombre real
    // está en org.org.name y el plan en org.org.plan (no en org.plan, que es un
    // dict de límites). Corregimos para no mostrar [object Object].
    if(org && org.org){
      $("#orgName").textContent = org.org.name||"";
      if(org.org.plan) $("#planPill").textContent = String(org.org.plan).toUpperCase();
    }
    updateSync(st, before);
    // pull open-incident count for the sidebar badge (best-effort)
    try{ const inc = await api("/api/incidents"); const open=(inc.incidents||[]).filter(i=>i.status!=="resolved").length; App._openIncidents = open||null; renderNav(); }catch(e){}
    // refresca el mapa de riesgo explicable (evidence gate) en segundo plano
    refreshRiskMap();
    // refresca la vista activa
    if(App.view==="overview") renderOverview();
    else if(App.view==="map") renderMapView();
    else if(App.view==="devices") renderDevices();
    else if(App.view==="inventory") renderInventory();
    else if(App.view==="riesgo") renderRisk();
    else if(App.view==="events") renderEvents();
    else if(App.view==="incidents") renderIncidents();
    else if(App.view==="soar") renderSoar();
    else if(App.view==="actions") renderActions();
    else if(App.view==="alerts") renderAlerts();
    else if(App.view==="fences") renderFences();
    else if(App.view==="routes") renderRoutes();
    else if(App.view==="workflows") renderWorkflows();
    else if(App.view==="goals") renderGoals();
    else if(App.view==="ai") loadAiProviders();
  }catch(e){ /* deja lo anterior */ }
}
function updateSync(st, before){
  const syncing = !before || (st && st.last_cycle_at && (!before.last_cycle_at || st.last_cycle_at>before.last_cycle_at));
  const se = $("#sync"); se.classList.remove("stale");
  if(st && st.last_cycle_at){
    const dt = parseTime(st.last_cycle_at);
    const age = dt ? Math.floor((Date.now()-dt.getTime())/1000) : 0;
    $("#syncText").textContent = "Ciclo hace "+fmt.ago(st.last_cycle_at);
    if(age>180) se.classList.add("stale");
  }
  $("#ratePill").textContent = (st&&st.cycle_period_s? Math.round(st.cycle_period_s/60)+" min" : "15 min");
  const mode = st&&st.mode? st.mode : (App.org && App.org.org ? "live":"simulation");
  $("#modeText").textContent = (st&&st.mode==="simulation")?"demo":(mode||"live");
  $("#modeText").style.color = (st&&st.mode==="simulation")?"var(--amber)":"var(--green)";
}

/* ============================================================
   RISK ENGINE EXPLICABLE (G2 — el moat del producto)
   Normaliza TANTO la forma especificada {risk_score, severity, reasons[],
   verified} como la forma real del product-layer {/api/risk -> risk:[{score,
   level, factors:[{label}], ...}]}. En ambos casos extrae reasons y verified.
   ============================================================ */
// Caché del último /api/risk (se actualiza en cada refresh y en el modal).
async function refreshRiskMap(){
  try{
    const data = await api("/api/risk");
    // product-layer devuelve {risk:[...]}; también toleramos {devices:[...]}
    const arr = data.risk || data.devices || (Array.isArray(data)? data : []);
    const map = {};
    (arr||[]).forEach(r=>{
      const id = r.device_id || r.id;
      if(!id) return;
      map[id] = normalizeRisk(r);
    });
    App._riskMap = map;
    // si la vista de riesgo o dispositivos está activa, repinta con reasons
    if(App.view==="riesgo") renderRisk();
    else if(App.view==="devices") renderDeviceRows();
  }catch(e){ /* best-effort: el score de /api/status sigue disponible */ }
}
function normalizeRisk(r){
  // reasons: nivel superior o derivado de factors[].label
  let reasons = Array.isArray(r.reasons) ? r.reasons : [];
  if(!reasons.length && Array.isArray(r.factors)) reasons = r.factors.map(f=>f.label||f).filter(Boolean);
  if(!reasons.length && Array.isArray(r.signals)) reasons = r.signals.map(s=>s.label||s).filter(Boolean);
  // verified: campo explícito, o deducido de "hay reasons => señal real"
  let verified = r.verified;
  if(verified===undefined) verified = reasons.length>0;
  const score = r.risk_score!=null ? r.risk_score : (r.score!=null ? r.score : 0);
  const severity = r.severity || r.level || sevFromScore(score);
  return { score, severity, reasons, verified, signals: r.signals||{} };
}
function sevFromScore(s){ s=Number(s)||0; return s>=70?"critical":s>=40?"high":s>=20?"medium":"low"; }
function severityLabel(s){ return ({low:"Bajo",medium:"Medio",high:"Alto",critical:"Crítico"})[s]||"—"; }
function verifiedBadge(verified, opts={}){
  // verified=true => señal real (verde); false => sin señal / no verificado (ámbar)
  const cls = verified ? "in" : "unk";
  const txt = verified ? (opts.short?"✓ Verificado":"✓ Verificado (señal real)") : (opts.short?"⚠ No verif.":"⚠ Sin señal / no verificado");
  return `<span class="tag ${cls}" title="${verified?'Riesgo respaldado por señales reales (reasons no vacío)':'Sin señal que respalde el score'}"><span class="d"></span>${txt}</span>`;
}
function iosGeofenceBadge(d, opts={}){
  const g = d && d.geofence_compliance;
  if(!g || (g.platform||"").toLowerCase()!=="ios") return opts.empty ? `<span class="sub">—</span>` : "";
  const ok = g.compliant === true;
  const txt = ok ? "iOS geocerca OK" : "iOS fuera/no cumple";
  const title = [g.policy_name, g.state, g.evidence].filter(Boolean).join(" · ");
  return `<span class="tag ${ok?'in':'nocomp'}" title="${esc(title)}"><span class="d"></span>${txt}</span>`;
}
function reasonsSummary(risk, max=1){
  if(!risk || !risk.reasons || !risk.reasons.length) return '<span class="sub">sin razones registradas</span>';
  const items = risk.reasons.slice(0, max).map(x=>esc(x));
  return items.join(" · ");
}
function reasonsList(risk){
  if(!risk || !risk.reasons || !risk.reasons.length)
    return `<div class="sub">Este dispositivo no tiene señales de riesgo activas.</div>`;
  return `<ul class="reasons">${risk.reasons.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`;
}

/* ============================================================
   VISTA: RIESGO (G2c) — lista de dispositivos por risk_score + reasons
   ============================================================ */
async function renderRisk(){
  const node = $("#view-riesgo"); if(!node) return;
  let devs = (App.status && App.status.devices) || [];
  // construye filas combinando status + risk explicable
  let rows = devs.map(d=>{
    const risk = (App._riskMap && App._riskMap[d.device_id]) || normalizeRisk({score: d.risk_score||0, reasons:[], verified:false});
    return { d, risk };
  }).sort((a,b)=> (b.risk.score||0) - (a.risk.score||0));
  const hi = rows.filter(r=>r.risk.score>=70).length;
  node.innerHTML = `
    <div class="view-head">
      <div><h2>Motor de Riesgo Explicable</h2>
        <div class="sub">Cada score lleva su justificación (reasons) y un sello de verificación (señal real vs. sin señal). Nada de "caja negra".</div></div>
      <div class="acts"><span class="tag ${hi?'nocomp':'in'}"><span class="d"></span>${hi} dispositivos en riesgo alto</span></div>
    </div>
    <div class="card"><div class="hd"><h3>Dispositivos por nivel de riesgo</h3><div class="grow"></div>
      <span class="sub">ordenados de mayor a menor score</span></div>
      <div class="bd"><div class="alist" id="riskList"></div></div></div>`;
  const list = $("#riskList");
  if(!rows.length){ list.innerHTML = emptyState("Sin dispositivos", "No hay datos de flota para evaluar."); return; }
  rows.forEach(({d, risk})=>{
    const item = el("div", "aitem");
    item.style.cursor = "pointer";
    const sc = risk.score!=null ? Math.round(risk.score) : "—";
    const sevCls = risk.score>=70?"bad":risk.score>=40?"warn":"ok";
    item.innerHTML = `
      <div class="ic" style="color:var(--${sevCls==='bad'?'red':sevCls==='warn'?'amber':'green'})">${platformIcon(d.platform)}</div>
      <div class="grow"><div class="nm">${esc(d.name||d.device_id)}</div>
        <div class="ds">${risk.reasons.length? esc(risk.reasons[0]) + (risk.reasons.length>1?` · +${risk.reasons.length-1} más`:"") : "sin señales"}</div></div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
        ${verifiedBadge(risk.verified, {short:true})}
        <span class="kpi ${sevCls}" style="padding:2px 10px;min-width:64px;text-align:center"><b style="font-size:15px">${sc}</b> <small style="color:var(--muted)">${esc(severityLabel(risk.severity))}</small></span>
      </div>
      <span class="act" title="Abrir detalle" onclick="openDeviceModal('${esc(d.device_id)}')">${I.bolt}</span>`;
    item.onclick = ()=>openDeviceModal(d.device_id);
    list.appendChild(item);
  });
}

window.addEventListener("DOMContentLoaded", boot);

/* ============================================================
   VISTA: RESUMEN (overview)
   ============================================================ */
function kpiCard(label, val, cls, icon, delta){
  return `<div class="kpi ${cls}">
    <div class="ic">${icon}</div>
    <div class="lab">${label}</div>
    <div class="val">${val}</div>
    ${delta?`<div class="bot">${delta}</div>`:""}
  </div>`;
}
const I = {
  dev:   reicon("devices"),
  in:    reicon("check-circle"),
  out:   reicon("x-circle"),
  alert: reicon("alert-triangle2"),
  shield:reicon("shield"),
  shieldAlert: reicon("shield-alert"),
  sitemap: reicon("sitemap-4"),
  route: reicon("route"),
  bolt:  reicon("bolt"),
  act:   reicon("bolt"),
  lock:  reicon("lock-keyhole"),
  bell:  reicon("bell"),
  trash: reicon("trash"),
};
function renderOverview(){
  const st = App.status; if(!st) return;
  const devs = st.devices||[];
  const inside = st.inside_count||0, outside = st.outside_count||0, unknown = st.unknown_count||0;
  const noncomp = st.noncompliant||0;
  const iosGeo = st.ios_geofence_summary || {};
  const total = devs.length || (inside+outside+unknown) || 1;
  const compPct = Math.round((total-noncomp)/total*100);
  const events = st.recent_events||[];
  const actions = st.recent_actions||[];
  const routes = st.routes||[];
  const fences = st.fences||[];

  $("#view-overview").innerHTML = `
    <div class="kpis">
      ${kpiCard("Dispositivos", devs.length||total, "acc", I.dev)}
      ${kpiCard("Dentro", inside, "ok", I.in)}
      ${kpiCard("Fuera", outside, "warn", I.out)}
      ${kpiCard("Desconocidos", unknown, "warn", I.out)}
      ${kpiCard("Incumplimiento", noncomp, noncomp?"bad":"ok", I.shield)}
      ${kpiCard("Eventos", (st.events_this_cycle||events.length||0), "acc", I.alert)}
      ${kpiCard("Acciones", (st.actions_this_cycle||actions.length||0), "acc", I.act)}
      ${kpiCard("Apps CVE", (st.cve_summary?.vulnerable_apps||0), (st.cve_summary?.critical_cve_apps||0)?"bad":"ok", I.shield)}
      ${kpiCard("CVE críticos", (st.cve_summary?.critical_cve_apps||0), (st.cve_summary?.critical_cve_apps||0)?"bad":"ok", I.alert)}
      ${kpiCard("iOS geocerca", (iosGeo.total?`${iosGeo.compliant}/${iosGeo.total}`:"0"), (iosGeo.noncompliant||0)?"bad":"ok", I.shield)}
    </div>
    <div class="grid-main">
      <div class="card">
        <div class="hd"><h3>Mapa de flota en vivo</h3><div class="grow"></div>
          <span class="tag ${inside>=outside?'in':'out'}"><span class="d"></span>${inside} dentro · ${outside} fuera</span></div>
        <div class="map-wrap"><div id="map"></div>
          <div class="map-legend"><div class="it"><span class="sw" style="background:var(--green)"></span>Dentro</div>
            <div class="it"><span class="sw" style="background:var(--blue)"></span>Fuera</div>
            <div class="it"><span class="sw" style="background:var(--amber)"></span>Desconocido</div></div>
        </div>
      </div>
      <div class="card">
        <div class="hd"><h3>Conformidad</h3><div class="grow"></div><span class="sub">${compPct}%</span></div>
        <div class="bd">
          <div class="donut-wrap">
            <div class="donut" id="compDonut" style="width:122px;height:122px"></div>
            <div class="legend-col">
              <div class="row"><span class="sw" style="background:var(--green)"></span>Conformes<b>${total-noncomp}</b></div>
              <div class="row"><span class="sw" style="background:var(--red)"></span>Incumplen<b>${noncomp}</b></div>
              <div class="row"><span class="sw" style="background:var(--blue)"></span>En geovallas<b>${inside}</b></div>
              <div class="row"><span class="sw" style="background:var(--amber)"></span>Sin señal<b>${unknown}</b></div>
            </div>
          </div>
          <div style="margin-top:18px"><canvas id="complianceChart"></canvas></div>
        </div>
      </div>
    </div>
    <div class="grid-main" style="margin-top:14px">
      <div class="card">
        <div class="hd"><h3>Actividad reciente</h3><div class="grow"></div><span class="link" onclick="goView('events')">Ver todo</span></div>
        <div class="tl" id="ovEvents"></div>
      </div>
      <div class="card">
        <div class="hd"><h3>Resumen de operación</h3></div>
        <div class="bd">
          <div class="alist">
            <div class="aitem"><div class="ic">${I.route}</div><div class="grow"><div class="nm">Rutas geocercadas</div><div class="ds">${routes.length} rutas · ${fences.length} geovallas</div></div><span class="mono">${routes.length}</span></div>
            <div class="aitem"><div class="ic">${I.bolt}</div><div class="grow"><div class="nm">Acciones ejecutadas</div><div class="ds">Ciclo actual</div></div><span class="mono">${st.actions_this_cycle||0}</span></div>
            <div class="aitem"><div class="ic">${I.shield}</div><div class="grow"><div class="nm">Conformidad global</div><div class="ds">Dispositivos conformes</div></div><span class="mono">${compPct}%</span></div>
            <div class="aitem"><div class="ic">${I.dev}</div><div class="grow"><div class="nm">Fuente de datos</div><div class="ds">${st.mode==="simulation"?"Simulación local":"Applivery UEM (live)"}</div></div><span class="tag ${st.mode==="simulation"?"unk":"in"}"><span class="d"></span>${st.mode==="simulation"?"demo":"live"}</span></div>
          </div>
          <button class="btn primary" style="width:100%;margin-top:14px;justify-content:center" onclick="openAiFromOverview()">${I.bolt} Pregunta a la IA sobre tu flota</button>
        </div>
      </div>
    </div>`;
  renderDonut($("#compDonut"), compPct, total-noncomp, total);
  renderComplianceChart(st);
  renderEventList($("#ovEvents"), events.slice(0,8));
  initMap(devs);
}
function openAiFromOverview(){ goView("ai"); }

function renderDonut(node, pct, fg, total){
  if(!node) return;
  const r=50, c=2*Math.PI*r, off=c*(1-pct/100);
  const lab = pct>=95?"OK":pct>=70?"Atención":"Riesgo";
  node.innerHTML = `<svg width="122" height="122" viewBox="0 0 122 122">
    <circle cx="61" cy="61" r="${r}" fill="none" stroke="var(--panel-3)" stroke-width="12"/>
    <circle cx="61" cy="61" r="${r}" fill="none" stroke="var(--green)" stroke-width="12" stroke-linecap="round"
      stroke-dasharray="${c}" stroke-dashoffset="${off}" transform="rotate(-90 61 61)"/>
  </svg><div class="center"><div class="big">${pct}%</div><div class="lab">${lab}</div></div>`;
}
function renderComplianceChart(st){
  const cv = $("#complianceChart"); if(!cv) return;
  const sh = st.stats_history||[];
  let data=[], labels=[];
  if(sh.length){
    // porcentaje de conformidad por ciclo = (total - non_compliant)/total*100
    sh.forEach((h,i)=>{
      const tot = h.devices_total||h.inside+h.outside+h.unknown||1;
      const nc = h.non_compliant||0;
      data.push(Math.round((tot-nc)/tot*100));
      labels.push(i+1);
    });
    if(data.length>24){ const k=Math.ceil(data.length/24); data=data.filter((_,i)=>i%k===0); labels=labels.filter((_,i)=>i%k===0); }
  } else {
    const series = (st.analytics&&st.analytics.compliance_series) || [];
    data = series.length? series.slice(-24) : [st.compliance_percent||0];
    labels = data.map((_,i)=>i+1);
  }
  if(App.complianceChart) App.complianceChart.destroy();
  App.complianceChart = new Chart(cv, {
    type:"line",
    data:{ labels, datasets:[{ data, borderColor:"#5e6ad5", backgroundColor:"rgba(94,106,213,.12)",
      borderWidth:2, fill:true, tension:.35, pointRadius:0 }]},
    options:{ responsive:true, plugins:{legend:{display:false}},
      scales:{ x:{display:false}, y:{min:0,max:100,grid:{color:"rgba(148,163,184,.08)"},ticks:{color:"var(--muted-2)",font:{size:9}}} },
      elements:{line:{borderJoinStyle:"round"}} }
  });
}

/* ---------- Event list renderer ---------- */
function evIcon(kind){
  if(kind==="enter") return I.in;
  if(kind==="exit") return I.out;
  if(kind==="action") return I.act;
  return I.alert;
}
function renderEventList(node, events){
  if(!node) return;
  if(!events || !events.length){ node.innerHTML = emptyState("Sin eventos recientes", "La actividad aparecerá aquí conforme la flota se mueva."); return; }
  node.innerHTML="";
  events.forEach(e=>{
    const d = el("div", "ev "+(e.kind||""));
    d.innerHTML = `<div class="ic">${evIcon(e.kind)}</div>
      <div class="body"><div class="t">${esc(e.text||e.msg||e.title||"Evento")}</div>
      ${e.device_name?`<div class="d">${esc(e.device_name)}</div>`:""}</div>
      <div class="time">${fmt.ago(e.ts)}</div>`;
    node.appendChild(d);
  });
}

/* ============================================================
   VISTA: MAPA
   ============================================================ */
function renderMapView(){
  const st = App.status; if(!st) return;
  $("#view-map").innerHTML = `
    <div class="toolbar"><div class="filters" id="mapFilters">
      <span class="chip active" data-f="all">Todos</span>
      <span class="chip" data-f="inside">Dentro</span>
      <span class="chip" data-f="outside">Fuera</span>
      <span class="chip" data-f="unknown">Desconocidos</span>
    </div><div class="grow"></div>
      <button class="btn sm" onclick="recenterMap()">Centrar</button></div>
    <div class="card"><div class="map-wrap"><div id="map"></div>
      <div class="map-legend"><div class="it"><span class="sw" style="background:var(--green)"></span>Dentro</div>
      <div class="it"><span class="sw" style="background:var(--blue)"></span>Fuera</div>
      <div class="it"><span class="sw" style="background:var(--amber)"></span>Desconocido</div></div></div></div>`;
  $$("#mapFilters .chip").forEach(c=>c.onclick=()=>{
    $$("#mapFilters .chip").forEach(x=>x.classList.remove("active")); c.classList.add("active");
    drawMapMarkers(App.status.devices||[], c.dataset.f);
  });
  initMap(App.status.devices||[]);
}
function recenterMap(){ if(App.map) App.map.setView([40.42,-3.70], 6); }

/* ---------- MAP engine (Leaflet) ---------- */
function initMap(devs){
  if(typeof L === "undefined") return;
  const node = $("#map"); if(!node) return;
  if(!App.map){
    App.map = L.map(node, {zoomControl:true, attributionControl:false}).setView([40.42,-3.70], 6);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",{maxZoom:19}).addTo(App.map);
    App.trailLayer = L.layerGroup().addTo(App.map);
    setTimeout(()=>App.map.invalidateSize(), 60);
  }
  drawMapMarkers(devs, App.devFilter);
}
function drawMapMarkers(devs, filter){
  if(!App.map) return;
  Object.values(App.mapMarkers).forEach(m=>App.map.removeLayer(m)); App.mapMarkers={};
  App.trailLayer.clearLayers();
  const colorFor = (s)=> s==="inside"?"#4cc38a": s==="outside"?"#4ea7fc":"#f2c94c";
  (devs||[]).forEach(d=>{
    if(filter && filter!=="all" && (d.fence_state||"unknown")!==filter) return;
    const lat=d.lat, lng=d.lng; if(lat==null||lng==null) return;
    const col = colorFor(d.fence_state||"unknown");
    const m = L.circleMarker([lat,lng], {radius:7, color:col, weight:2, fillColor:col, fillOpacity:.8});
    m.bindPopup(`<b>${esc(d.name)}</b><br><span style="font-size:11px;color:#888">${esc(d.platform||"")} · ${(d.fence_state||"unknown")}</span>`);
    m.on("click", ()=>openDeviceModal(d.device_id));
    m.addTo(App.map); App.mapMarkers[d.device_id]=m;
    // trail
    const tr = (d.trail||[]).slice(-30);
    if(tr.length>1){
      L.polyline(tr.map(p=>[p.lat,p.lng]).filter(p=>p[0]&&p[1]), {color:col, weight:1.5, opacity:.4}).addTo(App.trailLayer);
    }
  });
}

/* ============================================================
   VISTA: DISPOSITIVOS (estilo Linear)
   ============================================================ */
function renderDevices(){
  const st = App.status; if(!st) return;
  let devs = st.devices||[];
  $("#view-devices").innerHTML = `
    <div class="toolbar">
      <div class="filters" id="devFilters">
        <span class="chip active" data-f="all">Todos</span>
        <span class="chip" data-f="inside">Dentro</span>
        <span class="chip" data-f="outside">Fuera</span>
        <span class="chip" data-f="unknown">Desconocidos</span>
        <span class="chip" data-f="noncompliant">Incumplen</span>
      </div>
      <input class="search" id="devSearch" placeholder="Buscar dispositivo…"/>
    </div>
    <div class="card"><table class="tt"><thead><tr>
      <th class="sort" data-s="name">Dispositivo</th><th class="sort" data-s="platform">Plataforma</th>
      <th class="sort" data-s="fence_state">Estado</th><th class="sort" data-s="compliant">Conformidad</th><th>iOS geocerca</th>
      <th>Ubicación</th><th class="sort" data-s="last_seen">Visto</th><th>Verif.</th><th></th>
    </tr></thead><tbody id="devBody"></tbody></table></div>`;
  $$("#devFilters .chip").forEach(c=>c.onclick=()=>{
    $$("#devFilters .chip").forEach(x=>x.classList.remove("active")); c.classList.add("active");
    App.devFilter=c.dataset.f; renderDeviceRows();
  });
  $("#devSearch").oninput = (e)=>{ App.devSearch=e.target.value; renderDeviceRows(); };
  $$(".tt thead .sort").forEach(h=>h.onclick=()=>{
    App.devSort = h.dataset.s; renderDeviceRows();
  });
  renderDeviceRows();
}
function renderDeviceRows(){
  const st = App.status; if(!st) return;
  let devs = (st.devices||[]).filter(d=>{
    if(App.devFilter==="noncompliant") return d.compliant===false;
    if(App.devFilter!=="all" && (d.fence_state||"unknown")!==App.devFilter) return false;
    if(App.devSearch){ const q=App.devSearch.toLowerCase(); if(!((d.name||"")+ (d.platform||"")+(d.device_id||"")).toLowerCase().includes(q)) return false; }
    return true;
  });
  const sorters = {
    name:(a,b)=>(a.name||"").localeCompare(b.name||""),
    platform:(a,b)=>(a.platform||"").localeCompare(b.platform||""),
    fence_state:(a,b)=>(a.fence_state||"").localeCompare(b.fence_state||""),
    compliant:(a,b)=>((b.compliant===true)-(a.compliant===true)),
    last_seen:(a,b)=>((parseTime(b.last_seen)?.getTime()||0)-(parseTime(a.last_seen)?.getTime()||0)),
  };
  devs.sort(sorters[App.devSort]||sorters.name);
  const tb = $("#devBody");
  if(!devs.length){ tb.innerHTML = `<tr><td colspan="9">${emptyState("Sin dispositivos","No hay dispositivos para este filtro.")}</td></tr>`; return; }
  tb.innerHTML="";
  devs.forEach(d=>{
    const state = d.fence_state||"unknown";
    const tagCls = state==="inside"?"in":state==="outside"?"out":"unk";
    const compPct = d.compliance_pct!=null? d.compliance_pct : (d.compliant===false?0:100);
    const cbCls = compPct<40?"low":compPct<75?"mid":"";
    // G2b: risk explicable a nivel de fila
    const risk = (App._riskMap && App._riskMap[d.device_id]) || null;
    const verifiedCell = risk
      ? `<span title="${risk.reasons && risk.reasons.length ? esc(risk.reasons.join(' · ')) : 'sin señales'}" style="cursor:help">${verifiedBadge(risk.verified, {short:true})}</span>`
      : `<span class="sub" title="score de /api/status (sin reasons)">—</span>`;
    const tr = el("tr");
    tr.innerHTML = `
      <td><div class="dev"><div class="av" style="background:${avatarColor(d.device_id)}">${avatarText(d.name)}</div>
        <div style="min-width:0"><div class="nm">${esc(d.name||d.device_id)}</div>
        <div class="sub">${esc(d.device_id)}</div></div></div></td>
      <td><span class="plat">${platformIcon(d.platform)} ${esc(d.platform||"—")}</span></td>
      <td><span class="tag ${tagCls}"><span class="d"></span>${state==="inside"?"Dentro":state==="outside"?"Fuera":"Desconocido"}</span></td>
      <td>${d.compliant===false?`<span class="tag nocomp"><span class="d"></span>Incumple</span>`:`<div style="display:flex;align-items:center;gap:8px"><div class="cbar ${cbCls}"><i style="width:${compPct}%"></i></div><span class="mono">${compPct}%</span></div>`}</td>
      <td>${iosGeofenceBadge(d, {empty:true})}</td>
      <td class="mono">${esc(d.city||d.country|| (d.lat!=null?d.lat.toFixed(2)+","+d.lng.toFixed(2):"—"))}</td>
      <td class="mono">${fmt.ago(d.last_seen)}</td>
      <td>${verifiedCell}</td>
      <td><span class="plat" style="cursor:pointer" onclick="openDeviceModal('${esc(d.device_id)}')">${I.act}</span></td>`;
    tr.onclick = ()=>openDeviceModal(d.device_id);
    tb.appendChild(tr);
  });
}

/* ---------- device modal ---------- */
async function openDeviceModal(id){
  const d = (App.status.devices||[]).find(x=>x.device_id===id);
  if(!d) return;
  $("#mAv").textContent = avatarText(d.name); $("#mAv").style.background = avatarColor(d.device_id);
  $("#mName").textContent = d.name||d.device_id;
  $("#mId").textContent = d.device_id + (d.source? " · "+d.source : "");
  const state = d.fence_state||"unknown";
  $("#mTag").innerHTML = `<span class="tag ${state==="inside"?"in":state==="outside"?"out":"unk"}"><span class="d"></span>${state}</span>`;
  const rows = [
    ["Plataforma", d.platform||"—"], ["Estado geovalla", state],
    ["Conformidad", d.compliant===false?"Incumple":(d.compliance_pct!=null?d.compliance_pct+"%":"OK")],
    ["Cumplimiento iOS geocerca", d.geofence_compliance ? ((d.geofence_compliance.compliant?"OK":"Incumple") + " · " + (d.geofence_compliance.policy_name||"política iOS")) : "—"],
    ["Ubicación", d.lat!=null? `${d.lat.toFixed(4)}, ${d.lng.toFixed(4)}`:"—"],
    ["Ciudad / País", (d.city||"—")+" / "+(d.country||"—")],
    ["IP", d.ip||"—"], ["Fuente", d.location_source||d.source||"—"],
    ["Visto", fmt.date(d.last_seen)],
  ];
  $("#mKv").innerHTML = rows.map(r=>`<div class="k">${esc(r[0])}</div><div class="v">${esc(r[1])}</div>`).join("");
  // ---- G2a: Risk Engine explicable (reasons + verified) ----
  const mRisk = $("#mRisk");
  if(mRisk){
    // El score de riesgo compuesto ya viene en /api/status (d.risk_score).
    // El detalle explicable (reasons + verified) vive en App._riskMap, que se
    // llena con /api/risk en cada refresh (refreshRiskMap). Lo usamos y, si no
    // está aún disponible, hacemos un fetch puntual del bundle global.
    const renderRiskBlock = (rk)=>{
      mRisk.innerHTML = `
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
          ${verifiedBadge(rk.verified)}
          <span class="kpi ${rk.score>=70?'bad':rk.score>=40?'warn':'ok'}" style="padding:3px 12px">
            <b style="font-size:16px">${Math.round(rk.score)}</b> <small style="color:var(--muted)">${esc(severityLabel(rk.severity))}</small>
          </span>
          <span class="sub">score de riesgo compuesto</span>
        </div>
        <div style="margin-top:10px;font-size:11px;color:var(--muted-2);text-transform:uppercase;letter-spacing:.05em;font-weight:600">¿Por qué este riesgo?</div>
        <div id="mReasons" style="margin-top:6px">${reasonsList(rk)}</div>`;
    };
    const fromStatus = (App._riskMap && App._riskMap[id]) || normalizeRisk({score: d.risk_score||0, severity: d.risk_severity});
    renderRiskBlock(fromStatus);
    if(!(App._riskMap && App._riskMap[id])){
      // fetch puntual del bundle global para rellenar reasons/verified
      api("/api/risk").then(data=>{
        const arr = data.risk || data.devices || [];
        const hit = (arr||[]).find(x=> (x.device_id||x.id)===id);
        if(hit && App.view) renderRiskBlock(normalizeRisk(hit));
      }).catch(()=>{});
    }
  }
  // apps installed + CVE risk
  const mApps = $("#mApps");
  if(mApps){
    const apps = (d.apps||[]);
    if(!apps.length){ mApps.innerHTML = `<div class="sub">Sin datos de apps instaladas.</div>`; }
    else {
      mApps.innerHTML = apps.map(a=>{
        const sev = a.max_cve_severity;
        const sevCls = sev==="critical"?"bad":sev==="high"?"warn":sev?"out":"ok";
        const cves = (a.cves||[]).map(c=>`<span class="tag ${sevCls}"><span class="d"></span>${esc(c.id)} · ${(c.severity||"").toUpperCase()}</span>`).join(" ") || `<span class="sub">sin CVE conocidos</span>`;
        return `<div class="app-row"><div class="app-h"><b>${esc(a.name)}</b> <span class="mono">v${esc(a.version||"?")}</span> ${sev?`<span class="tag ${sevCls}"><span class="d"></span>${sev.toUpperCase()}</span>`:""}</div><div class="app-cves">${cves}</div></div>`;
      }).join("");
    }
  }
  // trail map
  const trailNode = $("#mTrail"); trailNode.innerHTML="";
  try{
    const det = await api("/api/devices/"+encodeURIComponent(id));
    const tr = (det.trail||[]).slice(-40);
    if(tr.length>1 && typeof L!=="undefined"){
      const tm = L.map(trailNode, {zoomControl:false, attributionControl:false}).setView([tr[0].lat,tr[0].lng], 9);
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",{maxZoom:19}).addTo(tm);
      L.polyline(tr.map(p=>[p.lat,p.lng]).filter(p=>p.lat&&p.lng), {color:"#5e6ad5",weight:2}).addTo(tm);
      tr.forEach(p=>{ if(p.lat&&p.lng) L.circleMarker([p.lat,p.lng],{radius:3,color:"#5e6ad5",fillOpacity:.7}).addTo(tm); });
      setTimeout(()=>tm.invalidateSize(),40);
    }
    const evs = (det.events||[]).slice(-8).reverse();
    $("#mEvents").innerHTML = "";
    renderEventList($("#mEvents"), evs.map(e=>({...e, kind:e.kind||"info", text:e.text||e.msg})));
    // remote commands wiring
    $$("#mCmd [data-cmd]").forEach(btn=>{
      btn.onclick = async ()=>{
        const cmd = btn.dataset.cmd;
        if(cmd==="wipe" && !confirm("¿Seguro que quieres BORRAR (wipe) este dispositivo?")) return;
        if(cmd==="message"){
          const txt = prompt("Mensaje para el dispositivo:");
          if(!txt) return;
          await sendDeviceCommand(id, "message", {"message": txt});
        } else {
          await sendDeviceCommand(id, cmd, {});
        }
      };
    });
  }catch(e){ $("#mEvents").innerHTML = `<div class="sub">No se pudieron cargar detalles.</div>`; }
  $("#ovl").classList.add("show"); $("#devModal").classList.add("show");
  if(App.map) App.map.closePopup();
}
function closeModal(){ $("#ovl").classList.remove("show"); $("#devModal").classList.remove("show"); }
$("#mClose") && ($("#mClose").onclick = closeModal);
$("#ovl") && ($("#ovl").onclick = closeModal);

/* ============================================================
   VISTA: EVENTOS
   ============================================================ */
function renderEvents(){
  const st = App.status; if(!st) return;
  const events = st.recent_events||[];
  const counts = {enter:0,exit:0,action:0,unknown:0};
  events.forEach(e=>counts[e.kind||"unknown"]=(counts[e.kind||"unknown"]||0)+1);
  $("#view-events").innerHTML = `
    <div class="toolbar"><div class="filters" id="evFilters">
      <span class="chip active" data-f="all">Todos</span>
      <span class="chip" data-f="enter">Entradas</span>
      <span class="chip" data-f="exit">Salidas</span>
      <span class="chip" data-f="action">Acciones</span>
    </div></div>
    <div class="card"><div class="tl" id="evList"></div></div>`;
  let f="all";
  $$("#evFilters .chip").forEach(c=>c.onclick=()=>{
    $$("#evFilters .chip").forEach(x=>x.classList.remove("active")); c.classList.add("active"); f=c.dataset.f;
    renderEventList($("#evList"), (f==="all"?events:events.filter(e=>e.kind===f)));
  });
  renderEventList($("#evList"), events);
}

/* ============================================================
   VISTA: INCIDENTES — triage persistente (ack/assign/resolve/reopen)
   ============================================================ */
let incidentFilter = "active";
async function renderIncidents(){
  const node = $("#view-incidents"); if(!node) return;
  node.innerHTML = `<div class="toolbar"><div class="filters" id="incFilters">
      <span class="chip ${incidentFilter==='active'?'active':''}" data-f="active">Activos</span>
      <span class="chip ${incidentFilter==='open'?'active':''}" data-f="open">Abiertos</span>
      <span class="chip ${incidentFilter==='acknowledged'?'active':''}" data-f="acknowledged">En investigación</span>
      <span class="chip ${incidentFilter==='resolved'?'active':''}" data-f="resolved">Resueltos</span>
      <span class="chip ${incidentFilter==='all'?'active':''}" data-f="all">Todos</span>
    </div><div class="grow"></div><button class="btn sm" id="incReload">Actualizar</button><button class="btn sm sec" id="incExport">Exportar CSV</button></div>
    <div class="grid3" id="incStats" style="margin:10px 12px;display:none">
      <div class="kpi"><div class="k" id="kOpen">–</div><div class="l">Abiertos</div></div>
      <div class="kpi"><div class="k" id="kMttr">–</div><div class="l">MTTR (mediana)</div></div>
      <div class="kpi"><div class="k" id="kOldest">–</div><div class="l">Más antiguo abierto</div></div>
    </div>
    <div class="card"><div class="hd"><h3>Cola operativa de incidentes</h3><div class="grow"></div><span class="sub" id="incCount">cargando…</span></div>
      <div class="bd"><div class="alist" id="incList"><div class="sk" style="height:120px"></div></div></div></div>`;
  $$("#incFilters .chip").forEach(c=>c.onclick=()=>{ incidentFilter=c.dataset.f; renderIncidents(); });
  $("#incReload").onclick=()=>renderIncidents();
  $("#incExport").onclick=()=>{ window.location.href="/api/incidents/export?format=csv"; };
  try{
    const data = await api("/api/incidents");
    try{ const an = await api("/api/incidents/analytics");
      const a = an.analytics||{};
      $("#incStats").style.display="grid";
      $("#kOpen").textContent = a.open||0;
      $("#kMttr").textContent = a.mttr_median_seconds!=null ? fmtDur(a.mttr_median_seconds) : "–";
      $("#kOldest").textContent = a.oldest_open_seconds!=null ? fmtDur(a.oldest_open_seconds) : "–";
    }catch(e){}
    let rows = data.incidents||[];
    if(incidentFilter==="active") rows=rows.filter(i=>i.status!=="resolved");
    else if(incidentFilter!=="all") rows=rows.filter(i=>i.status===incidentFilter);
    // sidebar badge = open + acknowledged (operational backlog)
    const open = (data.incidents||[]).filter(i=>i.status!=="resolved").length;
    App._openIncidents = open || null;
    renderNav();
    $("#incCount").textContent = rows.length+" incidente(s)";
    const list=$("#incList");
    if(!rows.length){ list.innerHTML=emptyState("Sin incidentes en esta cola","Los hallazgos del motor de riesgo aparecerán aquí."); return; }
    list.innerHTML="";
    rows.forEach(inc=>{
      const item=el("div","aitem");
      const sev=inc.severity||"medium", status=inc.status||"open";
      const statusLabel=status==="acknowledged"?"Investigando":status==="resolved"?"Resuelto":"Abierto";
      const statusCls=status==="resolved"?"in":status==="acknowledged"?"out":"nocomp";
      const sevIcon = reicon(sev==='critical'?'fire2':sev==='high'?'alert-circle2':sev==='low'?'info-circle':'shield-alert', {size:18});
      item.innerHTML=`<div class="ic" style="color:${sev==='critical'||sev==='high'?'var(--red)':'var(--amber)'}">${sevIcon}</div>
        <div class="grow"><div class="nm">${esc(inc.title||inc.id)}</div>
          <div class="ds">${esc(inc.device_name||inc.device_id||"—")} · ${esc(sev)} · ${fmt.ago(inc.last_seen)}${inc.assignee?" · asignado a "+esc(inc.assignee):""}</div>
          ${inc.recommendation?`<div class="ds" style="margin-top:4px">${esc(inc.recommendation)}</div>`:""}</div>
        <span class="tag ${statusCls}"><span class="d"></span>${statusLabel}</span>
        <div style="display:flex;gap:6px;margin-left:8px">
          ${status==="open"?'<button class="btn sm" data-act="ack">Reconocer</button>':""}
          ${status!=="resolved"?'<button class="btn sm" data-act="resolve">Resolver</button>':'<button class="btn sm" data-act="reopen">Reabrir</button>'}
        </div>`;
      const ack=$("[data-act='ack']",item), resolve=$("[data-act='resolve']",item), reopen=$("[data-act='reopen']",item);
      if(ack) ack.onclick=()=>transitionIncident(inc.id,"acknowledged",true);
      if(resolve) resolve.onclick=()=>transitionIncident(inc.id,"resolved",false);
      if(reopen) reopen.onclick=()=>transitionIncident(inc.id,"open",false);
      list.appendChild(item);
    });
  }catch(e){ $("#incList").innerHTML=emptyState("No se pudo cargar la cola",e.message); }
}
async function transitionIncident(id,status,askAssignee){
  const note=window.prompt("Nota de operación (opcional)","")||"";
  let assignee;
  if(askAssignee) assignee=window.prompt("Asignar a (email/equipo, opcional)","")||"";
  try{
    await api("/api/incidents/"+encodeURIComponent(id)+"/transition", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({status,note,assignee})});
    toast("Incidente actualizado",status,"ok"); renderIncidents();
  }catch(e){ toast("No se pudo actualizar",e.message,"bad"); }
}

/* ============================================================
   VISTA: ACCIONES
   ============================================================ */
function renderSoar(){
  const node = $("#view-soar");
  node.innerHTML = `<div class="card"><div class="hd"><h3>${I.shieldAlert} SOAR &middot; Postura CVE</h3>
      <div class="grow"></div><span class="sub">Orquestación y respuesta automática</span></div>
    <div id="soarKpis" class="kpis"></div>
    <div id="soarBody"><div class="loading">Cargando playbooks y postura CVE…</div></div></div>`;
  loadSoar();
}
async function loadSoar(st){
  let soar={playbooks:[],matched:[],devices_scanned:0}, cve={cve_summary:{},devices:[]};
  try{ soar = await api("/api/soar"); }catch(e){}
  try{ cve = await api("/api/cve"); }catch(e){}
  const s = cve.cve_summary||{};
  $("#soarKpis").innerHTML =
      kpiCard("Apps escaneadas", s.apps_total||0, "ok", I.dev)
    + kpiCard("Apps vulnerables", s.vulnerable_apps||0, (s.vulnerable_apps||0)?"bad":"ok", I.alert)
    + kpiCard("CVE críticos", s.critical_cve_apps||0, (s.critical_cve_apps||0)?"bad":"ok", I.shieldAlert)
    + kpiCard("CVE altos", s.high_cve_apps||0, (s.high_cve_apps||0)?"bad":"ok", I.bell);

  const pbs = (soar.playbooks||[]).map(p=>{
    const fired = (soar.matched||[]).filter(m=>m.playbook_id===p.id).length;
    const acts = (p.actions||[]).map(a=>`<span class="chip">${esc(a.action)}</span>`).join(" ");
    return `<div class="soar-pb">
      <div class="soar-pb-h"><b>${esc(p.name)}</b> ${p.enabled?`<span class="tag ok">activo</span>`:`<span class="tag">inactivo</span>`} ${fired?`<span class="nav-badge">${fired}</span>`:""}</div>
      <div class="sub">${esc(p.description||"")}</div>
      <div class="soar-acts">${acts||"<span class='sub'>sin acciones</span>"}</div>
    </div>`;
  }).join("");

  const hits = (soar.matched||[]).map(m=>{
    const acts = (m.actions||[]).map(a=>`<span class="chip">${esc(a.action)}</span>`).join(" ");
    const sev = (m.severity||"low");
    return `<div class="ev soar-hit sev-${sev}">
      <div class="ic">${I.shieldAlert}</div>
      <div class="body"><div class="t">${esc(m.name)}</div>
      <div class="d">${esc(m.device_name||m.device_id)} · severidad ${esc(sev)}</div>
      <div class="soar-acts">${acts}</div></div>
    </div>`;
  }).join("");

  const devRows = (cve.devices||[]).filter(d=>(d.apps||[]).some(a=>a.cves)).map(d=>{
    const rows = (d.apps||[]).filter(a=>a.cves).map(a=>{
      const sevs = (a.cves||[]).map(c=>`<span class="tag ${sevCls(c.severity)}">${esc(c.id)} · ${esc((c.severity||"").toUpperCase())}</span>`).join(" ");
      return `<div class="app-row"><b>${esc(a.name)}</b> v${esc(a.version||"?")}<div class="app-cves">${sevs}</div></div>`;
    }).join("");
    return `<div class="soar-dev"><div class="hd"><b>${esc(d.name)}</b></div>${rows}</div>`;
  }).join("");

  $("#soarBody").innerHTML = `
    <div class="soar-grid">
      <div class="card"><div class="hd"><h3>${I.sitemap} Playbooks SOAR</h3><div class="grow"></div>
        <span class="sub">${soar.devices_scanned||0} dispositivos evaluados</span></div>
        <div class="soar-pbs">${pbs||"<div class='sub'>Sin playbooks</div>"}</div></div>
      <div class="card"><div class="hd"><h3>${I.bolt} Coincidencias activas</h3><div class="grow"></div>
        <span class="sub">${(soar.matched||[]).length} ejecuciones este ciclo</span></div>
        <div class="tl">${hits||emptyState("Sin coincidencias","Ningún playbook coincide con el estado actual de la flota.")}</div></div>
    </div>
    <div class="card" style="margin-top:14px"><div class="hd"><h3>${I.shieldAlert} Inventario CVE por dispositivo</h3><div class="grow"></div>
      <span class="sub">${ (cve.devices||[]).filter(d=>(d.apps||[]).some(a=>a.cves)).length } dispositivos con apps vulnerables</span></div>
      <div class="soar-devs">${devRows||"<div class='sub'>Sin apps vulnerables detectadas</div>"}</div></div>`;
}
function sevCls(sev){
  sev=(sev||"").toLowerCase();
  return sev==="critical"?"bad":sev==="high"?"warn":sev==="medium"?"info":"ok";
}

function renderActions(){
   const st = App.status; if(!st) return;
  const actions = st.recent_actions||[];
  $("#view-actions").innerHTML = `
    <div class="card"><div class="hd"><h3>Acciones de remediación</h3><div class="grow"></div>
      <span class="sub">${actions.length} ejecutadas</span></div>
      <div class="tl" id="actList"></div></div>`;
  const node = $("#actList");
  if(!actions.length){ node.innerHTML = emptyState("Sin acciones", "Las acciones automáticas aparecen aquí cuando un dispositivo viola una política."); return; }
  actions.slice().reverse().forEach(a=>{
    const d = el("div", "ev action");
    const stTxt = a.result==="ok"?"OK": a.result==="delegated"?"Delegada (webhook)": a.result||"—";
    d.innerHTML = `<div class="ic">${I.act}</div>
      <div class="body"><div class="t">${esc(a.action||a.text||"Acción")}</div>
      <div class="d">${esc(a.device_name||"")} · ${esc(stTxt)}${a.webhook?` · ${esc(a.webhook)}`:""}</div></div>
      <div class="time">${fmt.ago(a.ts)}</div>`;
    node.appendChild(d);
  });
}

/* ============================================================
   VISTA: GEOVALLAS (fences) + crear
   ============================================================ */
function renderFences(){
  const st = App.status; if(!st) return;
  const fences = (st.fences||[]).map(f=>({...f, radius_m:f.radius_m||f.radius||500}));
  const routes = st.routes||[];
  $("#view-fences").innerHTML = `
    <div class="toolbar"><div class="grow"></div>
      <button class="btn primary" onclick="openFenceModal()">+ Nueva geovalla</button></div>
    <div class="grid-main">
      <div class="card"><div class="hd"><h3>Geovallas definidas</h3></div>
        <div class="bd"><div class="alist" id="fenceList"></div></div></div>
      <div class="card"><div class="hd"><h3>Rutas geocercadas</h3></div>
        <div class="bd"><div class="alist" id="routeMini"></div></div></div>
    </div>`;
  const fl = $("#fenceList");
  if(!fences.length) fl.innerHTML = emptyState("Sin geovallas", "Crea una zona para monitorizar entradas/salidas.");
  else fences.forEach(f=>{
    const it = el("div", "aitem");
    it.innerHTML = `<div class="ic" style="color:var(--accent)">${I.shield}</div>
      <div class="grow"><div class="nm">${esc(f.name)}</div><div class="ds">${esc(f.type||f.kind||"circle")} · ${f.radius_m} m</div></div>
      <span class="tag ${f.enabled!==false?'in':'unk'}"><span class="d"></span>${f.enabled!==false?'Activa':'Pausada'}</span>
      <span class="act" onclick="deleteFence('${esc(f.id)}')" title="Eliminar">${I.trash}</span>`;
    fl.appendChild(it);
  });
  const rm = $("#routeMini");
  if(!routes.length) rm.innerHTML = emptyState("Sin rutas", "Las rutas agrupan geovallas en un trayecto.");
  else routes.forEach(r=>{
    const it = el("div", "aitem");
    it.innerHTML = `<div class="ic">${I.route}</div>
      <div class="grow"><div class="nm">${esc(r.name)}</div><div class="ds">${r.fence_ids?r.fence_ids.length:0} paradas · ${r.device_ids?(r.device_ids.length+' disp.'):'toda la flota'}</div></div>`;
    rm.appendChild(it);
  });
}
function openFenceModal(){
  const body = `
    <div class="field"><label>Nombre</label><input class="input" id="fName" placeholder="Oficina central"/></div>
    <div class="field"><label>Latitud</label><input class="input" id="fLat" placeholder="40.4168"/></div>
    <div class="field"><label>Longitud</label><input class="input" id="fLng" placeholder="-3.7038"/></div>
    <div class="field"><label>Radio (m)</label><input class="input" id="fRad" value="500"/></div>
    <div class="field"><label>Dispositivos (vacío = todos)</label><input class="input" id="fDev" placeholder="dev1, dev2"/></div>
    <div id="fResult" class="test-result"></div>`;
  showModal("Nueva geovalla", null, body, async ()=>{
    const payload = {name:$("#fName").value, lat:parseFloat($("#fLat").value), lng:parseFloat($("#fLng").value),
      radius_m:parseInt($("#fRad").value)||500, devices:$("#fDev").value?$("#fDev").value.split(",").map(s=>s.trim()):[]};
    const r = await api("/api/fences", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
    if(r.ok){ toast("Geovalla creada", payload.name, "ok"); closeModal(); refresh(false); }
    else { $("#fResult").className="test-result bad show"; $("#fResult").textContent=r.error||"Error"; }
  });
}
async function deleteFence(id){
  if(!window.confirm("¿Eliminar esta geovalla? Las rutas existentes conservarán sus coordenadas.")) return;
  try{
    await api("/api/fences/"+encodeURIComponent(id), {method:"DELETE"});
    toast("Geovalla eliminada","","ok"); await refresh(false); renderFences();
  }catch(e){ toast("No se pudo eliminar",e.message,"bad"); }
}

/* ============================================================
   VISTA: RUTAS
   ============================================================ */
function renderRoutes(){
  const st = App.status; if(!st) return;
  const routes = st.routes||[];
  $("#view-routes").innerHTML = `
    <div class="toolbar"><div class="grow"></div>
      <button class="btn primary" onclick="openRouteModal()">+ Nueva ruta</button></div>
    <div class="card"><div class="tl" id="routeList"></div></div>`;
  const node = $("#routeList");
  if(!routes.length){ node.innerHTML = emptyState("Sin rutas", "Una ruta conecta varias geovallas en un orden de visita."); return; }
  routes.forEach(r=>{
    const d = el("div", "ev");
    d.innerHTML = `<div class="ic">${I.route}</div>
      <div class="body"><div class="t">${esc(r.name)}</div>
      <div class="d">${(r.waypoints||[]).length} puntos · ${r.device_ids&&r.device_ids.length?(r.device_ids.length+" dispositivos"):"toda la flota"} · corredor ${r.corridor_m||200} m · ventana ${(r.schedule&&r.schedule.start)||"--"}–${(r.schedule&&r.schedule.end)||"--"}</div></div>
      <div class="act" onclick="deleteRoute('${esc(r.id)}')">${I.trash}</div>`;
    node.appendChild(d);
  });
}
function openRouteModal(){
  const fences = (App.status.fences||[]).map(f=>`<option value="${esc(f.id)}">${esc(f.name)}</option>`).join("");
  const body = `
    <div class="field"><label>Nombre</label><input class="input" id="rName" placeholder="Ruta de reparto Madrid"/></div>
    <div class="field"><label>Geovallas (orden de visita)</label><select class="sel" id="rFences" multiple size="4">${fences}</select>
      <div class="help">Ctrl/Cmd+click para seleccionar varias.</div></div>
    <div class="field"><label>Corredor de tolerancia (m)</label><input class="input" id="rCorr" type="number" min="25" value="200"/></div>
    <div class="field"><label>Ventana horaria</label><div style="display:flex;gap:8px"><input class="input" id="rWs" placeholder="08:00"/><input class="input" id="rWe" placeholder="18:00"/></div></div>
    <div class="field"><label>Dispositivos (vacío = toda la flota)</label><input class="input" id="rDev" placeholder="dev1, dev2"/></div>`;
  showModal("Nueva ruta", null, body, async ()=>{
    const fs = $$("#rFences option").filter(o=>o.selected).map(o=>o.value);
    const payload = {name:$("#rName").value, fence_ids:fs, corridor_m:parseInt($("#rCorr").value)||200,
      window_start:$("#rWs").value, window_end:$("#rWe").value,
      device_ids:$("#rDev").value?$("#rDev").value.split(",").map(s=>s.trim()):[]};
    const r = await api("/api/routes", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
    if(r.ok){ toast("Ruta creada", payload.name, "ok"); closeModal(); refresh(false); }
    else { toast("Error", r.error||"", "bad"); }
  });
}
async function deleteRoute(id){
  const r = await api("/api/routes/"+encodeURIComponent(id)+"/delete", {method:"POST"});
  if(r.ok){ toast("Ruta eliminada","","ok"); refresh(false); }
}

/* ============================================================
   VISTA: WORKFLOWS
   ============================================================ */
async function renderWorkflows(){
  const st = App.status; if(!st) return;
  $("#view-workflows").innerHTML = `<div class="toolbar"><div class="grow"></div>
      <button class="btn primary" onclick="openWorkflowModal()">+ Nuevo workflow</button></div>
    <div class="grid-main">
      <div class="card"><div class="hd"><h3>Workflows activos</h3></div><div class="bd"><div class="alist" id="wfList"></div></div></div>
      <div class="card"><div class="hd"><h3>Plantillas</h3></div><div class="bd"><div class="alist" id="wfTpl"></div></div></div>
    </div>`;
  let tpl=[], active=[];
  try{
    const w = await api("/api/workflows");
    tpl = w.templates||[]; active = w.active||[];
    const triggers = w.triggers||[], actions = w.actions||[];
    window.__wf = {triggers, actions, templates:tpl};
  }catch(e){}
  const al = $("#wfList");
  if(!active.length) al.innerHTML = emptyState("Sin workflows", "Automatiza respuestas: al entrar/salir de una geovalla, ejecuta una acción.");
  else active.forEach(p=>{
    const it = el("div","aitem");
    it.innerHTML = `<div class="ic">${I.bolt}</div>
      <div class="grow"><div class="nm">${esc(p.name||"Policy")}</div><div class="ds">${esc((p.when||p.triggers||p.conditions||[]).length||0)} condiciones · ${esc((p.actions||[]).length||0)} acciones</div></div>
      <span class="tag in"><span class="d"></span>Activo</span>
      <span class="act" onclick="deleteWorkflow('${esc(p.id||"")}')">${I.trash}</span>`;
    al.appendChild(it);
  });
  const tp = $("#wfTpl");
  if(!tpl.length) tp.innerHTML = `<div class="sub">No hay plantillas disponibles.</div>`;
  else tpl.forEach(t=>{
    const it = el("div","aitem");
    it.innerHTML = `<div class="ic">${I.bolt}</div>
      <div class="grow"><div class="nm">${esc(t.name)}</div><div class="ds">${esc(t.summary||t.desc||"")}</div></div>
      <span class="link" onclick="applyTemplate('${esc(t.id)}')">Aplicar</span>`;
    tp.appendChild(it);
  });
}
async function applyTemplate(id){
  const r = await api("/api/workflows/apply", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({template_id:id})});
  if(r.ok){ toast("Workflow aplicado", "", "ok"); renderWorkflows(); }
  else toast("Error", r.error||"", "bad");
}
async function deleteWorkflow(id){
  if(!id) return;
  const r = await api("/api/workflows/"+encodeURIComponent(id)+"/delete", {method:"POST"});
  if(r.ok){ toast("Workflow eliminado","","ok"); renderWorkflows(); }
}
function openWorkflowModal(){
  const triggers = (window.__wf&&window.__wf.triggers)||[];
  const actions = (window.__wf&&window.__wf.actions)||[];
  const tOpts = triggers.map(t=>`<option value="${esc(t.value||t.id||t)}">${esc(t.label||t.value||t)}</option>`).join("");
  const aOpts = actions.map(a=>`<option value="${esc(a.value||a.id||a)}">${esc(a.label||a.value||a)}</option>`).join("");
  const body = `
    <div class="field"><label>Nombre</label><input class="input" id="wName" placeholder="Alertar si sale de ruta"/></div>
    <div class="field"><label>Disparador</label><select class="sel" id="wTrig">${tOpts}</select></div>
    <div class="field"><label>Condición (opcional)</label><input class="input" id="wCond" placeholder='{"fence_state":"outside"}'></div>
    <div class="field"><label>Acción</label><select class="sel" id="wAct">${aOpts}</select></div>`;
  showModal("Nuevo workflow", null, body, async ()=>{
    const payload = {name:$("#wName").value, trigger:$("#wTrig").value, action:$("#wAct").value,
      condition: $("#wCond").value?tryJson($("#wCond").value,{}):{}};
    const r = await api("/api/workflows/custom", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
    if(r.ok){ toast("Workflow creado","","ok"); closeModal(); renderWorkflows(); }
    else toast("Error", r.error||"", "bad");
  });
}

/* ============================================================
   VISTA: AJUSTES
   ============================================================ */
async function renderSettings(){
  $("#view-settings").innerHTML = `
    <div class="card" style="max-width:680px"><div class="hd"><h3>Configuración de integración</h3></div>
      <div class="bd" id="setBody"><div class="sk" style="height:200px"></div></div></div>`;
  let s={};
  try{ s = await api("/api/settings/status"); }catch(e){}
  const mode = s.mode||"simulation";
  $("#setBody").innerHTML = `
    <div class="switch-row"><div style="flex:1"><div class="lab">Modo</div><div class="ds">Live conecta con Applivery UEM real · Demo usa datos simulados.</div></div>
      <div class="seg" id="modeSeg"><button data-m="live" class="${mode==='live'?'active':''}">Live</button><button data-m="simulation" class="${mode==='simulation'?'active':''}">Demo</button></div></div>
    <div class="field"><label>Token de Applivery (Bearer)</label><div class="input-wrap"><input class="input" id="sKey" type="password" placeholder="••••••" value=""><button class="toggle" onclick="toggleShow('sKey',this)">Ver</button></div>
      <div class="help">${s.configured? "Actualmente configurado: <b>"+(s.masked_key||"")+"</b>":"No configurado"}</div></div>
    <div class="field"><label>Organization ID</label><input class="input" id="sOrg" placeholder="692f26…" value="${esc(s.org_id||"")}"></div>
    <div class="switch-row"><div style="flex:1"><div class="lab">Dry-run</div><div class="ds">No ejecuta acciones reales sobre los dispositivos.</div></div>
      <div class="switch ${s.dry_run?'on':''}" id="sDry"></div></div>
    <button class="btn outline" id="sTest">Probar conexión</button>
    <button class="btn primary" id="sSave" style="margin-left:8px">Guardar</button>
    <div id="sResult" class="test-result" style="margin-top:14px"></div>`;
  $$("#modeSeg button").forEach(b=>b.onclick=()=>{
    $$("#modeSeg button").forEach(x=>x.classList.remove("active")); b.classList.add("active");
  });
  $("#sDry").onclick=()=>$("#sDry").classList.toggle("on");
  $("#sTest").onclick = async ()=>{
    const r = await api("/api/settings/test", {method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({api_key:$("#sKey").value})});
    const res = $("#sResult");
    if(r.ok){ res.className="test-result ok show"; res.textContent="Conexión correcta ("+(r.device_count||0)+" dispositivos)."; }
    else { res.className="test-result bad show"; res.textContent=r.error||"Fallo de conexión"; }
  };
  $("#sSave").onclick = async ()=>{
    const mode = $("#modeSeg button.active").dataset.m;
    const r = await api("/api/settings", {method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({api_key:$("#sKey").value, org_id:$("#sOrg").value, mode, dry_run:$("#sDry").classList.contains("on")})});
    if(r.ok){ toast("Guardado", "Modo "+mode, "ok"); refresh(false); }
    else toast("Error", r.error||"", "bad");
  };
}
function toggleShow(id, btn){ const i=$("#"+id); if(i.type==="password"){i.type="text";btn.textContent="Ocultar";} else {i.type="password";btn.textContent="Ver";} }

/* ============================================================
   VISTA: IA · MoA  (chat multi-modelo con contexto de flota)
   ============================================================ */
async function loadAiProviders(){
  try{
    const data = await api("/api/ai/providers");
    App.aiProviders = data.providers||[];
    const box = $("#aiProv"); if(box){
      if(!data.online){
        box.innerHTML = `<div class="empty">${reicon("signal", {size:36})}
          <div class="t">Motor MoA no disponible</div><div class="s">Arranca /Users/adri/moa/server.py en el puerto 8085 para habilitar la IA.</div></div>`;
      } else {
        box.innerHTML = App.aiProviders.map(p=>`<div class="prov"><span class="st ${p.available?'on':'warn'}"></span>
          <div><div class="nm">${esc(p.name)}</div></div><span class="md">${esc(p.model||"")}</span></div>`).join("")
          + `<div class="ctx-row"><span class="sw"></span>Contexto: flota en vivo (${App.status?App.status.devices?.length||0:0} disp.) inyectado automáticamente</div>`;
      }
    }
  }catch(e){}
}
async function renderAI(){
  $("#view-ai").innerHTML = `
    <div class="toolbar"><div class="grow"></div>
      <div class="seg" id="aiMode"><button data-d="true" class="active">Demo (sin claves)</button><button data-d="false">Real (MoA)</button></div>
    </div>
    <div class="ai-wrap">
      <div class="chat">
        <div class="hd"><div class="ic" style="width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,var(--violet),var(--accent));display:grid;place-items:center;color:#fff">${I.bolt}</div>
          <h3>IA de Flota · Mixture-of-Agents</h3><div class="grow"></div>
          <span class="tag in"><span class="d"></span>local</span></div>
        <div class="msgs" id="aiMsgs"></div>
        <div class="composer">
          <textarea id="aiInput" placeholder="Pregunta sobre tu flota… (ej: ¿qué dispositivos están fuera de su geovalla y por qué?)"></textarea>
          <button class="btn primary" id="aiSend">${I.bolt} Enviar</button>
        </div>
      </div>
      <div class="providers" id="aiProv"><div class="sk" style="height:20px"></div></div>
    </div>`;
  $$("#aiMode button").forEach(b=>b.onclick=()=>{
    $$("#aiMode button").forEach(x=>x.classList.remove("active")); b.classList.add("active");
    App.aiDry = b.dataset.d==="true";
  });
  App.aiDry = true;
  $("#aiSend").onclick = sendAi;
  $("#aiInput").addEventListener("keydown", e=>{ if(e.key==="Enter" && !e.shiftKey){ e.preventDefault(); sendAi(); } });
  loadAiProviders();
  // saludo inicial
  if(!$("#aiMsgs").children.length){
    addAiMsg("ai", "Hola. Soy tu analista de flota multi-modelo (Mixture-of-Agents, 100% local). Tengo visibilidad de tu flota en vivo. Pregúntame sobre conformidad, rutas, incidentes o pide un resumen ejecutivo.", null);
  }
}
function addAiMsg(role, text, meta){
  const box = $("#aiMsgs"); if(!box) return;
  const m = el("div", "msg "+role);
  const av = role==="user"? avatarText(App.org&&App.org.org?App.org.org.name:"U") : "AI";
  let metaHtml = "";
  if(meta && (meta.agg_used||meta.ref_used)){
    metaHtml = `<div class="meta">MoA · agregador ${esc(meta.agg_used||"—")} · ${esc((meta.ref_used||[]).join(", ")||"—")} · ${meta.rounds||1} capa(s)</div>`;
  }
  m.innerHTML = `<div class="av2">${av}</div><div><div class="bubble">${esc(text)}</div>${metaHtml}</div>`;
  box.appendChild(m); box.scrollTop = box.scrollHeight;
}
async function sendAi(){
  const input = $("#aiInput"); const q = input.value.trim(); if(!q) return;
  addAiMsg("user", q, null); input.value="";
  const msgs = $("#aiMsgs");
  const typing = el("div","msg ai"); typing.innerHTML=`<div class="av2">AI</div><div class="bubble"><span class="typing"><i></i><i></i><i></i></span></div>`;
  msgs.appendChild(typing); msgs.scrollTop=msgs.scrollHeight;
  // Construye contexto de flota
  const st = App.status||{};
  const fleetSummary = buildFleetContext(st);
  const messages = [
    {role:"system", content:"Eres un analista senior de UEM/MDM para una empresa con geofencing. Tienes estos datos de la flota EN VIVO. Responde en español, concreto y accionable. Usa markdown ligero."},
    {role:"system", content:"FLOTA EN VIVO:\n"+fleetSummary},
    {role:"user", content:q},
  ];
  try{
    const r = await api("/api/ai", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({messages, moa_dry: App.aiDry!==false, moa_rounds:2, moa_agg_mode:"synthesize"})});
    typing.remove();
    if(r.ok){ addAiMsg("ai", r.text||"(sin respuesta)", {agg_used:r.agg_used, ref_used:r.ref_used, rounds:r.rounds}); }
    else { typing.remove(); addAiMsg("ai", "No pude obtener respuesta: "+(r.error||""), null); }
  }catch(e){
    typing.remove(); addAiMsg("ai", "Error de conexión con el motor MoA: "+e.message, null);
  }
}
function buildFleetContext(st){
  const devs = st.devices||[];
  const lines = [];
  lines.push(`Total dispositivos: ${devs.length}`);
  lines.push(`Dentro: ${st.inside_count||0} · Fuera: ${st.outside_count||0} · Desconocidos: ${st.unknown_count||0} · Incumplen: ${st.noncompliant||0}`);
  lines.push("Detalle:");
  devs.slice(0,40).forEach(d=>{
    lines.push(`- ${d.name} (${d.platform}) → ${d.fence_state||"desconocido"}${d.compliant===false?" [INCUMPLE]":""} | ${d.city||d.country||""} | ${d.lat!=null?d.lat.toFixed(3)+","+d.lng.toFixed(3):"sin coord"} | visto ${fmt.ago(d.last_seen)} | fuente ${d.location_source||d.source||"?"}`);
  });
  const evs = (st.recent_events||[]).slice(0,15);
  if(evs.length){ lines.push("Eventos recientes:"); evs.forEach(e=>lines.push(`- [${e.kind}] ${e.text||e.msg||""} (${fmt.ago(e.ts)})`)); }
  const acts = (st.recent_actions||[]).slice(0,15);
  if(acts.length){ lines.push("Acciones:"); acts.forEach(a=>lines.push(`- ${a.action||a.text||""} → ${a.result||""} (${fmt.ago(a.ts)})`)); }
  return lines.join("\n");
}

/* ============================================================
   VISTA: OBJETIVOS (/goal) — KPIs objetivo vs real
   ============================================================ */
function renderGoals(){
  const st = App.status; if(!st) return;
  const devs = st.devices||[];
  const total = devs.length || (st.inside_count+st.outside_count+st.unknown_count) || 1;
  const inside = st.inside_count||0, outside = st.outside_count||0, unknown = st.unknown_count||0;
  const noncomp = st.noncompliant||0;
  const compPct = Math.round((total-noncomp)/total*100);
  const routesOn = (st.stats&&st.stats.routes_on_route!=null)?st.stats.routes_on_route:0;
  const routesTot = (st.routes||[]).length;
  const fences = (st.fences||[]).length;

  // Objetivos (targets) — configurables aquí
  const goals = [
    {key:"comp", label:"Conformidad de flota", icon:I.shield, target:95, real:compPct, unit:"%", hint:"% dispositivos conformes"},
    {key:"inside", label:"Dispositivos en su geovalla", icon:I.in, target:90, real:Math.round(inside/total*100), unit:"%", hint:"% dentro de zona asignada"},
    {key:"cov", label:"Cobertura de geovallas", icon:I.dev, target:100, real:Math.min(100, Math.round(fences/3*100)), unit:"%", hint:fences+" geovallas definidas"},
    {key:"routes", label:"Rutas en trayecto", icon:I.route, target:100, real:routesTot?Math.round(routesOn/Math.max(1,routesTot)*100):0, unit:"%", hint:routesOn+"/"+routesTot+" en ruta"},
    {key:"vis", label:"Visibilidad (sin señal)", icon:I.out, target:0, real:unknown, unit:"disp", invert:true, hint:unknown+" sin señal"},
  ];

  function ring(pct, color){
    const r=34, c=2*Math.PI*r, off=c*(1-pct/100);
    return `<svg width="84" height="84" viewBox="0 0 84 84">
      <circle cx="42" cy="42" r="${r}" fill="none" stroke="var(--panel-3)" stroke-width="8"/>
      <circle cx="42" cy="42" r="${r}" fill="none" stroke="${color}" stroke-width="8" stroke-linecap="round"
        stroke-dasharray="${c}" stroke-dashoffset="${off}" transform="rotate(-90 42 42)"/>
      <text x="42" y="48" text-anchor="middle" font-size="18" font-weight="700" fill="var(--fg)">${pct}%</text></svg>`;
  }

  const cards = goals.map(g=>{
    const met = g.invert ? (g.real<=g.target) : (g.real>=g.target);
    const eff = g.invert ? Math.max(0,100-Math.min(100,g.real)) : Math.min(100,g.real);
    const color = met? "var(--green)": g.real>=g.target*0.8? "var(--amber)":"var(--red)";
    return `<div class="card" style="padding:18px">
      <div style="display:flex;align-items:center;gap:12px">
        <div style="width:36px;height:36px;border-radius:9px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent)">${g.icon}</div>
        <div style="flex:1;min-width:0"><div style="font-weight:600;font-size:13px">${esc(g.label)}</div>
        <div class="sub">${esc(g.hint)}</div></div>
        ${ring(Math.round(eff), color)}
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:14px;font-size:12px;color:var(--muted)">
        <span>Real: <b style="color:var(--fg)">${g.real}${g.unit==="%"?"%":(" "+g.unit)}</b></span>
        <span>Objetivo: <b style="color:var(--fg)">${g.target}${g.unit==="%"?"%":(" "+g.unit)}</b></span>
        <span style="color:${met?'var(--green)':'var(--amber)'};font-weight:600">${met?'✓ Cumplido':'En progreso'}</span>
      </div>
    </div>`;
  }).join("");

  // tendencia de conformidad (mini)
  const sh = st.stats_history||[];
  const trend = sh.length? sh.slice(-20).map(h=>{ const t=h.devices_total||1; return Math.round((t-(h.non_compliant||0))/t*100); }) : [];

  $("#view-goals").innerHTML = `
    <div class="toolbar"><div style="font-size:13px;font-weight:600">Objetivos de operación UEM</div><div class="grow"></div>
      <span class="tag ${compPct>=95?'in':'out'}"><span class="d"></span>${compPct>=95?'SLA OK':'SLA en riesgo'}</span></div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px">${cards}</div>
    <div class="card" style="margin-top:14px"><div class="hd"><h3>Tendencia de conformidad (ciclos recientes)</h3><div class="grow"></div>
      <span class="sub">${trend.length? trend[0]+"% → "+trend[trend.length-1]+"%":"—"}</span></div>
      <div class="bd"><canvas id="goalTrend" height="120"></canvas></div></div>`;

  const cv = $("#goalTrend"); if(cv && trend.length){
    if(App.__goalChart) App.__goalChart.destroy();
    App.__goalChart = new Chart(cv, {type:"line",
      data:{labels:trend.map((_,i)=>i+1), datasets:[{data:trend, borderColor:"#5e6ad5", backgroundColor:"rgba(94,106,213,.12)", borderWidth:2, fill:true, tension:.35, pointRadius:0}]},
      options:{responsive:true, plugins:{legend:{display:false}}, scales:{x:{display:false}, y:{min:0,max:100,grid:{color:"rgba(148,163,184,.08)"},ticks:{color:"var(--muted-2)",font:{size:9}}}}} });
  }
}

/* ---------- helpers UI ---------- */
function emptyState(title, sub){
  return `<div class="empty">${reicon("box", {size:36})}
    <div class="t">${esc(title)}</div><div class="s">${esc(sub||"")}</div></div>`;
}
function tryJson(s, fallback){ try{ return JSON.parse(s); }catch(e){ return fallback; } }
function showModal(title, avatarHtml, bodyHtml, onSave, saveLabel="Guardar"){
  $("#mName").textContent = title;
  $("#mAv").style.display = avatarHtml? "grid":"none";
  if(avatarHtml) $("#mAv").innerHTML = avatarHtml;
  $("#mKv").innerHTML = bodyHtml;
  $("#mTag").innerHTML = "";
  $("#mTrail").innerHTML = "";
  $("#mEvents").innerHTML = "";
  // reutilizamos el modal pero con botón guardar temporal
  let footer = $("#mFooter");
  if(!footer){ footer = el("div"); footer.id="mFooter"; footer.style.cssText="padding:0 18px 18px"; $("#devModal").appendChild(footer); }
  footer.innerHTML = `<div style="display:flex;gap:8px;justify-content:flex-end"><button class="btn outline" id="mCancel">Cancelar</button><button class="btn primary" id="mSave">${saveLabel}</button></div>`;
  $("#mCancel").onclick = closeModal;
  $("#mSave").onclick = async ()=>{ $("#mSave").disabled=true; await onSave(); $("#mSave").disabled=false; };
  $("#ovl").classList.add("show"); $("#devModal").classList.add("show");
}
function toggleTheme(){
  const cur = document.documentElement.getAttribute("data-theme");
  document.documentElement.setAttribute("data-theme", cur==="light"?"dark":"light");
  try{ localStorage.setItem("gf_theme", cur==="light"?"dark":"light"); }catch(e){}
}

/* ---------- command palette ---------- */
let cmdkSel = 0;
function openCmdk(){
  const list = $("#cmdkList"); const devs = (App.status&&App.status.devices)||[];
  const items = [
    {g:"Navegar", items: NAV.map(n=>({label:"Ir a "+n.label, ic:I.dev, act:()=>goView(n.id)}))},
    {g:"Acciones", items:[
      {label:"Forzar ciclo", ic:I.bolt, act:()=>forceCycle()},
      {label:"Refrescar", ic:I.act, act:()=>refresh(false)},
      {label:"Nueva geovalla", ic:I.act, act:()=>openFenceModal()},
      {label:"Nueva ruta", ic:I.route, act:()=>openRouteModal()},
      {label:"Nuevo workflow", ic:I.bolt, act:()=>openWorkflowModal()},
      {label:"Preguntar a la IA", ic:I.bolt, act:()=>goView("ai")},
    ]},
  ];
  let html = "";
  items.forEach(group=>{
    html += `<div class="group">${group.g}</div>`;
    group.items.forEach((it,i)=>{ html += `<div class="item" data-i="${i}"><span class="ic">${it.ic}</span>${esc(it.label)}</div>`; });
  });
  // dispositivos
  if(devs.length){ html += `<div class="group">Dispositivos</div>`; devs.slice(0,30).forEach((d,i)=>{
    html += `<div class="item" data-dev="${esc(d.device_id)}"><span class="ic">${platformIcon(d.platform)}</span>${esc(d.name)} <span class="k">${esc(d.fence_state||"")}</span></div>`; }); }
  list.innerHTML = html;
  cmdkSel = 0;
  $$("#cmdkList .item").forEach(elx=>elx.onclick=()=>{
    if(elx.dataset.dev) openDeviceModal(elx.dataset.dev); else runCmdk(elx);
    closeCmdk();
  });
  $("#cmdk").classList.add("show");
  $("#cmdkInput").value=""; $("#cmdkInput").focus();
}
function runCmdk(elx){
  const idx = parseInt(elx.dataset.i);
  const groups = [NAV, []];
  // mapeo simple por índice global
  const all = [];
  [ {g:"Navegar", items: NAV.map(n=>({label:"Ir a "+n.label, act:()=>goView(n.id)}))},
    {g:"Acciones", items:[
      {label:"Forzar ciclo", act:()=>forceCycle()},
      {label:"Refrescar", act:()=>refresh(false)},
      {label:"Nueva geovalla", act:()=>openFenceModal()},
      {label:"Nueva ruta", act:()=>openRouteModal()},
      {label:"Nuevo workflow", act:()=>openWorkflowModal()},
      {label:"Preguntar a la IA", act:()=>goView("ai")},
  ]}].forEach(g=>g.items.forEach(it=>all.push(it)));
  if(all[idx]) all[idx].act();
}
function closeCmdk(){ $("#cmdk").classList.remove("show"); }
async function forceCycle(){
  toast("Ciclo","Forzando…","info");
  try{ const r = await api("/api/run-once", {method:"POST"}); if(r.ok) toast("Ciclo completado","","ok"); refresh(false); }
  catch(e){ toast("Error de ciclo", e.message, "bad"); }
}

/* ---------- global bind ---------- */
function bindGlobal(){
  $("#refreshBtn").onclick = ()=>refresh(false);
  $("#cycleBtn").onclick = ()=>forceCycle();
  $("#themeBtn").onclick = ()=>toggleTheme();
  $("#cmdBtn").onclick = ()=>openCmdk();
  // ---- G1: auth UI wiring ----
  $("#authSubmit") && ($("#authSubmit").onclick = submitAuth);
  $("#authPass") && $("#authPass").addEventListener("keydown", e=>{ if(e.key==="Enter") submitAuth(); });
  $("#authEmail") && $("#authEmail").addEventListener("keydown", e=>{ if(e.key==="Enter") $("#authPass").focus(); });
  $("#authOrg") && $("#authOrg").addEventListener("keydown", e=>{ if(e.key==="Enter") submitAuth(); });
  $$("#authTabs button").forEach(b=>b.onclick=()=>setAuthTab(b.dataset.t));
  $("#authOvl") && ($("#authOvl").onclick = ()=>{ /* modal auth no se cierra con backdrop: evita acceso sin sesión */ });
  $("#sideLogout") && ($("#sideLogout").onclick = logout);
  document.addEventListener("keydown", e=>{
    if((e.metaKey||e.ctrlKey) && e.key.toLowerCase()==="k"){ e.preventDefault(); openCmdk(); }
    if(e.key==="Escape"){ closeModal(); closeCmdk(); }
  });
  $("#cmdkInput") && $("#cmdkInput").addEventListener("input", e=>{
    const q = e.target.value.toLowerCase();
    $$("#cmdkList .item").forEach(it=>{
      const txt = it.textContent.toLowerCase();
      it.style.display = (!q || txt.includes(q))?"":"none";
    });
  });
  // tema inicial
  try{ const t = localStorage.getItem("gf_theme"); if(t) document.documentElement.setAttribute("data-theme", t); }catch(e){}
}

/* ===================== INVENTARIO IT (MDM/UEM asset mgmt) ===================== */
async function renderInventory(){
  const node = $("#view-inventory"); if(!node) return;
  let devs = [];
  try{ devs = await api("/api/devices"); }catch(e){ node.innerHTML = `<div class="sub">No se pudo cargar el inventario.</div>`; return; }
  const cols = [
    {k:"name", t:"Dispositivo"},
    {k:"platform", t:"SO"},
    {k:"model", t:"Modelo"},
    {k:"os_version", t:"Versión SO"},
    {k:"serial_number", t:"Serial"},
    {k:"assigned_user", t:"Usuario"},
    {k:"department", t:"Depto"},
    {k:"fence_state", t:"Geovalla"},
    {k:"compliant", t:"Cumple"},
    {k:"battery_level", t:"Batería"},
    {k:"storage_free_gb", t:"Libre (GB)"},
    {k:"risk_score", t:"Riesgo"},
    {k:"verified", t:"Verif."},
  ];
  const filt = App.invFilter || "all";
  const filtered = devs.filter(d=>{
    if(filt==="all") return true;
    if(filt==="noncompliant") return d.compliant===false;
    if(filt==="outside") return d.fence_state==="outside";
    if(filt==="lowbattery") return (d.battery_level||100) < 25;
    if(filt==="lowstorage") return (d.storage_free_gb??9e9) < 10;
    return true;
  });
  node.innerHTML = `
    <div class="view-head">
      <div><h2>Inventario de Flota</h2><div class="sub">${devs.length} dispositivos · vista de activos para administradores IT</div></div>
      <div class="row gap">
        <div class="chips" id="invFilters">
          <button class="chip ${filt==='all'?'active':''}" data-f="all">Todos</button>
          <button class="chip ${filt==='noncompliant'?'active':''}" data-f="noncompliant">Incumplen</button>
          <button class="chip ${filt==='outside'?'active':''}" data-f="outside">Fuera</button>
          <button class="chip ${filt==='lowbattery'?'active':''}" data-f="lowbattery">Batería <25%</button>
          <button class="chip ${filt==='lowstorage'?'active':''}" data-f="lowstorage">Almacenaje <10GB</button>
        </div>
        <button class="btn ghost" onclick="exportReport('inventory','csv')">CSV</button>
        <button class="btn ghost" onclick="exportReport('inventory','html')">PDF</button>
        <button class="btn ghost" onclick="exportReport('compliance','csv')">Compliance CSV</button>
        <button class="btn ghost" onclick="exportReport('actions','csv')">Acciones CSV</button>
      </div>
    </div>
    <div class="card">
      <table class="tbl" id="invTbl">
        <thead><tr>${cols.map(c=>`<th>${c.t}</th>`).join("")}<th></th></tr></thead>
        <tbody>
          ${filtered.map(d=>`
            <tr>
              <td>${esc(d.name||d.device_id)}</td>
              <td>${esc(d.platform)}</td>
              <td>${esc(d.model||"—")}</td>
              <td>${esc(d.os_version||"—")}</td>
              <td class="mono">${esc(d.serial_number||"—")}</td>
              <td>${esc(d.assigned_user||"—")}</td>
              <td>${esc(d.department||"—")}</td>
              <td>${stateTag(d.fence_state)}</td>
              <td>${d.compliant===true?'<span class="tag in">SI</span>':d.compliant===false?'<span class="tag nocomp">NO</span>':'<span class="tag">?</span>'}</td>
              <td>${batt(d.battery_level)}</td>
              <td>${d.storage_free_gb!=null?d.storage_free_gb+' GB':'—'}</td>
              <td>${riskPill(d.risk_score)}</td>
              <td>${invVerified(d.device_id)}</td>
              <td><button class="btn sm" onclick="openDeviceModal('${esc(d.device_id)}')">Ver</button></td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
  $$("#invFilters .chip").forEach(c=>c.onclick=()=>{ App.invFilter=c.dataset.f; renderInventory(); });
}
function batt(v){
  if(v==null) return "—";
  const col = v<20?"var(--red)":v<50?"var(--amber)":"var(--green)";
  return `<span style="color:${col};font-weight:600">${v}%</span>`;
}
function riskPill(v){
  if(v==null) return "—";
  // Riesgo alto = rojo (peligro), medio = ámbar, bajo = verde. NUNCA reusar
  // "out" (azul) que significa "fuera de geovalla" — confunde a un admin IT.
  const sev = v>=70?"nocomp":v>=40?"unk":"in";
  return `<span class="tag ${sev}">${Math.round(v)}</span>`;
}
function invVerified(id){
  const risk = (App._riskMap && App._riskMap[id]) || null;
  if(!risk) return '<span class="sub">—</span>';
  return `<span title="${risk.reasons && risk.reasons.length ? esc(risk.reasons.join(' · ')) : 'sin señales'}" style="cursor:help">${verifiedBadge(risk.verified, {short:true})}</span>`;
}
function stateTag(s){
  if(s==="inside") return '<span class="tag in"><span class="d"></span>dentro</span>';
  if(s==="outside") return '<span class="tag out"><span class="d"></span>fuera</span>';
  return '<span class="tag"><span class="d"></span>desconocido</span>';
}
async function exportReport(kind, format){
  const url = `/api/export?kind=${kind}&format=${format}`;
  toast("Exportando", `${kind} (${format})`, "info");
  // open in new tab so the browser downloads/prints
  window.open(url, "_blank");
}

/* ===================== ALERTAS CONFIGURABLES ===================== */
async function renderAlerts(){
  const node = $("#view-alerts"); if(!node) return;
  let data = {rules:[],firings:[]};
  try{ data = await api("/api/alerts"); }catch(e){}
  const types = data.types || ["outside_duration","risk_above","noncompliant","battery_below","storage_low","stale_checkin"];
  const channels = data.channels || ["slack","email","none"];
  const tlabel = data.labels || {outside_duration:"Fuera de geovalla > N min",risk_above:"Riesgo > N",noncompliant:"Dispositivo non-compliant",battery_below:"Batería < N%",storage_low:"Almacenaje libre < N GB",stale_checkin:"Check-in antiguo > N min"};
  node.innerHTML = `
    <div class="view-head">
      <div><h2>Alertas & Notificaciones</h2><div class="sub">Umbrales configurables por el administrador IT · entrega Slack/Teams o email</div></div>
      <button class="btn" id="newAlertBtn">+ Nueva regla</button>
    </div>
    <div class="card" style="margin-bottom:16px">
      <table class="tbl">
        <thead><tr><th>Tipo</th><th>Umbral</th><th>Canal</th><th>Destino</th><th>Gravedad</th><th>Estado</th><th></th></tr></thead>
        <tbody id="alertRows">
          ${data.rules.map(r=>`
            <tr>
              <td>${tlabel[r.type]||r.type}</td>
              <td>${r.threshold} ${unit(r.type)}</td>
              <td>${esc(r.channel)}</td>
              <td class="mono">${esc(r.target||"—")}</td>
              <td>${esc(r.severity)}</td>
              <td>${r.enabled?'<span class="tag in">activa</span>':'<span class="tag">pausada</span>'}</td>
              <td><button class="btn sm bad" onclick="delAlert('${r.id}')">Eliminar</button></td>
            </tr>`).join("") || `<tr><td colspan="7" class="sub">Sin reglas. Crea tu primera alerta.</td></tr>`}
        </tbody>
      </table>
    </div>
    <div class="card">
      <h3>Disparos recientes</h3>
      <div id="alertFirings">
        ${(data.firings||[]).slice(0,30).map(f=>`
          <div class="kv"><span><b>${esc(f.device_name)}</b> · ${tlabel[f.rule_type]||f.rule_type} · ${esc(f.detail)}</span>
          <span class="sub">${esc(f.ts)} · ${f.delivered?'<span class="tag in">entregada</span>':'<span class="tag out">no entregada</span>'}</span></div>`).join("") || '<div class="sub">Sin disparos recientes.</div>'}
      </div>
      <button class="btn ghost" id="evalAlertsBtn">Evaluar ahora</button>
    </div>`;
  $("#newAlertBtn").onclick = ()=>openAlertModal(types, channels, tlabel);
  $("#evalAlertsBtn").onclick = async ()=>{ await api("/api/alerts/evaluate",{method:"POST"}); toast("Evaluado","Reglas procesadas","ok"); renderAlerts(); };
}
function unit(t){
  if(t==="battery_below") return "%";
  if(t==="storage_low") return "GB";
  if(t==="outside_duration"||t==="stale_checkin") return "min";
  if(t==="risk_above") return "pts";
  return "";
}
async function openAlertModal(types, channels, tlabel){
  const body = `
    <div class="form">
      <label>Tipo de alerta
        <select id="alType">${types.map(t=>`<option value="${t}">${tlabel[t]||t}</option>`).join("")}</select>
      </label>
      <label>Umbral (número)
        <input id="alThr" type="number" value="30" />
      </label>
      <label>Canal
        <select id="alCh">${channels.map(c=>`<option value="${c}">${c}</option>`).join("")}</select>
      </label>
      <label>Destino (webhook Slack/email)
        <input id="alTarget" placeholder="https://hooks.slack.com/... o admin@empresa.com" />
      </label>
      <label>Gravedad
        <select id="alSev"><option>low</option><option selected>medium</option><option>high</option><option>critical</option></select>
      </label>
      <label>Cooldown (min)
        <input id="alCd" type="number" value="30" />
      </label>
    </div>`;
  showModal("Nueva regla de alerta", "", body, async ()=>{
    const payload = {
      type: $("#alType").value,
      threshold: parseFloat($("#alThr").value),
      channel: $("#alCh").value,
      target: $("#alTarget").value.trim(),
      severity: $("#alSev").value,
      cooldown_minutes: parseInt($("#alCd").value)||30,
    };
    const r = await api("/api/alerts", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
    if(r.ok){ toast("Alerta creada", payload.type, "ok"); closeModal(); renderAlerts(); }
    else toast("Error", (r.error||"no válida"), "bad");
  }, "Crear");
}
async function delAlert(id){
  await api(`/api/alerts/${id}/delete`, {method:"POST"});
  toast("Eliminada","","ok"); renderAlerts();
}

/* ===================== COMANDOS REMOTOS ON-DEMAND ===================== */
async function sendDeviceCommand(devId, action, params){
  toast("Enviando", `${action} → ${devId}`, "info");
  const r = await api(`/api/devices/${devId}/command`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({action, params:params||{}})});
  if(r.ok){
    const note = r.dry_run? " (dry-run, simulado)" : (r.delegated? " (delegado vía webhook)" : "");
    toast("Comando enviado", `${action}${note}`, "ok");
  } else if(r.cooldown){
    toast("En cooldown", r.error, "bad");
  } else {
    toast("Error", (r.error||"no enviado"), "bad");
  }
  return r;
}

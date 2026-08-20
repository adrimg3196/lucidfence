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
  mapFilter: "all",
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
    // Local-app bootstrap: first inspect the HttpOnly session directly. If it
    // does not exist, ask the loopback-only demo endpoint for one and retry.
    let response = await fetch("/api/auth/me", {credentials:"same-origin"});
    if(response.status === 401){
      const demo = await fetch("/api/auth/demo", {
        method:"POST", credentials:"same-origin",
        headers:{"Content-Type":"application/json"}, body:"{}"
      });
      if(!demo.ok) throw new Error("demo local no disponible");
      response = await fetch("/api/auth/me", {credentials:"same-origin"});
    }
    if(!response.ok) throw new Error("no autenticado");
    const me = await response.json();
    App.user = me.user; App.orgs = me.orgs||[];
    await refreshOrg();
    updateUserUI();
    hideAuthModal();
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
  m.classList.add("show"); m.setAttribute("aria-hidden","false"); ov.classList.add("show");
  const e = $("#authEmail"); if(e) setTimeout(()=>e.focus(), 30);
}
function hideAuthModal(){
  const m = $("#authModal"), ov = $("#authOvl");
  if(m){ m.classList.remove("show"); m.setAttribute("aria-hidden","true"); } if(ov) ov.classList.remove("show");
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
  $("#orgName").textContent="";
  ["overview","map","devices","riesgo","inventory","ai","events","incidents","soar","actions","alerts","fences","routes","workflows","goals","intelligence","settings"].forEach(v=>{ const n=$("#view-"+v); if(n) n.innerHTML=""; });
  showAuthModal();
}
function startApp(){
  renderNav();
  refresh(true).then(()=>{
    const requested=location.hash.replace(/^#/,"");
    goView(NAV.some(item=>item.id===requested)?requested:(App.view||"overview"));
    App._started=true; startPolling();
  }).catch(()=>{});
}
function startPolling(){ stopPolling(); App.pollTimer = setInterval(()=>refresh(false), 60000); }
function stopPolling(){ if(App.pollTimer){ clearInterval(App.pollTimer); App.pollTimer=null; } }

/* ---------- navegación (iconos reicon: github.com/dqev/reicon) ---------- */
const NAV = [
  {id:"overview",   label:"Resumen",     icon:"grid"},
  {id:"map",        label:"Mapa",        icon:"map"},
  {id:"devices",    label:"Dispositivos",icon:"devices"},
  {id:"inventory",  label:"Inventario",  icon:"box"},
  {id:"connectors", label:"Conectores UEM", icon:"link"},
  {id:"riesgo",     label:"Riesgo",       icon:"shield-alert"},
  {id:"ai",         label:"AI opcional",  icon:"cpu"},
  {id:"events",     label:"Eventos",     icon:"calendar"},
  {id:"incidents",  label:"Incidentes",  icon:"alert-triangle2"},
  {id:"soar",       label:"SOAR · CVE",  icon:"shield-alert"},
  {id:"actions",    label:"Acciones",    icon:"bolt"},
  {id:"alerts",     label:"Alertas",     icon:"bell"},
  {id:"fences",     label:"Geovallas",   icon:"shield"},
  {id:"routes",     label:"Rutas",       icon:"route"},
  {id:"workflows",  label:"Workflows",   icon:"sitemap-4"},
  {id:"goals",      label:"Objetivos",   icon:"target"},
  {id:"intelligence",label:"Inteligencia",icon:"chart-line"},
  {id:"company",     label:"Compañía autónoma",icon:"building"},
  {id:"settings",   label:"Ajustes",     icon:"settings"},
  {id:"roadmap",    label:"Roadmap",     icon:"git-branch"},
  {id:"roi",        label:"ROI · Valor", icon:"trending-up"},
];

function renderNav(){
  const n = $("#nav"); n.innerHTML="";
  NAV.forEach(item=>{
    const a = el("a", App.view===item.id?"active":"");
    a.href = "#"+item.id;
    a.setAttribute("aria-current", App.view===item.id ? "page" : "false");
    let badge="";
    if(item.id==="incidents" && App._openIncidents){
      badge = ` <span class="nav-badge">${App._openIncidents}</span>`;
    }
    const ic = reicon(item.icon, {size:18, className:"nav-ic"});
    a.innerHTML = `${ic}<span>${item.label}</span>${badge}`;
    a.onclick = event=>{ event.preventDefault(); goView(item.id); };
    n.appendChild(a);
  });
}
function goView(id){
  App.view = id;
  if(location.hash!=="#"+id) history.replaceState(null,"","#"+id);
  renderNav();
  $$(".view").forEach(v=>v.classList.add("hidden"));
  const v = $("#view-"+id); v.classList.remove("hidden");
  const label = NAV.find(x=>x.id===id).label;
  $("#crumbC").textContent = label;
  if(id==="overview") renderOverview();
  if(id==="map") renderMapView();
  if(id==="devices") renderDevices();
  if(id==="inventory") renderInventory();
  if(id==="connectors") renderConnectors();
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
  if(id==="intelligence") renderIntelligence();
  if(id==="company") renderCompany();
  if(id==="settings") renderSettings();
  if(id==="roadmap") renderRoadmap();
  if(id==="roi") renderROI();
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
    else if(App.view==="connectors") renderConnectors();
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
    else if(App.view==="intelligence") renderIntelligence();
    else if(App.view==="company") renderCompany();
    else if(App.view==="ai") loadAiProviders();
    else if(App.view==="roadmap") renderRoadmap();
  }catch(e){
    const se=$("#sync"); if(se) se.classList.add("stale");
    const text=$("#syncText"); if(text) text.textContent="Error de conexión · datos anteriores";
    const now=Date.now();
    if(!App._lastRefreshErrorAt || now-App._lastRefreshErrorAt>30000){
      toast("Datos no actualizados", e.message||"No se pudo contactar con la API", "bad");
      App._lastRefreshErrorAt=now;
    }
  }
}

/* ============================================================
   VISTA: ROADMAP (mejora tooling) — fuente de verdad roadmap.json
   ============================================================ */
async function renderRoadmap(){
  const node = $("#view-roadmap"); if(!node) return;
  try{
    const [d, loopMetrics] = await Promise.all([
      api("/api/roadmap"),
      api("/api/loop/metrics").catch(()=>({iterations:0,average_score:0,below_threshold:0}))
    ]);
    const prog = d.progress || {};
    const pct = prog.pct||0;
    const barFull = Math.max(0, Math.min(10, Math.round(pct/10)));
    const bar = "█".repeat(barFull)+"░".repeat(10-barFull);
    const stCls = pct>=50 ? "in" : "unk";
    let html = `
      <div class="view-head">
        <div><h2>Roadmap de mejora tooling</h2>
          <div class="sub">${esc(d.meta?.title||"")} · ${esc(d.meta?.horizon||"")}</div></div>
        <div class="acts"><span class="tag ${stCls}"><span class="d"></span>${pct}% (${prog.done||0}/${prog.total||0})</span></div>
      </div>
      <div class="card"><div class="bd">
        <div class="donut-wrap" style="padding:8px 4px">
          <div class="donut"><div class="center"><div class="big">${pct}%</div><div class="lab">progreso</div></div></div>
          <div class="legend-col">
            <div class="row"><span class="sw" style="background:var(--green)"></span><b>${prog.done||0}</b> features terminadas</div>
            <div class="row"><span class="sw" style="background:var(--muted-2)"></span><b>${(prog.total||0)-(prog.done||0)}</b> pendientes</div>
            <div class="row" style="font-family:var(--mono);color:var(--muted)">[${bar}]</div>
            <div class="row"><b>${finiteMetric(loopMetrics.iterations,0,1000000)||0}</b> iteraciones del loop</div>
            <div class="row"><b>${finiteMetric(loopMetrics.average_score,0,10)||0}/10</b> calidad media · ${finiteMetric(loopMetrics.below_threshold,0,1000000)||0} bajo umbral</div>
          </div>
        </div>
      </div></div>`;
    (d.plan?.phases||[]).forEach(ph=>{
      const phSt = ph.status==="on_track"?"in":ph.status==="complete"?"in":ph.status==="at_risk"?"nocomp":"unk";
      html += `<div class="card" style="margin-top:14px"><div class="hd"><h3>◉ ${esc(ph.id)} (${esc(ph.timeframe||"")})</h3><div class="grow"></div><span class="tag ${phSt}"><span class="d"></span>${esc(ph.status)}</span></div><div class="bd"><div class="alist" id="rm-${esc(ph.id)}"></div></div></div>`;
    });
    node.innerHTML = html;
    (d.plan?.phases||[]).forEach(ph=>{
      const list = $("#rm-"+ph.id); if(!list) return;
      (ph.features||[]).forEach(f=>{
        const icon = {done:"✓",deployed:"🚀",in_progress:"▶",blocked:"✗",planned:"○",proposed:"?"}[f.status]||"?";
        const stCls = f.status==="done"||f.status==="deployed"?"in":f.status==="in_progress"?"in":f.status==="blocked"?"nocomp":"unk";
        const item = el("div","aitem");
        item.innerHTML = `<div class="ic">${icon}</div>
          <div class="grow"><div class="nm">${esc(f.id)} · ${esc(f.title)}</div>
            <div class="ds">${esc(f.impact||"")}/${esc(f.effort||"")} · ${esc(f.capability||"")}</div></div>
          <span class="tag ${stCls}"><span class="d"></span>${esc(f.status)}</span>`;
        list.appendChild(item);
      });
    });
  }catch(e){
    node.innerHTML = `<div class="empty"><div class="t">No se pudo cargar el roadmap</div><div class="s">${esc(e.message)}</div></div>`;
  }
}
function updateSync(st, before){
  const syncing = !before || (st && st.last_cycle_at && (!before.last_cycle_at || st.last_cycle_at>before.last_cycle_at));
  const se = $("#sync"); se.classList.remove("stale");
  if(st && st.last_cycle_at){
    const dt = parseTime(st.last_cycle_at);
    const age = dt ? Math.floor((Date.now()-dt.getTime())/1000) : 0;
    $("#syncText").textContent = "Ciclo "+fmt.ago(st.last_cycle_at);
    if(age>180) se.classList.add("stale");
  }
  $("#ratePill").textContent = (st&&st.cycle_period_s? Math.round(st.cycle_period_s/60)+" min" : "15 min");
  const mode = st&&st.mode? st.mode : (App.org && App.org.org ? "live":"simulation");
  // El chip de modo dice también en qué fase del rollout está el tenant:
  // "live · observación" = todo dry-run (nada sale al UEM), "live · enforce"
  // = las acciones de enforcement.live_actions se ejecutan de verdad.
  const enfMode = st && st.enforcement && st.enforcement.mode;
  let modeLabel = (st&&st.mode==="simulation")?"demo":(mode||"live");
  if(st && st.mode !== "simulation" && enfMode) modeLabel += enfMode==="observe" ? " · observación" : " · enforce";
  $("#modeText").textContent = modeLabel;
  $("#modeText").style.color = (st&&st.mode==="simulation")?"var(--amber)":(enfMode==="observe"?"var(--amber)":"var(--green)");
  // Control de fase de enforcement: editable solo por roles con engine:config
  // (owner/admin). Cambia el modo vía el endpoint y refresca el estado. Los
  // demás roles nunca ven el control (solo el chip de lectura de arriba).
  const enfRow = document.getElementById("enfRow");
  const enfSel = document.getElementById("enfSelect");
  if(enfRow && enfSel){
    const role = App.org && App.org.role;
    const canEdit = (role==="owner" || role==="admin") && !!enfMode;
    enfRow.style.display = canEdit ? "flex" : "none";
    if(canEdit){
      if(!enfSel._wired){
        enfSel.addEventListener("change", async ()=>{
          const mode = enfSel.value; enfSel.disabled = true;
          try{
            const r = await api("/api/settings/enforcement", {method:"POST",
              headers:{"Content-Type":"application/json"}, body:JSON.stringify({mode})});
            if(r && r.ok){ toast("Enforcement actualizado", mode==="enforce"?"enforce":"observación", "ok"); refresh(false); }
            else { toast("Error", (r&&r.error)||"No se pudo cambiar el modo", "bad"); enfSel.value = enfMode; }
          }catch(e){ toast("Error", e.message||"fallo de red", "bad"); enfSel.value = enfMode; }
          finally{ enfSel.disabled = false; }
        });
        enfSel._wired = true;
      }
      if(document.activeElement !== enfSel) enfSel.value = enfMode;
    }
  }
  // Banda de datos demo (issue #110): visible solo mientras el backend declara
  // modo simulación; con una organización real desaparecen banda y hueco.
  const demoBanner = document.getElementById("demoBanner");
  if(demoBanner) demoBanner.hidden = !(st && st.mode === "simulation");
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
  const txt = verified ? (opts.short?"Verificado":"Verificado · señal real") : (opts.short?"No verif.":"Sin señal · no verificado");
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
  // One snapshot, one truth: never mix counters from a concurrent engine tick
  // with the device array rendered on this frame.
  const inside = devs.filter(d=>(d.fence_state||"unknown")==="inside").length;
  const outside = devs.filter(d=>(d.fence_state||"unknown")==="outside").length;
  const unknown = devs.length-inside-outside;
  const noncomp = devs.filter(d=>d.compliant===false).length;
  const iosGeo = st.ios_geofence_summary || {};
  const total = devs.length;
  const compPct = total ? Math.round((total-noncomp)/total*100) : 0;
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
        <div class="map-wrap"><div id="overviewMap" class="map-canvas"></div>
          <div class="map-legend"><div class="it"><span class="sw" style="background:var(--green)"></span>Dentro</div>
            <div class="it"><span class="sw" style="background:var(--blue)"></span>Fuera</div>
            <div class="it"><span class="sw" style="background:var(--amber)"></span>Desconocido</div></div>
        </div>
      </div>
      <div class="card">
        <div class="hd"><h3>Conformidad</h3><div class="grow"></div><span class="sub">${compPct}%</span>
          <button class="btn sm" onclick="downloadCompliancePdf()">${I.shield} PDF</button></div>
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
  initMap(devs, "overviewMap");
}
function openAiFromOverview(){ goView("ai"); }

function downloadCompliancePdf(){
  window.location.href = "/api/export?kind=compliance&format=pdf";
}

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
      <button type="button" class="chip${App.mapFilter==="all"?" active":""}" data-f="all">Todos</button>
      <button type="button" class="chip${App.mapFilter==="inside"?" active":""}" data-f="inside">Dentro</button>
      <button type="button" class="chip${App.mapFilter==="outside"?" active":""}" data-f="outside">Fuera</button>
      <button type="button" class="chip${App.mapFilter==="unknown"?" active":""}" data-f="unknown">Desconocidos</button>
    </div><div class="grow"></div>
      <button class="btn sm" onclick="recenterMap()">Centrar</button></div>
    <div class="card"><div class="map-wrap"><div id="fleetMap" class="map-canvas"></div>
      <div class="map-legend"><div class="it"><span class="sw" style="background:var(--green)"></span>Dentro</div>
      <div class="it"><span class="sw" style="background:var(--blue)"></span>Fuera</div>
      <div class="it"><span class="sw" style="background:var(--amber)"></span>Desconocido</div></div></div></div>`;
  $$("#mapFilters .chip").forEach(c=>c.onclick=()=>{
    $$("#mapFilters .chip").forEach(x=>x.classList.remove("active")); c.classList.add("active");
    App.mapFilter=c.dataset.f; drawMapMarkers(App.status.devices||[], App.mapFilter);
  });
  initMap(App.status.devices||[], "fleetMap");
}
function recenterMap(){ if(App.map) App.map.setView([40.42,-3.70], 6); }

/* ---------- MAP engine (Leaflet) ---------- */
// Estilo de mapa: "local" (SVG vendorizado, cero red — el DEFECTO, Constitución I)
// u "osm" (teselas reales de openstreetmap.org, SOLO opt-in explícito del admin:
// cada tesela pedida revela al proveedor la zona del visor, aunque jamás se
// envían posiciones ni inventario). La elección vive en localStorage.
function mapStyleIsOSM(){ try{ return localStorage.getItem("lf_map_style")==="osm"; }catch(_e){ return false; } }
function basemapLayer(){
  return mapStyleIsOSM()
    ? L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        {maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'})
    : L.imageOverlay("/static/vendor/offline-map.svg", [[-85.05112878,-180],[85.05112878,180]], {opacity:1, interactive:false});
}
function toggleMapStyle(){
  if(!mapStyleIsOSM()){
    const msg = "Mapa detallado (OpenStreetMap)\n\n" +
      "El fondo del mapa se descargará de openstreetmap.org. Cada movimiento del visor " +
      "revela a ese servicio la zona del mapa que estás mirando (aprox. el área de tu flota). " +
      "Tus dispositivos, posiciones e inventario NUNCA se envían: solo se piden las imágenes del fondo.\n\n" +
      "¿Activar el mapa detallado?";
    if(!confirm(msg)) return;
    try{ localStorage.setItem("lf_map_style","osm"); }catch(_e){}
  } else {
    try{ localStorage.setItem("lf_map_style","local"); }catch(_e){}
  }
  if(App.map){
    const nodeId = App.map.getContainer().id;
    App.map.remove(); App.map=null; App.mapMarkers={}; App.trailLayer=null;
    initMap((App.status&&App.status.devices)||[], nodeId);
  }
}
const MapStyleControl = L.Control ? L.Control.extend({
  options:{position:"bottomright"},
  onAdd(){
    const b=L.DomUtil.create("button","map-style-btn");
    b.type="button";
    b.textContent = mapStyleIsOSM() ? "Mapa local" : "Mapa detallado";
    b.title = mapStyleIsOSM()
      ? "Volver al mapa local (cero peticiones de red)"
      : "Fondo real de OpenStreetMap (opt-in: pide teselas a un tercero)";
    b.style.cssText="background:var(--panel,#141924);color:var(--fg,#e6e9f0);border:1px solid var(--line,#232a3a);border-radius:6px;padding:5px 10px;font:12px system-ui;cursor:pointer";
    L.DomEvent.on(b,"click",(e)=>{ L.DomEvent.stop(e); toggleMapStyle(); });
    return b;
  }
}) : null;
function initMap(devs, targetId){
  if(typeof L === "undefined") return;
  const node=document.getElementById(targetId); if(!node) return;
  // Each view owns a distinct map node. Rebuild when navigation or refresh
  // replaces the currently bound container.
  if(App.map && App.map.getContainer() !== node){
    App.map.remove();
    App.map=null; App.mapMarkers={}; App.trailLayer=null;
  }
  if(!App.map){
    App.map = L.map(node, {zoomControl:true, attributionControl:mapStyleIsOSM()}).setView([40.42,-3.70], 6);
    // Basemap por defecto: vector vendorizado, sin proveedor de teselas ni red.
    // El fondo OSM real existe SOLO como opt-in explícito (ver basemapLayer).
    basemapLayer().addTo(App.map);
    if(MapStyleControl) new MapStyleControl().addTo(App.map);
    App.trailLayer = L.layerGroup().addTo(App.map);
    const settleMap = (attempt=0)=>{
      if(!App.map || App.map.getContainer()!==node) return;
      const box=node.getBoundingClientRect();
      if(box.width>0 && box.height>0){
        App.map.invalidateSize({pan:false,animate:false});
        return;
      }
      if(attempt<12) setTimeout(()=>settleMap(attempt+1), 50);
    };
    requestAnimationFrame(()=>requestAnimationFrame(()=>settleMap()));
  }
  drawMapMarkers(devs, App.mapFilter);
}
function drawMapMarkers(devs, filter){
  if(!App.map) return;
  Object.values(App.mapMarkers).forEach(m=>App.map.removeLayer(m)); App.mapMarkers={};
  App.trailLayer.clearLayers();
  const colorFor = (s)=> s==="inside"?"#4cc38a": s==="outside"?"#4ea7fc":"#f2c94c";
  const collisions = new Map();
  (devs||[]).forEach(d=>{
    if(filter && filter!=="all" && (d.fence_state||"unknown")!==filter) return;
    const lat=d.lat, lng=d.lng; if(lat==null||lng==null) return;
    const col = colorFor(d.fence_state||"unknown");
    // Devices may report the exact same site coordinate. Spread only their
    // visual marker in a tiny deterministic ring; popup/trail retain truth.
    const collisionKey = `${Number(lat).toFixed(4)},${Number(lng).toFixed(4)}`;
    const collisionIndex = collisions.get(collisionKey)||0;
    collisions.set(collisionKey, collisionIndex+1);
    const angle = collisionIndex*2.399963;
    const radius = collisionIndex ? .035*Math.ceil(collisionIndex/6) : 0;
    const markerLat = Number(lat)+Math.sin(angle)*radius;
    const markerLng = Number(lng)+Math.cos(angle)*radius;
    const m = L.circleMarker([markerLat,markerLng], {radius:7, color:col, weight:2, fillColor:col, fillOpacity:.8});
    m.bindPopup(`<b>${esc(d.name)}</b><br><span style="font-size:11px;color:#888">${esc(d.platform||"")} · ${(d.fence_state||"unknown")}</span>`);
    m.on("click", ()=>openDeviceModal(d.device_id));
    m.addTo(App.map); App.mapMarkers[d.device_id]=m;
    // trail
    const tr = (d.trail||[]).slice(-30);
    if(tr.length>1){
      L.polyline(tr.map(p=>[p.lat,p.lng]).filter(p=>p[0]!=null&&p[1]!=null), {color:col, weight:1.5, opacity:.4}).addTo(App.trailLayer);
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
        <button type="button" class="chip active" data-f="all">Todos</button>
        <button type="button" class="chip" data-f="inside">Dentro</button>
        <button type="button" class="chip" data-f="outside">Fuera</button>
        <button type="button" class="chip" data-f="unknown">Desconocidos</button>
        <button type="button" class="chip" data-f="noncompliant">Incumplen</button>
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
      <td class="mono">${esc(d.city||d.country|| (d.lat!=null&&d.lng!=null?d.lat.toFixed(2)+","+d.lng.toFixed(2):"—"))}</td>
      <td class="mono">${fmt.ago(d.last_seen)}</td>
      <td>${verifiedCell}</td>
      <td><span class="plat" style="cursor:pointer" onclick="openDeviceModal('${esc(d.device_id)}')">${I.act}</span></td>`;
    tr.onclick = ()=>openDeviceModal(d.device_id);
    tb.appendChild(tr);
  });
}

/* ---------- device modal ---------- */
async function openDeviceModal(id){
  App._modalReturnFocus = document.activeElement;
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
    ["Ubicación", d.lat!=null&&d.lng!=null? `${d.lat.toFixed(4)}, ${d.lng.toFixed(4)}`:"—"],
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
      basemapLayer().addTo(tm);
      L.polyline(tr.map(p=>[p.lat,p.lng]).filter(p=>p[0]!=null&&p[1]!=null), {color:"#5e6ad5",weight:2}).addTo(tm);
      tr.forEach(p=>{ if(p.lat!=null&&p.lng!=null) L.circleMarker([p.lat,p.lng],{radius:3,color:"#5e6ad5",fillOpacity:.7}).addTo(tm); });
      setTimeout(()=>tm.invalidateSize(),40);
    }
    const evs = (det.events||[]).slice(-8).reverse();
    $("#mEvents").innerHTML = "";
    renderEventList($("#mEvents"), evs.map(e=>({...e, kind:e.kind||"info", text:e.text||e.msg})));
    // Doble llave del wipe: el operador ve ANTES de pulsar si el borrado es
    // irreversible (LIVE), está bloqueado por la doble llave, o se simula.
    // Datos ya serializados en st.enforcement (allow_wipe/wipe_allowlist_size);
    // la fuente de verdad sigue siendo el servidor (engine bloquea igual).
    const enf = (App.status && App.status.enforcement) || {};
    const sim = App.status && App.status.mode === "simulation";
    const wipeLive = !sim && enf.mode === "enforce" && enf.allow_wipe === true;
    const wb = document.getElementById("cmdWipe"), wk = document.getElementById("wipeKey");
    if(wb && wk){
      wb.classList.toggle("danger", !!wipeLive);
      if(wipeLive){
        wk.textContent="LIVE"; wk.style.color="var(--red)";
        wb.title="Wipe EN VIVO e irreversible · alcance: "+(enf.wipe_allowlist_size?("allowlist ("+enf.wipe_allowlist_size+")"):"toda la flota");
      } else if(enf.mode==="enforce" && !enf.allow_wipe){
        wk.textContent="doble llave"; wk.style.color="var(--amber)";
        wb.title="Wipe con doble llave: enforcement.allow_wipe está desactivada (valor seguro por defecto). El servidor bloqueará el borrado hasta armarla en la config del tenant.";
      } else {
        wk.textContent="simulado"; wk.style.color="var(--muted)";
        wb.title="Wipe se simula (dry-run) en fase observación: no toca el dispositivo.";
      }
    }
    // remote commands wiring
    $$("#mCmd [data-cmd]").forEach(btn=>{
      btn.onclick = async ()=>{
        const cmd = btn.dataset.cmd;
        if(cmd==="wipe"){
          const msg = wipeLive
            ? "BORRADO IRREVERSIBLE de "+id+". Sale EN VIVO al UEM y no se puede deshacer. ¿Continuar?"
            : "Simular borrado (wipe) de "+id+"? En esta fase no toca el dispositivo real.";
          if(!confirm(msg)) return;
        }
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
  $("#ovl").classList.add("show"); $("#devModal").classList.add("show"); $("#devModal").setAttribute("aria-hidden","false");
  $("#mClose").focus();
  if(App.map) App.map.closePopup();
}
function closeModal(){
  $("#ovl").classList.remove("show"); $("#devModal").classList.remove("show"); $("#devModal").setAttribute("aria-hidden","true");
  if(App._modalReturnFocus && document.contains(App._modalReturnFocus)) App._modalReturnFocus.focus();
  App._modalReturnFocus=null;
}
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
      <button type="button" class="chip active" data-f="all">Todos</button>
      <button type="button" class="chip" data-f="enter">Entradas</button>
      <button type="button" class="chip" data-f="exit">Salidas</button>
      <button type="button" class="chip" data-f="action">Acciones</button>
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
      <button type="button" class="chip ${incidentFilter==='active'?'active':''}" data-f="active">Activos</button>
      <button type="button" class="chip ${incidentFilter==='open'?'active':''}" data-f="open">Abiertos</button>
      <button type="button" class="chip ${incidentFilter==='acknowledged'?'active':''}" data-f="acknowledged">En investigación</button>
      <button type="button" class="chip ${incidentFilter==='resolved'?'active':''}" data-f="resolved">Resueltos</button>
      <button type="button" class="chip ${incidentFilter==='all'?'active':''}" data-f="all">Todos</button>
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
    const acts = (p.actions||[]).map(a=>{
      const gate = (a.action==="lock"||a.action==="wipe"||a.action==="clear_passcode"||a.action==="reboot")
        ? ` <span class="tag warn" title="Acción destructiva: pausada para aprobación manual (SOAR human-gate)">human-gate</span>` : "";
      return `<span class="chip">${esc(a.action)}</span>${gate}`;
    }).join(" ");
    return `<div class="soar-pb">
      <div class="soar-pb-h"><b>${esc(p.name)}</b> ${p.enabled?`<span class="tag ok">activo</span>`:`<span class="tag">inactivo</span>`} ${fired?`<span class="nav-badge">${fired}</span>`:""}</div>
      <div class="sub">${esc(p.description||"")}</div>
      <div class="soar-acts">${acts||"<span class='sub'>sin acciones</span>"}</div>
    </div>`;
  }).join("");

  // Playbooks del tenant (REQ §5: editables desde la UI, sin código).
  const tpb = (soar.tenant_playbooks||[]).map(p=>{
    const fired = (soar.matched||[]).filter(m=>m.playbook_id===p.id).length;
    const acts = (p.actions||[]).map(a=>{
      const gate = (a.action==="lock"||a.action==="wipe"||a.action==="clear_passcode"||a.action==="reboot")
        ? ` <span class="tag warn">human-gate</span>` : "";
      return `<span class="chip">${esc(a.action)}</span>${gate}`;
    }).join(" ");
    const cond = esc(JSON.stringify(p.condition||{}));
    return `<div class="soar-pb" data-pb="${esc(p.id)}">
      <div class="soar-pb-h"><b>${esc(p.name)}</b>
        <button class="mini" onclick="soarToggle('${esc(p.id)}', ${p.enabled?false:true})">${p.enabled?"desactivar":"activar"}</button>
        <button class="mini danger" onclick="soarDelete('${esc(p.id)}')">borrar</button>
        ${fired?`<span class="nav-badge">${fired}</span>`:""}</div>
      <div class="sub">condición: <code>${cond}</code></div>
      <div class="soar-acts">${acts||"<span class='sub'>sin acciones</span>"}</div>
    </div>`;
  }).join("");

  const errs = (soar.tenant_playbook_errors||[]);
  const errBlock = errs.length
    ? `<div class="warn" style="margin-top:8px">⚠ Playbooks con errores de validación (no se evalúan):<ul>${errs.map(e=>`<li>${esc(e)}</li>`).join("")}</ul></div>` : "";

  // Matriz de capacidades por UEM (diseño §3.1 / REQ §3).
  const cap = soar.capability_matrix||{};
  const capRows = Object.keys(cap).sort().map(name=>{
    const c = cap[name];
    const dry = (c.dry_run_actions||[]).map(a=>`<span class="tag warn" title="Endpoint pendiente de validar: se construye como handoff dry-run, no se ejecuta">${esc(a)}*</span>`).join(" ");
    const real = (c.actions||[]).map(a=>`<span class="chip">${esc(a)}</span>`).join(" ");
    const inv = c.inventory?`<span class="tag ok">inventario</span>`:"";
    const loc = c.location?`<span class="tag ok">ubicación</span>`:"";
    const nf = c.native_geofences?`<span class="tag ok">geovallas</span>`:"";
    return `<tr><td><b>${esc(name)}</b></td><td>${inv}${loc}${nf}</td>
      <td>${real||"<span class='sub'>solo inventario</span>"}</td><td>${dry||"—"}</td></tr>`;
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
        <div class="soar-pbs">${pbs||"<div class='sub'>Sin playbooks</div>"}</div>
        <div style="margin-top:14px;border-top:1px solid var(--line);padding-top:10px">
          <h4>Playbooks del tenant</h4>
          <div class="soar-pbs">${tpb||"<div class='sub'>Aún no has creado playbooks propios.</div>"}</div>
          ${errBlock}
          <button class="btn" onclick="soarNew()">+ Nuevo playbook</button>
          <div id="soarNew" style="display:none;margin-top:10px"></div>
        </div></div>
      <div class="card"><div class="hd"><h3>${I.bolt} Coincidencias activas</h3><div class="grow"></div>
        <span class="sub">${(soar.matched||[]).length} ejecuciones este ciclo</span></div>
        <div class="tl">${hits||emptyState("Sin coincidencias","Ningún playbook coincide con el estado actual de la flota.")}</div></div>
    </div>
    <div class="card" style="margin-top:14px"><div class="hd"><h3>${I.shieldAlert} Matriz de capacidades por UEM</h3><div class="grow"></div>
      <span class="sub">La consola solo ofrece acciones que el UEM soporta</span></div>
      <div class="tbl"><table class="mini"><thead><tr><th>UEM</th><th>Capacidades</th><th>Acciones live</th><th>Dry-run (pendiente validar)</th></tr></thead>
      <tbody>${capRows||"<tr><td colspan=4 class='sub'>sin matriz</td></tr>"}</tbody></table></div></div>
    <div class="card" style="margin-top:14px"><div class="hd"><h3>${I.shieldAlert} Inventario CVE por dispositivo</h3><div class="grow"></div>
      <span class="sub">${ (cve.devices||[]).filter(d=>(d.apps||[]).some(a=>a.cves)).length } dispositivos con apps vulnerables</span></div>
      <div class="soar-devs">${devRows||"<div class='sub'>Sin apps vulnerables detectadas</div>"}</div></div>`;
}

// ---- Editor de playbooks del tenant (REQ §5) --------------------------
function soarNew(){
  const n = $("#soarNew"); if(!n) return;
  n.style.display = n.style.display==="none"?"block":"none";
  if(n.style.display!=="block") return;
  n.innerHTML = `<div class="card">
    <div class="row"><input id="spId" class="inp" placeholder="id (p.ej. soar-cliente-x)"></div>
    <div class="row"><input id="spName" class="inp" placeholder="nombre"></div>
    <div class="row"><input id="spSev" class="inp" placeholder="severidad mínima (low/medium/high/critical)" value="high"></div>
    <div class="row"><textarea id="spCond" class="inp" rows="4" placeholder='condición JSON: {"all":[{"field":"compliant","op":"eq","value":false},{"field":"fence_state","op":"eq","value":"outside"}]}'></textarea></div>
    <div class="row"><input id="spActions" class="inp" placeholder='acciones JSON: [{"action":"notify","params":{"channel":"soc"}},{"action":"lock","params":{}}]'></div>
    <div class="row"><button class="btn" onclick="soarCreate()">Guardar playbook</button> <span id="spMsg" class="sub"></span></div>
  </div>`;
}
async function soarCreate(){
  const id = $("#spId").value.trim(), name = $("#spName").value.trim();
  const cond = $("#spCond").value.trim(), actions = $("#spActions").value.trim();
  const sev = $("#spSev").value.trim()||"high";
  const msg = $("#spMsg"); if(!msg) return;
  if(!id||!name||!cond||!actions){ msg.textContent="completa id, nombre, condición y acciones"; return; }
  let condObj, actsObj;
  try{ condObj = JSON.parse(cond); actsObj = JSON.parse(actions); }
  catch(e){ msg.textContent="JSON inválido: "+e.message; return; }
  try{
    const r = await api("/api/soar/playbooks", "POST", {id, name, severity_min:sev, condition:condObj, actions:actsObj});
    if(r && r.ok){ msg.textContent="✓ creado"; loadSoar(); }
    else msg.textContent = "error: " + ((r&&r.error)||"desconocido");
  }catch(e){ msg.textContent = "error: "+e.message; }
}
async function soarToggle(id, enabled){
  try{ await api(`/api/soar/playbook/${encodeURIComponent(id)}/enable`, "POST", {enabled}); loadSoar(); }catch(e){}
}
async function soarDelete(id){
  if(!confirm("¿Borrar el playbook "+id+"?")) return;
  try{ await api(`/api/soar/playbook/${encodeURIComponent(id)}`, "DELETE"); loadSoar(); }catch(e){}
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
    <div class="view-head"><div><h2>Conectores locales</h2><div class="sub">LucidFence funciona en Demo sin credenciales. Activa solo los servicios que quieras conectar.</div></div></div>
    <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;align-items:start">
      <div class="card"><div class="hd"><h3>Fuente UEM / MDM</h3><div class="grow"></div><span class="tag in"><span class="d"></span>tenant-local</span></div>
        <div class="bd" id="setBody"><div class="sk" style="height:260px"></div></div></div>
      <div class="card"><div class="hd"><h3>Proveedor AI opcional</h3><div class="grow"></div><span class="tag unk"><span class="d"></span>BYO API</span></div>
        <div class="bd" id="aiSetBody"><div class="sk" style="height:260px"></div></div></div>
    </div>`;
  let s={}, ai={};
  try{ [s,ai] = await Promise.all([api("/api/settings/status"), api("/api/ai/settings")]); }catch(e){}
  const mode = s.mode||"simulation";
  $("#setBody").innerHTML = `
    <div class="field"><label>Conector</label><select class="input" id="sProvider">
      <option value="simulation" ${mode==='simulation'?'selected':''}>Demo local · sin claves</option>
      <option value="applivery" ${mode==='live'?'selected':''}>Applivery UEM</option>
      <option value="intune" disabled>Microsoft Intune · preview del adapter</option>
      <option value="jamf" disabled>Jamf Pro · preview del adapter</option>
    </select><div class="help">Intune y Jamf están en el SDK comunitario, pero el inventario live aún no se activa para no prometer una integración incompleta.</div></div>
    <div id="uemFields">
      <div class="field"><label>Token de Applivery (Bearer)</label><div class="input-wrap"><input class="input" id="sKey" type="password" placeholder="${s.configured?'Dejar vacío para conservar':'Pega el token aquí'}"><button class="toggle" onclick="toggleShow('sKey',this)">Ver</button></div>
        <div class="help">${s.configured?"Configurado: <b>"+esc(s.masked_key||"")+"</b>":"No configurado"}</div></div>
      <div class="field"><label>Organization / Workspace ID</label><input class="input" id="sOrg" placeholder="org_…" value="${esc(s.org_id||"")}"></div>
    </div>
    <div class="switch-row"><div style="flex:1"><div class="lab">Dry-run</div><div class="ds">Recomendado: calcula y audita sin ejecutar comandos reales.</div></div><div class="switch ${s.dry_run?'on':''}" id="sDry"></div></div>
    <div style="display:flex;gap:8px;margin-top:14px"><button class="btn outline" id="sTest">Probar conexión</button><button class="btn primary" id="sSave">Guardar UEM</button></div>
    <div id="sResult" class="test-result" style="margin-top:14px"></div>`;
  const syncUemFields=()=>{ $("#uemFields").style.display=$("#sProvider").value==='applivery'?'block':'none'; $("#sTest").style.display=$("#sProvider").value==='applivery'?'inline-flex':'none'; };
  $("#sProvider").onchange=syncUemFields; syncUemFields();
  $("#sDry").onclick=()=>$("#sDry").classList.toggle("on");
  $("#sTest").onclick=async()=>{
    const r=await api("/api/settings/test",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({api_key:$("#sKey").value})});
    const out=$("#sResult"); out.className="test-result "+(r.ok?"ok show":"bad show"); out.textContent=r.message||(r.ok?"Conexión verificada.":r.error||"Fallo de conexión");
  };
  $("#sSave").onclick=async()=>{
    const provider=$("#sProvider").value, live=provider==='applivery';
    const payload={api_key:live?$("#sKey").value:null,org_id:live?$("#sOrg").value:null,mode:live?'live':'simulation',dry_run:$("#sDry").classList.contains("on")};
    const r=await api("/api/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    if(r.ok){toast("UEM guardado",live?"Applivery":"Demo local","ok");refresh(false);}else toast("Error",r.error||"","bad");
  };
  // --- Validate-config: verify the location_source mapping against the live UEM/MDM API.
  const vcard=document.createElement("div"); vcard.className="card"; vcard.style.marginTop="14px";
  vcard.innerHTML='<div class="hd"><h3>Validar mapeo UEM (cualquier fabricante)</h3></div>'+
    '<div class="bd"><div class="help">Prueba tu bloque <code>location_source</code> de config.json contra la API real y ver que campos resuelven. Sirve para Fleet, Intune, Jamf, Mosyle, Workspace ONE o tu endpoint.</div>'+
    '<div style="display:flex;gap:8px;margin-top:10px"><button class="btn outline" id="vBtn">Validar config</button></div>'+
    '<div id="vResult" style="margin-top:12px;font-family:monospace;white-space:pre-wrap;font-size:12px"></div></div>';
  $("#view-settings").appendChild(vcard);
  $("#vBtn").onclick=async()=>{
    const out=$("#vResult"); out.textContent="validando…";
    const r=await api("/api/config/validate");
    if(!r){ out.textContent="sin respuesta"; return; }
    if(r.reason){ out.textContent="SKIP: "+r.reason; return; }
    const lines=[];
    lines.push("URL: "+(r.url||"-"));
    lines.push("Dispositivos: crudos "+(r.devices_raw??0)+" · con geo "+(r.devices_with_geo??0)+" · sin geo "+(r.devices_dropped_no_geo??0));
    if(r.fetch_error) lines.push("FETCH ERROR: "+JSON.stringify(r.fetch_error));
    lines.push("Campos:");
    for(const [k,v] of Object.entries(r.field_resolution||{})){
      const flag = v.resolved===v.total&&v.total ? "OK" : (v.resolved? "PARCIAL":"FALTA");
      lines.push("  "+k.padEnd(12)+" "+v.path.padEnd(28)+" "+v.resolved+"/"+v.total+"  ["+flag+"]");
    }
    lines.push("RESULTADO: "+(r.ok?"OK":"REVISAR MAPEO"));
    out.textContent=lines.join("\n");
  };

  // --- Egress de webhooks salientes (t_f33e2f23): policy + visibilidad de denegaciones.
  renderEgressCard(s);

  const presets=ai.presets||[];
  $("#aiSetBody").innerHTML=`
    <div class="switch-row"><div style="flex:1"><div class="lab">Habilitar AI</div><div class="ds">Opcional. La clave se guarda localmente con permisos 0600.</div></div><div class="switch ${ai.enabled?'on':''}" id="aiEnabled"></div></div>
    <div class="field"><label>Preset</label><select class="input" id="aiPreset">${presets.map(p=>`<option value="${esc(p.id)}" data-url="${esc(p.base_url||'')}" ${p.id===ai.provider?'selected':''}>${esc(p.name)}</option>`).join("")}</select></div>
    <div class="field"><label>Base URL OpenAI-compatible</label><input class="input mono" id="aiBase" value="${esc(ai.base_url||'')}" placeholder="http://127.0.0.1:11434/v1"></div>
    <div class="field"><label>Modelo</label><input class="input mono" id="aiModel" value="${esc(ai.model||'')}" placeholder="gpt-4.1-mini, llama3.2…"></div>
    <div class="field"><label>API key <span class="sub">(opcional para modelos locales)</span></label><div class="input-wrap"><input class="input" id="aiKey" type="password" placeholder="${ai.key_configured?'Dejar vacío para conservar':'sk-…'}"><button class="toggle" onclick="toggleShow('aiKey',this)">Ver</button></div><div class="help">${ai.key_configured?'Configurada: <b>'+esc(ai.masked_key||'')+'</b>':'Sin clave configurada'}</div></div>
    <div style="display:flex;gap:8px"><button class="btn outline" id="aiTest">Probar modelo</button><button class="btn primary" id="aiSave">Guardar AI</button></div>
    <div id="aiResult" class="test-result" style="margin-top:14px"></div>
    <div class="help" style="margin-top:14px">Gateway local: <code>${esc(window.location.origin)}/v1/chat/completions</code> · MCP: <code>lucidfence mcp</code></div>`;
  $("#aiEnabled").onclick=()=>$("#aiEnabled").classList.toggle("on");
  $("#aiPreset").onchange=()=>{const o=$("#aiPreset").selectedOptions[0];if(o.dataset.url)$("#aiBase").value=o.dataset.url;if(o.value==='disabled')$("#aiEnabled").classList.remove("on");};
  const aiPayload=()=>({enabled:$("#aiEnabled").classList.contains("on"),provider:$("#aiPreset").value,base_url:$("#aiBase").value,model:$("#aiModel").value,api_key:$("#aiKey").value});
  $("#aiSave").onclick=async()=>{const r=await api("/api/ai/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(aiPayload())});if(r.ok){toast("AI guardada",r.enabled?r.model:"Desactivada","ok");renderSettings();}else toast("Error",r.error||"","bad");};
  $("#aiTest").onclick=async()=>{const r=await api("/api/ai/test",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(aiPayload())});const out=$("#aiResult");out.className="test-result "+(r.ok?"ok show":"bad show");out.textContent=r.ok?`Conexión correcta · ${(r.models||[]).slice(0,3).join(', ')||'endpoint activo'}`:(r.error||"Fallo de conexión");};

  // Equipo / Roles: gestionar RBAC desde el dashboard. Solo lo ve el owner,
  // que es el único rol con la capability user:role en el backend.
  renderTeamCard();
  // Registro de auditoría: hace visible el log encadenado (a prueba de
  // manipulación) que ya se escribe en cada acción privilegiada. Da al rol
  // auditor una pantalla y responde "quién cambió qué" sin abrir audit.jsonl.
  renderAuditCard();
}

/* ===================== EGRESS DE WEBHOOKS SALIENTES (t_f33e2f23) ===================== */
async function renderEgressCard(s){
  const node = document.createElement("div");
  node.className = "card";
  node.style.marginTop = "14px";
  node.innerHTML = `
    <div class="hd"><h3>Egress de webhooks salientes</h3><div class="grow"></div><span class="tag unk"><span class="d"></span>opt-in</span></div>
    <div class="bd">
      <div class="help">Controla a qué destinos LucidFence puede entregar webhooks de incidente (Slack/Teams, genérico firmado, ntfy). Por defecto <b>permisivo</b> (comportamiento actual). El modo <b>estricto</b> solo entrega a los hosts de la allow-list y nunca silencia una denegación.</div>
      <div class="field"><label>Modo</label><select class="input" id="egMode">
        <option value="permissive">permisivo (allow-all, comportamiento actual)</option>
        <option value="strict">estricto (solo allow-list)</option>
      </select></div>
      <div id="egStrictFields" style="display:none">
        <div class="field"><label>Allow-list (host exacto, sufijo .dominio o IP; uno por línea)</label>
          <textarea class="input" id="egAllow" rows="3" placeholder="hooks.slack.com&#10;.slack.com&#10;10.20.30.40"></textarea>
          <div class="help">Sin comodín global <code>*</code>. En estricto, loopback/link-local/metadata 169.254.0.0/16 siguen siempre bloqueados (defense-in-depth).</div>
        </div>
        <div class="switch-row"><div style="flex:1"><div class="lab">Permitir destinos privados (RFC1918)</div><div class="ds">En estricto, permite SIEM internos/red bloqueada. Si está off, el egress privado se deniega aunque el host esté listado.</div></div><div class="switch" id="egPrivate"></div></div>
      </div>
      <div id="egDelivery" class="test-result" style="margin-top:12px"></div>
      <div style="display:flex;gap:8px;margin-top:12px"><button class="btn primary" id="egSave">Guardar egress</button></div>
    </div>`;
  $("#view-settings").appendChild(node);

  const eg = (s && s.egress_policy) || {mode:"permissive"};
  $("#egMode").value = eg.mode || "permissive";
  if(eg.mode === "strict"){
    $("#egStrictFields").style.display = "block";
    $("#egAllow").value = ((eg.allow||[]).join("\n"));
    if(eg.allow_private) $("#egPrivate").classList.add("on");
  }
  $("#egMode").onchange = ()=>{ $("#egStrictFields").style.display = $("#egMode").value==="strict" ? "block":"none"; };
  $("#egPrivate").onclick = ()=> $("#egPrivate").classList.toggle("on");

  const renderDelivery = (d)=>{
    const box = $("#egDelivery");
    if(!d || !d.configured){ box.className="test-result"; box.textContent=""; return; }
    const lr = d.last_result;
    const denied = JSON.stringify(lr||"").includes("denied_by_egress_policy");
    if(denied){
      box.className = "test-result bad show";
      box.textContent = "Última entrega DENEGADA por egress policy (denied_by_egress_policy) — visible, no silenciada.";
    } else if(lr && lr.ok){
      box.className = "test-result ok show";
      box.textContent = "Última entrega: OK.";
    } else if(lr){
      box.className = "test-result";
      box.textContent = "Última entrega: " + (lr.error || (lr.result || "sin resultado"));
    } else {
      box.className = "test-result";
      box.textContent = "Sin entregas recientes.";
    }
  };
  renderDelivery(s && s.webhook_delivery);

  $("#egSave").onclick = async ()=>{
    const mode = $("#egMode").value;
    const policy = { mode };
    if(mode === "strict"){
      const allow = $("#egAllow").value.split("\n").map(x=>x.trim().toLowerCase()).filter(Boolean);
      policy.allow = allow;
      policy.allow_private = $("#egPrivate").classList.contains("on");
    }
    // Persist alongside the (possibly empty) incident webhook URL.
    const cur = (s && s.incident_webhook_url) || "";
    const r = await api("/api/settings/incident-webhook", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({url: cur, egress_policy: policy})});
    if(r.ok){ toast("Egress guardado", policy.mode==="strict" ? "estricto · "+((policy.allow||[]).length)+" hosts" : "permisivo", "ok"); renderSettings(); }
    else toast("Error", r.error||"", "bad");
  };
}



async function renderAuditCard(){
  // Mismo círculo que autoriza el backend en GET /api/audit (403 en otro caso).
  if(!(App.org && ["owner","admin","viewer","auditor"].includes(App.org.role))) return;
  const card=document.createElement("div"); card.className="card"; card.style.marginTop="14px";
  card.innerHTML='<div class="hd"><h3>Registro de auditoría</h3><div class="grow"></div>'+
    '<span class="tag unk" id="auditIntegrity"><span class="d"></span>comprobando…</span></div>'+
    '<div class="bd" id="auditBody"><div class="sk" style="height:200px"></div></div>';
  $("#view-settings").appendChild(card);
  let data;
  try{ data = await api("/api/audit"); }
  catch(e){ $("#auditBody").innerHTML=`<div class="help">No se pudo cargar la auditoría: ${esc(e.message||"")}</div>`; return; }
  const integ = data.integrity||{};
  const chip = $("#auditIntegrity");
  if(integ.ok){ chip.className="tag in"; chip.innerHTML=`<span class="d"></span>cadena íntegra · ${integ.events||0} eventos`; }
  else { chip.className="tag nocomp"; chip.innerHTML=`<span class="d"></span>cadena alterada${integ.error?": "+esc(integ.error):""}`; }
  // Detalle compacto: solo campos relevantes de cada evento (whitelist).
  const DETAIL_KEYS=["mode","role","key_id","goal_id","segment","provider","target"];
  const detail=(e)=>DETAIL_KEYS.filter(k=>e[k]!=null&&e[k]!=="").map(k=>`${esc(k)}=${esc(e[k])}`).join(" · ");
  const events=(data.events||[]).slice(-100).reverse();
  const rows=events.map(e=>`<tr>
      <td class="sub" style="white-space:nowrap">${esc(e.ts||"")}</td>
      <td><b>${esc(e.event||"evento")}</b></td>
      <td class="sub">${esc(e.actor||"—")}</td>
      <td class="sub" style="font-family:monospace;font-size:11px">${detail(e)}</td>
    </tr>`).join("");
  $("#auditBody").innerHTML=
    '<div class="help">Cada acción privilegiada (enforcement, roles, claves API, providers, exportaciones) queda registrada en un log <b>encadenado por hash</b>: si alguien altera una línea, la cadena se rompe y se marca arriba.</div>'+
    (rows?`<table class="tbl" style="margin-top:10px;width:100%"><thead><tr><th>Cuándo</th><th>Evento</th><th>Actor</th><th>Detalle</th></tr></thead><tbody>${rows}</tbody></table>`
        :'<div class="help" style="margin-top:10px">Aún no hay eventos de auditoría.</div>')+
    `<details style="margin-top:12px"><summary>Exportar a SIEM (CEF)</summary>`+
    `<textarea class="input" readonly rows="6" style="margin-top:6px;width:100%;font-family:monospace;font-size:11px" onclick="this.select()">${esc((data.cef||[]).join("\n"))}</textarea></details>`;
}

async function renderTeamCard(){
  if(!(App.org && App.org.role === "owner")) return;
  const card=document.createElement("div"); card.className="card"; card.style.marginTop="14px";
  card.innerHTML='<div class="hd"><h3>Equipo · Roles</h3><div class="grow"></div>'+
    '<span class="tag in"><span class="d"></span>solo propietario</span></div>'+
    '<div class="bd" id="teamBody"><div class="sk" style="height:200px"></div></div>';
  $("#view-settings").appendChild(card);
  let data;
  try{ data = await api("/api/members"); }
  catch(e){ $("#teamBody").innerHTML=`<div class="help">No se pudo cargar el equipo: ${esc(e.message||"")}</div>`; return; }
  const roles = data.roles||[];
  const options = (sel)=>roles.map(r=>`<option value="${esc(r.id)}" ${r.id===sel?"selected":""}>${esc(r.label)}</option>`).join("");
  const rows = (data.members||[]).map(m=>{
    const self = m.is_self ? ' <span class="sub">(tú)</span>' : "";
    return `<tr>
      <td><div>${esc(m.name||m.email)}${self}</div><div class="sub">${esc(m.email)}</div></td>
      <td><select class="input" data-uid="${esc(m.id)}" data-current="${esc(m.role)}" style="min-width:150px">${options(m.role)}</select></td>
    </tr>`;
  }).join("");
  const legend = roles.map(r=>`<details style="margin-top:6px"><summary><b>${esc(r.label)}</b> <span class="sub">· ${r.caps.length} permisos</span></summary>`+
    `<div class="sub" style="margin:6px 0 0 12px;font-family:monospace;font-size:11px;line-height:1.5">${r.caps.map(esc).join(" · ")}</div></details>`).join("");
  $("#teamBody").innerHTML=
    '<div class="help">Asigna a cada miembro el <b>mínimo privilegio</b> que necesite. La organización conserva siempre al menos un propietario.</div>'+
    `<table class="tbl" style="margin-top:10px;width:100%"><thead><tr><th>Miembro</th><th>Rol</th></tr></thead><tbody>${rows}</tbody></table>`+
    `<div style="margin-top:14px"><div class="lab">Qué puede cada rol</div>${legend}</div>`;
  $$("#teamBody select[data-uid]").forEach(sel=>{
    sel.addEventListener("change", async ()=>{
      const uid=sel.dataset.uid, role=sel.value, prev=sel.dataset.current;
      sel.disabled=true;
      try{
        const r=await api("/api/members/role",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid,role})});
        if(r && r.ok){ toast("Rol actualizado", (r.member&&r.member.email)+" → "+(r.member&&r.member.role_label), "ok"); renderSettings(); }
        else { toast("Error",(r&&r.error)||"No se pudo cambiar el rol","bad"); sel.value=prev; }
      }catch(e){ toast("Error", e.message||"fallo de red","bad"); sel.value=prev; }
      finally{ sel.disabled=false; }
    });
  });
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
          <div class="t">AI opcional no configurada</div><div class="s">Conecta OpenAI, Ollama, LM Studio, Nous Portal u otro endpoint compatible cuando quieras.</div>
          <button class="btn primary" style="margin-top:12px" onclick="goView('settings')">Configurar proveedor</button></div>`;
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
    <div class="toolbar"><span class="sub">BYO model · los datos solo se envían al endpoint que configures</span><div class="grow"></div><button class="btn outline" onclick="goView('settings')">Configurar AI</button></div>
    <div class="ai-wrap">
      <div class="chat">
        <div class="hd"><div class="ic" style="width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,var(--violet),var(--accent));display:grid;place-items:center;color:#fff">${I.bolt}</div>
          <h3>Analista AI de flota</h3><div class="grow"></div>
          <span class="tag unk"><span class="d"></span>opcional</span></div>
        <div class="msgs" id="aiMsgs"></div>
        <div class="composer">
          <textarea id="aiInput" placeholder="Pregunta sobre tu flota… (ej: ¿qué dispositivos están fuera de su geovalla y por qué?)"></textarea>
          <button class="btn primary" id="aiSend">${I.bolt} Enviar</button>
        </div>
      </div>
      <div class="providers" id="aiProv"><div class="sk" style="height:20px"></div></div>
    </div>`;
  $("#aiSend").onclick = sendAi;
  $("#aiInput").addEventListener("keydown", e=>{ if(e.key==="Enter" && !e.shiftKey){ e.preventDefault(); sendAi(); } });
  loadAiProviders();
  // saludo inicial
  if(!$("#aiMsgs").children.length){
    addAiMsg("ai", "La IA es opcional. Si configuras un endpoint OpenAI-compatible, puedo analizar conformidad, rutas e incidentes con el contexto de esta flota. LucidFence funciona igualmente sin modelo.", null);
  }
}
function addAiMsg(role, text, meta){
  const box = $("#aiMsgs"); if(!box) return;
  const m = el("div", "msg "+role);
  const av = role==="user"? avatarText(App.org&&App.org.org?App.org.org.name:"U") : "AI";
  let metaHtml = "";
  if(meta && (meta.provider||meta.model)){
    metaHtml = `<div class="meta">${esc(meta.provider||"OpenAI-compatible")} · ${esc(meta.model||"modelo configurado")}</div>`;
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
    const r = await api("/api/ai/chat", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({messages})});
    typing.remove();
    if(r.ok){ addAiMsg("ai", r.text||"(sin respuesta)", {provider:r.provider, model:r.model}); }
    else { addAiMsg("ai", "AI no disponible: "+(r.error||"configura un proveedor en Ajustes"), null); }
  }catch(e){
    typing.remove(); addAiMsg("ai", "Error de conexión con el proveedor AI: "+e.message, null);
  }
}
function buildFleetContext(st){
  const devs = st.devices||[];
  const lines = [];
  lines.push(`Total dispositivos: ${devs.length}`);
  lines.push(`Dentro: ${st.inside_count||0} · Fuera: ${st.outside_count||0} · Desconocidos: ${st.unknown_count||0} · Incumplen: ${st.noncompliant||0}`);
  lines.push("Detalle:");
  devs.slice(0,40).forEach(d=>{
    lines.push(`- ${d.name} (${d.platform}) → ${d.fence_state||"desconocido"}${d.compliant===false?" [INCUMPLE]":""} | ${d.city||d.country||""} | ${d.lat!=null&&d.lng!=null?d.lat.toFixed(3)+","+d.lng.toFixed(3):"sin coord"} | visto ${fmt.ago(d.last_seen)} | fuente ${d.location_source||d.source||"?"}`);
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
  const total = devs.length;
  const inside = st.inside_count||0, outside = st.outside_count||0, unknown = st.unknown_count||0;
  const noncomp = st.noncompliant||0;
  const compPct = total ? Math.round((total-noncomp)/total*100) : 0;
  const routesOn = (st.stats&&st.stats.routes_on_route!=null)?st.stats.routes_on_route:0;
  const routesTot = (st.routes||[]).length;
  const fences = (st.fences||[]).length;

  // Objetivos (targets) — configurables aquí
  const goals = [
    {key:"comp", label:"Conformidad de flota", icon:I.shield, target:95, real:compPct, unit:"%", hint:"% dispositivos conformes"},
    {key:"inside", label:"Dispositivos en su geovalla", icon:I.in, target:90, real:total?Math.round(inside/total*100):0, unit:"%", hint:"% dentro de zona asignada"},
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
        <span style="color:${met?'var(--green)':'var(--amber)'};font-weight:600">${met?'Cumplido':'En progreso'}</span>
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

/* ============================================================
   VISTA: INTELIGENCIA DE FLOTA — evidencia local, no predicción
   ============================================================ */
function finiteMetric(value, min=0, max=100){
  if(value===null || value===undefined || value==="") return null;
  const number = Number(value);
  if(!Number.isFinite(number)) return null;
  return Math.max(min, Math.min(max, number));
}
function metricText(value, suffix=""){ return value===null ? "—" : `${value}${suffix}`; }
function safeDuration(value){ const number=finiteMetric(value,0,31536000); return number===null?"—":fmtDur(number); }

async function renderCompany(){
  const node=$("#view-company"); if(!node) return;
  node.innerHTML=`<div class="card" aria-live="polite"><div class="bd"><div class="sub">Cargando control plane por tenant…</div></div></div>`;
  try{
    const data=await api("/api/company");
    const metrics=data.metrics||{}, goals=data.goals||[], tasks=(data.tasks||[]).slice().reverse(), agents=data.agents||[];
    const activeGoals=goals.filter(g=>g.status==="active");
    const riskClass=r=>r==="forbidden"||r==="high"?"nocomp":r==="medium"?"out":"in";
    const statusClass=s=>s==="executed"?"in":s==="blocked"||s==="rejected"?"nocomp":"unk";
    const agentHtml=agents.map(a=>`<div class="company-agent"><b>${esc(a.name)}</b><div class="sub">${esc(a.mission)}</div></div>`).join("");
    const goalHtml=activeGoals.length?activeGoals.map(g=>`<div class="company-task"><div class="row gap wrap"><b style="font-size:12px">${esc(g.title)}</b><span class="tag in"><span class="d"></span>${esc(g.priority)} · ${esc(g.autonomy)}</span></div><div class="sub" style="margin-top:5px">${esc(g.outcome)}</div><div class="sub" style="margin-top:4px">${(g.metrics||[]).map(m=>`${esc(m.name)} → ${esc(m.target)}`).join(" · ")}</div></div>`).join(""):`<div class="sub">No hay objetivo activo. Define un resultado, métrica y límite de autonomía antes de ejecutar ciclos.</div>`;
    const taskHtml=tasks.length?tasks.slice(0,10).map(t=>`<div class="company-task"><div class="row gap wrap"><b style="font-size:12px;flex:1">${esc(t.title)}</b><span class="tag ${riskClass(t.risk)}"><span class="d"></span>${esc(t.risk)}</span><span class="tag ${statusClass(t.status)}"><span class="d"></span>${esc(t.status)}</span></div><div class="sub" style="margin-top:5px">${esc(t.agent_id)} · ${esc(t.action)} · evidencia ${(t.evidence||[]).length}</div>${t.status==="proposed"&&t.requires_approvals>0?`<button class="btn sm companyApprove" data-task="${esc(t.id)}" style="margin-top:8px">Revisar y aprobar handoff</button>`:""}</div>`).join(""):`<div class="sub">El primer ciclo convertirá telemetría real en tareas verificables.</div>`;
    node.innerHTML=`
      <section class="company-hero" aria-labelledby="companyTitle">
        <div class="company-eyebrow">Control plane · tenant scoped · ${data.paused?"PAUSED":"ACTIVE"}</div>
        <h1 id="companyTitle">Compañía autónoma de geofencing</h1>
        <div class="sub" style="max-width:760px">Un equipo digital que observa la flota, forma el squad adecuado y entrega simulaciones o recomendaciones con evidencia. Nunca ejecuta wipe, factory reset ni comandos UEM desde este plano.</div>
        <div class="row gap wrap" style="margin-top:15px"><button class="btn primary" id="companyNewGoal">Nuevo objetivo medible</button><button class="btn" id="companyRun" ${activeGoals.length&&!data.paused?"":"disabled"}>Ejecutar ciclo seguro</button><button class="btn" id="companyPause">${data.paused?"Reanudar compañía":"Pausar compañía"}</button></div>
        <form id="companyGoalForm" class="company-form hidden">
          <label class="sr-only" for="companyGoalTitle">Objetivo</label><input class="input" id="companyGoalTitle" maxlength="160" required placeholder="Objetivo: reducir salidas no autorizadas" />
          <label class="sr-only" for="companyGoalOutcome">Resultado</label><input class="input" id="companyGoalOutcome" maxlength="500" required placeholder="Resultado operativo esperado" />
          <label class="sr-only" for="companyGoalTarget">Meta</label><input class="input" id="companyGoalTarget" type="number" value="0" required title="Meta outside_devices" />
          <select class="input" id="companyGoalAutonomy" aria-label="Nivel de autonomía"><option value="recommend">Recomendar</option><option value="simulate" selected>Simular</option><option value="execute_safe">Ejecutar solo análisis seguros</option><option value="observe">Solo observar</option></select>
          <button class="btn primary" id="companyCreateGoal" type="button">Crear objetivo</button>
        </form>
      </section>
      <div class="kpis"><div class="kpi"><div class="lab">Ciclos</div><div class="val">${data.cycle||0}</div></div><div class="kpi"><div class="lab">Objetivos activos</div><div class="val">${metrics.active_goals||0}</div></div><div class="kpi"><div class="lab">Tareas abiertas</div><div class="val">${metrics.open_tasks||0}</div></div><div class="kpi"><div class="lab">Cobertura de evidencia</div><div class="val">${metrics.evidence_coverage??100}%</div></div><div class="kpi"><div class="lab">Bloqueos de seguridad</div><div class="val">${metrics.safety_blocks||0}</div></div></div>
      <div class="company-layout"><div><div class="card"><div class="hd"><h3>Squad disponible</h3><div class="grow"></div><span class="tag in"><span class="d"></span>${agents.length} roles</span></div><div class="bd"><div class="company-agents">${agentHtml}</div></div></div><div class="card" style="margin-top:14px"><div class="hd"><h3>Cola gobernada</h3></div><div class="bd">${taskHtml}</div></div></div><div><div class="card"><div class="hd"><h3>Objetivos</h3></div><div class="bd">${goalHtml}</div></div><div class="card" style="margin-top:14px"><div class="hd"><h3>Contrato de autonomía</h3></div><div class="bd"><div class="sub">LOW: análisis/simulación local. MEDIUM: una aprobación humana. HIGH: doble aprobación. FORBIDDEN: destrucción, borrado de tenant o desactivación de auditoría.</div></div></div></div></div>`;
    $("#companyNewGoal").onclick=()=>$("#companyGoalForm").classList.toggle("hidden");
    $("#companyCreateGoal").onclick=async()=>{ const form=$("#companyGoalForm"); if(!form.reportValidity())return; try{ await api("/api/company/goals",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({title:$("#companyGoalTitle").value,outcome:$("#companyGoalOutcome").value,metrics:[{name:"outside_devices",target:Number($("#companyGoalTarget").value),direction:"max"}],constraints:["No ejecutar acciones destructivas","Exigir evidencia y rollback"],priority:"p0",autonomy:$("#companyGoalAutonomy").value})}); toast("Objetivo creado","La compañía ya puede priorizar ciclos","good"); renderCompany(); }catch(err){toast("Objetivo no creado",err.message,"bad");} };
    $("#companyRun").onclick=async()=>{try{const r=await api("/api/company/cycle",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});toast("Ciclo completado",`${r.created_tasks.length} tareas con evidencia`,"good");renderCompany();}catch(err){toast("Ciclo detenido",err.message,"bad");}};
    $("#companyPause").onclick=async()=>{try{await api(data.paused?"/api/company/resume":"/api/company/pause",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({reason:"Pausa desde Command Center"})});renderCompany();}catch(err){toast("No se cambió el estado",err.message,"bad");}};
    $$(".companyApprove").forEach(btn=>btn.onclick=async()=>{const reason=window.prompt("Motivo de aprobación y comprobación realizada");if(!reason)return;try{await api(`/api/company/tasks/${btn.dataset.task}/approve`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({reason})});toast("Handoff aprobado","La acción sigue separada del control plane","good");renderCompany();}catch(err){toast("No aprobado",err.message,"bad");}});
  }catch(err){ node.innerHTML=`<div class="card"><div class="bd"><b>Control plane no disponible</b><div class="sub" style="margin-top:6px">${esc(err.message)}</div></div></div>`; }
}

async function renderIntelligence(){
  const node = $("#view-intelligence"); if(!node) return;
  node.innerHTML = `<div class="card" aria-live="polite"><div class="bd"><div class="sub">Calculando inteligencia local…</div></div></div>`;
  try{
    const payload = await api("/api/analytics");
    const analytics = payload.analytics || {};
    const intel = analytics.fleet_intelligence || {};
    const predictive = analytics.predictive_movement || {};
    if(intel.status !== "ready"){
      node.innerHTML = `<div class="toolbar"><div><h1 class="view-title">Inteligencia de flota</h1><div class="sub">Métricas descriptivas basadas en histórico local</div></div></div><div aria-live="polite">${emptyState("Aún no hay histórico suficiente", (intel.recommendations||[])[0]||"Acumula ciclos para activar esta vista.")}</div>`;
      return;
    }
    const q = intel.quality_components || {};
    const delta = finiteMetric(intel.compliance_delta_points,-100,100);
    const score = finiteMetric(intel.signal_quality_score,0,100);
    const freshnessSeconds = finiteMetric(intel.freshness_seconds,0,31536000);
    const gaps = finiteMetric(intel.gap_count,0,1000000);
    const transitions = finiteMetric(intel.geofence_transitions,0,1000000);
    const outsidePeak = finiteMetric(intel.outside_peak,0,1000000);
    const crossingRisk = finiteMetric(predictive.crossing_risk_count,0,1000000);
    const movementAnomalies = finiteMetric(predictive.anomaly_count,0,1000000);
    const gapThreshold = finiteMetric(intel.gap_threshold_seconds,1,31536000);
    const scoreTone = score===null?"warn":score>=90?"ok":score>=70?"warn":"bad";
    const components = [
      ["Recencia", finiteMetric(q.freshness_percent), "Tiempo desde el último ciclo"],
      ["Continuidad", finiteMetric(q.continuity_percent), "Intervalos sin interrupciones prolongadas"],
      ["Cobertura GPS", finiteMetric(q.gps_coverage_percent), "Puntos con coordenadas válidas"],
      ["Profundidad", finiteMetric(q.history_depth_percent), "Tiempo histórico disponible"],
    ];
    const componentHtml = components.map(([label,value,help])=>{
      const width=value===null?0:value;
      return `<div style="margin-bottom:14px"><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px"><span>${esc(label)} <span class="sub">· ${esc(help)}</span></span><b>${metricText(value,"%")}</b></div><div style="height:7px;background:var(--panel-3);border-radius:8px;overflow:hidden"><div style="height:100%;width:${width}%;background:${value===null?'var(--muted)':value>=90?'var(--green)':value>=70?'var(--amber)':'var(--red)'};border-radius:8px"></div></div></div>`;
    }).join("");
    const recommendations = (Array.isArray(intel.recommendations)?intel.recommendations:[]).map(text=>`<div class="aitem"><div class="ic">${reicon("search",{size:16})}</div><div class="grow"><div class="nm">${esc(text)}</div></div></div>`).join("");
    const top = intel.top_transition_device && typeof intel.top_transition_device==="object" ? intel.top_transition_device : null;
    const series = (Array.isArray(analytics.compliance_series)?analytics.compliance_series:[]).map((row,index)=>({idx:index+1,value:finiteMetric(row&&row.compliance_percent)})).filter(row=>row.value!==null).slice(-60);
    const tableRows = series.slice(-10).map(row=>`<tr><td>${row.idx}</td><td>${row.value}%</td></tr>`).join("");
    const chartContent = series.length ? `<canvas id="intelTrend" height="150" role="img" aria-label="Tendencia de conformidad observada en los ciclos recientes"></canvas><table class="sr-only intel-data-table"><caption>Últimos valores de conformidad observada</caption><thead><tr><th>Ciclo</th><th>Conformidad</th></tr></thead><tbody>${tableRows}</tbody></table>` : emptyState("Sin tendencia disponible","Se necesitan ciclos válidos para dibujar la serie.");
    const historyPoints = finiteMetric(intel.history_points,0,1000000);
    const spanSeconds = finiteMetric(Number(intel.history_span_hours)*3600,0,315360000);
    node.innerHTML = `
      <div class="toolbar"><div><h1 class="view-title">Inteligencia de flota</h1><div class="sub">${metricText(historyPoints)} ciclos · ${spanSeconds===null?'periodo no disponible':fmtDur(spanSeconds)} observados · previsión explicable local</div></div><div class="grow"></div><span class="tag in"><span class="d"></span>Evidencia local</span></div>
      <div class="kpis">
        ${kpiCard("Calidad de datos", metricText(score,"/100"), scoreTone, reicon("chart-line"))}
        ${kpiCard("Recencia", freshnessSeconds===null?"—":fmtDur(freshnessSeconds), freshnessSeconds===null?"warn":(finiteMetric(q.freshness_percent)||0)>=90?"ok":"warn", reicon("refresh"))}
        ${kpiCard("Cortes"+(gapThreshold===null?"":" > "+Math.round(gapThreshold/60)+"m"), metricText(gaps), gaps===null?"warn":gaps?"warn":"ok", reicon("alert-triangle2"))}
        ${kpiCard("Conformidad vs. inicio", delta===null?"—":`${delta>0?"+":""}${delta} pp`, delta===null?"warn":delta>=0?"ok":"bad", reicon("shield-check"))}
        ${kpiCard("Transiciones", metricText(transitions), transitions===null?"warn":"acc", reicon("route"))}
        ${kpiCard("Pico fuera", metricText(outsidePeak), outsidePeak===null?"warn":outsidePeak?"warn":"ok", reicon("map-pin"))}
        ${kpiCard("Riesgo de cruce", metricText(crossingRisk), crossingRisk?"warn":"ok", reicon("route"))}
        ${kpiCard("Anomalías GPS", metricText(movementAnomalies), movementAnomalies?"bad":"ok", reicon("alert-triangle2"))}
      </div>
      <div class="grid-main">
        <div class="card"><div class="hd"><h3>Conformidad observada</h3><div class="grow"></div><span class="sub">${series.length?`Últimos ${series.length} ciclos`:"Sin datos"}</span></div><div class="bd">${chartContent}</div></div>
        <div class="card"><div class="hd"><h3>Calidad explicada</h3><div class="grow"></div><span class="mono">${metricText(score,"/100")}</span></div><div class="bd">${componentHtml}<div class="sub" style="margin-top:8px">Fórmula: ${esc((intel.evidence||{}).quality_formula||"—")}</div></div></div>
      </div>
      <div class="grid-main" style="margin-top:14px">
        <div class="card"><div class="hd"><h3>Hallazgos accionables</h3></div><div class="bd"><div class="alist">${recommendations||emptyState("Sin hallazgos", "La señal histórica es estable.")}</div></div></div>
        <div class="card"><div class="hd"><h3>Movimiento de perímetro</h3></div><div class="bd"><div class="alist">
          <div class="aitem"><div class="ic">${reicon("route")}</div><div class="grow"><div class="nm">Transiciones detectadas</div><div class="ds">Cambios observados entre dentro, fuera y desconocido</div></div><span class="mono">${metricText(transitions)}</span></div>
          <div class="aitem"><div class="ic">${reicon("devices")}</div><div class="grow"><div class="nm">Mayor actividad</div><div class="ds">Dispositivo con más cambios de estado</div></div><span class="mono">${top?esc(top.device_id)+" · "+metricText(finiteMetric(top.transitions,0,1000000)):"—"}</span></div>
          <div class="aitem"><div class="ic">${reicon("clock")}</div><div class="grow"><div class="nm">Intervalo mediano</div><div class="ds">P95 ${safeDuration(intel.p95_interval_seconds)}</div></div><span class="mono">${safeDuration(intel.median_interval_seconds)}</span></div>
        </div></div></div>
      </div>`;
    const cv = $("#intelTrend");
    if(cv && series.length){
      if(App.__intelChart) App.__intelChart.destroy();
      App.__intelChart = new Chart(cv,{type:"line",data:{labels:series.map(x=>x.idx),datasets:[{label:"Conformidad",data:series.map(x=>x.value),borderColor:"#5e6ad5",backgroundColor:"rgba(94,106,213,.12)",borderWidth:2,fill:true,tension:.3,pointRadius:0}]},options:{responsive:true,plugins:{legend:{display:false}},scales:{x:{display:false},y:{min:0,max:100,grid:{color:"rgba(148,163,184,.08)"},ticks:{color:"#8b949e",callback:v=>v+"%"}}}}});
    }
  }catch(error){
    node.innerHTML = `<div aria-live="assertive">${emptyState("No se pudo cargar la inteligencia", error.message||"Error de conexión")}</div>`;
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
  App._modalReturnFocus = document.activeElement;
  $("#ovl").classList.add("show"); $("#devModal").classList.add("show"); $("#devModal").setAttribute("aria-hidden","false");
  $("#mCancel").focus();
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
  App._cmdkReturnFocus = document.activeElement;
  $("#cmdk").classList.add("show"); $("#cmdk").setAttribute("aria-hidden","false");
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
function closeCmdk(){
  const wasOpen=$("#cmdk").classList.contains("show");
  $("#cmdk").classList.remove("show"); $("#cmdk").setAttribute("aria-hidden","true");
  if(wasOpen && App._cmdkReturnFocus && document.contains(App._cmdkReturnFocus)) App._cmdkReturnFocus.focus();
  App._cmdkReturnFocus=null;
}
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
  window.addEventListener("hashchange", ()=>{
    const requested=location.hash.replace(/^#/,"");
    if(App._started && requested!==App.view && NAV.some(item=>item.id===requested)) goView(requested);
  });
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

/* ===================== VISTA: ROI (valor de negocio) ===================== */
async function renderROI(){
  const node = $("#view-roi"); if(!node) return;
  try{
    const prod = await api("/api/product");
    const roi = (prod && prod.roi) || {enabled:false};
    if(!roi.enabled){
      node.innerHTML = `<div class="empty"><div class="t">ROI no disponible</div><div class="s">Requiere al menos un dispositivo en la flota</div></div>`;
      return;
    }
    const s = roi.summary || {};
    const b = roi.breakdown || {};
    const d = roi.drivers || {};
    const a = roi.assumptions || {};
    node.innerHTML = `
      <div class="view-head">
        <div><h2>ROI · Valor de negocio</h2>
        <div class="sub">Estimación local a partir del estado observado · sin llamadas externas</div></div>
      </div>
      <div class="card"><div class="hd"><h3>Resumen</h3></div><div class="bd">
        <div class="metrics">
          <div class="metric"><div class="v">${esc(fmt.n(s.total_monthly_value||0))}</div><div class="l">Valor mensual estimado</div></div>
          <div class="metric"><div class="v">${esc(fmt.n(s.commercial_equivalent||0))}</div><div class="l">Equivalente comercial anual</div></div>
          <div class="metric"><div class="v">${esc(s.risk_reduction_pct!=null?s.risk_reduction_pct:"-")}%</div><div class="l">Reducción de riesgo</div></div>
        </div>
      </div></div>
      <div class="card"><div class="hd"><h3>Desglose</h3></div><div class="bd">
        <ul class="alist">
          <li><span>Ahorro laboral/mes</span><b>${esc(fmt.n(b.labor_savings_monthly||0))}</b></li>
          <li><span>Brechas evitadas/mes</span><b>${esc(fmt.n(b.breach_avoidance_monthly||0))}</b></li>
          <li><span>Compliance/mes</span><b>${esc(fmt.n(b.compliance_savings_monthly||0))}</b></li>
        </ul>
      </div></div>
      <div class="card"><div class="hd"><h3>Impulsores</h3></div><div class="bd">
        <ul class="alist">
          <li><span>Acciones ejecutadas</span><b>${esc(d.actions_executed||0)}</b></li>
          <li><span>Dispositivos fuera de geovalla</span><b>${esc(d.outside_fence||0)}</b></li>
          <li><span>Dispositivos no conformes</span><b>${esc(d.non_compliant||0)}</b></li>
        </ul>
      </div></div>
      <div class="card"><div class="hd"><h3>Supuestos</h3></div><div class="bd">
        <ul class="alist">
          <li><span>Coste por hora de incidente</span><b>${esc(fmt.n(a.cost_per_incident_hour||0))}</b></li>
          <li><span>Coste por brecha</span><b>${esc(fmt.n(a.cost_per_breach||0))}</b></li>
          <li><span>Coste por violación de compliance</span><b>${esc(fmt.n(a.cost_per_compliance_violation||0))}</b></li>
        </ul>
      </div></div>`;
  }catch(e){
    node.innerHTML = `<div class="empty"><div class="t">Error cargando ROI</div><div class="s">${esc(e.message)}</div></div>`;
  }
}

/* ===================== VISTA: CONECTORES UEM (wizard) ===================== */
async function renderConnectors(){
  const node = $("#view-connectors"); if(!node) return;
  node.innerHTML = `
    <div class="view-head">
      <div><h2>Conectores UEM</h2>
      <div class="sub">Conecta tus plataformas de gestión (MDM/UEM) para unificar inventario, ubicación y acciones de remediación.</div></div>
      <div class="grow"></div>
      <button class="btn primary" onclick="openConnWizard()">+ Conectar UEM</button>
    </div>
    <div class="card"><div class="bd" id="connList"><div class="empty"><div class="t">Cargando conectores…</div></div></div></div>`;
  await loadConnectors();
}

async function loadConnectors(){
  const list = $("#connList"); if(!list) return;
  try{
    const r = await api("/api/providers");
    const ps = (r && r.providers) || [];
    if(!ps.length){
      list.innerHTML = `<div class="empty"><div class="t">Sin conectores</div><div class="s">Usa "Conectar UEM" para añadir Applivery, Intune, Jamf, FleetDM…</div></div>`;
      return;
    }
    list.innerHTML = `<ul class="alist">` + ps.map(p=>`
      <li>
        <span>${esc(p.label||p.name)}${p.segment?' <span class="pill">'+esc(p.segment)+'</span>':''} ${p.configured?'<b style="color:var(--ok)">· conectado</b>':'<b style="color:var(--warn)">· sin credenciales</b>'}</span>
        <span class="row gap">
          <button class="btn sm ghost" onclick="removeConn('${esc(p.name)}')">Quitar</button>
        </span>
      </li>`).join("") + `</ul>`;
  }catch(e){
    list.innerHTML = `<div class="empty"><div class="t">Error</div><div class="s">${esc(e.message)}</div></div>`;
  }
}

async function openConnWizard(){
  let catalog = [];
  try{ const c = await api("/api/providers/catalog"); catalog = (c&&c.catalog)||[]; }catch(e){}
  const state = {step:1, name:null, meta:null, fields:{}};
  const modal = $("#connWizard");
  const open = ()=>{ modal.classList.add("show"); modal.setAttribute("aria-hidden","false"); };
  const close = ()=>{ modal.classList.remove("show"); modal.setAttribute("aria-hidden","true"); };
  $("#cwClose").onclick = close;

  function fieldLabel(f){
    return {api_key:"API key / token", org_id:"ID de organización", endpoint:"Endpoint (URL base)"}[f] || f;
  }
  function render(){
    const body = $("#cwBody"), foot = $("#cwFoot"), sub = $("#cwSub"), av = $("#cwAv"), title = $("#cwTitle");
    body.innerHTML = ""; foot.innerHTML = "";
    if(state.step===1){
      title.textContent = "Conectar UEM"; sub.textContent = "Paso 1 de 3 · elige tu plataforma";
      av.textContent = "+";
      body.innerHTML = `<div class="grid cols-2" style="gap:10px">` + catalog.map(c=>`
        <button class="btn outline" style="text-align:left;justify-content:flex-start" onclick="cwPick('${esc(c.name)}')">
          <b>${esc(c.label)}</b></button>`).join("") + `</div>`;
      const b = el("button","btn primary"); b.textContent="Siguiente"; b.onclick=()=>{
        if(!state.name){ toast("Elige una plataforma","","bad"); return; }
        state.step=2; render();
      };
      foot.appendChild(b);
    } else if(state.step===2){
      sub.textContent = "Paso 2 de 3 · credenciales"; av.textContent = state.meta?state.meta.label[0]:"·";
      const fields = state.meta?state.meta.fields:[];
      const segOpts = ["","móviles","portátiles","mixta","servidores","otros"];
      const segSel = `<label class="fld"><span>Segmento de flota <small style="opacity:.6">(qué cubre este UEM)</small></span>
          <select id="cw_segment">${segOpts.map(o=>`<option value="${o}"${o===(state.segment||"")?" selected":""}>${o||"— sin etiqueta —"}</option>`).join("")}</select></label>`;
      body.innerHTML = (fields.length ? fields.map(f=>`
        <label class="fld"><span>${fieldLabel(f)}</span>
          <input id="cw_${f}" type="${f==='api_key'?'password':'text'}" autocomplete="off" placeholder="${fieldLabel(f)}"></label>`).join("")
        : `<div class="empty"><div class="t">Este conector no requiere credenciales</div></div>`) + segSel;
      const back = el("button","btn ghost"); back.textContent="Atrás"; back.onclick=()=>{state.step=1;render();};
      const next = el("button","btn primary"); next.textContent="Siguiente"; next.onclick=()=>{
        state.fields = {}; fields.forEach(f=>{ state.fields[f] = $(("#cw_"+f)).value.trim(); });
        const seg = $("#cw_segment"); state.segment = seg ? seg.value : "";
        state.step=3; render();
      };
      foot.appendChild(back); foot.appendChild(next);
    } else {
      sub.textContent = "Paso 3 de 3 · guardar"; av.textContent = "✓";
      body.innerHTML = `<div class="empty"><div class="t">${esc(state.meta?state.meta.label:"")}${state.segment?' <span class="pill">'+esc(state.segment)+'</span>':''}</div>
        <div class="s">Listo para guardar el conector${state.meta&&state.meta.fields.length?" (credenciales aisladas en tu tenant, 0600)":""}.</div></div>`;
      const back = el("button","btn ghost"); back.textContent="Atrás"; back.onclick=()=>{state.step=2;render();};
      const save = el("button","btn primary"); save.textContent="Guardar conector";
      save.onclick = async ()=>{
        save.disabled = true; save.textContent = "Guardando…";
        try{
          const r = await api("/api/providers",{method:"POST",headers:{"Content-Type":"application/json"},
            body:JSON.stringify({name:state.name, segment:state.segment||"", ...state.fields})});
          if(r.ok){ toast("Conector guardado", state.meta?state.meta.label:"", "ok"); close(); await loadConnectors(); }
          else toast("Error", (r.error||"no se pudo guardar"), "bad");
        }catch(e){ toast("Error", e.message, "bad"); }
        finally{ save.disabled=false; save.textContent="Guardar conector"; }
      };
      foot.appendChild(back); foot.appendChild(window.cwTest()); foot.appendChild(save);
    }
  }
  window.cwTest = ()=>{
    const b = el("button","btn outline"); b.textContent="Probar conexión";
    b.onclick = async ()=>{
      b.disabled = true; b.textContent = "Probando…";
      try{
        const r = await api("/api/providers/test",{method:"POST",headers:{"Content-Type":"application/json"},
          body:JSON.stringify({name:state.name, ...state.fields})});
        if(r.ok) toast("Conexión OK", (r.verified==="live"?"verificada en vivo":r.note||""), "ok");
        else toast("Fallo", (r.error||"no se pudo conectar"), "bad");
      }catch(e){ toast("Error al probar", e.message, "bad"); }
      finally{ b.disabled=false; b.textContent="Probar conexión"; }
    };
    return b;
  };
  render();
  open();
}

async function removeConn(name){
  if(!confirm("¿Quitar el conector "+name+"?")) return;
  try{
    const r = await api("/api/providers/"+encodeURIComponent(name),{method:"DELETE"});
    if(r.ok){ toast("Conector quitado", name, "ok"); await loadConnectors(); }
    else toast("Error", r.error||"", "bad");
  }catch(e){ toast("Error", e.message, "bad"); }
}

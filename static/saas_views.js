/* LucidFence SaaS — product views (part 1: overview, devices, map, risk). */
window.GFViews = window.GFViews || {};
const h = (tag, attrs, ...kids) => { const e = document.createElement(tag); for (const k in (attrs||{})) { if (k==="class") e.className=attrs[k]; else if (k==="html") e.innerHTML=attrs[k]; else e.setAttribute(k, attrs[k]); } (kids||[]).forEach(c=>e.append(c)); return e; };
const esc = s => String(s==null?"":s).replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const stateTag = st => st==="inside"?'<span class="tag inside">dentro</span>':st==="outside"?'<span class="tag outside">fuera</span>':'<span class="tag unknown">desconocido</span>';
const compTag = c => c===false?'<span class="tag nocomp">no conforme</span>':c===true?'<span class="tag inside">conforme</span>':'<span class="tag unknown">—</span>';
const iosGeoTag = d => {
  const g = d && d.geofence_compliance;
  if(!g || String(g.platform||"").toLowerCase()!=="ios") return '<span class="tag unknown">—</span>';
  return g.compliant === true
    ? '<span class="tag inside" title="'+esc(g.policy_name||'iOS geofence')+'">iOS geocerca OK</span>'
    : '<span class="tag nocomp" title="'+esc((g.policy_name||'iOS geofence')+' · '+(g.evidence||''))+'">iOS fuera/no cumple</span>';
};

// ---------- OVERVIEW ----------
GFViews.overview = async (root, S, API, toast) => {
  const [st, prod] = await Promise.all([API("/api/status"), API("/api/risk")]);
  const sm = prod.summary || {};
  const iosGeo = st.ios_geofence_summary || {};
  const kpis = [
    ["Dispositivos", st.device_count||0],
    ["Dentro", st.inside_count||0],
    ["Fuera", st.outside_count||0],
    ["Desconocidos", st.unknown_count||0],
    ["No conformes", sm.noncompliant||0],
    ["iOS geocerca", iosGeo.total ? `${iosGeo.compliant}/${iosGeo.total}` : 0],
    ["Geovallas", (st.fences||[]).length],
  ];
  root.innerHTML = "";
  const kpiWrap = h("div",{class:"kpis"});
  kpis.forEach(([l,v]) => kpiWrap.append(h("div",{class:"kpi"}, h("div",{class:"label"},l), h("div",{class:"val"},String(v)))));
  root.append(kpiWrap);

  const grid = h("div",{class:"grid2"});
  // live map
  const mapCard = h("div",{class:"card"}, h("div",{class:"hd"}, h("h3","",["Mapa en vivo"]), h("span",{class:"badge dry",style:"margin-left:auto"},["tiempo real"])));
  const mapDiv = h("div",{id:"ovMap",style:"height:380px;border-radius:0 0 16px 16px"});
  mapCard.append(mapDiv);
  grid.append(mapCard);
  // risk panel
  const riskCard = h("div",{class:"card"}, h("div",{class:"hd"}, h("h3","",["Top riesgo"])));
  const riskBody = h("div",{class:"bd",style:"max-height:380px;overflow:auto"});
  (prod.risk||[]).slice(0,6).forEach(r => {
    riskBody.append(h("div",{class:"table"}, h("div",{style:"display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)"}, 
      h("div",{}, h("b","",[esc(r.device_name||r.device_id)]), h("div",{style:"font-size:11px;color:var(--muted-fg)"},[esc(r.device_id)])),
      h("div",{style:"text-align:right"}, h("span",{class:"tag "+(r.severity==="critical"?"crit":r.severity==="high"?"high":"high")},[esc(r.severity||"alto")]), h("div",{style:"font-size:11px;color:var(--muted-fg);margin-top:4px"},[esc(r.reasons?r.reasons[0]:"")])))));
  });
  if (!(prod.risk||[]).length) riskBody.append(h("p",{style:"color:var(--muted-fg);font-size:13px"},["Sin dispositivos en riesgo 🎉"]));
  riskCard.append(riskBody);
  grid.append(riskCard);
  root.append(grid);
  // draw map
  setTimeout(() => {
    if (!window.L) return;
    const m = L.map(mapDiv).setView([40.42,-3.70], 11);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19}).addTo(m);
    (st.devices||[]).forEach(d => { if (d.lat&&d.lng) L.circleMarker([d.lat,d.lng],{radius:7,color:d.fence_state==="inside"?"#10B981":d.fence_state==="outside"?"#3B82F6":"#94A3B8"}).addTo(m).bindPopup(esc(d.name)); });
  }, 60);
};

// ---------- DEVICES ----------
GFViews.devices = async (root, S, API, toast) => {
  const [devs, st] = await Promise.all([API("/api/devices"), API("/api/status")]);
  root.innerHTML = "";
  const tb = h("div",{class:"card"}, h("div",{class:"hd"}, h("h3","",["Flota ("+ (devs.length||0) +")"])));
  const body = h("div",{class:"bd",style:"overflow:auto"});
  const table = h("table",{class:"table"});
  table.append(h("thead",{}, h("tr",{}, ...["Dispositivo","Estado","Conformidad","iOS geocerca","Última act.","Acciones"].map(c=>h("th","",[c])))));
  const tbody = h("tbody",{});
  (devs||[]).forEach(d => {
    const tr = h("tr",{});
    tr.append(
      h("td",{}, h("div",{style:"display:flex;align-items:center;gap:10px"}, h("div",{class:"av",style:"background:linear-gradient(135deg,#2563EB,#7C3AED)"},[esc((d.name||"?").slice(0,2).toUpperCase())]), h("div",{}, h("b","",[esc(d.name)]), h("div",{style:"font-size:11px;color:var(--muted-fg)"},[esc(d.id)])))),
      h("td",{html:stateTag(d.fence_state)}),
      h("td",{html:compTag(d.compliant)}),
      h("td",{html:iosGeoTag(d)}),
      h("td",{style:"color:var(--muted-fg);font-size:12px"},[(d.last_update||"").replace("T"," ").slice(0,19)]),
      h("td",{}, h("button",{class:"btn",style:"height:30px;font-size:12px",onclick:"GF.goView(\"map\")"},["Ver en mapa"]))
    );
    tbody.append(tr);
  });
  table.append(tbody); body.append(table); tb.append(body); root.append(tb);
};

// ---------- MAP ----------
GFViews.map = async (root, S, API, toast) => {
  const st = await API("/api/status");
  root.innerHTML = "";
  const card = h("div",{class:"card"}, h("div",{class:"hd"}, h("h3","",["Mapa de flota y geovallas"])));
  const mapDiv = h("div",{id:"bigMap",style:"height:620px;border-radius:0 0 16px 16px"});
  card.append(mapDiv); root.append(card);
  setTimeout(() => {
    if (!window.L) return;
    const m = L.map(mapDiv).setView([40.42,-3.70], 11);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19}).addTo(m);
    (st.fences||[]).forEach(f => { try { const g=JSON.parse(f.geometry); if(g.type==="Polygon"){ L.polygon(g.coordinates[0],[[f.rule==="include"?"#10B981":"#F43F5E",f.rule==="include"?"#10B981":"#F43F5E"]]).addTo(m).bindPopup(esc(f.name)); } } catch(e){} });
    (st.devices||[]).forEach(d => { if (d.lat&&d.lng) L.marker([d.lat,d.lng]).addTo(m).bindPopup("<b>"+esc(d.name)+"</b><br>"+esc(d.fence_state)); });
  }, 60);
};

// ---------- RISK ----------
GFViews.risk = async (root, S, API, toast) => {
  const [prod, inc] = await Promise.all([API("/api/risk"), API("/api/incidents")]);
  root.innerHTML = "";
  const kpis = h("div",{class:"kpis"}, ...[
    ["Dispositivos en riesgo", (prod.risk||[]).length],
    ["Incidentes abiertos", (inc.incidents||[]).filter(i=>i.state==="open").length],
    ["Severidad crítica", (prod.risk||[]).filter(r=>r.severity==="critical").length],
    ["Media", (prod.risk||[]).length?(prod.risk.reduce((a,r)=>a+(r.score||0),0)/prod.risk.length).toFixed(1):"0"],
    ["Resueltos (24h)", 0],
    ["MTTR", "—"],
  ].map(([l,v])=>h("div",{class:"kpi"}, h("div",{class:"label"},l), h("div",{class:"val"},String(v)))));
  root.append(kpis);
  const card = h("div",{class:"card"}, h("div",{class:"hd"}, h("h3","",["Dispositivos priorizados"])));
  const body = h("div",{class:"bd",style:"overflow:auto"});
  const table = h("table",{class:"table"});
  table.append(h("thead",{}, h("tr",{}, ...["Dispositivo","Severidad","Score","Razones","Veredicto"].map(c=>h("th","",[c])))));
  const tb = h("tbody",{});
  (prod.risk||[]).forEach(r => {
    tb.append(h("tr",{}, 
      h("td",{}, h("b","",[esc(r.device_name||r.device_id)])),
      h("td",{html:'<span class="tag '+(r.severity==="critical"?"crit":r.severity==="high"?"high":"high")+'">'+esc(r.severity||"alto")+"</span>"}),
      h("td",{style:"font-variant-numeric:tabular-nums"},[String(r.score||0)]),
      h("td",{style:"color:var(--muted-fg);font-size:12px"},[(r.reasons||[]).join(" · ")]),
      h("td",{},[esc(r.verdict||"")])
    ));
  });
  table.append(tb); body.append(table); card.append(body); root.append(card);
};

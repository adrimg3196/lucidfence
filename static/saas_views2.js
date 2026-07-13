/* LucidFence SaaS — product views (part 2: policies, compliance, billing, users, settings). */
const v2 = window.GFViews = window.GFViews || {};

// ---------- POLICIES ----------
v2.policies = async (root, S, API, toast) => {
  const [prod, st] = await Promise.all([API("/api/policies"), API("/api/status")]);
  root.innerHTML = "";
  const grid = h("div",{class:"grid2"});
  const fc = h("div",{class:"card"}, h("div",{class:"hd"}, h("h3","",["Geovallas ("+((st.fences||[]).length)+")"])));
  const fb = h("div",{class:"bd",style:"overflow:auto;max-height:520px"});
  (st.fences||[]).forEach(f => {
    let meta = {}; try { meta = JSON.parse(f.metadata||"{}"); } catch(e){}
    const row = h("div",{style:"padding:11px 0;border-bottom:1px solid var(--border)"});
    const top = h("div",{style:"display:flex;justify-content:space-between"});
    top.append(h("b","",[esc(f.name)]), h("span",{class:"tag "+(f.rule==="include"?"inside":"outside")},[esc(f.rule==="include"?"incluye":"excluye")]));
    const desc = h("div",{style:"font-size:12px;color:var(--muted-fg);margin-top:3px"},[esc(meta.description||"")]);
    const meta2 = h("div",{style:"font-size:11px;color:var(--muted-fg);margin-top:3px"},["acción: "+esc(meta.action||"alert")+" · radius "+(f.radius||"?")]);
    row.append(top, desc, meta2);
    fb.append(row);
  });
  if (!(st.fences||[]).length) fb.append(h("p",{style:"color:var(--muted-fg)"},["Sin geovallas configuradas"]));
  fc.append(fb); grid.append(fc);
  const pc = h("div",{class:"card"}, h("div",{class:"hd"}, h("h3","",["Políticas recomendadas"])));
  const pb = h("div",{class:"bd",style:"overflow:auto;max-height:520px"});
  (prod.policies||[]).forEach(p => {
    const row = h("div",{style:"padding:11px 0;border-bottom:1px solid var(--border)"});
    const top = h("div",{style:"display:flex;justify-content:space-between"});
    top.append(h("b","",[esc(p.title)]), h("span",{class:"tag "+(p.priority==="alta"?"high":"outside")},[esc(p.priority||"media")]));
    const desc = h("div",{style:"font-size:12.5px;margin-top:4px"},[esc(p.description||"")]);
    const act = h("div",{style:"font-size:11.5px;color:var(--blue-400);margin-top:4px"},["▶ "+esc(p.action||"")]);
    row.append(top, desc, act);
    pb.append(row);
  });
  if (!(prod.policies||[]).length) pb.append(h("p",{style:"color:var(--muted-fg)"},["Sin recomendaciones"]));
  pc.append(pb); grid.append(pc);
  root.append(grid);
};

// ---------- COMPLIANCE ----------
v2.compliance = async (root, S, API, toast) => {
  const [c, a] = await Promise.all([API("/api/compliance"), API("/api/analytics")]);
  root.innerHTML = "";
  const kpis = h("div",{class:"kpis"}, ...[
    ["Conformidad", (c.compliance_percent||0)+"%"],
    ["Dentro", (c.state_distribution||{}).inside||0],
    ["Fuera", (c.state_distribution||{}).outside||0],
    ["Desconocidos", (c.state_distribution||{}).unknown||0],
    ["Tendencia 7d", "—"],
    ["Desviación", "—"],
  ].map(([l,v])=>h("div",{class:"kpi"}, h("div",{class:"label"},l), h("div",{class:"val"},String(v)))));
  root.append(kpis);
  const card = h("div",{class:"card"}, h("div",{class:"hd"}, h("h3","",["Serie de conformidad"])));
  const body = h("div",{class:"bd"});
  const series = (c.series||[]);
  if (series.length) {
    const max = Math.max(...series.map(s=>s.inside+s.outside), 1);
    const svg = h("div",{style:"display:flex;align-items:flex-end;gap:6px;height:160px"});
    series.slice(-14).forEach(s => {
      const tot = s.inside+s.outside; const pct = tot?Math.round(s.inside/tot*100):0;
      svg.append(h("div",{title:esc(s.ts)+" · "+pct+"%",style:"flex:1;height:100%;display:flex;flex-direction:column;justify-content:flex-end"},
        h("div",{style:"background:linear-gradient(180deg,#10B981,#059669);border-radius:5px 5px 0 0;height:"+(tot/max*100)+"%"})));
    });
    body.append(svg);
  } else body.append(h("p",{style:"color:var(--muted-fg)"},["Sin datos de serie todavía"]));
  card.append(body); root.append(card);
};

// ---------- BILLING ----------
v2.billing = async (root, S, API, toast) => {
  const [plan, prod] = await Promise.all([API("/api/plan"), API("/api/org")]);
  root.innerHTML = "";
  const cur = plan.plan || "free";
  const wrap = h("div",{class:"plan-grid",style:"grid-template-columns:repeat(3,1fr);gap:16px"});
  Object.entries(plan.plans||{}).forEach(([key,p]) => {
    const el = h("div",{class:"plan"+(key===cur?" active":""),onclick:"window.__upgrade&&window.__upgrade('"+key+"')"}, 
      h("h4","",[esc(p.label)]), h("div",{class:"price"},[esc(p.price)]),
      h("ul",{}, ...["Máx dispositivos: "+p.max_devices,"Máx geovallas: "+p.max_fences,"Retención: "+p.retention_days+" días"].map(x=>h("li","",[x]))));
    wrap.append(el);
  });
  root.append(h("div",{class:"card"}, h("div",{class:"hd"}, h("h3","",["Tu plan (mock · 100% local)"])), h("div",{class:"bd"}, wrap)));
  window.__upgrade = async (key) => {
    const r = await API("/api/plan/upgrade",{method:"POST",body:JSON.stringify({plan:key})});
    if (r.ok) { toast("Plan cambiado a "+key,"ok"); S.plan = r.limits; v2.billing(root,S,API,toast); }
    else toast(r.error||"sin permiso","bad");
  };
  const usage = h("div",{class:"card",style:"margin-top:16px"}, h("div",{class:"hd"}, h("h3","",["Uso actual"])));
  const ub = h("div",{class:"bd"});
  const lim = plan.limits||{};
  const sm = prod.summary||{};
  ub.append(h("p",{style:"font-size:13px"},["Dispositivos: "+(sm.total_devices||0)+" / "+lim.max_devices]));
  ub.append(h("p",{style:"font-size:13px"},["Geovallas: "+((prod.fences||[]).length)+" / "+lim.max_fences]));
  usage.append(ub); root.append(usage);
  root.append(h("p",{style:"font-size:11.5px;color:var(--muted-fg);margin-top:14px"},["Facturación simulada. No se procesa ningún pago real: el SaaS corre 100% en tu máquina."]));
};

// ---------- USERS ----------
v2.users = async (root, S, API, toast) => {
  const r = await API("/api/users");
  root.innerHTML = "";
  const card = h("div",{class:"card"}, h("div",{class:"hd"}, h("h3","",["Miembros de "+(S.org?"la organización":"")]), h("button",{class:"btn primary",style:"margin-left:auto;height:32px;font-size:12px",onclick:"window.__invite&&window.__invite()"},["Invitar"])));
  const body = h("div",{class:"bd",style:"overflow:auto"});
  const table = h("table",{class:"table"});
  table.append(h("thead",{}, h("tr",{}, ...["Usuario","Email","Rol","Estado"].map(c=>h("th","",[c])))));
  const tb = h("tbody",{});
  (r.users||[]).forEach(u => {
    tb.append(h("tr",{}, 
      h("td",{}, h("b","",[esc(u.name)])), h("td",{style:"color:var(--muted-fg)"},[esc(u.email)]),
      h("td",{},[esc(({"owner":"Propietario","admin":"Administrador","operator":"Operador","viewer":"Lectura"}[u.org_roles[S.org]]||"—"))]),
      h("td",{},[u.active?'<span class="tag inside">activo</span>':'<span class="tag unknown">inactivo</span>'])));
  });
  table.append(tb); body.append(table); card.append(body); root.append(card);
  window.__invite = async () => {
    const email = prompt("Email del invitado:"); if (!email) return;
    const name = prompt("Nombre:"); const role = prompt("Rol (admin/operator/viewer):","viewer");
    const res = await API("/api/users",{method:"POST",body:JSON.stringify({email,name,role})});
    if (res.ok) {
      const tp = res.temp_password ? " · contraseña temporal: "+res.temp_password : "";
      toast("Invitado añadido"+tp,"ok");
      v2.users(root,S,API,toast);
    } else toast(res.error||"error","bad");
  };
};

// ---------- SETTINGS ----------
v2.settings = async (root, S, API, toast) => {
  const st = await API("/api/settings/status");
  root.innerHTML = "";
  const card = h("div",{class:"card"}, h("div",{class:"hd"}, h("h3","",["Credenciales Applivery (UEM)"])));
  const body = h("div",{class:"bd",style:"max-width:560px"});
  body.append(h("div",{class:"field"}, h("label","",["API Token"]), h("input",{class:"input",id:"setKey",type:"password",placeholder:"Pega tu token de Applivery",value:st.masked_key||""})));
  body.append(h("div",{class:"field"}, h("label","",["Organization ID"]), h("input",{class:"input",id:"setOrg",placeholder:"opcional"})));
  const modeRow = h("div",{class:"field"}, h("label","",["Modo"]), h("div",{class:"toolbar"}, 
    h("button",{class:"chip"+(st.mode==="simulation"?" active":""),id:"mSim"},["Simulación"]),
    h("button",{class:"chip"+(st.mode==="live"?" active":""),id:"mLive"},["Live (UEM real)"])));
  body.append(modeRow);
  body.append(h("div",{class:"toolbar"}, 
    h("button",{class:"btn primary",onclick:"window.__save()"},["Guardar"]),
    h("button",{class:"btn",onclick:"window.__test()"},["Probar token"])));
  const out = h("div",{id:"setOut",style:"margin-top:10px;font-size:12.5px"});
  body.append(out);
  card.append(body); root.append(card);
  root.append(h("p",{style:"font-size:11.5px;color:var(--muted-fg);max-width:560px;margin-top:14px"},[st.note||"En modo simulación el motor genera una flota sintética para validar el producto sin llamar a la nube."]));
  window.__save = async () => {
    const key = document.getElementById("setKey").value.trim();
    const live = document.getElementById("mLive").classList.contains("active");
    const r = await API("/api/settings",{method:"POST",body:JSON.stringify({api_key:key,org_id:document.getElementById("setOrg").value,mode:live?"live":"simulation"})});
    if (r.ok) { toast("Guardado","ok"); S.mode=r.mode; S.dryRun=r.dry_run; window.GF.state&&0; document.getElementById("modeBadge").textContent = (r.dry_run?"dry-run":"live"); } else toast(r.error||"error","bad");
  };
  window.__test = async () => {
    const key = document.getElementById("setKey").value.trim();
    const r = await API("/api/settings/test",{method:"POST",body:JSON.stringify({api_key:key})});
    out.innerHTML = r.ok?'<span class="tag inside">token válido ✓</span> '+esc(r.org_name||"") : '<span class="tag nocomp">'+esc(r.error||"inválido")+"</span>";
  };
  document.getElementById("mSim").onclick = () => { document.getElementById("mSim").classList.add("active"); document.getElementById("mLive").classList.remove("active"); };
  document.getElementById("mLive").onclick = () => { document.getElementById("mLive").classList.add("active"); document.getElementById("mSim").classList.remove("active"); };
};

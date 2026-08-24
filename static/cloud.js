    const STATE_URL = "https://raw.githubusercontent.com/adrimg3196/lucidfence/cloud-state/data/cloud_state.json";

    const BB = {minLat:40.38, maxLat:40.44, minLng:-3.74, maxLng:-3.68};
    function proj(lat,lng){
      const x = (lng-BB.minLng)/(BB.maxLng-BB.minLng)*580+10;
      const y = (BB.maxLat-lat)/(BB.maxLat-BB.minLat)*320+10;
      return [x,y];
    }

    let CURRENT = null;
    let TENANTS = [];
    let FILTERED_TENANTS = [];

    function esc(v){
      return String(v == null ? "" : v).replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;","\"":"&quot;"}[ch]));
    }

    function pdfSafe(v, max){
      let s = String(v == null ? "" : v).replace(/[\r\n]+/g, " ").replace(/[áÁ]/g,"a").replace(/[éÉ]/g,"e").replace(/[íÍ]/g,"i").replace(/[óÓ]/g,"o").replace(/[úÚüÜ]/g,"u").replace(/[ñÑ]/g,"n").replace(/[—·]/g,"-");
      s = s.replace(/[\\()]/g, ch => "\\"+ch);
      if(max && s.length > max) s = s.slice(0, max-3) + "...";
      return s;
    }

    function simplePdf(lines){
      let y = 790;
      const streamLines = ["BT", "/F1 11 Tf"];
      lines.slice(0,48).forEach((line, i)=>{
        const size = i === 0 ? 16 : 11;
        streamLines.push(`/F1 ${size} Tf`);
        streamLines.push(`1 0 0 1 50 ${y} Tm (${pdfSafe(line)}) Tj`);
        y -= i === 0 ? 18 : 14;
      });
      streamLines.push("ET");
      const stream = streamLines.join("\n");
      const objs = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        "4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        `5 0 obj\n<< /Length ${stream.length} >>\nstream\n${stream}\nendstream\nendobj\n`,
      ];
      let out = "%PDF-1.4\n";
      const offsets = [0];
      objs.forEach(o=>{ offsets.push(out.length); out += o; });
      const xref = out.length;
      out += `xref\n0 ${objs.length+1}\n0000000000 65535 f \n`;
      offsets.slice(1).forEach(off=>{ out += `${String(off).padStart(10,"0")} 00000 n \n`; });
      out += `trailer\n<< /Size ${objs.length+1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
      return out;
    }

    function downloadTenantCompliancePdf(){
      const sel = document.getElementById("tenantSel");
      const selected = FILTERED_TENANTS[parseInt(sel.value || "0")] || FILTERED_TENANTS[0];
      const s = selected ? selected.t : ((CURRENT && CURRENT.tenants && CURRENT.tenants[0]) || CURRENT || {});
      const devices = s.devices || [];
      const totals = s.totals || {};
      const lines = [
        "LucidFence - Reporte de conformidad",
        `Tenant: ${tenantName(s, selected ? selected.i : 0)}`,
        `Generado: ${(CURRENT && CURRENT.generated_at) || new Date().toISOString()}`,
        "",
        `Dispositivos: ${totals.devices || devices.length || 0}`,
        `Dentro: ${totals.inside || 0}`,
        `Fuera: ${totals.outside || 0}`,
        `No conformes: ${totals.non_compliant || devices.filter(d=>d.compliant===false).length}`,
        `Compliance: ${totals.compliance_rate_pct || 0}%`,
        "",
        "Dispositivo | Plataforma | Estado | Conforme | Riesgo",
        ...devices.slice(0,34).map(d=>`${pdfSafe(d.name || d.device_id,24)} | ${pdfSafe(platformLabel(d.platform),11)} | ${pdfSafe(d.fence_state || "-",11)} | ${d.compliant===false?"NO":"SI"} | ${d.risk_score || 0}`),
      ];
      if(devices.length > 34) lines.push(`... ${devices.length - 34} dispositivos mas`);
      const blob = new Blob([simplePdf(lines)], {type:"application/pdf"});
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "reporte_conformidad_lucidfence.pdf";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(()=>URL.revokeObjectURL(a.href), 1000);
    }

    function tenantName(t, i){
      return t.tenant || t.org_id || ("tenant"+i);
    }

    function platformLabel(p){
      const key = String(p||"unknown").toLowerCase();
      return ({android:"Android", ios:"iOS", ipados:"iPadOS", chromeos:"ChromeOS", windows:"Windows", macos:"macOS"})[key] || key;
    }

    function platformClass(p){
      const key = String(p||"unknown").toLowerCase().replace(/[^a-z0-9_-]/g, "-");
      return `plat ${key}`;
    }

    async function load(){
      try{
        const r = await fetch(STATE_URL, {cache:"no-store"});
        if(!r.ok) throw new Error("HTTP "+r.status);
        const s = await r.json();
        render(s);
      }catch(e){
        document.getElementById("ts").textContent = " (error: "+e.message+")";
      }
    }

    function render(s){
      const tenants = (s.tenants && s.tenants.length) ? s.tenants : [s];
      CURRENT = s;
      TENANTS = tenants;
      document.getElementById("ts").textContent = " · generado " + (s.generated_at||"");
      applyTenantFilter(document.getElementById("tenantFilter").value || "");
      const agg = s.totals || (tenants[0] && tenants[0].totals) || {};
      const kpis = [
        ["Dispositivos", agg.devices||0, ""],
        ["Dentro", agg.inside||0, "var(--green)"],
        ["Fuera", agg.outside||0, "var(--red)"],
        ["No conformes", agg.non_compliant||0, "var(--amber)"],
        ["Compliance", (agg.compliance_rate_pct||0)+"%", "var(--blue)"],
        ["iOS Geo OK", (agg.ios_geofence_compliance_rate_pct||0)+"%", "var(--green)"],
        ["ChromeOS", ((agg.platform_counts&&agg.platform_counts.chromeos)||agg.chromeos_devices||0), "var(--green)"],
      ];
      document.getElementById("kpis").innerHTML = kpis.map(k=>
        `<div class="kpi"><div class="v" style="color:${k[2]}">${k[1]}</div><div class="l">${k[0]}</div></div>`).join("");
    }

    function applyTenantFilter(q){
      const needle = (q||"").trim().toLowerCase();
      const filterActive = !!needle;
      FILTERED_TENANTS = TENANTS.map((t,i)=>({t,i})).filter(({t,i})=>{
        const label = tenantName(t,i) + " " + (t.org_id||"");
        return !needle || label.toLowerCase().includes(needle);
      });
      if(!FILTERED_TENANTS.length && TENANTS.length && !filterActive){
        FILTERED_TENANTS = TENANTS.map((t,i)=>({t,i}));
      }
      const sel = document.getElementById("tenantSel");
      if(!FILTERED_TENANTS.length){
        sel.innerHTML = `<option value="0">Sin tenants para "${esc(q)}"</option>`;
        document.getElementById("deptDensity").innerHTML = `Sin tenants para "${esc(q)}".`;
        document.querySelector("#devices tbody").innerHTML = "";
        document.getElementById("map").innerHTML = "";
        return;
      }
      sel.innerHTML = FILTERED_TENANTS.map(({t,i},pos)=>
        `<option value="${pos}">${esc(tenantName(t,i))} · ${((t.totals&&t.totals.devices)||0)} dev</option>`).join("");
      if(CURRENT) renderTenant(0);
    }

    function departmentDensity(devices){
      const groups = new Map();
      (devices||[]).forEach(d=>{
        const dept = d.department || "Sin departamento";
        if(!groups.has(dept)) groups.set(dept, {dept, count:0, inside:0, outside:0, nonCompliant:0, risk:0, lat:0, lng:0, geo:0});
        const g = groups.get(dept);
        g.count += 1;
        if(d.fence_state === "inside") g.inside += 1;
        if(d.fence_state === "outside") g.outside += 1;
        if(d.compliant === false) g.nonCompliant += 1;
        g.risk += Number(d.risk_score||0);
        if(d.lat != null && d.lng != null){ g.lat += Number(d.lat); g.lng += Number(d.lng); g.geo += 1; }
      });
      return Array.from(groups.values()).map(g=>({
        ...g,
        avgRisk: g.count ? Math.round(g.risk/g.count) : 0,
        lat: g.geo ? g.lat/g.geo : null,
        lng: g.geo ? g.lng/g.geo : null,
      })).sort((a,b)=>b.count-a.count || b.avgRisk-a.avgRisk || a.dept.localeCompare(b.dept));
    }

    function renderDepartmentDensity(s, svg, NS){
      const density = departmentDensity(s.devices||[]);
      const max = Math.max(1, ...density.map(g=>g.count));
      density.forEach(g=>{
        if(g.lat == null || g.lng == null) return;
        const [x,y] = proj(g.lat,g.lng);
        const ratio = g.count / max;
        const risk = Math.min(1, g.avgRisk / 100);
        const r = 14 + ratio * 34;
        const color = risk > .45 || g.outside > g.inside ? "255,107,107" : "78,167,252";
        const halo = document.createElementNS(NS,"circle");
        halo.setAttribute("cx",x); halo.setAttribute("cy",y); halo.setAttribute("r",r.toFixed(1));
        halo.setAttribute("fill",`rgba(${color},${(0.16 + ratio*.22).toFixed(2)})`);
        halo.setAttribute("stroke",`rgba(${color},.75)`);
        halo.setAttribute("stroke-width","1");
        const title = document.createElementNS(NS,"title");
        title.textContent = `${g.dept}: ${g.count} dispositivos · fuera ${g.outside} · riesgo medio ${g.avgRisk}`;
        halo.appendChild(title);
        svg.appendChild(halo);
      });
      const el = document.getElementById("deptDensity");
      if(!density.length){ el.innerHTML = "Sin dispositivos con departamento."; return; }
      el.innerHTML = density.map(g=>{
        const pct = Math.round((g.count/max)*100);
        return `<div class="density-row"><span class="name">${esc(g.dept)}</span>`+
          `<span class="density-track"><span class="density-fill" style="width:${pct}%"></span></span>`+
          `<span>${g.count} dev · ${g.outside} fuera · riesgo ${g.avgRisk}</span></div>`;
      }).join("");
    }

    function renderTenant(idx){
      if(!CURRENT) return;
      const filterActive = (document.getElementById("tenantFilter").value||"").trim().length > 0;
      const tenants = FILTERED_TENANTS.length ? FILTERED_TENANTS.map(x=>x.t) : (filterActive ? [] : ((CURRENT.tenants && CURRENT.tenants.length) ? CURRENT.tenants : [CURRENT]));
      const s = tenants[idx] || tenants[0];
      const svg = document.getElementById("map");
      svg.innerHTML = "";
      if(!s){
        document.querySelector("#devices tbody").innerHTML = "";
        document.getElementById("deptDensity").innerHTML = "Sin tenants que coincidan con el filtro.";
        document.getElementById("cve").innerHTML = "-";
        document.getElementById("soar").innerHTML = "-";
        return;
      }
      const NS = "http://www.w3.org/2000/svg";
      renderDepartmentDensity(s, svg, NS);
      (s.fences||[]).forEach(f=>{
        if((f.kind==="circle" || f.type==="circle") && f.center){
          const [cx,cy] = proj(f.center.lat,f.center.lng);
          const r = Math.max(8, (f.radius_m||500)/1200*280);
          const c = document.createElementNS(NS,"circle");
          c.setAttribute("cx",cx); c.setAttribute("cy",cy); c.setAttribute("r",r);
          c.setAttribute("fill","rgba(94,106,213,.10)"); c.setAttribute("stroke","#5e6ad5");
          c.setAttribute("stroke-width","1.5");
          svg.appendChild(c);
          const tx = document.createElementNS(NS,"text");
          tx.setAttribute("x",cx); tx.setAttribute("y",cy-r-4);
          tx.setAttribute("fill","#8a8f98"); tx.setAttribute("font-size","10");
          tx.textContent = f.name||f.id;
          svg.appendChild(tx);
        }
      });
      (s.devices||[]).forEach(d=>{
        if(d.lat==null||d.lng==null) return;
        const [x,y] = proj(d.lat,d.lng);
        const color = d.fence_state==="inside"?"#4cc38a":"#ff6b6b";
        const c = document.createElementNS(NS,"circle");
        c.setAttribute("cx",x); c.setAttribute("cy",y); c.setAttribute("r","6");
        c.setAttribute("fill",color); c.setAttribute("stroke","#08090a"); c.setAttribute("stroke-width","1.5");
        const t2 = document.createElementNS(NS,"title");
        t2.textContent = `${d.name} · ${d.department||"Sin departamento"} · ${d.fence_state} · riesgo ${d.risk_score||0}`;
        c.appendChild(t2);
        svg.appendChild(c);
      });
      const tb = document.querySelector("#devices tbody");
      tb.innerHTML = "";
      (s.devices||[]).forEach(d=>{
        const st = d.fence_state==="inside"?"in":(d.fence_state==="outside"?"out":"unk");
        const stxt = d.fence_state==="inside"?"dentro":(d.fence_state==="outside"?"fuera":"desconocido");
        const comp = d.compliant===false?"comp-no":"comp-yes";
        const ctxt = d.compliant===false?"no":"sí";
        const geoApplicable = d.geofence_compliance_applicable===true;
        const geoClass = !geoApplicable || d.geofence_compliant==null ? "unk" : (d.geofence_compliant ? "comp-yes" : "comp-no");
        const geoText = !geoApplicable ? "-" : (d.geofence_compliant==null ? "sin señal" : (d.geofence_compliant ? "ok" : "fuera"));
        tb.insertAdjacentHTML("beforeend",
          `<tr><td class="tag">${esc(d.device_id)}</td><td>${esc(d.name||"")}</td>`+
          `<td><span class="pill ${esc(platformClass(d.platform))}">${esc(platformLabel(d.platform))}</span></td>`+
          `<td><span class="pill ${st}">${stxt}</span></td>`+
          `<td><span class="pill ${comp}">${ctxt}</span></td>`+
          `<td><span class="pill ${geoClass}" title="${esc(d.geofence_compliance_label||"")}">${geoText}</span></td>`+
          `<td>${d.risk_score||0}</td><td>${esc(d.department||"")}</td></tr>`);
      });
      const cve = s.cve_summary||{};
      if(cve.demo || cve.apps_total!=null){
        let html = `Apps escaneadas: <b>${cve.apps_total||0}</b> · Vulnerables: <b style="color:var(--red)">${cve.vulnerable_apps||0}</b>`+
                   ` · Críticas: <b style="color:var(--red)">${cve.critical_cve_apps||0}</b> · Altas: <b style="color:var(--amber)">${cve.high_cve_apps||0}</b>`;
        if(cve.ejemplos && cve.ejemplos.length){
          html += `<div style="margin-top:6px">`;
          cve.ejemplos.forEach(e=>{
            const col = e.severity==="critical"?"var(--red)":"var(--amber)";
            html += `<span class="pill" style="background:rgba(255,107,107,.12);color:${col};margin-right:6px">${e.cve} · ${e.app} ${e.version}</span>`;
          });
          html += `</div>`;
        }
        if(cve.demo) html += ` <span class="meta">(datos demo)</span>`;
        document.getElementById("cve").innerHTML = html;
      } else {
        document.getElementById("cve").innerHTML = "No disponible en este ciclo.";
      }
      const soar = s.soar||{};
      if(soar.playbooks && soar.playbooks.length){
        let html = soar.playbooks.map(p=>p.name||p.id).join("<br>");
        html += `<div class="meta" style="margin-top:6px">Dispositivos que disparan playbooks: <b>${soar.matched?soar.matched.length:0}</b>`+
                (soar.matched&&soar.matched.length?` (${soar.matched.slice(0,3).join(", ")}${soar.matched.length>3?"…":""})`:"")+
                (soar.demo?` · <span class="meta">(datos demo)</span>`:"")+`</div>`;
        document.getElementById("soar").innerHTML = html;
      } else {
        document.getElementById("soar").innerHTML = "Sin playbooks.";
      }
    }
    load();
    setInterval(load, 60000);

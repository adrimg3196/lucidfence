(function(){
  'use strict';
  let state=null;
  const $=selector=>document.querySelector(selector);
  const $$=selector=>Array.from(document.querySelectorAll(selector));
  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  function toast(message){const node=$('#toast');node.textContent=message;node.classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.classList.remove('show'),2600);}
  function showView(id){
    $$('.view').forEach(node=>node.classList.toggle('active',node.id==='view-'+id));
    $$('.nav [data-view]').forEach(node=>node.classList.toggle('active',node.dataset.view===id));
    $('#crumb').textContent=({company:'Compañía',fleet:'Flota',map:'Geovallas',connect:'Conectar'})[id]||'Compañía';
    if(location.hash!=='#'+id) history.replaceState(null,'','#'+id);
  }
  function evidenceCoverage(){const tasks=state.tasks||[];return tasks.length?Math.round(100*tasks.filter(t=>Array.isArray(t.evidence)&&t.evidence.length).length/tasks.length):100;}
  function render(){
    const snap=LucidFenceWeb.snapshot(state);
    $('#cycleValue').textContent=state.cycle||0;
    $('#goalsValue').textContent=(state.goals||[]).filter(g=>g.status==='active').length;
    $('#outsideValue').textContent=snap.outside;
    $('#complianceValue').textContent=snap.compliance+'%';
    $('#evidenceValue').textContent=evidenceCoverage()+'%';
    $('#pauseBtn').textContent=state.paused?'Reanudar compañía':'Pausar compañía';
    $('#uemGateway').value=state.settings?.gatewayUrl||'';
    $('#runCycle').disabled=state.paused||!(state.goals||[]).some(g=>g.status==='active');
    $('#agents').innerHTML=(state.agents||LucidFenceWeb.AGENTS).map(a=>`<article class="agent"><strong>${esc(a.name)}</strong><p>${esc(a.mission)}</p></article>`).join('');
    $('#goals').innerHTML=(state.goals||[]).length?(state.goals||[]).slice().reverse().map(g=>`<article class="row"><div><strong>${esc(g.title)}</strong><p>${esc(g.outcome)}<br>${esc(g.metric.name)}: ${g.metric.current===null?'—':esc(g.metric.current)} → ${esc(g.metric.target)}</p></div><span class="tag">${esc(g.status.toUpperCase())}</span></article>`).join(''):'<div class="empty">Crea el primer objetivo medible. Ningún ciclo comienza sin una meta.</div>';
    $('#tasks').innerHTML=(state.tasks||[]).length?(state.tasks||[]).slice(-10).reverse().map(t=>`<article class="row"><div><strong>${esc(t.action)}</strong><p>${esc(t.title)} · ${esc(t.agent)}<br>${esc(t.evidence?.[0]?.source||'evidence')} = ${esc(t.evidence?.[0]?.value??'—')}</p></div><span class="tag ${t.risk==='medium'?'medium':''}">${esc(t.risk.toUpperCase())} · ${esc(t.status.toUpperCase())}</span></article>`).join(''):'<div class="empty">La cola está vacía. Ejecuta un ciclo seguro para producir evidencia.</div>';
    $('#fleetRows').innerHTML=(state.devices||[]).map(d=>`<tr><td><strong>${esc(d.name)}</strong><br><span style="color:var(--muted)">${esc(d.id)}</span></td><td>${esc(d.platform)}</td><td class="state ${esc(d.fenceState)}">${esc(d.fenceState)}</td><td>${esc(d.risk)}</td><td>${d.compliant?'Cumple':'No cumple'}</td></tr>`).join('');
    const map=$('#map');if(map){map.querySelectorAll('.point').forEach(node=>node.remove());
    (state.devices||[]).filter(d=>d.lat!==null&&d.lng!==null).forEach((d,index)=>{const point=document.createElement('button');point.className='point '+(d.fenceState==='outside'?'out':'');point.style.left=(23+(index*13)%62)+'%';point.style.top=(22+(index*17)%59)+'%';point.title=d.name+' · '+d.fenceState;point.setAttribute('aria-label',point.title);map.appendChild(point);});}
    const fab=$('#uemFab');if(fab){const on=Boolean(state.settings?.gatewayUrl);fab.classList.toggle('connected',on);fab.innerHTML='<span class="dot"></span>'+(on?'Sincronizar UEM':'Conectar UEM');}
  }
  async function persist(){state.updatedAt=new Date().toISOString();await WebStore.save(state);render();}
  function cycleWithWorker(){return new Promise((resolve,reject)=>{
    if(!('Worker' in window)){try{resolve({state,result:LucidFenceWeb.runCycle(state,LucidFenceWeb.snapshot(state))});}catch(error){reject(error);}return;}
    const worker=new Worker('./web-worker.js');const timer=setTimeout(()=>{worker.terminate();reject(new Error('El worker no respondió'));},6000);
    worker.onmessage=event=>{clearTimeout(timer);worker.terminate();event.data.ok?resolve(event.data):reject(new Error(event.data.error));};
    worker.onerror=event=>{clearTimeout(timer);worker.terminate();reject(new Error(event.message||'Worker error'));};
    worker.postMessage({type:'RUN_CYCLE',state,snapshot:LucidFenceWeb.snapshot(state)});
  });}
  async function runCycle(){
    try{const output=await cycleWithWorker();state=output.state;await persist();toast(`Ciclo ${output.result.cycle}: ${output.result.tasks.length} tareas con evidencia`);
      if(state.settings?.soarLinked){
        const snap=LucidFenceWeb.snapshot(state);
        const soar=output.result.tasks.find(t=>t.action==='recommend_soar_playbook');
        if(soar||snap.outside>0)await triggerSoar({title:soar?soar.title:'Dispositivo fuera de geovalla',detail:soar?soar.evidence:[],
          outside:snap.outside,critical:snap.critical,cycle:output.result.cycle}).catch(e=>toast('SOAR: '+e.message));
      }
    }catch(error){toast(error.message);}
  }
  async function createGoal(event){
    event.preventDefault();
    try{LucidFenceWeb.createGoal(state,{title:$('#goalTitle').value,outcome:$('#goalOutcome').value,target:$('#goalTarget').value,autonomy:$('#goalAutonomy').value});await persist();event.target.reset();$('#goalTarget').value='0';$('#goalAutonomy').value='simulate';toast('Objetivo creado en este navegador');}catch(error){toast(error.message);}
  }
  async function importWorkspace(file){
    try{const raw=JSON.parse(await file.text());const clean=LucidFenceWeb.sanitizeImport(raw);if(!Array.isArray(clean.devices))throw new Error('El workspace necesita una lista devices');state={...LucidFenceWeb.initialState(),...clean,agents:LucidFenceWeb.AGENTS};await persist();toast('Workspace importado sin secretos');}catch(error){toast('Importación bloqueada: '+error.message);}
  }
  function exportWorkspace(){const blob=new Blob([JSON.stringify(state,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='lucidfence-workspace.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),500);}
  async function init(){
    state=await WebStore.load();state={...LucidFenceWeb.initialState(),...state,agents:LucidFenceWeb.AGENTS};
    $('#goalForm').addEventListener('submit',createGoal);$('#runCycle').addEventListener('click',runCycle);
    $('#pauseBtn').addEventListener('click',async()=>{state.paused=!state.paused;await persist();toast(state.paused?'Compañía pausada':'Compañía reanudada');});
    $('#exportBtn').addEventListener('click',exportWorkspace);$('#resetBtn').addEventListener('click',async()=>{if(confirm('¿Eliminar el workspace guardado en este navegador?')){state=await WebStore.reset();render();toast('Workspace restablecido');}});
    $('#importFile').addEventListener('change',event=>{if(event.target.files[0])importWorkspace(event.target.files[0]);event.target.value='';});
    // Asistente de conexión UEM (wizard). Campos por proveedor; el token vive solo en memoria.
    const uem={token:''};
    // ponytail: un mapa de campos, no 7 formularios. secret:true => va en memoria, jamás se persiste.
    const UEM_FIELDS={
      applivery:[{k:'workspaceId',l:'Workspace ID'},{k:'bearerToken',l:'Bearer Token',secret:true}],
      intune:[{k:'tenantId',l:'Tenant ID'},{k:'clientId',l:'Client ID'},{k:'clientSecret',l:'Client Secret',secret:true}],
      jamf:[{k:'baseUrl',l:'Jamf Pro URL'},{k:'clientId',l:'Client ID'},{k:'clientSecret',l:'Client Secret',secret:true}],
      workspace_one:[{k:'awHost',l:'Workspace ONE Host'},{k:'tenantCode',l:'Tenant Code (aw-tenant-code)'},{k:'username',l:'Username'},{k:'password',l:'Password',secret:true}],
      soti:[{k:'mcUrl',l:'MobiControl URL'},{k:'username',l:'Username'},{k:'password',l:'Password',secret:true}],
      fleet:[{k:'fleetUrl',l:'Fleet Server URL'},{k:'apiToken',l:'API Token',secret:true}],
      chromeos:[{k:'customerId',l:'Customer ID'},{k:'clientId',l:'Client ID'},{k:'clientSecret',l:'Client Secret',secret:true},{k:'refreshToken',l:'OAuth Refresh Token',secret:true}],
      other:[{k:'apiUrl',l:'API URL'},{k:'apiToken',l:'API Token',secret:true}]
    };
    UEM_FIELDS.cves=[{k:'baseUrl',l:'NVD API Base URL'},{k:'apiKey',l:'NVD API Key (opcional)',secret:true}];UEM_FIELDS.cves.kind='security';UEM_FIELDS.cves.path='/v1/cves';
    UEM_FIELDS.soar=[{k:'baseUrl',l:'SOAR API Base URL'},{k:'apiToken',l:'API Token',secret:true},{k:'action',l:'Acción: block (bloquear) o monitor'}];UEM_FIELDS.soar.kind='security';UEM_FIELDS.soar.path='/v1/soar';
    function setStep(n){
      $$('.steps li').forEach(li=>li.classList.toggle('active',li.dataset.step===String(n)));
      $$('[data-wstep]').forEach(node=>node.hidden=node.dataset.wstep!==String(n));
    }
    function renderFields(){ // depende del proveedor elegido en paso 1
      const p=$('#uemProvider').value,fields=UEM_FIELDS[p]||UEM_FIELDS.other;
      $('#uemFields').innerHTML=fields.map(f=>`<label class="sr" for="uem_${f.k}">${f.l}</label><input class="input" id="uem_${f.k}" type="${f.secret?'password':'text'}" autocomplete="off" placeholder="${f.l}">`).join('');
    }
    function validateApiUrl(value){
      const url=new URL(value.trim());
      if(url.username||url.password||url.search)throw new Error('La URL no puede contener credenciales ni parámetros');
      if(url.protocol!=='https:'&&!['localhost','127.0.0.1'].includes(url.hostname))throw new Error('Usa HTTPS');
      return url.origin;
    }
    async function uemSync(base,provider,headers){
      const fm=UEM_FIELDS[provider]||UEM_FIELDS.other;
      const response=await fetch(base+(fm.path||'/v1/fleet'),{method:'GET',credentials:'omit',cache:'no-store',headers:{accept:'application/json',...headers}});
      if(!response.ok)throw new Error('El conector respondió HTTP '+response.status);
      const payload=LucidFenceWeb.sanitizeImport(await response.json());
      if(fm.kind==='security')return []; // health-check, no es flota
      if(!Array.isArray(payload.devices)||payload.devices.length>10000)throw new Error('Respuesta de flota inválida');
      return payload.devices;
    }
    $('#uemProvider').addEventListener('change',renderFields);
    $('#uemNext1').addEventListener('click',()=>setStep(2));
    $('#uemBack2').addEventListener('click',()=>setStep(1));
    $('#uemNext2').addEventListener('click',async()=>{
      try{
        const base=validateApiUrl($('#uemGateway').value),p=$('#uemProvider').value;
        const fields=UEM_FIELDS[p]||UEM_FIELDS.other,nonSecret={};
        uem.token=''; // se reconstruye abajo en memoria, sin persistir
        fields.forEach(f=>{const v=$('#uem_'+f.k).value.trim();if(v){if(f.secret)uem.token+=f.k+'='+v+'\n';else nonSecret[f.k]=v;}});
        const fm=UEM_FIELDS[p]||UEM_FIELDS.other;
        const creds=uem.token?btoa(uem.token):'';
        state.settings={...(state.settings||{}),gatewayUrl:base};
        if(fm.kind==='security'){state.settings.secCredsB64=creds;state.settings.soarAction=nonSecret.action||'monitor';} // security no pisa las creds del UEM
        else{state.settings.uemProvider=p;state.settings.uemFields=nonSecret;state.settings.uemCredsB64=creds;}
        await persist();
        const secretCount=fields.filter(f=>f.secret).length;
        $('#uemSummary').innerHTML='<b>Proveedor:</b> '+esc($('#uemProvider').selectedOptions[0].textContent)+'<br><b>Gateway:</b> '+esc(base)+'<br><b>Campos enviados:</b> '+(Object.keys(nonSecret).join(', ')||'ninguno')+'<br><b>Secretos:</b> '+secretCount+' en memoria, no persistidos';
        setStep(3);toast('Conexión API lista para '+p+'; secretos en memoria');
      }catch(error){toast('Conexión API no válida: '+error.message);}
    });
    $('#uemBack3').addEventListener('click',()=>setStep(2));
    $('#uemTest').addEventListener('click',async()=>{ // ponytail: creds en uemCredsB64 (UEM) o secCredsB64 (security), reutilizados por el FAB
      try{
        const base=state.settings?.gatewayUrl,provider=$('#uemProvider').value;
        const fm=UEM_FIELDS[provider]||UEM_FIELDS.other;
        if(!base)throw new Error('Configura la URL en el paso 2');
        const b64=state.settings?.[fm.kind==='security'?'secCredsB64':'uemCredsB64']||(uem.token?btoa(uem.token):'');
        const ws=state.settings?.uemFields?.workspaceId;
        const headers={};
        if(b64){headers['x-uem-provider']=provider;headers['x-uem-secrets']=b64;}
        if(ws)headers['x-uem-workspace']=ws;
        await uemSync(base,provider,headers);
        if(fm.kind==='security'){ // conector de seguridad: health-check, no reemplaza la flota
          const linked={...state.settings,mode:'security_link',lastSync:new Date().toISOString()};
          if(provider==='cves')linked.cvesLinked=true; if(provider==='soar')linked.soarLinked=true;
          state.settings=linked;
          await persist();toast('Conector de seguridad listo: '+provider);uem.token='';showView('company');return;
        }
        const devices=await uemSync(base,provider,headers);
        state.devices=devices;await enrichRiskWithCves();
        state.settings={...state.settings,mode:'live_gateway',lastSync:new Date().toISOString()};
        await persist();toast(devices.length+' dispositivos sincronizados vía '+provider+(state.settings.cvesLinked?' (+CVE)':''));uem.token='';showView('fleet');
      }catch(error){toast('Verificación fallida: '+error.message);}
    });
    async function enrichRiskWithCves(){ // sube riesgo de la flota por CVEs reales del gateway
      if(!state.settings?.cvesLinked||!state.settings?.gatewayUrl)return;
      const b64=state.settings.secCredsB64||'',headers={accept:'application/json'};
      if(b64){headers['x-uem-provider']='cves';headers['x-uem-secrets']=b64;}
      const r=await fetch(state.settings.gatewayUrl+'/v1/cves/enrich',{method:'GET',credentials:'omit',cache:'no-store',headers});
      if(!r.ok)throw new Error('Enriquecimiento CVE HTTP '+r.status);
      const map=LucidFenceWeb.sanitizeImport(await r.json());
      const byP=map.byPlatform||{};
      const fallback={cveCount:Object.values(byP).reduce((a,c)=>a+(c.cveCount||0),0),cveCritical:Object.values(byP).some(c=>c.cveCritical)}; // ponytail: plataforma unknown/ausente usa el agregado total de NVD
      const order={low:0,medium:1,high:2,critical:3};
      const up=x=>order[x]??0;
      state.devices=(state.devices||[]).map(d=>{const c=byP[String(d.platform||'').toLowerCase()]||fallback;if(!c.cveCount)return d;
        const bump=c.cveCritical?'critical':c.cveCount?'high':d.risk;
        const risk=up(bump)>up(d.risk)?bump:d.risk;
        return {...d,cveCount:c.cveCount||0,cveCritical:c.cveCritical||0,risk};});
    }
    async function triggerSoar(payload){ // abre incidente en el SOAR conectado
      if(!state.settings?.soarLinked||!state.settings?.gatewayUrl)return;
      const b64=state.settings.secCredsB64||'',headers={'content-type':'application/json'};
      if(b64){headers['x-uem-provider']='soar';headers['x-uem-secrets']=b64;}
      const r=await fetch(state.settings.gatewayUrl+'/v1/soar/incident',{method:'POST',credentials:'omit',cache:'no-store',headers,body:JSON.stringify({...payload,action:state.settings.soarAction||'monitor'})});
      if(!r.ok)throw new Error('SOAR HTTP '+r.status);
      toast('SOAR → '+(state.settings.soarAction||'monitor')+': '+payload.title);
    }
    renderFields();setStep(1);
    $$('[data-view]').forEach(button=>button.addEventListener('click',()=>showView(button.dataset.view)));$$('[data-view-link]').forEach(button=>button.addEventListener('click',()=>showView(button.dataset.viewLink)));
    // FAB: acceso directo al wizard de conexión UEM desde cualquier vista.
    function syncFab(){
      const on=Boolean(state.settings?.gatewayUrl);
      $('#uemFab').classList.toggle('connected',on);
      $('#uemFab').innerHTML='<span class="dot"></span>'+(on?'Sincronizar UEM':'Conectar UEM');
    }
    $('#uemFab').addEventListener('click',async()=>{
      if(state.settings?.gatewayUrl){ // ya configurado: sync one-click
        try{
          const base=state.settings.gatewayUrl,provider=state.settings.uemProvider||$('#uemProvider').value;
          const b64=state.settings.uemCredsB64||'',ws=state.settings.uemFields?.workspaceId;
          const headers={};
          if(b64){headers['x-uem-provider']=provider;headers['x-uem-secrets']=b64;}
          if(ws)headers['x-uem-workspace']=ws;
          const fm=UEM_FIELDS[provider]||UEM_FIELDS.other;
          await uemSync(base,provider,headers);
          if(fm.kind==='security'){state.settings={...state.settings,mode:'security_link',lastSync:new Date().toISOString()};await persist();toast('Conector de seguridad listo: '+provider);showView('company');return;}
          const devices=await uemSync(base,provider,headers);
          state.devices=devices;await enrichRiskWithCves();
          state.settings={...state.settings,mode:'live_gateway',lastSync:new Date().toISOString()};
          await persist();toast(devices.length+' dispositivos sincronizados vía '+provider+(state.settings.cvesLinked?' (+CVE)':''));showView('fleet');
        }catch(e){toast('Sincronización fallida: '+e.message);}
        return;
      }
      showView('connect'); // sin config: abre el wizard
    });
    addEventListener('hashchange',()=>{const id=location.hash.slice(1);if(['company','fleet','map','connect'].includes(id))showView(id);});
    render();showView(['company','fleet','map','connect'].includes(location.hash.slice(1))?location.hash.slice(1):'company');
    window.LucidFenceApp={getState:()=>LucidFenceWeb.clone(state),runCycle};
    if('serviceWorker' in navigator&&location.protocol.startsWith('http'))navigator.serviceWorker.register('./sw.js').catch(()=>{});
  }
  addEventListener('DOMContentLoaded',init);
})();

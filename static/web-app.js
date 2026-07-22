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
    $('#gatewayUrl').value=state.settings?.gatewayUrl||'';
    $('#runCycle').disabled=state.paused||!(state.goals||[]).some(g=>g.status==='active');
    $('#agents').innerHTML=(state.agents||LucidFenceWeb.AGENTS).map(a=>`<article class="agent"><strong>${esc(a.name)}</strong><p>${esc(a.mission)}</p></article>`).join('');
    $('#goals').innerHTML=(state.goals||[]).length?(state.goals||[]).slice().reverse().map(g=>`<article class="row"><div><strong>${esc(g.title)}</strong><p>${esc(g.outcome)}<br>${esc(g.metric.name)}: ${g.metric.current===null?'—':esc(g.metric.current)} → ${esc(g.metric.target)}</p></div><span class="tag">${esc(g.status.toUpperCase())}</span></article>`).join(''):'<div class="empty">Crea el primer objetivo medible. Ningún ciclo comienza sin una meta.</div>';
    $('#tasks').innerHTML=(state.tasks||[]).length?(state.tasks||[]).slice(-10).reverse().map(t=>`<article class="row"><div><strong>${esc(t.action)}</strong><p>${esc(t.title)} · ${esc(t.agent)}<br>${esc(t.evidence?.[0]?.source||'evidence')} = ${esc(t.evidence?.[0]?.value??'—')}</p></div><span class="tag ${t.risk==='medium'?'medium':''}">${esc(t.risk.toUpperCase())} · ${esc(t.status.toUpperCase())}</span></article>`).join(''):'<div class="empty">La cola está vacía. Ejecuta un ciclo seguro para producir evidencia.</div>';
    $('#fleetRows').innerHTML=(state.devices||[]).map(d=>`<tr><td><strong>${esc(d.name)}</strong><br><span style="color:var(--muted)">${esc(d.id)}</span></td><td>${esc(d.platform)}</td><td class="state ${esc(d.fenceState)}">${esc(d.fenceState)}</td><td>${esc(d.risk)}</td><td>${d.compliant?'Cumple':'No cumple'}</td></tr>`).join('');
    const map=$('#map');map.querySelectorAll('.point').forEach(node=>node.remove());
    (state.devices||[]).filter(d=>d.lat!==null&&d.lng!==null).forEach((d,index)=>{const point=document.createElement('button');point.className='point '+(d.fenceState==='outside'?'out':'');point.style.left=(23+(index*13)%62)+'%';point.style.top=(22+(index*17)%59)+'%';point.title=d.name+' · '+d.fenceState;point.setAttribute('aria-label',point.title);map.appendChild(point);});
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
    try{const output=await cycleWithWorker();state=output.state;await persist();toast(`Ciclo ${output.result.cycle}: ${output.result.tasks.length} tareas con evidencia`);}catch(error){toast(error.message);}
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
    $('#saveGateway').addEventListener('click',async()=>{
      try{
        const value=$('#gatewayUrl').value.trim(),url=new URL(value);
        if(url.username||url.password||url.search)throw new Error('La URL no puede contener credenciales ni parámetros');
        if(url.protocol!=='https:'&&!['localhost','127.0.0.1'].includes(url.hostname))throw new Error('Usa HTTPS');
        state.settings={...(state.settings||{}),gatewayUrl:url.origin};await persist();toast('URL pública guardada; ningún secreto fue almacenado');
      }catch(error){toast('Gateway no guardado: '+error.message);}
    });
    $('#syncGateway').addEventListener('click',async()=>{
      try{
        const base=state.settings?.gatewayUrl;if(!base)throw new Error('Guarda primero la URL pública');
        const response=await fetch(base+'/v1/fleet',{method:'GET',credentials:'omit',cache:'no-store',headers:{accept:'application/json'}});
        if(!response.ok)throw new Error('El gateway respondió HTTP '+response.status);
        const payload=LucidFenceWeb.sanitizeImport(await response.json());
        if(!Array.isArray(payload.devices)||payload.devices.length>10000)throw new Error('Respuesta de flota inválida');
        state.devices=payload.devices;state.settings={...state.settings,mode:'live_gateway',lastSync:new Date().toISOString()};
        await persist();toast(payload.devices.length+' dispositivos sincronizados desde tu gateway');showView('fleet');
      }catch(error){toast('Sincronización fallida: '+error.message);}
    });
    $$('[data-view]').forEach(button=>button.addEventListener('click',()=>showView(button.dataset.view)));$$('[data-view-link]').forEach(button=>button.addEventListener('click',()=>showView(button.dataset.viewLink)));
    addEventListener('hashchange',()=>{const id=location.hash.slice(1);if(['company','fleet','map','connect'].includes(id))showView(id);});
    render();showView(['company','fleet','map','connect'].includes(location.hash.slice(1))?location.hash.slice(1):'company');
    window.LucidFenceApp={getState:()=>LucidFenceWeb.clone(state),runCycle};
    if('serviceWorker' in navigator&&location.protocol.startsWith('http'))navigator.serviceWorker.register('./sw.js').catch(()=>{});
  }
  addEventListener('DOMContentLoaded',init);
})();

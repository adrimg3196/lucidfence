(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports) module.exports=api;
  root.LucidFenceWeb=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const AGENTS=[
    ['mission-control','Mission Control','Prioriza objetivos y resuelve bloqueos'],
    ['field-intelligence','Inteligencia de campo','Comprueba movilidad y calidad de señal'],
    ['geo-policy','Política geográfica','Simula geovallas y rutas seguras'],
    ['uem-operations','Operaciones UEM','Prepara handoffs reversibles'],
    ['risk-compliance','Riesgo y compliance','Correlaciona CVE, riesgo y controles'],
    ['product-value','Valor de producto','Mide activación y utilidad'],
    ['roi-finance','ROI y finanzas','Explicita coste y ahorro'],
    ['independent-critic','Crítica independiente','Ejecuta pre-mortem y veta riesgo'],
    ['qa-sre','QA y SRE','Valida evidencia y rollback']
  ].map(([id,name,mission])=>({id,name,mission}));
  const FORBIDDEN=/^(wipe|factory_reset|delete_device|delete_tenant|disable_audit)$/;
  const SECRET_KEY=/(api[_-]?key|token|secret|password|credential|authorization)/i;
  const now=()=>new Date().toISOString();
  function id(prefix){
    const bytes=new Uint8Array(6);
    if(globalThis.crypto&&crypto.getRandomValues) crypto.getRandomValues(bytes);
    else for(let i=0;i<bytes.length;i++) bytes[i]=Math.floor(Math.random()*256);
    return prefix+'_'+Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
  }
  function initialState(){return{
    schema:'lucidfence-web/v1',cycle:0,paused:false,agents:AGENTS,goals:[],tasks:[],decisions:[],
    devices:[
      {id:'web-001',name:'Tablet Campo A1',platform:'Android',fenceState:'outside',risk:'high',compliant:false,lat:40.417,lng:-3.704},
      {id:'web-002',name:'Móvil Reparto B7',platform:'Android',fenceState:'inside',risk:'low',compliant:true,lat:40.416,lng:-3.702},
      {id:'web-003',name:'iPad Showroom C3',platform:'iOS',fenceState:'outside',risk:'critical',compliant:false,lat:40.421,lng:-3.708},
      {id:'web-004',name:'Terminal Almacén D2',platform:'Windows',fenceState:'inside',risk:'medium',compliant:true,lat:40.414,lng:-3.699},
      {id:'web-005',name:'Móvil Técnico E9',platform:'Android',fenceState:'unknown',risk:'medium',compliant:true,lat:null,lng:null},
      {id:'web-006',name:'Chromebook Kiosco F6',platform:'ChromeOS',fenceState:'inside',risk:'low',compliant:true,lat:40.419,lng:-3.701}
    ],
    geofences:[{id:'fence-madrid',name:'Operación Madrid',lat:40.4168,lng:-3.7038,radiusM:900}],
    settings:{mode:'demo',gatewayUrl:''},updatedAt:now()
  };}
  function clone(value){return JSON.parse(JSON.stringify(value));}
  function sanitizeImport(value){
    function walk(item,path){
      if(Array.isArray(item)) return item.map((v,i)=>walk(v,path+'['+i+']'));
      if(item&&typeof item==='object'){
        const clean={};
        for(const [key,val] of Object.entries(item)){
          if(SECRET_KEY.test(key)) throw new Error('Secret fields are forbidden in browser imports: '+path+key);
          clean[key]=walk(val,path+key+'.');
        }
        return clean;
      }
      if(typeof item==='string'&&/(bearer\s+[a-z0-9._-]{12,}|lf_[a-z0-9_-]{20,})/i.test(item)) throw new Error('Secret-like values are forbidden in browser imports');
      return item;
    }
    const clean=walk(value,'');
    if(!clean||typeof clean!=='object') throw new Error('Invalid workspace');
    return clean;
  }
  function createGoal(state,input){
    const title=String(input.title||'').trim(), outcome=String(input.outcome||'').trim();
    const target=Number(input.target);
    if(!title||!outcome||!Number.isFinite(target)) throw new Error('Objetivo, resultado y meta numérica son obligatorios');
    const autonomy=['observe','recommend','simulate'].includes(input.autonomy)?input.autonomy:'simulate';
    const goal={id:id('goal'),title:title.slice(0,160),outcome:outcome.slice(0,500),priority:'p0',autonomy,status:'active',metric:{name:'outside_devices',target,current:null,direction:'max'},constraints:['Sin secretos en el navegador','Sin acciones destructivas','Evidencia obligatoria'],createdAt:now()};
    state.goals.push(goal); state.updatedAt=now(); return goal;
  }
  function task(goal,agent,title,action,risk,evidence,autonomy){
    if(FORBIDDEN.test(action)) return {id:id('task'),goalId:goal.id,agent,title,action,risk:'forbidden',status:'blocked',evidence,acceptance:['La acción permanece bloqueada'],sideEffects:false,createdAt:now()};
    const safe=risk==='low', executed=safe&&autonomy==='simulate';
    return {id:id('task'),goalId:goal.id,agent,title,action,risk,status:executed?'executed':'proposed',requiresApprovals:risk==='medium'?1:risk==='high'?2:0,evidence,acceptance:['Resultado explicable, reversible y verificable'],sideEffects:false,result:executed?{mode:'browser_simulation',verified:true}:null,createdAt:now()};
  }
  function runCycle(state,snapshot){
    if(state.paused) throw new Error('La compañía está pausada');
    const goal=state.goals.find(g=>g.status==='active');
    if(!goal) throw new Error('Crea un objetivo medible antes del ciclo');
    state.cycle+=1;
    const evidence=(source,value)=>[{source,value,observedAt:now()}], created=[];
    if(Number(snapshot.outside)>0) created.push(task(goal,'geo-policy','Simular ajuste de geovalla','simulate_geofence','low',evidence('fleet.outside',Number(snapshot.outside)),goal.autonomy));
    if(Number(snapshot.unknown)>0) created.push(task(goal,'field-intelligence','Analizar calidad de ubicación','analyze_location_quality','low',evidence('fleet.unknown',Number(snapshot.unknown)),goal.autonomy));
    if(Number(snapshot.critical)>0) created.push(task(goal,'risk-compliance','Recomendar respuesta para CVE críticas','recommend_soar_playbook','medium',evidence('cve.critical',Number(snapshot.critical)),goal.autonomy));
    if(Number(snapshot.compliance)<90) created.push(task(goal,'risk-compliance','Evaluar brecha de compliance','assess_compliance','low',evidence('compliance.percent',Number(snapshot.compliance)),goal.autonomy));
    if(!created.length) created.push(task(goal,'product-value','Optimizar rutas sin cambios remotos','optimize_routes','low',evidence('fleet.devices',Number(snapshot.devices)||0),goal.autonomy));
    goal.metric.current=Number(snapshot.outside)||0; goal.metric.measuredAt=now();
    if(goal.metric.current<=goal.metric.target){goal.status='achieved';goal.achievedAt=now();}
    state.tasks.push(...created); state.tasks=state.tasks.slice(-300);
    state.decisions.push({id:id('decision'),cycle:state.cycle,goalId:goal.id,squad:[...new Set(['mission-control','qa-sre',...created.map(t=>t.agent)])],tasks:created.map(t=>t.id),at:now()});
    state.decisions=state.decisions.slice(-100); state.updatedAt=now();
    return {cycle:state.cycle,goalStatus:goal.status,tasks:clone(created)};
  }
  function snapshot(state){
    const devices=state.devices||[], known=devices.filter(d=>typeof d.compliant==='boolean');
    return {devices:devices.length,outside:devices.filter(d=>d.fenceState==='outside').length,unknown:devices.filter(d=>d.fenceState==='unknown').length,critical:devices.filter(d=>d.risk==='critical').length,compliance:known.length?Math.round(100*known.filter(d=>d.compliant).length/known.length):100};
  }
  return {AGENTS,initialState,sanitizeImport,createGoal,runCycle,snapshot,clone};
});

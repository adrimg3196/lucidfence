const json=(body,status=200,origin='')=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store','access-control-allow-origin':origin,'vary':'origin','x-content-type-options':'nosniff'}});
function allowedOrigin(request,env){const origin=request.headers.get('origin')||'';return origin&&origin===env.ALLOWED_ORIGIN?origin:'';}
function compactDevice(item){return{id:String(item.id||item.deviceId||item.device_id||''),name:String(item.name||item.deviceName||'Dispositivo'),platform:String(item.platform||item.os||'unknown'),fenceState:String(item.fenceState||item.fence_state||'unknown'),risk:String(item.risk||item.riskLevel||'unknown'),compliant:Boolean(item.compliant)};}
export default{
  async fetch(request,env){
    const url=new URL(request.url),origin=allowedOrigin(request,env);
    if(request.method==='OPTIONS')return new Response(null,{status:204,headers:{'access-control-allow-origin':origin,'access-control-allow-methods':'GET, OPTIONS','access-control-allow-headers':'content-type','access-control-max-age':'600','vary':'origin'}});
    if(url.pathname==='/health')return json({ok:true,mode:'read_only',configured:Boolean(env.UPSTREAM_BASE_URL&&env.UPSTREAM_TOKEN)},200,origin);
    if(!origin)return json({error:'origin_not_allowed'},403,'');
    if(request.method!=='GET')return json({error:'read_only_gateway'},405,origin);
    if(url.pathname!=='/v1/fleet')return json({error:'not_found'},404,origin);
    if(!env.UPSTREAM_BASE_URL||!env.UPSTREAM_TOKEN)return json({error:'gateway_not_configured'},503,origin);
    try{
      const upstream=new URL(env.FLEET_PATH||'/devices',env.UPSTREAM_BASE_URL);
      const response=await fetch(upstream,{headers:{authorization:`Bearer ${env.UPSTREAM_TOKEN}`,accept:'application/json'},signal:AbortSignal.timeout(8000)});
      if(!response.ok)return json({error:'upstream_unavailable',status:response.status},502,origin);
      const payload=await response.json(),items=Array.isArray(payload)?payload:(payload.devices||payload.items||[]);
      return json({source:'live_gateway',readOnly:true,devices:items.slice(0,10000).map(compactDevice)},200,origin);
    }catch(error){return json({error:'upstream_unavailable'},502,origin);}
  }
};

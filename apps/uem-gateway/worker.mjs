const json=(body,status=200,origin='')=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store','access-control-allow-origin':origin,'vary':'origin','x-content-type-options':'nosniff'}});
function allowedOrigin(request,env){const origin=request.headers.get('origin')||'';return origin&&origin===env.ALLOWED_ORIGIN?origin:'';}
function compactDevice(item){return{id:String(item.id||item.deviceId||item.device_id||''),name:String(item.name||item.deviceName||'Dispositivo'),platform:String(item.platform||item.os||'unknown'),fenceState:String(item.fenceState||item.fence_state||'unknown'),risk:String(item.risk||item.riskLevel||'unknown'),compliant:Boolean(item.compliant)};}
// NVD real (services.nvd.nist.gov) por keywordSearch — mismo patron que
// lucidfence/core/cve_feed_nvd.py (best-effort, no CPE exacto). Un
// NVD_API_KEY de Worker (opcional, wrangler secret put) sube el limite de
// 5 a 50 req/30s; sin el, best-effort y puede volver vacio por rate-limit.
const NVD_URL='https://services.nvd.nist.gov/rest/json/cves/2.0';
const CVE_PLATFORM_TERMS={ios:'apple ios',ipados:'apple ipados',macos:'apple macos',android:'google android',windows:'microsoft windows',chromeos:'google chrome os'};
function cvssSeverity(vuln){
  // baseSeverity vive dentro de cvssData en CVSS v3.x, pero como campo
  // hermano (fuera de cvssData) en CVSS v2 — asi lo define el schema NVD
  // oficial (cvss-v2 vs cvss-v30/v31 en cve_api_json_2.0.schema).
  const metrics=(vuln.cve&&vuln.cve.metrics)||{};
  for(const key of['cvssMetricV31','cvssMetricV30','cvssMetricV2']){
    for(const m of metrics[key]||[]){
      const sev=(m.baseSeverity||(m.cvssData&&m.cvssData.baseSeverity)||'').toLowerCase();
      if(sev)return sev;
    }
  }
  return'';
}
async function queryNvdPlatform(term,headers){
  try{
    const params=new URLSearchParams({keywordSearch:term,resultsPerPage:'10'});
    const res=await fetch(`${NVD_URL}?${params}`,{headers,signal:AbortSignal.timeout(6000)});
    if(!res.ok)return null;
    const data=await res.json();
    const vulns=Array.isArray(data.vulnerabilities)?data.vulnerabilities:[];
    return{cveCount:vulns.length,cveCritical:vulns.some(v=>cvssSeverity(v)==='critical')};
  }catch(error){return null;} // best-effort: rate-limit o timeout de NVD no rompe el enriquecimiento
}
async function enrichCves(env,origin){
  const headers={accept:'application/json'};
  if(env.NVD_API_KEY)headers.apiKey=env.NVD_API_KEY;
  const entries=await Promise.all(Object.entries(CVE_PLATFORM_TERMS).map(async([platform,term])=>[platform,await queryNvdPlatform(term,headers)]));
  const byPlatform={};
  for(const[platform,result]of entries)if(result)byPlatform[platform]=result;
  return json({source:'NVD',byPlatform},200,origin);
}
export default{
  async fetch(request,env){
    const url=new URL(request.url),origin=allowedOrigin(request,env);
    if(request.method==='OPTIONS')return new Response(null,{status:204,headers:{'access-control-allow-origin':origin,'access-control-allow-methods':'GET, OPTIONS','access-control-allow-headers':'content-type','access-control-max-age':'600','vary':'origin'}});
    if(url.pathname==='/health')return json({ok:true,mode:'read_only',configured:Boolean(env.UPSTREAM_BASE_URL&&env.UPSTREAM_TOKEN)},200,origin);
    if(!origin)return json({error:'origin_not_allowed'},403,'');
    if(request.method!=='GET')return json({error:'read_only_gateway'},405,origin);
    if(url.pathname==='/v1/cves/enrich')return enrichCves(env,origin);
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

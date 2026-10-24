// Isolated feasibility endpoint, not the product API. No secrets in responses/logs.
export function handler(env, transport = fetch) {
  const response = (status, value) => new Response(JSON.stringify(value), {status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
  async function equal(a,b) {
    const hash = async s => new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)));
    const [x,y]=await Promise.all([hash(a),hash(b)]);let diff=0;
    for(let i=0;i<x.length;i++)diff|=x[i]^y[i];return diff===0;
  }
  return async req => {
    if(req.method!=='POST')return response(405,{code:'method_not_allowed'});
    const secret=env('TICK_SECRET');
    if(!secret)return response(503,{code:'probe_auth_not_configured'});
    if(!await equal(req.headers.get('X-Probe-Secret')||'',secret))return response(401,{code:'probe_unauthorized'});
    try {
      if(!req.headers.get('Content-Type')?.startsWith('application/json'))return response(415,{code:'json_required'});
      const reader=req.body?.getReader();let size=0;const chunks=[];
      if(reader)while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>4096){await reader.cancel();return response(413,{code:'body_too_large'});}chunks.push(value);}
      const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
      const body=JSON.parse(new TextDecoder().decode(bytes));
      if(!body||Array.isArray(body)||Object.keys(body).some(k=>!['action','id','owner'].includes(k)))return response(400,{code:'invalid_fields'});
      if(body.owner!==undefined&&body.owner!=='demo')return response(403,{code:'owner_rejected'});
      if(['cookie_set','cookie_read','cookie_clear'].includes(body.action)) {
        if(req.headers.get('Origin')&&req.headers.get('Origin')!==env('APP_ORIGIN'))return response(403,{code:'origin_rejected'});
        const present=(req.headers.get('Cookie')||'').split(';').some(v=>v.trim()==='__Host-watchlist_probe=transport-check');
        const r=response(200,{probe:true,cookie_present:present});
        if(body.action!=='cookie_read')r.headers.set('Set-Cookie','__Host-watchlist_probe='+(body.action==='cookie_set'?'transport-check':'')+'; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age='+(body.action==='cookie_set'?'60':'0'));
        return r;
      }
      const keys=['APP_ORIGIN','DEMO_PASSWORD','SESSION_SECRET','TICK_SECRET','FUYAO_API_KEY','DEEPSEEK_API_KEY','SUPABASE_URL','SUPABASE_PUBLIC_URL','SUPABASE_SERVICE_ROLE_KEY','WATCHLIST_DATA_ORIGIN'];
      if(body.action==='status')return response(200,{probe:true,received_path:new URL(req.url).pathname,secrets_present:Object.fromEntries(keys.map(k=>[k,!!env(k)])),server_time:new Date().toISOString(),rpc_timeout_ms:8000,platform_max_execution_ms:null});
      if(!['write','read','fail','cleanup'].includes(body.action)||!/^[-a-f0-9]{36}$/i.test(body.id||''))return response(400,{code:'invalid_probe_request'});
      const base=env('WATCHLIST_DATA_ORIGIN')||env('SUPABASE_PUBLIC_URL')||env('SUPABASE_URL');
      if(!base||!env('SUPABASE_SERVICE_ROLE_KEY'))return response(503,{code:'rpc_config_missing'});
      if(new URL(base).protocol!=='https:')return response(503,{code:'rpc_https_required'});
      const r=await transport(base.replace(/\/$/,'')+'/rest/v1/rpc/watchlist_probe_v1',{method:'POST',redirect:'error',signal:AbortSignal.timeout(8000),headers:{'Content-Type':'application/json',apikey:env('SUPABASE_SERVICE_ROLE_KEY'),Authorization:'Bearer '+env('SUPABASE_SERVICE_ROLE_KEY')},body:JSON.stringify({p_action:body.action,p_id:body.id,p_owner:'demo'})});
      const data=await r.json();
      if(!r.ok)return response(r.status,{code:'rpc_rejected',sqlstate:typeof data.code==='string'?data.code:null});
      return response(200,{probe:true,transport:'https',result:data});
    } catch(e) {return response(e instanceof SyntaxError?400:502,{code:e instanceof SyntaxError?'invalid_json':'probe_upstream_failed'});}
  };
}

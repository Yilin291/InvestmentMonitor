const fs=require('fs');const crypto=require('crypto');
const {ApiClient}=require('/Users/alanli/.local/lib/node_modules/@aliyun-meoo/cli/dist/lib/apiClient.js');
(async()=>{
 const output=process.argv[2]||'artifacts/deno-probe-live.json';
 if(fs.existsSync(output))throw Error('output_exists');
 const config=JSON.parse(fs.readFileSync('.product-data/production-config.json'));
 const r=await ApiClient.fromCredentials().get('/open/v1/cli-compat/projects/ucdte4eh02uv/cloud/environment');
 const sb=r.data.instance.sbInfo;const base=sb.url.replace(/\/$/,'');
 if(!base.startsWith('https://'))throw Error('public_https_url_required');
 const url=base+'/functions/v1/watchlist-probe';
 const evidence={started_at:new Date().toISOString(),url,cases:[],gateway_jwt_enabled:true};
 const id=crypto.randomUUID(),failedId=crypto.randomUUID();
 async function call(name,body,{gateway=true,secret=config.TICK_SECRET,rpc=false}={}){
  const start=Date.now();const endpoint=rpc?base+'/rest/v1/rpc/watchlist_probe_v1':url;
  const headers={'Content-Type':'application/json'};
  if(gateway){headers.Authorization='Bearer '+sb.anonKey;headers.apikey=sb.anonKey;}
  if(secret)headers['X-Probe-Secret']=secret;
  try{const response=await fetch(endpoint,{method:'POST',headers,body:JSON.stringify(body),signal:AbortSignal.timeout(15000),redirect:'error'});const b=await response.json();
   const safe=rpc?{code:b.code}:Object.fromEntries(Object.entries(b).filter(([k])=>['probe','code','sqlstate','secrets_present','server_time','rpc_timeout_ms','platform_max_execution_ms','transport','result'].includes(k)));
   const result={name,status:response.status,elapsed_ms:Date.now()-start,body:safe};evidence.cases.push(result);return result;
  }catch(e){const result={name,error:e.name,elapsed_ms:Date.now()-start};evidence.cases.push(result);return result;}
 }
 await call('no_gateway',{action:'status'},{gateway:false,secret:null});
 await call('no_gateway_valid_business_secret',{action:'status'},{gateway:false});
 await call('wrong_business_secret',{action:'status'},{secret:'TEST_ONLY_WRONG'});
 const status=await call('secret_presence',{action:'status'});
 await call('owner_spoof',{action:'read',id,owner:'other'});
 await call('anonymous_direct_rpc',{p_action:'read',p_id:id,p_owner:'demo'},{rpc:true,secret:null});
 if(status.status===200){
  await call('commit',{action:'write',id});await call('independent_readback',{action:'read',id});
  await call('unique_conflict',{action:'write',id});await call('intentional_rollback',{action:'fail',id:failedId});
  await call('rollback_readback',{action:'read',id:failedId});await call('recovery_write',{action:'write',id:failedId});
  await call('recovery_readback',{action:'read',id:failedId});
  await call('cleanup_commit',{action:'cleanup',id});await call('cleanup_recovery',{action:'cleanup',id:failedId});
 }
 evidence.finished_at=new Date().toISOString();
 fs.writeFileSync(output,JSON.stringify(evidence,null,2));
 console.log(JSON.stringify(evidence));
})().catch(e=>{console.log(JSON.stringify({error:e.code||e.name}));process.exitCode=2});

import {modelConfig,modelBody,configuredEnv,settingsAction,modelTransport} from './llm.js';
import {Problem,exact,validate,preview} from './domain.js';
import {priceEvidence} from './providers.js';
import {closeEvidence,searchInstruments} from './close.js';
import {recommendInput} from './suggestions.js';
import {SYSTEM} from './prompt.js';
import {discoverInstrument} from './discovery.js';
const enc=new TextEncoder();
async function equal(a,b){const h=async x=>new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(x)));const [x,y]=await Promise.all([h(a),h(b)]);return x.reduce((n,v,i)=>n|(v^y[i]),0)===0;}
async function signature(secret,value){const k=await crypto.subtle.importKey('raw',enc.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);return [...new Uint8Array(await crypto.subtle.sign('HMAC',k,enc.encode(value)))].map(x=>x.toString(16).padStart(2,'0')).join('');}
export function handler(env,transport=fetch,resolve){return async req=>{
 const headers={'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin'};
 let modelState;
 const response=(data,status=200)=>new Response(JSON.stringify(modelState?.warning?{...data,model_warning:modelState.warning}:data),{status,headers});
 try{
  const origin=env('APP_ORIGIN');if(!origin?.startsWith('https://')||['SESSION_SECRET','TICK_SECRET','DEMO_PASSWORD'].some(k=>(env(k)||'').length<24))throw new Problem('runtime_config_missing','运行配置不完整。',503);
  const url=new URL(req.url);
  // Observed gateway strips /sb-api/functions/v1/<slug>; match the remaining route exactly.
  const path=url.pathname;
  if(path.includes('//')||path.includes('%'))throw new Problem('not_found','接口不存在。',404);
  const fixedPaths=['/api/health','/internal/monitor/tick','/api/v1/auth/login','/api/v1/auth/logout','/api/v1/auth/me','/api/v1/capabilities','/api/v1/instruments','/api/v1/rules/preview','/api/v1/rules/parse','/api/v1/tasks','/api/v1/notifications','/api/v1/settings/llm','/api/v1/settings/llm/test'];
  if(!fixedPaths.includes(path)&&!/^\/api\/v1\/tasks\/[a-f0-9]{32}(?:\/(activate|pause|resume|runs|versions|audit))?$/.test(path)&&!/^\/api\/v1\/notifications\/[a-f0-9]{32}\/read$/.test(path))throw new Problem('not_found','接口不存在。',404);
  if(!['GET','POST','PATCH','DELETE'].includes(req.method))throw new Problem('method_not_allowed','不支持的方法。',405);
  const deadline=Date.now()+30000;
  async function rpc(action,body={}){
   const base=env('WATCHLIST_DATA_ORIGIN');if(!base?.startsWith('https://'))throw new Problem('rpc_https_required','数据库HTTPS配置缺失。',503);
   const timeout=Math.min(8000,deadline-Date.now());if(timeout<=0)throw new Problem('request_budget_exhausted','执行预算已耗尽。',503);
   const r=await transport(base+'/rest/v1/rpc/'+(action==='login_gate'?'watchlist_login_gate_v1':action.startsWith('llm_')?'watchlist_llm_settings_v1':'watchlist_product_v1'),{method:'POST',redirect:'error',headers:{'Content-Type':'application/json',apikey:env('SUPABASE_SERVICE_ROLE_KEY'),Authorization:'Bearer '+env('SUPABASE_SERVICE_ROLE_KEY')},body:JSON.stringify(action==='login_gate'?{p_owner:'demo'}:{p_action:action,p_owner:'demo',p_body:body}),signal:AbortSignal.timeout(timeout)});
   const b=await r.json();if(!r.ok){const allowed=['past_time','task_limit','not_found','version_conflict','invalid_lifecycle','instrument_unverified','lease_rejected'];const code=allowed.includes(b.message)?b.message:'storage_error';throw new Problem(code,({past_time:'指定时间已过去，请重新编辑。',version_conflict:'任务版本已变更，请刷新。',task_limit:'每账户最多10个任务。',not_found:'记录不存在。'})[code]||'数据库操作未完成，请刷新后核对。',code==='not_found'?404:code==='storage_error'?503:409);}return b;
  }
  const tick=path==='/internal/monitor/tick';
  if(tick){if(req.method!=='POST')throw new Problem('method_not_allowed','仅支持POST。',405);if(!env('WATCHLIST_GATEWAY_ANON_KEY')||!await equal(req.headers.get('Authorization')||'','Bearer '+env('WATCHLIST_GATEWAY_ANON_KEY'))||!await equal(req.headers.get('X-Tick-Secret')||'',env('TICK_SECRET')))throw new Problem('unauthorized','调度身份校验失败。',401);}
  else if(req.method!=='GET'&&req.headers.get('Origin')!==origin)throw new Problem('origin_rejected','请求来源不匹配。',403);
  let body={};if(req.method!=='GET'){
   if(req.body){const reader=req.body.getReader();let size=0,chunks=[];while(true){const {value,done}=await reader.read();if(done)break;size+=value.length;if(size>32768){await reader.cancel();throw new Problem('payload_too_large','请求体超过限制。',413);}chunks.push(value);}if(size){if(!req.headers.get('Content-Type')?.startsWith('application/json'))throw new Problem('invalid_content_type','需要JSON请求体。',415);let all=new Uint8Array(size),off=0;for(const c of chunks){all.set(c,off);off+=c.length;}try{body=JSON.parse(new TextDecoder().decode(all));}catch{throw new Problem('invalid_json');}if(!body||Array.isArray(body)||typeof body!=='object')throw new Problem('invalid_json');}}
  }
  if(path==='/api/health'&&req.method==='GET')return response({...await rpc('health'),release:'deno-close-v20',ingress_path:path});
  if(tick){const key=req.headers.get('Idempotency-Key')||'';if(!/^[A-Za-z0-9:_-]{8,128}$/.test(key))throw new Problem('invalid_idempotency_key');const batch=body.batch??1;if(!Number.isInteger(batch)||batch<1||batch>10)throw new Problem('invalid_batch');const claim=await rpc('claim',{key});if(!claim.run_id)return response(claim);const task=await rpc('get',{id:claim.task_id});if(task.spec.rule.kind==='close_price_group'){claim.evaluation=await closeEvidence(task.spec,task.instrument,Date.now()/1000,env,transport,deadline,rpc);}else if(task.spec.rule.kind==='price_group'){claim.evaluation=await priceEvidence(task.spec,task.instrument,Date.now()/1000,env,transport,deadline);}return response(await rpc('finish',claim));}
  const suffix='; HttpOnly; Secure; SameSite=Strict; Path=/';
  if(path==='/api/v1/auth/login'&&req.method==='POST'){
   const gate=await rpc('login_gate');
   if(gate.allowed!==true){headers['Retry-After']=String(Math.max(1,gate.retry_after||60));throw new Problem('login_rate_limited','登录尝试过多，请稍后重试。',429);}
   if(typeof body.password!=='string'||!await equal(body.password,env('DEMO_PASSWORD')))throw new Problem('invalid_credentials','登录凭证错误。',401);
   const data=btoa(JSON.stringify({owner:'demo',expires:Date.now()/1000+43200})).replace(/\+/g,'-').replace(/\//g,'_');
   headers['Set-Cookie']='monitor_session='+data+'.'+await signature(env('SESSION_SECRET'),data)+'; Max-Age=43200'+suffix;return response({owner:'demo'});
  }
  const token=(req.headers.get('Cookie')||'').split(';').map(s=>s.trim()).find(s=>s.startsWith('monitor_session='))?.slice(16);
  let owner;try{const [data,sig]=token.split('.');if(!await equal(sig,await signature(env('SESSION_SECRET'),data)))throw Error();owner=JSON.parse(atob(data.replace(/-/g,'+').replace(/_/g,'/')));if(owner.owner!=='demo'||owner.expires<=Date.now()/1000)throw Error();}catch{throw new Problem('unauthorized','请登录演示账户。',401);}
  if(path==='/api/v1/auth/me'&&req.method==='GET')return response({owner:'demo'});
  if(path==='/api/v1/auth/logout'&&req.method==='POST'){headers['Set-Cookie']='monitor_session=; Max-Age=0'+suffix;return response({logged_out:true});}
  if(path==='/api/v1/settings/llm'||path==='/api/v1/settings/llm/test')return response(await settingsAction(req.method,body,env,rpc,transport,deadline,path.endsWith('/test'),resolve));
  if(path==='/api/v1/capabilities'&&req.method==='GET')return response({rule_kinds:['close_price_group','calendar_once'],fields:['close_price'],operators:['lt','gt'],max_conditions:4,max_tasks:10,interval_seconds_min:86400,frequency_verified:false,market_data:{available:true,scope:'沪深A股日收盘 / 不复权 / CNY',reason:'positive_calendar_only_missing_weekdays_unknown'},scheduler:{verified:false,capacity:'每tick最多1任务，日期优先；不承诺每任务5分钟'},natural_language:!!env('DEEPSEEK_API_KEY')||!!(await rpc('llm_get'))?.provider,disabled:['announcement','heat','trading','external_notifications'],deployment:'deno_postgresql_pending_full_acceptance'});
  if(path==='/api/v1/instruments'&&req.method==='GET'){const q=url.searchParams.get('q')||'';if(q.trim()){const items=await searchInstruments(q,env,transport,deadline);return response(await rpc('instrument_import',{items}));}return response(await rpc('instruments'));}
  async function instrumentsFor(spec){return rpc('instruments',{q:typeof spec?.instrument_id==='string'?spec.instrument_id.split('.').at(-1):''});}
  async function checked(spec,future=true){const instruments=await instrumentsFor(spec);const health=await rpc('health');return validate(spec,health.server_time,instruments.map(i=>i.id),future);}
  if(path==='/api/v1/rules/preview'&&req.method==='POST'){await checked(body);const h=await rpc('health');if(body.rule.kind==='close_price_group'){const instruments=await instrumentsFor(body);return response(await closeEvidence(body,instruments.find(i=>i.id===body.instrument_id),h.server_time,env,transport,deadline,rpc));}if(body.rule.kind==='price_group'){const instruments=await instrumentsFor(body);return response(await priceEvidence(body,instruments.find(i=>i.id===body.instrument_id),h.server_time,env,transport,deadline));}return response(preview(body,h.server_time));}
  const baseEnv=env,baseTransport=transport;
  if(path==='/api/v1/rules/parse'&&req.method==='POST'){
   const env=await configuredEnv(baseEnv,rpc);modelState=env('LLM_STATE');
   const transport=modelTransport(env,baseTransport,deadline,resolve);
   if(typeof body.text!=='string'||!body.text.trim()||body.text.length>4000)throw new Problem('invalid_input');
   if(!modelConfig(env).key)return response({drafts:[],questions:['自然语言服务未配置，请使用结构化表单。'],unsupported:[],status:'unavailable'});
   let outcome='rejected',detail={reason_code:'model_unavailable'};
   try{if(/【[^】]*】/.test(body.text)){outcome='validated';detail={drafts:[],questions:['请先补齐推荐输入中的【占位内容】，再生成草稿。'],unsupported:[],suggestions:[]};return response({...detail,status:'needs_clarification'});}if(/实时|盘中|最新成交价|最新价/.test(body.text)){outcome='validated';detail={drafts:[],questions:['当前仅支持最新已完成交易日的日收盘价，不支持实时或盘中价格。是否明确改为日收盘规则？'],unsupported:['intraday_price']};detail=await recommendInput(body.text,detail,env,transport,deadline);return response({...detail,status:'needs_clarification'});}const lookup=await discoverInstrument(body.text,env,transport,deadline,rpc);if(lookup.question){outcome='validated';detail={drafts:[],questions:[lookup.question],unsupported:[],instrument_lookup:lookup};detail=await recommendInput(body.text,detail,env,transport,deadline);return response({...detail,status:'needs_clarification'});}const instruments=[...new Map([...(await rpc('instruments')),...lookup.instruments].map(i=>[i.id,i])).values()];const h=await rpc('health');const r=await transport(modelConfig(env).url,{method:'POST',redirect:'error',headers:{'Content-Type':'application/json',Authorization:'Bearer '+modelConfig(env).key},body:JSON.stringify({...modelBody(env),stream:false,response_format:{type:'json_object'},messages:[{role:'system',content:SYSTEM},{role:'user',content:JSON.stringify({current_time:h.server_time,timezone:'Asia/Shanghai',instruments,selected_instrument_id:instruments.some(i=>i.id===body.instrument_id)?body.instrument_id:null,request:body.text})}]}),signal:AbortSignal.timeout(Math.min(8000,Math.max(1,deadline-Date.now()-8000)))});
    if(!r.ok)throw new Problem('model_unavailable','模型暂时不可用，请使用表单。',502);const raw=await r.json();const p=JSON.parse(raw.choices[0].message.content);exact(p,['drafts','questions','unsupported']);if(!Array.isArray(p.drafts)||p.drafts.length>10||['questions','unsupported'].some(k=>!Array.isArray(p[k])||p[k].length>20||p[k].some(s=>typeof s!=='string'||s.length>1000)))throw new Problem('invalid_model_output');for(const s of p.drafts){validate(s,h.server_time,instruments.map(i=>i.id));if(s.rule.kind==='close_price_group'&&lookup.instruments.length===1&&s.instrument_id!==lookup.instruments[0].id)throw new Problem('invalid_model_output','模型标的与已核验目标不一致，请重新生成草稿。');if(s.rule.kind==='price_group')throw new Problem('intraday_unsupported','当前只允许明确的日收盘草稿。');}if(p.questions.length||p.unsupported.length)p.drafts=[];if(!p.drafts.length&&!p.questions.length)p.questions=['请补充明确的股票、价格阈值或提醒时间。'];outcome='validated';detail=await recommendInput(body.text,{...p,instrument_lookup:lookup},env,transport,deadline);return response({...detail,status:p.drafts.length?'ready':'needs_clarification',model:modelConfig(env).model,provider:modelConfig(env).provider,prompt_version:'watchlist-close-v1'});
   }catch(e){throw e instanceof Problem?e:new Problem('invalid_model_output','模型输出未通过验证，请使用表单。',502);}finally{await rpc('parser_audit',{outcome,detail:{prompt_revision:'daily-close-explicit-v1',response:detail}});}
  }
  if(path==='/api/v1/tasks'){if(req.method==='GET')return response(await rpc('list'));if(req.method==='POST'){if(body.rule?.kind==='price_group')throw new Problem('intraday_unsupported','当前只支持日收盘新任务；请明确选择日收盘。');await checked(body);return response(await rpc('create',{spec:body}),201);}}
  const task=path.match(/^\/api\/v1\/tasks\/([a-f0-9]{32})(?:\/(activate|pause|resume|runs|versions|audit))?$/);
  if(task){const [,id,action]=task;if(req.method==='GET'&&(!action||['runs','versions','audit'].includes(action)))return response(await rpc(action||'get',{id,limit:url.searchParams.get('limit')||50,offset:url.searchParams.get('offset')||0}));if(req.method==='PATCH'&&!action){if(!Number.isInteger(body.expected_version))throw new Problem('version_conflict');await checked(body.spec);return response(await rpc('edit',{id,spec:body.spec,expected_version:body.expected_version}));}if(req.method==='DELETE'&&!action)return response(await rpc('delete',{id}));if(req.method==='POST'&&['activate','pause','resume'].includes(action)){if(action!=='pause'&&!Number.isInteger(body.expected_version))throw new Problem('version_conflict');return response(await rpc(action,{id,expected_version:body.expected_version}));}}
  if(path==='/api/v1/notifications'&&req.method==='GET')return response(await rpc('notifications'));
  const read=path.match(/^\/api\/v1\/notifications\/([a-f0-9]{32})\/read$/);if(read&&req.method==='POST')return response(await rpc('read',{id:read[1]}));
  throw new Problem('not_found','接口不存在。',404);
 }catch(e){return response({code:e instanceof Problem?e.code:'internal_error',message:e instanceof Problem?e.message:'请求未完成，请刷新核对。'},e instanceof Problem?e.status:500);}
};}

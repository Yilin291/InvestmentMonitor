import {Problem} from './domain.js';
const BUILTIN={provider:'deepseek',protocol:'openai',url:'https://api.deepseek.com/chat/completions',model:'deepseek-flash'};
const LEGACY={deepseek:BUILTIN.url,qwen:'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'};
export const PROVIDERS={openai:{name:'OpenAI 兼容',model:''},anthropic:{name:'Anthropic 兼容',model:''}};
export function endpoint(value,protocol){
 if(!Object.hasOwn(PROVIDERS,protocol)||typeof value!=='string'||value.length>512)throw new Problem('invalid_model_url','请选择协议并填写 HTTPS API URL。');
 let u;try{u=new URL(value.trim());}catch{throw new Problem('invalid_model_url','API URL 格式无效。');}
 if(u.protocol!=='https:'||u.username||u.password||u.search||u.hash||(u.port&&u.port!=='443')||! /^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}$/i.test(u.hostname)||/(?:^|\.)(?:localhost|local|internal|lan|test|invalid|example)$/.test(u.hostname))throw new Problem('invalid_model_url','请使用公网 HTTPS 域名（443端口），URL不能包含密钥、查询参数或账号信息。');
 let p=u.pathname.replace(/\/+$/,'');if(/%|\\|\/\//.test(p))throw new Problem('invalid_model_url','API URL 路径无效。');
 const suffix=protocol==='anthropic'?'/messages':'/chat/completions';
 if(protocol==='anthropic'&&p.endsWith('/chat/completions')||protocol==='openai'&&p.endsWith('/messages'))throw new Problem('invalid_model_url','URL 与所选协议不一致。');
 if(!p.endsWith(suffix))p+=(p?'':'/v1')+suffix;u.pathname=p;return u.href;
}
export function publicIP(ip){
 if(ip.includes(':'))return /^(2|3)[0-9a-f]{3}:/i.test(ip)&&!/^2001:(?:0*0:|0*2:|db8:)/i.test(ip)&&!/^2002:/i.test(ip);
 const a=ip.split('.').map(Number);if(a.length!==4||a.some(n=>!Number.isInteger(n)||n<0||n>255))return false;
 const [x,y,z]=a;return !(x===0||x===10||x===127||x>=224||x===169&&y===254||x===172&&y>=16&&y<=31||x===192&&y===168||x===100&&y>=64&&y<=127||x===198&&[18,19].includes(y)||x===192&&y===0||x===192&&y===88&&z===99||x===198&&y===51&&z===100||x===203&&y===0&&z===113);
}
async function dns(host){if(!globalThis.Deno?.resolveDns)throw Error('dns_unavailable');const results=await Promise.allSettled(['A','AAAA'].map(t=>Deno.resolveDns(host,t)));return results.flatMap(r=>r.status==='fulfilled'?r.value:[]);}
export async function checkEndpoint(url,resolve=dns){let timer;try{const addresses=await Promise.race([resolve(new URL(url).hostname),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('dns_timeout')),1500)})]);if(!addresses.length||addresses.some(ip=>!publicIP(ip)))throw Error('unsafe_address');}finally{clearTimeout(timer);}}
export function modelConfig(env){return env('LLM_STATE')?.current||{...BUILTIN,key:env('DEEPSEEK_API_KEY')};}
export function modelBody(env){const c=modelConfig(env);return {model:c.model,...(c.provider==='qwen'?{enable_thinking:false}:{})};}
const enc=new TextEncoder();
const context=(c,v)=>enc.encode(JSON.stringify(v===1?['watchlist-llm-v1','demo',c.provider,c.model]:['watchlist-llm-v2','demo',c.provider,c.model,c.base_url]));
async function key(secret){return crypto.subtle.importKey('raw',await crypto.subtle.digest('SHA-256',enc.encode('watchlist-llm-encryption-v1:'+secret)),{name:'AES-GCM'},false,['encrypt','decrypt']);}
export async function encryptKey(value,c,secret){const iv=crypto.getRandomValues(new Uint8Array(12)),v=c.base_url?2:1;const bytes=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:context(c,v)},await key(secret),enc.encode(value));return {v,iv:Array.from(iv),data:btoa(String.fromCharCode(...new Uint8Array(bytes)))};}
export async function decryptKey(c,secret){try{const v=c.encrypted_key.v;if(![1,2].includes(v))throw Error();return new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:new Uint8Array(c.encrypted_key.iv),additionalData:context(c,v)},await key(secret),Uint8Array.from(atob(c.encrypted_key.data),x=>x.charCodeAt(0))));}catch{throw new Problem('model_key_unreadable','自定义密钥无法解密，请重新保存配置。',503);}}
export function publicSettings(c){return {mode:c&&c.enabled!==false?'custom':'builtin',provider:c?(LEGACY[c.provider]?'openai':c.provider):'openai',base_url:c?.base_url||LEGACY[c?.provider]||'',model:c?.model||'',has_key:!!c,updated_at:c?.updated_at||null,providers:Object.entries(PROVIDERS).map(([id,p])=>({id,name:p.name,default_model:p.model})),warning:c?.last_error||null,builtin_model:BUILTIN.model,message:'不更改时使用内置 DeepSeek；自定义连接失败时会提示并继续使用内置模型。'};}
export async function configuredEnv(env,rpc){const builtin={...BUILTIN,key:env('DEEPSEEK_API_KEY')},state={current:builtin,builtin,custom:false,warning:null};const c=await rpc('llm_get');if(c?.provider){if(c.enabled===false)state.warning=c.last_error||'自定义配置尚未连通，正在使用内置模型。';else try{const protocol=LEGACY[c.provider]?'openai':c.provider;state.current={provider:c.provider,protocol,url:endpoint(c.base_url||LEGACY[c.provider],protocol),model:c.model,key:await decryptKey(c,env('SESSION_SECRET'))};state.custom=true;}catch{state.warning='自定义配置无法读取，已改用内置模型。请在模型设置中修正。';}}return n=>n==='LLM_STATE'?state:env(n);}
function reason(e){return e?.status===401||e?.status===403?'认证失败':e?.status===429?'限流或额度不足':e?.message==='unsafe_address'?'地址未通过公网校验':'连接超时、接口不兼容或响应无效';}
async function complete(c,payload,transport,deadline,custom,resolve){
 if(custom)await checkEndpoint(c.url,resolve);
 const budget=Math.min(custom?5000:8000,deadline-Date.now()-500);if(budget<250)throw Error('budget');
 const headers={'Content-Type':'application/json'};let body;
 if(c.protocol==='anthropic'){headers['x-api-key']=c.key;headers['anthropic-version']='2023-06-01';body={model:c.model,max_tokens:payload.max_tokens||4096,stream:false,system:payload.messages.filter(m=>m.role==='system').map(m=>m.content).join('\n'),messages:payload.messages.filter(m=>m.role!=='system')};}
 else{headers.Authorization='Bearer '+c.key;body={...payload,model:c.model};if(!custom)delete body.enable_thinking;if(new URL(c.url).hostname==='api.deepseek.com'&&payload.max_tokens===128)body.thinking={type:'disabled'};}
 const r=await transport(c.url,{method:'POST',redirect:'error',headers,body:JSON.stringify(body),signal:AbortSignal.timeout(budget)});if(!r.ok){const e=Error('http');e.status=r.status;throw e;}
 const reader=r.body.getReader();let size=0,chunks=[];while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>262144){await reader.cancel();throw Error('response_too_large');}chunks.push(value);}const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}const raw=JSON.parse(new TextDecoder().decode(bytes));const content=c.protocol==='anthropic'?raw.content?.filter(b=>b.type==='text').map(b=>b.text).join(''):raw.choices?.[0]?.message?.content;
 if(typeof content!=='string'||content.length>100000)throw Error('invalid_response');JSON.parse(content);
 return new Response(JSON.stringify({choices:[{message:{content}}]}),{headers:{'Content-Type':'application/json'}});
}
export function modelTransport(env,transport,deadline,resolve=dns){return async(url,opts)=>{const state=env('LLM_STATE');if(!state||url!==state.current.url)return transport(url,opts);const payload=JSON.parse(opts.body);try{return await complete(state.current,payload,transport,deadline,state.custom,resolve);}catch(e){if(!state.custom)throw e;state.warning='自定义模型'+reason(e)+'，本次已改用内置 DeepSeek。可在模型设置中修正后重试。';state.current=state.builtin;state.custom=false;return complete(state.builtin,payload,transport,deadline,false,resolve);}};}
export async function settingsAction(method,body,env,rpc,transport,deadline,testOnly=false,resolve=dns){
 if(method==='GET'&&!testOnly)return publicSettings(await rpc('llm_get'));
 if(method==='DELETE'&&!testOnly){await rpc('llm_delete');return publicSettings(null);}
 if(method!=='POST')throw new Problem('method_not_allowed','不支持的方法。',405);
 if(Object.keys(body).some(k=>!['provider','base_url','model','api_key'].includes(k))||!Object.hasOwn(PROVIDERS,body.provider)||typeof body.model!=='string'||! /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$/.test(body.model))throw new Problem('invalid_model_settings','请选择接口协议，并填写有效模型名称。');
 const c={provider:body.provider,model:body.model,base_url:endpoint(body.base_url,body.provider)};let apiKey=body.api_key;
 if(apiKey===undefined||apiKey===''){const old=await rpc('llm_get');const oldUrl=old?.base_url||LEGACY[old?.provider];if(!oldUrl||endpoint(oldUrl,LEGACY[old?.provider]?'openai':old.provider)!==c.base_url||(LEGACY[old.provider]?'openai':old.provider)!==c.provider)throw new Problem('model_key_required','首次配置或更换 URL/协议时必须重新输入 API Key。');apiKey=await decryptKey(old,env('SESSION_SECRET'));}
 if(typeof apiKey!=='string'||apiKey.length<8||apiKey.length>4096||/\s/.test(apiKey))throw new Problem('invalid_model_key','API Key 格式无效，请检查空格和换行。');
 let warning=null;try{const r=await complete({...c,protocol:c.provider,url:c.base_url,key:apiKey},{max_tokens:128,stream:false,response_format:{type:'json_object'},messages:[{role:'system',content:'Return only JSON: {"ok":true}'},{role:'user',content:'Connection test. Return JSON.'}]},transport,deadline,true,resolve);const b=await r.json();if(JSON.parse(b.choices[0].message.content).ok!==true)throw Error();}catch(e){warning='自定义模型'+reason(e)+'；'+(testOnly?'配置未启用。保存失败配置后将继续使用内置模型。':'已保留待修正配置，继续使用内置 DeepSeek。');}
 if(testOnly)return {ok:!warning,provider:c.provider,model:c.model,saved:false,warning};
 c.enabled=!warning;c.last_error=warning;c.encrypted_key=await encryptKey(apiKey,c,env('SESSION_SECRET'));const saved=await rpc('llm_save',c);return {...publicSettings(saved),tested:!warning};
}

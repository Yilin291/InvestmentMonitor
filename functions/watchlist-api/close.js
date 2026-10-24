import {compare,Problem} from './domain.js';
import {exchangeCalendar,scheduledClosed} from './calendar.js';
import {losslessJSON} from './providers.js';
export const MAPPING='fuyao-daily-close-v1';
export const POLICY='cn-sh-sz-2026-positive-calendar-v3';
const BASE='https://fuyao.aicubes.cn',DAY=86400000;
export function supportedInstrument(market,code){return typeof code==='string'&&(market==='SH'?/^6\d{5}$/:market==='SZ'?/^[03]\d{5}$/:/a^/).test(code);}
export function shDate(ms){return new Date(ms+8*3600000).toISOString().slice(0,10);}
export function midnight(date){const n=Date.parse(date+'T00:00:00+08:00');if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Number.isFinite(n)||shDate(n)!==date)throw Error('invalid_trade_date');return n;}
export function nextClose(now){const ms=now*1000,d=midnight(shDate(ms));return (ms<d+15*3600000?d+15*3600000:d+DAY+15*3600000)/1000;}
// Positive provider dates confirm expected open days; only official scheduled closures are skipped.
// Unknown year, conflicting dates and absent expected trading days fail closed.
export function expectedClose(items,now,market='SH'){
 const calendar=exchangeCalendar(market);
 const ms=now*1000,today=shDate(ms),dates=[];let prev=0;
 if(!today.startsWith(String(calendar.year)))throw Error('calendar_year_uncovered');
 if(!Array.isArray(items)||!items.length)throw Error('calendar_coverage_unknown');
 for(const x of items){const raw=String(x.date);if(!/^\d{8}$/.test(raw))throw Error('calendar_invalid');const d=raw.slice(0,4)+'-'+raw.slice(4,6)+'-'+raw.slice(6),at=midnight(d);if(String(at)!==String(x.date_ms)||at<=prev||d>today)throw Error('calendar_invalid');if(d.startsWith(String(calendar.year))&&scheduledClosed(d,market))throw Error('calendar_source_conflict');prev=at;dates.push(d);}
 let candidate=midnight(today);if(ms<candidate+15*3600000)candidate-=DAY;
 while(scheduledClosed(shDate(candidate),market))candidate-=DAY;
 const date=shDate(candidate);if(!dates.includes(date))throw Error('calendar_coverage_unknown');
 return {trade_date:date,policy_version:POLICY,source_ref:BASE+'/api/a-share/calendar/trading-days',exchange:market,exchange_rule:market==='SZ'?'https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf':'https://www.sse.com.cn/lawandrules/sselawsrules2025/fund/trading/c/c_20260424_10817739.shtml',calendar_version:calendar.version,calendar_sources:calendar.sources,coverage:market+' 2026 scheduled closures plus positive provider expected date; emergency halt remains unknown',checked_at:now};
}
export function validateBars(data,instrument,now,expected){
 const symbol=instrument.code+'.'+instrument.market;
 if(!supportedInstrument(instrument.market,instrument.code)||instrument.currency!=='CNY')throw Error('instrument_scope_unsupported');
 if(data.thscode!==symbol)throw Error('provider_identity_mismatch');
 if(data.interval!=='1d'||data.adjust!=='none')throw Error('provider_basis_mismatch');
 if(data.ticker&&data.ticker!==instrument.code)throw Error('provider_identity_mismatch');
 if(!Array.isArray(data.item)||data.item.length>40)throw Error('provider_invalid_response');
 let prev=0,bars=[];const today=midnight(shDate(now*1000));
 for(const row of data.item){if(row.thscode&&row.thscode!==symbol||row.ticker&&row.ticker!==instrument.code)throw Error('provider_identity_mismatch');const ms=Number(row.date_ms);if(!Number.isSafeInteger(ms)||ms<=prev||midnight(shDate(ms))!==ms||ms>today||ms<today-35*DAY)throw Error('bars_dates_invalid');prev=ms;compare(row.close_price,'1');if(compare(row.close_price,'1000000000000')>0)throw Error('provider_invalid_value');if(ms+15*3600000<=now*1000)bars.push({trade_date:shDate(ms),value:row.close_price,date_ms:String(row.date_ms)});}
 const bar=bars.at(-1);if(!bar||bar.trade_date!==expected.trade_date)throw Error('expected_bar_missing_or_suspended');return bar;
}
export function combine(results,combinator){return combinator==='all'?(results.includes(false)?false:results.includes(null)?null:true):(results.includes(true)?true:results.includes(null)?null:false);}
export function evaluateClose(spec,observation,market,now){
 const valid=observation.quality==='valid';const evidence=spec.rule.conditions.map(condition=>({condition,observation,result:valid?(condition.operator==='gt'?compare(observation.value,condition.value)>0:compare(observation.value,condition.value)<0):null,quality:observation.quality,reason_code:observation.reason_code}));
 const result=combine(evidence.map(e=>e.result),spec.rule.combinator);return {result,decision:result===null?'insufficient_data':result?'matched':'no_match',evaluated_at:now,evidence,market,warnings:valid?[]:[observation.reason_code],valid_until:nextClose(now),next_check:valid?nextClose(now)+900:now+900,mapping_version:MAPPING};
}
async function get(path,env,transport,deadline){
 if(!env('FUYAO_API_KEY'))throw Error('provider_credentials_missing');const budget=Math.min(8000,deadline-Date.now()-8000);if(budget<=0)throw Error('provider_budget_exhausted');
 const r=await transport(BASE+path,{headers:{Accept:'application/json','X-api-key':env('FUYAO_API_KEY')},redirect:'error',signal:AbortSignal.timeout(budget)});
 if(!r.ok)throw Error(r.status===429?'provider_rate_limited':'provider_http_error');const raw=await r.text();if(raw.length>1000000)throw Error('provider_response_too_large');const d=losslessJSON(raw);if(String(d.code)==='4001')throw Error('provider_rate_limited');if(String(d.code)!=='0'||!Array.isArray(d.data?.item))throw Error('provider_invalid_response');return {...d.data,request_id:d.request_id??null};
}
export async function searchInstruments(q,env,transport,deadline){
 if(typeof q!=='string'||!q.trim()||q.length>100)throw new Problem('invalid_search','请填写股票名称或代码。');
 const path='/api/meta/tickers/search?'+new URLSearchParams({q,asset_type:'a-share',limit:'20'});
 const d=await get(path,env,transport,deadline),seen=new Set();return d.item.filter(i=>i.asset_type==='a-share'&&supportedInstrument(i.exchange,i.ticker)&&i.currency==='CNY'&&i.thscode===i.ticker+'.'+i.exchange&&typeof i.name==='string'&&i.name.length>0&&i.name.length<=100&&!i.end_date).map(i=>{if(seen.has(i.thscode))throw Error('provider_duplicate_instrument');seen.add(i.thscode);return {id:'CN.'+i.exchange+'.'+i.ticker,code:i.ticker,market:i.exchange,name:i.name,asset_class:'stock',currency:'CNY',provenance:JSON.stringify({provider:'fuyao',source:BASE+path,request_id:d.request_id,verified_at:new Date().toISOString(),asset_type:i.asset_type})};});
}
export async function closeEvidence(spec,instrument,now,env,transport,deadline,rpc){
 let observation={instrument_id:spec.instrument_id,field:'close_price',value:null,unit:'CNY',source_time:null,trade_date:null,adjust:'none',mapping_version:MAPPING,fetched_at:new Date(now*1000).toISOString(),provider:'fuyao',source_ref:BASE+'/api/a-share/prices/historical',quality:'missing',reason_code:null};let market={status:'unknown',policy_version:POLICY};
 try{
  const key=instrument.id+':'+shDate(now*1000),cached=await rpc('close_cache_get',{key});let bundle=cached.value;
  if(!bundle){if(cached.busy)throw Error('provider_fetch_in_progress');try{const calendar=await get('/api/a-share/calendar/trading-days',env,transport,deadline);const expected=expectedClose(calendar.item,now,instrument.market);const end=midnight(shDate(now*1000));const path='/api/a-share/prices/historical?'+new URLSearchParams({thscode:instrument.code+'.'+instrument.market,interval:'1d',adjust:'none',start:String(end-35*DAY),end:String(end)});const bars=await get(path,env,transport,deadline);bundle={calendar,bars,path,fetched_at:new Date(now*1000).toISOString()};validateBars(bars,instrument,now,expected);await rpc('close_cache_put',{key,token:cached.token,value:bundle,expires:nextClose(now)});}catch(e){await rpc('close_cache_put',{key,token:cached.token,value:{error:e.message},expires:now+900});throw e;}}
  if(bundle.error)throw Error(bundle.error);
  const expected=expectedClose(bundle.calendar.item,now,instrument.market),bar=validateBars(bundle.bars,instrument,now,expected);
  observation={...observation,...bar,fetched_at:bundle.fetched_at,source_ref:BASE+bundle.path,quality:'valid',reason_code:null,request_id:bundle.bars.request_id,identity_basis:'response thscode/interval/adjust strictly matched',provider_echo:{thscode:bundle.bars.thscode,interval:bundle.bars.interval,adjust:bundle.bars.adjust}};market={...expected,status:'completed_close',expected_trade_date:expected.trade_date};
 }catch(e){const allowed=['calendar_coverage_unknown','calendar_year_uncovered','calendar_source_conflict','calendar_invalid','instrument_scope_unsupported','provider_identity_mismatch','provider_basis_mismatch','provider_invalid_response','bars_dates_invalid','provider_invalid_value','expected_bar_missing_or_suspended','provider_credentials_missing','provider_budget_exhausted','provider_rate_limited','provider_http_error','provider_response_too_large','provider_fetch_in_progress'];observation.reason_code=allowed.includes(e.message)?e.message:'provider_timeout_or_invalid_response';}
 return evaluateClose(spec,observation,market,now);
}

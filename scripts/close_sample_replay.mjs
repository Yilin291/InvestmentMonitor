// Revalidate verification-session captured LIVE samples with product code. This is replay, not a new live request.
import fs from 'node:fs';import assert from 'node:assert/strict';
import {expectedClose,validateBars,evaluateClose} from '../functions/watchlist-api/close.js';
const input=process.argv[2],output=process.argv[3];if(!input||!output||fs.existsSync(output))throw Error('new_input_output_required');
const samples=JSON.parse(fs.readFileSync(input)),now=Date.parse(samples.checked_at)/1000;
const expected=expectedClose(samples.checks.find(c=>c.label==='calendar').rows,now),results=[];
for(const c of samples.checks.filter(c=>c.label.startsWith('daily:'))){const symbol=c.label.slice(6),meta=samples.checks.find(x=>x.label==='meta:'+symbol).rows[0];const instrument={id:'CN.SH.'+meta.ticker,code:meta.ticker,market:meta.exchange,currency:meta.currency};const bar=validateBars({item:c.rows,thscode:c.symbol_echo,adjust:c.adjust_echo,interval:c.interval_echo},instrument,now,expected);const spec={rule:{combinator:'all',conditions:[{id:'p1',operator:'gt',value:bar.value}]}};assert.equal(evaluateClose(spec,{...bar,quality:'valid'},expected,now).result,false);results.push({symbol,name:meta.name,...bar,equality_false:true,source_request_id:c.request_id});}
assert.equal(results.length,3);fs.writeFileSync(output,JSON.stringify({mode:'captured_live_sample_replay_not_new_online_run',input,expected,results,passed:true},null,2));console.log(JSON.stringify({passed:true,symbols:results.map(r=>r.symbol)}));

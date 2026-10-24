const assert=require('node:assert/strict');
module.exports=function assess(c,b){
 if(c.id){assert.equal(b.status,'ready');assert.equal(b.drafts.length,1);assert.equal(b.questions.length,0);assert.equal(b.unsupported.length,0);const d=b.drafts[0];assert.equal(d.instrument_id,c.id);assert.equal(d.rule.kind,'close_price_group');assert.equal(d.rule.combinator,c.combinator);assert.deepEqual(d.rule.conditions.map(x=>[x.operator,x.value]).sort(),c.conditions);assert.ok(d.rule.conditions.every(x=>x.field==='close_price'&&x.currency==='CNY'));assert.deepEqual(d.schedule,{mode:'daily_close',timezone:'Asia/Shanghai',interval_seconds:86400});assert.equal(d.notification_policy.cooldown_seconds,c.cooldown);assert.equal(d.notification_policy.mode,'on_episode');
 }else{assert.equal(b.drafts.length,0);assert.equal(b.status,'needs_clarification');assert.match([...b.questions,...b.unsupported].join(' '),c.relevant);if(c.name==='unsupported')assert.ok(!b.questions.some(q=>/股票代码|股票名称|提醒时间/.test(q)));}
};

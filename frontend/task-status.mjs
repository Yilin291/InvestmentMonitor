// Presentation-only adapter. Inputs and epoch units are documented in FRONTEND_SESSION_HANDOFF.md.
export function taskStatus(task){
 const rt=task.runtime||{},s=task.scheduler_observation||{},now=s.server_time;
 const e=task.last_evaluation?.version===task.version?task.last_evaluation:null;
 const active=task.lifecycle==='enabled',calendar=task.spec.rule.kind==='calendar_once';
 const decision=e?.decision||null;
 let title='等待首次检查',reason='当前规则版本尚无执行结果；启用后由云调度检查。',tone='info';
 if(e){
  const states={notify:['已生成站内提醒','本次满足条件，提醒已保存到站内通知。','success'],no_match:['条件未满足','本次检查未达到你设置的条件，因此没有发送提醒。','info'],already_notified:['本轮已提醒','条件持续满足属于同一事件段，不会重复提醒；有效不满足后再次满足才开启新事件段。','info'],cooldown_suppressed:['冷却中，暂未提醒','条件满足，但仍处于滚动冷却期。到期后还需使用有效数据重新检查，不保证到点即提醒。','warning'],insufficient_data:['数据不足，无法判断','本次数据无法支持有效判断，保留之前的事件状态，不据此重置提醒。','warning'],missed:['已错过补发窗口','超过一次性提醒允许的24小时迟到补发窗口，本次没有发送提醒。','warning'],skipped_not_due:['尚未到提醒时间','当前尚未到指定时间，因此未发送提醒。','info']};
  [title,reason,tone]=states[decision]||['检查结果待核对','请查看执行依据确认本次处理结果。','warning'];
 }
 if(task.lifecycle==='draft'){title='草稿，尚未启用';reason='预览不会发送提醒，请核对规则并明确启用。';tone='info';}
 if(task.lifecycle==='paused'){title='已暂停检查';reason='暂停期间不再检查或发送新提醒，下方依据仅为最近一次历史检查。';tone='info';}
 if(task.lifecycle==='deleted'){title='已删除，只读历史';reason='不会恢复执行；历史提醒和依据仍可查看。';tone='info';}
 if(active&&calendar&&rt.state?.calendar_done&&rt.next_run==null&&decision==='notify'){title='一次性提醒已完成';reason='已生成站内提醒，无下一次检查。';}
 const basis=(e?.evidence||[]).map(x=>({condition_id:x.condition.id,field:x.condition.field,operator:x.condition.operator,threshold:x.condition.value,currency:x.condition.currency,value:x.observation?.value??null,trade_date:x.observation?.trade_date??null,result:x.result??null,quality:x.quality,reason_code:x.reason_code||x.observation?.reason_code||null,provider:x.observation?.provider||null}));
 const cooldownRemaining=decision==='cooldown_suppressed'&&Number.isFinite(now)?Math.max(0,Math.ceil((rt.state?.cooldown_until||0)-now)):null;
 let scheduler={tone:'warning',title:'尚无云调度完成记录',reason:'不能仅凭页面打开或普通请求认定自动调度正常。'};
 if(Number.isFinite(now)&&s.last_cloud_finished!=null){
  const age=now-s.last_cloud_finished;
  scheduler=age>=0&&age<=(s.warning_after_seconds||180)?{tone:'success',title:'近期云调度请求已完成',reason:'按已认证tick的约定请求键识别；近期成功不代表每个历史时隙都成功。'}:{tone:'warning',title:'云调度可能延迟',reason:'超过3分钟未观察到云调度完成记录，请刷新并核对执行情况。'};
  if(s.last_cloud_request>s.last_cloud_finished&&now-s.last_cloud_request>60)scheduler={tone:'warning',title:'最近云调度请求尚未完成',reason:'请求已到达，但超过1分钟未见完成记录；可能影响到期检查。'};
 }
 if(!Number.isFinite(now))scheduler={tone:'warning',title:'调度状态待刷新',reason:'缺少服务端读取时间，无法判断请求是否近期完成。'};
 return {title,reason,tone,basis,decision,result:e?.result??null,rule_version:task.version,evaluated_at:e?.evaluated_at??null,trigger_source:e?.trigger_request_id?.startsWith('cf-cron:ucdte4eh02uv:')?'cloud_request':e?.trigger_request_id?'other_request':'unconfirmed',cooldown_remaining_seconds:cooldownRemaining,cooldown_until:decision==='cooldown_suppressed'?rt.state?.cooldown_until:null,next_check:active?rt.next_run:null,next_label:!active?'未安排（任务未启用）':rt.next_run==null?(calendar&&rt.state?.calendar_done?'无（一次性提醒已结束）':'暂无安排'):rt.overdue?'已到期，检查延迟':'计划检查时间（可能排队）',overdue:active&&!!rt.overdue,scheduler:{...scheduler,last_completed:s.last_cloud_finished??null,observed_at:now??null},calendar:e?.calendar||null};
}

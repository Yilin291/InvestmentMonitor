import React from 'react';
import {Alert,Tag} from 'antd';
import {taskStatus} from '../task-status.mjs';
export function TaskStatus({task,date,label}){
 const v=taskStatus(task);
 return <section aria-label="检查与提醒说明" className="task-status">
  <Alert type={v.tone} showIcon message={v.title} description={v.reason}/>
  {v.cooldown_remaining_seconds!==null&&<p>冷却{v.cooldown_remaining_seconds>0?`剩余约 ${Math.ceil(v.cooldown_remaining_seconds/60)} 分钟`:'已到期，等待重新检查'} · 截至 {date(v.scheduler.observed_at)}；到期 {date(v.cooldown_until)}</p>}
  {v.basis.map((b,i)=><div className="task-basis" key={b.condition_id||i}>
   <strong>{b.trade_date?`${b.trade_date} 收盘价`:'本次价格'}：{b.value??'未取得有效值'} {b.value!==null?'CNY':''}</strong>
   <p>你的条件：{b.field==='close_price'?'日收盘价':'旧盘中价'}{b.operator==='gt'?'高于':'低于'} {b.threshold} 元 · <Tag>{b.result===null?'无法判断':b.result?'满足':'未满足'}</Tag></p>
   {b.reason_code&&<p>{label(b.reason_code)}</p>}<small>来源：{b.provider||'未取得'}{b.field==='close_price'?' · 不复权 · 日期不是精确成交时间':''}</small>
  </div>)}
  {v.calendar&&<p>原定提醒：{date(v.calendar.scheduled_at)}；实际检查：{date(v.calendar.actual_at)}{v.calendar.late_seconds>0?`（迟到 ${Math.ceil(v.calendar.late_seconds/60)} 分钟）`:''}</p>}
  <p>当前规则 v{v.rule_version} 最近检查：{date(v.evaluated_at)}<br/>执行来源：{v.trigger_source==='cloud_request'?'云调度请求':v.trigger_source==='other_request'?'其他已认证请求（非自动来源证明）':'尚未确认'}<br/>{v.next_label}：{date(v.next_check)}</p>
  {v.overdue&&<Alert type="warning" showIcon message="检查已延迟" description="尚未完成本次到期检查；旧结果不能代表当前新判断。日期任务优先，每个调度时隙最多处理一个任务。"/>}
  <p><Tag color={v.scheduler.tone==='success'?'green':'orange'}>{v.scheduler.title}</Tag><br/>最近云调度完成：{date(v.scheduler.last_completed)}<br/><small>{v.scheduler.reason} 状态读取于 {date(v.scheduler.observed_at)}，刷新可获取最新状态。</small></p>
 </section>;
}

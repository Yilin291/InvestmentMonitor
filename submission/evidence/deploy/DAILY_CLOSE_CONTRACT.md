# 日收盘契约 v1（用户已明确批准范围调整，2026-10-24）

现有项目ucdte4eh02uv，沿用watchlist。新增close_price_group，不改写price_group或任何旧RuleVersion。旧盘中请求只能unknown；自然语言明确实时/盘中/最新价会要求确认改义，绝不自动替换。

```json
{"name":"日收盘提醒","instrument_id":"CN.SH.600519","rule":{"kind":"close_price_group","combinator":"all","conditions":[{"id":"p1","field":"close_price","operator":"lt","value":"1336.0","currency":"CNY"}]},"schedule":{"mode":"daily_close","timezone":"Asia/Shanghai","interval_seconds":86400},"notification_policy":{"mode":"on_episode","cooldown_seconds":86400}}
```

沪深A股、CNY、metadata核验后可选：SH六位6开头，SZ六位0/3开头（含深市主板/创业板）；不包括B股、北交所、港美股。官方meta ticker search按用户名称/代码返回，服务端交叉核对thscode/ticker/exchange/asset_type/currency，数据库保存provenance；不会把未知股票映射为茅台。

## 数据与日期

日线固定interval=1d、adjust=none、单一已核验thscode、最近35自然日，end为当前上海日期零点（不查询未来）。价格用原始JSON数值词法转为字符串后BigInt比较，从未经过Number；date_ms允许安全整数，仅表示上海日线日期，不是成交时间。Observation保存trade_date/date_ms/mapping_version/adjust/request_id与抓取时间，source_time=null。来源https://fuyao.aicubes.cn/llms-full.txt。

mapping_version=fuyao-daily-close-v1。完整日期/排序/唯一性/正价/窗口及证券/周期/复权回显核对；验证session18:42交接确认data.thscode/interval/adjust存在，v9起三者必须精确匹配，缺失即unknown。不伪称响应逐bar有证券标识。原始日线sample核验见验证session的fuyao_close_three证据。

预期完成日策略cn-sh-sz-2026-positive-calendar-v3：按标的market分别选择沪深2026年度休市依据，跳过已核验休市日与周末；候选日期仍必须正向出现在实取交易日历中。日历与官方休市冲突、缺少预期交易日或超出2026年度时unknown，不把缺失工作日当休市，不推断临时停市。星期六读取已确认星期五完成日不按盘中时效判旧。

官方公告来源：https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml 、https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml 。日期表及版本见functions/watchlist-api/calendar.js。

当前交易日15:00前的bar不消费；若预期日期bar未到，expected_bar_missing_or_suspended（不能仅由缺bar断言停牌）。日期覆盖错误、接口错误、429、日期回退、同日更正分别有原因。年度表仅覆盖2026，不能代表未来年度或所有临时停市。

## 执行、缓存与状态

产品策略：正常每日下一收盘边界后15分钟检查；未知/429等15分钟退避，不立即重试。不是供应商发布SLA。数据库共享缓存以标的/抓取上海日期为键，内含交易日期；有效期不跨下一完成日边界，复用时重新校验预期日；30秒抓取租约避免并行重复上游请求。错误也缓存15分钟。不同规则复用同标的日线，非每分钟取数。

Deno纯比较gt/lt，等于false；AND任false则false，否则有unknown则unknown；OR任true则true，否则有unknown则unknown。受限SQL重新核对版本/生命周期/租约/数据边界，复核十进制比较，读取最新Runtime并事务完成Run/Evidence/Notification。

首次true提示用户可直接提醒；持续true只一次；有效false重新武装，随后true新事件段。unknown保留此前状态，不撤销已通知标记。冷却内抑制，结束后仍须有效的最新完成日判断才补发；无效数据不能仅靠时钟补提醒。相同bar和新日期连续true均不开新事件段；same-day更正标记conflict，原证据不覆盖。编辑新版本重置事件段判断但保留冷却，暂停/编辑/删除使旧租约失效。

每个tick最多1任务，日期优先；每分钟唤醒不等于每个任务每分钟取数，10个到期任务至少约10个slot。独立调度器实际运行前不承诺检查延迟或无人值守成功。双层凭证与幂等键契约保持原样。

## 测试证据与边界

- close-offline-v1.txt：30项Node测试（20回归+10新项）通过。
- close-migration-dryrun.json：目标数据库迁移回滚演练/纯状态机断言通过。
- close-isolated-state-test-r2.json：目标数据库独立TEST schema内验证首true、同bar、新日连续true、false、unknown、冷却补发、回退、更正冲突、重复键、暂停在途和删除历史，最终ROLLBACK；不是实际多次市场穿越。r1测试脚本变量歧义失败保留。
- close-live-stage-v8.json：线上3标的真实预览和2项明确启用任务、删除历史读回；未调用tick。
- 新范围审批曾被自动审核拒绝，用户明确批准后才应用007和发布v8；未绕过审批。


深市独立来源、三标的真实样本及缓存隔离见SH_SZ_SCOPE.md。缓存键CN.SH.code:日期与CN.SZ.code:日期不共享；不因扩展范围改变旧规则或通知事件段。

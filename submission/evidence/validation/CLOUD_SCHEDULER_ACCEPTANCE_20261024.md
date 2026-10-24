# 独立云调度验收：2026-10-24 19:44

## 判定

- **已通过：** 正式tick独立云调度；至少三个连续自动业务时隙；真实日期到期补执行；日收盘true/false；同键重放去重；跨产品v10→v11部署保持记录、v12后恢复。
- **观察已完成，包含失败：** 19:13:23.333至19:43:23.333（北京时间）连续观察30分钟，共31个计划时隙。30个时隙业务tick HTTP200并有数据库ticks；19:42健康探测5秒超时，未发送tick，19:43自动恢复。严格“无遗漏业务分钟/零失败”判定未通过，脚本实际退出1，不改称全通过。
- **未执行：** 本机断电试验、新建未来提醒准时性测试、完整灾备重建。可选新增生产验证任务被自动审批拒绝，未创建，不绕过。已有日期任务原定17:45，19:13:28补执行，迟到5308秒，不能称准时提醒。
- **待用户操作：** 本次调度接入无剩余账户操作；未来若撤销OAuth/免费额度或轮换双层tick凭证，须按维护说明更新。

## 配置与真实运行

Cloudflare现有免费账户，Worker `tonghuashun-tick`，Cron `* * * * *`（UTC）。当前active版本 `067222d2-a4a3-4605-b6d9-4d8756f86f86`，cf-cron-v4；只保存 `WATCHLIST_GATEWAY_ANON_KEY`、`TICK_SECRET`。正式POST `https://ucdte4eh02uv.meoo.info/sb-api/functions/v1/watchlist-api/internal/monitor/tick`，Bearer+X-Tick-Secret，body batch=1。请求键前缀`cf-cron:ucdte4eh02uv:`，首尾分钟29880673～29880703；29880702为明确健康超时槽，没有数据库tick，不能伪造补写。

三项日收盘使用产品已取得的真实日线缓存（18:44取数），非每分钟重复行情请求。10月23日不复权CNY：茅台1335.0 < 1336.0=true；平安51.76 < 50.76=false；招商41.77 < 42.77=true。每条Evidence保存标的、日期、request_id、fetched_at和比较条件；source_time为null，不伪造逐笔时刻。最终数据库仍为4条Run、4条Evidence、3条Notification：

|任务ID|Run ID|Notification ID|
|---|---|---|
| 48bf9e848e5a4b29ba47241a4636ab3e | d30d9a01269d47c5bba771b8854df16f | 928d0f1735a940f89b73f620bbe50d2e |
| 67c22ac8c03742a9939a6f4fa98c278b | 522e50acd7474688b7a19f7575d160bc | 6f18ade4d2d34ec9a5040295f453bf3d |
| 546597e801114893915b4fa98c978d0a | 3c652b8c53ec470aae42a8b3ebd7fb3b | 无 |
| 57a30a61beea43ee85e48e748c12f314 | 0af54d95a16f486185db142c651617bf | af97828457b34349a322eff00f921dd9 |

19:21同一云ScheduledEvent额外重放日期旧键...673，显式标记`TEST_intentional_same_key_replay`，HTTP200/duplicate=true；主请求仍使用新键...681。读回数量和旧ID不变。一次性重放变量已经移除，普通Cron继续运行。此验证不是市场价格穿越，也不是人工tick。

产品19:20:40.797部署v11；自动健康日志19:20为v10、19:21为v11。19:43读到v12并恢复200；19:42超时的根因未进一步确认，不自动归因于产品部署或网络。

## 证据与实际命令

- 原始云日志：`validation/evidence/cloudflare_tail_20261024T1100Z.jsonl`（Wrangler连续JSON流，非每行一个JSON）。
- 唯一窗口快照：`validation/evidence/cloud_events_final_20261024T1144Z.json`。
- 数据库读回：`validation/evidence/cloud_business_final_20261024T1144Z.json`。
- 严格判定：`validation/evidence/cloud_assessment_strict_20261024T1144Z.json`，passed=false，仅no_missing_minute/no_recorded_primary_failure两项不通过。
- 云部署读回：`validation/evidence/cloudflare_deployments_20261024T1124Z.json`；Secret仅名称：`cloudflare_secret_names_20261024T1124Z.json`。
- `wrangler login --device --browser=false`成功；`wrangler deploy`成功；`node upload_tick_secrets.mjs --upload`退出0，两值仅stdin；`wrangler tail --format json`只读观察。环境禁用Wrangler磁盘日志。
- `node --test validation/cloudflare/worker.test.mjs`：10项明确TEST通过，仅针对调度边界，非真实供应商证据。
- `python3 validation/summarize_cloud_log.py <原始日志> <唯一快照>`退出0。
- `node validation/read_cloud_scheduler.cjs <唯一数据库快照>`退出0。
- `python3 validation/assess_cloud_acceptance.py <云快照> <数据库快照> <唯一判定>`本窗口独立执行退出1；保留失败，不通过后续shell命令掩盖状态。

## 故障历史、维护与边界

OAuth回调超时、邮箱10034、子域10063、本机ENOSPC及前三个probe redirect:error运行时错误均保留。邮箱由用户验证，Workers首页初始化子域，仅清理本任务npm缓存；redirect改manual且拒绝3xx。19:12云自动probe200后才启用正式tick。

调度不依赖本机登录或网页；本机tail只观察，停止tail不停止云Cron。没有以手动请求/本机循环代替。未做物理关机实验。健康超时槽在云日志有明确失败记录；当前策略下一分钟重试检查，不补造上一slot。每tick最多领取1任务，不承诺高负载时每任务5分钟检查。

配置、双层认证安全同步、超时/有界重试/停用及改动文件见`validation/cloudflare/README.md`。三标的字段、单位、交易日历和新鲜度见`validation/CLOSE_DATA_HANDOFF_20261024.md`与`FUYAO_DATA_BOUNDARIES.md`。服务保持active，不因完成取证停掉。

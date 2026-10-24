# Cloudflare 独立产品调度

仅此 Worker 在 Cloudflare；产品/数据库留在秒悟。使用用户授权现有免费额度，未购买资源。Cron 每分钟 UTC，由平台 ScheduledEvent 唤醒；不依赖本机登录、网页或电脑在线。`wrangler tail` 只是本机观察者，退出不停止 Cron。

## 当前部署与操作

配置见 `wrangler.jsonc`。`probe` 仅请求健康接口，`active` 才调用正式 tick；其他 mode 直接结束。没有公开 HTTP 触发入口。两项 Secret 通过 `node upload_tick_secrets.mjs --upload` 从现有受限产品配置读取，stdin 上传；不持有行情密钥或数据库角色。

```sh
cd validation/cloudflare
npm ci
WRANGLER_WRITE_LOGS=false WRANGLER_SEND_METRICS=false ./node_modules/.bin/wrangler deploy
WRANGLER_WRITE_LOGS=false WRANGLER_SEND_METRICS=false ./node_modules/.bin/wrangler tail --format json
```

不得将 tail/部署命令成功当自动执行业务成功。须看到 scheduled event、health HTTP 200，再确认 active 自动 tick 及数据库结果。

## 键与边界

`cf-cron:ucdte4eh02uv:<floor(scheduledTime/60000)>`。不同分钟不同键，同 slot 重试复用键。健康探测最多 5 秒；tick 第一次最多 35 秒、第二次最多 12 秒、两次之间等待 500ms，总 tick 预算 50 秒。仅网络错误、502/503/504 重试一次；401/403/429 不重试。过期超过 5 分钟 slot 不执行。每次 batch=1，当前吞吐须以产品实际领取为准。

## 停用与恢复

把 `wrangler.jsonc` 的 `SCHEDULER_MODE` 改为 `disabled` 后部署，阻止后续业务调用；如要移除触发，另把 `triggers.crons` 改为 `[]` 后部署。平台配置传播期间不能承诺立即停用；需立刻阻断时由产品 session 撤销/轮换 tick 凭证。恢复 active 前安全同步最新双层凭证。不要删除产品历史。

## 证据与复验

日志保存到 `validation/evidence/` 的唯一文件；Worker 日志仅允许安全字段，禁止记录 headers/env/完整响应。控制台 Workers Logs 也启用。每个执行检查 cron、scheduled_at、request_key、HTTP、run_id；通过 `node validation/read_cloud_scheduler.cjs validation/evidence/<唯一名称>.json` 只读关联 ticks / Run / Evidence / Notification。SQL 排除租约 token。

最低验收：连续三个不同自动 slot，至少一个真实到期任务、后续无重复提醒；另需日收盘 true/false 和至少 30 分钟跨产品重部署观察。离线 10 项 TEST 仅证明调度器边界，不能代替此验收。

## 2026-10-24 实际执行记录

- active 持续版本：`067222d2-a4a3-4605-b6d9-4d8756f86f86`，代码 revision cf-cron-v4。仅 SCHEDULER_MODE=active；一次性重放配置已移除。
- 同键重放在19:21的云ScheduledEvent执行，测试键为已完成的日期提醒键，日志显式 `TEST_intentional_same_key_replay`，主tick仍使用新分钟键。返回duplicate=true，数据库业务数量和ID保持不变。重放参数缺省时此分支完全不运行。
- 产品19:20:40.797重部署v11；云19:20读到v10、19:21读到v11，tick继续200。
- 最初三个probe失败是Workers不支持redirect:error，修复为manual并拒绝3xx。原失败保留。
- Wrangler连续JSON输出不是每行一个JSON；用上级summarize_cloud_log.py提取可解析快照。
- Cloudflare官方说明Cron配置传播可能需要15分钟；本次首次云事件在19:09，不能用部署成功时刻作为自动执行起点。来源：https://developers.cloudflare.com/workers/configuration/cron-triggers/ 。
- 新增独立未来提醒的可选验证被自动审批拒绝，未执行；采用已有日期任务和价格任务完成本轮验收。历史日期任务迟到88分钟必须保留，不能宣称准时性已验收。

## 本轮改动文件

- cloudflare/worker.mjs、worker.test.mjs、wrangler.jsonc、package.json、package-lock.json、.gitignore：独立Cron实现、最小依赖及针对性验证。
- cloudflare/upload_tick_secrets.mjs：只通过stdin上传两项Secret。
- read_cloud_scheduler.cjs：正式数据库只读关联。
- summarize_cloud_log.py：真实云日志快照提取。
- assess_cloud_acceptance.py：真实证据断言（时隙/持久化/语义/去重/版本/30分钟）。
- fuyao_close_probe.py、CLOSE_DATA_HANDOFF_20261024.md、FUYAO_DATA_BOUNDARIES.md：三标的真实数据与时间口径。
- SCHEDULER_HANDOFF.md、根VALIDATION_REPORT.md及evidence/新文件：实际状态和证据；deploy/HANDOFF.md只追加验证侧交接。

未修改产品backend/frontend/functions/根入口；产品session自行部署v11。

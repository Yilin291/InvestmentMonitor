# 投资监控 MVP 基础设施验证报告

## 19:44 最终调度观察：闭环通过，窗口含一次真实超时

**已通过：** 独立Cloudflare正式tick、四任务真实自动执行、日收盘true/false、同键重放去重、跨v11部署持久化。最终Run4/Evidence4/Notification3，后续未重复提醒。

**失败并自动恢复：** 30分钟/31个计划slot中，19:42 health5秒超时未发tick，19:43恢复200（v12）；其余30个slot有HTTP200和数据库tick。严格零失败判定退出1，不能称全窗口无故障。

**未执行：** 新建未来提醒准时性、物理关机和完整灾备重建；本次无剩余账户操作。服务继续active。实际配置、日志、请求键、Run/Evidence/Notification、复验步骤和限制以[独立云调度验收](validation/CLOUD_SCHEDULER_ACCEPTANCE_20261024.md)为准；本节覆盖下方历史状态。

## 19:22 增量：跨产品重部署与云端同键重放通过

产品于19:20:40.797完成v11部署（产品记录deploy/HANDOFF.md）。云端19:20 health v10、19:21 health v11且tick200，服务持续可达。19:21指定时隙执行一次明确TEST标记的已完成日期键重放，返回duplicate=true；同一分钟主tick仍用新键。数据库9个slot，Run4、Evidence4、Notification3，旧日期Run/通知ID不变。证据 `validation/evidence/cloud_events_20261024T1121Z.json` 与 `validation/evidence/cloud_after_replay_redeploy_20261024T1122Z.json`。一次性重放配置已移除并重新部署active；完整30分钟观察仍进行中，目标19:44复核。

## 19:18 最新验收：正式云调度四个连续时隙已通过

本节覆盖后文历史阻塞描述。Cloudflare 现有免费账户 Worker `tonghuashun-tick` 已启用每分钟 Cron，active 版本 `911ea779-e2dd-43bd-9a9c-d20420f36614`；正式 POST `/internal/monitor/tick` 使用最新两层 Secret。无手动 tick、本机循环或网页触发。

**已通过：** 19:13、19:14、19:15、19:16（北京时间）四个连续不同 slot，HTTP 200，分别处理日期提醒、茅台 true、平安 false、招商 true。数据库独立读回四条 Run、四条 Evidence、三条 Notification，关联如下。

| 请求键 | Run ID | 判断 | Evidence 数 | Notification ID |
|---|---|---|---|---|
| `cf-cron:ucdte4eh02uv:29880673` | `d30d9a01269d47c5bba771b8854df16f` | notify | 1 | 928d0f1735a940f89b73f620bbe50d2e |
| `cf-cron:ucdte4eh02uv:29880674` | `522e50acd7474688b7a19f7575d160bc` | notify | 1 | 6f18ade4d2d34ec9a5040295f453bf3d |
| `cf-cron:ucdte4eh02uv:29880675` | `3c652b8c53ec470aae42a8b3ebd7fb3b` | no_match | 1 | 无（不满足） |
| `cf-cron:ucdte4eh02uv:29880676` | `0af54d95a16f486185db142c651617bf` | notify | 1 | af97828457b34349a322eff00f921dd9 |

证据：`validation/evidence/cloud_scheduler_events_20261024T1117Z.json`（云 ScheduledEvent/版本/请求键/HTTP），`validation/evidence/cloud_scheduler_three_20261024T1116Z.json`（数据库只读关联），`validation/evidence/close_baseline_before_cloud_20261024T1109Z.json`（执行前四任务均无 Run/Notification）。持续原始日志 `validation/evidence/cloudflare_tail_20261024T1100Z.jsonl` 实际是 Wrangler 连续 JSON 对象流，用 `validation/summarize_cloud_log.py` 提取唯一快照。

**真实数据口径：** 茅台 1335.0 < 1336.0 为 true，平安 51.76 < 50.76 为 false，招商 41.77 < 42.77 为 true；均使用 2026-10-23 的真实不复权 CNY 收盘。运行复用产品18:44已取数的真实日线缓存，记录供应商 request_id/fetched_at/trade_date；不把调度时间冒充新行情抓取时间。日期任务原定17:45，实际19:13:28，迟到5308秒，原因是调度到此才接通，不能称准时交付。

**失败并已修复：** 首次 OAuth 回调超时；API10034邮箱待验证；API10063子域待初始化；本机ENOSPC清理本任务临时npm缓存；云probe前三次因 Workers 不支持 redirect:error 失败，v3改为manual且拒绝重定向，针对性9项TEST通过。19:12云自动health200已证明执行位置可达，产品release=deno-close-v10。历史失败不覆盖。

**未执行／观察中：** 至少30分钟连续运行、跨产品重部署恢复、线上同键重试验收、后续时隙通知数量稳定仍需后续证据。已在deploy/HANDOFF.md追加产品重部署交接；验证session不发布产品。持续服务保持运行，不为验收后停掉。配置/超时/重试/停用见 `validation/cloudflare/README.md`。新真实缺q错误及三标的字段/年度日历见 `validation/CLOSE_DATA_HANDOFF_20261024.md`。

复验：`node validation/read_cloud_scheduler.cjs validation/evidence/<唯一名称>.json` 只读读回；`python3 validation/summarize_cloud_log.py validation/evidence/cloudflare_tail_20261024T1100Z.jsonl validation/evidence/<唯一快照>.json`。不要手动发tick充作自动证据。

## 19:03 最新状态：Cloudflare Cron 已部署，等待首次自动探测

邮箱验证与 Workers 子域初始化已完成；`wrangler deploy` 退出 0，计划 `* * * * *`，Worker `tonghuashun-tick`，probe 版本 `59302295-837d-4769-95bf-b5f716d6e6c6`。双层 tick Secret 已经通过 stdin 注入成功，未记录值；仍保持 probe，未发送正式 tick。部署证据 `validation/evidence/cloudflare_probe_deploy_20261024.json`，实时观察日志 `validation/evidence/cloudflare_tail_20261024T1100Z.jsonl`。首次自动事件与三次业务闭环尚待验证；不能将配置成功写成执行成功。此前账户阻塞已解除。

## 18:57 最新阻塞：Cloudflare 邮箱验证

设备 OAuth 已成功；实际 `wrangler deploy` 退出 1，Cloudflare API 错误 **10034**：账户须验证邮箱后才能使用 Workers。用户已获提示；没有创建成功的 Cron、没有发送正式 tick。真实失败证据：`validation/evidence/cloudflare_deploy_20261024T105633Z.json`。邮箱验证完成后重试同一 probe 部署，不新增付费资源。此状态覆盖下方尚待 OAuth 的旧描述。

## 最新增量：2026-10-24 18:55（北京时间）

以下更新优先于后文 18:01 历史状态；历史失败证据保留。

- **已通过：真实三标的日线与元数据。** `python3 validation/fuyao_close_probe.py` 退出 0，8 次串行真实请求通过；证据 `validation/evidence/fuyao_close_three_20261024T183738060490+0800.json`。600519.SH / 601318.SH / 600036.SH 的 2026-10-23 不复权收盘分别为 1335.0 / 51.76 / 41.77 CNY。请求 ID、字段、阈值候选和缺 q 的真实业务错误见 `validation/CLOSE_DATA_HANDOFF_20261024.md`。这些不是产品线上 true/false 验收。
- **已通过：本机授权网络探活。** 正式产品 `/api/health` 返回 HTTP 200、`storage=postgresql_rpc`、`release=deno-product-v7`。此前 DNS 失败来自受限执行环境，不能再写成产品当前不可达；尚未证明 Cloudflare 执行位置可达。
- **已通过：调度实现离线检查。** `node --test validation/cloudflare/worker.test.mjs` 为明确 TEST，9 项通过；Wrangler dry-run 打包成功。只有 Cron 入口，每分钟计划时隙稳定键，双层鉴权，最多两次同键尝试，日志脱敏。
- **待用户操作／未执行：云调度。** 用户已授权现有 Cloudflare 免费额度；首次 OAuth 回调超时，whoami 仍未认证。已重新启动官方设备授权并等待批准。Worker 尚未发布、正式 tick 尚未自动执行，不能声明三时隙或 Run/Evidence/Notification 验收完成。无需重新提供已有行情或产品密钥。
- **数据边界调整：** 按最新方案采用显式新版本日收盘规则；旧 last_price 不能静默换义。周六 10/24 的最新完成日 10/23 有真实日线、实际交易日列表和交易所周末规则支持。年度休市公告已查，日线日期不能写为精确成交时间，供应商数值 SLA/QPS 仍未知。详见新的日收盘交接。


更新时间：2026-10-24 18:01（Asia/Shanghai）  
范围：扶摇、iFinD MCP、DeepSeek、秒悟部署、独立调度、持久化、去重与恢复。  
验证实现：`validation/`。真实服务调用与本地故障记录分开标识；本地 SQLite/launchd 结果不代表云端验收。

## 当前验收状态（2026-10-24 18:01，北京时间）

| 状态 | 项目 | 当前结论与证据 |
| --- | --- | --- |
| **已通过** | V-01～V-05整改、Lead独立39项离线检查、DeepSeek严格四场景 | 最新已接受验收见 `docs/lead/TWO_SESSIONS_ACCEPTANCE.md`；本轮未重复调用 DeepSeek 或重跑已关闭问题。 |
| **已通过（有限口径）** | 扶摇真实复验 | 新严格检查器对快照、交易日历和10天日线三次真实只读调用均 HTTP 200 / code 0；当前证据 [`fuyao_live_strict_20261024T032658Z.json`](validation/evidence/fuyao_live_strict_20261024T032658Z.json)。官方单位映射已补齐；快照缺每标的成交时间，盘中新鲜度仍未通过。上交所规则/公告替代日历路径已查明并写入 [`FUYAO_DATA_BOUNDARIES.md`](validation/FUYAO_DATA_BOUNDARIES.md)，但未来日历尚未拉取校验或接入产品。 |
| **已通过（权限清单）** | iFinD 当前工具权限 | 本轮当前 stock/news 两个 `tools/list` 均 HTTP 200；stock 10 项含 `get_stock_performance`，news 3 项含 `search_news`、`search_notice`。[`ifind_listtools_live_20261024T032510Z.json`](validation/evidence/ifind_listtools_live_20261024T032510Z.json)。`search_news` 不是公告增量流，公告监控仍禁用。 |
| **产品侧已报告通过，验证侧当前无法独立探活** | 正式产品发布与业务链路 | `IMPLEMENTATION_REPORT.md` 17:44 报告 static v2 / watchlist-api v5 READY、产品侧 health 200、PostgreSQL RPC与业务读回。验证侧本次 health preflight 在 DNS 阶段失败（curl exit 6 / HTTP 000），这不等同服务故障。详情见产品报告与 `deploy/HANDOFF.md`。 |
| **受阻，未执行** | 正式产品独立调度三时隙 | 秒悟当前官方 FAQ 写明不支持自动定时；CLI 无 cron 命令。唯一 `--sync-cron` 属 DUAL 发布同步，本次安全预检被 `CLOUD_SYNC_INCOMPATIBLE` 拒绝；证据 [`scheduler_platform_probe_20261024T095727Z.json`](validation/evidence/scheduler_platform_probe_20261024T095727Z.json)。因此没有发送 tick、没有新的 Run/Evidence/Notification。Lead 17:48 对目标任务的读回应保留为历史观察：enabled/overdue、`last_checked=null`、`runs=[]`、无通知；这证明当时未执行，不证明永久调度故障。 |

**当前小包**：运行时能力证据和实际可交产品操作见 [`deploy/RUNTIME_CONFIG_HANDOFF.md`](deploy/RUNTIME_CONFIG_HANDOFF.md)；扶摇字段、日线替代路径、日历/限流口径见 [`validation/FUYAO_DATA_BOUNDARIES.md`](validation/FUYAO_DATA_BOUNDARIES.md)。

本次 17:57 补充：已核查秒悟 FAQ、CLI 帮助、安装 CLI 技能说明和项目只读状态。`meoo deploy --sync-cron --skip-push` 返回 `CLOUD_SYNC_INCOMPATIBLE`，没有触发发布。绕过 `--skip-push` 会进入源码同步/发布路径；当前工作区无 Git HEAD 或 remote，且会影响现有生产入口，因此未尝试。产品 URL 健康探测在本验证环境 DNS 解析失败（curl exit 6 / HTTP 000）。双层凭证契约保持为 `Authorization: Bearer <WATCHLIST_GATEWAY_ANON_KEY>` + `X-Tick-Secret: <TICK_SECRET>`；每时隙新 `Idempotency-Key`、同次重试复用，JSON `{"batch":1}`。没有发 tick，不将本地 runner 或单次 worker当作服务端调度。平台需提供独立可读回的任务创建/停用入口，或 Lead 指定已有授权调度资源后才能继续三时隙验收。详见 [`validation/SCHEDULER_HANDOFF.md`](validation/SCHEDULER_HANDOFF.md) 与脱敏证据 [`scheduler_platform_probe_20261024T095727Z.json`](validation/evidence/scheduler_platform_probe_20261024T095727Z.json)。盘中价格保持 unknown，公告保持禁用。

### 扶摇价格时间、交易日历与新鲜度结论（本次更新）

- **官方保证**：`last_price` 为最新成交价、单位为 A 股原始货币 CNY；`price_change_ratio_pct` 用百分数值表示（1.74 即 +1.74%）；`data.timestamp` 是快照中最新上游有效数据/数据就绪时间，不是逐证券成交时间。接口没有提供逐股 `last_trade_time` 或 `trade_date`。官方日历是上海时区 `[今日-1年, 今日]` 固定窗口，无参数，按日期升序；不提供未来交易日、完整性标志、下一开市或交易时段。[扶摇价格字段与限流文档](https://fuyao.aicubes.cn/llms-full.txt#股票行情数据)、[扶摇交易日历文档](https://fuyao.aicubes.cn/llms-full.txt#交易日历)、[高频端外接入边界](https://fuyao.aicubes.cn/docs/api-reference/high-frequency/)。
- **本次观察**：脱敏真实证据显示 snapshot 返回 `600519.SH` / `ticker=600519` / `last_price=1335` / 涨跌幅 `1.25219`；最新日线日期为 `2026-10-23`、收盘 `1335.0`。休市周六取得的响应时间接近请求时间，但价格与前一交易日收盘相同。因此只证明响应/上游快照新，不证明这只证券有新成交。日历共 242 项，首尾为 `2025-10-24` 至 `2026-10-23`，目标日 `2026-10-24` 未包含；没有证据确认该区间之外是否休市。
- **官方交易规则与适用范围**：上交所现行规则给出周一至周五（法定假日和交易所公告休市除外）及 9:15–9:25、9:30–11:30、13:00–14:57、14:57–15:00 的竞价时段。它说明常规交易安排，不能补出年度假日表、临时停市、个股停牌/无成交或数据更新时间。[上交所《交易规则（2026年修订）》](https://www.sse.com.cn/lawandrules/sselawsrules2025/fund/trading/c/c_20260424_10817739.shtml)。
- **尚未知/产品结论**：扶摇没有公开可用的数值新鲜度 SLA 或固定 QPS；限流时 HTTP 429 / `code=4001` 要降低频率，不能快速重试。高频接口文档标明未开放端外接入。故维持产品价格判断 `unknown/not_evaluated`，不能基于快照 timestamp 设置陈旧度阈值。若 Lead 接受日收盘规则，可另行确定日线 `adjust=none` 的范围；若坚持盘中，应先获得逐证券成交时间与服务 SLA，或批准下一交易时段对 iFinD 高频接口做字段/单位/时间实测。每 5 分钟轮询目前只能算待批准的保守候选，不是供应商承诺，也不应作为已验收频率。

数据库解除阻塞的路径已由 Lead 在 `docs/lead/DECISION_DENO_RPC.md` 批准。产品报告称正式 Deno/RPC 业务链路已部署并通过目标环境恢复证据；验证 session 当前只推进三时隙调度验证及扶摇数据口径，不将产品侧证据冒称为本 session 独立复验。

## 最新补充：V-02 已修复并完成真实复验（2026-10-24 02:01，北京时间）

- 修复歧义场景判定：必须报告所有要求的缺失字段；追问需覆盖 A 股代码及目标阈值/规则值。无关问题、只问代码、未覆盖阈值的响应均失败；明确逐项询问全部字段可通过。
- 修复账户余额拒绝判定：`unsupported` 字段去空白并匹配 `account_balance` 及明确账户余额/资金同义字段；无关字段和空白字段失败。也接受明确写出“不支持账户余额/资金条件”的拒绝说明。
- 离线回归：`node validation/deepseek_assessment_offline_check.mjs`，13 项通过，包含三个验收负例与有效正例；脱敏结果：[`deepseek_assessment_offline_v02_final.json`](validation/evidence/deepseek_assessment_offline_v02_final.json)。
- 真实在线复验：加载本机 `.env.local` 后运行 `EVIDENCE_OUT=validation/evidence/deepseek_live_v02_strict_final.json node validation/deepseek_check.mjs`；调用 `deepseek-flash` 四个场景，退出码 0、overall_passed=true。两个正常场景逐字段匹配 symbol/metric/operator/value/unit；歧义场景追问股票代码和阈值及其余缺失规则字段；账户余额场景明确拒绝。completion ID、token usage 和脱敏摘要见 [`deepseek_live_v02_strict_final.json`](validation/evidence/deepseek_live_v02_strict_final.json)；代码与证据摘要清单见 [`deepseek_v02_final_manifest.json`](validation/evidence/deepseek_v02_final_manifest.json)，凭证值未进入证据。
- 之前真实尝试的失败结果保留为独立文件，没有覆盖；它们显示严格协议提示迭代时模型遗漏 status、证券代码或部分追问字段。最终通过结论只引用上述最终运行文件。

## 后续操作更新（2026-10-24）

- 按用户确认，在秒悟网页控制台软删除唯一旧应用 `pocket-adum`。控制台确认删除成功、回收站保留 30 天；云服务用量从 `1/1` 降到 `0/1`。
- 通过 `meoo --json projects create 'TongHuaShun 投资监控 MVP'` 创建并绑定当前目录项目，URL ID `ucdte4eh02uv`。在其上启用了 Free 套餐的云服务，PostgreSQL 已就绪、存储 `0/1 GB`；`meoo db tables` 可连接，但当前无表、未迁移。命令证据见 [`meoo_project_setup.json`](validation/evidence/meoo_project_setup.json)。
- `meoo info` 实测镜像运行时支持 Python，要求监听 `0.0.0.0:${PORT:-9000}` 并提供 `scripts/setup.sh`、`scripts/start.sh`。后续产品 session 已报告 static v2 / watchlist-api v5 上线；早期两次镜像发布失败属于历史状态，不能用于描述当前部署状态。
- 用户已在本机隐藏提示输入扶摇和 DeepSeek key。根 `.env.local` 权限 `0600` 且 Git 忽略；没有读取或输出 key 值。扶摇两端点有历史真实成功调用证据；DeepSeek 新严格真实复验见本报告最新 V-02 补充，旧检查器的历史 `passed=true` 不作为语义验收结论。
- 用户随后从 home 目录运行带反斜线转义的脚本路径，导致文件解析到 `/Users/alanli/...` 而不是本项目；已在项目根目录按正确路径重跑。沙箱内首次网络请求受限；经批准的网络复验再次成功，脱敏证据分别写入 `fuyao_live_rerun.json`、`deepseek_live_rerun.json`。错误和成功结果均保留，密钥没有输出。
- **历史记录（早期时点）**：当时尚未上传/部署，随后两次镜像发布也失败。以上均已被后续产品 session 的上线报告覆盖；当前产品 session 报告已有可访问 URL / static v2 / watchlist-api v5。验证 session 本次因 DNS exit 6 未能独立探活；这不是产品仍未部署的证据。

## 2026-10-24 验证实现专项审查整改（V-01 至 V-05）

本节回应验证 session 专项审查。修复后的针对性检查为离线 fixture / 临时数据库；不调用供应商、不改云资源。最新脱敏运行结果见 [`validation_review_offline_2026-10-23T17-33-19-181Z.json`](validation/evidence/validation_review_offline_2026-10-23T17-33-19-181Z.json)，时间文件名为 UTC。

| 项 | 结论 | 修正与证据 |
|---|---|---|
| V-01 合法规则二次校验 | **已修正；离线通过** | `validateRule` 仅接收外部五字段；新增 `validateValidatedRule` 只接受这五字段加正确版本，仍拒绝任意未知字段。`runCheck` 将外部输入错误归为 `RULE_INVALID`，然后把受校验内部规则传入执行器。直接调用真实 `runCheck` 函数、临时 SQLite 和 mock upstream，证明 checked rule 到达 `matched`；另验证默认价格判断 gate 和 provider 失败记录。见 `validation/runcheck_offline_check.mjs`、`validation/self_check.mjs`。 |
| V-02 DeepSeek 语义判定 | **已修正；13 项离线通过；真实四场景通过** | 正常场景逐字段比对；歧义场景检查 missing、股票代码与阈值相关追问；账户余额拒绝匹配明确字段、同义字段或明确拒绝说明。三个历史负例均被拒绝。最终 `deepseek-flash` 在线四场景退出码 0；证据见 `validation/evidence/deepseek_live_v02_strict_final.json` 与 `deepseek_assessment_offline_v02_final.json`。 |
| V-03 Provider 退出码 | **离线通过；DeepSeek 真实成功路径退出码 0 已验证** | 扶摇成功 `0`、业务/网络/结构失败 `1`、缺密钥 `not_run` 为 `2`；快照验证正确标的、必要数值字段和可解析时间，日历验证结构、日期格式、排序唯一性和时间。DeepSeek 全部严格场景通过才为 `0`，失败为 `1`，缺密钥 `not_run` 为 `2`。本轮真实 DeepSeek 四场景退出码 0；HTTP 401、扶摇业务码 2003、错误标的、缺凭证等失败退出码仍由离线 fixture 验证。 |
| V-04 日历覆盖未知 | **已修正；离线通过** | 删除 `today_is_trading_day=false`。列表未含检查日时为 `today_trading_status=unknown`，保存覆盖范围并标明完整性未验证，不推算下一开市。无单位/时效映射依据时，验证服务默认 `not_evaluated_mapping_unverified`。细节见 [`validation/FUYAO_DATA_BOUNDARIES.md`](validation/FUYAO_DATA_BOUNDARIES.md) 和 `runcheck_offline_check.mjs`。 |
| V-05 iFinD 工具清单 | **已修正；离线与当前真实清单通过** | 本次只读 `tools/list` 实际得到 stock 10 项（含 `get_stock_performance`）、news 3 项（含 `search_news`、`search_notice`）；工具数量动态读取。唯一证据 [`ifind_listtools_live_20261024T032510Z.json`](validation/evidence/ifind_listtools_live_20261024T032510Z.json)。公告保持禁用。 |

复验命令：`node validation/review_fixes_offline_check.mjs`。此前六组离线检查记录见前文。本次 V-02 针对性离线检查 13 项全部通过，并已另行执行真实 DeepSeek 四场景在线复验。离线检查只证明注入响应处理，不替代在线证据。

## 已通过

### iFinD MCP（有限能力）

- **当前权限清单**：本次真实 `listTools('stock')` HTTP 200、10 项、含 `get_stock_performance`；`listTools('news')` HTTP 200、3 项、含 `search_news` 和 `search_notice`。工具数量/名称来自当前返回，不是常量。真实行情历史响应提供 `600519.SH` 最近交易日 `2026-10-23` 收盘价 `1335`，成交额 `76.7722亿`、成交量 `576.8593万`；响应没有独立交易所时刻，不能声明盘中行情。当前工具清单证据：[`ifind_listtools_live_20261024T032510Z.json`](validation/evidence/ifind_listtools_live_20261024T032510Z.json)。
- **资讯**：`news.search_news` 返回贵州茅台相关资讯《贵州茅台董事长陈华上任一年：i茅台破局，飞天随行就市两连涨》，发布日期 `2026-10-19`，来源域名 `news.sohu.com`，查询标的关联为“贵州茅台”。返回 URL 可作为该条资讯的去重候选，不证明公告具备稳定 ID 或完整增量覆盖。
- **错误响应**：无效的 `search_notice` 参数请求收到 HTTP 400、JSON-RPC `-32602`。这是参数/协议错误证据，不是权限拒绝证据。
- **限制**：完成的是鉴权、行情和新闻搜索样例；不是公告增量接口验收。公告监控须保持禁用。证据：[`ifind_live.json`](validation/evidence/ifind_live.json)。

### 扶摇真实行情与交易日历

- 本轮新严格检查器真实调用快照、交易日历及10天日线，均 HTTP 200 / code 0。快照返回 `600519.SH`→`ticker=600519`、`last_price=1335`、`price_change_ratio_pct=1.25219`；日线 8 根，最新 `date_ms` 对应 `2026-10-23`，收盘 `1335.0`。脱敏证据 [`fuyao_live_strict_20261024T032658Z.json`](validation/evidence/fuyao_live_strict_20261024T032658Z.json)。
- 扶摇当前官方契约说明 A股价格为 CNY，涨跌幅为百分点数值（1.74 即 1.74%），成交量为股、成交额为原始货币。快照 `data.timestamp` 是快照级最新上游有效时间，不是每只标的的成交时间；实际周六 snapshot 值与上个交易日 close 一致，不能证明盘中报价新鲜。详见 [`validation/FUYAO_DATA_BOUNDARIES.md`](validation/FUYAO_DATA_BOUNDARIES.md) 与 [官方全文字段/限流契约](https://fuyao.aicubes.cn/llms-full.txt)。
- 日历官方固定返回上海时区近一年窗口 `[today-1 year,today]`，按日期升序；实际 242 项、末日 2026-10-23。没有 completeness 标志、未来日期或下一开市/时段字段，因此缺失日期依旧为 `unknown`，不推算下一个交易日。轮询数值限额未公布，429/code4001 应退避。

### DeepSeek `deepseek-flash` 在线解析

新严格复验 `deepseek-flash` 的四个在线场景均通过：两个正常规则各字段匹配预期；“它涨了就提醒我”被要求补充证券代码、指标、比较方式、阈值和单位；账户余额条件被明确拒绝。completion ID 和脱敏摘要保留于 [`deepseek_live_v02_strict_final.json`](validation/evidence/deepseek_live_v02_strict_final.json)。旧检查器的历史 `passed=true` 仍不作为语义验收证据，历史摘要保留于 [`deepseek_live.json`](validation/evidence/deepseek_live.json) 和 [`deepseek_live_rerun.json`](validation/evidence/deepseek_live_rerun.json)。

### 规则契约（不含 DeepSeek 在线调用）

`node validation/self_check.mjs` 通过：合法规则结构、未知字段、未知指标、错误单位、非有限阈值拒绝，以及给定行情下的确定性规则比较。该结果明确为 `contract_only_no_provider_or_market_data`；不属于模型输入验收。规则只允许 `last_price` / `change_pct` 与白名单运算符，非法账户余额字段被本地校验拒绝。

### 本地独立调度、失败持久化、幂等与重启读回

- 使用 macOS `launchd`，label `local.tonghuashun.monitor-validation`，`StartInterval=65` 秒、`RunAtLoad=true`；触发脚本调用本地服务 HTTP API，不访问网页。三次自动触发分别在 `2026-10-23T16:43:12.799Z`、`16:44:18.286Z`、`16:45:23.471Z` 执行。
- 三次均生成失败记录，失败码 `FUYAO_CREDENTIAL_MISSING`。这是明确失败记录，不是模拟行情或成功监控。
- 重放第一次相同幂等键返回 HTTP 200、`duplicate=true`，记录总数保持 3。停止并重启本地服务后，从同一 SQLite 文件读回 3 条历史记录。
- 页面未打开；任务在三次后卸载。证据：[`local_auto_run.json`](validation/evidence/local_auto_run.json)、[`local-scheduler.out.log`](validation/evidence/local-scheduler.out.log)、[`local-auto-runs.sqlite`](validation/evidence/local-auto-runs.sqlite)。调度安装阶段的三条错误另存于 [`scheduler-setup-failures.log`](validation/evidence/scheduler-setup-failures.log)，不计入后续三次成功触发计数。

## 失败

### 扶摇：首轮未鉴权请求失败，后续真实鉴权已通过

首次未加载 key 的两条请求返回 HTTP 200、业务码 `2003`、`Missing X-api-key`；该证据仅说明当时请求未带 key。后续加载本机 key 后，两端点均业务成功，见“已通过 / 扶摇真实行情与交易日历”。首轮错误证据保留于 [`fuyao_unauthenticated.json`](validation/evidence/fuyao_unauthenticated.json)。

### 首次沙箱网络复验受限，已在授权网络下复验通过

本轮此前在项目目录首次复验时，扶摇返回 `URLError`，DeepSeek 请求为网络失败 `TypeError`；随后在获准网络环境下真实重调，扶摇两端点 HTTP 200 / 业务码 0，DeepSeek 有三个 API 响应。专项审查后发现 DeepSeek 的历史 checker 未充分验证语义，因此不保留其“三场景均通过”的结论。本次专项审查未再调用供应商。历史摘要保留于 [`fuyao_live_rerun.json`](validation/evidence/fuyao_live_rerun.json)、[`deepseek_live_rerun.json`](validation/evidence/deepseek_live_rerun.json)。

### iFinD 公告能力

真实资讯搜索通过，但该结果来自搜狐新闻搜索，不是上市公司公告增量流；`search_notice` 的无效参数请求返回协议错误。当前证据不满足开启公告监控的条件。细节见“已通过 / iFinD MCP”。

## 当前未完成与边界

- **产品链路（产品侧报告）**：产品 session 最新报告称 static v2 / watchlist-api v5 READY，Deno/RPC 与 PostgreSQL 业务事务、任务读回、恢复/重部署证据已完成。验证 session 本次未重新部署、未修改生产配置；health 请求 DNS 失败，因此独立实时确认待网络恢复。早期 FC preflight 中 APP_ORIGIN、数据库连接和认证变量缺失是部署前记录，不能沿用为上线后的当前配置结论。
- **独立调度（本轮失败/受阻）**：无秒悟可验证服务端 cron 创建及任务读回路径；正式 tick 未调用、三时隙未执行、没有本 session 的 Run/Evidence/Notification。CLI预检、DNS探测和 Lead 17:48 目标任务读回应见 [`scheduler_platform_probe_20261024T095727Z.json`](validation/evidence/scheduler_platform_probe_20261024T095727Z.json)。
- 不要求用户重复提供本机已有 provider keys；本轮未读或输出任何密钥。没有购买或启用新增付费资源。

## 对 REVIEW_NOTES.md 的逐项回应

### L-01：正式持久化方案

**回应：产品侧报告生产持久化闭环已完成；验证 session 当前不能独立探活。** `IMPLEMENTATION_REPORT.md` 报告产品运行时已通过 Deno/RPC 使用 PostgreSQL，并记录业务事务、读回、重部署恢复及去重证据。早期 Secret 名称存在但 FC preflight 缺字段，是上线前的历史阻塞；不可表述成当前容器仍未注入。当前验证环境 DNS exit 6，无法本轮再读 URL 或数据库。产品侧证据和验证侧探活限制需分开引用。

**当前交接：** 不要求产品 session 重做已提交的上线和数据库验收。若后续需要独立复核，按 `IMPLEMENTATION_REPORT.md` 指向的产品 Run/Evidence/Notification 与 PostgreSQL读回证据核对；当前先解除验证环境 DNS 阻塞。SQLite/launchd 本地记录不代替产品 PostgreSQL及服务端调度。

**历史运行时交接记录：** [`deploy/RUNTIME_CONFIG_HANDOFF.md`](deploy/RUNTIME_CONFIG_HANDOFF.md) 和 [`meoo_runtime_config_audit_20261024T032607Z.json`](validation/evidence/meoo_runtime_config_audit_20261024T032607Z.json) 记录上线前自定义变量注入限制。产品 session 后续已报告通过正式 Deno/RPC 与 PostgreSQL链路，故该历史 preflight 不再作为当前失败证据；本验证 session没有重新取回 Secret/DSN，也没有读取秘密值。

**证据：** [`backend/store.py`](backend/store.py)、[`backend/schema.sql`](backend/schema.sql)、[`backend/server.py`](backend/server.py)、[`local_auto_run.json`](validation/evidence/local_auto_run.json)。本地恢复证据范围仅限本地 SQLite。

### L-02：验证入口与产品入口交接

**回应：产品 session 报告入口已上线，验证入口仍独立保留。** 当前最新产品报告为 static v2 / watchlist-api v5 READY，并记录 health 200 与生产业务证据；验证 session 本次从本机访问时 DNS exit 6，因此未能独立复核，不将其改写成部署失败。两次镜像发布失败和早期健康 404 已是历史状态。

**产品会话关闭条件：** 产品报告已记录生产 URL 与对应发布版本；验证 session当前待 DNS 可达后再独立读取。V0 本地验证实现仍可独立复验。

### L-03：iFinD 能力范围

**回应：有限通过，公告能力保持禁用。** iFinD 权限、贵州茅台收盘行情和一条新闻搜索通过；收盘价单位与交易所时刻未返回，新闻来自搜狐，URL 只是单条新闻的去重候选。错误请求为参数无效，不是公告权限通过。产品不能基于此开启盘中最新价或公告全量监控。

### L-04：扶摇鉴权

**回应：真实鉴权调用已通过。** 首轮缺少 X-api-key 时为 HTTP 200 / 业务码 2003；本机凭证调用后，快照/日历/日线均 HTTP 200 / 业务码 0。最新字段和时间口径见 [`validation/FUYAO_DATA_BOUNDARIES.md`](validation/FUYAO_DATA_BOUNDARIES.md)。本轮不复核或读取产品运行时密钥；早期 FC 注入失败已由产品 session 后续上线报告覆盖。

## 部署与调度配置

| 项目 | 本轮值 | 验收边界 |
| --- | --- | --- |
| 部署 URL | `https://ucdte4eh02uv.meoo.info`（产品报告） | static v2 / watchlist-api v5；产品 session 报告 health 200。验证侧本次 DNS exit 6，无法独立复核 |
| 秒悟项目 | `TongHuaShun 投资监控 MVP` / `ucdte4eh02uv` | 已绑定、云服务 enabled；产品侧上线报告为当前部署状态 |
| 云数据库 | PostgreSQL，enabled | 产品报告记录 Deno/RPC业务事务及读回/恢复；当前报告引用产品侧证据，不冒称本 session 新复验 |
| 本地验证服务 | `HOST=127.0.0.1 PORT=9901` | 临时回环服务，非公网 |
| 本地数据库 | `validation/evidence/local-auto-runs.sqlite` | 本地文件，仅用于此轮重启恢复证明 |
| 定时器 | macOS launchd，65 秒间隔、RunAtLoad | 人机登录会话的本机任务；不是秒悟云调度 |
| 触发去重 | 分钟槽 `launchd:<epoch-minute>` | 同键重放仅一条本地业务记录 |
| 失败记录 | 缺扶摇密钥时 HTTP 502，错误码 `FUYAO_CREDENTIAL_MISSING` | 已验证本地服务明确记录失败 |
| 秒悟 CLI | 0.5.6 | 只读 cloud status enabled、watchlist-api v5 READY；无 cron 命令。自定义 Secrets早期注入失败后，由产品 session报告的 Deno/RPC方案完成上线 |
| 产品调度契约 | 产品报告确认正式函数 v5 READY；调度入口仍待验证 | `POST /sb-api/functions/v1/watchlist-api/internal/monitor/tick`；`Authorization: Bearer <WATCHLIST_GATEWAY_ANON_KEY>` + `X-Tick-Secret`；每 slot 新 Idempotency-Key、同次重试复用；`batch=1`；读回产品 Run/Evidence/Notification |

### 产品独立调度准备（平台阻塞；未启动）

- **触发目标与鉴权**：产品报告当前正式路径 `POST /sb-api/functions/v1/watchlist-api/internal/monitor/tick`，需平台 JWT Bearer 与 `X-Tick-Secret` 双层鉴权，JSON `{"batch":1}`。产品提供 `scripts/product_tick_once.cjs` 从权限为0600的 `.product-data/production-config.json` 读取凭证；验证 wrapper 不读取或打印凭证，只调用该 worker。health URL 固定要求返回2xx后再触发。
- **超时/重试**：产品单次 worker 超时35秒，默认不重试；本轮 wrapper 采用同一 Idempotency-Key 重试以外的保守策略——发生超时/网络不确定时先停止自动重试，由产品侧按该键核对结果，避免响应未知时重复业务写入。tick业务预算30秒、RPC/上游8秒、租约45秒是产品报告方案；执行边界仍由产品证据限定。
- **运行位置/频率/停用**：秒悟官方[FAQ](https://docs.meoo.com/faq)目前明确不支持自动定时任务；本机 `meoo` 无 `cron` 命令，`--sync-cron` 是 DUAL 发布同步项而非独立创建/管理 API。安全预检 `meoo --json deploy --sync-cron --skip-push --project ucdte4eh02uv` 以退出码 1 返回 `CLOUD_SYNC_INCOMPATIBLE`。未去掉 `--skip-push` 继续发布，避免同步/改动生产。此前工程师转述的最小一分钟能力尚无当前项目任务创建、读回、日志或停用证据。当前明确阻塞，不用本机 runner 替代。
- **本轮结果/证据**：产品页面保持关闭；正式 tick 完全未发送。产品健康 URL 请求在本验证环境 DNS 阶段失败（curl exit 6 / HTTP 000），不据此判定产品下线。没有本 session 的三个 scheduled time、Idempotency-Key、HTTP结果或产品 Run/Evidence/Notification。平台路径及 Lead 17:48 任务快照见 [`validation/evidence/scheduler_platform_probe_20261024T095727Z.json`](validation/evidence/scheduler_platform_probe_20261024T095727Z.json)；交接见 [`validation/SCHEDULER_HANDOFF.md`](validation/SCHEDULER_HANDOFF.md)。

## 实际复验命令

历史复验命令不包含任何凭证。在线 provider 命令通过被 Git 忽略的本机 `.env.local` 加载密钥。以下 CLI 部署命令仅用于说明本次安全预检失败，不要删除 `--skip-push` 后直接执行，否则进入发布/同步路径。

```sh
# 先进入项目根目录；shell 路径中的下划线不要写成反斜线转义
cd "/Users/alanli/Documents/ChatGPT/TongHuaShun"

# 若尚未导入本机 key，运行隐藏提示输入
python3 scripts/import_provider_keys.py

# iFinD 客户端权限（读取本机技能配置，但不打印 token）
node scripts/verify_ifind.cjs

# iFinD 当前真实工具清单、行情、新闻和无效参数响应；输出路径须是新文件
EVIDENCE_OUT="validation/evidence/ifind_live_$(date +%Y%m%dT%H%M%S).json" node validation/ifind_live_check.cjs

# 扶摇真实快照和交易日历请求
set -a; . ./.env.local; set +a
EVIDENCE_OUT="validation/evidence/fuyao_live_strict_$(date -u +%Y%m%dT%H%M%SZ).json" python3 validation/fuyao_probe.py

# DeepSeek 四种自然语言场景（需 DEEPSEEK_API_KEY；严格语义检查）
node validation/deepseek_check.mjs

# V-01 至 V-05 离线回归（不访问供应商）
node validation/review_fixes_offline_check.mjs

# Meoo 本机运行时/CLI 契约检查（不读取凭证、不访问数据库）
python3 validation/meoo_runtime_probe.py

# 当前只读能力核查的安全预检；预期 CLOUD_SYNC_INCOMPATIBLE，禁止继续发布
meoo --json deploy --sync-cron --skip-push --project ucdte4eh02uv

# 本轮重跑使用独立文件名，避免覆盖前次真实调用证据
EVIDENCE_OUT=validation/evidence/fuyao_live_rerun.json python3 validation/fuyao_probe.py
EVIDENCE_OUT=validation/evidence/deepseek_live_rerun.json node validation/deepseek_check.mjs

# 只读秒悟状态/Secret 名称审计；脚本剥离一切 Secret 值
EVIDENCE_OUT="validation/evidence/meoo_runtime_config_audit_$(date -u +%Y%m%dT%H%M%SZ).json" python3 validation/meoo_runtime_config_audit.py

# 当前 iFinD tools/list，只检查权限清单、不调用行情/新闻工具
EVIDENCE_OUT="validation/evidence/ifind_listtools_live_$(date -u +%Y%m%dT%H%M%SZ).json" node validation/ifind_listtools_live_check.cjs

# 本地规则契约；明确不调用 provider/行情
node validation/self_check.mjs

# 本地服务（开发/恢复复验；不得视作云端部署）
HOST=127.0.0.1 PORT=9000 DB_PATH="$PWD/validation/data/monitor.sqlite" node validation/server.mjs

# 服务独立触发（另一个终端；带唯一幂等键）
MONITOR_BASE_URL=http://127.0.0.1:9000 node validation/scheduled_trigger.mjs
```

本轮调度使用 [`launchd.sample.plist`](validation/launchd.sample.plist) 替换本机绝对路径并由 launchd 加载；服务监听 9901、DB 使用上述 `local-auto-runs.sqlite`。为避免旧证据被覆盖，复验生产恢复时应另设新的 `DB_PATH` 和证据文件名。调度设置阶段失败证据保留，不应算入正式三次运行。

## 改动文件与边界

- 验证实现：`validation/server.mjs`、`validation/index.html`、`validation/rule_contract.mjs`、`validation/deepseek_check.mjs`、`validation/deepseek_assessment.mjs`、`validation/self_check.mjs`、`validation/fuyao_probe.py`、`validation/ifind_live_check.cjs`、`validation/ifind_tool_assessment.cjs`、`validation/scheduled_trigger.mjs`、`validation/local_scheduler.py`、`validation/launchd.sample.plist`、`validation/OPERATIONS.md`、`validation/FUYAO_DATA_BOUNDARIES.md`、`validation/meoo_runtime_probe.py`。本次 V-02 复验修改了 DeepSeek checker、评估器、针对性离线检查及操作文档。
- 本次新增：`validation/ifind_listtools_live_check.cjs`（只读清单复验）、`validation/meoo_runtime_config_audit.py`（只读并过滤配置值）、`validation/product_tick_trigger.mjs`（生产 tick 调用准备脚本，默认拒绝运行且本轮未运行）；更新 `validation/fuyao_probe.py` 加小窗日线验证，并更新 `validation/FUYAO_DATA_BOUNDARIES.md`、`deploy/RUNTIME_CONFIG_HANDOFF.md`、`VALIDATION_REPORT.md`。
- 专项离线复验：`validation/runcheck_offline_check.mjs`、`validation/deepseek_assessment_offline_check.mjs`、`validation/deepseek_cli_offline_check.mjs`、`validation/fuyao_probe_offline_check.py`、`validation/ifind_tool_assessment_offline_check.cjs`、`validation/review_fixes_offline_check.mjs`。
- 脱敏证据：`validation/evidence/ifind_live.json`、`validation/evidence/fuyao_unauthenticated.json`、`validation/evidence/local_auto_run.json`、`validation/evidence/local-auto-runs.sqlite`、scheduler 日志。
- 后续真实调用/云项目及离线审查证据：扶摇 `validation/evidence/fuyao_live.json`；DeepSeek 历史复验 `validation/evidence/deepseek_live.json` / `deepseek_live_rerun.json`；本次最终在线/离线证据 `validation/evidence/deepseek_live_v02_strict_final.json`、`deepseek_assessment_offline_v02_final.json`，证据及源文件摘要清单 `deepseek_v02_final_manifest.json`；Meoo 与离线审查证据见各自文件。严格复验迭代中的失败 evidence 保留为独立文件。
- 入口状态：根 `package.json` / `scripts/start.sh` 为产品 Waitress；`npm run start:validation` / `node validation/server.mjs` 为 V0 验证服务。入口交接已完成，公网部署验收未完成。
- 本地凭证辅助：`scripts/import_provider_keys.py`，只负责隐藏交互输入并创建 Git 忽略的 `.env.local`；未包含或记录密钥值。
- Meoo CLI 生成：`src/supabase/client.ts`、`src/supabase/types.ts`；开通云服务时生成。尚未把产品后端接到该客户端或云数据库。
- 没有改动 `backend/` 或 `frontend/` 产品实现文件；产品实现会话应以它们作为各自交付范围，不要覆盖验证目录。

## 限制与复验关闭标准

V-01～V-05整改和已接受的离线/DeepSeek验收保持关闭；扶摇真实三端点小范围复验和 iFinD 当前工具清单复验已通过。盘中报价新鲜度、未来日历/下一开市时间和数值QPS仍未知，公告增量监控禁用。产品部署/数据库闭环为产品 session 已报告完成；验证 session 本次 DNS 失败，未独立复核。秒悟独立服务端调度三时隙受平台能力路径阻塞，未发送 tick、未产生对应 Run/Evidence/Notification。平台提供正式 scheduler 创建、读回、日志及停用方式，或 Lead 指定已有授权外部调度后，再由服务端以双层凭证完成三个正式时隙；不得用本机 launchd 或手动请求替代。

参考平台文档：秒悟 [CLI 部署](https://docs.meoo.com/features/cli)、[常见问题](https://docs.meoo.com/faq)；扶摇 [快速开始](https://fuyao.aicubes.cn/docs/quickstart/)；DeepSeek [API 文档](https://api-docs.deepseek.com/guides/search_fetch)。

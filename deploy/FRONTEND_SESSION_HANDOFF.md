# 独立前端设计 session 交接

## 目标与启动边界

设计范围：改善观澜监控台、规则编辑、任务详情和站内提醒的布局、视觉层级、响应式与交互反馈。现有业务是真实服务，不是静态mock演示。优先让用户回答“检查了吗、满足吗、为什么没有通知”。产品session负责服务端、数据库、部署和业务验收；设计session提交可构建前端改动及浏览器证据，发布由产品session统一执行，避免相互覆盖。

仓库 /Users/alanli/Documents/ChatGPT/TongHuaShun ，分支 codex/daily-close-mvp。开始前读取git状态与最新HANDOFF，保留其他session改动。建议从本轮已提交基线建立独立 codex/frontend-design 工作树，不在共享工作目录同时编辑同一文件。用户尚未要求创建新session，本交接不代表已创建。基线提交和发布逐文件SHA见 artifacts/task-status-release.json；若此文件尚未生成，等产品完成本轮发布再开始集成。

允许设计修改：frontend/src.jsx、frontend/style.css、frontend/components/TaskStatus.jsx及新建纯展示组件/资源。新增依赖需说明必要性，优先已有React/Ant Design。业务适配 frontend/task-status.mjs、frontend/time.mjs、API契约及测试视为只读，确需修改先向产品session说明具体原因；不自行改后端、functions/、deploy/migrations/、调度、鉴权、规则语义。不得改validation/、VALIDATION_REPORT.md或docs/lead/。

## 技术与运行

React + Vite + Ant Design。正式入口 https://ucdte4eh02uv.meoo.info 。同源API前缀 /sb-api/functions/v1/watchlist-api/api/v1；HttpOnly会话，不在浏览器保存API业务密钥。已有演示登录口令使用受控渠道，不进入截图、报告、源码。无远端推送授权，交付本地Git即可。

```sh
npm --prefix frontend ci
VITE_API_PREFIX=/sb-api/functions/v1/watchlist-api npm --prefix frontend run build
node --test tests/task_status.test.mjs tests/daily_close.test.mjs tests/deno_product.test.mjs tests/input_suggestions.test.mjs tests/instrument_discovery.test.mjs
```

npm run build也可；磁盘紧张或依赖已安装时可直接构建，不要清理用户文件。根npm start是历史Python参考，不是当前日收盘服务。不要以本地静态预览冒充生产功能；本地组件测试允许明确TEST fixture，不得把fixture发布成真实行情/调度。

## 保持的产品语义

- 仅已核验沪深A股最新已完成交易日、不复权、CNY日收盘。日期不是精确成交时间。旧盘中规则保持unknown，显式转换才可新建版本。
- 模型生成草稿，不自动保存或启用。未入库标的经真实元数据精确核验入库，查无/歧义继续追问；不自动换股。
- 推荐按钮只回填输入；用户补齐【占位内容】后重新生成草稿。不能伪装成已执行、直接启用或投资建议。
- 预览不发送通知，启用需明确确认。编辑改变规则版本，旧运行结果不能当作新版本判断。
- true/false/unknown三值必须区分。连续true同事件段只提醒一次，冷却到期需有效数据复核；unknown不重新武装。交易、公告、短信、邮件均未支持。
- 已删任务保留只读历史，不能显示编辑/恢复按钮；暂停时历史结果不可误称仍在检查。
- 页面刷新只读，不触发tick或行情执行。网页关闭仍由云Cron运行；每tick最多1任务，日期任务优先，不承诺每任务每分钟检查。

## 接口与数据单位

api()在src.jsx中串行请求，保留请求队列以适应平台并发限制。请求失败统一展示错误；401回登录；不能并发轮询全部详情或自动重试写操作。

- GET /tasks → Task[]；GET /tasks/:id → Task（归属校验，已删也可读）。
- GET /tasks/:id/runs?offset=0&limit=50、/versions、/audit → 历史记录。
- GET /notifications；POST /notifications/:id/read → 已读更新，不改变任务。
- GET /instruments?q=关键词 → 真实检索并核验；POST /rules/parse {text,instrument_id?} → status/drafts/questions/unsupported，可能有instrument_lookup、suggestions、suggestions_status。suggestions为可点击字符串数组，不是RuleSpec。
- POST /rules/preview RuleSpec → 三值结果与证据，不创建任务。
- POST /tasks RuleSpec，PATCH /tasks/:id {spec,expected_version}；POST /tasks/:id/activate|pause|resume {expected_version}。启用、暂停、删除保持现有确认流程及并发版本校验。

Task保留原字段，009增量的重点如下：

| 字段 | 含义 |
|---|---|
| version/lifecycle/spec | 当前规则版本、生命周期、完整规则 |
| runtime.next_run | 计划检查时间，Unix秒；null不是0 |
| runtime.overdue | 服务端迟到策略：日期至少60秒；日收盘600秒 |
| runtime.state.cooldown_until | 冷却截止Unix秒，不能据此自行推断已发通知 |
| last_evaluation | 当前版本最近一次成功执行；无当前版本记录为null，历史仍在runs |
| last_evaluation.result | true/false/null，null不可渲染成false |
| last_evaluation.decision | notify/no_match/already_notified/cooldown_suppressed/insufficient_data/missed/skipped_not_due等 |
| last_evaluation.evidence[] | 条件、原始十进制价格字符串、trade_date、quality、reason_code、provider；不自行Number比较 |
| last_evaluation.evaluated_at/calendar | 实际检查Unix秒；日期提醒原定/实际/迟到秒数 |
| last_evaluation.trigger_request_id | 与Run关联的已认证tick请求键；cf-cron:ucdte4eh02uv:前缀识别约定云请求来源 |
| scheduler_observation.server_time | 本次数据读取时服务端Unix秒，避免客户端钟误判 |
| last_cloud_request / last_cloud_finished | 约定云请求键的最近开始/完成Unix秒；与泛用last_request分开 |
| expected_interval_seconds / warning_after_seconds | 当前Cron60秒/3分钟无完成警示，产品观测策略不是供应商SLA |
| automatic_execution_verified | 仍false：单次读模型不等于独立日志验收，不要据此显示“自动调度未接入” |

来源判定靠已认证请求键约定，仍需验证session独立日志佐证；近期成功不能声称历史零失败。19:44验证报告记录30分钟31slot中一次health超时随后恢复，不得宣传全窗口无故障。

所有展示时区Asia/Shanghai；Unix字段单位秒，ISO字段按偏移转换，不能字符串截断。frontend/time.mjs处理datetime-local秒/毫秒往返。价格始终保留字符串。状态是读取时快照：显示读取时间，提供刷新，不伪造实时倒计时或后台执行状态。

## 推荐组件与验收场景

TaskStatus组件负责展示，taskStatus(task)纯适配模块统一语义。可换视觉布局，但应保留标题/解释、逐条件依据、当前版本检查、计划时间、冷却与调度观察。通知按钮和证据入口继续可达。新增组件需遵守keyboard focus、aria-label、触控尺寸，长推荐文本允许换行。

至少检查：
1. 真实茅台/招商true且已通知；平安false无通知，明确日期和阈值。
2. 日历一次完成且曾迟到，不显示仍等待执行。
3. TEST冷却、持续true去重、unknown、不满足、请求延迟/未完成、暂停/草稿/删除。
4. TEST修改版本后无新运行，不拿旧结果展示为新版本。
5. 自然语言追问→推荐点击→占位拦截→补齐→草稿→试运行→显式确认；测试不要未经约定占用10任务容量。
6. 360px移动端、桌面，键盘操作，加载/空/错误态，长名称和多条件。

真实样本见artifacts/task-status-live.json（只读，无密钥）；测试fixture仅在tests/task_status.test.mjs并明确TEST。最终设计session交付：本地提交、改动文件清单、构建/测试实际退出码、桌面/移动截图、未完成项。请勿自行部署或把未运行检查标成通过。


## 沪深范围增量（用户已授权，2026-10-24）
产品已将范围扩为沪深A股，包含深市主板和创业板，仍仅日收盘。保持字段结构不变；Instrument.market可为SH/SZ，ID为CN.SH.code或CN.SZ.code，不能拼死.SH；按返回name/code/market展示。页面范围使用“沪深A股”。日历与缓存后端按交易所隔离，设计不应自行改语义。详见deploy/SH_SZ_SCOPE.md与HANDOFF最新发布结果。产品本轮仅改frontend/src.jsx范围文字，请设计集成时保留；task-status接口不变。

最新沪深范围基线覆盖旧task-status基线：artifacts/sz-release-manifest.json，函数v16/static10；三深市真实预览与两个自动任务均通过。不要恢复旧范围文字。

## 模型设置增量（用户明确要求）
新增独立组件 frontend/components/ModelSettings.jsx，由frontend/src.jsx页头“模型设置”进入。请设计集成保留入口与全流程：默认内置告知、当前生效配置、提供商/模型/密码输入、测试不保存、保存实际测试、恢复内置、错误与加载状态。API与安全说明见deploy/LLM_SETTINGS.md。不得将Key存入localStorage、日志或截图；共享demo账户生效范围需展示。所有LLM环节统一服务端配置，不能只在页面展示选择。后端提供providers列表，当前DeepSeek/百炼北京，不做任意URL输入。

## 模型设置协议URL版（覆盖上一节固定提供商/禁止URL输入）
用户要求改为OpenAI/Anthropic协议+自填URL。ModelSettings已改为接口协议、API URL、模型、Key。后端GET.providers现在是协议列表；POST增加base_url。测试失败HTTP200但ok=false，保存失败HTTP200但tested=false且mode=builtin；必须显示warning。规则解析响应增加model_warning，显示自动回退信息。不要恢复上一版本“失败不回退”或固定DeepSeek/百炼选择器。当前组件/API完整契约见LLM_SETTINGS.md。

## 漏检恢复接口增量（不做雷达）
产品修复013：last_evaluation可增加gap/retry/recovery。gap={from,to,reason_code,historical_prices_replayed:false}；retry={consecutive_failures,next_retry_at,last_success,policy}；recovery={previous_failures,recovered_at,historical_prices_replayed:false}。runtime.state新增failure_count/failure_since（恢复或改版清除）。继续按当前版本读取，unknown不表示条件不满足；日收盘重试15/30/60分钟封顶。新字段展示可纳入现有任务说明，不创建雷达页；设计session不要自行改SQL/调度。详见RECOVERY_ACCEPTANCE.md。

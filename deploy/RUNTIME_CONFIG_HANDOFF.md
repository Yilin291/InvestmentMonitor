# 当前运行时交接更新（2026-10-24 17:42）

正式线上采用已批准的Deno + 受限事务RPC + 既有PostgreSQL；watchlist-api v5和static v2已实际上线。原生DSN/FC变量注入不再是当前阻塞。当前Secrets由Deno实际读取；双层tick凭证契约及安全配置文件位置见deploy/HANDOFF.md。下面保留原FC核查历史。

# 既有秒悟目标：运行时配置阻塞操作单

目标 `ucdte4eh02uv`，不新建数据库/项目，不重复迁移 watchlist。

## V0 只读平台能力核查（2026-10-24 11:27，北京时间；优先于早期未核查表述）

### 核查结论

1. **FC 镜像已文档化的自动注入**：秒悟官方 CLI 技能的 image-deploy/cloud-patterns 只明确承诺项目云服务开启后，在 FC 容器部署时注入 `SUPABASE_URL`、`SUPABASE_ANON_KEY`、`SUPABASE_SERVICE_ROLE_KEY`、`MEOO_PROJECT_API_KEY`。文档说明服务端通过进程环境变量读取；本地 `.env` 会从镜像发布包排除。没有列出 `APP_ORIGIN`、`DEMO_PASSWORD`、`SESSION_SECRET`、`TICK_SECRET`、provider key 或 `SUPABASE_DB_URL` 的自动注入，也没有说明通用 `meoo secrets` 写入项会引用进 image runtime。
2. **项目 Secrets 不等于镜像变量已注入**：当前只读 `meoo --json secrets list` 可见这些配置名（包括 `SUPABASE_DB_URL`、业务认证项和 provider key），但 CLI 文档明确 Secret 值 write-only；清单不回读真实值，也不能把列表摘要视为 URI/DSN。产品两次镜像发布日志的启动 preflight 都显示应用必需变量不存在，应用退出码 2、发布退出码 1；数据库 driver 尚未启动，因此没有 TLS、网络或 DB 权限失败证据。
3. **PostgreSQL 原生 DSN 获取方式未由秒悟 CLI 证实**：`meoo cloud status --json` 返回云服务 enabled 及 Supabase HTTP API 连接元数据，没有返回原生 PostgreSQL host/port/database/user/password/DSN；项目 Secret 清单只有变量名。`meoo cloud pull-env --help` 只说明把 Supabase URL、Anon Key 等写入本地 `.env`，本轮没有执行该写文件命令。当前不能声称已获得原生 DSN。
4. **运行时阶段**：文档化的四个平台值声明为“deploy time”注入到 FC 容器；对于自定义业务 Secrets，官方资料未确认是 build、deploy 还是容器启动时注入，也没有记录 FC 自定义变量管理页面/引用语法。由于生产容器 preflight 已观察到这些变量缺失，当前应用实例并无可读值。
5. **只读当前状态**：本地 `meoo` CLI 0.5.6；目标 cloud status enabled，当前 project binding 标识匹配 `ucdte4eh02uv`、未部署；Secrets 清单包含名为 `SUPABASE_DB_URL` 等字段。对应脱敏证据 [`meoo_runtime_config_audit_20261024T032607Z.json`](../validation/evidence/meoo_runtime_config_audit_20261024T032607Z.json)。值未写入证据。秒悟原两次失败部署与产品 11:23 回传均未被本轮修改或覆盖。

### 给产品 session / 平台操作者的准确操作单

由产品 session 统一执行所有生产配置写入和发布；V0 不再写 Secrets、不重试发布：

1. 在秒悟项目 `ucdte4eh02uv` 的**FC 镜像/函数服务运行时配置**中确认是否有“Environment variables / Secrets references”设置页或官方引用机制。该入口必须明确绑定本项目的 FC 镜像 revision；普通项目 Secrets 名称清单、Edge Function secrets 页和本地 `.env` 都不能代替。
2. 如有受支持入口，使用项目内部已存值为 `APP_ENV`、`APP_ORIGIN`、`PRODUCT_RUNTIME_PROBE`、`DEMO_PASSWORD`、`SESSION_SECRET`、`TICK_SECRET`、`FUYAO_API_KEY`、`DEEPSEEK_API_KEY` 配置服务端变量，不把值放入 argv、日志、报告或镜像源文件；发布 revision 后只记录逐变量 presence 布尔值，确认 preflight 进入 driver 前通过。
3. 从**该 Meoo PostgreSQL 实例自身的官方连接设置**取原生 PostgreSQL 连接 URI，并安全注入为产品已约定的 `SUPABASE_DB_URL`（或 `DATABASE_URL`）。若控制台无此 connection URI 页，向 Meoo 平台索取同实例 FC 可达的原生 URI/凭据注入方式。不要从 Supabase HTTP API URL、anon/service-role key、Secrets 名称或 64 位摘要拼造 DSN。
4. 注入实际 URI 后，由产品自己的运行时探针验证 TLS、提交/回滚、唯一约束、失败后连接恢复和业务读回。当前 preflight 未进入 psycopg，只有这些事务探针成功后才可报告连接/TLS通过。
5. 若官方确认 FC 镜像不支持自定义业务 Secrets 和原生 PostgreSQL URI，由 Lead 决定是否把同一 PostgreSQL事务能力改为明确的受支持 Supabase RPC/API（只暴露专用业务操作，不做任意 SQL API），或批准其他运行环境。该替代会改变现有持久化访问实现，需要产品 session 实施和重新验收；V0 未实施、未购买任何资源。

### 官方依据与证据范围

- 秒悟官方 CLI image-deploy：[镜像运行环境、环境注入清单、临时容器存储](https://github.com/ali-meoo/meoo-cli/blob/main/skills/meoo-cli/references/image-deploy.md)。
- 秒悟官方 cloud-patterns：[服务端 SDK 与 FC 容器自动变量清单](https://github.com/ali-meoo/meoo-cli/blob/main/skills/meoo-cli/references/cloud-patterns.md)。
- 秒悟官方 CLI 主技能：[Secrets write-only、cloud/deploy 命令边界](https://github.com/ali-meoo/meoo-cli/blob/main/skills/meoo-cli/SKILL.md)。
- 本机安装同名技能核对位置：`/Users/alanli/.local/lib/node_modules/@aliyun-meoo/cli/skills/meoo-cli/`；本机 `meoo --version` 为 `0.5.6`，`meoo cloud --help` 将 `pull-env` 说明为本地 `.env` 写入，`meoo secrets --help` 仅提供 list/set/delete 管理，不提供 FC runtime 引用参数。
- 当前生产 preflight/部署失败事实仍以 [`deploy/HANDOFF.md`](HANDOFF.md) 中产品 session 最新记录和 `IMPLEMENTATION_REPORT.md` 为准；本次没有调用产品 runtime、修改远端配置、写入 Secrets、迁移数据库或发布。

## 已执行及证据

两次 `meoo --json deploy --project ucdte4eh02uv --runtime image --skip-push --force` 均退出1，镜像实际执行 `/code/scripts/start.sh` 并由产品启动保护退出2。第二次 traceId：`0a0328ca17927787481087323ed290`；平台健康检查60秒后HTTP412/CAExited。日志明确 preflight 阶段以下变量不存在。证据 `artifacts/product-deploy-diagnostic.json`。

`meoo secrets` 写入成功但未进入该FC容器。Secrets列表为摘要，不能当DSN。平台预定URL `https://ucdte4eh02uv.meoo.info` 尚未发布可用。

## 请平台或具有配置入口的操作者完成

1. 指定此项目 **FC镜像运行时** 的受支持环境变量/Secret引用入口（不是仅云函数Secrets管理页）。
2. 在该入口配置 APP_ENV=production、APP_ORIGIN=https://ucdte4eh02uv.meoo.info、PRODUCT_RUNTIME_PROBE=1。
3. 将 `.product-data/production-config.json` 中 DEMO_PASSWORD、SESSION_SECRET、TICK_SECRET、FUYAO_API_KEY、DEEPSEEK_API_KEY 安全注入同一运行时，不打印、不提交、不发聊天、不放前端或镜像源码包。文件0600且被Git/镜像排除。
4. 注入该既有PostgreSQL的真实原生连接串 SUPABASE_DB_URL 或 DATABASE_URL，连接用户需访问已建 watchlist schema 和表/序列。必须支持TLS（require或更严格）；不以 anon/service-role HTTP key 代替DSN。不要覆盖平台保留Secrets或把摘要当原值。
5. 返回“配置入口/配置完成”即可，不返回密钥。产品session重新发布，用Store事务探针完成TLS、提交、回滚、唯一冲突恢复，再验证健康/登录/Host/Origin/tick/端口。

若平台镜像仅支持四个内置Supabase HTTP变量且不开放原生PostgreSQL或业务Secrets注入，请明确该能力限制。此时需要Lead决定受支持的服务端事务RPC接入方案；不能伪称当前Psycopg成功，也不自动另建生产环境。

平台CLI技能 cloud-patterns 仅列自动注入 SUPABASE_URL、SUPABASE_ANON_KEY、SUPABASE_SERVICE_ROLE_KEY、MEOO_PROJECT_API_KEY；未承诺原生DSN/任意业务变量。公开文档：https://docs.meoo.com/open/reference/cloud-services 。


## 11:23 核查更新

本轮字段级只读核查和具体平台请求/替代方案见 `deploy/PLATFORM_DECISION_PR01.md`。公开凭证接口403需要权限，但仅追加该权限不能保证原生DSN；不要让用户无目的扩权。尚无可核实的FC自定义Secret注入入口，未重发部署。

## 11:35 只读修复路径补充（未改产品实现/配置）

- 官方 `cloud-patterns` 明确支持 FC 服务端用 `@supabase/supabase-js` 读取 `SUPABASE_URL` 与自动注入的 `SUPABASE_SERVICE_ROLE_KEY` 执行 Supabase Data API 操作；该密钥绕过 RLS，只能在可信服务端使用。此路径可避免要求原生 PostgreSQL DSN，但它需要产品 session 把现有 psycopg 存储适配器改成 Supabase 客户端。
- 为保持一次 tick 的 Run/Evidence/Notification 写入原子性，建议把“处理一个 tick”的多表事务封装为受限 Postgres function，再由服务端 `supabase.rpc(...)` 调用；利用唯一约束处理 `Idempotency-Key`，函数只接受明确业务参数，不开放任意 SQL。Supabase 官方支持从客户端通过 RPC 调用 Postgres function；原子性和重复键语义仍须由产品 session 用真实 DB 事务探针验证，当前不算通过。
- 该路径只解决数据库访问，不自动提供 `APP_ORIGIN`、`TICK_SECRET`、`DEMO_PASSWORD`、`SESSION_SECRET` 或扶摇/DeepSeek key。产品 session仍须先从秒悟平台确认 FC 自定义 env/Secret 注入；若确实不支持，Lead 需在“把密钥依赖移入平台支持的服务端函数”与“改用能提供自定义运行时密钥的部署环境”之间决策。没有作任何资源购买或配置变更。
- 参考：秒悟 [FC 服务端 Supabase 客户端和四项自动变量](https://github.com/ali-meoo/meoo-cli/blob/main/skills/meoo-cli/references/cloud-patterns.md)；Supabase [数据库函数与 RPC](https://supabase.com/docs/guides/database/functions)、[JavaScript RPC 调用](https://supabase.com/docs/reference/javascript/rpc)。


## 2026-10-24 12:06 官方工单已提交

按用户明确授权，通过秒悟“用户菜单 → 问题反馈 → 提交工单”，提交三项能力确认：FC自定义Secret注入入口、既有PostgreSQL原生TLS连接、独立云调度（周期/鉴权/超时/重试/日志/套餐限制）。工单ID **000GJSKKC0**，详情 https://meoo.com/support/detail?id=000GJSKKC0 ，提交时间12:06:33北京时间，提交后详情页读回状态**已分派**。尚无平台答复，不计为能力已确认或配置完成。

已附项目ID、失败traceId和必要变量缺失的脱敏事实；没有发送任何密钥或附件，没有授权购买、删除资源或换项目。正文和状态证据：`artifacts/meoo-support-request-000GJSKKC0.txt`、`artifacts/meoo-support-ticket-000GJSKKC0.json`。下一步核对工单答复中的实际入口/约束，再执行已授权配置；不在原失败条件下重复部署。

# 既有项目运行时配置：核查与决策包

时间：2026-10-24 11:23 北京时间。项目仅 `ucdte4eh02uv`。

## 可复核事实

1. 原两次发布失败；第二次容器preflight必要变量全部false，尚未调用driver。原证据 `artifacts/product-deploy-diagnostic.json`。本轮没有重复部署、迁移、覆盖Secrets或新建资源。
2. 本轮通过现有CLI ApiClient只读请求 `GET /open/v1/cli-compat/projects/ucdte4eh02uv/cloud/environment` 成功；仅保存字段名，返回 sbInfo.url/publicUrl/anonKey/serviceKey 和 meooProjectApiKey，没有原生DSN或自定义容器变量字段。
3. `GET /open/v1/projects/ucdte4eh02uv/cloud/credentials` 返回HTTP403、insufficient_scope。未尝试绕过权限；此接口官方响应也仅承诺url/anon_key/service_key，**补此权限本身不能证明会获得DSN**。退出命令0只表示诊断完成，内含403不算凭证读取成功。
4. 证据 `artifacts/runtime-config-fields-pr01.json` 不含任何凭证值。当前验证session文件中没有新增可执行注入方式；未改其文件。
5. 已核对官方云服务文档 https://docs.meoo.com/open/reference/cloud-services 及已安装CLI部署命令/技能。文档描述云函数Secrets、Supabase HTTP访问；没有找到当前镜像任意变量/原生DSN的配置契约。**尚不能据文档缺失断言平台绝对不支持。**

## 可直接提交平台的请求（未代发）

项目：ucdte4eh02uv；失败traceId：0a0328ca17927787481087323ed290。
现象：项目云Secrets已设置，但FC镜像容器启动时 APP_ORIGIN、SUPABASE_DB_URL/DATABASE_URL、DEMO_PASSWORD、SESSION_SECRET、TICK_SECRET 均不存在；根脚本启动保护退出2。请明确：

- 此项目FC镜像如何引用项目Secrets？提供具体控制台入口或受支持API及权限，不需要返回Secret值。
- 现有PostgreSQL是否向该FC运行时提供原生TLS连接？若支持，请在服务端注入SUPABASE_DB_URL或DATABASE_URL并授权已有watchlist schema；不要重新创建数据库或迁移。
- 若镜像只注入内置Supabase HTTP凭证，请明确自定义业务Secrets及原生PostgreSQL的能力限制。

业务key已有本机0600私有配置；有受支持注入入口后由产品session执行，不让用户重新提交key。

## Lead可选方案及代价（均未擅自实施）

A. 保留当前Psycopg/Waitress：由平台落实同一FC的Secrets引用与原生TLS连接。改动最少，完成后直接运行已有Store事务探针及线上业务验收。当前首选。

B. 若平台明确不支持A：仍使用同一项目和watchlist PostgreSQL，评估Supabase事务RPC + Deno云函数后端。需要把领取/提交/去重/版本校验等原子逻辑封装为固定RPC，严格固定search_path、撤销PUBLIC/anon执行权，仅服务端授权身份执行；外部取数仍在事务外。不提供任意SQL接口、不把管理API用户凭证交给运行时。Deno云函数读取现有Secrets，前端同源代理/登录/session/Host/Origin/tick鉴权需重新验证。此项是后端架构变更，工作量和验收面较大，须Lead批准后实施；不能称作Psycopg验收通过。事务RPC可达性、私有schema授权、云函数超时和恢复能力均待实测。

若A无支持、B未获批准，则如实保留线上未交付；不将本机SQLite、V0服务或静态壳页替代生产产品。不申请另一套资源。

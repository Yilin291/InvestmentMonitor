# 观澜运行与交付说明（2026-10-24 ON修复后）

## 当前入口与版本

- 产品：https://ucdte4eh02uv.meoo.info
- 健康：GET /sb-api/functions/v1/watchlist-api/api/health，当前release=deno-close-v16、storage=postgresql_rpc。
- 前端static v10；Deno watchlist-api v16、verify_jwt=true；既有watchlist PostgreSQL，增量001–010已应用。
- 当前源码清单见artifacts/close-release-manifest-r4.json，源码快照watchlist-product-20261024-r4.zip；旧r1/r2仅历史。

## 登录与限流

已有演示口令从受控的`.product-data/production-config.json`读取；不要发到聊天、日志、视频或提交到仓库。浏览器使用原有HttpOnly/Secure/SameSite=Strict会话。

所有云函数实例调用同一个数据库限流函数watchlist_login_gate_v1。此演示产品仅一个demo账户，共享滚动60秒窗口，最多10次登录尝试，成功/错误口令都计数；不是按IP限流，也不是函数内存计数。第11次及窗口内正确口令返回429与Retry-After，等待后再尝试，不重置数据表绕过。数据库不可用时503拒绝登录。限流验证会短暂影响同一demo账户的其他登录，请在窗口恢复后进行演示；已有有效会话不受影响。

## 路由与平台边界

外部前缀保持 `/sb-api/functions/v1/watchlist-api`。目标网关实际转发给Deno的是已剥离前缀的路径（如/api/health），函数仅匹配完整允许路径，绝不indexOf截断。任意/嵌套前缀及后缀近似路径404。

网关会把 `//api/health`、`/api/%68ealth`规范化为 `/api/health` 后再转发；应用看不到原始编码形态，因此这两个外部表示可返回同一健康资源200。离线直接将未规范化路径交给handler会404。不要把这层规范化说成网关原始字节严格拒绝，也不推断业务鉴权被绕过。

## 独立调度交接

正式tick：POST /sb-api/functions/v1/watchlist-api/internal/monitor/tick。

- Authorization: Bearer WATCHLIST_GATEWAY_ANON_KEY
- X-Tick-Secret: TICK_SECRET
- Idempotency-Key: 每个时隙独立、重试同次复用；JSON {"batch":1}
- `node scripts/product_tick_once.cjs REQUEST_ID`仅一次调用；不是调度器。验证session的wrapper负责时隙元数据。

不要在浏览器或URL存放调度密钥。验证session已部署Cloudflare Worker tonghuashun-tick，每分钟Cron，19:03报告仍为探测模式；正式tick及持续自动执行尚待日志与业务记录联合验收。本机runner不能代替云端证据。

收到调度日志后，核对scheduled_at、actual_at、request_id、HTTP结果与数据库ticks.outcome关联run_id；同一任务的通知dedup_key最多一条。`scripts/read_scheduler_business.cjs 新证据文件`只读核对指定演示任务与到期后tick，无手动执行副作用。响应未知时先查同键记录，不用新键盲目补发。

## 备份、回退与交付

006只新增短期登录计数表与受限RPC，未改业务状态或删除既有数据。历史14业务表的隔离恢复不等于完整实例灾备或可直接接管的运行环境；登录计数不属于业务历史快照，完整重建需保留迁移与函数配置。不要重跑已应用迁移，不回退到存在ON-01/02缺陷的旧函数来绕过故障。

源包不含密钥、私有配置、node_modules或validation/、docs/lead/；前端构建命令npm run build，运行目标以本说明为准。根npm start是Python参考实现，当前static+Deno部署不执行它。

视频artifacts/watchlist-demo-20261024-r2.mp4为161.4秒真实页面采样实录，保留观察时长并加中文范围字幕，无口令/密钥输入。日期提醒展示的是已完成的手动功能验收；自动任务仍逾期、无执行记录；价格有真实报价证据但unknown、无价格通知。该视频不是完整MVP或自动调度通过证明。

## 日收盘新增运行范围

本轮经用户明确批准的冻结后范围调整，执行007/008并发布v8/static4。完整数据与缓存契约见DAILY_CLOSE_CONTRACT.md。日级规则是新kind，旧last_price不自动迁移。未知工作日覆盖不当休市，周末使用正向核验的周五收盘；失败15分钟重试为产品策略。

用户已授权验证session在已有Cloudflare免费额度部署一个Cron触发器，已收到探测版部署记录，尚不能宣称正式业务自动运行。三项日收盘演示任务已启用；产品只读核对工具scripts/close_business_readback.cjs。最终视频需待实际自动闭环另录，r2不是日收盘新版本视频。


自然语言追问后可点击模型推荐，仅填入编辑框；补齐【占位内容】再生成草稿。缺阈值不猜价格，推荐失败保留追问。当前v15/static8对应源码哈希见artifacts/input-suggestions-source-v15.json，r4包为历史，最新本地bundle为r5。


009已应用：仅更新任务只读函数，last_evaluation限定当前版本，新增证据和云请求关联。任务解释纯模块frontend/task-status.mjs，展示组件frontend/components/TaskStatus.jsx；服务端读取时间用于延迟判断，3分钟无云完成告警是产品策略。当前基线以artifacts/task-status-release.json为准，旧r4/r5包保留历史。


沪深范围更新v16/static10，010已应用，只扩展标的导入与缓存合法键；不重复迁移。新代码/包以artifacts/sz-release-manifest.json为准。

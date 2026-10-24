# 源码布局与复核

frontend/：最终v14界面，含Three.js助手及原许可证。
functions/watchlist-api/：Deno v20生产业务。
deploy/migrations/：001–013增量迁移；既有生产库不可重复覆盖。
validation/cloudflare/：独立Cron源代码、配置、锁文件与10项测试。
tests/：产品离线回归。
submission/：脱敏验收证据、真实截图和最终视频。
backend/：历史Python参考实现，非当前日收盘生产后端。

从仓库根目录执行 `npm run build` 构建前端；执行 `node --test tests/*.test.mjs validation/cloudflare/worker.test.mjs` 运行80项离线检查。完整服务运行还需要受限数据库RPC、供应商密钥与云调度，评审可直接使用README在线URL。

本次发布在目标仓库初始提交之后追加源码快照，保留该初始历史，不把本地多人并行工作区的所有未跟踪文件直接推送。构建已匹配v14四个产物哈希。

你负责观澜自选股监控的前端设计与交互优化。请先读：
- /Users/alanli/Documents/ChatGPT/TongHuaShun/deploy/FRONTEND_SESSION_HANDOFF.md
- /Users/alanli/Documents/ChatGPT/TongHuaShun/deploy/HANDOFF.md 最新增量
- /Users/alanli/Documents/ChatGPT/TongHuaShun/README.md
- /Users/alanli/Documents/ChatGPT/TongHuaShun/artifacts/sz-release-manifest.json

重点：让用户快速看懂“检查了吗、结果是什么、为什么没通知”。改善监控台、任务详情、规则编辑和站内提醒的视觉层级、响应式及可访问性，保留真实API与完整业务流程。

从已交接基线创建独立codex/frontend-design工作树。修改前端展示文件；task-status.mjs/time.mjs和业务契约只读，必要调整先提出具体理由。不要修改后端、数据库、鉴权、调度、validation/或docs/lead/；不要自动启用任务、公开推送或独自发布生产。产品session负责集成发布。

完成本地构建、相关测试和真实浏览器桌面/移动核对，交付本地Git提交、变更清单、截图、实际结果及未完成项。禁止用模拟行情/调度冒充线上结果。优先复用React/Ant Design，不新增产品功能。


## 沪深范围增量（用户已授权，2026-10-24）
产品已将范围扩为沪深A股，包含深市主板和创业板，仍仅日收盘。保持字段结构不变；Instrument.market可为SH/SZ，ID为CN.SH.code或CN.SZ.code，不能拼死.SH；按返回name/code/market展示。页面范围使用“沪深A股”。日历与缓存后端按交易所隔离，设计不应自行改语义。详见deploy/SH_SZ_SCOPE.md与HANDOFF最新发布结果。产品本轮仅改frontend/src.jsx范围文字，请设计集成时保留；task-status接口不变。

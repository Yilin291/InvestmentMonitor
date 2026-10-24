# 正式路由方案与审查历史

当前：用户已明确要求实现正式业务链路，并批准Authorization平台anon JWT + X-Tick-Secret原业务密钥的双层tick方案。已实施；具体实测及公开契约见HANDOFF.md与IMPLEMENTATION_REPORT.md。下文为提出方案时的历史记录，不再要求重复批准。

# 请求Lead审查：已实测同源代理的产品路由方案（尚未改正式API）

2026-10-24 16:49。依据DECISION_DENO_RPC的接口变更审查要求。

## 新事实与推荐

已实测 `https://ucdte4eh02uv.meoo.info/sb-api/functions/v1/watchlist-probe`：缺业务密钥401、正确密钥200，证据 `artifacts/deno-same-origin-authenticated.json`。因此撤回先前跨源内存会话建议，采用现成同源 `/sb-api` 代理，保留HttpOnly Cookie身份方式。

- React仍发布于 https://ucdte4eh02uv.meoo.info 。产品API固定前缀 `/sb-api/functions/v1/watchlist-api`，内部继续 `/api/v1/...` 和 `/api/auth/...`；原前端API helper统一添加前缀。
- 登录后继续 `monitor_session` 签名会话，HttpOnly/Secure/SameSite=Strict/Path=/，owner由已验证签名确定为demo，12小时过期；禁止客户端owner覆盖。Cookie已经通过同源HTTPS CookieJar设置、携带、清除实测；证据artifacts/deno-cookie-readback.json。浏览器登录仍未验收。
- 浏览器不需要跨源请求，不设置Access-Control-Allow-Origin通配；写请求强制确切APP_ORIGIN。GET依赖业务会话及浏览器同源隔离；所有入口固定允许路径，拒绝未支持方法和超限体。
- 正式调度地址变为 `/sb-api/functions/v1/watchlist-api/internal/monitor/tick`，保持 `Authorization: Bearer <TICK_SECRET>` 和 Idempotency-Key及JSON批次契约，不新增业务鉴权头。产品函数自己校验Bearer，不依赖平台JWT标记。
- 重要实测：探针部署元数据verify_jwt=true，但缺网关Authorization、持正确业务Secret的请求仍200。因此未证实平台网关JWT强制；代码业务鉴权为实际防线，原Python也自行验证身份，不借公开anon key授权。正式业务函数将保持独立认证。不会为兼容而关闭业务鉴权。
- 所有service-role/RPC仅云函数调用，浏览器不持有管理凭证；平台转发头不能决定owner或应用Origin。

请Lead审查上述**API前缀变化、沿用同源Cookie和原tick Bearer**。未获明确批准前不变更正式前端/API；独立受保护probe继续取证。

## 执行时限尚缺

官方Meoo文档和meoo info未给目标Deno函数最大执行时限。当前测得请求176–918ms，RPC客户端超时8s、SQL函数5s；这些是应用自设上限，不是平台承诺。先不沿用原Python45s批次/90s租约，不以短请求成功判定最大时限通过。需平台/验证session提供目标时限依据后设置批次和租约；超时/中断后以DB时间和lease token恢复，未知提交结果重试必须同幂等键。

## 17:07 工程师答复后的时限与恢复设计（待实现）

用户转述同一工单工程师确认：Edge Function网关60秒超时。记录于artifacts/deno-engineer-timeout-basis.json；本轮没有独立读回工单。该答复给出网关等待上限，不证明worker CPU配额、存活时长或JWT执行行为。上节“缺最大时限依据”为此前状态。

迁移采用保守预算：单次tick最多领取1项，总预算30秒，外部请求单次8秒，RPC单次8秒，租约45秒（均小于网关60秒）。每一步采用剩余总预算与自身超时的较小值；没有足够完成预算则不再领取。上述为待实现配置，不计作运行验证。

领取与完成均为独立短事务；领取写入DB时间计算的lease_until及token。请求被中断不假定事务失败：相同幂等键先读已有结果；未完成且租约过期后，由后续独立tick回收。完成事务核对DB时间、token、version、generation和生命周期，旧worker即使仍存活也不得提交。通知唯一键与执行结果同事务提交，避免未知响应后重试重复提醒。应补目标环境并发、截止边界及中断恢复实测。

已查阅 https://docs.meoo.com/open/authentication ：它描述管理API的用户Key/OAuth/团队凭证与scope，不能替代云函数业务会话、tick Bearer或RPC执行权限。此前403 insufficient_scope与探针缺网关JWT仍200是不同问题；不扩大平台账号权限，也不将网关认证标为通过。

正式API前缀仍待Lead审查；此项为DECISION_DENO_RPC第23行的明确要求。无需重复申请Deno/RPC架构批准。

用户现已明确要求“实现正式业务链路”，本轮据此实施已提交的同源前缀方案。实际内部认证路径保持原有 /api/v1/auth/*（修正此前方案简写 /api/auth/*）；不更换认证架构。

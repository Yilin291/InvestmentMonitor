# R2-HTTP：产品 HTTP 与入口交付

状态：Waitress 本地真实进程测试通过；公网代理、生产数据库、线上运行尚未验收。

## 根入口已经交接

- `scripts/setup.sh`：创建隔离 `.venv`，安装固定 Waitress 3.0.2，按前端 lockfile 安装/构建，编译检查 Python。
- `scripts/start.sh` / 根 `npm start`：启动 `backend.serve`，默认 `APP_ENV=production`、`0.0.0.0:${PORT:-9000}`，符合 V0 回传的平台契约。
- `deploy/product-start.sh` / `npm run start:local`：使用同一 Waitress 传输，默认本机开发模式。
- `npm run start:validation` / `node validation/server.mjs`：保留 V0 独立复验。
- `backend.server` 的 ThreadingHTTPServer 仅保留旧本地测试入口；根产品入口不再使用它。

**production 不再因为 HTTP 入口是开发服务器而被阻塞，但仍在生产数据库配置和驱动连接/迁移检查未通过时拒绝启动。** 缺 PostgreSQL/HTTPS 配置或驱动连接/迁移检查失败时返回退出码 2，不会回退到容器临时 SQLite，也不会用 development 冒充上线。生产库方向依据最新 V0：秒悟已授权项目 `ucdte4eh02uv` 的 PostgreSQL；不再同时搭建另一套单机生产方案。SQLite 保留为本地开发存储。

## 已实现边界

| 层 | 限制 | 实测/说明 |
|---|---|---|
| Waitress 3.0.2 | 8 worker threads；64 connections/backlog | 配置检查与真实进程启动 |
| Waitress | 总请求头 8192 字节，请求体 32768 字节 | 实际 HTTP 返回 431 / 413 |
| Waitress | 非活动 channel 15 秒，清理周期 1 秒 | 配置锁定；不是整个业务执行的硬截止 |
| WSGI | Host 必须匹配 APP_ORIGIN | 伪造 Host/Forwarded Host 拒绝 |
| WSGI | JSON 对象，拒绝 NaN、错误媒体类型/长度 | 400/413/415 测试 |
| WSGI | 单演示账户全局每分钟 10 次登录尝试 | 429 + Retry-After；不信任 XFF 绕过 |
| WSGI | tick 同进程最多 1 个、模型解析最多 2 个 | 容量满立即 503，不排队占线程 |
| Application | cookie HttpOnly/SameSite/HTTPS Secure；写请求 Origin 校验 | 登录/归属/CSRF/tick 鉴权测试 |
| 数据事务 | 通知唯一键、版本/租约二次复核 | 原有确定性测试继续通过 |
| 错误输出 | 不返回 Python/供应商堆栈或口令 | Sentinel 脱敏测试 |

Waitress 不自动证明 TLS、慢速上传总时限、平台边界隔离。15 秒 channel_timeout 是无收发活动时限，不能描述成整个请求总耗时上限。取数/模型请求仍有各自超时；tick 预算可能延长至当前单项网络调用结束。

## 公网部署必须提供的外层证据

秒悟路径：确认平台 TLS URL、源容器网络隔离、请求体和请求头超时/大小、最大连接数、代理响应超时（覆盖有限 tick），以及平台是否原样传递合法 Host。没有这些事实前 R2-HTTP 的线上部分保持 OPEN。

若平台不能提供对应边界，需在容器/常驻环境增加明确的反向代理。下列 Nginx 样例仅是准备文件 `deploy/nginx.example.conf`，**没有在目标平台启动或通过 nginx -t**。不得把示例当生产证据。

## 复验

```sh
sh scripts/setup.sh
.venv/bin/python -m unittest discover -s tests -v
# 本地服务注入口令、session、tick环境变量；不要在命令行写实际值。
sh deploy/product-start.sh
# 未准备生产存储时预期拒绝启动：
APP_ENV=production APP_ORIGIN=https://example.invalid sh scripts/start.sh
```

41 项测试的当次输出见 `artifacts/round2-tests.txt`；后续新增测试以报告中的最终计数为准。真实公网 URL 与 target runtime readback 尚无。

依据：[Waitress 参数](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html)、[秒悟全栈平台契约](https://docs.meoo.com/features/cli)。

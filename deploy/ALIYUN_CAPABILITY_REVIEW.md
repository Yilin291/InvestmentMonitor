# 阿里云服务适配核查（2026-10-24；仅文档与代码核查）

结论：阿里云FC或ECS具备承载产品的基础能力；秒悟托管项目是否开放其配置入口仍未确认。没有访问用户阿里云账号、购买/开通资源、运行部署或改变当前生产方向。

## 秒悟说明中实际存在的路径

官方《MEOO CLI进阶：部署到你自己的阿里云账号》明确区分默认meoo deploy（秒悟托管CDN/FC）与meoo aliyun deploy（用户账号ECS/EIP及可选RDS/SLB，用户自行付费）。这是一条已有文档的替代部署路径，不能当作当前ucdte4eh02uv托管容器的Secret设置入口。文档还明确：自动数据库开通仅支持RDS MySQL，PostgreSQL需单独配置。本产品只有SQLite/Psycopg，不能直接套MySQL模板。
来源：https://docs.meoo.com/features/cli-aliyun

## 能力对应

- FC运行时配置：函数管理→函数列表→目标函数→配置→高级配置→环境变量，可经控制台/SDK/Serverless Devs设置；环境变量加密存储、实例初始化时解密注入。阿里云资源所有者具备此入口不等于秒悟用户可管理其托管函数。https://help.aliyun.com/zh/functioncompute/environment-variables
- FC HTTP服务：自定义容器支持HTTP Server，监听端口需与函数配置一致，默认9000；当前Waitress根入口具备该形式。https://help.aliyun.com/zh/functioncompute/custom-container/
- FC PostgreSQL：官方有Python访问RDS PostgreSQL方案，需匹配网络/VPC/白名单。RDS支持SSL/TLS，但既有秒悟数据库不是已确认可访问的用户RDS，不能据此认定其DSN/权限可用。https://help.aliyun.com/zh/functioncompute/access-the-rds-postgresql-database 、https://help.aliyun.com/zh/rds/apsaradb-rds-for-postgresql/configure-ssl-encryption-for-an-apsaradb-rds-for-postgresql-instance
- FC定时：原生定时触发器支持每n分钟执行；触发对象为函数，并非直接指定产品任意HTTP路径。适配方案为小型调度函数读取私密TICK_SECRET，POST正式tick接口，基于计划时隙生成幂等键。不能假定给现有Web函数加timer就能自动路由到/internal/monitor/tick。https://help.aliyun.com/zh/functioncompute/time-triggers
- ECS持久化：云数据盘提供持久存储；可使用现有SQLite实现，数据放发布目录外。独立cron/systemd timer在云主机执行，不依赖本机/网页。https://help.aliyun.com/zh/ecs/user-guide/create-and-use-a-data-disk 、https://help.aliyun.com/zh/ecs/user-guide/cron-scheduled-tasks
- 恢复：ECS支持快照/从快照创建新盘。数据库仍须一致性备份及隔离恢复验证；有快照功能不等于产品恢复通过。https://help.aliyun.com/zh/ecs/user-guide/snapshot-overview

## 对本项目的判断（工程判断，不是已完成验收）

1. 保留秒悟：若平台落实Secrets/原生DSN入口，可继续当前Psycopg代码，改动最少。工单000GJSKKC0尚待答复。
2. 若获准切换自有阿里云，单台Linux ECS + 持久云盘 + SQLite + HTTPS反向代理 + 独立定时器是本MVP更直接的备选；不必为10个任务强制购买RDS/SLB。已有领域/Store/页面可复用，但必须正式增加SQLite生产模式、校验持久路径与单实例约束，保留生产保护，不能APP_ENV=development绕过。
3. ECS+PostgreSQL或FC+RDS也可，配置与资源更多；现有秒悟库是否可复用仍需平台明确，不能承诺自动迁移。
4. 任何切换均涉及运行目标、资源费用及验收变更，当前仅提交评估，未执行。HTTPS域名/证书、地域、机器权限和费用需在具体方案确定后核对。
5. 无论哪条路，仍需真实事务、三次自动时隙、并发去重、重部署/恢复证据；服务器选择不会修复价格单位/来源时间/日历口径缺口。

# 题目要求与证据索引

表中 artifacts/ 与 validation/ 的精选证据位于本目录 evidence/ 下；checks/ 为本目录检查输出。文件SHA见交付包MANIFEST.json。通过、明确失败和隔离TEST分别标注。

| 题目要求 | 证据文件 | 证明范围 |
| --- | --- | --- |
| 自然语言转可修改规则 | artifacts/close-model-live-v1.json、close-model-assessment-v1.json | 正式云端模型真实日收盘、歧义及不支持语义检查 |
| 真实沪深数据及预览 | artifacts/sz-product-stage-v16.json、sz-provider-live-v1.json | 三只深市标的真实取数与产品预览，非全市场逐股验收 |
| 独立服务端调度 | validation/evidence/cloud_events_final_20261024T1144Z.json | 云ScheduledEvent、时隙键和HTTP结果 |
| 自动判断及持久化 | validation/evidence/cloud_business_final_20261024T1144Z.json、artifacts/sz-auto-readback-r3.json | 真实Run、Evidence、Notification及true/false |
| 去重与跨部署 | validation/CLOUD_SCHEDULER_ACCEPTANCE_20261024.md | 自动同键重放、跨版本，含明确失败说明 |
| 严格观察窗口的失败 | validation/evidence/cloud_assessment_strict_20261024T1144Z.json | passed=false保留；一次健康超时后恢复，不宣称零故障 |
| 三值、事件段、冷却 | artifacts/close-isolated-state-test-r2.json | 目标PG隔离TEST，最后回滚；不是实际市场穿越 |
| 暂停、编辑、租约与恢复 | artifacts/recovery-applied-test-r2.json、recovery-cloud-live.json、recovery-final-readback.json | 隔离状态机与真实时钟云恢复分别记录 |
| 持久化备份恢复 | artifacts/watchlist_restore_20261024_214139-assessment.json | 同实例15业务表内容一致；非完整灾备 |
| 鉴权与请求边界 | artifacts/on01-on02-live-v7-r2.json、deno-product-tick-v2.json | 真实登录限流、路由、双层tick凭证；后续本地回归补充 |
| AI使用与验证记录 | artifacts/AI_USAGE.md | AI职责、开发与验证方式、失败历史 |
| 当前独立本地检查 | checks/node-tests.txt | 2026-10-24提交整理时产品70项加Worker10项，共80项通过；不是80项云端测试 |
| 最近调度业务读回 | checks/cloud-readback.json | 只读数据库近期时隙，不手动发tick；独立云来源仍由上方ScheduledEvent日志证明 |

完整产品源码位于仓库根目录，独立调度位于 validation/cloudflare/；最终浏览器证据位于本目录 final-browser/。当前视频说明见 VIDEO.md，旧v7视频不属于最终演示。


最终交付补充：见[最终验收](FINAL_ACCEPTANCE.md)、checks/final-node-tests.txt、checks/final-rebuild-hashes.json及final-browser/。此前待前端发布的描述是历史准备状态。

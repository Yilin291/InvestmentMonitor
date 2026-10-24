# Deno正式链路测试说明

本地 `node --test tests/deno_product.test.mjs tests/deno_probe.test.mjs` 验证纯JS规则与HTTP handler；不是Deno运行时测试。目标运行时以 `artifacts/deno-product-*.json` 中实际调用为证据。Python55项仅参考，未把它们计为新实现通过。

- `product_cloud_smoke.cjs`：真实登录、日期任务预览/创建/启用/独立读回、Origin反例。会创建明确标记的真实未来日期任务。
- `product_tick_live.cjs`：批准后的平台anon JWT + X-Tick-Secret双层认证正反例。手动检查，不是自动调度。
- `product_cloud_transactions.cjs`：通过目标受限RPC验证同键/不同键竞争、重复完成、暂停/编辑失效和版本冲突。v1在原Bearer网关401失败；v2明确使用直接RPC只验事务，未冒充正式tick。
- `product_cloud_lease.cjs`：真实等待45秒租约到期，新执行恢复、旧执行失效、单条通知、暂停恢复后日历事件保持终态。非模拟时钟。
- `product_cloud_model.cjs`：真实云端模型三场景，数据库审计增量3、任务增量0；用`scripts/product_model_assertions.py`同一严格oracle核对。v1无关追问失败，v2修复后通过，两个证据均保留。
- `product_price_live.cjs`：真实扶摇HTTP响应，无损十进制字符串，预览/Observation/Evidence/Run读回；判断unknown、无通知，验收任务随后暂停。未声称盘中价格有效。
- `product_redeploy_readback.cjs`：部署v5后Task/RuleVersion/Run/Notification及已读状态保持。
- `product_backup_restore.py`：一致性单SQL快照，恢复至新隔离schema，外键/不可变触发器/identity序列随恢复建立，14表逐表一致。仅同实例隔离恢复，未验证跨实例灾备。不要将恢复目标当作生产数据源。

真实脚本涉及业务写入，须在明确授权下运行；证据文件拒绝覆盖历史。密钥从`.product-data/production-config.json`读取，不能作为命令参数或写入报告。独立自动调度由验证session执行，其日志与三个时隙是单独验收项。单次调用工具不是自动调度证明。

## ON-01/02专项

新增3项测试，当前Node共20项（13产品+7probe）。`on01-on02-offline-v3.txt`通过；两个handler共用外部限流模拟、存储失败拒绝登录、完整实际路由及嵌套负例；离线不计目标多实例证明。

`node scripts/online_review_check.cjs 新证据文件`对真实目标执行阈值与自然窗口恢复，会短暂占满demo账户登录配额。`node scripts/login_gate_concurrency_check.cjs`共享数据库并发检查，需上一窗口自然过期后执行，文件拒绝覆盖。不得通过清表/伪造时钟取得通过。线上v7-r2与共享并发证据已通过；v6和v7首次规范化诊断失败文件保留。

## 日收盘专项（当前v8）

最新命令：`node --test tests/deno_product.test.mjs tests/deno_probe.test.mjs tests/daily_close.test.mjs tests/close_model_oracle.test.mjs`，close-offline-v3.txt：33项通过。31项阶段结果v2保留。

- close_live_stage.cjs <新文件>：真实3标的搜索/预览、显式创建启用2个任务、删除历史只读；不发tick。已运行一次，不为重复证据再造任务。
- close_business_readback.cjs <新文件>：只读任务/Run/Notification，对照调度session日志，不自动宣称云调度通过。
- close_model_check.cjs <新文件>：真实日收盘all/any、歧义、盘中拒绝、账户拒绝五场景；严格oracle核对标的/条件/方向/阈值/CNY/明确冷却，审计+5、tasks+0。close_model_oracle.test.mjs覆盖错误方向/阈值和无关追问负例。close-model-live-v1.json及assessment通过。
- close_sample_replay.mjs：验证session真实样本的产品适配器复核，明确为回放，不计新在线执行。
- build_close_sql_test.py：生成目标数据库隔离TEST schema事务脚本；synthetic价格只在该schema中使用，最后ROLLBACK。close-isolated-state-test-r2.json通过；r1变量歧义失败历史保留。测试不是周末真实价格穿越。
- 007迁移先回滚演练再正式应用；008只读模型增量。数据库schema_version与新函数不能由本地单测替代。

验证脚本部分依赖本机已安装meoo CLI的绝对路径，换维护机器需安装官方CLI并调整工具路径；业务Deno函数本身无此依赖。恢复脚本尚需补充新缓存/收盘冲突表的策略与测试，旧14表证据不得外推。

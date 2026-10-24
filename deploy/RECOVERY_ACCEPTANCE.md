# 漏检与恢复专项（2026-10-24）

本轮只修既有监控服务，不增加雷达、行情或规则类型，不停用现有Cloudflare调度。

## 缺口与修复

1. 领取时ticks原先无run_id，进程中断后旧tick可能长期未完成。013在领取时事务内关联Run；重新领取过期租约时关闭关联旧tick并记录expired_lease_recovered，旧Run标为superseded。历史未关联tick不能可靠归属，不批量猜测补写。
2. finish补充请求键与Run关联复核；错误键不能把其他tick写成成功。租约、生命周期、generation与版本保护继续保留。
3. 日收盘连续unknown原先固定15分钟重试，没有连续失败计数。现在为15/30/60/60分钟（最大1小时），记录failure_count/failure_since/last_success及next_retry_at。unknown不重置价格事件段和冷却，恢复后清除故障计数；修改规则清除旧版本故障计数。
4. Run.detail新增retry、recovery、gap；当前版本last_evaluation同步返回。数据恢复记录previous_failures；检查迟到超过价格10分钟/日期60秒时记录计划检查空档，日期本身仍精确记录late_seconds。原因scheduled_check_delayed只表示迟到，不擅自断言是调度中断还是排队。没有补造漏检期间行情。

这些是重试/恢复记录，不保证外部服务永不失败，也不代表能从关停的全部基础设施中自行启动。页面既有下一检查、逾期提示与执行详情继续可用；新retry/recovery/gap的专门卡片文案交前端session，不在本轮替换其设计。

## 实际验证与证据

- 目标PG候选事务回滚：artifacts/recovery-candidate-test-r5.json。当前生产函数克隆隔离复验：recovery-applied-test-r2.json。两个都退出0。所有合成价格和故障时间都只在watchlist_recovery_test隔离事务，最终ROLLBACK。
- 场景：15/30/60/60退避、unknown保留事件状态、恢复持续true不重复提醒、故障与空档读回、过期租约收尾、错误请求键拒绝、暂停/编辑在途失效、迟到日期补发、重复finish幂等、已完成日期暂停恢复不再执行。
- 真实时钟专项：scripts/recovery_cloud_check.cjs。只手动领取一个明确TEST日期提醒后中断，必须等租约45秒自然到期，由现有cf-cron前缀正式请求产生新Run和唯一Notification；不手动执行恢复tick。结束标已读并软删除TEST任务，历史保留。
- 初始失败保留：平台多次cloud_not_enabled与只读成功矛盾；直接编译明确定位候选CASE表达式括号缺失，后续隔离断言因id变量遮蔽列误判，分别修正。不是数据库网络/TLS故障。最终动态迁移及状态机测试均通过后才应用。
- 70项Node回归：recovery-node-regression.txt。本次业务变更在SQL，Node通过不能替代上面的目标PG及自动恢复证据。

## 复现

```
python3 scripts/recovery_isolated_check.py /tmp/recovery-test.sql
meoo --json db query --project ucdte4eh02uv --file /tmp/recovery-test.sql
```

默认克隆当前函数，不重跑013。`--candidate`仅用于尚未应用013前的候选迁移回滚演练，正式库已应用后不要再用此参数。所有TEST数据通过tests/fixtures/recovery_price.sql明确标记。

真实日期专项需要演示账户还有一个任务名额且近期无其他到期任务；脚本会先检查。运行期间不要修改其TEST任务。此脚本会产生一个真实站内通知，不是生产市场触发证明。

备份恢复使用scripts/product_backup_restore.py的同实例新隔离schema，验证15张业务表。排除login_attempts/close_cache/llm_settings；Key需要重新配置。快照不是可运行的替代实例：切换前必须重建排除表、部署函数、清理租约并单独验收，不能把逐表相等当作跨实例灾备成功。


## 本轮完成读回

真实故障注入与云恢复：artifacts/recovery-cloud-live.json，退出0；函数v20于北京时间21:39:09.007发布，云端21:40:29.314完成，晚109.314秒，唯一通知、已读与终态验证通过，TEST软删保留历史。recovery-final-readback.json记录跨部署时间关系与HTTP200健康/登录/任务数9。手动恢复tick为0。

同实例15表恢复：artifacts/watchlist_restore_20261024_214139-assessment.json，退出0，15表内容一致，14外键恢复。源码版本与快照详见artifacts/recovery-release-manifest.json。

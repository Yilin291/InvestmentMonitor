# 沪深 A 股日收盘范围扩展（2026-10-24）

用户明确要求扩展现有核心功能。保持close_price_group/close_price、不复权CNY、滚动冷却、三值判断、显式启用、云Cron与站内通知；不是盘中、港美股或全市场交易能力。

## 身份、日历与缓存

元数据asset_type=a-share、currency=CNY且市场/代码/thscode一致：SH的6开头六位代码；SZ的0或3开头六位代码（包括主板/创业板）。这只是允许范围，仍须供应商元数据核验，不凭前缀编造股票。B股、指数、基金、北交所和港美股不纳入。

标的ID分别CN.SH.代码 / CN.SZ.代码；行情请求使用代码.SH / 代码.SZ，要求返回证券/1d/none三项精确一致。缓存键保留完整市场ID及上海抓取日期，跨任务复用但不跨证券或市场。原SH缓存与旧规则不迁移或改义。

expectedClose按instrument.market选择独立calendar来源。沪深2026常规休市日期本次公告核验一致，但实现分别记录来源，不假设未来始终一致；预期交易日还必须出现在真实交易日历中。未知年度、公告冲突、缺bar/停牌或临时停市覆盖不足保持unknown。日线日期仍不代表精确成交时间，收盘后15分钟等待/错误15分钟重试是产品策略，不是供应商SLA。只消费15:00收盘竞价结束后的已发布日线，不声称提供15:30盘后成交指标。

深交所依据：
- 年度通知：https://www.szse.cn/disclosure/notice/general/t20251222_618087.html
- 官方披露原文PDF（深证会〔2025〕481号）：https://dataclouds.cninfo.com.cn/sjother2/regulatory/2025/20251222/50b258f0d89b4076b459eb746a7e100d.pdf
- 2026交易规则第2.3节：https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf

网页直取超时，已实际读取官方披露PDF核对年度日期与深交所规则PDF核对收盘竞价时段；不是拿上交所公告替代深交所证据。上交所来源保留calendar.js原独立记录。

## 迁移与验收

010只对已部署public.watchlist_product_v1的三个已知片段作有前置断言的替换：标的导入范围、导入market值、缓存键合法性。不覆盖009读模型，不重跑007，不重建表，不改通知状态机。若函数片段与预期不符则中止，避免覆盖其他session修复。

首次回滚脚本错误引用watchlist.product_rpc函数名，退出1；修正为真实public.watchlist_product_v1后r2回滚演练通过，随后010正式应用。失败文件保留，不能归因为DB网络或TLS。

实际证据：
- artifacts/sz-provider-live-v1.json：7次串行真实请求；交易日历及000001.SZ/002594.SZ/300750.SZ的meta和日线。
- artifacts/sz-sample-assessment-v1.json：对上述真实样本重新执行新适配器，明确不是新线上请求。10月23日收盘分别11.2 / 81.42 / 237.6 CNY。
- artifacts/sz-tests-v2.txt：63项Node测试通过；包含深市范围、交易所独立来源、错误市场拒绝和缓存复用等TEST。
- artifacts/sz-migration-dryrun-r2.json / sz-migration-010.json：演练与正式增量退出0。
- 产品预览、自然语言、自动Run/Notification验收以后续sz-product-stage-v16.json和sz-auto-readback.json为准；不能仅由此文档声称已全部通过。


最终自动业务读回：artifacts/sz-auto-readback-r3.json退出0，两个不同正式自动slot，平安银行notify一条通知、宁德时代no_match零通知；sz-cache-auto-assessment.json证明两任务均复用预览缓存。首次等待及一次GET429失败历史保留。

# 日收盘数据交接（2026-10-24 18:42，北京时间）

适用范围：本轮验证的上交所 A 股。独立云调度/线上规则判断尚未完成，以下是新的真实供应商数据证据，不是产品 Run 或 Notification 验收。

## 真实样本

命令：`python3 validation/fuyao_close_probe.py`，从已有 0600 `.env.local` 在内存读取凭证，授权网络下串行 8 次请求，退出码 0。唯一证据文件 [`evidence/fuyao_close_three_20261024T183738060490+0800.json`](evidence/fuyao_close_three_20261024T183738060490+0800.json)。

| 股票 | 标准代码 | 不复权日收盘价（CNY） | 交易日 | 历史日线 request_id |
|---|---|---|---|---|
| 贵州茅台 | 600519.SH | 1335.0 | 2026-10-23 | 57444ca984ac4c43ac18f156dc060950 |
| 中国平安 | 601318.SH | 51.76 | 2026-10-23 | 18c2f977952b44daa65cbf73ab0658b7 |
| 招商银行 | 600036.SH | 41.77 | 2026-10-23 | 3764f6146af447fbac181c8b8def3ffe |

三次按真实中文名调用 `/api/meta/tickers/search?q=<name>&asset_type=a-share&limit=10`，逐一核对 `thscode/ticker/name/exchange=SH/currency=CNY/asset_type=a-share`。名称返回真实元数据，未做所有输入映射到茅台。meta request ID 均保存在 evidence。

三次历史请求均 `/api/a-share/prices/historical`，`interval=1d`、`adjust=none`、单一完整 `thscode`、14 天有界窗口（截至本日上海零点，不请求未来）。实际顶层返回 `thscode`、`interval`、`adjust`、`timestamp` 和 `item`；本轮三只股票的 symbol/adjust 回显都准确。每根 bar 提供 `date_ms/open_price/high_price/low_price/close_price/volume/turnover`，价格由 JSON 十进制 token 直接解析为 Python Decimal，再保存为字符串；没有经过二进制 float。

错误样例为**真实缺参请求**：meta search 刻意不传 q，HTTP 200 / `code=1001` / `Missing required parameter: q`，request ID `28e1732f2b7c4bb3ac1b89c4ebc4313c`。这不属于模拟行情或生产故障。

## 产品可以直接采用的契约

- 新版本规则明确 `close_price` / `1d` / `adjust=none` / `CNY`，不可静默复用旧 `last_price` 语义。日线 `date_ms` 是交易日日期键，不能写成精确成交时间。快照 timestamp 也不能填进成交时间。
- 本次元数据、日线及日历三方的代码/日期能关联；建议产品强制核验日线 `data.thscode` 与请求一致、`data.interval=1d`、`data.adjust=none`，缺少/冲突时 unknown，不猜值。金额从原始响应十进制文本进入比较，禁止先 `JSON.parse` 转 Number 再转字符串。
- 日历真实响应包含 2026-10-23；2026-10-24 为周六，上交所正常周内交易规则确认周六非正常交易日。结合两条证据，本次**最新已完成交易日为 2026-10-23**。该日有效日收盘可在周末继续比较，不按盘中秒级陈旧度判废。
- 今日任务候选：茅台 `close_price > 1334.0` 为 true，`close_price > 1336.0` 为 false，`close_price > 1335.0` 等值为 false。平安/招行对应阈值在 JSON 中。这里的数学期望尚不是线上结果，需由自动 slot 实际执行后读回。
- 价格新鲜度按**预期最近完成交易日**对齐，不依据 API 返回时刻。交易日收盘前排除当日日线；收盘后预期新日线未发布时返回 `expected_bar_not_ready`，按产品约定等待再取，不将上一日价冒充当日。停牌/缺 bar、日期回退、同日更正冲突、接口失败分别记录。
- 官方未给出确定发布 SLA/QPS，仍可采用产品等待策略：例如收盘后先等 5 分钟，未到位则 5 分钟有界退避；该数值由 Lead/产品确认，不称供应商保证。每分钟调度唤醒不等于每分钟向扶摇取数；按证券+交易日复用已验证日线。

## 日历依据与覆盖

已读官方[上交所2026年全年节假日安排](https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml)及[9月17日中秋国庆公告](https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml)。后者确认 10月1日至7日休市、10月8日起恢复，10月10日周六也休市；调休工作日不能自动认作证券交易日。

可以用上交所周内交易规则与该年度公告构建**预定日历**，再与供应商已发布日期交叉检查；不能把预定开市保证为个股必有成交。全年公告及常规规则不涵盖后来临时停市或个股停牌，应保留冲突/缺 bar 状态。超出已维护年度或交易所覆盖仍 unknown，禁止把 SH 的日历直接套给 SZ/BJ。

附源：[价格/元数据/日历官方字段](https://fuyao.aicubes.cn/llms-full.txt)，[上交所2026交易规则](https://www.sse.com.cn/lawandrules/sselawsrules2025/fund/trading/c/c_20260424_10817739.shtml)。

## 当前调度进度（19:07 更新）

Cloudflare OAuth、邮箱验证与子域初始化已完成。Worker 和每分钟 Cron 部署成功，两项 tick Secret 已安全注入；当前 probe 模式等首次自动网络探测，未启用正式 tick。详见 SCHEDULER_HANDOFF.md 与 cloudflare/README.md。生产健康在本机授权网络下返回 HTTP 200 / release=deno-product-v7；此前受限沙箱 DNS 失败不是产品公网故障。

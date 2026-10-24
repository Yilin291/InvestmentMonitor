> 历史分阶段实现记录。最终交付状态以根README和submission/FINAL_ACCEPTANCE.md为准；下文旧版本、待办与本地交付决定保留作审计，不覆盖最终交付。

# 自选股监控 MVP 实现报告

## 当前状态：漏检与恢复专项修复已上线（2026-10-24T21:42:29.514576+08:00）

URL https://ucdte4eh02uv.meoo.info；Deno **v20 / deno-close-v20 / verify_jwt=true**，static仍v12（2drTFgVY0vO7zq3fKQUqM4lZrUGMEn88）。013已应用，未改变价格口径、正式tick契约或现有云Cron。此段覆盖旧版本状态，不代表P1–P5整体签收。

- 修复：tick领取即关联Run；过期租约接管关闭旧Run/tick并留下恢复原因；finish复核请求键。日收盘连续unknown按15/30/60/60分钟退避，保留事件段和冷却；有效恢复清零故障计数并记录恢复、漏检空档；编辑清除旧版本故障计数。新gap/retry/recovery通过任务读模型返回，前端设计契约已追加，未改其他session页面。
- 真实自动恢复退出0：artifacts/recovery-cloud-live.json。TEST日期计划21:38:40，21:38:43手动领取后中断（只注入故障，不手动tick）；45秒租约自然到期。函数v20于**21:39:09.007**发布；现有云slot `cf-cron:ucdte4eh02uv:29880820` 于21:40:28.502领取、**21:40:29.314**完成。晚109.314秒，gap明确记录。旧Run superseded、旧tick关闭、迟到旧finish无效、通知恰好1条、重复已读持久化、已完成一次性提醒暂停/恢复仍next_run=null。测试任务已软删留史，可用任务恢复9个。跨部署时间关联见recovery-final-readback.json；健康/登录/任务读回均200。云来源以既有调度证据与cf键关联，不把服务读模型前缀单独当自动证明。
- 目标PG退出0：候选迁移回滚recovery-candidate-test-r5.json；正式013 recovery-migration-013.json；实际函数隔离复验recovery-applied-test-r2.json。覆盖退避、unknown保留状态、恢复不重复、gap读回、租约/错键/暂停/编辑隔离、迟到补发、超过24小时missed、claim/finish幂等、持租约不重复领取、完成后不重排。TEST价格仅隔离schema事务，最终ROLLBACK；不是本轮线上真实行情穿越或新的并发压力测试。
- 同实例隔离备份恢复退出0：watchlist_restore_20261024_214139-assessment.json，15表逐表内容hash相等、14外键与不可变版本触发器恢复。未覆盖当前产品数据；排除登录限流、缓存和加密模型设置，后者恢复需重填Key。快照不是可运行替代实例，未验收跨实例灾备。
- 操作命令/退出码：`node --test tests/*.test.mjs` 0（70/70，recovery-node-regression.txt）；`meoo --json db query --project ucdte4eh02uv --file deploy/migrations/013_monitor_recovery.sql` 0；`meoo --json fn deploy watchlist-api --project ucdte4eh02uv` 0（recovery-function-v20.json）；`node scripts/recovery_cloud_check.cjs artifacts/recovery-cloud-live.json` 0；`python3 scripts/product_backup_restore.py` 0。源码微调只使验收脚本从PATH或MEOO_CLI查找CLI，不影响已发布业务代码。
- 失败保留：初期平台cloud_not_enabled与同项目成功查询不一致；候选SQL CASE括号错误、隔离断言列名遮蔽已修正并重跑通过。详见专项文档，不归因为DB网络/TLS失败。
- 改动清单：013、core健康版本、recovery_isolated_check.py、recovery_cloud_check.cjs、TEST SQL fixture、备份恢复边界说明、README/专项验收/前端交接/AI记录。源码提交与SHA见artifacts/recovery-release-manifest.json，本地bundle r10；不推远端。
- 未执行：跨实例灾备、真实供应商长故障恢复、停机期间市场穿越重建、前端专门恢复卡片、新演示视频、本轮新的并发压测。当前专项无待用户授权阻塞；若扩大到跨实例灾备，唯一前置依赖是Lead指定隔离恢复目标与切换验收范围。当前恢复不补造历史行情，不承诺分钟级准时。

## 当前状态：自填模型协议URL与自动回退上线（2026-10-24T20:48:22.877159+08:00）

本段覆盖旧固定提供商与“不回退”语义。用户明确要求改为自填OpenAI/Anthropic兼容URL，并在连接失败时提示后继续使用内置模型。现Deno v19 READY / deno-close-v19 / JWT保持，static v12（artifactId 2drTFgVY0vO7zq3fKQUqM4lZrUGMEn88），URL https://ucdte4eh02uv.meoo.info；012增量已应用，不修改任务、tick或云Cron。

- 实现：协议选择+API URL+模型+Key，基础地址/完整接口规范化；OpenAI Chat及Anthropic Messages真实适配。保存测试失败保留加密的待修正配置并使用内置；运行失败请求内回退一次，结果model_warning明确告知，内置失败则报错。更换URL/协议不复用旧Key；密文AAD绑定URL，兼容旧配置。
- 验证与退出码：70项Node回归0（llm-url-tests-v1.txt）；前端构建0（llm-url-build-v1.txt）；012回滚演练0、正式迁移0（llm-url-migration-dryrun.json / llm-url-migration-012.json）；函数部署0、静态部署0；git diff检查和已知凭证扫描见本轮文件。
- 实际线上：node scripts/llm_url_live.cjs artifacts/llm-url-live-v19.json 退出0。自填DeepSeek完整URL测试/保存/另请求读回/真实解析通过；错误模型保存后mode=builtin、warning可见，真实内置解析成功。另用明确TEST无效模型短暂启用来测试运行中真实HTTP失败，返回内置草稿且model_warning存在。这是受控故障注入，不是自然供应商故障，未注入行情。结束已删除测试配置恢复内置；任务9→9，手动tick0。
- 浏览器：llm-url-browser.txt/png记录两种协议、自填URL、Anthropic示例、默认内置及回退说明；未输入或截取真实Key。设计session交接已追加覆盖上一版契约。
- 改动清单：llm.js协议/URL/DNS预检/有界响应/回退，core.js统一模型transport与提示，ModelSettings和src.jsx显示配置及解析warning；012迁移、llm_url_live.cjs、7项模型设置测试；README、LLM_SETTINGS、AI_USAGE和交接文档同步。
- 仍未执行：Anthropic真实供应商账户调用（缺用户自填Key，只离线协议/错误路径通过）；新设置页视频未重录；不扩大宣称全P1–P5验收。应用层DNS预检不是网络层IP固定，不声称消除DNS重绑定；只使用公网HTTPS443并拒绝重定向/内网响应。当前无需阻塞用户使用，下一验证依赖仅用户自选服务的有效URL/Key。
- 源码提交与逐文件SHA见artifacts/llm-url-release-manifest.json，本地bundle r9。平台static commitId是上传时旧HEAD，不作为本轮源码快照依据。历史失败和早期状态保留供审查。

## 当前状态：模型设置页面上线（2026-10-24T20:40:14.762363+08:00）

本段覆盖下方历史版本状态。URL https://ucdte4eh02uv.meoo.info；Deno v18 READY / deno-close-v18 / verify_jwt=true，static v11（artifactId 6EKN9l618mrImTilRmnHO9zU9E56UxRv）。011模型配置迁移已应用，原日收盘、日期任务、双层tick和云Cron契约不变。不代表P1–P5全部签收。

- 用户要求已实现：页头“模型设置”可配置DeepSeek或百炼北京提供商、模型和API Key，真实测试成功后保存并影响标的提取/规则解析/推荐输入；默认明确告知内置DeepSeek，支持恢复内置。固定官方地址，失败不静默回退。共享demo作用范围在页面说明。
- 密钥：AES-GCM服务端加密，SESSION_SECRET域隔离派生，AAD绑定账户/提供商/模型；数据库RPC仅service_role可调用，API不返回密钥或密文。轮换SESSION_SECRET需重填；业务备份不含自定义配置，恢复后重填，见deploy/LLM_SETTINGS.md。
- 实际操作/退出码：67项Node回归0（artifacts/llm-settings-tests-v3.txt）；Vite构建0（llm-settings-build-v2.txt）；SQL回滚演练首次1（RETURNING别名错误），修正r2为0；正式011为0；函数v17/v18部署0；静态首次1（CLI互斥选项，未发布），移除不兼容项后static11发布0。
- 真实复验：v17首轮JSON连接探测失败，未保存（llm-settings-live-v17.json，退出1）。本机两种思考设置均成功，不能将首轮失败断言为已定位的供应商问题（llm-settings-probe-diagnosis.json）。最小探测改为明确非思考模式并限制128token，v18完整链路退出0（llm-settings-live-v18.json）：测试不落库→保存→另请求读回→真实草稿→错误模型保存502且旧配置保留→恢复内置。任务数9→9，手动tick0。
- 浏览器：真实页面显示默认内置说明；百炼选择会填qwen-plus，未填Key测试返回明确错误且当前生效仍内置。证据llm-settings-browser.txt/png。未在浏览器输入或截取真实密钥。
- 改动清单：新增llm.js、011_llm_settings.sql、ModelSettings.jsx、llm_settings.test.mjs、llm_settings_live.cjs、LLM_SETTINGS.md；core/discovery/suggestions统一配置路由；src.jsx增加入口；旧测试环境桩改为按变量名返回，避免把所有新配置变量当TEST密钥；README/AI_USAGE/前端交接同步。
- 未执行与下一验证依赖：百炼真实账户调用尚未验证，需要用户在页面输入北京Key并测试；离线路由和失败保护已验证。未重录本次设置页视频，未重新完成全业务备份恢复/整体验收；不以本轮67项测试代替这些交付。无需Lead再决定默认模型；保持内置，用户主动切换。源码提交、文件SHA和bundle见artifacts/llm-settings-release-manifest.json；平台static显示的是发布时旧HEAD，仅作平台元数据，实际源快照以manifest为准。

## 沪深日收盘扩展已完成本轮验证（2026-10-24T20:21:20.883403+08:00）

用户要求拓宽核心范围，现支持经真实元数据核验的沪深A股（深市主板及创业板），保持日收盘/不复权/CNY、未知降级、冷却去重、指定时间提醒与原云Cron。Deno v16 READY、static v10 artifactId=n9779QcqldIODZB1gh0yBT3p0Ybr6j35；010已应用，不重跑历史迁移、不覆盖009解释读模型。

- 真实供应商7次串行只读请求退出0：sz-provider-live-v1.json。深市3标的000001.SZ/002594.SZ/300750.SZ，10月23日收盘11.2/81.42/237.6；日线字段thscode/interval/adjust严格匹配。sz-sample-assessment-v1.json为真实样本复核，非新请求。
- 日历按market选择SH/SZ官方来源，深市年度公告及交易规则PDF已核对；预期日仍必须正向出现在真实日历中，临时停市/缺bar未知不推断。依据deploy/SH_SZ_SCOPE.md。
- 63项离线测试通过sz-tests-v2.txt，构建sz-build-v1.txt退出0；覆盖深市范围、错误证券身份、独立日历、同标的缓存复用、旧SH回归。010目标回滚演练r2与正式应用退出0。首次演练错函数名退出1保留，不是网络/TLS失败。
- 产品真实3标的预览、重复请求缓存复用、宁德时代自然语言草稿、SH旧任务预览均通过：sz-product-stage-v16.json，退出0；明确启用2项演示。未手动tick。
- 自动业务读回通过sz-auto-readback-r3.json：平安银行task833fdcb0dbdf4f219f35a205d20cd84d由slot cf-cron:ucdte4eh02uv:29880739处理，Run1/notify/Notification1；宁德时代task52327cf88cdc4e6188f23cadd7dbecd4由slot ...740处理，Run1/no_match/Notification0。预览与自动执行provider request_id/fetched_at相同，真实缓存复用见sz-cache-auto-assessment.json。
- 首次读回时第二项尚未执行，断言退出1；r2遇GET429退出1；r3有界只读退避后通过，历史文件全部保留。两任务未注入模拟行情，周末结果不冒称市场多次穿越。日后有效false→true仍沿用既有经隔离TEST验证的状态机。
- 前端接口结构未改，范围文字与设计交接已同步沪深；market字段显示SH/SZ，不拼死.SH。设计session继续只负责展示，本session统一发布。当前精确源版本与包见artifacts/sz-release-manifest.json。
- 本轮没有扩展B股/北交所/港美股/盘中实时，也没有完成新的30分钟全窗口或完整灾备验收。两项演示占用2任务名额，未删除用户任务，后续可在页面暂停或删除。

## 当前增量：任务解释与独立前端交接（2026-10-24T20:06:20.267733+08:00）

任务卡和详情现直接展示当前规则版本的真实价格/日期/条件、满足或未满足、已提醒/同事件段去重/冷却/数据不足原因、检查来源与下次计划、到期延迟及云请求近期完成状态；提供只读刷新。修改版本后不展示旧版本结果为当前判断，unknown不回退旧价格；暂停/草稿/删除显示未安排，日历完成显示无下次。调度状态使用服务端时间与已认证约定请求键，3分钟告警为产品策略，不宣称历史零故障。

- 只读迁移009目标库回滚演练通过并正式应用，均退出0：artifacts/task-status-migration-dryrun.json、task-status-migration-009.json；未改变业务规则、执行器或通知状态。
- 前端static v9，artifactId HKg5SwMeLIoO35eVlFAmnaFK4fTs27qj；Deno仍v15，JWT保持。构建退出0 task-status-build-v2.txt。59项Node测试通过 task-status-tests-v1.txt，包含冷却/unknown/旧版本/暂停/日历完成/手动请求不能代替云记录/超时警示等明确TEST。
- 真实线上只读3场景退出0：task-status-live.json；茅台notify、平安no_match、日期完成，证据与云请求关联准确，未调用tick或修改任务。浏览器卡片与详情实际核对通过 task-status-browser-dashboard/detail.{txt,png}，页面已关闭。未把TEST冷却等伪称真实市场穿越。
- 前端展示组件frontend/components/TaskStatus.jsx与纯语义适配frontend/task-status.mjs分离。独立session交接deploy/FRONTEND_SESSION_HANDOFF.md，启动prompt deploy/FRONTEND_SESSION_PROMPT.md；建议独立工作树，设计不改服务端/调度/DB，不自行发布。用户尚未要求创建新session，因此仅准备资料。基线与源码SHA见artifacts/task-status-release.json。
- 最新验证session报告已确认云端四任务、跨v11部署和同键去重；30分钟31slot中一次health超时，随后恢复，严格零失败判定未通过。此前“无自动执行”段落属于历史。新未来提醒准时性、完整灾备重建、最终新视频仍未整体验收；P1–P5不因此整体签收。

## 可点击模型推荐输入上线：2026-10-24T19:47:22.780065+08:00

用户新增要求已实现：不符合规则时DeepSeek flash生成可编辑推荐，按钮点击只回填自然语言输入并清除旧解析/试运行，不创建/启用任务。缺失阈值、标的或日期用【占位内容】；未补齐时服务端确定性拦截。查无标的不替换为其他股票，盘中改义必须明确确认。纯不支持需求或推荐不可用时保留追问，允许手工修正。

- 当前Deno v15 READY / deno-close-v15，static v8，artifactId rXEcPKlqYlV5EblNJtR4ZYr2yNBhgNLI。JWT、tick和DB schema未变。
- 51项离线测试通过：artifacts/input-suggestions-tests-v5.txt；构建退出0：input-suggestions-build-v1.txt。
- 真实API复验退出0：input-suggestions-live-v15.json；缺阈值/盘中/查无标的3场景得到推荐，未补齐拦截，补齐100元后ready且lt100，盘中显式转换后保留42元，tasks增量0。
- 真实浏览器点击回填→补齐100→重新生成草稿成功，未保存/启用，测试页已关闭：input-suggestions-ui-v15-before.txt、filled.txt、roundtrip.txt；旧占位符拦截证据input-suggestions-ui-placeholder-block.txt。
- 历史v13真实复验失败1（推荐被校验拒绝），v14基础断言通过但人工复核发现混合日期/盘中词，已修复为v15，历史未覆盖。v15通过才作为当前结论。
- 发布源SHA及本地快照见artifacts/input-suggestions-source-v15.json；生产整体签收和30分钟调度结论仍由Lead/验证session独立判定，不以本轮推荐功能测试替代。

## 最新增量：自然语言标的自动核验（2026-10-24 19:42）

用户本轮要求将未入库标的通过项目数据源核验后扩充数据库；已发布Deno v12/static v7，健康deno-close-v12。复用既有扶摇meta接口与受限instrument_import，无数据库迁移。模型仅提取原文名称/代码；元数据精确唯一匹配、SH/A股/CNY范围校验及入库读回后才能生成草稿；查无、歧义、失败不放行，模型草稿不得替换已解析标的。页面合并新核验标的供采用草稿。

44项离线测试通过、构建通过；三次真实复验通过：长江电力核验入库并生成lt100/CNY/86400草稿；字节跳动查无支持标的不生成；长江电力模糊阈值继续追问。任务数前后不变，未启用监控或手动tick。证据artifacts/instrument-discovery-live-v12.json，命令node scripts/instrument_discovery_live.cjs artifacts/instrument-discovery-live-v12.json退出0。失败/别名/多标的/非支持市场/模型幻觉/无读回离线覆盖，见instrument-discovery-tests-v2.txt。

下方v10及调度待接通属于历史；v11跨部署读回见HANDOFF，正式自动时隙已由验证session产生，连续30分钟最终结论仍以验证报告为准。本轮仅验收标的发现与草稿，不新增调度完成声明。源码/部署对应见artifacts/instrument-discovery-source-v12.json；r4包保留为之前快照。

## 当前交付增量：Deno v10 / static v6，本地仓库交付（2026-10-24 19:13 北京时间）

以下覆盖后文旧版本及“无Git提交/正在整理”描述；历史证据不删除。正式URL https://ucdte4eh02uv.meoo.info 。函数v10 READY、verify_jwt=true；static v6 artifactId=YJr6lTemuxb6BSBCVlgslG2kvdAbux8x。静态发布平台commitId仍记录旧HEAD 5065a553，发布时工作区含新代码，不能将该元数据当作完整源码对应；本轮r4清单以逐文件SHA和实际构建dist建立对应。

- 生产操作：`meoo --json fn deploy watchlist-api --project ucdte4eh02uv`、既有静态入口发布均退出0，证据close-function-v10.json、close-static-v6.json；函数发布前SHA见close-function-v10-source.json。
- 实际复验：`node scripts/close_basis_check.cjs artifacts/close-basis-live-v10.json`退出0，健康v10、三只股票实际日收盘预览均通过（茅台true、平安false、招商true）；强制证券/1d/none回显、trade_date=2026-10-23，source_time=null。此脚本不调用tick，不能替代自动执行。
- 日历：已接上交所2026年度休市表并要求供应商正向日历共同验证；非2026、缺预期日或冲突均unknown。实际样本复核close-calendar-contract-v2.json；Node 37项通过close-offline-v6.txt，构建close-build-v6.txt退出0。
- UI：真实删除历史只读验证close-ui-deleted-history-v4.{txt,png}；UTC日期编辑转换上海并保留毫秒close-ui-timezone-v4.txt。新版缺失结果不会误显示false，原因中文化。
- 用户选择先交付本地Git仓库和可克隆bundle，不创建/推送远端。r4交付说明deploy/LOCAL_SOURCE_DELIVERY.md、版本/源码SHA清单artifacts/close-release-manifest-r4.json；已保存r3历史快照。
- 唯一下一集成阻塞：独立调度尚缺正式tick自动业务读回；验证session19:03已部署Cloudflare探测Cron，旧邮箱/OAuth阻塞已解除。三次自动slot、至少30分钟跨重部署连续运行、带收盘记录的恢复与最终自动闭环视频均未验收。P1–P5仍未整体签收。

## 当前状态：日收盘候选版本已上线（2026-10-24 18:58 北京时间）

**正式URL：https://ucdte4eh02uv.meoo.info ，watchlist-api v8 READY（release=deno-close-v8，verify_jwt=true），static v4，artifactId UwB4tKwFJpC7PBvgs1ymr0A9lDv9NNbM。P1–P5仍未整体签收。** 用户本轮明确批准日收盘口径、18:00后007迁移及配套发布；自动审批第一次因冻结范围冲突拒绝后，取得这项明确批准才继续，未绕过。

下方18:12及更早段落均为历史：旧“价格执行器尚未实现/只能unknown”“只有1只标的”“v7/static2”不再是当前状态。**当前已实现价格有效分支，但生产自动执行与真实通知仍未通过，不能以预览代替。** 旧盘中last_price规则继续保持原义和unknown，没有被静默迁移。

### 本轮实际改动、验证与证据

| 交付项 | 实际结果 | 证据路径（artifacts/）/退出码 |
|---|---|---|
| P-A / ON-03 日收盘执行器 | 新增close_price_group/close_price/daily_close，真实历史1d/none，BigInt十进制比较、三值AND/OR；受限SQL事务内复核租约/版本/生命周期并推进事件段/冷却，持久化日线日期/来源/口径 | functions/watchlist-api/close.js、007_daily_close.sql；close-offline-v3.txt，33项Node通过，0 |
| 生产迁移 | 007先目标库回滚演练，再明确获批正式应用；008补读模型和日级调度逾期阈值，不修改旧RuleVersion | close-migration-dryrun.json、close-migration-007.json、close-migration-008.json，0 |
| 目标DB状态机 | 独立TEST schema验证首true、同bar、新日连续true、false→true、冷却、unknown、日期回退、同日更正、重复键、暂停在途、删除历史，最终ROLLBACK | close-isolated-state-test-r2.json，0；r1脚本变量歧义失败1保留，不是业务代码失败 |
| 真实3标的接入 | 茅台/平安/招商搜索及Instrument写回；真实10月23日收盘1335.0/51.76/41.77。正式预览true/false、source_time仍null且trade_date独立 | close-live-stage-v8.json，0；验证session原样本产品复核另见close-three-sample-replay.json，明确是回放 |
| P-B / ON-04 删除历史 | 既有两条通知所属已删任务详情/runs返回200，resume409；保留归属校验，页面隐藏编辑/删除/恢复操作 | close-live-stage-v8.json，0 |
| P-B / ON-05 时区 | Z/+08:00/其他偏移转换上海编辑值，保留秒/毫秒；不再字符串截断当时区转换 | close-offline-v2/v3.txt，通过；frontend/time.mjs |
| 模型一致性 | 真正all/any正常场景逐字段匹配，歧义相关追问、盘中拒绝改义、账户拒绝均通过；audit+5/tasks+0。oracle负例覆盖错方向/阈值/币种/冷却/无关追问 | close-model-live-v1.json、close-model-assessment-v1.json，0 |
| UI自然语言链路 | 搜索招商→输入日收盘lt42.77/滚动86400秒→模型草稿→采用→真实预览41.77且trade_date=2026-10-23→弹框明确启用→页面关闭 | close-ui-preview-v8.{txt,png}、close-ui-enabled-v8.{txt,png}，CUA完成；尚无执行/通知 |
| 发布与构建 | 函数v8、static v3→v4；最终构建通过，有bundle大小提示无失败 | close-function-v8.json、close-static-v4.json、close-build-v3.txt，0 |

主要命令：`node --test tests/deno_product.test.mjs tests/deno_probe.test.mjs tests/daily_close.test.mjs tests/close_model_oracle.test.mjs`；`npm run build`；`meoo --json db query --project ucdte4eh02uv --file deploy/migrations/007_daily_close.sql`（已应用，勿重跑）；008同类命令；`meoo --json fn deploy watchlist-api --project ucdte4eh02uv`；静态发布`meoo --json deploy --project ucdte4eh02uv --runtime static --skip-build --skip-push --force`；上述真实脚本见scripts/close_*.cjs/mjs。退出码0只代表对应验证范围，不代表完整自动闭环。

### 独立调度与未完成项

用户已明确批准验证session使用**已有Cloudflare账户免费额度**部署一个Cron触发器，不授权新购资源；授权、双层tick契约、任务ID及网络执行约定已追加deploy/HANDOFF.md。产品没有自行创建第二套调度器或手动替代自动slot。

18:51只读核对close-business-readback-1851.json（退出0）：3个日收盘任务与原日期任务Run/Notification均0。日收盘任务：67c22ac8c03742a9939a6f4fa98c278b（茅台lt1336.0，预览true）、546597e801114893915b4fa98c978d0a（平安lt50.76，预览false）、57a30a61beea43ee85e48e748c12f314（UI招商lt42.77，预览true）。旧日期48bf...仍等待首次自动调用。**下一集成阻塞：验证session完成Cloudflare账户接入、触发器发布与执行位置实测。** 收到slot后产品核对真实Run/Evidence/Notification及重复通知；至少30分钟并跨产品重部署的验收尚未执行。

日历范围诚实限定：仅正向确认预期交易日并依据上交所周末规则跳过周末，不把缺工作日当节假日；完整年度休市/临时停市覆盖仍未接入，覆盖不明unknown。15分钟等待/退避是产品策略，不是供应商SLA。每tick最多1任务，日期优先，不承诺10任务每5分钟。详细契约deploy/DAILY_CLOSE_CONTRACT.md。

P-C：README、运行说明、模型提示词、JSON、数据库和页面已对齐日收盘；正在整理本地codex/daily-close-mvp交付分支，准确提交与源码SHA见artifacts/close-release-manifest-r3.json。远端归属/可见性未确认，不擅自公开；源码ZIP只补充快照。最终自动闭环视频尚未录制；r2为历史v7采样视频，不能作为当前日收盘/云调度通过证明。旧14表恢复未覆盖新缓存/冲突表，需要补验；跨实例灾备仍未验收。

未改validation/、VALIDATION_REPORT.md或docs/lead/；无新账户、付费资源或密钥入库。已有ON-01/02保护保持。Lead仍负责设计及整体签收。

---
以下为历史阶段记录。

## 当前状态：ON-01 / ON-02 修复与交付（2026-10-24 18:12 北京时间）

**产品 https://ucdte4eh02uv.meoo.info 可访问，watchlist-api v7 READY，健康200/release=deno-product-v7；static v2未变。P1–P5尚未整体签收。** 下方17:44及更早段落均为历史，旧v5/17项测试/视频未录制等状态由本节替代。18:00后仅做既有范围复验、录制和交付，无新增功能。

### 审查逐项回应及证据

| 项目 | 实际实现与复验 | 证据（均在artifacts/）及退出码 |
|---|---|---|
| ON-01 登录限流 | 新增006迁移：所有实例共用PostgreSQL滚动60秒/10次计数，事务级锁串行竞争；成功和失败登录都计数。阈值后429/Retry-After且无Cookie；数据库失败503，不绕过保护 | on01-login-migration.json，迁移命令退出0；on01-on02-live-v7-r2.json，真实10次错口令401、第11次429、窗口内正确口令429，真实等待55秒后正确口令200，退出0 |
| ON-01 共享并发与权限 | 12个独立HTTP请求，两两并发，共享数据库恰好10允许/2拒绝；匿名RPC被42501拒绝。此证据不声称观测到不同Edge实例ID | on01-shared-gate-concurrency.json，退出0 |
| ON-02 精确路由 | 删除indexOf前缀截断；按实际网关传入的完整路径及固定ID规则匹配。嵌套/任意前缀、近似后缀404；合法健康200 | on02-actual-ingress.json、on01-on02-live-v7-r2.json，退出0 |
| 离线回归 | 20项Node测试通过（13产品、7探针），覆盖共享限流、故障关闭及路由负例；不是20项Deno运行时测试 | on01-on02-offline-v3.txt，退出0 |
| 部署 | 产品v7，verify_jwt=true；前端仍static v2，artifactId I1cu9ALl7JcP0Gn9p2O3rBmyb66dcvwy。未重新构建未变前端 | on01-on02-function-deploy-v7.json，部署退出0 |
| 自动执行业务核对 | 18:09只读核对UI任务48bf9e848e5a4b29ba47241a4636ab3e：enabled、overdue，Run=0、Notification=0、到期后tick=0；本轮未发送手动tick | on-review-scheduler-business-readback.json，命令退出0，但自动调度验收未通过 |
| 演示视频 | 161.4秒、H264、1440×900；48张真实浏览器采样按观察时长播放，明确标注采样实录。展示已完成日期功能、持久化通知和已读状态，以及尚未通过的价格判断/自动调度；非全帧录屏 | demo-video-manifest-r2.json、demo-video-render.log；生成与ffprobe校验退出0，另解码95秒画面人工核对 |

实际命令：`meoo --json db query --project ucdte4eh02uv --file deploy/migrations/006_login_rate_limit.sql`（已应用一次，不重复）；`meoo --json fn deploy watchlist-api --project ucdte4eh02uv`；`node --test tests/deno_product.test.mjs tests/deno_probe.test.mjs`；`node scripts/online_review_check.cjs artifacts/on01-on02-live-v7-r2.json`；`node scripts/login_gate_concurrency_check.cjs`；`node scripts/read_scheduler_business.cjs`；`.venv/bin/python scripts/build_demo_video.py`。复跑取新证据文件，避免覆盖历史；联网命令在已授权网络执行上下文运行。

保留失败证据：v6部署命令虽退出0，但因误判网关保留前缀而健康404；受保护探针实测网关传入/api/health后修正为v7。v7初次路由复验将网关规范化误判为应404，脚本退出1；修订断言区分网关与应用后r2退出0。外部//api/health及/api/%68ealth由平台规范化后返回同一健康200，handler看不到原始字节；不宣称这两种原始表示被网关拒绝。相关失败文件on01-on02-live-v6.json、on01-on02-live-v7.json均保留。

### 交付与下一阻塞

源码包 `artifacts/watchlist-product-20261024-r2.zip`，版本及逐文件SHA清单 `artifacts/deno-product-release-manifest-r2.json`；扫描结果 `artifacts/deno-product-secret-scan-r2.json`。无Git提交，源码快照为交付依据，r1包保留历史。运行说明deploy/RUNBOOK.md，视频artifacts/watchlist-demo-20261024-r2.mp4，实际脚本deploy/DEMO_SCRIPT.md。AI记录、测试说明、README及共享HANDOFF已同步；没有改动validation/、VALIDATION_REPORT.md或docs/lead/。

**唯一下一集成阻塞：独立调度尚无三个正式自动时隙的成功证据。** 已在HANDOFF交接v7、双层凭证契约及只读核对命令；验证session17:50记录DNS失败，产品当前授权联网环境可访问，不能据此推断产品不在线，也不能擅自建立另一生产环境。待其提供调度执行位置/停用方式和时隙请求ID后核对Run/Evidence/Notification及去重。既有手动并发/唯一通知证据不替代自动执行去重验收。

价格判断仍是独立未通过项：source_time缺失、单位/日历/时效口径未齐，保持unknown，真实报价不是有效触发证明。视频中日期执行为手动功能验收，自动任务仍逾期无执行；录制页面18:05关闭。跨实例灾备、完整价格主链路、全部AC及P1–P5整体仍未签收；同实例14业务表恢复证据的范围没有扩大到新登录计数表或完整实例恢复。

---
以下为历史阶段记录。

## 当前状态：正式业务链路已上线（2026-10-24 17:44 北京时间）

**产品URL：https://ucdte4eh02uv.meoo.info 。P1–P5尚未整体签收。** 已从探针推进到真实React页面、Deno业务API和既有PostgreSQL业务数据。当前线上static v2，artifactId `I1cu9ALl7JcP0Gn9p2O3rBmyb66dcvwy`；watchlist-api v5 READY，verify_jwt=true。健康实际200且release=deno-product-v5。代码未创建Git提交；源码/产物SHA清单 `artifacts/deno-product-release-manifest.json`，源码交付包 `artifacts/watchlist-product-20261024-r1.zip`。不是原FC镜像发布成功，也不再等待DSN/Psycopg路径。

### 本轮改动与实际操作

- 用户明确要求实现正式业务链路，随后明确批准双层tick凭证方案。React沿用同源HttpOnly/Secure/SameSite=Strict Cookie，API前缀 `/sb-api/functions/v1/watchlist-api`；实际认证路径保持 `/api/v1/auth/*`。源码在functions/watchlist-api/，原Python保留参考，不运行第二套生产执行器。
- 增量003固定产品RPC、004真实核验标的导入、005真实Observation/Evidence保存均已应用，`meoo --json db query --project ucdte4eh02uv --file ...` 退出0。没有重跑001/002、重置业务状态或对anon开放业务RPC。SECURITY DEFINER固定search_path、限定schema、service_role执行；领取和完成分别事务，完成按DB时间/token/version/generation/lifecycle再次校验。
- `meoo --json fn deploy watchlist-api --project ucdte4eh02uv` v1–v5退出0，阶段修复均有对应源变更；static v1/v2发布退出0。根npm build现构建同源静态产物；原npm start仍是Python参考，当前静态部署不调用它。frontend构建退出0，有bundle大小提示，无构建失败。
- 真实网关不接受随机TICK_SECRET作为Authorization平台JWT，原契约三请求均401；补apikey仍401。证据deno-product-transactions-v1.json、deno-tick-gateway-compat.json。用户批准后：Authorization使用现有项目anon JWT，X-Tick-Secret使用原业务密钥；两项均由产品检查，平台verify_jwt未关闭。业务密钥不变、不打印、不进入前端。新契约完整写入deploy/HANDOFF.md。
- 浏览器真实登录、创建未来日期、预览、弹框明确确认启用。初次保存后页面并行刷新触发平台并发上限，DB读回任务已启用；已将该页面请求串行化，static v2浏览器复验正常。没有自动重放不确定的写请求。

### 生产证据（不是本地测试替代）

| 验证 | 实际结果与证据 | 命令退出码 |
|---|---|---|
| 正式健康/登录/Origin/任务与版本写入读回 | `deno-product-smoke-v1.json`，真实未来日期、draft→enabled | 0 |
| 双层tick鉴权 | `deno-product-tick-v2.json`，仅平台/仅业务/错业务均401，正确组合200 | 0 |
| PG并发、唯一提醒、已读、版本冲突、暂停/编辑在途失效 | `deno-product-transactions-v2.json` 全通过；直接受限RPC测试，不冒称正式tick自动运行 | 0 |
| 真实45秒租约中断恢复 | `deno-product-lease-recovery.json`，旧执行superseded、新执行notify且只有一条通知，暂停恢复保持终态 | 0 |
| 云端真实模型语义 | v1账户请求出现无关股票追问，严格oracle失败；修订提示词后 `deno-product-model-v2.json` + assessment-v2 全通过，审计增量3、任务增量0 | 采集0；修订后断言0 |
| 真实价格观察 | `deno-product-price-live.json`，真实扶摇值以十进制字符串保存，source_time=null、来源证据持久化、result=null、通知0；任务随后暂停 | 0 |
| 重部署读回 | `deno-product-redeploy-readback.json`，v5读回v1所建Task/RuleVersion/Run/Notification，通知ID与read_at不变 | 0 |
| 隔离恢复 | `watchlist_restore_20261024_174126-assessment.json`，14表逐表一致，包含7任务/8版本/7执行/1真实Observation/4Evidence/3通知；13外键、不可变触发器及序列建立 | 0 |
| 浏览器 | dashboard/run 的txt/png：真实启用状态、执行时间线、日期证据与已读提醒，页面于17:36前关闭 | CUA操作完成 |

同实例隔离恢复不等于跨实例灾备。恢复schema为watchlist_restore_20261024_174126；没有覆盖当前watchlist。此前173127快照/恢复证据保留历史。

本地新JS模块测试17项通过（10产品+7探针），Node执行，`artifacts/deno-product-final-node-tests.txt`，退出0；不冒称17项Deno运行时测试。Python55项是已有参考，未计作迁移实现验收。测试说明deploy/TESTING_DENO.md。真实调用脚本见scripts/product_cloud_*、product_tick_live.cjs、product_price_live.cjs、product_redeploy_readback.cjs。

### 交接、未完成与唯一下一阻塞

**下一主线阻塞：验证session尚未提交正式URL上三个独立自动时隙的证据。** 已提供双层凭证安全注入约定与单次调用工具scripts/product_tick_once.cjs；该工具不是调度器。产品没有把手动请求包装成自动执行。

UI已创建并启用 `48bf9e848e5a4b29ba47241a4636ab3e`，名称“UI日期提醒演示（等待独立调度）”，真实计划时间2026-10-24 17:45:00+08:00；页面已关闭。验证session可使用17:45/17:46/17:47或稍后时隙，24小时内允许迟到补发。产品侧随后核对Run/Evidence/Notification及请求ID；若未收到调度证据，就保持未通过。

价格有效判断仍独立阻塞：逐标的成交时间、日历完整性、时效/频率依据不足。当前Deno仅持久真实观察并保持unknown；完整有效价格事件段/冷却主链路尚未在目标环境验收，不能用Python参考测试或日期链路替代。只有一只已核验标的，不宣称完整代码表。

P5：README、AI记录、Deno测试说明、部署与源码交付同步；120秒演示脚本已有，实际60–180秒视频未录制，待自动线上闭环确认。跨实例灾备、完整AC-01–18及跨语言所有边界仍需Lead签收。不新增另一套生产环境；18:00后只做既有范围集成、阻塞修复和验收。

未修改validation/、VALIDATION_REPORT.md或docs/lead/；共享HANDOFF仅追加交接。密钥与私有配置未纳入源码包，扫描结果见artifacts/deno-product-secret-scan.json。

---
以下各节为历史阶段记录；其中“未部署”“缺DSN”“仅探针”“等待时限”等描述已被本节的新证据取代，不再作为当前等待条件。


## 当前状态更新（2026-10-24 17:07）

用户转述秒悟工程师确认Edge Function网关60秒超时，执行预算依据已补齐；非独立工单读回，未证明worker CPU/存活限制。新证据artifacts/deno-engineer-timeout-basis.json。已实际阅读工程师提供的认证文档，它描述管理API凭证与scope，不能解释或证明Edge Function的verify_jwt强制。没有扩权、改密钥或重复发布。

已补30秒tick总预算、45秒DB租约、单次8秒调用及每tick最多1项的保守方案，详见deploy/DENO_ROUTE_REVIEW.md；这些尚未写入正式业务执行器或实测。中断按未知提交处理，同幂等键查结果、DB租约回收、完成时token/version/generation/生命周期校验与通知唯一约束共同保证恢复。

正式API前缀审查仍未收到明确结论。17:07距18:00冻结约53分钟，目前部署版本仍为watchlist-probe v3，完整Deno业务后端和可用产品页面均未交付，存在明显截止风险。独立调度三个时隙、业务并发/重部署/隔离恢复、价格有效判断与视频均未验收。旧证据保留；本轮仅文档与证据更新，无新增线上测试通过声明。下一直接门槛：Lead审查同源API前缀方案；随后按已批准范围实施，不能把探针当成产品。


## 产品 Deno/RPC 首包（2026-10-24 16:54）

依据DECISION_DENO_RPC，实际开工16:44，已晚于16:00目标，未伪称按时。已在既有项目执行002增量迁移并发布watchlist-probe v1→v2→v3，全部部署命令退出0；没有重跑001或改变业务数据。v1只因注入URL非HTTPS而被探针拒绝，随后新增WATCHLIST_DATA_ORIGIN指向同一库的公开HTTPS入口，v2/v3真实事务成功。

- v3目标函数 https://ut94z1so4a5dnl30.database.meoo.xyz/functions/v1/watchlist-probe ，以及同源代理 https://ucdte4eh02uv.meoo.info/sb-api/functions/v1/watchlist-probe 均实际可用（POST且需业务密钥），不是正式产品页面。
- Secret存在性全部true；提交及独立HTTP读回、故意失败回滚、唯一冲突23505、错误后恢复、清理全通过。匿名直接RPC被42501拒绝；无/错业务密钥401，越权owner403。`artifacts/deno-probe-live-v3.json`、`deno-probe-stage-result.json`。
- 数据库ACL读回anon/authenticated不可EXECUTE，service_role可EXECUTE；业务tasks/rule_versions/notifications前后皆0，probe记录清理后0。证据deno-probe-before/after-counts/after-permissions.json。不造正式提醒或模拟行情。
- 元数据verify_jwt=true但无网关Authorization且正确业务密钥仍200：网关JWT未证实强制，不能计作网关鉴权通过。应用独立鉴权已拒绝坏凭据。
- 同源HTTPS CookieJar设置/携带/清除及HttpOnly/Secure/SameSite/Path属性读回通过，非浏览器UI验收。无需跨源内存会话；正式路由前缀方案见deploy/DENO_ROUTE_REVIEW.md，等Lead审查后变更。
- CLI/官方资料未给Deno最大执行时限。客户端8s、SQL配置5s只是自设限制；实测短延迟不能替代平台允许时限。故探针总门槛尚未全过，暂不扩大完整后端移植。

官方工单新增事实：12:59工程师回复数据库仅接口接入；CLI云定时最小1分钟、可并发、每云服务最多5个。16:52已追加追问Deno/网关时限、具体cron命令及verify_jwt实际行为，详情与证据artifacts/meoo-support-deno-followup.json。请验证session按此确认正式独立调度，不以probe代替tick。


以下为历史阶段状态，当前以Deno首包为准。


## 2026-10-24 12:06 官方工单已提交

按用户明确授权，通过秒悟“用户菜单 → 问题反馈 → 提交工单”，提交三项能力确认：FC自定义Secret注入入口、既有PostgreSQL原生TLS连接、独立云调度（周期/鉴权/超时/重试/日志/套餐限制）。工单ID **000GJSKKC0**，详情 https://meoo.com/support/detail?id=000GJSKKC0 ，提交时间12:06:33北京时间，提交后详情页读回状态**已分派**。尚无平台答复，不计为能力已确认或配置完成。

已附项目ID、失败traceId和必要变量缺失的脱敏事实；没有发送任何密钥或附件，没有授权购买、删除资源或换项目。正文和状态证据：`artifacts/meoo-support-request-000GJSKKC0.txt`、`artifacts/meoo-support-ticket-000GJSKKC0.json`。下一步核对工单答复中的实际入口/约束，再执行已授权配置；不在原失败条件下重复部署。

## 当前状态与 Lead 小包（2026-10-24 11:24，北京时间）

P1–P5未整体完成。唯一生产目标仍为秒悟 `ucdte4eh02uv` + 已建watchlist PostgreSQL；根入口、Psycopg和迁移已完成，不再等待这些旧条件。当前唯一部署阻塞是**未找到可执行的FC运行时业务Secrets/原生DSN注入路径**，不是数据库网络或TLS失败。

### 本轮实际操作与结果

- 运行时配置优先核查：通过CLI当前认证请求同项目cloud/environment成功，仅返回Supabase HTTP相关字段；公开cloud/credentials接口返回403 insufficient_scope，未绕过。只保存字段名/HTTP状态，未保存返回密钥。命令退出0代表诊断完成，不代表403接口通过。证据 `artifacts/runtime-config-fields-pr01.json`。
- 尚无新增可用的FC配置契约。未重试部署、重跑迁移、重复写Secrets、创建资源或关闭production保护。原两次发布退出1、应用preflight退出2仍有效；driver未运行，原公网404为Lead 11:10读回。本轮没有声称已上线或新增可用URL。
- 给出可直接交平台的明确项目/traceId/变量及能力请求，并提出同项目事务RPC+Deno候选及代价，见 `deploy/PLATFORM_DECISION_PR01.md`。文档未承诺原生DSN不等于平台已证实不支持；候选架构未实施。单独补cloud.credentials.read也不能证明DSN可用，不要求用户盲目扩权。
- PR-01已修复：`scripts/product_model_assertions.py`对正常回答核对标的、单条件all结构、last_price/gt/1500/CNY、Asia/Shanghai市场调度与滚动86400秒冷却；歧义核对标的和阈值追问，账户要求相关unsupported，拒绝无关追问/任何草稿。最终强制3条审计、全库正式任务0。脚本默认写新证据且拒绝已有输出文件，保留历史。
- 离线：`tests/test_product_model_acceptance.py`重放Lead三个负例，通过真实Parser和临时Store，全部拒绝；保留历史真实正例，另覆盖方向/阈值/单位/标的/结构/冷却及副作用变异。命令 `.venv/bin/python -m unittest discover -s tests -p test_product_model_acceptance.py -v` 退出0，5项通过，`artifacts/pr01-offline-tests.txt`。
- 必要真实复验：`PYTHONPATH=. .venv/bin/python scripts/product_model_check.py --output artifacts/product-model-live-pr01.json` 退出0。正常/歧义/账户三场景严格语义均通过，审计3、正式任务0。证据 `artifacts/product-model-live-pr01.json` 和 `artifacts/pr01-live-command.txt`；这仅证明三条固定提示，不外推任意自然语言理解能力。相关性断言为针对固定中文测试语料的词语/结构检查，不是通用语义判别器。
- 全套回归 `.venv/bin/python -m unittest discover -s tests -v` 退出0，55项/3.466秒，`artifacts/pr01-product-suite.txt`。未改前端，本轮未重复构建；Lead本轮构建通过作为其独立证据，不冒称本轮自测。

### 交付、未执行项与下一阻塞

README、AI记录、共享交接和平台操作单已同步；代码/证据SHA清单 `artifacts/pr01-source-evidence-manifest.json`。无成功部署版本，本轮未创建Git提交。没有修改validation/、VALIDATION_REPORT.md或docs/lead/。

未执行：目标运行时TLS/事务探针、业务Task/RuleVersion/标的导入读回、产品公网登录/Host/Origin/tick/端口验证、真实未来日期UI启用和三个独立自动时隙、PG并发/重部署/隔离恢复及实际视频。均依赖运行时路径解决；本地55项不能替代。价格继续unknown，单位/来源时间/日历补证仍是价格主链路独立门槛。

唯一的下一部署阻塞：平台提供并落实**该FC容器的Secret引用入口与同一库的原生TLS连接**。若平台明确不能提供，由Lead审阅操作单中的同项目RPC方案；不擅自换架构或另建环境。验证session继续补价格口径、只读能力确认，产品session接到具体入口后执行配置和实测。

## 历史证据（以下为当时状态；当前判断以上方为准）

## 当前状态与 Lead 小包（2026-10-24 02:09，北京时间）

唯一生产目标：既有秒悟项目 `ucdte4eh02uv` 与其 PostgreSQL。根生产入口已经由产品接管，Waitress/Psycopg adapter 与 watchlist schema 均已存在，不再等待入口交接、数据库品牌批准或本机业务密钥。没有另建生产环境，也没有重新执行迁移。

- **L-01 OPEN**：新增真实 Store 事务探针 `backend/runtime_probe.py`，验证 TLS、提交后另一连接读回、主动回滚、唯一约束错误及错误后连接恢复；仅使用独立命名 ticks 探针行并清理，不制造市场数据/提醒。Secrets 列表值实际是只写配置的64位摘要（已安装CLI技能明确说明write-only，并比较新配置Origin/密码确认非原值）；误将摘要传给libpq的本机尝试在解析阶段退出2，没有建立数据库连接，不得用于判断目标网络/TLS。证据 `artifacts/target-driver-local.json`、`artifacts/secret-interface-diagnostics.json`。第二次发布的实际容器日志确认 preflight 阶段 APP_ORIGIN、SUPABASE_DB_URL、DATABASE_URL、DEMO_PASSWORD、SESSION_SECRET、TICK_SECRET 全部不存在，尚未进入数据库连接/事务探针。具体阻塞是项目Secrets未注入FC容器；尚无应用运行时PostgreSQL成功证明。
- **L-02 OPEN（发布部分）**：远端项目元数据返回预定 origin `https://ucdte4eh02uv.meoo.info`，已配置 HTTPS APP_ORIGIN、APP_ENV、密码/session/tick secrets、扶摇/DeepSeek key 与启动探针开关。密钥通过现有认证 API 内存传入，未放入 argv/源码/报告。发布命令 `meoo --json deploy --project ucdte4eh02uv --runtime image --skip-push --force` 首次退出1：平台实际执行根start，应用RuntimeError退出2，健康检查60秒失败；原始脱敏结果 `artifacts/product-deploy-attempt.json`。第二次增加启动阶段/变量存在布尔诊断后发布仍退出1；应用退出2，平台健康检查60秒失败，实际结果 `artifacts/product-deploy-diagnostic.json`，traceId `0a0328ca17927787481087323ed290`。没有成功部署版本；源快照见 `artifacts/source-manifest-runtime-diagnostic.json`，不是发布成功证明。健康地址当前 HTTP404，不作为可用产品 URL 交付。
- `.dockerignore` 明确排除 .env*、.product-data、.venv、.git、validation、artifacts 等，防止镜像源码包携带密钥/本地数据。没有覆盖 validation/、VALIDATION_REPORT.md 或 docs/lead/。
- **调度未验收**：正式 tick 契约与同工作区安全注入约定已追加 deploy/HANDOFF.md；等待产品 URL 健康后由验证 session 接入，产品核对持久记录。尚无三次生产自动触发，不以手动调用替代。
- **并发/重部署/隔离恢复未验收**：依赖实际运行时连接；现有本地与 CLI SQL 结果不替代这些。
- **价格主链路仍 unknown**：已实现真实扶摇映射与真实模型草稿；阻塞为单位、交易所来源时间、日历覆盖/完整性及频率时效口径，不是缺 key。公告仍禁用。
- **P5**：README 已纠正旧状态，新增 `deploy/DEMO_SCRIPT.md` 120秒真实证据演示脚本；实际视频等待线上链路，未录制。

实际验证：编译成功；50项回归（含新增2项探针检查）在允许本机监听环境通过（3.538秒，`artifacts/next-stage-tests.txt`）。首次沙箱内4项因本机 bind PermissionError 未运行成功，重新在允许监听环境通过；不掩盖首次失败。新增探针错误脱敏/拒绝SQLite两项测试已纳入全套。上述均不是生产验收。

需要 Lead/平台协调：请落实现有项目FC镜像容器的服务端环境变量注入入口，以及同一PostgreSQL的原生TLS连接配置。项目Secrets写入成功不能替代运行时注入。具体操作单见 `deploy/RUNTIME_CONFIG_HANDOFF.md`。不要求重新提供已存本机业务key，不申请新生产环境。若平台仅支持Supabase HTTP服务、无法提供原生连接，应由Lead决定是否改用事务RPC适配；本轮没有擅自改架构或增加公开SQL执行接口。



## 第二轮推进结果（2026-10-24 01:32，北京时间；本节优先于下方早期状态）

### R2-HTTP / L-02：生产入口已实现并接管，公网验收仍 OPEN

- 新增 `backend/wsgi.py`、`backend/serve.py`，固定 Waitress 3.0.2，复用原 Application/Store/Engine。根 `scripts/setup.sh`、`scripts/start.sh`、`package.json` 已切换为产品入口；默认符合秒悟 `0.0.0.0:${PORT:-9000}`。V0 保留 `npm run start:validation` / `node validation/server.mjs`；未修改 validation/ 和 lead 文档。
- 8 工作线程、64 连接/backlog、8 KiB 请求头、32 KiB 请求体、15 秒非活动连接超时；单演示账户每分钟 10 次登录；tick 单进程 1 槽、模型解析 2 槽，忙时返回 503。Host/Origin 校验、Secure/HttpOnly cookie、CSP、错误脱敏均有测试。非活动超时不是业务总截止，未把它包装成慢速请求全面防护。
- 根生产入口要求 HTTPS APP_ORIGIN、PostgreSQL 连接及已迁移 schema；缺配置、连接或 schema 失败时退出码 2，不回退到临时 SQLite。`artifacts/round2-production-guard.txt` 为实际拒绝启动结果。
- `sh scripts/setup.sh` 已完整执行成功，日志 `artifacts/round2-build.txt`；Waitress 真实进程已从根 start 启动并通过登录、tick 鉴权和 413/431 拒绝测试。首次大 body 测试遇到客户端提前断连；调整测试为先发送超限 Content-Length、读取服务器拒绝响应，未放宽服务端限制。
- 仍需目标平台 TLS、源端网络隔离、代理超时及公网 Host 实测。`deploy/nginx.example.conf` 只是未安装的参考，不作为证据。详见 `deploy/HTTP_DEPLOYMENT.md`。R2-HTTP 代码项已实现，线上项未签收；L-02 入口归属/整合完成，发布项仍 OPEN。

### L-01：选定既有秒悟 PostgreSQL，完成真实迁移与部分约束验证

- 已读 V0 最新报告：用户释放旧资源并建立项目 `ucdte4eh02uv`；本轮没有删除/修改旧项目、购买资源，也没有另建单机生产环境。SQLite 保留本地开发，生产方向选择已授权 PostgreSQL。
- 只读列出服务端环境变量名称，确认有 `SUPABASE_DB_URL`、`SUPABASE_URL` 等；没有读取/输出值。无需重复询问已完成的密钥导入。
- `backend/postgres.py` 实现 Psycopg 3.3.2 适配，读取 SUPABASE_DB_URL 或 DATABASE_URL，加密连接、连接8秒/语句10秒/锁5秒超时；短事务使用同一 transaction advisory lock 串行提交，外部网络仍在事务之外。单机 SQLite 的 API 语义复用，不把它的并发结果算作 PostgreSQL 结果。
- 已在目标项目实际执行 `deploy/migrations/001_watchlist.sql`，创建产品专属 watchlist schema 与 14 张表；没有修改 public 表。证据 `artifacts/postgres-migration.json`、`artifacts/postgres-schema-verification.json`。
- 同一目标 PostgreSQL 的真实 SQL 回滚测试证明：不可变 RuleVersion 触发器拒绝更新；通知 dedup_key 冲突不插入第二条；回滚后 TEST_ONLY 任务数量 0。测试没有留下模拟产品任务。
- **尚未验证**：Psycopg 从应用容器实际连接、完整业务经 driver 写回、真实生产并发 tick、云备份/恢复、重部署读回。CLI SQL 不能证明这些；本地 Docker daemon 未运行，没有拿假的 PG 测试替代。L-01 仍 OPEN。

### R2-MODEL：产品协议真实三场景通过，完整提醒链路仍未验收

- 用现有本机安全配置的 DeepSeek key，通过产品 Parser/RuleVersion 协议实际请求三次：明确贵州茅台1500元条件 → ready；模糊需求 → needs_clarification；账户余额 → needs_clarification。全部通过产品结构/标的/单位/数值白名单，临时 DB 产生3条解析审计、0个正式任务。证据 `artifacts/product-model-live.json`，可复验脚本 `scripts/product_model_check.py`。
- 初次脚本的内部标的 ID 使用了被导入器拒绝的冒号，已改为合法 `CN.SH.600519` 后执行真实调用；未放宽白名单。
- 真实元数据来源为 V0 的 iFinD 名称/代码与扶摇代码证据；只有一个标的，未伪造完整代码表。文件 `deploy/instruments_verified.json`。CNY 是 A 股实体元数据，不是“供应商已返回报价单位”的证据。

### L-04：扶摇真实字段映射完成，但价格语义尚不能启用有效判断

- FuyaoProvider 不再是无条件占位：已接 V0 实际观测到的 data.item、thscode、last_price 与历史日期字段，校验业务 code=0、空数据、标的重复/错误、数值。HTTP 成功但业务失败仍是 error。
- 没有把 response timestamp 当交易所时间，也没有猜单位；实际 observation 的 unit/source_time 为空、quality=missing、reason=quote_unit_and_exchange_time_unverified。交易日历截止前一日，当前日不在覆盖范围，market=unknown / calendar_coverage_incomplete，不按周六默认休市。
- 真实产品模型草稿接实际扶摇 preview：读到 1335，结论 unknown，正式任务/提醒均为0。证据 `artifacts/product-quote-live.json`、复验脚本 `scripts/product_quote_check.py`。
- 待 V0/lead 解决的具体契约：报价单位、交易所数据时间、可覆盖当前/未来日期及下一交易时段的日历参数/完整性、时效与频率。仅凭当前成功响应不签收实时价格监控。

### 最终本轮测试、浏览器与版本

- `.venv/bin/python -m unittest discover -s tests -v`：**48 tests / OK / 2.955秒**；`artifacts/round2-tests.txt`。其中 PostgreSQL 的3条本机测试仅是 SQL翻译/配置契约，不是 PostgreSQL运行证据；实际云SQL证据单列。
- 编译检查、根 shell 语法检查、完整根构建通过；构建有 Ant Design use-client 与体积警告，未宣称优化完成。
- 本地8080已实际重启为 Waitress，保留之前日历任务和已读提醒。浏览器完成真实自然语言 → 采用草稿 → 将1500修改为1501 → 真实预览unknown → 保存draft；正式规则读回为1501，未启用或创建价格提醒。截图 `artifacts/round2-browser-preview.png`、读回 `artifacts/round2-browser-readback.json`。这不是价格触发成功，也不是公网验收。
- 原 `artifacts/source-manifest.json` 保留为第一轮审查快照；本轮新增 `artifacts/source-manifest-round2.json`，不要用旧 manifest 校验已修改的新文件。未创建 Git commit，也没有线上部署版本。

### 当前下一步与未完成项

目标运行时 PostgreSQL driver连接/事务验证、部署Secrets与HTTPS origin/代理边界、真实价格语义补齐、产品独立自动tick至少三次、重部署/备份恢复、公网URL与代码版本、演示视频仍未完成。没有把48项本机测试或云SQL迁移包装成 P1–P5 全部交付。公告仍禁用；本轮没有改 docs/lead/、validation/、VALIDATION_REPORT.md。

## Lead 审查逐项回应

### L-01 生产持久化 — OPEN / 外部依赖未交接

认可问题。当前 `backend/store.py` 与 `backend/schema.sql` 是 SQLite 专用实现，不是可直接换 URL 的 PostgreSQL 实现。`validation/OPERATIONS.md` 已明确秒悟容器本地文件不跨冷启动持久化，因此不会以该实现宣称云端持续监控。

已采取措施：产品新增 production 启动保护（不允许当前 SQLite 实现以 production 模式启动）；本地并发/重开证据仅标为 SQLite；`deploy/HANDOFF.md` 提供具体 DB 类型、连接、TLS、迁移、事务与重建证据交接清单。没有复制验证 session 的基础设施验证工作，没有创建付费资源。

待 V0：确定实际可用的生产 DB/驱动/连接注入方式。待产品：依照回传实现对应迁移与事务，针对实际 DB 测并发去重、重建后任务/版本/运行/提醒读回。待 lead：批准生产方案。**L-01 未关闭；不能用本地测试代替关闭条件。**

证据：`backend/store.py`、`backend/schema.sql`、`backend/server.py`、`deploy/HANDOFF.md`、`artifacts/unit-tests.txt`；外部事实引用 `validation/OPERATIONS.md`（只读）。

### L-02 部署入口交接 — OPEN / 产品入口已隔离

观察到另一 session 正在写根 `package.json`，已停止使用根包作为产品入口。产品依赖及锁文件放 `frontend/`；产品构建/运行入口分别为 `deploy/product-build.sh`、`deploy/product-start.sh`。根 `scripts/start.sh` 与根 `package.json` 继续归 V0，未覆盖；V0 直接启动命令保留。

已提供 `deploy/HANDOFF.md` 的双入口矩阵与 Python runtime/平台端口/构建配置交接清单。交接前不改平台配置、不把验证页标为产品。产品正式 tick 与 V0 `/api/check` 不同，调度必须切到 `/internal/monitor/tick`，鉴权及幂等契约已写清。

待 V0 回传平台 runtime、当前部署配置、URL/项目、根入口可移交的明确状态；待产品执行目标部署与页面读回。**尚无产品公网 URL 或部署版本，L-02 未关闭。**

证据：`frontend/package.json`、`frontend/package-lock.json`、`deploy/product-build.sh`、`deploy/product-start.sh`、`deploy/HANDOFF.md`。根入口当前仍为验证服务，可直接只读核对。

### L-03 iFinD 能力 — 保持禁用

产品没有启用公告、新闻监控或 iFinD 盘中价格。`/api/v1/capabilities` 把 announcement 明确列为 disabled；没有把新闻搜索样例当公告增量流，也没有补造行情单位/交易所时刻。证据：`backend/server.py` capabilities、`backend/domain.py` 规则白名单。

### L-04 扶摇证据 — unavailable，等待 V0

没有重复请求扶摇 API。产品 adapter 未猜测行情/交易日历字段；缺密钥返回 `fuyao_credentials_missing`，已配置但无有效映射仍返回 `fuyao_mapping_unverified`。行情判断 unknown，不会默认休市或输出条件不满足。证据：`backend/providers.py`、`backend/engine.py`；真实联通仍待 V0。

## 已实现与当前状态

- P1：实体、观察/事件、日历、任务、不可变版本、运行状态、执行、证据、提醒、审计表；Decimal 严格阈值、AND/OR 三值、事件段、冷却、版本冲突、暂停/恢复/软删除、10任务上限。本地 SQLite 已测；生产 DB 未接入。
- P2：严格草稿校验、标的搜索、DeepSeek flash adapter 与解析审计、无副作用 preview；真实模型请求未运行，标的表无虚构种子；扶摇 mapping/交易日历未交接；公告禁用。
- P3：服务端 tick、事务领取、90秒租约、有限批次、旧版本/生命周期防竞态、提醒原子提交、唯一键、空档、恢复与逾期检测；未验生产独立调度。
- P4：React/Ant Design 登录、监控台、创建/编辑、任务详情、执行证据、版本、提醒已读；构建成功，本地 Chrome 日历链路已验证（不等于真实行情/AI 主链路）。
- P5：独立产品构建/启动入口、配置示例、交接清单已写；公网部署/源仓库版本/线上恢复/60–180秒演示视频未完成。

## 实际测试与发现

- Python 3.14.3 / Node 26.8.2 / npm 11.19.1。
- `python3 -m compileall -q backend`：通过。
- 首轮测试暴露 runs 与 observations INSERT 占位符数量错误，已修复；没有把失败记录写成通过。
- `python3 -m unittest discover -s tests -v`：32 tests，全部通过；输出 `artifacts/unit-tests.txt`。包括全部81种4条件三值组合、十进制边界、冷却/unknown、同键/不同键8线程竞争、租约过期、编辑/暂停/删除在途、日历迟到/missed、只读预览、归属/鉴权与解析非法字段。
- `npm --prefix frontend run build`：通过；Ant Design 的 use client 指令及大包警告存在，不影响本次构建；性能优化尚未验收。
- 模拟数据只位于 `tests/` 临时 SQLite 数据库，名称明确 `TEST ONLY`。不进入产品默认代码表/页面/真实证据。

## 改动归属

新增/维护：`backend/`、`frontend/`、`tests/`、`deploy/`、`artifacts/`、`IMPLEMENTATION_REPORT.md`；`README.md` 已补全。`dist/` 为本地构建产物。根 `package-lock.json` 曾因并行切换根 package 生成验证包空锁，无生产依赖，交由 V0 保留/处理；产品已有自己的锁文件。

`.gitignore` 仅追加产品 dist/ 与本地数据忽略规则，保留 V0 原有行。

未写：`validation/`、`VALIDATION_REPORT.md`、`docs/lead/`、现有 `scripts/`。未提交代码或密钥。

## Lead 待决定 / 验收阻塞

1. 与 V0 明确云数据库产品和可用连接；当前 SQLite 不准上线。
2. 确认目标平台支持 Python 服务或指定经过验证的运行位置；完成根构建/启动文件移交。
3. 提供经过验证的扶摇标的映射、价格口径、来源时间、交易日历、时效阈值与额度边界。
4. 独立调度必须实际调用产品 tick；V0 的验证记录不能替代产品记录。
5. 无上述证据前，AC-08/10（生产恢复）/16/18 保持未验收，不能宣称 P1–P5 全部完成。

## 用户追问后的方案调整：SQLite 不等于不能生产

用户询问能否只用 SQLite。回应：可以，MVP 不必强制购买云数据库；真正约束是持久磁盘、常驻服务、独立调度和恢复证据。提交 `deploy/SQLITE_PRODUCTION_PROPOSAL.md`，建议单机 SQLite + 应用目录外的持久本地磁盘。此为 lead 基线的待审替代方案，尚未擅自把 L-01 关闭。

已读取 V0 新报告并在 `deploy/HANDOFF.md` 明确接收 L-02 后续整合责任；V0 没有实际可用 DB/runtime，因此根验证入口继续保留，产品入口独立可运行。此前向用户询问资源是因为没有已授权的运行位置，不是要求购买云数据库。

核对 SQLite 官方资料时发现本机 Python 链接 SQLite 3.51.2，属于 WAL-reset 修复前版本。`backend/store.py` 对旧版本改用 rollback DELETE journal、FULL synchronous；仅修复版本开启 WAL，并修复初始化连接显式关闭。相关测试将在最终证据中重新执行。


## 最终本地证据补充（北京时间约 01:02）

- 最终自动测试：`python3 -m unittest discover -s tests -v`，**32 tests / OK**，2.608 秒（见 `artifacts/unit-tests.txt`）。新增真实 HTTP、独立 Python 服务进程终止/重启后 Task/Version/Run/Notification 完整相等读回、一致性备份恢复、finish 重放不改审计。
- 本机 SQLite 3.51.2；最终 journal 为 DELETE / synchronous FULL，避免旧版 WAL-reset 风险。此运行时上的并发与恢复已实测，生产机器未测。
- React / react-dom 最终锁定 18.3.1，Ant Design 5.27.6，Vite 7.1.12。浏览器实际发现 React 19 下静态确认未显示；切换兼容版本后确认框正常，实际创建/启用成功。最终构建输出 `artifacts/frontend-build.txt`（有非阻塞 use-client 与大包警告）。
- `APP_ENV=production python3 -m backend.server`：按预期拒绝未知持久化环境启动，证据 `artifacts/production-guard.txt`。这是保护措施，不是上线验收。
- 本地 Chrome：登录 → 自然语言缺凭证提示 → 表单创建未来日历 → 试运行 → 确认启用 v1 → 修改名称并重新试运行 → 保存 v2 → 刷新读回 → 离开到 about:blank → 手动调用产品 tick → 返回页面看到提醒 → 标已读 → 查看证据。**未验证在线自然语言生成/真实价格规则主链路，不能将此写成 AC-01 全部通过。**
- 浏览器任务 ID `cd125adc4c7f4e2988317eacad046275`；运行 ID `87e6ffcccbc94b9387eedd38954f3e61`。原定 2026-10-24 00:58:00 +08:00，实际 00:58:33，页面显示迟到 33 秒。一个通知；相同 tick 重放 duplicate=true。标已读后 runtime state 与 next_run 未改变。
- `artifacts/browser-readback.json` 保存脱敏 API/SQLite 读回及上述断言；`browser-dashboard.png`、`browser-detail.png` 为桌面截图；`browser-mobile.png` 为 390px 视口基本可读检查（随后已恢复原视口）。截图仅补充 JSON/数据库证据。
- 本机产品进程在最后代码修复后已实际重启，使用同一数据库与本地会话凭证；页面仍显示 v2 和已读提醒。当前本地地址 `http://127.0.0.1:8080`；不是公网 URL。
- 本地口令只在忽略目录 `.product-data/local-credentials.json`，0600；未写入浏览器包、报告或日志；服务不打印凭证。未对 V0 目录进行改写。
- 代码尚无 Git commit/部署版本；`artifacts/source-manifest.json` 给出本轮产品源文件 SHA-256，方便只读审查。不能用它代替尚不存在的线上部署 commit。

### 当前验收映射

| 项目 | 当前证据 | 尚缺 |
|---|---|---|
| AC-04/06/07/11/12 | 确定性单元/SQLite集成通过 | lead 独立审查 |
| AC-03 | 测试证明 preview 不修改 runtime/run/notification | 真实供应商证据 |
| AC-09/10/15 | SQLite 并发/进程重启/备份/提醒读回；浏览器本地链路 | 目标生产环境重建与独立触发 |
| AC-14 | HTTP 鉴权、origin、归属、tick 凭证测试 | 生产 TLS/平台鉴权部署验证 |
| AC-01/02/05/13/16 | 草稿/质量校验、不可用提示、日历失败不默认休市 | 真实模型、行情/日历与故障场景 |
| AC-08 | 未验产品独立调度 | 三次真正自动调用产品 tick |
| AC-17 | 未启用，保持禁用 | 无需把新闻样例扩充成公告证据 |
| AC-18 | 本地源码、README、测试/AI记录 | 公网部署、源版本、完整演示视频 |

### 交接后的下一步

不必购买云数据库。优先落实 `deploy/SQLITE_PRODUCTION_PROPOSAL.md` 的常驻单机与持久盘；若目标仍是秒悟，先确认其是否能提供持久盘及 Python runtime。收到该环境后完成目标部署/调度/重建读回；收到 V0 的扶摇与模型真实证据后接入 adapter。两类外部依赖尚未满足，本轮未将 P1–P5 标记全部完成。


## 阿里云服务核查补充（2026-10-24）

已查到秒悟官方自有阿里云部署说明及阿里云FC/ECS能力文档。底层能力满足产品需求；默认秒悟托管入口仍待工单确认。自有阿里云为另一部署路径，且Meoo自动开通RDS仅支持MySQL，不适配本产品现有Psycopg。提出ECS+持久盘+SQLite的有条件备选，未创建资源或修改生产模式。详见 `deploy/ALIYUN_CAPABILITY_REVIEW.md`；文档核查不替代线上验收。

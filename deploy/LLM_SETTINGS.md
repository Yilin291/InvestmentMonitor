# 自定义自然语言模型设置（协议 URL 版）

登录产品，点击“模型设置”。**不更改时使用内置 DeepSeek / deepseek-flash**。用户选择 OpenAI 兼容或 Anthropic 兼容协议，自填公网 HTTPS API URL、模型名称及 API Key；不再限制 DeepSeek/百炼提供商列表。

URL 可填基础地址或完整接口：OpenAI 的 `/v1` 自动补 `/chat/completions`，Anthropic 的 `/v1` 自动补 `/messages`；域名根地址先补 `/v1`。自定义反向代理前缀保留，例如 `/proxy/v1`。模型须支持按提示返回 JSON，领域规则仍由确定性校验和用户预览确认决定。

## 失败与生效语义

- “测试连接”只测试，不改变已保存配置。
- “保存并使用”实际测试。成功启用自定义；失败保留加密配置供修正，标记 disabled，页面提示原因，继续使用内置。重新保存可再次验证启用。
- 运行中自定义网络/HTTP/响应JSON失败：该请求内只尝试回退一次，然后剩余模型环节使用内置；结果显示 `model_warning`。不会丢弃自定义设置，下一次请求可以再次尝试。内置也失败则明确报错，不伪造草稿。
- 标的提取、规则解析和推荐输入统一使用配置。已启用监控仍由确定性日期/收盘执行器运行，不依赖LLM。
- 当前共享demo账户，配置对所有同账户会话生效。自定义URL收到用户Key和自然语言请求，界面明确说明；只能填写用户信任的服务。

## 协议、接口与安全

OpenAI兼容：Bearer Key，Chat Completions messages + JSON object，读取choices.message.content。Anthropic兼容：x-api-key、anthropic-version 2023-06-01，顶层system，messages移除system角色，max_tokens有界，读取content文本块后校验JSON。两种协议都有真实网络调用适配，不伪装为仅字段设置。

- GET /api/v1/settings/llm 返回mode、provider、base_url、model、has_key、warning、providers、builtin_model；无Key/密文。provider是协议ID `openai` / `anthropic`，旧deepseek/qwen配置可兼容读取。
- POST 同路径及 `/test` 输入 `{provider,base_url,model,api_key}`。GET返回的base_url是规范化的完整接口地址。更换URL或协议必须重填Key，同URL/协议可留空沿用；测试失败返回200且 `ok:false,warning`，保存失败返回200且 `tested:false,mode:builtin,warning`，UI须按业务结果展示警告，不能只看HTTP200。
- DELETE删除自定义配置并恢复内置。Cookie、写入Origin及路径精确匹配不变。
- 仅HTTPS443域名，拒绝IP字面值、账号密码、查询串/片段、重定向；每次自定义调用前有界检查A/AAAA，拒绝内网/回环/链路本地等地址。DNS失败不发自定义请求，使用内置。当前是应用层DNS预检，不是网络层固定IP出口；不宣称能消除所有DNS重绑定风险。
- 只将用户提供的Key发送至自定义地址，永不携带数据库service-role、Cookie或内置Key。回退调用只向固定DeepSeek官方地址使用内置Key。上游错误不转发原文。响应限制256KiB，自定义单次HTTP5秒、内置8秒，整体仍受30秒预算约束；回退不保证内置服务永远可用。
- migration012扩展011表及受限RPC，仅service_role可调用。AES-GCM v2的AAD绑定账户/协议/模型/URL，兼容旧v1。SESSION_SECRET派生密钥；轮换后需重填。业务备份不含自定义Key，恢复后重填。

协议依据：[OpenAI Chat接口](https://developers.openai.com/api/reference/resources/chat)、[Anthropic Messages接口](https://platform.claude.com/docs/en/api/messages/create)。

## 验证

70项回归见artifacts/llm-url-tests-v1.txt。真实云端记录见artifacts/llm-url-live-v19.json：自填DeepSeek URL成功、错误模型保存后使用内置、明确TEST无效模型注入后的运行中回退，最终恢复内置。TEST注入不是自然发生的供应商故障；不改行情/任务，不手动tick。Anthropic协议请求和响应、异常回退已离线验证，未持有用户对应Key，不宣称其真实供应商调用通过。

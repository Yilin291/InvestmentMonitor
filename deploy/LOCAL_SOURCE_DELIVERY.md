# 本地源码交付 r4

用户已选择先交付本地 Git 仓库与 bundle；没有远端推送，也未公开代码。

- 原仓库：/Users/alanli/Documents/ChatGPT/TongHuaShun
- 分支：codex/daily-close-mvp
- 可克隆快照：artifacts/watchlist-product-20261024-r4.bundle
- 辅助源码与构建ZIP：artifacts/watchlist-product-20261024-r4.zip
- 精确提交、文件哈希、包哈希与部署对应：artifacts/close-release-manifest-r4.json

在另一个目录恢复源码：

```sh
git clone -b codex/daily-close-mvp /Users/alanli/Documents/ChatGPT/TongHuaShun/artifacts/watchlist-product-20261024-r4.bundle watchlist-product
cd watchlist-product
npm run build
node --test tests/deno_product.test.mjs tests/deno_probe.test.mjs tests/daily_close.test.mjs tests/close_model_oracle.test.mjs
```

bundle包含提交历史，ZIP是补充快照。交付不含生产密钥、私有配置、node_modules、其他session的validation或Lead文档；演示口令沿用受控渠道，不在包中。正式目标为既有秒悟static+Deno+PostgreSQL，配置变量见README和RUNBOOK；npm start只是旧Python参考入口。既有库001–008已应用，不应重跑。

当前函数v10/static v6；平台静态发布commitId为发布时旧HEAD，不证明工作区内容一致，因此以清单内实际文件SHA和dist SHA为准。三标的真实预览通过，正式自动tick、30分钟持续运行及最终视频仍待验收。r2视频只作历史，不是当前日收盘自动运行证明。

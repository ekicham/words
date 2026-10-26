# Cloudflare 适配实施计划

> 主代理负责实现；子代理只做探索和独立核验。使用 test-driven-development 和 verification-before-completion。

**目标：** 保留本地版，实现可在 Cloudflare Workers 部署的完整多账号学习应用。

**架构：** Python Worker 复用 App/Phonetics 领域逻辑；SQLite Durable Object 持久保存学习数据，以同步事务保持答题、抽奖幂等。静态资源由 Workers Assets 提供。账号密码与邀请码注册；每个账号独立 Durable Object 数据库；服务端签名/邀请码/评测凭据只放 Workers Secrets，用户密码采用随机盐 PBKDF2。云端浏览器朗读，腾讯云评测异步请求，Mac 本地评测明确不可用。

**技术：** Python Workers、SQLite Durable Objects、Workers Assets、pywrangler、原生浏览器 JS。

- [x] 先补测试：内置资源注入不依赖本机数据路径、评测两阶段状态、认证过期/篡改。
- [x] app.py 增加资源注入和业务日期配置，phonetics.py 分离提交/结果落库，保留本地默认行为。运行原有 Python 测试。
- [x] cloudflare/storage.py 适配 SQL cursor；cloudflare/worker.py 实现认证、API 路由、Durable Object、异步评测。事务使用 storage.transactionSync，外部网络等待在事务之外。
- [x] cloudflare/build.py 只复制源码和内置资源到 .cloudflare；生成资源模块。新增 pyproject.toml、锁文件、wrangler.jsonc，忽略构建/本地状态/secret。
- [x] 增加云端登录页和设置说明，隐藏本机模型按钮和浏览器密钥配置。跨域 POST 拒绝，响应不缓存，签名密钥轮换撤销旧会话。
- [x] 使用本地 workerd 验证真实 HTTP 流程：未授权/登录/导入/学习/听写/报告/奖励/音标/持久化/登出/跨域拒绝。复用已有业务测试，浏览器核验登录和主要学习流程。
- [x] 写中文部署说明，说明 Workers 入口、Secrets、构建/部署命令、数据备份、云端与本地能力差异；构建 dry-run。通过后同步 GitHub。远程部署需 Cloudflare 账号，未部署不宣称线上验证。

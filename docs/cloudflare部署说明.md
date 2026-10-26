# 将词屿部署到 Cloudflare

整个应用运行在 Workers：静态页面 + Python API + SQLite Durable Objects。无需另买服务器、配置 D1 ID 或上传本机数据库。每个账号有独立的学习数据库，账号密码以随机盐 PBKDF2 保存。

## 从 GitHub 部署

1. 登录 [Cloudflare 控制台的 Workers & Pages](https://dash.cloudflare.com/?to=%2F%3Aaccount%2Fworkers-and-pages)，先进入账号层级。侧栏通常在“构建 / Compute & AI”下。选择创建应用、连接 GitHub 仓库，选择 `ekicham/words`，创建 **Worker**。
2. 生产分支选择 `main`，根目录保持仓库根目录。名称使用 `wordisle`；若改名，同时修改 `wrangler.jsonc` 中的 `name`。
3. 构建命令填写 `npm ci && uv sync --locked`，部署命令填写 `npm run deploy`。需要 Node.js 22 或更高、Python 3.12 或更高及 uv；当前 Workers 构建环境提供这些工具，项目锁定 Python 工具版本。不要填写 Pages 的 `dist` 输出目录。
4. 部署会自动创建两个 Durable Object 绑定。首次部署后，在该 Worker 的“设置 → 变量和机密”中添加下表的 **Secret**，保存并部署新版本。不要把密钥写进 GitHub 或普通前端环境变量。
5. 打开分配的 HTTPS `workers.dev` 地址，点击“创建账号”，输入管理员提供的邀请码。每个人注册自己的账号。以后推送 `main`，Git 集成会自动更新应用。

| Secret | 用途 |
| --- | --- |
| `AUTH_SECRET` | 必填，随机生成至少 32 字符，用于登录签名；建议 64 位十六进制 |
| `REGISTRATION_CODE` | 注册必填，随机生成至少 16 字符；只给允许注册的人 |
| `TENCENT_SECRET_ID` | 可选，腾讯云 SOE 的 SecretId |
| `TENCENT_SECRET_KEY` | 可选，腾讯云 SOE 的 SecretKey |
| `TENCENT_SOE_APP_ID` | 可选，腾讯云 SOE 业务配置要求时填写 |

可在自己的终端分别运行 `python3 -c 'import secrets; print(secrets.token_hex(32))'` 生成随机值，两项使用不同的值。未设置 AUTH_SECRET 时页面会提示管理员配置；未设置邀请码时关闭新注册，已有账号仍能登录。更换 AUTH_SECRET 会让所有现有登录失效，但不删除账号或学习数据。

如果控制台首次部署无法设置 Secret，先完成部署，再添加并重新部署即可。构建失败时查看日志，确认 Node 版本与部署命令；无需寻找 Pages 专用入口。

## 在电脑上预览或手动部署

安装 Node.js 22+、Python 3.12+ 和 uv 后，在仓库根目录运行：

```sh
npm ci
uv sync --locked
```

本地预览先创建 `.dev.vars`，填入仅供本地测试的随机值：

```dotenv
AUTH_SECRET=替换为至少32字符的随机值
REGISTRATION_CODE=替换为至少16字符的随机邀请码
```

```sh
npm run dev
```

打开终端显示的本地地址。本地模拟数据库在 `.wrangler/`，不与线上共享；`.dev.vars` 已被 Git 忽略。不要删除 `.wrangler/` 后误以为账号丢失是应用故障。

手动发布：

```sh
npx wrangler login
npm run deploy
npx wrangler secret put AUTH_SECRET
npx wrangler secret put REGISTRATION_CODE
```

腾讯云评分需要管理员开通 SOE 并配置对应 Secret；不配置也可正常学习单词、听写、查看报告和观看音标课程。网页不能修改服务器密钥。

## 数据与功能边界

- 每个账号独立保存学习会话、错词、奖品、导入词库和录音；换设备登录同一账号即可继续。桌面版历史数据不会自动上传，当前未提供桌面数据库迁移功能。
- 更新 Worker 代码保留 Durable Object 数据。不要删除 Worker、修改对象绑定/命名规则或删除迁移记录来“重新部署”。CSV 导出是学习报告，不是完整数据库备份；当前没有管理员批量备份、账号删除及自助密码找回功能。正式长期使用前，应按 Cloudflare 的 Durable Objects 数据恢复说明制定备份方案。
- “今日”以北京时间 UTC+8 计算。语音朗读依赖浏览器和设备的中英文语音；麦克风需要 HTTPS 和用户授权。
- Mac 专用 OpenPronounce 模型不能在 Workers 运行。云端评分调用腾讯云；录音与评分保存在账号中，可删除整次测试记录。第三方服务可能收费，超时重试也可能再次计费。
- 注册需要邀请码；同一 IP 的登录/注册合计每 15 分钟最多 10 次。多人共享网络时请错开频繁尝试。登录有效期 7 天；退出清除当前浏览器 Cookie。
- 内置课程和视频使用 Workers Assets；剑桥真人发音等外部资源仍需联网。Cloudflare、腾讯云的套餐、存储及请求额度分别适用，使用前查看各自控制台。

## 验证

```sh
python3 -m unittest test_cloudflare test_app test_catalog test_rewards test_dictation test_phonetics test_openpronounce test_macos test_windows
npm run check:deploy
```

本地启动后，`python3 test_cloudflare_http.py` 验证双账号隔离、答题幂等、听写、报告和录音接口；会创建一次性测试账号。可运行安装了 Playwright 的 `node test_cloudflare_browser.cjs` 检查界面，然后停止并重启本地服务，运行 `python3 test_cloudflare_http.py --verify-restart` 验证持久化并删除临时测试凭据。

评分接口的可重复测试步骤见 `test_cloudflare_assessment.py` 文件头；生成的测试配置只在本地使用，正式构建会清除测试替身。

本次已在本地 workerd 验证业务接口，并通过真实 Chrome 检查主要流程。腾讯云网络返回使用测试替身验证成功、失败与重复提交；未用真实腾讯云密钥计费调用。部署预检不等同于线上验收，仍需在你自己的 Cloudflare 账号完成发布后验证访问。

参考：[Python Workers](https://developers.cloudflare.com/workers/languages/python/)、[SQLite Durable Objects](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/)、[Workers Git 构建](https://developers.cloudflare.com/workers/ci-cd/builds/)。

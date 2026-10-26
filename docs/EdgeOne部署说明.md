# Words 部署到 Tencent EdgeOne Makers

本分支：`codex/tencent-edgeone`。前端与 Python API 部署在同一个 EdgeOne 项目，账号、教材导入、学习记录、奖品、录音存入 MySQL。没有默认账号；管理员设置邀请码后，用户在登录页点击“创建账号”。密码至少 12 字符。

## 1. 准备数据库

使用专用 MySQL 8.0.16+（建议 8.4 LTS）数据库，存储引擎 InnoDB。不要使用 SQLite、MariaDB 或 Cloudflare D1 连接信息。数据库需允许 EdgeOne 云函数所在地域连接；不要假定腾讯云私网 IP 可以直接访问。检查数据库网络、防火墙和 TLS 证书，优先选择与函数同地域的数据库。

管理员可执行以下 SQL 创建专用库和用户；替换示例密码，并根据实际出口限制来源。应用自动建表，不需要手工导入学习数据。

```sql
CREATE DATABASE wordisle CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE USER 'wordisle_app'@'%' IDENTIFIED BY 'REPLACE_WITH_A_RANDOM_DATABASE_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, REFERENCES ON wordisle.* TO 'wordisle_app'@'%';
```

`%` 仅表示 MySQL 用户匹配来源，不代表应向所有公网来源开放防火墙。不要使用 root 账号运行应用。配置自动备份；录音也在数据库中，需考虑存储空间。

## 2. 导入 GitHub 分支

在 EdgeOne Makers 创建项目，选择 GitHub 仓库 `ekicham/words`，生产分支选择 **`codex/tencent-edgeone`**。

| 设置 | 值 |
| --- | --- |
| 框架 | Other / 自定义 |
| 根目录 | 仓库根目录 |
| 安装命令 | `npm ci` |
| 构建命令 | `npm run build` |
| 输出目录 | `dist/edgeone` |

仓库 `edgeone.json` 已提供配置，Python API 在 `cloud-functions/api/[[default]].py`。构建会自动生成辅助模块；不要把 `dist/edgeone` 当作项目根目录，否则会漏掉 API。无需填写 `wrangler deploy`。

Python 云函数使用 3.10，依赖位于 `cloud-functions/requirements.txt`；超时设为 60 秒。当前地域：大陆广州、海外新加坡，可按数据库位置修改 `edgeone.json`。

## 3. 配置运行环境变量

在“项目设置 → 环境管理”为生产环境填写；预览环境使用独立数据库和密钥。修改后重新部署。模板位于 `edgeone/env.example`，不要把真实值提交 GitHub。

| 变量 | 内容 |
| --- | --- |
| `APP_ORIGIN` | 实际访问地址，例如 `https://words.example.com`；不含路径 |
| `AUTH_SECRET` | 独立随机密钥，至少 32 字符；更换会使现有登录失效 |
| `REGISTRATION_CODE` | 独立随机邀请码，至少 16 字符；分享给获准注册的人 |
| `DB_HOST` | 数据库证书对应的主机名 |
| `DB_PORT` | 通常 `3306` |
| `DB_NAME` | `wordisle` |
| `DB_USER` | `wordisle_app` |
| `DB_PASSWORD` | 数据库密码 |
| `DB_TLS` | 保持 `1`，验证服务端证书及主机名 |
| `DB_TLS_CA_FILE` | 使用公共 CA 时不填；自有 CA 见下文 |
| `TENCENT_SECRET_ID` / `TENCENT_SECRET_KEY` | 可选：腾讯云 SOE 评测服务凭证 |
| `TENCENT_SOE_APP_ID` | 可选：SOE AppId |

没有 SOE 凭证仍可背词、听写和查看报告，评分会提示未配置。密钥只由管理员配置，用户页面无法修改。浏览器朗读取决于终端可用语音，云端不运行 Mac 本地语音模型。

生成两个独立随机值可分别运行 `python3 -c "import secrets; print(secrets.token_hex(32))"`，分别用于 AUTH_SECRET 和邀请码；不要复用数据库密码。

如数据库使用私有 CA，将服务商提供的 **公开 CA 证书** 保存到 `edgeone/mysql-ca.pem`（绝不能包含私钥），设置 `DB_TLS_CA_FILE=bundled`。构建会以 `mysql-ca.txt` 文件名收集证书，以兼容 EdgeOne Python 打包白名单。

不要把生产密钥写进仓库根目录 `.env` 或 `.env.local`：当前 EdgeOne CLI 会将其中部分变量写入生成的函数代码。生产配置应由控制台环境变量注入。本地测试模板使用其他文件名并从进程环境读取。

## 4. 域名与验收

建议绑定稳定自定义域名，再把 `APP_ORIGIN` 设为这个地址。选择包含中国大陆的加速区域时需满足平台域名备案要求。默认项目域名在大陆访问可能要求控制台生成的临时预览链接（有效期 3 小时）；因此默认域名不能当作稳定的大陆访问方案。参见官方 [域名说明](https://pages.edgeone.ai/zh/document/domain-overview)。

部署后，用两个新账号分别导入词库、练习、刷新页面、退出后重新登录，确认记录独立保存。HTTPS 下允许麦克风才能录音。邀请码是管理员提供的 REGISTRATION_CODE，**不是 AUTH_SECRET**。现有 Cloudflare 账号、SQLite 学习记录不会自动迁移，本分支会新建独立账号和记录。

常见问题：

- 首页显示但注册失败：检查数据库连接、权限、TLS 和运行环境变量，然后重新部署。
- 提示“请求来源无效”：访问域名必须与 APP_ORIGIN 一致；不要通过另一个预览域名提交。
- 503 含错误编号：按编号在函数日志查数据库错误类型/代码；日志不会输出密码、SQL、答案或录音。
- 桌面版正常、云端记录为空：这是不同存储，不能直接复用本机数据库文件。

## 本地验证与边界

```sh
npm ci
npm run build
# EdgeOne CLI 本地模拟也要求腾讯云授权/token：
npm run dev:edgeone
```

集成回归需专用测试 MySQL（库名必须以 `_test` 结尾），将测试连接变量写到不提交的 `.env.edgeone.test`，并设置 `EDGEONE_LOCAL=1`、`APP_ORIGIN=http://localhost`、仅回环数据库可 `DB_TLS=0`：

```sh
python3 -m pip install -r cloud-functions/requirements.txt
WORDISLE_TEST_ENV=.env.edgeone.test python3 -m unittest test_edgeone
```

实现采用每个账号 10 张表、同一账号写入串行的方案，面向小规模多人使用；大规模开放注册前应改为共享表租户结构并进行容量测试。认证有账号级和全局限流，当前不提供自助找回密码。不要向不受控人群公开邀请码。

当前 EdgeOne CLI 1.6.46 的开发依赖 `npm audit` 报告 esbuild / extract-zip 风险且无官方自动修复；它们不进入 Python 线上运行包。避免处理不可信压缩包、对公网开放开发服务；后续关注官方 CLI 更新。

平台参考：[Python 云函数](https://pages.edgeone.ai/zh/document/python)、[配置文件](https://pages.edgeone.ai/zh/document/edgeone-json)、[环境管理](https://pages.edgeone.ai/zh/document/build-guide)。

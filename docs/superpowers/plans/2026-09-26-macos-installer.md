# macOS 安装版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Scouts only inspect; the primary agent implements and verifies.

**Goal:** 交付包含运行环境的词屿 Universal2 DMG，拖入 Applications 后可直接使用。

**Architecture:** 保留 Python 标准库服务和现有界面，用 Swift/AppKit + WKWebView 提供独立窗口。PyInstaller 打包 Python 和内置只读词库；学习数据存入用户 Application Support，偏好由原生应用保存，不随随机本机端口变化。

**Tech Stack:** Python 3.13、PyInstaller、Swift、AppKit、WebKit、hdiutil；目标 macOS 12.3+，arm64 / x86_64。

---

- [x] 为动态端口、语音失败回退、桌面服务启动/退出和持久化添加 `test_macos.py`，先验证缺失行为。
- [x] 修改 `app.py` 的 Host 校验使用实际绑定端口，语音合成失败返回既有浏览器回退；增加 `macos/backend.py`，支持独立数据目录、原子就绪文件、父进程退出清理。
- [x] 增加 `macos/WordIsle.swift` 和 `Info.plist`：应用菜单、独立窗口、内置后台启动/退出、导入面板、导出保存面板、偏好保存、外链跳转系统浏览器。最小修改 `static/app.js` 连接原生偏好和下载桥。
- [x] 增加 `scripts/build_macos.sh`，从 Universal2 Python 构建内置后端、编译双架构启动器、复用 favicon 制作图标，签名并生成含 Applications 链接和中文说明的 DMG。只列入词库、静态资源和来源/许可证，排除个人数据库、缓存、备份。
- [x] 执行 `python3 test_app.py`、`python3 test_catalog.py`、`python3 test_rewards.py`、`python3 test_macos.py`；验证冻结后端两种架构的真实 HTTP 学习闭环、音频和重启持久化。
- [x] 挂载 DMG，复制安装并启动实际 `.app`，检查窗口、偏好、下载/导入、进程清理；执行 `codesign --verify --deep --strict`、`hdiutil verify`，记录 SHA-256 和已验证平台边界。
- [x] 更新 README 和 macOS 验收记录，直接交付 DMG 路径；本机旧学习记录单独用 SQLite backup 迁移，绝不放进分发包。无 Developer ID 时明确尚未公证及首次打开方式。

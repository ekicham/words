# 学习方式与全屏练习 Implementation Plan

**Goal:** 增加顺序/随机学习、下划线直接输入、离线音标、语速选择和可用 Esc 退出的全屏大字练习。
**Architecture:** 延续 Python 标准库和原生页面。新会话保存 learning_order，旧会话默认为 random，items 的既有顺序不变；音标使用本地词典子集。真实输入框放在单词区域，以字母格和光标呈现输入。使用浏览器 Fullscreen API，并保留不支持时的满窗口布局。
**Tech Stack:** SQLite、Python、HTML/CSS/JavaScript、现有 Playwright 浏览器验收。

- [x] 在 test_app.py 增加顺序、随机无重复、恢复和非法排序测试；先确认失败，再修改 App.start、数据库兼容迁移和返回字段。
- [x] 制作 data/phonetics.json 及来源许可；测试全部内置词条覆盖、read 两种时态、短语标识。保持原词库和学习记录不变。
- [x] 新增 test_learning_browser.cjs，先确认缺少控件而失败。修改 static/app.js 的设置、单词输入、语速及全屏事件；static/style.css 增加大字与输入光标样式。
- [x] 浏览器核验自动跳词、错误重输、长短语、小屏、两种语音路径、Esc/完成后退出全屏、恢复进度和偏好保存；运行现有回归。
- [x] 备份正式 SQLite，启动新版并只读核对词库与学习记录；更新 README 与验收记录。

交互约定：Esc 退出全屏，练习和计时继续；结束本轮沿用已有确认及报告。语速 0.75× / 1× / 1.25× / 1.5×，默认 1×。顺序按单元编号排列，单元内保持词表导入次序，Numbers 等附录置后。

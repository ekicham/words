# 练习页简化与设置

**Goal:** 全屏上一个/下一个、教材格式音标、参考答案同中文字号、移除练习小字、左侧设置入口。
**Architecture:** 保留 sessions.position 作为原进度；只读 GET position 参数回看已学词，当前题的下一项仍走现有 skip 事务。设置沿用浏览器偏好。六上音标单独保存源文核对表，其他来源保留标识。
**Tech Stack:** Python 标准库、SQLite、原生 JS/CSS、现有 Playwright。

- [x] 先写后端回看不计分和教材音标断言，确认失败，再实现只读查看接口和教材优先音标。
- [x] 先写浏览器设置/导航/字体断言，确认控件缺失；再修改 index.html、app.js、style.css。
- [x] 设置收纳声音与语速；练习保留答错/保存失败提示，去掉常驻补字、鼓励、发声状态等小字。
- [x] 回归导航往返、当前下一项跳过、重复计分防护、设置持久化、语音变速、全屏退出和小屏；备份学习库并重启验证。

## Liquid Glass 整体视觉

- 参考 Apple 官方 Materials、Designing for macOS、Color、Motion：玻璃用于导航和操作层，内容采用清晰阅读表面。
- 原生 CSS 实现浮动侧栏、工具栏、胶囊按钮、分段选项与设置开关；不新增运行依赖。
- 深色、减少动态效果、减少透明度、增强对比度与强制颜色模式；桌面及 390px 布局验收。
- 独立核对修正 was 教材读音；计时及窗口同步保留只读回看状态，增加可复现断言。

官方参考：https://developer.apple.com/design/human-interface-guidelines/materials
https://developer.apple.com/design/human-interface-guidelines/designing-for-macos
https://developer.apple.com/design/human-interface-guidelines/color
https://developer.apple.com/design/human-interface-guidelines/motion

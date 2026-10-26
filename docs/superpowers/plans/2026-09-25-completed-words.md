# 累计与今日完成词表 Implementation Plan

**Goal:** 首页增加去重累计完成数，累计和今日卡片可打开完整学习表格。
**Architecture:** 从已有正确提交记录只读聚合，按忽略大小写及多余空白的英文拼写去重。使用实际提交日期，包含活动会话，不新增表或改写历史；同词的教材、单元、地区出处分别保留。
**Tech Stack:** Python / SQLite / 原生 JavaScript 与 CSS，无新增依赖。

- [x] 在 `test_app.py` 先验证：不同轮次、会话、教材同词只计一个；跳过/答错不算完成；提示后答对计入；午夜按答对日期归属；请求重试不增加频次；表格元数据和首页数量一致。运行 `python3 -m unittest test_app` 确认新测试失败。
- [x] `app.py` 新增只读 completed_words(scope='all'|'today') 查询：正确 attempts 按 word_id/地区聚合 COUNT(DISTINCT item_id)、MAX(submitted)，按英文拼写合并词条并保留 sources；phonetic() 复用。bootstrap 返回 completed_words/today_words；新增 GET `/api/completed-words?scope=all|today`，非法 scope 返回 400。
- [x] `static/app.js` 增加累计与今日详情路由，使用原生按钮卡片。明细按最近学习排序；同词多出处采用分组表格，列为最近学习日期、单词、音标、中文、单元、学习频次、学期、年级、教材、地区；频次为所选时间范围内成功完成次数。
- [x] `static/style.css` 首页四卡桌面一行、窄屏两列；详情表局部横向滚动，保留键盘焦点与深色适配。
- [x] 新建临时数据库浏览器验收脚本 `test_completed_browser.cjs`：零记录、两个卡片点击、全部字段、合并词条、日期切换、返回、390px布局、只读访问记录不变；运行 Python 回归和此浏览器脚本，检查截图。
- [x] 只读备份正式数据库、重启服务，验证原记录和新卡片；更新 README 与验收记录，不提交 Git。

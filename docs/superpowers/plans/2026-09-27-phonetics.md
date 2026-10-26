# 音标学习 Implementation Plan

**Goal:** 单词探险之前新增48组英美音标学习、参考视频、真实专业评测和持久化报告。
**Architecture:** 复用本地HTTP、SQLite和WKWebView；新功能集中于phonetics.py/static/phonetics.js，原拼写记录独立。示范使用剑桥官方远程录音及例词，视频/MP3随包离线提供。腾讯云SOE以显式音素结构评测，不以识别文字或音量伪造分数。
**Tech Stack:** Python标准库、Web Audio PCM录音、原生video、SQLite、Tencent SOE REST/TC3签名。

- [x] 数据：data/phonetics-course.json保留48组UK/US符号、独立录音URL、例词和口型提示；tr/dr/ts/dz注明组合音，缺少独立音频时明确使用例词示范；英式特有音在美式展示对应音/例词。
- [x] 媒体：data/phonetics-media包含用户视频/MP3，HTTP白名单支持Range/HEAD和错误范围416。验证首段、末段及视频时长。
- [x] 后端：新增独立测试/评分表；校验口音/题数/16kHz单声道PCM；密钥只保存在用户目录0600文件且API不回传。请求幂等，云失败不计0分；报告列有效评分数量、均分、跳过、每音素成绩与建议。
- [x] 先写test_phonetics.py，断言`len(course)==48`、UK/US音频不同、无密钥拒绝评测、重复提交一次评分、失败无假分、Range206/416；运行RED，再实现并运行GREEN。
- [x] 前端：新增导航与独立学习页；英美切换、分组点读、视频、10/48项测试、显式录音/停止/回放/提交、麦克风状态、评测披露和同意、历史报告/CSV。离开停止录音和音频。
- [x] 设置：腾讯云SecretId/SecretKey及可选SoeAppId，保存后仅显示已配置；允许移除。无密钥可学习，测试显示配置入口。
- [x] 原生：NSMicrophoneUsageDescription、只允许主框架本地源的麦克风权限请求；版本1.3.0，Universal包携带新资源，不携带密钥/录音/数据库。
- [x] 核验：Python回归、实际Chrome录音/媒体/布局（云回包用明确mock）、原生窗口及系统权限、冻结包测试，备份后从DMG升级并比较旧记录。

自动评分依赖用户开通腾讯云并填写凭证；未取得凭证时仅能验证协议/错误路径与模拟回包，不宣称真实云评分验收通过。SOE无独立英式/美式口音开关，报告需注明所选学习口音和通用英语音素引擎，不能声称英美口音标准鉴定。

完成：2026-09-27。视频增加独立全屏按钮，原生 WKWebView 启用元素全屏；麦克风权限回调以主框架、当前本地页面及精确请求源校验，兼容 frame.request.url 为空。证据见 macos/验收记录.md 和 output/phonetics/。真实云评分待用户配置账号后验证。

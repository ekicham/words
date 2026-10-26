# OpenPronounce Implementation Plan

**Goal:** 接入本地例词发音参考评测，保留腾讯云音素评测、历史报告及全部学习数据。
**Architecture:** 现有 Phonetics 统一保存测试快照/录音/幂等结果；provider 固定在每次测试。独立 OpenPronounce 子进程通过私有 stdin/stdout JSON 通信，无公开端口；冻结 arm64 组件随 Universal 主应用打包。模型首次由用户点击准备时下载到 Application Support，之后离线评分。OpenPronounce 参考声使用 macOS 本机语音，无 Google TTS 和录音上传。
**Tech Stack:** 现有 Python/SQLite/Web Audio；OpenPronounce 0.3.0、PyTorch、Transformers、espeakng-loader；PyInstaller 独立 helper。

- [x] 先写 test_openpronounce.py：配置切换保留云凭证、旧测试迁移为腾讯云、新测试固定 provider、失败不计分、引擎结果解析/静音/无效响应。
- [x] local_assessment.py：子进程管理、模型准备状态、严格 WAV/参考词输入，失败后可重试。scripts/openpronounce_engine.py：加载固定模型、系统参考声、真实 OpenPronounce 评分，屏蔽联网 TTS，家目录可写缓存。
- [x] phonetics.py / app.py：设置选择与模型准备 API，测试 provider 快照与报告/CSV；不按全局配置改变已开始测试的引擎。
- [x] static/phonetics.js：本地/腾讯云选择，模型准备/刷新状态，本地例词录音、评分来源和识别音素展示，云模式原有同意和凭证入口保留。
- [x] 真实本机例词和不匹配录音验证；单元回归、浏览器录音/切换/报告/失败重试。每份本地报告明确参考分不是孤立音标准确率或英美口音鉴定。
- [x] scripts/build_openpronounce.sh、macos/openpronounce.spec：生成 macOS14+ arm64 helper；scripts/build_macos.sh 拷贝组件并注明架构差异，版本1.4.0，模型/录音/凭证不进入DMG。
- [x] 备份已安装数据和偏好；冻结组件真实推理、DMG签名/安装/启动、旧数据逐行核对。更新 README、使用说明、验收记录并交付DMG。

本次是明确授权的继续实现，直接在当前未跟踪源码基线推进，不提交或重置用户文件。专业云评分仍待真实账号；本地评测的存在不代表儿童/孤立音标准确性已经校准。

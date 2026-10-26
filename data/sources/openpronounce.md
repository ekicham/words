# OpenPronounce 本地例词评测

集成版本：OpenPronounce 0.3.0；核对日期：2026-09-27。

- 项目及评分实现：[Halleck45/OpenPronounce](https://github.com/Halleck45/OpenPronounce)，MIT 许可证。
- 固定发行包：[PyPI openpronounce 0.3.0](https://pypi.org/project/openpronounce/0.3.0/)。完整依赖版本在 `macos/openpronounce-requirements.txt`。
- 词识别模型：[facebook/wav2vec2-large-960h](https://huggingface.co/facebook/wav2vec2-large-960h)，固定 revision `bdeaacdf88f7a155f50a2704bc967aa81fbbb2ab`。
- 音素识别模型：[facebook/wav2vec2-lv-60-espeak-cv-ft](https://huggingface.co/facebook/wav2vec2-lv-60-espeak-cv-ft)，固定 revision `ae45363bf3413b374fecd9dc8bc1df0e24c3b7f4`。
- 两份模型卡标注 Apache-2.0；首次准备模型时一同下载模型卡，模型不包含在 DMG 内。

## 评分口径

使用上游 `compare_audio_with_text(..., use_phone_model=True)` 的真实分数和识别结果。输入为课程例词及 16 kHz 单声道 WAV。仅替换模型加载位置和参考声生成方式；参考声由 macOS Samantha 在本机生成，不调用 Google TTS。本机参考声是合成语音，不等同于学习页的剑桥真人录音。

分数评价完整例词，不是孤立音标准确率，也不是考试成绩。英语音素规则偏向美式；英式/美式切换控制课程示范，不代表两套独立口音评测模型。儿童、短词、重复读词、噪声均可能引起误判；报告保留录音回听、识别文本和音素用于参考。80 分是本应用练习建议阈值，未经教师或儿童语料标定。

模型准备需要联网，合计约 2.4 GB；后续评分设置 Hugging Face/Transformers 离线模式。录音仅通过私有子进程管道发送至本机引擎，不上传，不在失败时回退至腾讯云。无有效声音或引擎失败不计分。现有腾讯云凭证和历史测试保留，每次测试固定记录开始时所选服务。

## 平台与随包源码

主应用为 Universal，最低 macOS 12.3。独立 OpenPronounce helper 为 arm64，因所用 PyTorch 轮子要求，仅支持 Apple 芯片与 macOS 14+。首次模型准备还检查 Samantha 声音是否可用；缺失时按提示安装系统声音。

辅助组件使用 [phonemizer](https://github.com/bootphon/phonemizer) 3.4.0（GPL-3.0）及 [eSpeak NG](https://github.com/espeak-ng/espeak-ng)（GPL-3.0-or-later），由 espeakng-loader 0.2.4 提供运行库。随包二进制报告 eSpeak NG 1.52.0；包含对应官方发布源码、phonemizer 源码、各依赖许可证、适配代码及构建脚本，位于 `Contents/Helpers/OpenPronounceEngine.app/Contents/Resources/source-and-notices/`。组合 helper 适配源码按 GPL-3.0-or-later 提供；上游组件保留各自许可证。

## 验证范围

源码引擎已用实际模型验证合成语音目标词、错误词和静音；浏览器通过合成麦克风执行录音、真实评分、报告、CSV 与服务切换。合成对照用于验证链路，不能证明儿童或真实口音评分准确性。打包后运行和安装检查另见 `macos/验收记录.md`。

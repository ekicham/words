# 音标学习来源与评测口径

核对日期：2026-09-27。`data/phonetics-course.json` 的 48 组分类采用英语教学常见的 20 组元音、24 个辅音及 4 组组合音；这不是“完整国际音标表”，也不表示英式、美式各有完全相同的 48 个独立音位。`tr/dr/ts/dz` 为组合音。

## 点读

主要来源：[Cambridge Dictionary 发音符号及英美录音](https://dictionary.cambridge.org/help/phonetics.html)。每项保存独立的 UK / US 音频地址、例词与来源链接。录音在线播放，不将剑桥音频复制入安装包；[剑桥授权说明](https://dictionary.cambridge.org/license.html)。口型提示为本应用编写，发音变体并非口型文字可以完整描述。

- 英式 /ɒ/ 对应常见美式 /ɑː/，因此美式列表可出现重复的 /ɑː/。英式 /ɜː/ 对应美式 /ɝː/，/əʊ/ 对应 /oʊ/。
- 英式 /ɪə eə ʊə/ 的美式对应 /ɪr er ʊr/ 使用剑桥 [ear](https://dictionary.cambridge.org/dictionary/english/ear)、[hair](https://dictionary.cambridge.org/dictionary/english/hair)、[pure](https://dictionary.cambridge.org/dictionary/english/pure) 的美国例词音频，明确显示“例词示范”，不伪称独立音素录音。/r/ 为英语教材习惯写法，实际近音 [ɹ]，不是 IPA 颤音 [r]。
- 组合音使用 [tree](https://dictionary.cambridge.org/dictionary/english/tree)、[dream](https://dictionary.cambridge.org/dictionary/english/dream)、[pizza](https://dictionary.cambridge.org/dictionary/english/pizza)、[goods](https://dictionary.cambridge.org/dictionary/english/goods) 的真实英美例词录音。练习目标分别为例词中的 /tr dr ts dz/，不是整个例词。
- 未用普通文字转语音冒充孤立音标录音。原有单词练习的系统语音保持不变。

用户提供的 `一首歌教会你48个国际音标的标准发音…_xWT111.mp4/mp3` 复制为 `data/phonetics-media/lesson.mp4/mp3`。视频长约 115.75 秒，H.264 / AAC；作为参考歌谣随包离线播放，保留原画面和声音，未宣称来源机构或用其生成标准音标分数。原素材包含创作者信息，点读与评测独立。第三方内容权利归原作者，商业再分发应自行取得对应授权。

## 自动评分

采用腾讯云 SOE 基础版 REST [TransmitOralProcessWithInit](https://cloud.tencent.com/document/product/884/32605)，英语单词模式 `EvalMode=0`、音素结构 `TextMode=1`、非流式 `WorkMode=1`、`ScoreCoeff=1.0`。参考文本显式传入 `wordList[].pron`，映射依据[官方智聆音素表](https://cloud.tencent.com/document/product/884/33698)与[文本结构说明](https://cloud.tencent.com/document/product/884/78883)，非普通语音转文字匹配。

录音转换为 16 kHz / 16 bit / mono PCM WAV，0.5–8 秒。仅点击“提交评测”后发送至 `soe.tencentcloudapi.com`，通过 TC3-HMAC-SHA256 签名。凭证存入用户目录权限 0600 的配置文件，不在前端持久化或 API 回显，也不进入安装包。服务未配置时可以学习但不能开始自动评分。

得分取服务 `PronAccuracy`，0–100；官方 `-1` 表示完全不匹配，界面记 0 分并明确反馈，保留原值。报告显示有效评分的算术平均值，错误请求、无有效分数、跳过和未完成不记 0 分。不以音量、录音时长或转写文字伪造准确度。低于 80 分仅为本应用建议再练阈值。逐音素详情若服务返回则保留；接口失败保留录音供明确重试，相同提交不重复评测。

SOE 此接口没有独立的英国/美国口音选择参数，部分对立元音共用引擎音素。因此报告标注“通用英语音素模型”，不能用来鉴定英美口音。所选口音仅固定学习示范及相应参考音素。真实评测需用户开通服务、配置有效凭证并联网；无凭证的验收只能核验协议、错误路径及模拟回包，不能证明实际评分质量。

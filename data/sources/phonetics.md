# 离线读音参考

## 官网新版六上优先使用教材格式

`official/1212001601265-phonetics.tsv` 保存 143 个唯一词形，对应 144 个词条（run 在不同单元重复）。依据人教社[六上阅读器](https://book.pep.com.cn/1212001601265/mobile/index.html)印刷第 81–84 页词表核对；图片为阅读器第 87–90 张，原图链接及 SHA-256 已保存在 `official/manifest.json`。

保留教材长音、重音、/r/ 和 (r) 写法，短语合为一组斜线，例如 Terracotta Warriors `/ˌterəˈkɒtə ˈwɒriəz/`。教材只注出新词部分的短语，未注部分按常见英式读音补全，例如 Eiffel Tower 的 Tower；因此完整短语不声明为教材逐字转写。中文地名 Jinggangshan、Zhuhai 保留拼音。was 使用教材 `/wəz/`。字体采用系统衬线字体显示 IPA，来源说明保留在悬停提示。

## 其他教材的词典参考


核对日期：2026-09-30。`data/phonetics.json` 保存内置 2,048 个词条对应的 1,224 个不区分大小写的词形/短语。新增河南外研四上需要的 57 个词形使用同一 SHA-256 的原词典重建，原有 1,167 个词形的读音保持不变。它是独立发音参考，不冒充逐字摘录教材音标。

主来源：[open-dict-data/ipa-dict](https://github.com/open-dict-data/ipa-dict) 的 [en_US.txt](https://raw.githubusercontent.com/open-dict-data/ipa-dict/master/data/en_US.txt)，General American；MIT 许可原文保存在 `ipa-dict-LICENSE.txt`。原始文件 SHA-256 存在 JSON 的 `source_sha256`。仅打包本项目所需子集，无需联网查词，也不引入应用依赖。重建方式：`python3 scripts/build_phonetics.py /path/to/en_US.txt`。

- 单词一般保留词典列出的读音变体；read 根据词条释义区分原形 /ˈɹid/ 与过去式 /ˈɹɛd/。reading、wind、windy、live、use、reuse 按当前教材中的“阅读、风、多风、居住、使用、重复使用”义项选用对应读音，避免误选地名或其他词性的首变体。
- 短语按组成词的独立发音列出，标为“美式分词参考”，不是连续语流中的完整重音、弱读或连读转写。短语 read books 使用原形读音，冠词 a 使用 /ə/。
- colourful 使用美式同义拼写 colorful 的发音。BDS、PE、CPC 按字母名称拼读。
- 词典缺项的核对来源：[maths](https://dictionary.cambridge.org/pronunciation/english/maths)、[mooncake](https://dictionary.cambridge.org/pronunciation/english/mooncake)、[schoolbag](https://dictionary.cambridge.org/pronunciation/english/schoolbag)、[terracotta](https://dictionary.cambridge.org/us/pronunciation/english/terracotta)、[pipa](https://dictionary.cambridge.org/pronunciation/english/pipa)、[Westray](https://dictionary.cambridge.org/pronunciation/english/westray)，均取美式条目。
- taikonaut 使用 [Collins / Dictionary.com](https://www.dictionary.com/browse/taikonaut) 已给出的英式 /ˈtaɪkəʊˌnɔːt/，单独标为“英式参考”，不虚构美式值。
- Turpan 依据人教社 [六下旧版阅读器](https://book.pep.com.cn/1212001602145/) 的印刷第 59 页（阅读器第 65 张图）人工查看，原文 /ˈtuəˈpɑːn/，标为“教材音标”。这是对已有旧词库的读音补充，没有新增六下教材。
- Jinggangshan 和 Taishan 在教材词表未给音标，保留带声调的地名拼音 Jǐnggāngshān、Tàishān，并明确标“分词参考 · 地名为拼音”。其余组成词提供英语音标，不把推测写成词典事实。

展示时将词典的 ɹ / ɫ 统一为基础音位写法 r / l，保留底层词典原值。

音标与系统语音分别来自上述参考和本机合成引擎，可能有合理的口音、变体差异。外部新导入词库中尚未收录的词形显示“音标待补充”。

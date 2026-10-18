# 第三方数据来源与许可

本 skill 的数据由下列来源加工而成，各许可证的**完整原文**在 `references/licenses/` 目录。分发本 skill 时请保留该目录和本文件。

| 来源 | 用在哪里 | 许可证 | 完整文本 |
|---|---|---|---|
| Unicode Unihan 数据库（© 2026 Unicode, Inc.） | 康熙部首与部外笔画、康熙字典页位、拼音、英文释义、通用规范汉字序号、简繁对应 | Unicode License v3 | `licenses/Unicode-3.0.txt` |
| shunshi-kangxi-core（© 2026 Shunshi.AI） | 汉字五行标注（`chars.csv` 的 `wx` 列，来源标为 `shunshi`）；康熙字典原文所属部与原文自带的康熙笔画标注，用于核验 | MIT | `licenses/MIT-shunshi-kangxi-core.txt` |
| pwxcoo/chinese-xinhua（© 2018 PWXCOO） | 汉字中文释义片段（`def_zh` 列） | MIT | `licenses/MIT-chinese-xinhua.txt` |
| Chinese-Names-Corpus（wainshine） | 只使用聚合统计：每个字出现在名字里的次数和男女次数（`name_freq.csv`），不含任何具体姓名 | Apache-2.0 | `licenses/Apache-2.0-Chinese-Names-Corpus.txt` |

仓库地址：Unihan https://www.unicode.org/charts/unihan.html ；shunshi-kangxi-core https://github.com/shunshi-ai/kangxi-mcp ；chinese-xinhua https://github.com/pwxcoo/chinese-xinhua ；Chinese-Names-Corpus https://github.com/wainshine/Chinese-Names-Corpus 。

《康熙字典》（1716）原文属于公有领域。

## 81 数理吉凶评语

`shuli_81.json` 只记录各来源对每个数给出的吉凶等级（事实性信息），不搬运原文的解说文字。来源是公开网页：搜狐发布的"1—81数理吉凶查对表"、台湾师范大学课程资料中的数理表、国际易经风水策划研究院页面的"81数理与个人吉凶"。

## 仅用于交叉校验、未纳入数据的来源

cantian-naming（https://github.com/cantian-ai/agent-skill）：仓库中未找到许可证文件，因此只用它的笔画、五行和吉凶评语做校验对比（`chars.csv` 的 `kx_status` 列和 `verify` 列的判定过程用到了这种对比），其数据和代码都没有复制进本 skill。重建脚本的 `--cantian` 参数是可选的，需要自行获取该文件。它的流程设计（喜用神优先、数理五行与汉字五行分开、自拟候选必须回填评分）给了本 skill 的设计思路。

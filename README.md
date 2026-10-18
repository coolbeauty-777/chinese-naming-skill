# chinese-naming｜中文起名 Skill

一个给 Claude 用的 Skill：结合**生辰八字的五行喜用神**、**《康熙字典》笔画**和**五格数理**，为人起名，或分析、比较已有的名字，并且把每一步的依据讲清楚。

> 这是传统姓名学的规则体系。本项目按其规则认真执行并说明依据，但**不替它背书**：评语是各流派的经验性说法，不是科学结论，也不构成对任何人命运的预测。

## 特点

- **笔画以《康熙字典》为准**。不是现代笔画：氵算 4 画，艹算 6 画，辶算 7 画，姓氏"王"是 5 画。每个字都标有证据等级，通用规范汉字 8105 个里约 97.8% 有《康熙字典》原文或原书页位的依据（见下文）。
- **排盘由程序计算，不靠模型心算**：支持公历/农历，自动处理 1986–1991 年夏令时，并按出生地做真太阳时校正，两种盘不一致时会如实指出。
- **少而精的笔画组合**：人格、总格必须是吉数，地格尽量吉，组合太少才逐层放宽，地格凶的不列；最后给出建议组合和小结。
- **具体的字让你自己选**：按笔画、按五行列出可选的字，不替你做决定。
- **自带回归自检**：`python chinese-naming/scripts/selftest.py`。

## 安装

### 在 Claude.ai 中使用

1. 打开本仓库的 **Releases** 页面，下载 `chinese-naming-v1.0.0.zip`。
   - 不要使用仓库首页绿色按钮 Code → Download ZIP：它会在外面多包一层仓库文件夹，上传会失败。
2. 在 Claude.ai 中打开 **Customize → Skills**，点 **+** → **Create skill** → **Upload a skill**，选择下载的 zip。
3. 确认已在 **Settings → Capabilities** 中开启 **Code execution and file creation**（Skills 需要它）。

详细说明见官方帮助文档：[Use skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)。

### 在 Claude Code 中使用

把 `chinese-naming/` 文件夹复制到 `~/.claude/skills/`（所有项目可用），或项目里的 `.claude/skills/`（仅该项目）。

### 依赖

需要 Python 3 和 lunar-python（用于排八字）：

```bash
pip install lunar_python
```

其余脚本只用 Python 标准库。如果运行环境不能联网，需要提前安装。

## 怎么用

直接对 Claude 说，例如：

> 姓李，男，农历 2023 年五月初八上午 10:20 出生，出生在成都，想起个双名。

它会按这个流程走，并把每一步写出来：

1. **八字**：四柱、日主，出生地对时柱有没有影响
2. **喜用神**：怎么判断旺衰，取哪个五行，为什么
3. **笔画与五格**：吉数是哪些、筛选规则、筛选后的笔画组合、建议组合和小结
4. **可选的字**：只列建议组合用到的笔画，按五行列出具体的字
5. **推荐**：从中挑出的名字，附寓意、五格和需要留意的地方

也可以直接问："王雨慧这个名字怎么样？"

## 数据与可靠度

笔画的证据等级（`data/chars.csv` 的 `evidence` 列），共 8105 个通用规范汉字：

| 等级 | 含义 |
|---|---|
| A | 以《康熙字典》原文自带的康熙笔画标注为准 |
| B | 原书正文页位核验通过 |
| C | 原书页位核验通过，原书用的是异体字形，强度稍弱 |
| D | 只有多个来源互相一致，没能在原书核验（字表里标 †） |
| X | 本字与繁体字形笔画不同，需要取舍（如于 3/於 8） |

A、B、C 合计约 97.8%。方法、阈值和已知问题见 [`chinese-naming/references/methodology.md`](chinese-naming/references/methodology.md)。

## 局限

- 只覆盖 8105 个通用规范汉字（中国大陆姓名可用字范围）。
- 传统姓名学没有统一标准：81 数理的吉凶评语、汉字五行、是否使用真太阳时，各流派不同；本项目把采用的取舍写在文档里，并在输出中标出有分歧的地方。
- 喜用神由模型结合全盘判断，不同流派可能得出不同结论。
- 三才配置只做了生克的简单打分，没有 125 种组合的吉凶表。
- 用字频次来自一份公开人名语料，偏向较早年代的名字。

## 目录结构

```
chinese-naming/
├── SKILL.md                 # 工作流与规则（Claude 读这个）
├── scripts/
│   ├── bazi.py              # 排八字、夏令时、真太阳时
│   ├── list_options.py      # 吉数 → 笔画组合 → 可选字
│   ├── wuge.py              # 五格计算与自拟名字分析
│   ├── pick_names.py        # 随机候选
│   ├── selftest.py          # 回归自检
│   └── rebuild/             # 数据生成与审计脚本
├── data/                    # 字库、81 数理表、用字频次
└── references/              # 方法说明与第三方许可
```

## 反馈

发现某个字的康熙笔画不对，欢迎提 Issue。请附上依据（《康熙字典》的部、部外笔画或页位），这样我能核对并加入回归自检。

## 许可证与致谢

本项目自己编写的代码与文档使用 **MIT** 许可证，见 [LICENSE](LICENSE)。

数据部分来自以下项目，各自适用其许可证（完整文本在 `chinese-naming/references/licenses/`）：

- [Unicode Unihan 数据库](https://www.unicode.org/charts/unihan.html)：Unicode License v3
- [shunshi-kangxi-core](https://github.com/shunshi-ai/kangxi-mcp)：MIT
- [pwxcoo/chinese-xinhua](https://github.com/pwxcoo/chinese-xinhua)：MIT
- [Chinese-Names-Corpus](https://github.com/wainshine/Chinese-Names-Corpus)：Apache-2.0（只使用聚合统计，不含任何具体姓名）

《康熙字典》（1716）原文属于公有领域。

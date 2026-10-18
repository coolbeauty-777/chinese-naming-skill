#!/usr/bin/env python3
"""构建 81 数理吉凶表 (data/shuli_81.json)。

只转录各来源给出的"吉凶等级"这一事实, 不搬运原文的解说文字。
多个来源的评语并存, 数值化后求均值/最小值, 并标出有争议的数。

来源:
  A  搜狐《1—81数理吉凶查对表》: 全 81 数; 版本不一致时同时给出两个评语
  B  台师大课程资料的 81 数理表: 仅 18-49, 分级最细 (大吉/吉/吉多于凶/凶多于吉/凶/大凶)
  C  国际易经风水策划研究院页面: 仅部分数 (1-10, 78-81)

用法: python build_shuli.py [--validate cantian_wuge.ts]
  --validate 仅用于交叉校验转录有无笔误, 不会写入数据。
"""
import argparse, json, re
from pathlib import Path

# ---- 评语 -> 数值 ----
SCORE = {"大吉": 2, "吉": 1, "吉多于凶": 0.5, "半吉": 0.5, "吉带凶": 0.5, "半凶": -0.5,
         "凶多于吉": -0.5, "凶带吉": -0.5, "凶": -1, "大凶": -2, "吉凶各半": 0}

# ---- A: 搜狐 (一个数可有两个版本的评语, 用 | 分隔) ----
A_RAW = """1 吉;2 凶;3 吉;4 凶;5 吉;6 吉;7 半吉|吉;8 半吉|吉;9 凶|半吉;10 凶;11 吉;12 凶;13 吉;14 凶;15 吉;
16 吉;17 半吉|吉;18 半吉;19 半凶|凶;20 凶;21 吉;22 凶;23 吉;24 吉;25 吉|半吉;26 凶;27 凶;28 凶;29 半吉;
30 半凶|半吉;31 吉;32 吉;33 吉;34 凶;35 吉;36 凶|半吉;37 吉;38 半吉;39 吉|半吉;40 半凶|凶;41 吉;42 凶;
43 凶;44 凶;45 吉|半吉;46 凶;47 吉;48 吉;49 凶|半吉;50 凶|半吉;51 凶|半吉;52 吉;53 凶;54 凶;55 凶|半吉;
56 凶;57 半吉|吉;58 半吉;59 凶;60 凶;61 吉|半吉;62 凶;63 吉;64 凶;65 吉;66 凶;67 吉;68 吉;69 凶;70 凶;
71 半凶|吉;72 半凶|吉;73 半吉|吉;74 凶;75 半凶|吉;76 凶;77 半凶|半吉;78 半吉|凶;79 凶;80 凶;81 吉"""

# ---- B: 台师大 (18-49) ----
B_RAW = """18 吉;19 大凶;20 大凶;21 大吉;22 凶;23 大吉;24 大吉;25 吉;26 凶多于吉;27 吉多于凶;28 大凶;29 大吉;
30 吉多于凶;31 大吉;32 吉;33 大吉;34 大凶;35 吉;36 凶;37 吉;38 吉;39 大吉;40 吉多于凶;41 大吉;
42 吉多于凶;43 凶多于吉;44 大凶;45 吉;46 大凶;47 大吉;48 大吉;49 吉多于凶"""

# ---- C: 部分数 ----
C_RAW = "1 吉;2 凶;3 吉;4 大凶;5 吉;6 吉;7 吉;8 吉;9 凶;10 半凶|半吉;78 半凶|半吉;79 凶;80 凶;81 大吉"


def parse(raw):
    out = {}
    for item in raw.replace("\n", "").split(";"):
        item = item.strip()
        if not item:
            continue
        n, labels = item.split(" ", 1)
        out[int(n)] = labels.split("|")
    return out


# 女性相关标注 (来源 A/B 的文字说明): avoid=多数来源明确"女性不宜/忌女"; caution=偏男性化, 宜注意
FEMALE = {"avoid": [21, 23, 33, 39], "caution": [7, 17, 29], "fit": [35]}
WUXING = {0: "水", 1: "木", 2: "木", 3: "火", 4: "火", 5: "土", 6: "土", 7: "金", 8: "金", 9: "水"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "data" / "shuli_81.json"))
    args = ap.parse_args()

    A, B, C = parse(A_RAW), parse(B_RAW), parse(C_RAW)
    assert sorted(A) == list(range(1, 82)), "A 应覆盖 1-81"
    for src in (A, B, C):
        for ls in src.values():
            for l in ls:
                assert l in SCORE, f"未知评语 {l}"

    table = []
    for n in range(1, 82):
        labels = {"A": A[n]}
        if n in B: labels["B"] = B[n]
        if n in C: labels["C"] = C[n]
        scores = [SCORE[l] for ls in labels.values() for l in ls]
        mean, lo, hi = sum(scores) / len(scores), min(scores), max(scores)
        table.append({
            "n": n, "wuxing": WUXING[n % 10], "labels": labels,
            "mean": round(mean, 2), "min": lo, "max": hi,
            "solid_ji": lo >= 1,                 # 所有来源/版本都 >= 吉
            "top_ji": lo >= 1 and hi == 2,       # 稳吉, 且至少一个来源给大吉
            "disputed": (hi - lo) >= 1.5,        # 来源之间跨度 >= 1.5 (如 吉 vs 凶)
            "female": next((k for k, v in FEMALE.items() if n in v), None),
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"note": "各来源评语为事实性转录, 无统一标准; 见 SKILL.md 中的取舍说明",
               "scores": SCORE, "female": FEMALE, "table": table},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("写出", out)

    solid = [t["n"] for t in table if t["solid_ji"]]
    top = [t["n"] for t in table if t["top_ji"]]
    disp = [t["n"] for t in table if t["disputed"]]
    print("稳吉(所有来源>=吉):", solid, f"({len(solid)}个)")
    print("稳吉且有来源给大吉:", top)
    print("来源有明显分歧:", disp)

    if args.validate:   # 交叉校验: 用 cantian 的吉/凶方向核对我的转录
        txt = Path(args.validate).read_text(encoding="utf-8")
        blk = txt[txt.index("LUCK_BY_NUMBER"):]
        blk = blk[:blk.index("};")]
        cant = {int(n): v for n, v in re.findall(r'(\d+):\s*"([^"]+)"', blk)}
        side = lambda s: 1 if s.startswith("吉") and "带凶" not in s and "帶凶" not in s and "各半" not in s else (-1 if s == "凶" else 0)
        bad = []
        for t in table:
            c = cant.get(t["n"])
            if c is None: continue
            cs = side(c)
            if cs == 1 and t["max"] < 1: bad.append((t["n"], c, "我的评语", t["labels"]["A"]))
            if cs == -1 and t["min"] > -1 and t["mean"] > 0: bad.append((t["n"], c, "我的评语", t["labels"]["A"]))
        print("\n与 cantian 方向明显相反的数(供核对转录):", bad if bad else "无")


if __name__ == "__main__":
    main()

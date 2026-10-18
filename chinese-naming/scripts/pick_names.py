#!/usr/bin/env python3
"""按 姓氏 + 喜用神五行 + 五格硬条件 生成候选名 (供 Claude 再从字义、音律上精选)。

流程 (先枚举笔画组合, 再按笔画和五行取字):
  1. 硬条件: 人格、总格 "稳吉" (所有来源评语 >= 吉); 女性另排除 人格/总格/地格 的"女性不宜"数
  2. 在满足条件的笔画组合里, 取 康熙笔画可靠 + 五行匹配喜用神 的字
  3. 软评分: 地格/外格评语、三才生克、喜用神匹配度、字的常用级别
  4. 输出 Top N, 同一个字最多出现 --max-repeat 次, 保证候选多样

用法示例:
  python pick_names.py --surname 李 --gender 男 --elements 木,火 --len both --count 20
"""
import argparse, csv, itertools, json, math, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wuge as wg

SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
# 明显不适合入名的字 (负面语义/不雅); 用户可用 --avoid 追加
BLACKLIST = set(
    "死病痛丧哀愁怨恨仇毒鬼魔妖祸灾殃凶恶贱穷贫饥饿苦悲泣泪孤寡败亡灭杀斩刑罪奴"
    "臭屎尿屁淫娼妓奸骚贪赌盗匪贼狗猪蛇鼠蚁蝇蛆尸棺坟墓葬祭"
    "粪毙滥吓瞪糠谤谎嚎憾懈撼浊澡痹隙鄙膨鞭腻呛愕嫉疙疚疳疽痂痞疤疥疮痢痨瘟疫癌疯瘸瞎聋哑瘫痴傻呆笨蠢懒骗偷抢劫诈骂咒殴屠戮骸殡魂魄孽厄"
    "惧恐怖惨凄囚狱吼哮呸呕吐泻溃漏堕腐烂惰懦怯佞谗妒恼怒愤怼悔惭愧耻辱羞垢污秽脏腥臊膻肮瘪枯槁朽萎凋衰残废缺陷破碎裂崩塌坠沉溺淹嫖贩"
)


def rel(a, b):
    """相邻两格数理五行关系得分: 生 +1, 比和 +0.5, 克 -1, 被生/泄 0"""
    if SHENG[a] == b: return 1.0
    if a == b: return 0.5
    if KE[a] == b: return -1.0
    return 0.0


def usable(r, allow_unverified, allow_ambiguous):
    v, st = r["verify"], r["kx_status"]
    if v in ("verified", "text_note"):
        return True
    if v in ("unverified", "page_conflict") and st == "agree_all":
        return True                      # 原书无法定位/页位属分类特例, 但三方一致
    if allow_unverified and v in ("narrowed", "unverified"):
        return True
    if allow_ambiguous and v == "policy_dual":
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--surname", required=True, help="姓, 1-2 字")
    ap.add_argument("--gender", default="不限", choices=["男", "女", "不限"])
    ap.add_argument("--elements", default="", help="喜用神五行, 逗号分隔, 先写主要的, 如 木,火; 不填则不按五行筛")
    ap.add_argument("--len", dest="glen", default="both", choices=["1", "2", "both"])
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--max-level", type=int, default=1, choices=[1, 2, 3], help="用字级别上限: 1=一级常用字(默认)")
    ap.add_argument("--avoid", default="", help="需排除的字, 如家族字辈或避讳字")
    ap.add_argument("--must-include", default="", help="指定必须出现的字(如字辈)")
    ap.add_argument("--both-in-elements", action="store_true", help="双名时两个字都要在喜用神五行内")
    ap.add_argument("--allow-unverified", action="store_true", help="允许笔画未被原书完全核验的字")
    ap.add_argument("--allow-ambiguous", action="store_true", help="允许本字/繁体笔画有取舍争议的字")
    ap.add_argument("--strict-soft", action="store_true", help="地格、外格也要求不凶")
    ap.add_argument("--min-name-freq", type=int, default=30,
                    help="字在真实人名(名字部分)中至少出现的次数, 用来保证是正常人名用字; 0=不限")
    ap.add_argument("--no-gender-filter", action="store_true", help="不按字的男女用名倾向过滤")
    ap.add_argument("--max-repeat", type=int, default=2)
    ap.add_argument("--max-per-strokes", type=int, default=2, help="同一笔画组合最多出几个, 保证多样")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    chars = wg.load_chars(); shuli, _ = wg.load_shuli()
    freq = {r["char"]: (int(r["n_total"]), int(r["n_male"]), int(r["n_female"]))
            for r in csv.DictReader(open(wg.HERE.parent / "data" / "name_freq.csv", encoding="utf-8"))}
    for c in a.surname:
        if c not in chars:
            sys.exit(f"字库中没有姓「{c}」, 请用 --surname 以外的方式手动给笔画")
    S = [int(chars[c]["kx"]) for c in a.surname]
    els = [e for e in a.elements.split(",") if e]
    avoid = set(a.avoid) | BLACKLIST
    rng = random.Random(a.seed)

    pool = []
    for c, r in chars.items():
        if c in avoid or c in a.surname or int(r["level"] or 9) > a.max_level:
            continue
        if not usable(r, a.allow_unverified, a.allow_ambiguous):
            continue
        n, m, f = freq.get(c, (0, 0, 0))
        if a.min_name_freq and n < a.min_name_freq:
            continue
        if not a.no_gender_filter and a.gender != "不限" and m + f >= 30:
            share_f = f / (m + f)
            if (a.gender == "男" and share_f > 0.85) or (a.gender == "女" and share_f < 0.15):
                continue
        if els and r["wx"] not in els:
            if not (a.glen != "1" and not a.both_in_elements and r["wx"]):   # 双名第二字可放宽到任意已知五行
                continue
        pool.append(r)
    by_stroke = {}
    for r in pool:
        by_stroke.setdefault(int(r["kx"]), []).append(r)

    def cscore(r):
        s = {0: 3.0, 1: 2.0}.get(els.index(r["wx"]), 1.0) if r["wx"] in els else 0.0
        n = freq.get(r["char"], (0,))[0]
        s += (1.0 if r["level"] == "1" else 0.3 if r["level"] == "2" else 0.0) + 0.4 * math.log10(1 + min(n, 3000))
        return s - (0.5 if int(r["kx"]) > 18 else 0.0)

    fem_bad = lambda n: a.gender == "女" and shuli[n]["female"] == "avoid"
    ok_hard = lambda n: shuli[n]["solid_ji"] and not fem_bad(n)
    soft = lambda n: shuli[n]["mean"]

    results = []
    lens = [1, 2] if a.glen == "both" else [int(a.glen)]
    must = set(a.must_include)
    for L in lens:
        ranges = [range(1, 31)] * L
        for strokes in itertools.product(*ranges):
            if any(s not in by_stroke for s in strokes):
                continue
            ge = wg.wuge(S, list(strokes))
            if not (ok_hard(ge["人格"]) and ok_hard(ge["总格"])):
                continue
            if fem_bad(ge["地格"]):
                continue
            if a.strict_soft and (soft(ge["地格"]) < 0 or soft(ge["外格"]) < 0):
                continue
            tian, ren, di = (wg.WUXING[ge[k] % 10] for k in ("天格", "人格", "地格"))
            base = (3 * soft(ge["人格"]) + 2 * soft(ge["总格"]) + 1.0 * soft(ge["地格"]) + 0.5 * soft(ge["外格"])
                    + 1.0 * (rel(tian, ren) + rel(ren, di)))
            groups = []
            for s in strokes:
                g = sorted(by_stroke[s], key=lambda r: (-cscore(r), rng.random()))[:30]
                groups.append(g)
            for combo in itertools.product(*groups):
                gv = "".join(r["char"] for r in combo)
                if must and not (must & set(gv)):
                    continue
                if a.both_in_elements and els and any(r["wx"] not in els for r in combo):
                    continue
                if els and not any(r["wx"] in els for r in combo):
                    continue
                if L == 2 and combo[0]["char"] == combo[1]["char"]:
                    continue
                results.append((base + sum(cscore(r) for r in combo), gv, combo, ge, strokes))
    results.sort(key=lambda x: (-x[0], rng.random()))

    picked, use, per = [], {}, {}
    for sc, gv, combo, ge, strokes in results:
        if any(use.get(c, 0) >= a.max_repeat for c in gv) or per.get(strokes, 0) >= a.max_per_strokes:
            continue
        for c in gv:
            use[c] = use.get(c, 0) + 1
        per[strokes] = per.get(strokes, 0) + 1
        picked.append((sc, gv, combo, ge))
        if len(picked) >= a.count:
            break

    out = []
    for sc, gv, combo, ge in picked:
        out.append({
            "姓名": a.surname + gv, "分": round(sc, 1),
            "字": [{"字": r["char"], "拼音": r["pinyin"], "康熙笔画": int(r["kx"]), "五行": r["wx"],
                   "五行来源": r["wx_src"], "释义(英)": r["def_en"], "名用字频次": freq.get(r["char"], (0,))[0]} for r in combo],
            "五格": {k: {"数": n, "评语": "/".join(sum(shuli[n]["labels"].values(), [])), "数理五行": shuli[n]["wuxing"]}
                   for k, n in ge.items()},
            "三才": "".join(wg.WUXING[ge[k] % 10] for k in ("天格", "人格", "地格")),
        })
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1)); return
    print(f"姓{a.surname}(康熙{'+'.join(map(str, S))}画) 性别:{a.gender} 喜用神:{','.join(els) or '不限'} "
          f"| 可用字池 {len(pool)} 个, 满足条件的组合 {len(results)} 个, 展示 {len(out)} 个\n")
    print("| 姓名 | 笔画 | 人格 | 总格 | 地格 | 外格 | 三才 | 字五行 | 释义 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for o in out:
        g = o["五格"]
        f = lambda k: f"{g[k]['数']}{g[k]['评语'].split('/')[0]}"
        print(f"| {o['姓名']} | {'+'.join(str(x['康熙笔画']) for x in o['字'])} | {f('人格')} | {f('总格')} | {f('地格')} | "
              f"{f('外格')} | {o['三才']} | {''.join(x['五行'] or '?' for x in o['字'])} | "
              f"{'；'.join(x['字']+':'+(x['释义(英)'] or '')[:22] for x in o['字'])} |")


if __name__ == "__main__":
    main()

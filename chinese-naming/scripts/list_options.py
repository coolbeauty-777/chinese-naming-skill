#!/usr/bin/env python3
"""列出筛选后的笔画组合 + 建议组合 + 这些组合要用到的笔画下按喜用神五行可选的字。

筛选逻辑 (分层递补, 目的是组合少而精):
  硬条件   人格、总格必须是"稳吉数"; 女性不用 21/23/33/39 作人格、总格、地格
  地格     尽量吉; 只有组合太少时才补充"地格半吉(无凶)"的; 地格凶的一律不列
  外格     只大概看一下; 组合够多时外格凶的不列, 组合太少时才放进来并标明
  可选字   某个笔画下喜用神五行的可选字太少(默认 <3 个)的组合没有实际用处, 不列
  天格     对单姓是固定的, 不计

用法:
  python list_options.py --surname 王 --gender 女 --elements 水,木 [--len both] [--few 6]
"""
import argparse, itertools, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import csv as _csv
import wuge as wg
from pick_names import usable, BLACKLIST, SHENG, KE


def lab(t):
    """一个数的评语: 全部来源一致评吉记"吉", 否则列出不同评语; 有分歧加 *"""
    ls = list(dict.fromkeys(sum(t["labels"].values(), [])))
    return ("吉" if t["solid_ji"] else "/".join(ls)) + ("*" if t["disputed"] else "")


def flow(a, x, b, y):
    """返回 (关系文字, 得分): 任何生 +1, 比和 +0.5, 任何克 -1"""
    if SHENG[x] == y: return f"{a}生{b}", 1.0
    if x == y: return "比和", 0.5
    if KE[x] == y: return f"{a}克{b}", -1.0
    if SHENG[y] == x: return f"{b}生{a}", 1.0
    return f"{b}克{a}", -1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--surname", required=True)
    ap.add_argument("--gender", default="不限", choices=["男", "女", "不限"])
    ap.add_argument("--elements", required=True, help="喜用神五行, 如 水,木")
    ap.add_argument("--len", dest="glen", default="both", choices=["1", "2", "both"])
    ap.add_argument("--max-level", type=int, default=2, choices=[1, 2, 3])
    ap.add_argument("--avoid", default="")
    ap.add_argument("--allow-unverified", action="store_true")
    ap.add_argument("--allow-ambiguous", action="store_true")
    ap.add_argument("--max-stroke", type=int, default=30)
    ap.add_argument("--chars-level", type=int, default=2, choices=[1, 2],
                    help="字表里列到哪一级: 1=只列一级常用字; 2=一二级都列(二级字单独一行)")
    ap.add_argument("--few", type=int, default=6, help="少于这个数就视为组合太少, 才会递补次一级的组合 (单名自动减半)")
    ap.add_argument("--min-chars", type=int, default=10, help="某笔画下可选字少于这个数的组合不列(太少没法选, 也多为很生僻难写的字)")
    ap.add_argument("--top", type=int, default=3, help="每种名字长度给出几个建议组合")
    ap.add_argument("--max-show", type=int, default=10, help="每种名字长度最多列出几个组合(单名取一半), 超出的按综合评分取前几名")
    a = ap.parse_args()

    chars = wg.load_chars(); shuli, _ = wg.load_shuli()
    els = [e for e in a.elements.split(",") if e]
    S = []
    for c in a.surname:
        if c not in chars:
            sys.exit(f"字库中没有姓「{c}」")
        S.append(int(chars[c]["kx"]))
    freq = {r["char"]: (int(r["n_male"]), int(r["n_female"]))
            for r in _csv.DictReader(open(wg.HERE.parent / "data" / "name_freq.csv", encoding="utf-8"))}
    avoid = set(a.avoid) | BLACKLIST

    # ---- 字池: 按 (笔画, 五行) 分组 ----
    pool, removed = {}, []
    for c, r in chars.items():
        if c in avoid or c in a.surname or int(r["level"] or 9) > a.max_level:
            if c in BLACKLIST and int(r["level"] or 9) <= a.max_level and r["wx"] in els \
                    and usable(r, a.allow_unverified, a.allow_ambiguous):
                removed.append(c)
            continue
        if not usable(r, a.allow_unverified, a.allow_ambiguous) or r["wx"] not in els:
            continue
        pool.setdefault(int(r["kx"]), {}).setdefault(r["wx"], []).append(r)
    for st in pool:
        for wx in pool[st]:
            pool[st][wx].sort(key=lambda r: (int(r["level"]), -sum(freq.get(r["char"], (0, 0)))))
    nchar = lambda st: sum(len(v) for v in pool.get(st, {}).values())

    solid = [n for n in range(1, 82) if shuli[n]["solid_ji"]]
    fem = [n for n in range(1, 82) if shuli[n]["female"] == "avoid"]
    fem_bad = lambda n: a.gender == "女" and n in fem
    ok = lambda n: shuli[n]["solid_ji"] and not fem_bad(n)

    print("## 吉数\n")
    print(f"稳吉数（三份资料对它们的评语都是吉，共 {len(solid)} 个）：" + " ".join(map(str, solid)))
    if a.gender == "女":
        print(f"\n女性：{'、'.join(map(str, fem))} 在资料里标为女性不宜，不用作人格、总格、地格。")
    print("\n**筛选规则**：人格、总格必须是稳吉数（硬条件）；地格尽量吉，组合太少时才补充地格半吉的，地格凶的不列；"
          "外格只大概看，组合够多时外格凶的不列；天格对单姓固定，不计。\n")

    # ---- 枚举满足硬条件的组合 ----
    lens = [1, 2] if a.glen == "both" else [int(a.glen)]
    allc = {1: [], 2: []}
    stats = {1: {"地格凶": 0, "字太少": 0}, 2: {"地格凶": 0, "字太少": 0}}
    for L in lens:
        for strokes in itertools.product(range(1, a.max_stroke + 1), repeat=L):
            if any(nchar(s) == 0 for s in strokes):
                continue
            ge = wg.wuge(S, list(strokes))
            if not (ok(ge["人格"]) and ok(ge["总格"]) and not fem_bad(ge["地格"])):
                continue
            di = shuli[ge["地格"]]; wai = shuli[ge["外格"]]
            if di["mean"] < 0:
                stats[L]["地格凶"] += 1; continue
            if min(nchar(s) for s in strokes) < a.min_chars:
                stats[L]["字太少"] += 1; continue
            wai_bad = (L == 2) and wai["mean"] < 0                  # 单名外格恒为 2, 不看
            tian, ren, dix = (wg.WUXING[ge[k] % 10] for k in ("天格", "人格", "地格"))
            r1, s1 = flow("天", tian, "人", ren); r2, s2 = flow("人", ren, "地", dix)
            allc[L].append(dict(strokes=strokes, ge=ge, di_g=0 if di["solid_ji"] else 1, wai_bad=wai_bad,
                                sancai=tian + ren + dix, rel=f"{r1}；{r2}", rel_score=s1 + s2,
                                n=[nchar(s) for s in strokes]))

    def combo_score(c, L):
        g = c["ge"]; sc = 2.0 if c["di_g"] == 0 else 1.0
        if L == 2:
            sc += 1.0 if shuli[g["外格"]]["solid_ji"] else (-1.0 if c["wai_bad"] else 0.3)
            if fem_bad(g["外格"]): sc -= 0.5
        sc += c["rel_score"] * 0.7 + min(min(c["n"]) / 20.0, 1.0)
        return sc - 1.0 * sum(1 for x in c["strokes"] if x > 20)

    ORDER = [((0, False), "A 地格吉，外格不凶"), ((1, False), "B 地格半吉（无凶），外格不凶"),
             ((0, True), "C 地格吉，外格凶"), ((1, True), "D 地格半吉，外格凶")]

    def pick(L):
        T = a.few if L == 2 else max(2, a.few // 2)
        b = {k: [c for c in allc[L] if (c["di_g"], c["wai_bad"]) == k] for k, _ in ORDER}
        sel, cnt = [], 0
        for i, (k, name) in enumerate(ORDER):
            if (i == 0 or cnt < T) and b[k]:
                sel.append((name, b[k])); cnt += len(b[k])
        # 展示上限: 组合太多时按综合评分只取前几名, 保持分层
        cap = a.max_show if L == 2 else max(3, a.max_show // 2)
        dropped = 0
        if cnt > cap:
            ranked = sorted(((c, nm) for nm, g in sel for c in g), key=lambda x: -combo_score(x[0], L))[:cap]
            keep = {id(c) for c, _ in ranked}
            sel = [(nm, [c for c in g if id(c) in keep]) for nm, g in sel]
            sel = [(nm, g) for nm, g in sel if g]
            dropped = cnt - cap
        return sel, T, len(b[ORDER[0][0]]), dropped

    shown, used = {}, set()
    for L in lens:
        sel, T, nA, dropped = pick(L)
        shown[L] = sel
        total = sum(len(g) for _, g in sel)
        print(f"## {'单名' if L == 1 else '双名'}：筛选后的笔画组合（共 {total} 个）\n")
        if L == 1:
            print("单名的人格和总格是同一个数；外格恒为 2（评语为凶，是单名的结构性特点，不参与判断）。\n")
        if not sel:
            print("没有满足条件的组合。\n"); continue
        if len(sel) > 1:
            print(f"> A 类（地格吉、外格不凶）只有 {nA} 个，少于 {T} 个，所以按层补充了：{'、'.join(n for n, _ in sel[1:])}。\n")
        else:
            print(f"> A 类（地格吉、外格不凶）有 {nA} 个，已经足够，其余层级不再列出。\n")
        for name, grp in sel:
            grp.sort(key=lambda c: (-c["rel_score"], c["strokes"]))
            print(f"### {name}（{len(grp)} 个）\n")
            if L == 1:
                print("| 名字笔画 | 人格=总格 | 地格 | 三才 | 三才关系 | 可选字数 |")
                print("|---|---|---|---|---|---|")
                for c in grp:
                    g = c["ge"]; used.update(c["strokes"])
                    print(f"| {c['strokes'][0]} | {g['人格']}{lab(shuli[g['人格']])} | {g['地格']}{lab(shuli[g['地格']])} | "
                          f"{c['sancai']} | {c['rel']} | {c['n'][0]} |")
            else:
                print("| 笔画 | 人格 | 地格 | 外格 | 总格 | 三才 | 三才关系 | 可选字数 |")
                print("|---|---|---|---|---|---|---|---|")
                for c in grp:
                    g = c["ge"]; used.update(c["strokes"])
                    wai = f"{g['外格']}{lab(shuli[g['外格']])}" + ("⚠女性不宜" if fem_bad(g["外格"]) else "")
                    print(f"| {'+'.join(map(str, S))}+{c['strokes'][0]}+{c['strokes'][1]} | {g['人格']}{lab(shuli[g['人格']])} | "
                          f"{g['地格']}{lab(shuli[g['地格']])} | {wai} | {g['总格']}{lab(shuli[g['总格']])} | "
                          f"{c['sancai']} | {c['rel']} | {c['n'][0]}/{c['n'][1]} |")
            print()
        extra = []
        if dropped:
            extra.append(f"同层级中综合评分靠后的 {dropped} 个（只取前 {a.max_show if L == 2 else max(3, a.max_show // 2)} 个，可用 --max-show 调整）")
        if stats[L]["地格凶"]: extra.append(f"地格凶的 {stats[L]['地格凶']} 个")
        if stats[L]["字太少"]: extra.append(f"某个笔画下可选字少于 {a.min_chars} 个的 {stats[L]['字太少']} 个")
        omitted = len(allc[L]) - total - dropped
        if omitted > 0: extra.append(f"满足条件但层级较低、这次不需要的 {omitted} 个")
        if extra:
            print(f"*未列出：{'；'.join(extra)}。*\n")

    # ---- 建议的笔画组合 ----
    print("## 建议的笔画组合\n")
    print("综合排序依据：地格吉优先；外格不凶；三才相生或比和更好；每个笔画下可选字多、好选；笔画过繁（超过 20 画）扣分较多。\n")
    for L in lens:
        cand = [c for _, g in shown.get(L, []) for c in g]
        if not cand:
            continue

        cand.sort(key=lambda c: -combo_score(c, L))
        print(f"**{'单名' if L == 1 else '双名'}**")
        for c in cand[:a.top]:
            g = c["ge"]; why = []
            if c["di_g"] == 0 and (L == 1 or shuli[g["外格"]]["solid_ji"]):
                why.append("人格、总格、地格" + ("" if L == 1 else "、外格") + "全是吉")
            elif c["di_g"] == 0:
                why.append("人格、总格、地格是吉")
            else:
                why.append("人格、总格吉，地格半吉")
            why.append("三才" + c["rel"].replace("；", "，"))
            why.append("可选字 " + (f"{c['n'][0]} 个" if L == 1 else f"{c['n'][0]}/{c['n'][1]} 个"))
            if L == 2 and fem_bad(g["外格"]): why.append("外格是女性不宜数，需留意")
            tag = f"{c['strokes'][0]} 画" if L == 1 else f"{'+'.join(map(str, S))}+{c['strokes'][0]}+{c['strokes'][1]}"
            print(f"- **{tag}**：" + "；".join(why))
        print()

    # ---- 字表: 只列出用到的笔画 ----
    opp = {"男": "女", "女": "男"}.get(a.gender)
    print(f"## 可选的字（按康熙笔画，五行属 {'、'.join(els)}，只列上面组合用到的笔画）\n")
    print(f"范围：通用规范汉字{'一级' if (a.max_level == 1 or a.chars_level == 1) else '一、二级'}字，康熙笔画可靠，"
          f"已剔除明显不宜入名的字 {len(removed)} 个（如死、病、粪、毙，完整名单见末尾）。不按\"是否常见名用字\"过滤。"
          + ("字后标 ♂ 表示这个字在真实人名里明显偏男性使用，仅供参考。" if opp == "男" else "")
          + ("字后标 ♀ 表示这个字在真实人名里明显偏女性使用，仅供参考。" if opp == "女" else "")
          + "字后标 † 表示这个字的康熙笔画只有多个来源互相一致、没能在康熙字典原书里核验，要用的话建议自己再核对一下。\n")

    def mark(c):
        mk = "†" if chars[c]["evidence"] in ("D", "X") else ""
        if opp:
            m, f = freq.get(c, (0, 0))
            if m + f >= 30:
                if a.gender == "女" and m / (m + f) > 0.85: mk += "♂"
                if a.gender == "男" and f / (m + f) > 0.85: mk += "♀"
        return mk
    for st in sorted(used):
        print(f"**{st} 画**")
        for wx in els:
            cs = pool.get(st, {}).get(wx, [])
            l1 = [r for r in cs if r["level"] == "1"]
            l2 = [r for r in cs if r["level"] != "1"]
            if not cs:
                continue
            print(f"- {wx}：" + (" ".join(r["char"] + mark(r["char"]) for r in l1) if l1 else "（无一级字）") + f"（{len(l1)}）")
            if a.chars_level == 2 and l2:
                print(f"  - 二级字（{len(l2)}）：" + " ".join(r["char"] + mark(r["char"]) for r in l2))
        print()
    print(f"**已剔除的字（{len(removed)} 个，属于喜用神五行但明显不宜入名）**：" + " ".join(sorted(removed)))


if __name__ == "__main__":
    main()

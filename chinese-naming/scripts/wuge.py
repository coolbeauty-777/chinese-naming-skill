#!/usr/bin/env python3
"""五格计算 + 吉凶查询 + 可行性统计。

规则 (传统五格剖象法, 康熙笔画):
  单姓双名  天=S+1   人=S+a    地=a+b   外=b+1    总=S+a+b
  单姓单名  天=S+1   人=S+a    地=a+1   外=2      总=S+a      (人格==总格)
  复姓双名  天=S1+S2 人=S2+a   地=a+b   外=S1+b   总=S1+S2+a+b
  复姓单名  天=S1+S2 人=S2+a   地=a+1   外=S1+1   总=S1+S2+a
  数大于 81 时减 80 取余; 数理五行按末位: 1,2木 3,4火 5,6土 7,8金 9,0水
"""
import argparse, csv, json, itertools
from pathlib import Path

HERE = Path(__file__).resolve().parent
WUXING = {0: "水", 1: "木", 2: "木", 3: "火", 4: "火", 5: "土", 6: "土", 7: "金", 8: "金", 9: "水"}


def fold(n):
    return (n - 1) % 80 + 1 if n > 81 else n


def wuge(surname, given):
    """surname/given: 各字康熙笔画列表, 姓 1-2 字, 名 1-2 字"""
    assert len(surname) in (1, 2) and len(given) in (1, 2)
    if len(surname) == 1:
        S = surname[0]; tian = S + 1; ren_base = S; wai_front = 1
    else:
        S1, S2 = surname; tian = S1 + S2; ren_base = S2; wai_front = S1
    if len(given) == 1:
        a = given[0]; di = a + 1; wai = wai_front + 1
        if len(surname) == 1:
            wai = 2
    else:
        a, b = given; di = a + b; wai = wai_front + b
        if len(surname) == 1:
            wai = b + 1
    ren = ren_base + a
    zong = sum(surname) + sum(given)
    out = {"天格": tian, "人格": ren, "地格": di, "外格": wai, "总格": zong}
    return {k: fold(v) for k, v in out.items()}


def load_shuli():
    d = json.load(open(HERE.parent / "data" / "shuli_81.json", encoding="utf-8"))
    return {t["n"]: t for t in d["table"]}, d["female"]


def load_chars():
    """返回 {字: 行字典}; 行含 kx(康熙笔画) wx(汉字五行) level pinyin def_zh verify ..."""
    p = HERE.parent / "data" / "chars.csv"
    return {r["char"]: r for r in csv.DictReader(open(p, encoding="utf-8"))}


def load_strokes():
    return {c: int(r["kx"]) for c, r in load_chars().items()}


def analyze(surname, given, chars=None, shuli=None):
    """分析一个具体姓名, 返回结构化结果。字不在字库时抛出 KeyError 并指明哪个字。"""
    chars = chars or load_chars(); shuli = shuli or load_shuli()[0]
    detail = []
    for c in surname + given:
        if c not in chars:
            raise KeyError(f"字库中没有「{c}」(非通用规范汉字或太生僻), 请改字或手动给笔画")
        detail.append(chars[c])
    ge = wuge([int(chars[c]["kx"]) for c in surname], [int(chars[c]["kx"]) for c in given])
    return {"姓名": surname + given, "字": detail, "五格": ge,
            "三才": "".join(WUXING[ge[k] % 10] for k in ("天格", "人格", "地格")),
            "评语": {k: {"数": n, "数理五行": shuli[n]["wuxing"], "评语": sum(shuli[n]["labels"].values(), []),
                      "稳吉": shuli[n]["solid_ji"], "有争议": shuli[n]["disputed"], "女性": shuli[n]["female"]}
                   for k, n in ge.items()}}


def describe(ge, shuli):
    rows = []
    for k, n in ge.items():
        t = shuli[n]
        rows.append(f"{k} {n:2d} 数理五行={t['wuxing']} 评语={'/'.join(sum(t['labels'].values(), []))}"
                    f"{' [有争议]' if t['disputed'] else ''}{' [女性不宜]' if t['female']=='avoid' else ''}")
    return "\n".join(rows)


def feasibility(S, shuli, female=False, level="solid_ji", lo=1, hi=25):
    """给定单姓笔画 S, 统计 人格 & 总格 同时满足条件的名字笔画组合数"""
    ok = lambda n: shuli[fold(n)][level] and not (female and shuli[fold(n)]["female"] == "avoid")
    single = [a for a in range(lo, hi + 1) if ok(S + a)]                      # 单名: 人格==总格
    double = [(a, b) for a, b in itertools.product(range(lo, hi + 1), repeat=2) if ok(S + a) and ok(S + a + b)]
    return len(single), len(double), (hi - lo + 1), (hi - lo + 1) ** 2


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--surname"); ap.add_argument("--given")
    ap.add_argument("--strokes", help="直接给笔画, 如 7:8 表示姓7画名8画; 复姓/双名用逗号 15,17:11,20")
    ap.add_argument("--feasibility", action="store_true")
    a = ap.parse_args()
    shuli, _ = load_shuli()
    if a.feasibility:
        st = load_strokes()
        print(f"{'姓':<3}{'笔画':<5}{'单名可选(男)':<12}{'双名可选(男)':<14}{'单名(女)':<10}{'双名(女)':<10}   [稳吉 / 稳吉且有大吉]")
        for s in "王李张刘陈杨黄赵周吴徐孙马朱胡林何高郭罗梁":
            S = st[s]
            r1 = feasibility(S, shuli, False); r2 = feasibility(S, shuli, True)
            r3 = feasibility(S, shuli, False, "top_ji")
            print(f"{s:<3}{S:<5}{r1[0]:>2}/25 ({r1[0]/25:.0%})  {r1[1]:>3}/625 ({r1[1]/625:.0%})  "
                  f"{r2[0]:>2}/25     {r2[1]:>3}/625     | 大吉: {r3[0]:>2}/25  {r3[1]:>3}/625 ({r3[1]/625:.0%})")
    else:
        if a.strokes:
            sur, giv = [list(map(int, x.split(","))) for x in a.strokes.split(":")]
            ge = wuge(sur, giv)
            print(describe(ge, shuli))
            print("三才(天人地)数理五行:", "".join(WUXING[ge[k] % 10] for k in ("天格", "人格", "地格")))
        else:
            try:
                r = analyze(a.surname, a.given)
            except KeyError as e:
                print(f"无法分析: {e.args[0]}"); raise SystemExit(2)
            for row in r["字"]:
                note = {"verified": "", "narrowed": " [笔画可能有±1误差]", "policy_dual": f" [本字/繁体字形笔画不同,取舍,备选{row['alt']}]",
                        "unverified": " [仅多来源一致,未能在原书核验]", "page_conflict": " [仅多来源一致,原书页位不同]",
                        "text_note": " [以《康熙字典》原文标注为准]", "no_source_in_interval": " [来源与原书页位都不符,需核对]"}.get(row["verify"], "")
                print(f"{row['char']}  康熙{row['kx']}画  五行={row['wx'] or '未知'}({row['wx_src']})  {row['pinyin']}{note}")
            print(describe(r["五格"], shuli))
            print("三才(天人地)数理五行:", r["三才"])

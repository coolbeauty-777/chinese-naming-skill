#!/usr/bin/env python3
"""以《康熙字典》原书排版为准, 裁决三方笔画分歧。

对每个字, 用原书页位反推"部外笔画"区间 (相邻同部字的笔画上下夹逼):
    下界 = 前 2 个同部字部外笔画的最大值
    上界 = 后 2 个同部字部外笔画的最小值
康熙笔画区间 = 部首笔画 + 部外笔画区间。三方来源的数值落在区间内才算"被原书支持"。

状态:
  verified     三方值中恰有一种被原书支持 (或区间唯一确定且与某来源吻合)
  policy_dual  本字与繁体字形各自都被原书支持, 属"取哪个字形"的取舍问题 (如 于3/於8)
  unverified   无法在原书中定位 (没有页位/部), 沿用多数票
"""
import argparse, bisect, collections, csv, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_chars as bc
import kangxi_page_check as kp


def interval(ch, bu, name2n, pos, anchors, order=None):
    """返回 (康熙笔画下界, 上界) 或 None"""
    pp = pos.get(ch) or kp.POS_VIRT.get(ch)
    if not pp:
        return None
    b_text = bu.get(ch)
    b_page = kp.infer_bu(ch, pos, order) if order else None
    if b_text and b_page and b_text != b_page:
        return None                       # 原文所属部与页位所在部对不上: 页位指向的是另一个字, 证据作废
    bname = b_text or b_page
    if not bname:
        return None
    n = name2n.get(bname)
    if not n or n not in anchors:
        return None
    lst = anchors[n]
    keys = [(a[0], a[1]) for a in lst]
    i = bisect.bisect_left(keys, pp)
    j = i + 1 if i < len(lst) and lst[i][3] == ch else i
    prev = [a[2] for a in lst[max(0, i - 2):i] if a[3] != ch]
    nxt = [a[2] for a in lst[j:j + 2] if a[3] != ch]
    if not prev and not nxt:
        return None
    lo = max(prev) if prev else 0          # 排在该部最前面: 下界是 0 (不能用后一个字的笔画)
    hi = min(nxt) if nxt else 99           # 排在该部最后面: 上界不封顶
    if lo > hi:                      # 邻居自相矛盾, 放宽为 [hi, lo]
        lo, hi = hi, lo
    base = bc.KX_RADICAL_STROKES[n]
    return base + lo, base + hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unihan", required=True)
    ap.add_argument("--shunshi-data", required=True)
    ap.add_argument("--cantian")
    ap.add_argument("--data-dir", default=str(Path(__file__).resolve().parents[2] / "data"))
    a = ap.parse_args()

    bc.WANT.add("kZVariant")
    U = bc.load_unihan(a.unihan)
    bu = kp.load_bu(a.shunshi_data)
    name2n, pos, anchors = kp.build_index(U, bu)
    order = kp.build_bu_order(pos, bu)
    sh = dict(json.load(__import__("gzip").open(Path(a.shunshi_data) / "chars.json.gz", "rt", encoding="utf-8")))["chars"]
    ct = {}
    if a.cantian:
        ct = {x["simplified"]: x["wugeStrokeCount"] for x in json.load(open(a.cantian, encoding="utf-8"))}

    ktext = json.load(__import__("gzip").open(Path(a.shunshi_data) / "kangxi-text.json.gz", "rt", encoding="utf-8"))
    note_pat = re.compile(r"康熙筆画[：:]\s*(\d+)")
    notes = {k: int(m.group(1)) for k, v in ktext.items() if (m := note_pat.search(v[:200]))}
    FOLD_EXEMPT = {"万"}          # 万: 原文本字 3 画, 但姓名学约定折成"萬"(15), 沿用折算值
    dd = Path(a.data_dir)
    rows = list(csv.DictReader(open(dd / "kangxi_strokes.csv", encoding="utf-8-sig")))
    stat = collections.Counter()
    src_hit = collections.defaultdict(lambda: [0, 0])      # 来源 -> [被支持数, 参与数]
    out_rows, remain = [], []
    for r in rows:
        ch, form = r["char"], r["kangxi_form"]
        vals = {"ours": int(r["kx_ours_v2"]), "shunshi": sh[ch]["kx"] if ch in sh else None, "cantian": ct.get(ch)}
        vals = {k: v for k, v in vals.items() if v is not None}
        iv_form = interval(form, bu, name2n, pos, anchors, order)
        iv_self = interval(ch, bu, name2n, pos, anchors, order) if ch != form else None
        ivs = [iv for iv in (iv_form, iv_self) if iv]
        via_var = False
        if not ivs:                       # 康熙字典用的是异体写法(淸/靑/靜/戶/敎...): 顺着 Z 异体字找
            for base in {form, ch}:
                for v in bc.parse_variants(U.get(bc.cp_of(base), {}).get("kZVariant")):
                    iv = interval(v, bu, name2n, pos, anchors, order)
                    if iv:
                        ivs.append(iv); via_var = True
                        if iv_form is None:
                            iv_form = iv
        r2 = dict(r)
        r2["kx_page_interval"] = f"{iv_form[0]}-{iv_form[1]}" if iv_form else ""
        if not ivs:
            r2["kx_verify"] = "unverified"; stat["unverified"] += 1
            out_rows.append(r2); continue
        supported = {v for v in vals.values() if any(lo <= v <= hi for lo, hi in ivs)}
        # 单点区间时, 即使没有来源命中, 也直接采用原书值
        pts = {lo for lo, hi in ivs if lo == hi}
        for k, v in vals.items():
            src_hit[k][1] += 1
            if any(lo <= v <= hi for lo, hi in ivs):
                src_hit[k][0] += 1
        # 三方(或可用的全部来源)一致、但原书页位不支持 => 多为"分类特例"(如 王 被归在玉部), 保留共识值并标记
        if not supported and len(vals) >= 2 and len(set(vals.values())) == 1:
            r2["kx_strokes"] = next(iter(vals.values())); r2["kx_verify"] = "page_conflict"
            stat["page_conflict"] += 1; remain.append(r2); out_rows.append(r2); continue
        cand = supported                     # 原书页位只用来在已有候选值里做选择, 绝不凭空采用没有来源支持的数
        # 本字/繁体 两个字形各有支持值 -> 取舍问题
        sv_form = {v for v in vals.values() if iv_form and iv_form[0] <= v <= iv_form[1]}
        sv_self = {v for v in vals.values() if iv_self and iv_self[0] <= v <= iv_self[1]}
        if sv_form and sv_self and sv_form != sv_self:
            r2["kx_verify"] = "policy_dual"; stat["policy_dual"] += 1
            r2["kx_strokes"] = min(sv_self)               # 默认本字
            r2["kx_alt"] = ",".join(map(str, sorted(sv_form)))
            remain.append(r2)
        elif len(cand) == 1:
            r2["kx_strokes"] = next(iter(cand)); r2["kx_verify"] = "verified"; stat["verified"] += 1
            r2["kx_via_variant"] = "1" if via_var else ""
        elif len(cand) > 1:
            # 区间内有多个来源值: 取区间内与多数一致者, 仍算"部分验证"
            cnt = collections.Counter(v for v in vals.values() if v in cand)
            r2["kx_strokes"] = cnt.most_common(1)[0][0]; r2["kx_verify"] = "narrowed"; stat["narrowed"] += 1
        else:
            r2["kx_verify"] = "no_source_in_interval"; stat["no_source_in_interval"] += 1
            remain.append(r2)
        out_rows.append(r2)

    # ---- 最高优先级: 《康熙字典》原文自带的"康熙笔画"标注 ----
    n_note = 0
    for r in out_rows:
        ch, form = r["char"], r["kangxi_form"]
        tv = None if ch in FOLD_EXEMPT else notes.get(ch)
        if tv is None and form != ch:
            tv = notes.get(form)
        if tv is not None and str(tv) != str(r["kx_strokes"]):
            r["kx_note_old"] = r["kx_strokes"]; r["kx_strokes"] = tv; r["kx_verify"] = "text_note"; n_note += 1
    print(f"原文自带康熙笔画标注 {len(notes)} 条; 因此改动的字: {n_note} 个")

    # ---- 部首字本身又是繁体字的简化(儿/兒 气/氣 无/無 网/網 里/裏 ...): 同于/余, 归为"取舍字" ----
    radset = {bc.radical_char(n): n for n in range(1, 215)}
    n_dual = 0
    for r in out_rows:
        n = radset.get(r["char"])
        if n and r["kangxi_form"] != r["char"] and str(r["kx_strokes"]) != str(bc.KX_RADICAL_STROKES[n]) \
                and r["kx_verify"] in ("verified", "narrowed", "page_conflict", "unverified"):
            r["kx_alt"] = r["kx_strokes"]; r["kx_strokes"] = bc.KX_RADICAL_STROKES[n]; r["kx_verify"] = "policy_dual"; n_dual += 1
    print(f"部首字归为取舍字: {n_dual} 个")

    # ---- 证据等级 ----
    #  A 原文自带康熙笔画标注 | B 原书正文页位核验 | C 原书页位核验(原书用异体字形, 强度稍弱)
    #  D 仅多个来源一致(原书定位不到或页位冲突) | X 需人工取舍或无依据
    for r in out_rows:
        v = r["kx_verify"]
        if v == "text_note":
            ev = "A"
        elif v in ("verified", "narrowed"):
            ev = "B" if (r["char"] in pos or r["kangxi_form"] in pos) and not r.get("kx_via_variant") else "C"
        elif v in ("unverified", "page_conflict"):
            ev = "D"
        else:
            ev = "X"
        r["kx_evidence"] = ev

    keys = list(out_rows[0].keys())
    for r in out_rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    for r in out_rows:
        for k in keys:
            r.setdefault(k, "")
    with open(dd / "kangxi_strokes.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(out_rows)

    tgh = [r for r in out_rows if r["in_tgh"] == "1"]
    print("全部字:", dict(stat))
    print("通用规范汉字:", dict(collections.Counter(r["kx_verify"] for r in tgh)))
    print("\n各来源的值被康熙原书页位支持的比例 (越高越可靠):")
    for k, (h, n) in src_hit.items():
        print(f"  {k:8s} {h}/{n} = {h/n:.1%}")
    return out_rows


if __name__ == "__main__":
    main()

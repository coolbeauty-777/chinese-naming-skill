#!/usr/bin/env python3
"""修复康熙笔画并做三方合并。

修复: Unihan 某些字的 kRSUnicode 有多个值 (如 萬 = 114.8 / 140.9), 不能取第一个;
      改为选"部首 == 《康熙字典》原文里该字所属的部"的那个值。
合并: 我们(Unihan) / shunshi-kangxi-core (MIT) / cantian(仅投票校验, 不入库) 三方比对。

用法:
  python merge_strokes.py --unihan Unihan.zip --shunshi-data <npm包 data 目录> \
      [--cantian hanzi.json] --out-dir ../data
"""
import argparse, collections, csv, gzip, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_chars as bc
from opencc import OpenCC

NUMERALS = set("一二三四五六七八九十")


def load_gz(p):
    return json.load(gzip.open(p, "rt", encoding="utf-8"))


def pick_rs(f, U, bu):
    """返回 (部首号, 康熙笔画) 或 None。f 是康熙字形。"""
    d = U.get(bc.cp_of(f))
    if not d or "kRSUnicode" not in d:
        return None
    cands = []
    for tok in d["kRSUnicode"].split():
        m = re.match(r"(\d+)('*)\.(-?\d+)", tok)
        if m:
            n, prime, r = int(m[1]), bool(m[2]), int(m[3])
            cands.append((n, prime, bc.KX_RADICAL_STROKES[n] + r))
    if not cands:
        return None
    want = bu.get(f)
    pick = [c for c in cands if want and bc.radical_char(c[0]) == want] or cands
    pick = [c for c in pick if not c[1]] or pick
    return pick[0][0], pick[0][2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unihan", required=True)
    ap.add_argument("--shunshi-data", required=True)
    ap.add_argument("--cantian")
    ap.add_argument("--out-dir", default=str(Path(__file__).resolve().parents[2] / "data"))
    a = ap.parse_args()

    U = bc.load_unihan(a.unihan)
    sdir = Path(a.shunshi_data)
    sh = dict(load_gz(sdir / "chars.json.gz"))["chars"]
    ktext = load_gz(sdir / "kangxi-text.json.gz")
    bu = {}
    for k, t in ktext.items():
        m = re.search(r"【([^】【]+?)字部】", t[:40])
        if m:
            bu[k] = m.group(1)
    ct = {}
    if a.cantian:
        ct = {x["simplified"]: x["wugeStrokeCount"] for x in json.load(open(a.cantian, encoding="utf-8"))}

    cc = OpenCC("s2t")
    base = list(csv.DictReader(open(Path(a.out_dir) / "kangxi_strokes.csv", encoding="utf-8-sig")))

    fixed = 0
    rows, review = [], []
    stat = collections.Counter()
    for r in base:
        ch = r["char"]; form = r["kangxi_form"]
        old = int(r["kx_strokes"])
        info = pick_rs(form, U, bu) or pick_rs(ch, U, bu)
        ours = info[1] if info else old
        if ours != old:
            fixed += 1
        s_v = sh[ch]["kx"] if ch in sh else None
        c_v = ct.get(ch)
        vals = {"ours": ours, "shunshi": s_v, "cantian": c_v}
        have = {k: v for k, v in vals.items() if v is not None}
        cnt = collections.Counter(have.values())
        top, topn = cnt.most_common(1)[0]
        if len(cnt) == 1:
            status = "agree_all" if len(have) >= 2 else "single_source"
            final = top
        elif topn >= 2:
            # 多数一致; 但若多数是 shunshi+cantian 且与我们不同, 且我们用的是本字(没做繁体转换), 视为"折叠争议"
            majority_srcs = [k for k, v in have.items() if v == top]
            if "ours" not in majority_srcs and form == ch:
                status, final = "review_fold", ours      # 默认取本字(我们)
            else:
                status, final = "agree_2of3", top
        else:
            status, final = "review_split", ours
        if ch in NUMERALS and len(set(have.values())) > 1:
            status = "numeral_convention"
            final = ours                                  # 默认取康熙实际笔画
        stat[status] += 1
        tgh = U.get(bc.cp_of(ch), {}).get("kTGH", "")
        m_t = re.search(r":(\d+)", tgh)
        seq = int(m_t.group(1)) if m_t else 0
        level = 1 if 0 < seq <= 3500 else 2 if 3500 < seq <= 6500 else 3 if seq > 6500 else ""
        minority = ",".join(k for k, v in have.items() if v != final) if len(cnt) > 1 else ""
        r2 = dict(r)
        r2["level"] = level
        r2["kx_strokes"] = final
        r2["kx_ours_v2"] = ours
        r2["kx_shunshi"] = s_v if s_v is not None else ""
        r2["kx_status"] = status
        rows.append(r2)
        if status not in ("agree_all", "single_source"):
            review.append({"char": ch, "form": form, "level_tgh": r["in_tgh"], "level": level,
                           "minority": minority, "status": status,
                           "ours": ours, "shunshi": s_v, "cantian": c_v, "default_final": final,
                           "flags": r["flags"]})

    order = {"review_split": 0, "review_fold": 1, "numeral_convention": 2, "agree_2of3": 3}
    review.sort(key=lambda x: (x["level"] or 9, order.get(x["status"], 9), x["char"]))
    out = Path(a.out_dir)
    keep = list(rows[0].keys())
    with open(out / "kangxi_strokes.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=keep); w.writeheader(); w.writerows(rows)
    with open(out / "stroke_review.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(review[0].keys())); w.writeheader(); w.writerows(review)

    byl = collections.Counter((x["level"], x["status"], x["minority"]) for x in review if x["level"])
    print("\n复核清单按(级别,状态,少数派)计数:")
    for k, v in sorted(byl.items(), key=lambda kv: (kv[0][0], -kv[1])):
        print("  ", k, v)
    tgh = [r for r in rows if r["in_tgh"] == "1"]
    print(f"修复多值/部首选择后, 我们自己的笔画变化 {fixed} 字")
    print("全部字 status:", dict(stat))
    c2 = collections.Counter(r["kx_status"] for r in tgh)
    print("通用规范汉字 status:", dict(c2))
    rv = [x for x in review if x["level_tgh"] == "1"]
    print(f"需复核(通用规范汉字): {len(rv)}  -> review_fold {sum(x['status']=='review_fold' for x in rv)}, "
          f"review_split {sum(x['status']=='review_split' for x in rv)}, numeral {sum(x['status']=='numeral_convention' for x in rv)}")


if __name__ == "__main__":
    main()

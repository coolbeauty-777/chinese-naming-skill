#!/usr/bin/env python3
"""从 Unihan 生成起名用的康熙笔画基础字库。

用法:
    python build_chars.py --unihan Unihan.zip [--xinhua xinhua_word.json] [--out ../data/kangxi_strokes.csv]

康熙笔画 = 康熙部首笔画 + 余画
  - 余画来自 Unihan 的 kRSUnicode (格式 "部首号.余画")
  - 简体字先转成繁体字形再计算 (氵=水=4画, 艹=艸=6画, 辶=辵=7画, 阝=阜/邑=8/7画 ...)
  - kKangXi 存在表示该字形在《康熙字典》中有条目
"""
import argparse, collections, csv, io, json, re, unicodedata, zipfile
from pathlib import Path

from opencc import OpenCC

# ---- 康熙 214 部首的笔画数 (按笔画分段, 部首号区间) ----
_RANGES = [(1, 6, 1), (7, 29, 2), (30, 60, 3), (61, 94, 4), (95, 117, 5),
           (118, 146, 6), (147, 166, 7), (167, 175, 8), (176, 186, 9),
           (187, 194, 10), (195, 200, 11), (201, 204, 12), (205, 208, 13),
           (209, 210, 14), (211, 211, 15), (212, 213, 16), (214, 214, 17)]
KX_RADICAL_STROKES = {n: s for a, b, s in _RANGES for n in range(a, b + 1)}
assert len(KX_RADICAL_STROKES) == 214


def radical_char(n):
    """康熙部首号 -> 对应汉字 (U+2F00 起的康熙部首区, NFKC 归一化)"""
    return unicodedata.normalize("NFKC", chr(0x2F00 + n - 1))


WANT = {"kRSUnicode", "kTotalStrokes", "kKangXi", "kMandarin", "kDefinition",
        "kTraditionalVariant", "kSimplifiedVariant", "kTGH", "kGB0", "kBigFive",
        "kGradeLevel"}


def load_unihan(zip_path):
    data = collections.defaultdict(dict)
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            with z.open(name) as f:
                for line in io.TextIOWrapper(f, encoding="utf-8"):
                    if line.startswith("#") or "\t" not in line:
                        continue
                    cp, field, val = line.rstrip("\n").split("\t", 2)
                    if field in WANT:
                        data[cp][field] = val
    return data


def cp_of(ch):
    return "U+%04X" % ord(ch)


def parse_variants(val):
    """'U+8FD9 U+9019<kLau' -> ['这','這']"""
    out = []
    for tok in (val or "").split():
        m = re.match(r"U\+([0-9A-F]+)", tok)
        if m:
            out.append(chr(int(m.group(1), 16)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unihan", required=True)
    ap.add_argument("--xinhua")
    ap.add_argument("--out", default="kangxi_strokes.csv")
    args = ap.parse_args()

    U = load_unihan(args.unihan)
    cc = OpenCC("s2t")

    xin = {}
    if args.xinhua:
        for e in json.load(open(args.xinhua, encoding="utf-8")):
            exp = re.sub(r"\s+", " ", e.get("explanation", "")).strip()
            xin[e["word"]] = exp[:120]

    def rs(ch):
        """返回 (部首号, 是否简化部首, 康熙笔画, 现代总笔画) 或 None"""
        d = U.get(cp_of(ch))
        if not d or "kRSUnicode" not in d:
            return None
        m = re.match(r"(\d+)('*)\.(-?\d+)", d["kRSUnicode"].split()[0])
        if not m:
            return None
        n, prime, r = int(m[1]), m[2], int(m[3])
        total = int(d["kTotalStrokes"].split()[0]) if "kTotalStrokes" in d else None
        return n, bool(prime), KX_RADICAL_STROKES[n] + r, total

    # 起名可用字范围: 通用规范汉字(kTGH) ∪ GB2312 ∪ Big5
    chars = []
    for cp, d in U.items():
        if any(k in d for k in ("kTGH", "kGB0", "kBigFive")):
            chars.append(chr(int(cp[2:], 16)))
    chars.sort()

    rows = []
    for ch in chars:
        d = U[cp_of(ch)]
        flags = []
        form = cc.convert(ch)            # 康熙字形 (繁体)
        if len(form) != 1:
            form = ch
        trad_list = [t for t in parse_variants(d.get("kTraditionalVariant")) if t != ch]
        if form != ch:
            if "kKangXi" in d:
                flags.append("dual")           # 本字本身也是康熙字典字(如 后/後, 干/乾)
            if len(trad_list) > 1:
                flags.append("multi_trad:" + "".join(trad_list))
        info = rs(form) or rs(ch)
        if info is None:
            flags.append("no_rs")
            continue
        n, prime, kx, total = info
        if prime:
            flags.append("simp_radical")      # 余画按简化部首数的, 笔画不可靠
        alt = rs(ch) if "dual" in flags else None
        fd = U.get(cp_of(form), {})
        rows.append({
            "char": ch,
            "kangxi_form": form,
            "radical_no": n,
            "radical": radical_char(n),
            "kx_strokes": kx,
            "alt_strokes": alt[2] if alt else "",
            "modern_strokes": total if total is not None else "",
            "in_kangxi_dict": int("kKangXi" in fd),
            "in_tgh": int("kTGH" in d),
            "pinyin": (d.get("kMandarin") or fd.get("kMandarin") or "").replace(" ", "/"),
            "grade": d.get("kGradeLevel", ""),
            "def_en": (d.get("kDefinition") or fd.get("kDefinition") or "")[:80],
            "def_zh": xin.get(ch) or xin.get(form, ""),
            "flags": ";".join(flags),
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- 内部一致性校验: 同一部首下, 康熙笔画-现代笔画 的差值应基本一致 ----
    by_rad = collections.defaultdict(collections.Counter)
    for r in rows:
        if r["modern_strokes"] != "":
            by_rad[r["radical_no"]][r["kx_strokes"] - r["modern_strokes"]] += 1
    print(f"写出 {len(rows)} 个字 -> {out}")
    print("flags 统计:", collections.Counter(
        x.split(":")[0] for r in rows for x in r["flags"].split(";") if x))
    print("\n部首差值分布 (康熙-现代), 仅列出存在多种差值的部首:")
    for n, c in sorted(by_rad.items()):
        if len(c) > 1:
            print(f"  {n:3d} {radical_char(n)}  {dict(c.most_common())}")


if __name__ == "__main__":
    main()

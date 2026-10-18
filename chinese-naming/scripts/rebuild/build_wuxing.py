#!/usr/bin/env python3
"""生成最终字库 data/chars.csv (仅通用规范汉字, 即中国大陆姓名可用字范围)。

汉字五行来源 (wx_src):
  shunshi      shunshi-kangxi-core 的五行标注 (MIT)
  radical_rule 缺标注的字, 按"康熙部首 -> 多数五行"规则推断 (规则从 shunshi 标注中学得,
               只采用 样本>=8 且 某五行占比>=85% 的部首)
  none         无法判断, 默认不参与按五行的筛选

用法: python build_wuxing.py --shunshi-data <data目录> --data-dir ../data
"""
import argparse, collections, csv, gzip, json, random
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shunshi-data", required=True)
    ap.add_argument("--data-dir", default=str(Path(__file__).resolve().parents[2] / "data"))
    a = ap.parse_args()
    dd = Path(a.data_dir)

    sh = dict(json.load(gzip.open(Path(a.shunshi_data) / "chars.json.gz", "rt", encoding="utf-8")))["chars"]
    rows = [r for r in csv.DictReader(open(dd / "kangxi_strokes.csv", encoding="utf-8-sig")) if r["in_tgh"] == "1"]

    def learn(train):
        by = collections.defaultdict(collections.Counter)
        for r in train:
            by[r["radical"]][r["wx"]] += 1
        rule = {}
        for rad, c in by.items():
            tot = sum(c.values()); el, n = c.most_common(1)[0]
            if tot >= 8 and n / tot >= 0.85:
                rule[rad] = el
        return rule

    for r in rows:
        r["wx"] = (sh.get(r["char"]) or {}).get("wx") or ""
    labeled = [r for r in rows if r["wx"]]

    # 5 折交叉验证: 规则在没见过的字上准确率如何
    random.seed(7); random.shuffle(labeled)
    hit = tot = covered = 0
    for k in range(5):
        test = labeled[k::5]; train = [r for i, r in enumerate(labeled) if i % 5 != k]
        rule = learn(train)
        for r in test:
            tot += 1
            if r["radical"] in rule:
                covered += 1; hit += rule[r["radical"]] == r["wx"]
    print(f"[交叉验证] 偏旁规则覆盖 {covered}/{tot} ({covered/tot:.0%}), 覆盖部分准确率 {hit/covered:.1%}")

    rule = learn(labeled)
    print("采用的部首规则:", " ".join(f"{k}→{v}" for k, v in sorted(rule.items(), key=lambda x: x[1])))

    out = []
    src = collections.Counter()
    for r in rows:
        wx, wsrc = r["wx"], "shunshi"
        if not wx:
            if r["radical"] in rule:
                wx, wsrc = rule[r["radical"]], "radical_rule"
            else:
                wx, wsrc = "", "none"
        src[wsrc] += 1
        zh = (r["def_zh"] or "")[:60]
        out.append({"char": r["char"], "trad": r["kangxi_form"], "kx": r["kx_strokes"], "radical": r["radical"],
                    "wx": wx, "wx_src": wsrc, "level": r["level"], "pinyin": r["pinyin"],
                    "def_zh": zh, "def_en": r["def_en"][:50], "verify": r["kx_verify"],
                    "evidence": r.get("kx_evidence", ""), "alt": r.get("kx_alt", ""), "kx_status": r.get("kx_status", ""), "flags": r["flags"]})
    with open(dd / "chars.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print(f"写出 {len(out)} 字 -> {dd/'chars.csv'}  五行来源:", dict(src))
    print("五行分布:", dict(collections.Counter(o['wx'] or '未知' for o in out)))


if __name__ == "__main__":
    main()

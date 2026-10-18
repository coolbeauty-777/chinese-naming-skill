#!/usr/bin/env python3
"""从公开人名语料统计"每个字用在名字里的频率", 作为"适合入名"和"性别倾向"的信号。

语料: wainshine/Chinese-Names-Corpus (Apache-2.0), 文件 Chinese_Names_Corpus_Gender（120W）.txt
只保留聚合计数 (不含任何具体姓名)。

口径: 只取 3 字人名, 其后两个字视为"名" (避免把姓氏计入; 2 字名与 4 字名的拆分有歧义, 跳过)。
输出 data/name_freq.csv: char, n_total, n_male, n_female  (性别"未知"只计入 n_total)
"""
import argparse, collections, csv, glob
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-dir", required=True, help="Chinese_Names_Corpus 目录")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "data" / "name_freq.csv"))
    a = ap.parse_args()
    f = [p for p in glob.glob(str(Path(a.corpus_dir) / "*")) if "Gender" in p][0]
    raw = open(f, "rb").read()
    txt = raw.decode("utf-8-sig", "replace")
    tot, male, fem = collections.Counter(), collections.Counter(), collections.Counter()
    n = 0
    for line in txt.splitlines():
        if "," not in line:
            continue
        name, sex = line.rsplit(",", 1)
        if len(name) != 3 or not all("\u4e00" <= c <= "\u9fff" for c in name):
            continue
        n += 1
        for c in name[1:]:
            tot[c] += 1
            if sex == "男": male[c] += 1
            elif sex == "女": fem[c] += 1
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo); w.writerow(["char", "n_total", "n_male", "n_female"])
        for c, t in tot.most_common():
            if t >= 5:
                w.writerow([c, t, male[c], fem[c]])
    print(f"统计 3 字人名 {n} 个, 输出 {sum(1 for t in tot.values() if t>=5)} 个字 -> {a.out}")


if __name__ == "__main__":
    main()

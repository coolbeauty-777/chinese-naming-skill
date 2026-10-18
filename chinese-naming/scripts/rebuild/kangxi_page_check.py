#!/usr/bin/env python3
"""用《康熙字典》原书的排版顺序反推"部外笔画", 作为独立于三方来源的第四个证据。

原理: 康熙字典每个部内, 字按"部外笔画"从小到大排列。Unihan 的 kKangXi 给出每字在原书的
      页码.位置 (如 0365.370)。一个字前后相邻的、同部的字的部外笔画, 就框定了它自己的部外笔画。
      例: 成 夹在一串部外 3 画的字中间 => 康熙字典把它列为戈部 3 画 => 4+3=7。

输出: 对每个字给出 (部, 部外笔画下界, 上界, 是否唯一确定)。
"""
import bisect, collections, re, sys, gzip, json, statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_chars as bc

K = 4   # 取前后各 K 个同部相邻字


def load_bu(shunshi_data):
    ktext = json.load(gzip.open(Path(shunshi_data) / "kangxi-text.json.gz", "rt", encoding="utf-8"))
    bu = {}
    for k, t in ktext.items():
        m = re.search(r"【([^】【]+?)字部】", t[:40])
        if m:
            bu[k] = m.group(1)
    return bu


POS_VIRT = {}      # 末位=1: 原书里用的是异体字形, 页位记的是该异体字形的位置(目标字可用, 不作邻居锚点)


def build_index(U, bu):
    name2n = {bc.radical_char(n): n for n in range(1, 215)}
    pos = {}                                   # ch -> (page, idx)
    for cp, d in U.items():
        v = d.get("kKangXi")
        if not v:
            continue
        m = re.match(r"(\d{4})\.(\d{2})(\d)", v.split()[0])
        if m and m[3] == "0":                  # 末位 0 = 原书正文条目
            pos[chr(int(cp[2:], 16))] = (int(m[1]), int(m[2]))
        elif m:
            POS_VIRT[chr(int(cp[2:], 16))] = (int(m[1]), int(m[2]))
    # 每个部的页码范围 (由有原文的字投票得到)
    pr = collections.defaultdict(lambda: [10**9, -1])
    for ch, name in bu.items():
        n = name2n.get(name)
        if n and ch in pos:
            pr[n][0] = min(pr[n][0], pos[ch][0]); pr[n][1] = max(pr[n][1], pos[ch][0])
    # 各部的"锚点"表: 页码在该部范围内, 且 kRSUnicode 部首与该部一致的字
    anchors = collections.defaultdict(list)
    for ch, p in pos.items():
        d = U.get(bc.cp_of(ch), {})
        for tok in d.get("kRSUnicode", "").split():
            m = re.match(r"(\d+)('*)\.(-?\d+)", tok)
            if not m or m[2]:
                continue
            n, r = int(m[1]), int(m[3])
            if n in pr and pr[n][0] <= p[0] <= pr[n][1]:
                anchors[n].append((p[0], p[1], r, ch))
    for n in anchors:
        anchors[n].sort()
    return name2n, pos, anchors


def build_bu_order(pos, bu):
    """按原书页位排序的 (页, 位, 部名) 列表, 仅含原文里有部名的字, 用于给没有原文条目的字推断所属部"""
    return sorted((pos[c][0], pos[c][1], bu[c]) for c in bu if c in pos)


def infer_bu(c, pos, order):
    """没有原文条目的字: 看它在原书里前后最近的两个有部名的字, 两者同部则取该部, 否则不推断"""
    p = pos.get(c) or POS_VIRT.get(c)
    if not p:
        return None
    keys = [(a, b) for a, b, _ in order]
    i = bisect.bisect_left(keys, p)
    prev = order[i - 1][2] if i > 0 else None
    nxt = order[i][2] if i < len(order) else None
    return prev if prev == nxt else None


def infer(ch, bu, name2n, pos, anchors):
    """返回 (部首号, lo, hi) 部外笔画范围; 无法推断返回 None"""
    if ch not in pos or ch not in bu:
        return None
    n = name2n.get(bu[ch])
    if not n or n not in anchors:
        return None
    lst = anchors[n]
    keys = [(a[0], a[1]) for a in lst]
    i = bisect.bisect_left(keys, pos[ch])
    before = [a[2] for a in lst[max(0, i - K):i] if a[3] != ch]
    after = [a[2] for a in lst[i + 1 if i < len(lst) and lst[i][3] == ch else i: i + 1 + K] if a[3] != ch]
    if not before and not after:
        return None
    lo = statistics.median(before) if before else statistics.median(after)
    hi = statistics.median(after) if after else statistics.median(before)
    if lo > hi:
        lo, hi = hi, lo
    return n, int(lo), int(hi)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--unihan", required=True)
    ap.add_argument("--shunshi-data", required=True)
    ap.add_argument("chars", nargs="*", help="要查询的字(康熙字形, 繁体)")
    a = ap.parse_args()
    U = bc.load_unihan(a.unihan)
    bu = load_bu(a.shunshi_data)
    name2n, pos, anchors = build_index(U, bu)
    for ch in a.chars:
        r = infer(ch, bu, name2n, pos, anchors)
        if not r:
            print(ch, "无法推断"); continue
        n, lo, hi = r
        print(f"{ch} 部={bu[ch]} 原书页位={pos[ch]}  部外笔画∈[{lo},{hi}] => 康熙笔画∈[{bc.KX_RADICAL_STROKES[n]+lo},{bc.KX_RADICAL_STROKES[n]+hi}]"
              f"{'  (唯一确定)' if lo == hi else ''}")

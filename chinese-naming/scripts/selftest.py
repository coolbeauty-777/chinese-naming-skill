#!/usr/bin/env python3
"""回归自检: 已逐个核实过的关键字的康熙笔画 + 五格公式 + 数理表, 防止数据或脚本改动引入错误。
运行: python selftest.py   (全部通过则输出 OK)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import wuge as wg

VERIFIED = {  # 字: 康熙笔画 (均经原书页位/多来源核实)
    "王": 5, "李": 7, "张": 11, "刘": 15, "陈": 16, "杨": 13, "黄": 12, "赵": 14, "周": 8, "吴": 7,
    "朱": 6, "胡": 11, "沈": 8, "向": 6, "姜": 9, "万": 15, "苏": 22, "钟": 17, "曹": 10, "戴": 18,
    "于": 3, "余": 7, "十": 2, "八": 2, "卜": 2, "成": 7, "诚": 14, "城": 10, "盛": 12, "海": 11, "明": 8, "母": 4, "水": 4,
    "浩": 11, "泽": 17, "涵": 12, "轩": 10, "琪": 13, "瑞": 14, "梓": 11, "怡": 9, "雅": 12, "婷": 12,
}
ch = wg.load_chars(); bad = []
for c, v in VERIFIED.items():
    if c not in ch: bad.append((c, "缺"))
    elif int(ch[c]["kx"]) != v: bad.append((c, ch[c]["kx"], v))
# 证据等级: 王来自原文标注(A); 其余常见姓氏必须有原书依据(A/B/C), 仅 于/余 为取舍字
SURN = "李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘蒋蔡杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤"
if ch["王"]["evidence"] != "A": bad.append(("王证据等级", ch["王"]["evidence"]))
for c in SURN:
    if c in ch and ch[c]["evidence"] not in "ABC" and c != "万": bad.append(("姓氏缺原书依据", c, ch[c]["evidence"]))
# 五格公式 (手算校验)
cases = [
    ([7], [8], dict(天格=8, 人格=15, 地格=9, 外格=2, 总格=15)),              # 单姓单名
    ([4], [6, 10], dict(天格=5, 人格=10, 地格=16, 外格=11, 总格=20)),         # 单姓双名
    ([15, 17], [11, 20], dict(天格=32, 人格=28, 地格=31, 外格=35, 总格=63)),  # 复姓双名
    ([15, 17], [8], dict(天格=32, 人格=25, 地格=9, 外格=16, 总格=40)),        # 复姓单名
    ([40], [30, 20], dict(天格=41, 人格=70, 地格=50, 外格=21, 总格=10)),      # 总格超 81 折算
]
for sur, giv, want in cases:
    got = wg.wuge(sur, giv)
    if got != want: bad.append(("五格", sur, giv, got, want))
shuli, fem = wg.load_shuli()
if len(shuli) != 81: bad.append(("数理表条数", len(shuli)))
if not (shuli[21]["female"] == "avoid" and shuli[27]["disputed"]): bad.append(("数理表标注",))
# 出生地/夏令时/均时差
from datetime import datetime
import bazi as bz
if not (bz.in_cn_dst(datetime(1989, 7, 15, 14, 45)) and not bz.in_cn_dst(datetime(1991, 9, 15, 2, 30)) and not bz.in_cn_dst(datetime(1992, 7, 1, 12))):
    bad.append(("夏令时判断",))
if bz.in_cn_dst(datetime(1988, 4, 12, 12)) or not bz.in_cn_dst(datetime(1988, 4, 18, 12)):
    bad.append(("1988 夏令时起始应为 4 月 17 日",))
for md, lo, hi in [((2, 11), -16, -13), ((5, 14), 2.5, 5), ((7, 26), -7.5, -5), ((11, 3), 15, 17.5)]:
    e = bz.equation_of_time(datetime(1991, *md))
    if not lo <= e <= hi: bad.append(("均时差", md, e))
def hour_zhi(place):
    t, _ = bz.correct_time(datetime(1989, 7, 15, 14, 45), bz.CITY_LON[place])
    return bz.analyze(t.year, t.month, t.day, t.hour, t.minute)["四柱"]["时"][1]
# 夏令时内 14:45 -> 标准时间 13:45; 北京真太阳时约 13:25 仍是未时; 成都约 12:35 变成午时
if hour_zhi("北京") != "未" or hour_zhi("成都") != "午": bad.append(("出生地对时柱的影响", hour_zhi("北京"), hour_zhi("成都")))
print("OK: 全部通过" if not bad else f"FAIL: {bad}")
sys.exit(1 if bad else 0)

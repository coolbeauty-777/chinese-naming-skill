#!/usr/bin/env python3
"""八字排盘 + 五行统计 + 日主旺衰参考。排盘全部由 lunar-python 计算, 不靠心算。

用法:
  python bazi.py --date 2026-03-15 --time 08:30 [--gender 男|女] [--json]      # 公历
  python bazi.py --lunar 1995-3-15 --time 10:20 [--leap]                       # 农历 (闰月加 --leap)

输出: 四柱、日主、五行统计、月令、旺衰参考分、候选"扶抑"五行。
出生地与时间校正 (--place 城市名 或 --lon 经度):
  - 夏令时: 中国大陆 1986-1991 年实行夏令时, 落在期间的钟表时间自动减 1 小时 (可用 --no-dst 关闭)
  - 真太阳时 = 标准时间 + 4 分钟 x (出生地经度 - 120) + 均时差。给了出生地就同时排"钟表时间"和"真太阳时"两个盘,
    并指出哪一柱不同。不同流派取法不同, 不一致时请如实告诉用户。
说明:
  - 旺衰分只是启发式参考 (月令权重最大); 最终喜用神由 Claude 结合全盘判断并说明依据。
  - 临近节气交接、晚子时 (23:00-24:00) 出生时, 请向用户确认并说明排盘口径 (本脚本晚子时日柱算当天)。
"""
import argparse, json, math
from datetime import datetime, timedelta
from lunar_python import Lunar, Solar

GAN_WX = dict(zip("甲乙丙丁戊己庚辛壬癸", "木木火火土土金金水水"))
ZHI_WX = dict(zip("子丑寅卯辰巳午未申酉戌亥", "水土木木土火火土金金土水"))
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}   # 我生
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}       # 我克
HIDE_W = [1.0, 0.5, 0.25]                                               # 藏干: 本气/中气/余气权重


# 常见城市经度 (东经, 度); 县级市等不在表内时, 用所属地级市或直接用 --lon
CITY_LON = {
    "北京": 116.4, "天津": 117.2, "上海": 121.5, "重庆": 106.5, "石家庄": 114.5, "太原": 112.5, "呼和浩特": 111.7,
    "沈阳": 123.4, "长春": 125.3, "哈尔滨": 126.6, "南京": 118.8, "杭州": 120.2, "合肥": 117.3, "福州": 119.3,
    "南昌": 115.9, "济南": 117.0, "郑州": 113.7, "武汉": 114.3, "长沙": 113.0, "广州": 113.3, "南宁": 108.4,
    "海口": 110.3, "成都": 104.1, "贵阳": 106.7, "昆明": 102.7, "拉萨": 91.1, "西安": 108.9, "兰州": 103.8,
    "西宁": 101.8, "银川": 106.3, "乌鲁木齐": 87.6, "深圳": 114.1, "青岛": 120.4, "大连": 121.6, "厦门": 118.1,
    "苏州": 120.6, "无锡": 120.3, "宁波": 121.6, "温州": 120.7, "东莞": 113.8, "佛山": 113.1, "珠海": 113.6,
    "洛阳": 112.5, "徐州": 117.2, "烟台": 121.4, "唐山": 118.2, "保定": 115.5, "大同": 113.3, "包头": 109.8,
    "鞍山": 123.0, "吉林": 126.5, "齐齐哈尔": 123.9, "常州": 120.0, "扬州": 119.4, "南通": 120.9, "绍兴": 120.6,
    "嘉兴": 120.8, "泉州": 118.7, "汕头": 116.7, "湛江": 110.4, "桂林": 110.3, "柳州": 109.4, "遵义": 106.9,
    "大理": 100.2, "绵阳": 104.7, "宜昌": 111.3, "襄阳": 112.1, "岳阳": 113.1, "株洲": 113.1, "衡阳": 112.6,
    "赣州": 114.9, "九江": 116.0, "芜湖": 118.4, "蚌埠": 117.4, "潍坊": 119.1, "临沂": 118.4, "济宁": 116.6,
    "开封": 114.3, "新乡": 113.9, "安阳": 114.4, "宝鸡": 107.2, "延安": 109.5, "榆林": 109.7, "喀什": 76.0,
    "伊宁": 81.3, "香港": 114.2, "澳门": 113.5, "台北": 121.5, "高雄": 120.3, "乐山": 103.8, "南充": 106.1,
    "宜宾": 104.6, "泸州": 105.4, "德阳": 104.4, "自贡": 104.8, "内江": 105.1, "达州": 107.5, "攀枝花": 101.7,
}

# 中国大陆夏令时 (1986-1991): (起始月日, 结束月日), 当日 02:00 切换
CN_DST = {1986: ((5, 4), (9, 14)), 1987: ((4, 12), (9, 13)), 1988: ((4, 17), (9, 11)),
          1989: ((4, 16), (9, 17)), 1990: ((4, 15), (9, 16)), 1991: ((4, 14), (9, 15))}


def in_cn_dst(dt):
    if dt.year not in CN_DST:
        return False
    (sm, sd), (em, ed) = CN_DST[dt.year]
    start = datetime(dt.year, sm, sd, 3, 0)     # 02:00 拨快到 03:00, 起始日 03:00 后算夏令时
    end = datetime(dt.year, em, ed, 2, 0)       # 结束日 02:00 拨回到 01:00; 02:00 之前算夏令时
    return start <= dt < end


def equation_of_time(dt):
    """均时差(分钟): 真太阳时 = 平太阳时 + 均时差, 近似公式, 误差约 0.5 分钟"""
    n = dt.timetuple().tm_yday
    b = math.radians(360.0 / 365.0 * (n - 81))
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def correct_time(dt, lon=None, dst=True):
    """返回 (校正后时间, 说明列表)。dst: 是否处理夏令时; lon: 出生地经度, 为 None 则不做真太阳时校正"""
    notes = []
    t = dt
    if dst and in_cn_dst(dt):
        t = t - timedelta(hours=1)
        notes.append(f"出生在中国大陆夏令时期间, 钟表时间减 1 小时 -> {t:%H:%M}")
    if lon is not None:
        eot = equation_of_time(t)
        shift = 4.0 * (lon - 120.0) + eot
        t = t + timedelta(minutes=shift)
        notes.append(f"真太阳时校正: 经度差 {4.0*(lon-120.0):+.1f} 分钟, 均时差 {eot:+.1f} 分钟, 合计 {shift:+.1f} 分钟 -> {t:%Y-%m-%d %H:%M}")
    return t, notes


def edge_minutes(t):
    """距最近的时辰交界(奇数整点: 23, 1, 3, ... 13 ...)还有多少分钟"""
    x = (t.hour * 60 + t.minute - 60) % 120
    return min(x, 120 - x)


def analyze(y, mo, d, h, mi):
    ec = Solar.fromYmdHms(y, mo, d, h, mi, 0).getLunar().getEightChar()
    pillars = {"年": ec.getYear(), "月": ec.getMonth(), "日": ec.getDay(), "时": ec.getTime()}
    hide = {"年": ec.getYearHideGan(), "月": ec.getMonthHideGan(), "日": ec.getDayHideGan(), "时": ec.getTimeHideGan()}
    dm = ec.getDayGan()
    me = GAN_WX[dm]

    shown = {k: 0.0 for k in "木火土金水"}              # 显性: 4 天干 + 4 地支本气 各记 1
    weighted = {k: 0.0 for k in "木火土金水"}           # 含藏干加权, 月支乘 1.5
    for k, gz in pillars.items():
        shown[GAN_WX[gz[0]]] += 1
        shown[ZHI_WX[gz[1]]] += 1
        weighted[GAN_WX[gz[0]]] += 1.0
        mult = 1.5 if k == "月" else 1.0
        for g, w in zip(hide[k], HIDE_W):
            weighted[GAN_WX[g]] += w * mult

    parent = next(k for k, v in SHENG.items() if v == me)   # 生我 (印)
    kids = SHENG[me]                                         # 我生 (食伤)
    wealth = KE[me]                                          # 我克 (财)
    officer = next(k for k, v in KE.items() if v == me)      # 克我 (官杀)
    support = weighted[me] + weighted[parent] - 1.0          # 扣掉日主自身
    drain = weighted[kids] + weighted[wealth] + weighted[officer]
    ratio = support / (support + drain) if support + drain else 0.5
    month_zhi = pillars["月"][1]
    de_ling = ZHI_WX[month_zhi] in (me, parent)
    if ratio >= 0.55:
        verdict = "偏强"
    elif ratio <= 0.40:
        verdict = "偏弱"
    else:
        verdict = "中和偏平衡 (需细看)"
    return {
        "四柱": pillars, "藏干": hide, "日主": f"{dm}({me})",
        "五行显性统计": shown, "五行含藏干加权": {k: round(v, 2) for k, v in weighted.items()},
        "月令": {"月支": month_zhi, "月支五行": ZHI_WX[month_zhi], "日主得令": de_ling},
        "旺衰参考": {"生扶占比": round(ratio, 2), "倾向": verdict, "生扶五行": [me, parent],
                  "克泄耗五行": [kids, wealth, officer]},
        "扶抑候选五行": ([me, parent] if verdict == "偏弱" else [kids, wealth, officer] if verdict == "偏强" else []),
        "缺失五行(显性)": [k for k, v in shown.items() if v == 0],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="公历 YYYY-MM-DD")
    ap.add_argument("--lunar", help="农历 YYYY-M-D (与 --date 二选一)")
    ap.add_argument("--leap", action="store_true", help="农历闰月")
    ap.add_argument("--time", default="12:00", help="HH:MM, 24 小时制 (钟表时间)")
    ap.add_argument("--gender", default="")
    ap.add_argument("--place", help="出生地城市名, 用于真太阳时校正, 如 成都")
    ap.add_argument("--lon", type=float, help="出生地东经度数 (城市不在表内时用)")
    ap.add_argument("--no-dst", action="store_true", help="不处理 1986-1991 夏令时")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    h, mi = map(int, a.time.split(":"))
    if a.lunar:
        ly, lm, ld = map(int, a.lunar.split("-"))
        sol = Lunar.fromYmdHms(ly, -lm if a.leap else lm, ld, h, mi, 0).getSolar()
        y, mo, d = sol.getYear(), sol.getMonth(), sol.getDay()
        print(f"农历 {a.lunar}{'(闰月)' if a.leap else ''} 换算为公历 {y}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}")
    elif a.date:
        y, mo, d = map(int, a.date.split("-"))
    else:
        ap.error("需要 --date 或 --lunar")

    lon, place_name = a.lon, None
    if a.place:
        key = next((k for k in CITY_LON if k in a.place or a.place in k), None)
        if key is None:
            ap.error(f"城市「{a.place}」不在经度表内, 请改用所属地级市, 或用 --lon 直接给经度")
        lon, place_name = CITY_LON[key], key

    clock = datetime(y, mo, d, h, mi)
    base, n_base = correct_time(clock, None, dst=not a.no_dst)       # 仅夏令时校正 (钟表标准时间)
    r_clock = analyze(base.year, base.month, base.day, base.hour, base.minute)
    r_true, n_true = None, []
    if lon is not None:
        tt, n_true = correct_time(clock, lon, dst=not a.no_dst)
        r_true = analyze(tt.year, tt.month, tt.day, tt.hour, tt.minute)

    def show(r, title, notes):
        p = r["四柱"]
        print(f"\n【{title}】" + ("  " + "；".join(notes) if notes else ""))
        print(f"四柱: {p['年']} {p['月']} {p['日']} {p['时']}   日主: {r['日主']}   {a.gender}")
        print("五行(显性):", r["五行显性统计"], "| 含藏干加权:", r["五行含藏干加权"])
        print("月令:", r["月令"], "| 旺衰参考:", r["旺衰参考"])
        print("扶抑候选五行(仅供参考):", r["扶抑候选五行"] or "无明确倾向", "| 显性缺失:", r["缺失五行(显性)"] or "无")

    if a.json:
        print(json.dumps({"钟表时间盘": r_clock, "真太阳时盘": r_true}, ensure_ascii=False, indent=1))
    else:
        show(r_clock, "按钟表时间" + ("（已处理夏令时）" if n_base else ""), n_base)
        if r_true:
            show(r_true, f"按真太阳时（出生地 {place_name or '经度 %.1f' % lon}，东经 {lon:.1f}°）", n_true)
            em = edge_minutes(tt)
            if em <= 10:
                print(f"\n⚠ 校正后的时间 {tt:%H:%M} 距时辰交界只有 {em} 分钟，经度取值或均时差的小误差就可能让时柱改变，"
                      f"请向用户确认出生的具体地点和时间（尽量精确到分钟）。")
            diff = [k for k in "年月日时" if r_clock["四柱"][k] != r_true["四柱"][k]]
            if diff:
                print("\n⚠ 两种时间排出的四柱不同: " + "；".join(f"{k}柱 {r_clock['四柱'][k]} → {r_true['四柱'][k]}" for k in diff)
                      + "。多数流派用真太阳时，也有人只用钟表时间；请把两种都告诉用户，并说明对喜用神有无影响。")
            else:
                print("\n✓ 两种时间排出的四柱完全一致，出生地不影响本盘。")
        else:
            if edge_minutes(base) <= 10:
                print(f"\n⚠ 标准时间 {base:%H:%M} 距时辰交界只有 {edge_minutes(base)} 分钟，请向用户确认出生时间。")
            print("\n（未提供出生地，只按钟表时间排盘。出生地离东经 120° 越远，时柱越可能不同。）")

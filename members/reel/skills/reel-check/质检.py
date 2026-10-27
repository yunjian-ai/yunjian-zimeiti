"""成片质检和导出。要 ffmpeg；查闪烁要 numpy。
用法：
  python3 质检.py 查 <成片.mp4> [--平台 抖音,小红书] [--秒 15] [--报告 出片/质检.md]
      机器查：分辨率（9:16 要 1080×1920）、时长、帧率、码率（≤10Mbps）、编码和像素格式、响度（-16～-12 LUFS）、真峰值（≤-1 dB）、
      中途黑帧、闪烁（1 秒内亮度大跳超过 6 次＝超过 3 次闪，光敏风险）、色彩标记；平台规格是「待核」的直接拦。有问题退出码 1。
  python3 质检.py 联系表 <成片.mp4> <出.jpg> [--每 1]     每隔几秒一格、5 格一行，人眼按坑清单看
  python3 质检.py 审片 <成片.mp4> <出.mp4> [--mb 20]      压一份小文件发手机、微信看（不是发布用的）
  python3 质检.py 封面 <成片.mp4> <出.jpg> --秒 1.7        从成片里取一帧原尺寸当封面底图
规格读 库/视频规格.json（装好在 ~/.yunjian/reel/库/）。"""
import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "reel-brief"))
import 媒体  # noqa: E402


def 规格():
    for p in (Path.home() / ".yunjian" / "reel" / "库" / "视频规格.json", HERE.parent.parent / "库" / "视频规格.json"):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {"默认": {"竖": {"宽": 1080, "高": 1920}, "横": {"宽": 1920, "高": 1080}, "帧率": [24, 60], "码率上限Mbps": 10,
                   "视频编码": ["h264"], "像素格式": "yuv420p", "响度LUFS": [-16, -12], "真峰值上限dB": -1.0}, "平台": {}}


def 响度(path):
    err = 媒体.分析("-i", path, "-af", "ebur128=peak=true", "-f", "null", "-")
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    tp = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", err)
    return (float(i[-1]) if i else None), (float(tp[-1]) if tp and tp[-1] != "-inf" else None)


def 黑帧(path, 时长):
    err = 媒体.分析("-i", path, "-vf", "blackdetect=d=0.1:pix_th=0.10", "-an", "-f", "null", "-")
    段 = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)]
    return [(a, b) for a, b in 段 if not (b >= 时长 - 0.7) and not (a < 0.05 and b < 0.5)]  # 片尾淡出、片头半秒淡入不算


def 闪烁(path, fps):
    """逐帧平均亮度，相邻帧差超过 20/255 记一次大跳；返回最密那 1 秒的次数和起点。"""
    try:
        import numpy as np
    except ImportError:
        return None, None
    r = subprocess.run([媒体.ffmpeg(), "-v", "error", "-nostdin", "-i", str(path), "-vf", "scale=64:64,format=gray",
                        "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(r.stdout, np.uint8)
    a = a[:len(a) // 4096 * 4096].reshape(-1, 4096).mean(1)
    跳 = np.nonzero(np.abs(np.diff(a)) > 20)[0] / (fps or 30)
    最多, 起 = 0, None
    for t in 跳:
        n = int(((跳 >= t) & (跳 < t + 1)).sum())
        if n > 最多:
            最多, 起 = n, round(float(t), 2)
    return 最多, 起


def 查(g):
    S = 规格()
    默 = S["默认"]
    d = 媒体.信息(g.视频)
    坏, 提醒 = [], []
    if not d.get("宽"):
        sys.exit(f"NO_VIDEO：{g.视频} 里没有画面")
    竖 = d["高"] > d["宽"]
    要 = 默["竖" if 竖 else "横"]
    if (d["宽"], d["高"]) != (要["宽"], 要["高"]):
        坏.append((f"分辨率 {d['宽']}×{d['高']}，应该是 {要['宽']}×{要['高']}", "reel-cut 成片.py 按默认尺寸重出（720p 素材会自动放大）"))
    if g.秒 and abs(d["时长"] - g.秒) > 0.15:
        坏.append((f"时长 {d['时长']:.2f} 秒，要的是 {g.秒} 秒", "核对镜头表最后一刀的出点和歌的长度"))
    lo, hi = 默["帧率"]
    if d.get("帧率") and not lo <= d["帧率"] <= hi:
        坏.append((f"帧率 {d['帧率']}，应在 {lo}～{hi}", "成片.py 默认 30 帧重出"))
    if d.get("视频编码") not in 默["视频编码"]:
        坏.append((f"视频编码 {d.get('视频编码')}，要 H.264", "成片.py 重出（libx264）"))
    if d.get("像素格式") != 默["像素格式"]:
        坏.append((f"像素格式 {d.get('像素格式')}，平台要 yuv420p", "成片.py 重出"))
    mb = Path(g.视频).stat().st_size * 8 / 1e6 / max(d["时长"], 0.1)
    上限 = 默["码率上限Mbps"]
    if mb > 上限:
        坏.append((f"码率约 {mb:.1f} Mbps，超过 {上限} Mbps（视频号上限）", "成片.py 重出（默认限 9.5Mbps），或用「审片」压一版"))
    if not d.get("有音轨"):
        坏.append(("没有声音", "成片.py 重出时带上歌"))
    else:
        i, tp = 响度(g.视频)
        a, b = 默["响度LUFS"]
        if i is not None and not a <= i <= b:
            坏.append((f"响度 {i} LUFS，{'太大' if i > b else '太小'}（应在 {a}～{b}，-14 左右）", "成片.py 自带响度标准化，重出一次"))
        if tp is not None and tp > 默["真峰值上限dB"]:
            坏.append((f"真峰值 {tp} dB，超过 {默['真峰值上限dB']}（手机外放会破音）", "成片.py 重出（响度标准化会压峰值）"))
    for a, b in 黑帧(g.视频, d["时长"]):
        坏.append((f"{a:.2f}～{b:.2f} 秒黑屏", "查这几秒是哪一刀：素材坏了或可用窗口取过了头，reel-cut 换素材或改窗口"))
    次, 起 = 闪烁(g.视频, d.get("帧率"))
    if 次 is None:
        提醒.append(("没装 numpy，闪烁没查", "pip install numpy 后再查，或者人眼逐帧看闪白的地方"))
    elif 次 > 6:
        坏.append((f"{起}～{起 + 1:.2f} 秒 1 秒内亮度大跳 {次} 次（超过 3 次闪），有光敏风险", "剪辑.json 里把这里的闪帧去掉或隔开（1 秒最多 3 次）"))
    if "bt709" not in (d.get("色彩") or ""):
        提醒.append(("没有 BT.709 色彩标记，有的手机颜色会偏", "成片.py 重出会带上"))
    for 名 in [x for x in (g.平台 or "").replace("，", ",").split(",") if x.strip()]:
        p = S["平台"].get(名.strip())
        if not p:
            坏.append((f"{名} 不在规格表里", "先核这家官方规格再出成品"))
            continue
        if p["状态"] == "待核":
            坏.append((f"{名} 的视频规格还没核对官方（{p.get('提醒', '')}）", f"{名} 版先不出成品，请主人登录一次补核"))
        if p.get("最低高") and min(d["宽"], d["高"]) < p["最低高"]:
            坏.append((f"{名} 建议 {p['最低高']}p 以上", "按默认 1080 重出"))
        if p.get("采样率") and d.get("采样率") and d["采样率"] != p["采样率"]:
            坏.append((f"{名} 要求采样率 {p['采样率']}，这条是 {d['采样率']}", "成片.py 重出（默认 48000）"))
        if p.get("声道上限") and d.get("声道") and d["声道"] > p["声道上限"]:
            坏.append((f"{名} 要求声道不超过 {p['声道上限']}，这条是 {d['声道']} 声道", "成片.py 重出（跟着歌，单声道或立体声）"))
        if p.get("时长上限秒") and d["时长"] > p["时长上限秒"]:
            坏.append((f"超过 {名} 时长上限", "剪短"))
        if 名.strip() == "抖音" and 竖 and d["时长"] > 40:
            提醒.append(("抖音官方建议超过 40 秒的视频传横版", "问主人要不要另出 16:9 横版"))
        for x in p.get("待核", []):
            if x != "全部":
                提醒.append((f"{名} 的{x}规格还没核", "交付时告诉主人"))
    i_txt = f"{d['宽']}×{d['高']} {d.get('帧率')} 帧 {d['时长']:.2f} 秒 约 {mb:.1f} Mbps {d.get('视频编码')} {d.get('像素格式')}"
    行 = [f"# 质检：{Path(g.视频).name}", "", f"- 规格：{i_txt}", ""]
    行 += [f"- ❌ {x} → {y}" for x, y in 坏] + [f"- ⚠️ {x} → {y}" for x, y in 提醒]
    行 += ["", "结论：" + ("不能发，先按上面改" if 坏 else "机器检查通过；再按坑清单人眼看联系表、做 6 项自评")]
    print("\n".join(行))
    if g.报告:
        Path(g.报告).parent.mkdir(parents=True, exist_ok=True)
        Path(g.报告).write_text("\n".join(行) + "\n", encoding="utf-8")
    return 1 if 坏 else 0


def 联系表(g):
    d = 媒体.信息(g.视频)
    n = max(1, math.ceil(d["时长"] / g.每 - 1e-6))
    行数 = math.ceil(n / 5)
    f = 媒体.字体(False)
    标 = (f"drawtext=fontfile={媒体.滤镜路径(f)}:text='%{{eif\\:floor(t)\\:d}}.%{{eif\\:mod(round(t*10)\\,10)\\:d}}s':"
         f"x=8:y=8:fontsize=26:fontcolor=yellow:borderw=2:bordercolor=black," if f else "")
    竖 = d["高"] > d["宽"]
    w, h = (216, 384) if 竖 else (384, 216)
    媒体.跑("-i", g.视频, "-vf", f"fps=1/{g.每}:round=down,scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
           f"{标}setpts=N/TB,tile=5x{行数}:padding=3:color=0x101010", "-frames:v", "1", "-q:v", "3", g.出)
    print(f"OK {g.出}：{n} 格，每 {g.每} 秒一格")
    return 0


def 审片(g):
    d = 媒体.信息(g.视频)
    kbps = max(300, int(g.mb * 8000 * 0.9 / max(d["时长"], 0.1)) - 128)
    竖 = d["高"] > d["宽"]
    媒体.跑("-i", g.视频, "-vf", "scale=540:960" if 竖 else "scale=960:540", "-c:v", "libx264", "-preset", "medium",
           "-b:v", f"{min(kbps, 4000)}k", "-maxrate", f"{min(kbps, 4000) * 2}k", "-bufsize", f"{min(kbps, 4000) * 2}k",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", g.出)
    print(f"OK {g.出} {Path(g.出).stat().st_size / 1e6:.1f}MB（审片用，不是发布版）")
    return 0


def 封面(g):
    媒体.跑("-ss", f"{g.秒:.3f}", "-i", g.视频, "-frames:v", "1", "-q:v", "2", g.出)
    print(f"OK {g.出}（第 {g.秒} 秒那一帧，原尺寸；要加标题交给 reel-cut 或丹青）")
    return 0


def main():
    ap = argparse.ArgumentParser(description="成片质检和导出")
    sub = ap.add_subparsers(dest="做", required=True)
    a = sub.add_parser("查")
    a.add_argument("视频")
    a.add_argument("--平台", default="")
    a.add_argument("--秒", type=float)
    a.add_argument("--报告")
    b = sub.add_parser("联系表")
    b.add_argument("视频")
    b.add_argument("出")
    b.add_argument("--每", type=float, default=1.0)
    c = sub.add_parser("审片")
    c.add_argument("视频")
    c.add_argument("出")
    c.add_argument("--mb", type=float, default=20)
    e = sub.add_parser("封面")
    e.add_argument("视频")
    e.add_argument("出")
    e.add_argument("--秒", type=float, required=True)
    g = ap.parse_args()
    sys.exit({"查": 查, "联系表": 联系表, "审片": 审片, "封面": 封面}[g.做](g))


if __name__ == "__main__":
    main()

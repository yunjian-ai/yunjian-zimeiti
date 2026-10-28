"""成片质检和导出。要 ffmpeg；查闪烁要 numpy。
用法：
  python3 质检.py 查 <成片.mp4> [--平台 抖音,小红书] [--秒 15] [--报告 出片/质检.md]
      机器查：分辨率（9:16 要 1080×1920）、时长、帧率、码率（≤10Mbps）、编码和像素格式、响度（-16～-12 LUFS）、真峰值（≤-1 dB）、
      中途黑帧、闪烁（1 秒内亮度大跳超过 6 次＝超过 3 次闪，光敏风险）、色彩标记；平台规格是「待核」的直接拦。有问题退出码 1。
  python3 质检.py 联系表 <成片.mp4> <出.jpg> [--每 1]     每隔几秒一格、5 格一行，人眼按坑清单看
  python3 质检.py 审片 <成片.mp4> <出.mp4> [--mb 20]      压一份小文件发手机、微信看（不是发布用的）
  python3 质检.py 封面 <成片.mp4> <出.jpg> --秒 1.7        从成片里取一帧原尺寸当封面底图
  python3 质检.py 安全区 <成片.mp4> <出.jpg> [--秒 3,8,12]   在这几秒的画面上画出按钮区（上 10%、下 20%、右 15%），人眼看字和货有没有压进去
  python3 质检.py 封面AB <出文件夹> --图 a.png b.png --题 "标题一|标题二|标题三" [--比例 3:4]
      带货片封面 A/B：干净底图（静帧，不要用带字幕的成片帧）× 几个标题 × 4 种版式轮换，出 封面_A.jpg… 和对比图 封面对比.jpg
  python3 质检.py 口播 <成片.mp4> --稿 稿子.md [--字幕 出片/字幕.ass] [--出 出片/口播质检]
      口播片加查：成片的声音再转一遍文字对稿子——每句出现且只出现一次（主人说删的写进 --删 3,5）、漏了哪句；最长停顿 ≤0.5 秒；
      时长和稿子「约 N 秒」差 ≤15%；字幕：有 ASS 就逐字比稿子（标点除外），没有（字烧在画面上、别人剪的）就每句抽一帧、
      下面标上稿子原文拼成「字幕对照.jpg」，逐格看字对不对。有问题退出码 1。要先装转文字（reel-voice/对时间.py 装）。
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
    for p in (HERE.parent.parent / "库" / "视频规格.json", Path.home() / ".yunjian" / "reel" / "库" / "视频规格.json"):  # 包里带的优先（和脚本同一版）
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
    按比例 = {(3, 4): (1080, 1440), (4, 3): (1440, 1080), (1, 1): (1080, 1080)}  # 详情页、小红书这类 3:4、1:1 版不拿 9:16 去套（Bot 实测误报）
    for (a, b), (w, h) in 按比例.items():
        if abs(d["宽"] / d["高"] - a / b) < 0.02:
            要 = {"宽": w, "高": h}
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
            坏.append((f"{d['时长']:.1f} 秒，超过 {名} 时长上限 {p['时长上限秒']} 秒", "剪短（删刀或删台词）"))
        if p.get("时长下限秒") and d["时长"] < p["时长下限秒"]:
            坏.append((f"{d['时长']:.1f} 秒，不到 {名} 要求的 {p['时长下限秒']} 秒", "加一刀或放慢"))
        if p.get("大小上限MB") and Path(g.视频).stat().st_size / 1e6 > p["大小上限MB"]:
            坏.append((f"文件 {Path(g.视频).stat().st_size / 1e6:.0f}MB，超过 {名} 上限 {p['大小上限MB']}MB", "用「审片」那样压一版，或剪短"))
        if p.get("格式") and Path(g.视频).suffix.lower().lstrip(".") not in p["格式"]:
            坏.append((f"{名} 只收 {'、'.join(p['格式'])}", "成片.py 出的是 mp4，换那一份"))
        if p.get("画幅"):
            比 = {f"{a}:{b}": a / b for a, b in ((1, 1), (3, 4), (4, 3), (9, 16), (16, 9))}
            if not any(abs(d["宽"] / d["高"] - 比[x]) < 0.02 for x in p["画幅"] if x in 比):
                坏.append((f"{d['宽']}×{d['高']} 不是 {名} 收的画幅（{'、'.join(p['画幅'])}）", "剪辑.json 改画幅重出"))
        if p.get("提醒") and 名.strip() != "抖音":
            提醒.append((f"{名}：{p['提醒']}", "交付时告诉主人"))
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
    if d.get("码率kbps"):
        kbps = min(kbps, max(300, int(d["码率kbps"] * 0.6)))  # 审片版是小样，不该比原片还大
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


def 安全区(g):
    d = 媒体.信息(g.视频)
    W, H = d["宽"], d["高"]
    秒们 = [float(x) for x in (g.秒 or "").replace("，", ",").split(",") if x.strip()] or [min(1.5, d["时长"] / 2), d["时长"] / 2, d["时长"] - 0.5]
    框 = (f"drawbox=x=0:y=0:w=iw:h=ih*0.10:color=red@0.35:t=fill,drawbox=x=0:y=ih*0.80:w=iw:h=ih*0.20:color=red@0.35:t=fill,"
         f"drawbox=x=iw*0.85:y=0:w=iw*0.15:h=ih:color=red@0.25:t=fill")
    选 = "+".join(f"eq(n\\,{int(round(t * (d.get('帧率') or 30)))})" for t in 秒们)
    w, h = (360, 640) if H > W else (640, 360)
    媒体.跑("-i", g.视频, "-vf", f"select='{选}',{框},scale={w}:{h},tile={len(秒们)}x1:padding=4:color=0x101010", "-frames:v", "1", g.出)
    print(f"OK {g.出}：{'、'.join(f'{t:.1f}' for t in 秒们)} 秒，红色是按钮区（上 10%、下 20%、右 15%，推算值）。字、价格、商品主体压进红区就要挪")
    return 0


def 封面AB(g):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        sys.exit("NO_PIL：要 PIL（pip install pillow）")
    sys.path.insert(0, str(HERE.parent / "reel-cut"))
    import 字体
    题们 = [x.strip() for x in g.题.split("|") if x.strip()]
    W, H = {"3:4": (1080, 1440), "9:16": (1080, 1920), "1:1": (1080, 1080)}[g.比例]
    f = 字体.找("中文")
    版式 = [("黄字黑边", (255, 215, 51), (0, 0, 0), None), ("白字红边", (255, 255, 255), (220, 40, 40), None),
          ("黄底黑字", (20, 20, 20), None, (255, 215, 51)), ("黑底白字", (255, 255, 255), None, (0, 0, 0, 150))]
    出 = Path(g.出)
    出.mkdir(parents=True, exist_ok=True)
    小们 = []
    for i, 题 in enumerate(题们):
        if len(题) > 14:
            print(f"⚠️ 「{题}」{len(题)} 字，手机缩略图上看不清，最好 14 字以内", file=sys.stderr)
        底 = Image.open(g.图[i % len(g.图)]).convert("RGB")
        r = max(W / 底.width, H / 底.height)
        底 = 底.resize((int(底.width * r) + 1, int(底.height * r) + 1)).crop((0, 0, W, H))
        名, 字色, 边色, 块色 = 版式[i % len(版式)]
        字 = ImageFont.truetype(f, int(min(W * 0.11, W * 0.86 / max(1, len(题)))))
        画 = ImageDraw.Draw(底, "RGBA")
        宽 = 画.textlength(题, font=字)
        x, y = (W - 宽) / 2, H * 0.12
        if 块色:
            画.rectangle((x - W * 0.04, y - W * 0.03, x + 宽 + W * 0.04, y + 字.size * 1.25), fill=块色)
        画.text((x, y), 题, font=字, fill=字色, stroke_width=int(字.size * 0.08) if 边色 else 0, stroke_fill=边色)
        p = 出 / f"封面_{chr(65 + i)}.jpg"
        底.save(p, quality=92)
        小们.append((chr(65 + i), 名, 题, 底.resize((W // 3, H // 3))))
        print(f"{chr(65 + i)}：{题}｜{名}｜底图 {Path(g.图[i % len(g.图)]).name} → {p}")
    拼 = Image.new("RGB", (len(小们) * (W // 3 + 10), H // 3 + 60), (16, 16, 16))
    标 = ImageFont.truetype(f, 28)
    for k, (号, 名, 题, im) in enumerate(小们):
        拼.paste(im, (k * (W // 3 + 10), 0))
        ImageDraw.Draw(拼).text((k * (W // 3 + 10) + 8, H // 3 + 14), f"{号} {名}", font=标, fill=(255, 255, 255))
    拼.save(出 / "封面对比.jpg", quality=90)
    记 = 出 / "AB记录表.md"
    if not 记.exists():
        记.write_text("| 版本 | 标题 | 版式 | 发布时间 | 曝光 | 点击率 | 完播率 | 结论 |\n|---|---|---|---|---|---|---|---|\n"
                     + "".join(f"| {号} | {题} | {名} | | | | | |\n" for 号, 名, 题, _ in 小们), encoding="utf-8")
    print(f"OK 对比图 {出 / '封面对比.jpg'}、记录表 {记}。一次只改一个变量（标题或底图或版式），看平台数据定，不凭感觉")
    return 0


def 净(t):
    return re.sub(r"[\s，。？！、；：,.?!;:…—“”\"'（）()《》*=]", "", t)


def 读ass(path):
    """→ [(起, 止, 文字)]：只要底部字幕（Sub 开头的样式），去掉 {…} 特效。"""
    out = []
    for l in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"Dialogue:\s*\d+,([\d:.]+),([\d:.]+),(Sub\w*),[^,]*,\d+,\d+,\d+,[^,]*,(.*)$", l)
        if m:
            秒 = lambda x: sum(float(a) * b for a, b in zip(x.split(":"), (3600, 60, 1)))  # noqa: E731
            out.append((秒(m[1]), 秒(m[2]), re.sub(r"\{[^}]*\}", "", m[4])))
    return out


def 口播(g):
    import shutil
    import tempfile
    对 = HERE.parent / "reel-voice" / "对时间.py"
    sys.path.insert(0, str(对.parent))
    import 对时间
    稿 = Path(g.稿)
    句们 = [s for s in 对时间.读稿(稿) if not s.get("夹带")]
    删 = {int(x) for x in re.split(r"[,，]", g.删 or "") if x.strip().isdigit()}
    d = 媒体.信息(g.视频)
    出 = Path(g.出 or Path(g.视频).with_name("口播质检"))
    出.mkdir(parents=True, exist_ok=True)
    问题, 好, 提醒 = [], [], []
    # 1. 时长
    m = re.search(r"约\s*(\d+(?:\.\d+)?)\s*秒", 稿.read_text(encoding="utf-8"))
    if m:
        预, 实 = float(m[1]), d["时长"]
        说 = f"时长 {实:.1f} 秒，稿子预计约 {预:g} 秒（差 {abs(实 - 预) / 预:.0%}，上限 15%）"
        if 实 > 预 * 1.15:
            问题.append(说 + "→ 先删停顿，再问主人删哪句；加速最多 1.1 倍")
        elif 实 < 预 * 0.85:
            提醒.append(说 + "：短了——句子都在的话多半是语速快，告诉主人一声；漏了句看下面")
        else:
            好.append(说)
    # 2. 停顿
    err = 媒体.分析("-i", g.视频, "-af", "silencedetect=n=-38dB:d=0.5", "-f", "null", "-")
    停 = [(float(a), float(b)) for a, b in zip(re.findall(r"silence_start: ([\d.]+)", err), re.findall(r"silence_end: ([\d.]+)", err))]
    停 = [(a, b) for a, b in 停 if a > 0.05 and b < d["时长"] - 0.6]
    for a, b in 停:
        问题.append(f"{a:.2f}–{b:.2f} 秒停了 {b - a:.1f} 秒（上限 0.5）→ 回 清剪 压短这处停顿")
    if not 停:
        好.append("没有超过 0.5 秒的停顿")
    # 3. 每句一次（成片声音再转一遍）
    tmp = Path(tempfile.mkdtemp())
    try:
        shutil.copy(稿, tmp / "稿子.md")
        r = subprocess.run([sys.executable, str(对), "转", str(tmp), "--录音", str(Path(g.视频).resolve())], capture_output=True, text=True)
        if r.returncode:
            问题.append("没转成文字，「每句一次」没查：" + (r.stdout + r.stderr).strip().splitlines()[-1])
            结果 = None
        else:
            subprocess.run([sys.executable, str(对), "对", str(tmp)], capture_output=True, text=True)
            结果 = json.loads((tmp / "口播" / "对时间.json").read_text(encoding="utf-8"))
    finally:
        pass
    时 = {}
    if 结果:
        for s in 结果["句"]:
            if s.get("夹带"):
                continue
            if s["号"] in 删:
                if s["状态"] != "漏念":
                    问题.append(f"第 {s['号']} 句「{s['字幕']}」主人说删，片子里还有（{s['起']:.2f} 秒）")
                continue
            if s["状态"] == "漏念":
                问题.append(f"第 {s['号']} 句「{s['字幕']}」片子里没有（漏了）→ 回粗剪找这句，录音里也没有就问主人补录还是删")
            elif s["删掉的遍"]:
                问题.append(f"第 {s['号']} 句「{s['字幕']}」出现了不止一次（" + "；".join(f"{x['起']:.2f} 秒" for x in s["删掉的遍"]) + "）→ 回清剪只留一遍")
            elif s["状态"] == "改了说法？":
                问题.append(f"第 {s['号']} 句听着和稿子不一样：听到「{s['听到']}」（可能是同音错字，也可能主人改了说法）→ 人耳核一下")
            if s.get("起") is not None:
                时[s["号"]] = (s["起"], s["止"])
        for x in 结果.get("多出来的", []):
            问题.append(f"{x['起']:.2f}–{x['止']:.2f} 秒有稿子里没有的话「{x['听到']}」→ 主人说留就留，没说过就问")
        if not any("片子里没有" in x or "不止一次" in x for x in 问题):
            好.append(f"稿子 {len(句们) - len(删)} 句在片子里都出现、各一次")
    shutil.rmtree(tmp, ignore_errors=True)
    # 4. 字幕
    ass = Path(g.字幕) if g.字幕 else Path(g.视频).with_name("字幕.ass")
    if ass.exists():
        字 = 读ass(ass)
        稿字 = "".join(净(s["字幕"]) for s in 句们 if s["号"] not in 删)
        幕字, 位 = "", []
        for a, b, t in 字:
            for c in 净(t):
                幕字 += c
                位.append(a)
        sm = __import__("difflib").SequenceMatcher(None, 稿字, 幕字, autojunk=False)
        错 = [(op, 稿字[i1:i2], 幕字[j1:j2], 位[min(j1, len(位) - 1)] if 位 else 0) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
        for op, a, b, t in 错:
            问题.append(f"字幕 {t:.2f} 秒附近：稿子「{a or '（没有）'}」，字幕「{b or '（没有）'}」→ 字幕照稿子改（主人临场改了说法的照他真说的）")
        if not 错:
            好.append(f"字幕和稿子一字不差（{len(字)} 条，标点不算）")
    else:
        try:
            from PIL import Image, ImageDraw, ImageFont
            格, 号们 = [], [s for s in 句们 if s["号"] in 时]
            for s in 号们:
                a, b = 时[s["号"]]
                f = 出 / f"_{s['号']:02d}.jpg"
                媒体.跑("-ss", f"{(a + b) / 2:.2f}", "-i", g.视频, "-frames:v", "1", "-vf", "scale=360:-2", f)
                格.append((s, Image.open(f).convert("RGB")))
                f.unlink()
            if 格:
                w, h = 格[0][1].size
                列 = 5
                图 = Image.new("RGB", (列 * w, math.ceil(len(格) / 列) * (h + 90)), (16, 16, 16))
                字体 = ImageFont.truetype(媒体.字体(), 22)
                画 = ImageDraw.Draw(图)
                for k, (s, im) in enumerate(格):
                    x, y = k % 列 * w, k // 列 * (h + 90)
                    图.paste(im, (x, y))
                    画.text((x + 6, y + h + 6), f"第{s['号']}句 {时[s['号']][0]:.1f}s", font=字体, fill=(255, 220, 60))
                    稿行 = s["字幕"]
                    画.text((x + 6, y + h + 36), 稿行[:15], font=字体, fill=(255, 255, 255))
                    if len(稿行) > 15:
                        画.text((x + 6, y + h + 62), 稿行[15:30], font=字体, fill=(255, 255, 255))
                图.save(出 / "字幕对照.jpg", quality=88)
                问题.append(f"字幕是烧在画面上的，脚本读不出字：看 {出 / '字幕对照.jpg'}，每格画面里的字幕和下面的稿子逐字比（数字、错别字、漏字）")
        except ImportError:
            问题.append("字幕没查：没有字幕文件，也没装 PIL 出对照图；请人眼对着稿子看一遍")
    报告 = ["# 口播质检：" + Path(g.视频).name, "", f"- 规格：{d.get('宽')}×{d.get('高')}，{d['时长']:.2f} 秒", ""]
    报告 += [f"- ❌ {x}" for x in 问题 if "字幕对照" not in x] + [f"- 👀 {x}" for x in 问题 if "字幕对照" in x] + [f"- ⚠️ {x}" for x in 提醒] + [f"- ✅ {x}" for x in 好]
    硬 = [x for x in 问题 if "字幕对照" not in x]
    报告 += ["", "结论：" + ("改完再发" if 硬 else "机器能查的都过了" + ("；字幕对照图人眼核完再发" if 问题 else ""))]
    (出 / "口播质检.md").write_text("\n".join(报告) + "\n", encoding="utf-8")
    print("\n".join(报告))
    return 1 if 硬 else 0


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
    f = sub.add_parser("安全区")
    f.add_argument("视频")
    f.add_argument("出")
    f.add_argument("--秒")
    h = sub.add_parser("封面AB")
    h.add_argument("出")
    h.add_argument("--图", nargs="+", required=True)
    h.add_argument("--题", required=True)
    h.add_argument("--比例", default="3:4", choices=["3:4", "9:16", "1:1"])
    k = sub.add_parser("口播")
    k.add_argument("视频")
    k.add_argument("--稿", required=True)
    k.add_argument("--字幕")
    k.add_argument("--删", default="")
    k.add_argument("--出")
    g = ap.parse_args()
    sys.exit({"口播": 口播, "查": 查, "联系表": 联系表, "审片": 审片, "封面": 封面, "安全区": 安全区, "封面AB": 封面AB}[g.做](g))


if __name__ == "__main__":
    main()

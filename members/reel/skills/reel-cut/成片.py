"""卡点剪辑：项目文件夹 → 粗剪预览 → 成片。全用 ffmpeg 一条滤镜链做完。
读：分镜.md（镜头表：进出点、大字、素材）、视频/可用窗口.md（每刀从素材第几秒起）、音乐/歌.*、音乐/拍子.json（大落点、速度）、
    音乐/歌词.json（有就逐字出歌词）、剪辑.json（可选：字号、颜色、调色、闪帧这些开关；改版就改它）、出片/遮罩.mp4（有就把大字压在人身后）
用法：
  python3 成片.py 粗剪 <项目>              半尺寸快速预览 出片/粗剪/粗剪.mp4 ＋ 每刀一格的联系表，给主人定顺序和节奏（关口）
  python3 成片.py 几帧 <项目> --秒 1.0,5.2  只出这几秒的全尺寸画面（看字、看调色，不出整片）
  python3 成片.py 底片 <项目>              只出调好色、没字的底片 出片/底片.mp4（给 抠像.py 做遮罩用）
  python3 成片.py 成片 <项目>              出 出片/成片.mp4；已经有了就出 成片_v2.mp4、_v3……旧版不删；同名 .设置.json 记下这版用的设置
  选项：--跳过体检（镜头表体检不过也出）、--不查关口（粗剪没点头也出成片，只在主人明说时用）、--允许超窗（素材不够长就停在最后一帧）
没有视频的刀：用 静帧/<号>.png 慢推（视频重出 3 次不行退回静帧就是这样）；素材写「—」的刀（开场纯大字）用底色。
静帧的动法看镜头动作那一格：快推（钩子）、慢推（默认）、拉远、左移、右移、静止。
带货片：剪辑.json 写 "类型": "带货"（分镜有「台词」列也自动认）——配音（配音/<号>.wav，在每刀开头 0.15 秒出声）＋背景乐（音乐/歌.*，可没有；
  有人声时自动压低）＋字幕和花字（字幕.py 出 ASS）＋贴纸、价格、行动号召；默认明亮清新调色，不闪帧、不故障、不加颗粒。
口播片：有 口播/清剪.json 就自动认（剪辑.json "类型": "口播"）——底子是 口播/粗剪.*（清剪.py 出的），分镜.md 是剪辑方案（镜头表.py 口播 生成）：
  「素材」写「—」的句子用粗剪里同一时间的主人画面，写文件的插入画面（声音不断）；字幕照台词；背景乐（音乐/歌.*，可没有）压在人声底下；
  默认不调色、不加特效；剪辑.json 可写 "片尾引导": "评论区报个日期"。"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for d in ("reel-brief", "reel-board", "reel-cut"):
    sys.path.insert(0, str(HERE.parent / d))
import 体检  # noqa: E402
import 媒体  # noqa: E402
import 字幕  # noqa: E402
import 字体  # noqa: E402
import 调色  # noqa: E402
import 镜头表  # noqa: E402

默认 = {
    "画幅": "9:16", "帧率": 30, "调色": "街头逆光", "调色强度": 1.0, "暗角": True, "底色": "0x101010",
    "大字": {"字号": 1.0, "颜色": "#F2EBDD", "位置": "中", "压人身后": True},
    "歌词": True, "HUD": {"标题": "", "副标题": ""}, "跑马灯": "",
    "闪帧": True, "故障": True, "颗粒": 6, "片尾": {"字": "", "副": ""}, "淡出": 0.6,
}
带货默认 = {  # 淡出 0：白底画面淡到黑会被质检当成闪烁，带货片结尾停在行动号召上就好
"调色": "明亮清新", "暗角": False, "歌词": False, "HUD": None, "闪帧": False, "故障": False, "颗粒": 0, "淡出": 0,
          "背景乐音量": -18, "贴纸": "", "价格": "", "行动": "点下方小黄车 ›"}
口播默认 = {"调色": "无", "暗角": False, "歌词": False, "HUD": None, "闪帧": False, "故障": False, "颗粒": 0, "淡出": 0,
          "背景乐音量": -22, "片尾引导": ""}
画幅表 = {"9:16": (1080, 1920), "16:9": (1920, 1080), "3:4": (1080, 1440), "4:3": (1440, 1080), "1:1": (1080, 1080)}


def 是带货(P, 用户):
    if 用户.get("类型"):
        return 用户["类型"] == "带货"
    return any(s.get("台词", "").strip() not in ("", "—", "-") for s in 镜头表.读镜头表(P / "分镜.md"))


def 读设置(P):
    s = json.loads(json.dumps(默认))
    f = P / "剪辑.json"
    用户 = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    if 用户.get("类型") == "口播" or (not 用户.get("类型") and (P / "口播" / "清剪.json").exists()):
        s.update(json.loads(json.dumps(口播默认)))
        s["类型"] = "口播"
    elif (P / "分镜.md").exists() and 是带货(P, 用户):
        s.update(json.loads(json.dumps(带货默认)))
        s["类型"] = "带货"
    if 用户:
        for k, v in 用户.items():
            if isinstance(v, dict) and isinstance(s.get(k), dict):
                s[k].update(v)
            else:
                s[k] = v
    return s


def 色值(c):
    return "0x" + c[1:] if str(c).startswith("#") else c


class 文字:
    """drawtext 的文字都写进临时文件（不用转义），textfile 引用。"""

    def __init__(self, 目录):
        self.目录, self.n = 目录, 0

    def 文件(self, text):
        self.n += 1
        p = self.目录 / f"{self.n:04d}.txt"
        p.write_text(text, encoding="utf-8")
        return 媒体.滤镜路径(p)

    def 写(self, text, 字体路径, 大小, x, y, 颜色="white", 起=None, 止=None, 淡入=0.0, 边=0, 展开=False, 额外=""):
        f = [f"fontfile={媒体.滤镜路径(字体路径)}", f"textfile={self.文件(text)}", f"fontsize={int(大小)}", f"fontcolor={色值(颜色)}",
             f"x={x}", f"y={y}", f"expansion={'normal' if 展开 else 'none'}"]
        if 边:
            f += [f"borderw={边}", "bordercolor=black@0.55", f"shadowx={边}", f"shadowy={边}", "shadowcolor=black@0.35"]
        if 起 is not None:
            f.append(f"enable='between(t,{起:.3f},{止:.3f})'")
            if 淡入:
                f.append(f"alpha='min(1,(t-{起:.3f})/{淡入})'")
        return "drawtext=" + ":".join(f) + 额外


def 口播收刀(P):
    """剪辑方案 → 刀：连着几句同一个素材合成一刀；「—」＝从粗剪里取同一时间的主人画面。"""
    清 = json.loads((P / "口播" / "清剪.json").read_text(encoding="utf-8"))
    粗 = Path(清["粗剪"])
    表 = 镜头表.读镜头表(P / "分镜.md")
    if not 表:
        sys.exit(f"NO_TABLE：{P / '分镜.md'} 里没有剪辑方案。先跑 reel-board/镜头表.py 口播 {P}")
    刀们, 缺 = [], []
    for s in 表:
        素材 = s.get("素材", "").strip()
        主人 = 素材 in ("", "—", "-", "无")
        if not 主人 and 刀们 and 刀们[-1]["素材"] == 素材:
            刀们[-1]["出"] = s["出"]
            刀们[-1]["长"] = s["出"] - 刀们[-1]["进"]
            continue
        if 主人 and 刀们 and 刀们[-1]["素材"] == "主人" and abs(刀们[-1]["出"] - s["进"]) < 0.01:
            刀们[-1]["出"] = s["出"]
            刀们[-1]["长"] = s["出"] - 刀们[-1]["进"]
            continue
        写 = s.get("画面", "") + s.get("备注", "")
        动 = next((k for k in ("快推", "拉", "左移", "右移", "静止") if k in 写), "慢推")  # 方案里写了镜头动作就照它，没写慢推
        d = {"号": len(刀们) + 1, "进": s["进"], "出": s["出"], "长": s["出"] - s["进"], "大字": "", "动": 动, "备注": "",
             "起": 0.0, "景别": "", "素材": "主人" if 主人 else 素材}
        if 主人:
            if not 清["有画面"]:
                缺.append(f"第 {s['号']} 句（只有声音，要配画面）")
                continue
            d["种"], d["文件"], d["起"] = "视频", 粗, s["进"]
        elif (P / 素材).exists():
            d["种"], d["文件"] = ("视频" if (P / 素材).suffix.lower() in (".mp4", ".mov", ".webm", ".mkv", ".m4v") else "静帧"), P / 素材
        else:
            缺.append(f"第 {s['号']} 句（{素材}）")
            continue
        刀们.append(d)
    if 缺:
        sys.exit("MISSING：这些句子的画面还没有：" + "、".join(缺) + "。照剪辑方案补素材，或先改成主人出镜「—」")
    return 刀们


def 口播混音(P, 总长, 设置):
    """粗剪里的人声＋背景乐（有就放，人声时自动压低）→ 出片/.混音.wav；再交给 音频链 统一响度。"""
    粗 = json.loads((P / "口播" / "清剪.json").read_text(encoding="utf-8"))["粗剪"]
    入, 链 = ["-i", 粗], [f"[0:a]aresample=48000,apad=whole_dur={总长:.3f},atrim=0:{总长:.3f}[人声]"]
    乐 = next((p for p in sorted((P / "音乐").glob("歌.*")) if p.suffix.lower() in (".wav", ".mp3", ".m4a", ".aac", ".flac")), None) \
        if (P / "音乐").is_dir() else None
    if 乐:
        入 += ["-i", 乐]
        链.append(f"[1:a]aresample=48000,aloop=loop=-1:size=2e9,atrim=0:{总长:.3f},volume={float(设置.get('背景乐音量', -22))}dB[乐]")
        链 += ["[人声]asplit[人1][人2]", "[乐][人1]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[压]",
              "[压][人2]amix=inputs=2:normalize=0[混]"]
    else:
        链.append("[人声]anull[混]")
    out = P / "出片" / ".混音.wav"
    媒体.跑(*入, "-filter_complex", ";".join(链), "-map", "[混]", "-ac", "2", "-ar", "48000", "-t", f"{总长:.3f}", out)
    return out


def 收刀(P, 设置, 允许超窗=False):
    if 设置.get("类型") == "口播":
        return 口播收刀(P)
    表 = 镜头表.读镜头表(P / "分镜.md")
    if not 表:
        sys.exit(f"NO_TABLE：{P / '分镜.md'} 里没有镜头表")
    窗 = 镜头表.读窗口表(P / "视频" / "可用窗口.md")
    刀们, 缺, 超 = [], [], []
    for s in 表:
        号 = int(s["号"])
        d = {"号": 号, "进": s["进"], "出": s["出"], "长": s["出"] - s["进"], "大字": 体检.大字词(s.get("大字", ""))[0],
             "动": s.get("镜头动作", ""), "备注": s.get("备注", ""), "起": 0.0, "景别": s.get("景别", "")}
        if d["大字"] in ("—", "-", "无", "【待填】"):
            d["大字"] = ""
        素材 = s.get("素材", "").strip()
        静帧 = next((p for p in (P / "静帧" / f"{号:02d}.png", P / "静帧" / f"{号:02d}.jpg", P / "静帧" / f"{号}.png") if p.exists()), None)
        if 素材 in ("", "—", "-", "无") or "纯大字" in d["备注"]:
            d["种"] = "色"
        elif (P / 素材).exists() and (P / 素材).suffix.lower() in (".mp4", ".mov", ".webm", ".mkv"):
            d["种"], d["文件"] = "视频", P / 素材
            w = 窗.get(str(号))
            if w:
                d["起"] = w["起"]
                if d["长"] > w["止"] - w["起"] + 0.05:
                    超.append(f"第 {号} 刀要 {d['长']:.2f} 秒，可用窗口只有 {w['止'] - w['起']:.2f} 秒（{w['起']}–{w['止']}）")
        elif (P / 素材).exists():
            d["种"], d["文件"] = "静帧", P / 素材
        elif 静帧:
            d["种"], d["文件"] = "静帧", 静帧
        else:
            缺.append(f"第 {号} 刀（{素材}）")
            continue
        刀们.append(d)
    if 缺:
        sys.exit("MISSING：这些刀还没有素材：" + "、".join(缺) + "。出完视频再剪，或者先放 静帧/<号>.png 用静帧慢推代替")
    if 超 and not 允许超窗:
        sys.exit("OVER_WINDOW：" + "；".join(超) + "。缩短这一刀（改分镜）或重出视频；主人同意停在最后一帧就加 --允许超窗")
    return 刀们


def 找歌(P, 设置):
    if 设置.get("歌"):
        return P / 设置["歌"]
    for p in sorted((P / "音乐").glob("歌.*")):
        if p.suffix.lower() in (".wav", ".mp3", ".m4a", ".aac", ".flac"):
            return p
    sys.exit("NO_SONG：音乐/ 里没有 歌.wav（或 歌.mp3）。先用 reel-music 剪好歌")


def 构图(P, 设置, 刀们, W, H, 字目录, 粗=False, 要底片=False):
    fps = int(设置["帧率"])
    入, 链 = [], []
    for i, d in enumerate(刀们):
        L = d["长"]
        if d["种"] == "视频":
            入 += ["-ss", f"{d['起']:.3f}", "-t", f"{L + 0.2:.3f}", "-i", d["文件"]]
            链.append(f"[{i}:v]fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                     f"tpad=stop_mode=clone:stop_duration=2,trim=duration={L:.4f},setpts=PTS-STARTPTS,format=yuv420p[v{i}]")
        elif d["种"] == "静帧":
            入 += ["-loop", "1", "-framerate", str(fps), "-t", f"{L + 0.2:.3f}", "-i", d["文件"]]
            n = max(1, int(L * fps))
            动 = d["动"]
            x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
            if "快推" in 动:  # 钩子：0.35 秒快速推近再停住
                z = f"min(1.12,1+0.12*on/{max(1, int(0.35 * fps))})"
            elif "静止" in 动 or "不动" in 动:
                z = "1"
            elif "左移" in 动 or "右移" in 动:
                z = "1.08"
                x = f"(iw-iw/zoom)*{'(1-on/' + str(n) + ')' if '左移' in 动 else 'on/' + str(n)}"
            elif "拉" in 动:
                z = f"1.06-0.06*on/{n}"
            else:
                z = f"1+0.06*on/{n}"
            链.append(f"[{i}:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
                     f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={W}x{H}:fps={fps},setsar=1,"
                     f"trim=duration={L:.4f},setpts=PTS-STARTPTS,format=yuv420p[v{i}]")
        else:
            入 += ["-f", "lavfi", "-t", f"{L + 0.2:.3f}", "-i", f"color=c={设置['底色']}:s={W}x{H}:r={fps}"]
            链.append(f"[{i}:v]setsar=1,trim=duration={L:.4f},setpts=PTS-STARTPTS,format=yuv420p[v{i}]")
    n = len(刀们)
    链.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[底]")
    链.append(f"[底]{调色.滤镜(设置['调色'], float(设置['调色强度']))}[调]")
    当前 = "调"
    if 设置.get("暗角"):
        链.append(f"[{当前}]vignette=angle=PI/5[暗]")
        当前 = "暗"
    if 要底片:
        return 入, 链, 当前, n
    字 = 文字(字目录)
    总长 = 刀们[-1]["出"]
    大 = 设置["大字"]
    片尾 = 设置.get("片尾") or {}
    尾起 = max(刀们[-1]["进"], 总长 - 2.5) if 片尾.get("字") else 总长  # 片尾最多占最后 2.5 秒
    层, 前层 = [], []  # 前层：近景、特写这类人占满画面的刀，字压在人身后会被整个挡住，放到人前面
    for d in 刀们:
        t = d["大字"]
        if not t:
            continue
        止 = min(d["出"], 尾起)  # 片尾一出来，这一刀的大字就让位
        if 止 - d["进"] < 0.1:
            continue
        单位 = sum(1.0 if 字体.是中文(c) else 0.55 for c in t) or 1
        号字 = min(float(大["字号"]) * 0.30 * min(W, H * 0.6), 0.86 * W / 单位)
        y = {"上": f"{H * 0.16:.0f}", "下": f"{H * 0.62:.0f}-text_h"}.get(大["位置"], "(h-text_h)/2")
        画 = 字.写(t, 字体.挑(t, P), 号字, "(w-text_w)/2", y, 大["颜色"], d["进"], 止 - 0.001, 淡入=0.06, 边=max(2, int(号字 / 40)))
        (前层 if any(k in d["景别"] for k in ("近景", "特写")) else 层).append(画)
    遮罩 = P / "出片" / "遮罩.mp4"
    if 层 and 大.get("压人身后") and 遮罩.exists() and not 粗:
        入 += ["-i", 遮罩]
        n_入 = n
        n += 1
        链.append(f"[{当前}]split[背][前源]")
        链.append(f"[背]{','.join(层)}[有字]")
        链.append(f"[{n_入}:v]scale={W}:{H},format=gray,setpts=PTS-STARTPTS[遮]")
        链.append("[前源]format=yuva420p[前a];[前a][遮]alphamerge[前]")
        链.append("[有字][前]overlay=format=auto:shortest=1[叠]")
        当前 = "叠"
    elif 层:
        链.append(f"[{当前}]{','.join(层)}[叠]")
        当前 = "叠"
    上层 = list(前层)
    中文字体 = 字体.找("中文", P)
    英文字体 = 字体.找("英文", P)
    竖 = H > W
    if 设置.get("歌词") and (P / "音乐" / "歌词.json").exists():
        for 行 in json.loads((P / "音乐" / "歌词.json").read_text(encoding="utf-8"))["行"]:
            text, 位, 字们 = 行["行"], 0, 行["字"]
            for k, (w, a, _) in enumerate(字们):
                位 = text.find(w, 位) + len(w) if text.find(w, 位) >= 0 else 位
                止 = 字们[k + 1][1] if k + 1 < len(字们) else 行["止"]
                if 止 > a and a < 总长:
                    上层.append(字.写(text[:位], 中文字体, W * 0.055, "(w-text_w)/2", f"{H * (0.70 if 竖 else 0.80):.0f}", "white",
                                    a, min(止, 总长) - 0.001, 边=3))
    hud = 设置.get("HUD")
    if hud:
        x0, y0 = (W * 0.07, H * 0.11) if 竖 else (W * 0.04, H * 0.05)
        标题 = hud.get("标题") or ""
        上层.append(字.写("● REC  " + 标题, 中文字体, W * 0.028, f"{x0:.0f}", f"{y0:.0f}", "white@0.9", 边=2))
        上层.append(字.写("%{pts\\:hms}", 英文字体, W * 0.028, f"w-text_w-{x0:.0f}", f"{y0:.0f}", "white@0.9", 边=2, 展开=True))
        拍子 = P / "音乐" / "拍子.json"
        副 = hud.get("副标题") or (f"{json.loads(拍子.read_text(encoding='utf-8'))['bpm']:.0f} BPM" if 拍子.exists() else "")
        if 副:
            上层.append(字.写(副, 中文字体, W * 0.022, f"{x0:.0f}", f"{y0 + W * 0.04:.0f}", "white@0.7", 边=2))
    if 设置.get("跑马灯"):
        上层.append(字.写(("    ".join([设置["跑马灯"]] * 6)), 英文字体, W * 0.03, f"'w-mod(t*{W * 0.22:.0f},w+text_w)'",
                       f"{H * (0.765 if 竖 else 0.9):.0f}", "white@0.85", 边=2))
    if 片尾.get("字"):
        起 = 尾起
        上层.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.5:t=fill:enable='between(t,{起:.3f},{总长:.3f})'")
        上层.append(字.写(片尾["字"], 字体.挑(片尾["字"], P), W * 0.11, "(w-text_w)/2", "(h-text_h)/2", 大["颜色"], 起, 总长, 淡入=0.25, 边=3))
        if 片尾.get("副"):
            上层.append(字.写(片尾["副"], 中文字体, W * 0.035, "(w-text_w)/2", f"(h/2)+{W * 0.1:.0f}", "white@0.85", 起 + 0.3, 总长,
                           淡入=0.25, 边=2))
    拍子 = json.loads((P / "音乐" / "拍子.json").read_text(encoding="utf-8")) if (P / "音乐" / "拍子.json").exists() else {}
    落点 = [x for x in 拍子.get("大落点", []) if x < 总长]
    if 设置.get("闪帧"):
        上次 = -9.0
        for d in 刀们[1:]:
            c = d["进"]
            猛 = any(abs(c - x) < 0.06 for x in 落点)
            if c - 上次 >= 0.34 or 猛:  # 1 秒最多 3 闪（光敏）
                上层.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=white@{0.85 if 猛 else 0.5}:t=fill:"
                          f"enable='between(t,{c:.3f},{c + (0.066 if 猛 else 0.033):.3f})'")
                上次 = c
    if 设置.get("故障"):
        for x in 落点:
            上层.append(f"rgbashift=rh=-{W // 70}:bh={W // 70}:enable='between(t,{x:.3f},{x + 0.2:.3f})'")
    if 设置.get("颗粒") and not 粗:
        上层.append(f"noise=alls={int(设置['颗粒'])}:allf=t")
    if 设置.get("类型") in ("带货", "口播"):
        a, 字目 = 字幕.ass(P, 设置, 总长, W, H)
        上层.append(f"ass=filename={媒体.滤镜路径(a)}:fontsdir={媒体.滤镜路径(字目)}")
    淡 = float(设置.get("淡出") or 0)
    if 淡:
        上层.append(f"fade=t=out:st={max(0, 总长 - 淡):.3f}:d={淡}")
    上层.append("format=yuv420p")
    链.append(f"[{当前}]{','.join(上层)}[画]")
    return 入, 链, "画", n


def 音频链(歌, 歌序号, 总长, 设置):
    """先量这一段歌有多响，整体加减增益到 -14 LUFS，再用限幅器压到 -3 dB（AAC 编码后峰值会冒上来约 1 dB，留足余量；单遍 loudnorm 对短片拉不上去）。"""
    淡 = float(设置.get("淡出") or 0)
    前 = f"apad,atrim=0:{总长:.3f},asetpts=PTS-STARTPTS" + (f",afade=t=out:st={max(0, 总长 - 淡):.3f}:d={淡}" if 淡 else "")
    量 = re.findall(r"I:\s+(-?[\d.]+) LUFS", 媒体.分析("-i", 歌, "-af", 前 + ",ebur128", "-f", "null", "-"))
    增益 = max(-20.0, min(20.0, -14.0 - float(量[-1]))) if 量 else 0.0
    return f"[{歌序号}:a]{前},volume={增益:.2f}dB,alimiter=limit=0.708:level=false,aresample=48000[声]"


def 带货混音(P, 刀们, 总长, 设置):
    """配音按刀放（每刀开头 0.15 秒出声）＋背景乐（有人声时自动压低）→ 出片/.混音.wav；再交给 音频链 统一响度。"""
    入, 链, 声们 = [], [], []
    for d in 刀们:
        f = P / "配音" / f"{d['号']:02d}.wav"
        if f.exists():
            k = len(入) // 2
            入 += ["-i", f]
            链.append(f"[{k}:a]aresample=48000,adelay={int((d['进'] + 0.15) * 1000)}:all=1[人{k}]")
            声们.append(f"[人{k}]")
    乐 = None
    for p in sorted((P / "音乐").glob("歌.*")) if (P / "音乐").is_dir() else []:
        if p.suffix.lower() in (".wav", ".mp3", ".m4a", ".aac", ".flac"):
            乐 = p
            break
    if not 声们 and not 乐:
        sys.exit("NO_AUDIO：带货片既没有配音（配音/<号>.wav）也没有背景乐（音乐/歌.mp3）。先跑 reel-voice 配音，或放一首自带曲进 音乐/")
    if 声们:
        链.append("".join(声们) + f"amix=inputs={len(声们)}:normalize=0:duration=longest,apad=whole_dur={总长:.3f},atrim=0:{总长:.3f}[人声]")
    if 乐:
        k = len(入) // 2
        入 += ["-i", 乐]
        链.append(f"[{k}:a]aresample=48000,aloop=loop=-1:size=2e9,atrim=0:{总长:.3f},volume={float(设置.get('背景乐音量', -18))}dB[乐]")
        if 声们:
            链.append("[人声]asplit[人1][人2]")
            链.append("[乐][人1]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[压]")
            链.append("[压][人2]amix=inputs=2:normalize=0[混]")
        else:
            链.append("[乐]anull[混]")
    else:
        链.append("[人声]anull[混]")
    out = P / "出片" / ".混音.wav"
    脚本 = out.with_name(".混音滤镜.txt")
    脚本.write_text(";\n".join(链), encoding="utf-8")
    try:
        媒体.跑(*入, "-filter_complex_script", 脚本, "-map", "[混]", "-ac", "2", "-ar", "48000", "-t", f"{总长:.3f}", out)
    finally:
        脚本.unlink()
    return out


def 压峰值(out, 上限=-1.5):
    """AAC 编码后峰值会冒上来：再量一次真峰值，超了就只把声音整体调低超出的那点（视频直接复制，不重编码）。"""
    峰 = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", 媒体.分析("-i", out, "-af", "ebur128=peak=true", "-f", "null", "-"))
    if not 峰 or float(峰[-1]) <= 上限:
        return
    tmp = Path(out).with_name(".压峰值.mp4")
    媒体.跑("-i", out, "-map", "0", "-c:v", "copy", "-af", f"volume={上限 - float(峰[-1]) - 0.2:.2f}dB",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", tmp)
    tmp.replace(out)


def 跑图(入, 链, 出参数):
    脚本 = Path(出参数[-1]).with_name(".滤镜.txt")
    脚本.write_text(";\n".join(链), encoding="utf-8")
    try:
        媒体.跑(*入, "-filter_complex_script", 脚本, *出参数)
    finally:
        脚本.unlink()


def 下一个版本(出片):
    if not (出片 / "成片.mp4").exists():
        return 出片 / "成片.mp4"
    k = 2
    while (出片 / f"成片_v{k}.mp4").exists():
        k += 1
    return 出片 / f"成片_v{k}.mp4"


def main():
    ap = argparse.ArgumentParser(description="卡点剪辑")
    ap.add_argument("做", choices=["粗剪", "几帧", "底片", "成片"])
    ap.add_argument("项目")
    ap.add_argument("--秒", help="几帧模式：要看的秒数，逗号隔开")
    ap.add_argument("--跳过体检", action="store_true")
    ap.add_argument("--不查关口", action="store_true")
    ap.add_argument("--允许超窗", action="store_true")
    g = ap.parse_args()
    P = Path(g.项目).resolve()
    设置 = 读设置(P)
    if 设置["画幅"] not in 画幅表:
        sys.exit(f"剪辑.json 的画幅只认：{'、'.join(画幅表)}")
    W, H = 画幅表[设置["画幅"]]
    if not g.跳过体检:
        _, 坏, _, _ = 体检.查(P / "分镜.md")
        if 坏:
            sys.exit("AUDIT_FAILED：镜头表体检没过：\n" + "\n".join(f"- 第 {a} 刀：{b} → {c}" for a, b, c in 坏)
                     + "\n先照 reel-board 改镜头表（问过主人），或主人同意后加 --跳过体检")
    if g.做 == "成片" and not g.不查关口:
        关 = P / "进度" / "关口.json"
        if "粗剪" not in (json.loads(关.read_text(encoding="utf-8")) if 关.exists() else {}):
            sys.exit("GATE：粗剪主人还没点头。先出粗剪给主人看，点头后跑 进度.py 关口 <项目> 粗剪 过")
    刀们 = 收刀(P, 设置, g.允许超窗)
    总长 = 刀们[-1]["出"]
    出片 = P / "出片"
    出片.mkdir(parents=True, exist_ok=True)
    字目录 = 出片 / ".字"
    shutil.rmtree(字目录, ignore_errors=True)
    字目录.mkdir()
    fps = int(设置["帧率"])
    try:
        if g.做 == "底片":
            入, 链, 末, _ = 构图(P, 设置, 刀们, W, H, 字目录, 要底片=True)
            out = 出片 / "底片.mp4"
            跑图(入, 链, ["-map", f"[{末}]", "-r", fps, "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p",
                       "-t", f"{总长:.3f}", out])
            print(f"OK {out}（{总长:.2f} 秒，没字）。下一步：python3 {HERE / '抠像.py'} {out} {出片 / '遮罩.mp4'}")
        elif g.做 == "几帧":
            if not g.秒:
                sys.exit("几帧模式要 --秒 1.0,5.2")
            秒们 = [float(x) for x in g.秒.replace("，", ",").split(",") if x.strip()]
            入, 链, 末, n = 构图(P, 设置, 刀们, W, H, 字目录)
            选 = "+".join(f"eq(n\\,{int(round(t * fps))})" for t in 秒们)
            链.append(f"[{末}]select='{选}'[选]")
            d = 出片 / "几帧"
            d.mkdir(exist_ok=True)
            跑图(入, 链, ["-map", "[选]", "-fps_mode", "passthrough", d / "帧_%02d.png"])
            print(f"OK {d}：" + "、".join(f"帧_{i + 1:02d}.png＝{t} 秒" for i, t in enumerate(秒们)))
        else:
            粗 = g.做 == "粗剪"
            w, h = (W // 2 // 2 * 2, H // 2 // 2 * 2) if 粗 else (W, H)
            入, 链, 末, n = 构图(P, 设置, 刀们, w, h, 字目录, 粗=粗)
            歌 = 带货混音(P, 刀们, 总长, 设置) if 设置.get("类型") == "带货" else 口播混音(P, 总长, 设置) if 设置.get("类型") == "口播" else 找歌(P, 设置)
            入 += ["-i", 歌]
            链.append(音频链(歌, n, 总长, 设置))
            if 粗:
                (出片 / "粗剪").mkdir(exist_ok=True)
                out = 出片 / "粗剪" / "粗剪.mp4"
                编码 = ["-preset", "veryfast", "-crf", "26"]
            else:
                out = 下一个版本(出片)
                编码 = ["-preset", "medium", "-crf", "18", "-maxrate", "8500k", "-bufsize", "17000k"]
            跑图(入, 链, ["-map", f"[{末}]", "-map", "[声]", "-r", fps, "-c:v", "libx264", *编码, "-pix_fmt", "yuv420p",
                       "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-t", f"{总长:.3f}", out])
            if not 粗:
                压峰值(out)
            if 粗:
                标字 = 文字(字目录 / "标")
                标字.目录.mkdir(exist_ok=True)
                标 = [标字.写(f"#{d['号']}  {d['进']:.2f}–{d['出']:.2f}  {d['大字']}", 字体.找("中文", P), 22, 8, 8, "yellow",
                                  d["进"], d["出"] - 0.001, 边=2) for d in 刀们]
                选 = "+".join(f"eq(n\\,{int(round((d['进'] + d['长'] / 2) * fps))})" for d in 刀们)
                行数 = (len(刀们) + 4) // 5
                媒体.跑("-i", out, "-vf", ",".join(标) + f",select='{选}',setpts=N/TB,tile=5x{行数}:padding=3:color=0x101010",
                       "-frames:v", "1", "-q:v", "3", 出片 / "粗剪" / "联系表.jpg")
                print(f"OK 粗剪：{out}（{w}×{h}，{总长:.2f} 秒，{len(刀们)} 刀）＋ {出片 / '粗剪' / '联系表.jpg'}（每刀中间一帧）")
                print("给主人看：顺序、节奏、大字对不对；点头后跑 进度.py 关口 <项目> 粗剪 过，再出成片")
            else:
                Path(str(out)[:-4] + ".设置.json").write_text(json.dumps(设置, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"OK {out}（{W}×{H}，{总长:.2f} 秒）" + ("" if 设置.get("类型") == "口播" else "；大字压在人身后" if (出片 / "遮罩.mp4").exists() and 设置["大字"].get("压人身后") else
                                                     "；没有遮罩，大字在人前面"))
                print(f"下一步：python3 {HERE.parent / 'reel-check' / '质检.py'} 查 {out}"
                      + (f"；再 python3 {HERE.parent / 'reel-check' / '质检.py'} 口播 {out} --稿 {P / '稿子.md'}" if 设置.get("类型") == "口播" else ""))
    finally:
        shutil.rmtree(字目录, ignore_errors=True)


if __name__ == "__main__":
    main()

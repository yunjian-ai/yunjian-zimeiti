"""掠影自测：python3 members/reel/tests/run_tests.py（只用标准库；脚本写一个就在这里加一组用例）。"""
import subprocess
import sys
import tempfile
from pathlib import Path

S = Path(__file__).resolve().parent.parent / "skills"
坏 = []


def 跑(脚本, *参数):
    r = subprocess.run([sys.executable, str(S / 脚本), *参数], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def 应该(条件, 说明):
    if not 条件:
        坏.append(说明)


# 进度.py：接着上次做（考题第 20 题的情景）
with tempfile.TemporaryDirectory() as t:
    p = Path(t) / "夜跑"
    for g in ("需求", "锁定", "分镜"):
        跑("reel-brief/进度.py", "关口", str(p), g, "过")
    (p / "音乐").mkdir(parents=True)
    (p / "音乐" / "拍子.json").write_text("{}")
    (p / "分镜.md").write_text("")
    (p / "静帧").mkdir()
    (p / "静帧" / "01.png").write_text("")
    跑("reel-brief/进度.py", "纠正", str(p), "不要叉腿，站直")
    _, out = 跑("reel-brief/进度.py", "看", str(p))
    应该("在哪：5 静帧" in out, "进度.py：做到静帧没认出来")
    应该("「不要叉腿，站直」" in out, "进度.py：纠正没报出来")
    跑("reel-brief/进度.py", "关口", str(p), "前三张", "过")
    _, out = 跑("reel-brief/进度.py", "看", str(p))
    应该("在哪：6 视频" in out, "进度.py：前三张过了没往下走")
    跑("reel-brief/进度.py", "关口", str(p), "锁定", "撤")
    _, out = 跑("reel-brief/进度.py", "看", str(p))
    应该("在哪：2 锁人" in out, "进度.py：撤了关口没退回去")
    code, _ = 跑("reel-brief/进度.py", "关口", str(p), "乱写", "过")
    应该(code != 0, "进度.py：不认识的关口名没拦住")


# 体检.py：考题第 10 题那 9 类毛病都要报；干净的表要放行
坏表 = """140 拍／分
| # | 进–出（秒） | 景别 | 人物动作 | 镜头动作 | 大字 | 素材 |
|---|---|---|---|---|---|---|
| 1 | 0.000–1.714 | 全身 | 站定 | 慢推 | NIGHT | v/01.mp4 |
| 2 | 1.714–3.429 | 特写 | 抬眼 | 微推 | RUN | v/02.mp4 |
| 3 | 3.429–5.143 | 特写 | 跟着歌词唱、对口型 | 手持 | GO | v/03.mp4 |
| 4 | 5.143–5.400 | 中景 | 看手机 | 横移 | NIGHT RUN（一直显示到 8.0 秒） | v/02.mp4 |
| 5 | 5.400–6.857 | 全身 | 原地小跑 | 360 度环绕 | MOVE | v/05.mp4 |
| 6 | 6.857–8.571 | 近景 | 拉帽子 | 先推近、再横移、最后升起 | HOOD | v/06.mp4 |
| 7 | 8.571–10.286 | 全身 | 两腿叉开深蹲 | 低机位慢推 | LOW | v/07.mp4 |
| 8 | 10.286–12.000 | 远景 | 走远 | 慢拉 | 夜跑 | v/08.mp4 |
"""
好表 = 坏表.replace("跟着歌词唱、对口型", "抬手看表").replace("| 3 | 3.429–5.143 | 特写", "| 3 | 3.429–5.143 | 中景") \
    .replace("5.143–5.400 | 中景", "5.143–5.571 | 近景").replace("NIGHT RUN（一直显示到 8.0 秒） | v/02.mp4", "FAST | v/04.mp4") \
    .replace("5.400–6.857", "5.571–6.857").replace("360 度环绕", "弧移").replace("先推近、再横移、最后升起", "慢推") \
    .replace("两腿叉开深蹲", "靠墙站直").replace("| 夜跑 |", "| HOME |")
with tempfile.TemporaryDirectory() as t:
    (Path(t) / "坏.md").write_text(坏表, encoding="utf-8")
    code, out = 跑("reel-board/体检.py", str(Path(t) / "坏.md"))
    for 词 in ("景别都是", "对口型", "太短", "重复", "两个词", "跨过", "不在拍上", "360", "3 个镜头动作", "不像真人", "中英混用"):
        应该(词 in out, f"体检.py：没报出「{词}」")
    应该(code == 1, "体检.py：有毛病退出码应该是 1")
    (Path(t) / "好.md").write_text(好表, encoding="utf-8")
    code, out = 跑("reel-board/体检.py", str(Path(t) / "好.md"))
    应该(code == 0, "体检.py：干净的表没放行：" + out[-300:])


# 带货片（v0.2）：镜头表认四列、改时间只改那一格；合规挑出考题 B6 那几类；体检要求卖点有证明；字幕 ASS 字体名带粗细
带货表 = """| # | 进–出（秒） | 景别 | 镜头动作 | 画面 | 台词 | 字幕 | 花字 | 卖点 | 素材 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0–2 | 近景 | 快推 | 拉领口 | 毛衣总扎脖子？ | 毛衣总**扎脖子**？ | 扎脖子？ | — | 静帧/01.png | 钩子 |
| 2 | 2–4.6 | 中景 | 慢推 | 亮相 | 试试这件手工粗针开衫。 | 试试这件**手工粗针**开衫 | — | — | 静帧/02.png | |
| 3 | 4.6–7.5 | 特写 | 微距推近 | 针目 | 一针一针手工织。 | 一针一针／**手工织** | 手工粗针 | 手工粗针 | 静帧/03.png | |
| 4 | 7.5–10 | 近景 | 慢推 | 扣子 | 五颗胡桃木扣。 | 五颗**胡桃木扣** | — | 胡桃木扣 | 静帧/04.png | 字幕上 |
| 5 | 10–13 | 中景 | 静止 | 结尾卡 | 喜欢就点下方小黄车。 | 喜欢就点**小黄车** | — | — | 静帧/05.png | 行动号召 |
"""
sys.path.insert(0, str(S / "reel-board"))
import 镜头表  # noqa: E402
with tempfile.TemporaryDirectory() as t:
    P = Path(t) / "开衫"
    P.mkdir()
    (P / "分镜.md").write_text(带货表, encoding="utf-8")
    (P / "卖点.md").write_text("卖点：手工粗针 · 新西兰羊毛 · 胡桃木扣\n吊牌：羊毛 70%、锦纶 30%\n", encoding="utf-8")
    表 = 镜头表.读镜头表(P / "分镜.md")
    应该(表[2]["台词"] == "一针一针手工织。" and 表[2]["卖点"] == "手工粗针" and 表[0]["花字"] == "扎脖子？" and 表[0].get("大字", "") == "",
         "镜头表.py：带货四列没认对（字幕、花字不能被当成大字）")
    原 = (P / "分镜.md").read_text(encoding="utf-8")
    镜头表.改时间(P / "分镜.md", {"1": (0, 1.5), "2": (1.5, 4.0)})
    新 = (P / "分镜.md").read_text(encoding="utf-8")
    应该("| 0.00–1.50 |" in 新 and "| 1.50–4.00 |" in 新 and 新.count("|") == 原.count("|") and "毛衣总**扎脖子**？" in 新,
         "镜头表.py 改时间：只该改进–出那一格")
    code, out = 跑("reel-check/合规.py", str(P))
    应该(code == 0 and "PASS" in out, "合规.py：干净的台词不该报：" + out[-300:])
    坏词 = 带货表.replace("毛衣总扎脖子？ |", "这是最好看的开衫！ |").replace("一针一针手工织。 |", "顶级手工，100% 羊毛，零扎感。 |") \
        .replace("五颗胡桃木扣。 |", "加微信 maoyi_8888 领券。 |")
    (P / "分镜.md").write_text(坏词, encoding="utf-8")
    code, out = 跑("reel-check/合规.py", str(P))
    for 词 in ("最好看", "顶级", "100%", "导流", "零扎"):
        应该(词 in out, f"合规.py：没报出「{词}」")
    应该(code == 1 and out.count("「最好") == 1, "合规.py：有 ❌ 退出码应该是 1，「最好」「最好看」只报一次")
    (P / "卖点.md").write_text("卖点：手工粗针 · 胡桃木扣\n吊牌：羊毛 70%\n不能写：纯羊毛、零扎感\n", encoding="utf-8")
    code, out = 跑("reel-check/合规.py", str(P))
    应该("零扎" in out, "合规.py：卖点.md 里「不能写」那行的词不该算出处")
    (P / "分镜.md").write_text(带货表.replace("| 手工粗针 | 静帧/03.png", "| — | 静帧/03.png").replace("| 胡桃木扣 | 静帧/04.png", "| — | 静帧/04.png"), encoding="utf-8")
    code, out = 跑("reel-board/体检.py", str(P / "分镜.md"))
    应该(code == 1 and "证明哪个卖点" in out, "体检.py：带货片中间几刀没写卖点没拦住")
    sys.path.insert(0, str(S / "reel-cut"))
    import 字幕  # noqa: E402
    for 名, 粗细, 应 in (("Source Han Sans CN", "Heavy", "Source Han Sans CN Heavy"), ("Noto Sans CJK SC", "Bold", "Noto Sans CJK SC")):
        class 假:
            def getname(self, 名=名, 粗细=粗细):
                return (名, 粗细)
        try:
            from PIL import ImageFont
            原函数 = ImageFont.truetype
            ImageFont.truetype = lambda *a, **k: 假()
            应该(字幕.字体名("x") == 应, f"字幕.py：字体名应该是「{应}」（只写家族名 libass 认不出 Heavy，会变方框）")
            ImageFont.truetype = 原函数
        except ImportError:
            pass


def 有音视频工具():
    try:
        import numpy  # noqa: F401
        sys.path.insert(0, str(S / "reel-brief"))
        import 媒体
        媒体.ffmpeg()
        return True
    except (ImportError, SystemExit):
        return False


def 合成曲(path, bpm=120, 小节=16, 鼓从=4, 垫=0.04):
    """标准库合成一段测试曲：前几小节只有低声的长音，第「鼓从」小节起每拍一声底鼓、重拍更响。"""
    import math
    import struct
    import wave
    sr, 拍 = 22050, 60 / bpm
    n = int(sr * 小节 * 4 * 拍)
    y = [垫 * math.sin(2 * math.pi * 220 * i / sr) for i in range(n)]
    for k in range(鼓从 * 4, 小节 * 4):
        s0, g = int(k * 拍 * sr), (0.9 if k % 4 == 0 else 0.55)
        for i in range(int(0.15 * sr)):
            if s0 + i < n:
                t = i / sr
                y[s0 + i] += g * math.sin(2 * math.pi * (50 + 100 * math.exp(-t * 30)) * t) * math.exp(-t * 18)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 32000)) for v in y))


if 有音视频工具():
    import json
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        合成曲(t / "曲.wav")
        code, out = 跑("reel-music/节拍.py", str(t / "曲.wav"), "--out", str(t / "拍子.json"), "--click", str(t / "试听.wav"))
        应该(code == 0, "节拍.py 跑不起来：" + out[-300:])
        if code == 0:
            d = json.loads((t / "拍子.json").read_text(encoding="utf-8"))
            应该(abs(d["bpm"] - 120) < 1, f"节拍.py：速度扒成 {d['bpm']}，应该约 120")
            误差 = [abs(x / 0.5 - round(x / 0.5)) * 500 for x in d["拍"] if x >= 8]
            应该(误差 and max(误差) < 25, f"节拍.py：鼓点后的拍点偏了 {max(误差 or [0]):.0f} 毫秒（要 < 25）")
            应该(any(abs(x - 8.0) < 0.05 for x in d["大落点"]), f"节拍.py：大落点应该在 8 秒（鼓进来），扒成 {d['大落点']}")
            应该(any(abs(x - 8.0) < 0.05 for x in d["重拍"]), "节拍.py：8 秒应该是重拍")
            应该((t / "试听.wav").exists(), "节拍.py：--click 没出试听")
            for 曲, 速 in (("夜行-128.mp3", 128), ("慢灯-86.mp3", 86)):  # 切分节奏、慢歌：速度不能差 1 拍
                code, out = 跑("reel-music/节拍.py", str(S.parent / "库" / "音乐" / 曲), "--out", str(t / "库曲.json"))
                d2 = json.loads((t / "库曲.json").read_text(encoding="utf-8"))
                偏 = max(abs(x / (60 / 速) - round(x / (60 / 速))) * 60 / 速 * 1000 for x in d2["拍"])
                应该(abs(d2["bpm"] - 速) < 0.3 and 偏 < 25, f"节拍.py：{曲} 扒成 {d2['bpm']} 拍、最大偏 {偏:.0f} 毫秒")
            code, out = 跑("reel-music/剪歌.py", str(t / "曲.wav"), str(t / "短.wav"), "--秒", "10", "--拍子", str(t / "拍子.json"))
            import re
            长 = re.search(r"共 ([\d.]+) 秒", out)
            应该(code == 0 and 长 and abs(float(长[1]) - 10) < 0.03, "剪歌.py：10 秒应该是整 5 小节约 10 秒：" + out[-200:])
            应该("成片时间 = 原曲 − " in out, "剪歌.py：没报成片和原曲的时间对照")
            应该((t / "短.wav.对照.json").exists(), "剪歌.py：没写对照.json")
            (t / "词.txt").write_text("[主歌]\n夜里12点（耶）\n追逐梦想\n", encoding="utf-8")
            code, out = 跑("reel-music/歌词.py", "体检", str(t / "词.txt"), "--bpm", "120")
            应该(code == 1 and all(k in out for k in ("段落标记用英文", "阿拉伯数字", "括号", "套话")), "歌词.py 体检：漏报毛病")
            code, out = 跑("reel-board/切点.py", str(t / "拍子.json"), "--秒", "16", "--出", str(t / "分镜.md"))
            应该(code == 0 and "8 刀" in out and "大落点在第 5 刀" in out, "切点.py：16 秒一小节一刀应该 8 刀、大落点第 5 刀：" + out[:200])
            code, out = 跑("reel-board/切点.py", str(t / "拍子.json"), "--秒", "16", "--出", str(t / "分镜.md"))
            应该(code != 0 and "EXISTS" in out, "切点.py：分镜已有时没拦住覆盖")
            code, out = 跑("reel-music/歌词.py", "对时间", str(t / "词.txt"), str(t / "拍子.json"), "--出", str(t / "歌词.json"))
            应该(code == 0 and len(json.loads((t / "歌词.json").read_text(encoding="utf-8"))["行"]) == 2, "歌词.py 对时间：行数不对")
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        import 媒体
        # 现造一条坏片：720×1280、2.0～2.6 秒黑屏、4～5 秒每 0.2 秒闪一次白、声音过响；第 3 秒后整个画面变成红色（模拟变形变色）
        媒体.跑("-f", "lavfi", "-i", "testsrc2=s=720x1280:r=24:d=6", "-f", "lavfi", "-i", "sine=f=440:d=6",
               "-vf", "drawbox=c=red:t=fill:enable='gte(t,3)',drawbox=c=black:t=fill:enable='between(t,2,2.6)',"
               "drawbox=c=white:t=fill:enable='between(t,4,5)*lt(mod(t,0.2),0.1)'",
               "-af", "volume=25dB", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-shortest", t / "坏.mp4")
        code, out = 跑("reel-check/质检.py", "查", str(t / "坏.mp4"), "--平台", "抖音,B站,快手")
        for 词 in ("720×1280", "黑屏", "光敏", "LUFS", "B站 要求采样率 48000", "快手 不在规格表里"):
            应该(词 in out, f"质检.py：没报出「{词}」")
        应该(code == 1, "质检.py：坏片退出码应该是 1")
        应该("2.0" in out.split("黑屏")[0][-12:], "质检.py：黑屏时间不对：" + out)
        code, out = 跑("reel-check/质检.py", "联系表", str(t / "坏.mp4"), str(t / "表.jpg"))
        应该(code == 0 and (t / "表.jpg").exists(), "质检.py 联系表：没出图")
        code, out = 跑("reel-motion/抽帧.py", str(t / "坏.mp4"), "--出", str(t / "视频" / "联系表.jpg"), "--窗口表", str(t / "视频" / "可用窗口.md"))
        应该(code == 0 and (t / "视频" / "联系表.jpg").exists(), "抽帧.py：没出联系表：" + out[-300:])
        应该("和开头差很多" in out, "抽帧.py：后半段变色没提示出来：" + out[-300:])
        sys.path.insert(0, str(S / "reel-board"))
        import 镜头表
        应该(镜头表.读窗口表(t / "视频" / "可用窗口.md").get("1", {}).get("止") == 6.0, "抽帧.py：窗口表骨架读不回来")
    # 成片.py：粗剪 → 关口没点头不出成片 → 成片 → 再出一版是 _v2、旧版还在 → 质检过
    with tempfile.TemporaryDirectory() as t:
        P = Path(t) / "片"
        for d in ("音乐", "视频", "进度"):
            (P / d).mkdir(parents=True)
        合成曲(P / "音乐" / "歌.wav", 小节=6, 鼓从=0, 垫=0.3)
        跑("reel-music/节拍.py", str(P / "音乐" / "歌.wav"), "--out", str(P / "音乐" / "拍子.json"))
        for k, c in enumerate(("red", "blue", "green", "orange"), 1):
            媒体.跑("-f", "lavfi", "-i", f"testsrc2=s=720x1280:r=24:d=3", "-vf", f"drawbox=c={c}@0.4:t=fill",
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", P / "视频" / f"{k:02d}.mp4")
        景 = ("全身", "特写", "中景", "近景")
        (P / "分镜.md").write_text("120 拍／分\n\n| # | 进–出（秒） | 景别 | 镜头动作 | 大字 | 素材 |\n|---|---|---|---|---|---|\n" + "".join(
            f"| {k} | {2 * (k - 1):.3f}–{2 * k:.3f} | {景[k - 1]} | 慢推 | W{k} | 视频/{k:02d}.mp4 |\n" for k in range(1, 5)), encoding="utf-8")
        (P / "视频" / "可用窗口.md").write_text("| 号 | 文件 | 窗口（秒） | 问题 | 处理 |\n|---|---|---|---|---|\n" + "".join(
            f"| {k} | 视频/{k:02d}.mp4 | 0.5–2.9 | | 留 |\n" for k in range(1, 5)), encoding="utf-8")
        code, out = 跑("reel-cut/成片.py", "粗剪", str(P))
        应该(code == 0 and (P / "出片" / "粗剪" / "联系表.jpg").exists(), "成片.py 粗剪：没出预览和联系表：" + out[-400:])
        code, out = 跑("reel-cut/成片.py", "成片", str(P))
        应该(code != 0 and "GATE" in out, "成片.py：粗剪没点头就出了成片")
        跑("reel-brief/进度.py", "关口", str(P), "粗剪", "过")
        code, out = 跑("reel-cut/成片.py", "成片", str(P))
        应该(code == 0 and (P / "出片" / "成片.mp4").exists(), "成片.py：成片没出来：" + out[-400:])
        code, out = 跑("reel-cut/成片.py", "成片", str(P))
        应该((P / "出片" / "成片_v2.mp4").exists() and (P / "出片" / "成片.mp4").exists(), "成片.py：第二版没加 _v2 或者旧版没了")
        code, out = 跑("reel-check/质检.py", "查", str(P / "出片" / "成片.mp4"), "--秒", "8")
        应该(code == 0, "质检.py：自己出的成片没过质检：" + out[-500:])
        (P / "视频" / "可用窗口.md").write_text((P / "视频" / "可用窗口.md").read_text(encoding="utf-8").replace("| 3 | 视频/03.mp4 | 0.5–2.9", "| 3 | 视频/03.mp4 | 0.5–1.5"), encoding="utf-8")
        code, out = 跑("reel-cut/成片.py", "粗剪", str(P))
        应该(code != 0 and "OVER_WINDOW" in out, "成片.py：一刀比可用窗口长没拦住")
        code, out = 跑("reel-cut/调色.py", "导出", "国风", str(Path(t) / "国风.cube"))
        应该(code == 0 and "LUT_3D_SIZE 25" in (Path(t) / "国风.cube").read_text(encoding="utf-8"), "调色.py：导出 .cube 不对")
        try:
            import rembg  # noqa: F401
        except ImportError:
            code, out = 跑("reel-cut/抠像.py", str(P / "视频" / "01.mp4"), str(Path(t) / "遮罩.mp4"))
            应该(code == 3 and "MATTE_DEPS_MISSING" in out, "抠像.py：没装 rembg 时应该说清怎么装、退出码 3")
    # 带货片出片：配音用 ffmpeg 合成的音代替（测试不联网）；排时间、粗剪、成片、质检、抖店详情页规格
    with tempfile.TemporaryDirectory() as t:
        P = Path(t) / "开衫"
        for d in ("静帧", "配音", "音乐", "进度"):
            (P / d).mkdir(parents=True)
        (P / "分镜.md").write_text(带货表, encoding="utf-8")
        for k in range(1, 6):
            媒体.跑("-f", "lavfi", "-i", f"testsrc2=s=1080x1920:d=1", "-frames:v", "1", P / "静帧" / f"{k:02d}.png")
            媒体.跑("-f", "lavfi", "-i", f"sine=frequency={300 + k * 40}:duration={1.0 + k * 0.2}", "-ar", "48000", P / "配音" / f"{k:02d}.wav")
        (P / "配音" / "时长.json").write_text(json.dumps({str(k): {"秒": 1.0 + k * 0.2, "合成": False} for k in range(1, 6)}), encoding="utf-8")
        code, out = 跑("reel-voice/配音.py", "排时间", str(P))
        末 = 镜头表.读镜头表(P / "分镜.md")[-1]
        应该(code == 0 and 末["出"] - 末["进"] >= 3.0 - 0.01, "配音.py 排时间：最后一刀行动号召要至少 3 秒：" + out[-200:])
        (P / "剪辑.json").write_text(json.dumps({"贴纸": "测试店", "价格": "¥99"}, ensure_ascii=False), encoding="utf-8")
        code, out = 跑("reel-cut/成片.py", "粗剪", str(P))
        应该(code == 0, "成片.py 带货粗剪没出来：" + out[-400:])
        跑("reel-brief/进度.py", "关口", str(P), "粗剪", "过")
        code, out = 跑("reel-cut/成片.py", "成片", str(P))
        应该(code == 0 and (P / "出片" / "成片.mp4").exists() and (P / "出片" / "字幕.ass").exists(), "成片.py 带货成片没出来：" + out[-400:])
        ass = (P / "出片" / "字幕.ass").read_text(encoding="utf-8") if (P / "出片" / "字幕.ass").exists() else ""
        应该("\\1c&H0033D7FF&}扎脖子" in ass and "Style: CTA" in ass and "¥99" in ass and "测试店" in ass, "字幕.py：高亮、价格、贴纸、行动号召没写进 ASS")
        应该(ass.count(",Sub,,") >= 5 and ",SubTop,," in ass, "字幕.py：「／」分段的字幕没拆成两条，或备注「字幕上」那刀没挪上去")
        code, out = 跑("reel-check/质检.py", "查", str(P / "出片" / "成片.mp4"))
        应该(code == 0, "质检.py：带货成片没过机器检查：" + out[-500:])
        媒体.跑("-f", "lavfi", "-i", "color=c=gray:s=1080x1920:d=62", "-f", "lavfi", "-i", "sine=duration=62", "-c:v", "libx264",
               "-pix_fmt", "yuv420p", "-shortest", P / "长.mp4")
        code, out = 跑("reel-check/质检.py", "查", str(P / "长.mp4"), "--平台", "抖店详情页")
        应该(code == 1 and "时长上限 60" in out, "质检.py：抖店详情页 62 秒没拦住")
        (P / "剪辑.json").write_text(json.dumps({"贴纸": "测试店", "价格": "¥99", "画幅": "3:4"}, ensure_ascii=False), encoding="utf-8")
        code, out = 跑("reel-cut/成片.py", "成片", str(P))
        code, out = 跑("reel-check/质检.py", "查", str(P / "出片" / "成片_v2.mp4"), "--平台", "抖店详情页")
        应该(code == 0 and "1080×1440" in out, "质检.py：3:4 详情页版不该拿 1080×1920 去套：" + out[-400:])
        code, out = 跑("reel-check/质检.py", "安全区", str(P / "出片" / "成片.mp4"), str(P / "安全区.jpg"))
        应该(code == 0 and (P / "安全区.jpg").exists(), "质检.py 安全区图没出来：" + out[-200:])
        try:
            import PIL  # noqa: F401
            code, out = 跑("reel-cut/卡片.py", "结尾", str(P / "静帧" / "01.png"), "-o", str(P / "卡.png"), "--名", "开衫", "--点", "手工粗针／胡桃木扣", "--价", "¥99")
            应该(code == 0 and (P / "卡.png").exists(), "卡片.py 结尾卡没出来：" + out[-200:])
            code, out = 跑("reel-check/质检.py", "封面AB", str(P / "封面"), "--图", str(P / "静帧" / "02.png"), "--题", "标题一|标题二")
            应该(code == 0 and (P / "封面" / "封面对比.jpg").exists() and (P / "封面" / "封面_B.jpg").exists(), "质检.py 封面AB 没出来：" + out[-200:])
        except ImportError:
            pass
else:
    print("（没有 numpy 或 ffmpeg，音视频脚本的用例跳过）")

print("\n".join("❌ " + x for x in 坏) or "✅ 掠影自测全过")
sys.exit(1 if 坏 else 0)

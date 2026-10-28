"""配音：带货片、口播片逐句配音。免费的 edge-tts（微软在线语音，要联网）；主人自己录的也能放进来。
读：分镜.md 的「台词」列（一刀一句）。写：配音/<号>.wav（去掉首尾静音、48k 单声道）、配音/时长.json。
用法：
  python3 配音.py 装                               找不到 edge-tts 时装上：建单独的 Python 环境 ~/.yunjian/reel/venv 再装（系统 Python 不让装也不碰它）
  python3 配音.py 音色 [zh-CN]                     列出这个语言的全部音色
  python3 配音.py 试听 <项目> [--声音 X] [--语速 +10%] [--句 2]   只合成前几句，存 配音/试听_<号>.wav，先给主人听
  python3 配音.py 合成 <项目> [--声音 X] [--语速 +10%] [--目标 15]  整条合成；主人自己录的（配音/<号>.wav 已有、且不是我们合成的）不覆盖
  python3 配音.py 排时间 <项目> [--留白 0.25] [--最短 1.2]          按真实配音时长改写镜头表的进–出点（只改那一格）
  python3 配音.py 口播 <项目> [--声音 X] [--语速 +10%] [--试听]     不露脸的口播片：照 <项目>/稿子.md 一句一句合成，按句型留停顿拼成
                                                                    口播/粗剪.wav，并写好 口播/清剪.json（不用转文字），接着走 镜头表.py 口播；--试听 只出前 2 句
声音、语速不写就读项目 声音.json（店里固定的声音，reel-voice 第 4 步存的），再没有用 zh-CN-XiaoxiaoNeural、+10%。"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for d in ("reel-brief", "reel-board"):
    sys.path.insert(0, str(HERE.parent / d))
import 媒体  # noqa: E402
import 镜头表  # noqa: E402

家 = Path(os.environ.get("REEL_HOME", Path.home() / ".yunjian" / "reel"))
默认声音, 默认语速 = "zh-CN-XiaoxiaoNeural", "+10%"
音色推荐 = {
    "zh-CN-XiaoxiaoNeural": "女声，亲切种草（默认）", "zh-CN-XiaoyiNeural": "女声，活泼",
    "zh-CN-YunxiNeural": "男声，活力种草", "zh-CN-YunjianNeural": "男声，激情促销", "zh-CN-YunyangNeural": "男声，专业讲解",
}


def 找python():
    """返回装了 edge-tts 的 python；都没有返回 None。"""
    候选 = [sys.executable, str(家 / "venv" / "bin" / "python"), "/workspace/reel/venv/bin/python"]
    for py in 候选:
        if Path(py).exists() and subprocess.run([py, "-c", "import edge_tts"], capture_output=True).returncode == 0:
            return py
    return None


def 要python():
    py = 找python()
    if not py:
        sys.exit("NO_TTS：没装免费配音 edge-tts。先问主人一句，同意后跑 python3 配音.py 装（约 1 分钟，装在 ~/.yunjian/reel/venv，不动系统 Python）；"
                 "不想装就让主人自己录（每刀一句，存成 配音/<号>.wav），或者不配音只放音乐和大字")
    return py


def 装():
    if 找python():
        print("OK 已经装好了")
        return
    venv = 家 / "venv"
    if subprocess.run([sys.executable, "-m", "pip", "install", "--user", "-q", "edge-tts"], capture_output=True).returncode == 0 and 找python():
        print("OK 装好了（装进了当前 Python）")
        return
    venv.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, "-m", "venv", str(venv)], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"VENV_FAILED：建单独的 Python 环境没成功：{r.stderr.strip()[-300:]}")
    r = subprocess.run([str(venv / "bin" / "python"), "-m", "pip", "install", "-q", "edge-tts"], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"PIP_FAILED：{r.stderr.strip()[-300:]}（多半是连不上网；先让主人自己录，或者不配音）")
    print(f"OK 装好了：{venv}")


def 音色(语言):
    py = 要python()
    r = subprocess.run([py, "-m", "edge_tts", "--list-voices"], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"TTS_FAILED：列音色没成功（多半是连不上微软语音）：{r.stderr.strip()[-200:]}")
    for l in r.stdout.splitlines():
        if l.startswith(语言) or l.startswith("Name: " + 语言):
            名 = l.split()[0] if not l.startswith("Name") else l.split()[1]
            print(名, 音色推荐.get(名, ""))


def 声音设置(P, g):
    f = P / "声音.json"
    s = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    return g.声音 or s.get("声音") or 默认声音, g.语速 or s.get("语速") or 默认语速


def 台词们(P):
    out = []
    for s in 镜头表.读镜头表(P / "分镜.md"):
        t = re.sub(r"\*\*", "", s.get("台词", "")).strip()
        if t and t not in ("—", "-", "无"):
            out.append((s["号"], t))
    if not out:
        sys.exit("NO_LINES：分镜.md 的镜头表里没有「台词」列，或者全是空的。带货片先照 reel-board 写台词")
    return out


def 合成一句(py, text, 声音, 语速, out):
    """edge-tts 出 mp3 → ffmpeg 去首尾静音、转 48k 单声道 wav。最多试 3 次（网络偶尔断）。"""
    tmp = out.with_suffix(".mp3")
    for _ in range(3):
        r = subprocess.run([py, "-m", "edge_tts", "--voice", 声音, f"--rate={语速}", "--text", text, "--write-media", str(tmp)],
                           capture_output=True, text=True)
        if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 1000:
            break
    else:
        sys.exit(f"TTS_FAILED：「{text}」没合成出来（多半是连不上微软语音）：{r.stderr.strip()[-200:]}")
    去静音 = "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse"
    媒体.跑("-i", tmp, "-af", 去静音, "-ar", "48000", "-ac", "1", out)
    tmp.unlink()
    return round(媒体.信息(out)["时长"], 3)


def 合成(P, g, 只试=0):
    py = 要python()
    声音, 语速 = 声音设置(P, g)
    d = P / "配音"
    d.mkdir(exist_ok=True)
    记 = d / "时长.json"
    旧 = json.loads(记.read_text(encoding="utf-8")) if 记.exists() else {}
    时长 = {}
    句们 = 台词们(P)[:只试] if 只试 else 台词们(P)
    for 号, t in 句们:
        out = d / (f"试听_{int(号):02d}.wav" if 只试 else f"{int(号):02d}.wav")
        if not 只试 and out.exists() and not 旧.get(号, {}).get("合成"):
            时长[号] = {"秒": round(媒体.信息(out)["时长"], 3), "合成": False, "台词": t}  # 主人自己录的
            continue
        时长[号] = {"秒": 合成一句(py, t, 声音, 语速, out), "合成": True, "台词": t}
        print(f"第 {号} 刀  {时长[号]['秒']:.2f} 秒  {len(t)} 字  {t}")
    if 只试:
        print(f"OK 试听 {len(句们)} 句在 {d}（试听_*.wav），声音 {声音}、语速 {语速}。给主人听，定了再整条合成")
        return
    记.write_text(json.dumps({"声音": 声音, "语速": 语速, **时长}, ensure_ascii=False, indent=1), encoding="utf-8")
    总 = sum(v["秒"] for v in 时长.values())
    print(f"OK {len(时长)} 句，配音共 {总:.2f} 秒（声音 {声音}、语速 {语速}）→ {记}")
    if g.目标:
        估 = 总 + len(时长) * 0.4
        if 估 > g.目标 + 0.5:
            print(f"⚠️ 加上每句留白约 {估:.1f} 秒，超过目标 {g.目标} 秒：删台词（不要把语速加到 +20% 以上）")
        else:
            print(f"加上每句留白约 {估:.1f} 秒，目标 {g.目标} 秒以内")
    print(f"下一步：python3 {HERE / '配音.py'} 排时间 {P}")


def 排时间(P, 留白, 最短):
    记 = P / "配音" / "时长.json"
    if not 记.exists():
        sys.exit("NO_VOICE：还没配音。先跑 配音.py 合成")
    时长 = json.loads(记.read_text(encoding="utf-8"))
    表 = 镜头表.读镜头表(P / "分镜.md")
    新, t = {}, 0.0
    for i, s in enumerate(表):
        原长 = s["出"] - s["进"]
        v = 时长.get(s["号"])
        长 = max(最短, v["秒"] + 0.15 + 留白) if isinstance(v, dict) else 原长  # 0.15 秒前导：配音在这一刀开头 0.15 秒才出声
        if i == len(表) - 1:
            长 = max(长, 3.0)  # 最后一刀是行动号召，至少留 3 秒给人点
        新[s["号"]] = (round(t, 2), round(t + 长, 2))
        t += 长
    n = 镜头表.改时间(P / "分镜.md", 新)
    print(f"OK 改了 {n} 刀的进–出点，全片 {t:.2f} 秒（每句配音＋0.15 秒前导＋{留白} 秒留白，最短 {最短} 秒；最后一刀至少 3 秒）")
    for 号, (a, b) in 新.items():
        print(f"  第 {号} 刀 {a:.2f}–{b:.2f}")


def 口播(P, g):
    """不露脸口播：稿子逐句合成 → 按句型停顿拼起来 → 口播/粗剪.wav ＋ 清剪.json（和清剪.py 出的同一个样子）。"""
    sys.path.insert(0, str(HERE.parent / "reel-cut"))
    import 对时间
    import 清剪
    import numpy as np
    稿 = P / "稿子.md"
    if not 稿.exists():
        sys.exit(f"NO_SCRIPT：先把口播稿原样存成 {稿}")
    句们 = [s for s in 对时间.读稿(稿) if not s.get("夹带")]
    py = 要python()
    声音, 语速 = 声音设置(P, g)
    d = P / "口播" / "配音"
    d.mkdir(parents=True, exist_ok=True)
    if g.试听:
        for s in 句们[:2]:
            合成一句(py, s["字幕"], 声音, 语速, d / f"试听_{s['号']:02d}.wav")
        print(f"OK 试听 2 句在 {d}（试听_*.wav），声音 {声音}、语速 {语速}。给主人听，定了再整条合成")
        return
    SR, 段, 句时, t = 48000, [], [], 0.12
    段.append(np.zeros(int(0.12 * SR), np.float32))
    for i, s in enumerate(句们):
        f = d / f"{s['号']:02d}.wav"
        合成一句(py, s["字幕"], 声音, 语速, f)
        y = 媒体.解码音频(f, sr=SR)
        句时.append({**{k: s[k] for k in ("号", "原文", "字幕", "句尾", "段", "提示")}, "多出来的": False,
                    "起": round(t, 3), "止": round(t + len(y) / SR, 3)})
        停 = 0.4 if i == len(句们) - 1 else 清剪.停顿表.get(s["句尾"], 0.22)
        段 += [y, np.zeros(int(停 * SR), np.float32)]
        t += len(y) / SR + 停
    out = P / "口播" / "粗剪.wav"
    媒体.写音频(out, np.concatenate(段), SR)
    长 = round(媒体.信息(out)["时长"], 3)
    (P / "口播" / "清剪.json").write_text(json.dumps({"录音": "AI 配音", "粗剪": str(out), "有画面": False, "原长": 长, "新长": 长,
                                                   "段": [{"原起": 0, "原止": 长, "新起": 0, "新止": 长, "段": 1, "推近": 1.0}],
                                                   "句": 句时, "声音": 声音, "语速": 语速}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK {len(句们)} 句、{长:.1f} 秒（{声音}、{语速}）→ {out}")
    print(f"下一步：python3 {HERE.parent / 'reel-board' / '镜头表.py'} 口播 {P}，每句配画面（主人照片 → 丹青母版静帧 → 卡片）")


def main():
    ap = argparse.ArgumentParser(description="配音")
    ap.add_argument("做", choices=["装", "音色", "试听", "合成", "排时间", "口播"])
    ap.add_argument("--试听", action="store_true")
    ap.add_argument("项目", nargs="?")
    ap.add_argument("--声音")
    ap.add_argument("--语速")
    ap.add_argument("--句", type=int, default=2)
    ap.add_argument("--目标", type=float)
    ap.add_argument("--留白", type=float, default=0.25)
    ap.add_argument("--最短", type=float, default=1.2)
    g = ap.parse_args()
    if g.做 == "装":
        return 装()
    if g.做 == "音色":
        return 音色(g.项目 or "zh-CN")
    if not g.项目:
        sys.exit("要给项目文件夹")
    P = Path(g.项目).resolve()
    if g.做 == "口播":
        口播(P, g)
    elif g.做 == "试听":
        合成(P, g, 只试=g.句)
    elif g.做 == "合成":
        合成(P, g)
    else:
        排时间(P, g.留白, g.最短)


if __name__ == "__main__":
    main()

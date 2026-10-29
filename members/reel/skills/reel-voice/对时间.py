"""口播片对时间：主人录的口播转出每个字的时间，和执笔稿逐句对上；漏念、念了几遍、半截重来、改了说法、多出来的话都列出来给主人定。
转文字只用来找时间，字幕永远照稿子（主人改了说法的，照他真说的、并告诉他）。
用法：
  python3 对时间.py 装                                  装转文字工具 faster-whisper（装在 ~/.yunjian/reel/venv，不动系统 Python；第一次转时再下 small 模型约 464MB）
  python3 对时间.py 转 <项目> [--录音 文件]             录音／录像 → 口播/转写.json（逐词时间）。不给 --录音 就找 <项目>/录音/ 里唯一的音视频
  python3 对时间.py 对 <项目> [--稿 文件]               转写＋稿子 → 口播/对时间.json、口播/对时间.md。不给 --稿 就用 <项目>/稿子.md
  python3 对时间.py 读稿 <稿子.md>                      只看稿子分成了哪几句（检查用）
  python3 对时间.py 出稿 <项目>                         主人没有稿子：用转出来的字按标点分句，写 <项目>/稿子.md（开头注明「转文字出的，请主人核」）
稿子：执笔口播稿格式（色块段头、〔…〕提示、==重点==、**花字**），一行一句；别的格式按非空行算句，不改字。
退出码：0 都对上了；1 有要主人定的（漏念、改了说法、多出来的话）；2 用法或文件不对。"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "reel-brief"))
import 媒体  # noqa: E402

家 = Path(os.environ.get("REEL_HOME", Path.home() / ".yunjian" / "reel"))
标点 = "，。？！、；：,.?!;:…—"
口头禅 = set("呃嗯啊额哦唉诶哎")
段头 = re.compile(r"^\s*(🟥|🟧|🟨|🟩|🟦|🟪|🟫|⬛|⬜|[①-⑳])")


# ---------- 读稿 ----------
def 读稿(path):
    """→ [{号, 段, 原文(带==/**), 字幕(去掉标记), 句尾, 提示(这段段头〔…〕里的画面提示)}]"""
    句们, 段, 提示 = [], 0, ""
    for l in Path(path).read_text(encoding="utf-8").splitlines():
        s = l.strip()
        if 句们 and re.fullmatch(r"-{3,}|={3,}|\*{3,}", s):
            break  # 执笔稿正文写完用 --- 隔开，下面是出处表、自查记录，不是台词
        if not s or s.startswith(("标题", ">", "---", "#")) or re.match(r"^约\s*\d+", s):
            continue
        if 段头.match(s):
            段 += 1
            m = re.search(r"〔([^〕]*)〕", s)
            提示 = m[1].strip() if m else ""
            continue
        s = re.sub(r"〔[^〕]*〕", "", s).strip()
        if not s or re.fullmatch(r"[（(].*[)）]", s) and "AI" in s:  # 括号里整行写给 AI 的话：不是台词（防夹带，交给主人看）
            if s:
                句们.append({"号": None, "段": 段, "原文": s, "字幕": "", "句尾": "", "夹带": True})
            continue
        字幕 = re.sub(r"==|\*\*", "", s)
        句们.append({"号": sum(not x.get("夹带") for x in 句们) + 1, "段": max(段, 1), "原文": s, "字幕": 字幕, "句尾": 字幕[-1] if 字幕[-1] in 标点 else "",
                    "提示": 提示})
    return 句们


# ---------- 拼音 ----------
数字 = "零一二三四五六七八九"


def 数转汉字(m):
    s = m.group(0)
    if "." in s:
        a, b = s.split(".", 1)
        return 整数(a) + "点" + "".join(数字[int(c)] for c in b)
    return 整数(s)


def 整数(s):
    n = int(s)
    if n < 10:
        return 数字[n]
    if n >= 10000:
        return "".join(数字[int(c)] for c in s)
    out, 位 = "", ["", "十", "百", "千"]
    ds = str(n)
    for i, c in enumerate(ds):
        k = len(ds) - 1 - i
        if c == "0":
            if out and not out.endswith("零") and any(x != "0" for x in ds[i:]):
                out += "零"
        else:
            out += 数字[int(c)] + 位[k]
    return out[1:] if out.startswith("一十") else out


def 字串(text):
    """台词 → 只留汉字、英文字母（数字读成汉字）的列表；英文一个字母一项，「Grok Bot」和「GrokBot」比起来一样。"""
    t = re.sub(r"\d+(\.\d+)?", 数转汉字, text)
    return re.findall(r"[一-鿿]|[A-Za-z]", t)


def 音(字们):
    """一个字（或一个英文词）对一个音节，长度和输入一样——英文词整词小写，不拆成字母（10-28 稿子里有「Grok Bot」时对不齐、下标越界）。"""
    from pypinyin import Style, lazy_pinyin
    return [lazy_pinyin(c, style=Style.NORMAL)[0].lower() if re.match(r"[一-鿿]", c) else c.lower() for c in 字们]


def 像(a, b):
    """两个音节的分：一样 2；平翘舌、前后鼻音、n/l 混 1；不一样 -1。"""
    if a == b:
        return 2
    return 1 if _糊(a) == _糊(b) else -1


def _糊(p):
    return re.sub(r"^l", "n", re.sub(r"ng$", "n", re.sub(r"^([zcs])h", r"\1", p)))


# ---------- 转 ----------
def 找python():
    for py in (sys.executable, str(家 / "venv" / "bin" / "python"), "/workspace/reel/venv/bin/python"):
        if Path(py).exists() and subprocess.run([py, "-c", "import faster_whisper"], capture_output=True).returncode == 0:
            return py
    return None


def 装():
    if 找python():
        print("OK 已经装好了")
        return 0
    if subprocess.run([sys.executable, "-m", "pip", "install", "--user", "-q", "faster-whisper"], capture_output=True).returncode == 0 and 找python():
        print("OK 装好了（装进了当前 Python）")
        return 0
    venv = 家 / "venv"
    if not (venv / "bin" / "python").exists():
        venv.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([sys.executable, "-m", "venv", str(venv)], capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"VENV_FAILED：建单独的 Python 环境没成功：{r.stderr.strip()[-300:]}")
    r = subprocess.run([str(venv / "bin" / "python"), "-m", "pip", "install", "-q", "faster-whisper"], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"PIP_FAILED：{r.stderr.strip()[-300:]}（多半是连不上网；退路：只按声音找空白去停顿，念错重说请主人在粗剪里勾）")
    print(f"OK 装好了：{venv}")
    return 0


# 在装了 faster-whisper 的 Python 里跑：读 16k float32 原始数据（ffmpeg 先解好，不让 faster-whisper 自己读文件——新版 av 会报错）
转写程序 = r"""
import json, sys, numpy as np
from faster_whisper import WhisperModel
raw, out, 模型名, 模型目录 = sys.argv[1:5]
m = WhisperModel(模型名, device="cpu", compute_type="int8", download_root=模型目录 or None)
segs, info = m.transcribe(np.fromfile(raw, dtype=np.float32), language="zh", word_timestamps=True, vad_filter=False,
                          condition_on_previous_text=False)
词 = [[w.word, round(w.start, 3), round(w.end, 3)] for s in segs for w in (s.words or [])]
json.dump({"模型": 模型名, "时长": info.duration, "词": 词}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
"""


def 找录音(P):
    d = P / "录音"
    fs = [f for f in sorted(d.glob("*")) if f.suffix.lower() in (".wav", ".mp3", ".m4a", ".aac", ".mp4", ".mov", ".m4v", ".webm")] if d.exists() else []
    if len(fs) != 1:
        sys.exit(f"NO_RECORDING：{d} 里要正好一个录音或录像（现在 {len(fs)} 个）；或者用 --录音 指定")
    return fs[0]


def 转(P, 录音, 模型):
    py = 找python()
    if not py:
        sys.exit("NO_ASR：没装转文字工具 faster-whisper。先问主人一句，同意后跑 python3 对时间.py 装（约 1 分钟；第一次转再下 464MB 模型）；"
                 "不想装：只按声音找空白去停顿（清剪.py --只按声音），念错重说请主人在粗剪里勾")
    录音 = Path(录音) if 录音 else 找录音(P)
    d = P / "口播"
    d.mkdir(parents=True, exist_ok=True)
    raw = d / "_16k.f32"
    raw.write_bytes(媒体.解码音频(录音, sr=16000).tobytes())
    out = d / "转写.json"
    环境 = {**os.environ, "HF_HUB_DISABLE_XET": "1"}  # 新的 xet 下载方式在国内常常卡住不动，走普通下载
    r = subprocess.run([py, "-c", 转写程序, str(raw), str(out), 模型, str(家 / "模型")], capture_output=True, text=True, env=环境)
    raw.unlink()
    if r.returncode:
        sys.exit("ASR_FAILED：" + "\n".join(r.stderr.strip().splitlines()[-4:]) + "（第一次要从 Hugging Face 下模型 464MB，多半是连不上；可以在能上的电脑上下好 Systran/faster-whisper-small，放进 ~/.yunjian/reel/模型）")
    j = json.loads(out.read_text(encoding="utf-8"))
    j["录音"] = str(录音)
    out.write_text(json.dumps(j, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"OK 转好了：{len(j['词'])} 个词、{j['时长']:.1f} 秒 → {out}")
    print(f"下一步：python3 {HERE / '对时间.py'} 对 {P}")
    return 0


# ---------- 对 ----------
def 逐字(词们):
    """[[词, 起, 止]] → [(字, 起, 止)]：一个词几个字就平分它的时间；标点去掉。
    几乎没有时长的词（不到 0.03 秒）是转文字在静音处编出来的（常见「字幕 by …」「请不吝点赞」），丢掉。"""
    out = []
    for w, a, b in 词们:
        if b - a < 0.03:
            continue
        cs = 字串(w)
        for k, c in enumerate(cs):
            out.append((c, a + (b - a) * k / len(cs), a + (b - a) * (k + 1) / len(cs)))
    return out


def 局部对齐(句音, 听音, 起=0, 止=None):
    """Smith-Waterman：句子音节在 听音[起:止] 里最像的一段 → (分, 听里从, 听里到, 句里从, 句里到)。"""
    止 = len(听音) if 止 is None else 止
    m, best = len(句音), (0, 0, 0, 0, 0)
    prev = [(0, 0, 0)] * (m + 1)  # (分, 听里起点, 句里起点)
    for j in range(起, 止):
        cur = [(0, j, 0)]
        for i in range(1, m + 1):
            s = 像(句音[i - 1], 听音[j])
            d = prev[i - 1]
            候 = [(d[0] + s, d[1] if d[0] > 0 else j, d[2] if d[0] > 0 else i - 1),
                 (prev[i][0] - 1, prev[i][1], prev[i][2]), (cur[i - 1][0] - 1, cur[i - 1][1], cur[i - 1][2]), (0, j + 1, i)]
            c = max(候, key=lambda x: x[0])
            cur.append(c)
            if c[0] > best[0]:
                best = (c[0], c[1], j + 1, c[2], i)
        prev = cur
    return best


def 找遍(句音, 听音, 用过):
    """一句在整条录音里所有像的地方（不重叠、没被别的句占）→ [(分, 从, 到, 句里从, 句里到)]。"""
    满分, out = 2 * len(句音), []
    lo = 0
    while True:
        段 = [(a, b) for a, b in _空段(用过, len(听音)) if b > lo]
        best = max((局部对齐(句音, 听音, max(a, lo), b) for a, b in 段), default=(0,) * 5, key=lambda x: x[0])
        if best[0] < max(4, 0.5 * 满分):
            return out
        out.append(best)
        用过 = 用过 | set(range(best[1], best[2]))


def _空段(用过, n):
    out, a = [], None
    for k in range(n + 1):
        if k < n and k not in 用过:
            a = k if a is None else a
        elif a is not None:
            out.append((a, k))
            a = None
    return out


def 对(P, 稿):
    稿 = Path(稿) if 稿 else P / "稿子.md"
    转写 = P / "口播" / "转写.json"
    if not 稿.exists():
        sys.exit(f"NO_SCRIPT：没找到稿子 {稿}。没有稿子：先问主人要；实在没有，字幕先用转出来的字，交之前请主人核一遍")
    if not 转写.exists():
        sys.exit(f"NO_TRANSCRIPT：还没转文字。先跑 python3 {HERE / '对时间.py'} 转 {P}")
    句们 = 读稿(稿)
    台词 = [s for s in 句们 if not s.get("夹带")]
    听 = 逐字(json.loads(转写.read_text(encoding="utf-8"))["词"])
    听音 = 音([c for c, _, _ in 听])
    时 = lambda a, b: (round(听[a][1], 3), round(听[b - 1][2], 3))  # noqa: E731

    # 1. 每句找所有像的地方，按分从高到低占位（长句先占，免得短句抢走）
    候 = {}
    用过 = set()
    for s in sorted(台词, key=lambda s: -len(字串(s["字幕"]))):
        句音 = 音(字串(s["字幕"]))
        s["音"] = 句音
        候[s["号"]] = 找遍(句音, 听音, 用过)
        for h in 候[s["号"]]:
            用过 |= set(range(h[1], h[2]))
    # 2. 定每句留哪一遍：按稿子顺序、时间往后走；同一句几遍里留最后一遍完整的，前面的列为删
    上 = 0
    for k, s in enumerate(台词):
        遍 = sorted((h for h in 候[s["号"]] if h[1] >= 上), key=lambda h: h[1])
        下句起 = min((h[1] for t in 台词[k + 1:] for h in 候[t["号"]] if h[1] >= 上), default=len(听))
        遍 = [h for h in 遍 if h[1] < 下句起] or 遍[:1]
        if not 遍:
            s.update(状态="漏念", 起=None, 止=None)
            continue
        完整 = [h for h in 遍 if h[4] - h[3] >= 0.8 * len(s["音"])]
        留 = (完整 or 遍)[-1]
        a, b = 留[1], 留[2]  # 紧挨着（隔不到 0.15 秒）、没被别的句占的字算这一遍的（主人临场加了几个字、换了说法）
        while a > 0 and a - 1 not in 用过 and 听[a][1] - 听[a - 1][2] < 0.15:
            a -= 1
        while b < len(听) and b not in 用过 and 听[b][1] - 听[b - 1][2] < 0.15:
            b += 1
        用过 |= set(range(a, b))
        原 = 留
        留 = (留[0], a, b, 留[3], 留[4])
        s["起"], s["止"] = 时(a, b)
        s["相似"] = round(difflib.SequenceMatcher(None, [_糊(x) for x in s["音"]], [_糊(x) for x in 听音[a:b]], autojunk=False).ratio(), 2)
        s["听到"] = "".join(c for c, _, _ in 听[a:b])
        s["删掉的遍"] = [{"起": 时(h[1], h[2])[0], "止": 时(h[1], h[2])[1], "听到": "".join(c for c, _, _ in 听[h[1]:h[2]]),
                       "为什么": "前面念过一遍，留最后一遍" if h[4] - h[3] >= 0.8 * len(s["音"]) else "半截就停了，后面重说了"}
                      for h in 遍 if h is not 原]
        s["状态"] = "改了说法？" if s["相似"] < 0.85 else ("念了几遍" if s["删掉的遍"] else "对上")
        上 = 留[2]
    # 3. 半截重来常常只说了两三个字，第 1 步门槛够不着：在每句留的那遍前面的空当里再找它的开头
    占 = set()
    for s in 台词:
        if s.get("起") is not None:
            for x in [s] + s["删掉的遍"]:
                占 |= {i for i, (_, a, b) in enumerate(听) if a >= x["起"] - 1e-3 and b <= x["止"] + 1e-3}
    for s in 台词:
        if s.get("起") is None:
            continue
        前 = [i for i in range(len(听)) if i not in 占 and 听[i][2] <= s["起"] + 1e-3 and 听[i][1] >= s["起"] - 6]
        if len(前) >= 2:
            头 = s["音"][:max(2, len(前))]
            h = 局部对齐(头, 听音, 前[0], 前[-1] + 1)
            if h[0] >= 4 and h[3] == 0 and h[2] - h[1] >= 2:
                s["删掉的遍"].insert(0, {"起": 时(h[1], h[2])[0], "止": 时(h[1], h[2])[1], "听到": "".join(c for c, _, _ in 听[h[1]:h[2]]),
                                       "为什么": "半截就停了，后面重说了"})
                占 |= set(range(h[1], h[2]))
                if s["状态"] == "对上":
                    s["状态"] = "念了几遍"
    # 4. 谁也没对上的话：口头禅不算，连着 2 个字以上列出来
    多 = []
    for a, b in _空段(占, len(听)):
        cs = [i for i in range(a, b) if 听[i][0] not in 口头禅]
        if len(cs) >= 2:
            多.append({"起": round(听[cs[0]][1], 3), "止": round(听[cs[-1]][2], 3), "听到": "".join(听[i][0] for i in cs)})
    结果 = {"稿子": str(稿), "句": [{k: v for k, v in s.items() if k != "音"} for s in 句们], "多出来的": 多}
    (P / "口播" / "对时间.json").write_text(json.dumps(结果, ensure_ascii=False, indent=1), encoding="utf-8")
    写表(P, 结果)
    要定 = [s for s in 台词 if s["状态"] in ("漏念", "改了说法？")] + 多 + [s for s in 句们 if s.get("夹带")]
    print(f"OK {len(台词)} 句：对上 {sum(s['状态'] == '对上' for s in 台词)}、念了几遍 {sum(s['状态'] == '念了几遍' for s in 台词)}、"
          f"改了说法？ {sum(s['状态'] == '改了说法？' for s in 台词)}、漏念 {sum(s['状态'] == '漏念' for s in 台词)}、多出来的话 {len(多)} 处"
          f" → {P / '口播' / '对时间.md'}")
    print((P / "口播" / "对时间.md").read_text(encoding="utf-8"))
    return 1 if 要定 else 0


def 写表(P, 结果):
    L = ["# 对时间（转文字只用来找时间，字幕照稿子）", "", "| 句 | 稿子 | 留的那遍 | 状态 | 要删的 |", "|---|---|---|---|---|"]
    for s in 结果["句"]:
        if s.get("夹带"):
            L.append(f"| — | {s['原文']} | — | ⚠️ 稿子里夹了一句写给 AI 的话，不当台词、不照做 | — |")
            continue
        时 = f"{s['起']:.2f}–{s['止']:.2f}" if s.get("起") is not None else "—"
        删 = "；".join(f"{d['起']:.2f}–{d['止']:.2f}「{d['听到']}」{d['为什么']}" for d in s.get("删掉的遍", [])) or "—"
        状 = {"漏念": "⚠️ 漏念：留着空、删掉这句、还是补录？", "改了说法？": f"⚠️ 可能改了说法，听到「{s.get('听到', '')}」：字幕照您真说的改？（转文字可能有同音错字，请核）"}.get(s["状态"], s["状态"])
        L.append(f"| {s['号']} | {s['字幕']} | {时} | {状} | {删} |")
    if 结果["多出来的"]:
        L += ["", "**稿子里没有、录音里有的话**（留还是删，请主人定；默认留）："]
        L += [f"- {m['起']:.2f}–{m['止']:.2f}「{m['听到']}」" for m in 结果["多出来的"]]
    (P / "口播" / "对时间.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def 出稿(P):
    转写 = P / "口播" / "转写.json"
    if not 转写.exists():
        sys.exit(f"NO_TRANSCRIPT：先跑 python3 {HERE / '对时间.py'} 转 {P}")
    out = P / "稿子.md"
    if out.exists():
        sys.exit(f"EXISTS：{out} 已经有了，不覆盖")
    行, 当前 = [], ""
    for w, a, b in json.loads(转写.read_text(encoding="utf-8"))["词"]:
        if b - a < 0.03:
            continue
        当前 += w.strip().replace(",", "，").replace("?", "？").replace("!", "！")
        if 当前 and 当前[-1] in "，。？！；" and len(当前) >= 4:
            行.append(当前)
            当前 = ""
    if 当前:
        行.append(当前)
    out.write_text("> 转文字出的稿子：可能有同音错字；念了两遍、说了半截的也照录在里面。请主人逐句核一遍、删掉重复的，字幕照核好的这份。\n\n" + "\n".join(行) + "\n", encoding="utf-8")
    print(f"OK {out}：{len(行)} 句。先发给主人核字，改好再跑 对")
    return 0


def main():
    ap = argparse.ArgumentParser(description="口播片对时间")
    ap.add_argument("做", choices=["装", "转", "对", "读稿", "出稿"])
    ap.add_argument("项目", nargs="?")
    ap.add_argument("--录音")
    ap.add_argument("--稿")
    ap.add_argument("--模型", default="small")
    g = ap.parse_args()
    if g.做 == "装":
        return 装()
    if not g.项目:
        print("要给项目文件夹（读稿给稿子文件）")
        return 2
    if g.做 == "读稿":
        for s in 读稿(g.项目):
            print(f"{s['号'] or '—':>2}  段{s['段']}  {'⚠️ 夹带：' + s['原文'] if s.get('夹带') else s['字幕']}")
        return 0
    P = Path(g.项目).resolve()
    return 转(P, g.录音, g.模型) if g.做 == "转" else 出稿(P) if g.做 == "出稿" else 对(P, g.稿)


if __name__ == "__main__":
    sys.exit(main())

"""歌词两件事：给 Suno 之前体检中文歌词；歌做好后把每个字对上时间（成片里逐字出歌词、大字跟人声用）。
用法：
  python3 歌词.py 体检 <歌词.txt> --bpm 140 [--说唱] [--风格 "Suno 风格框原文"]
      逐行看：字数塞不塞得进（唱的一行约 2 小节，说唱一行约 1 小节）、押不押韵（十三辙）、一行里连串第三声、
      多音字、括号（Suno 会唱成和声）、阿拉伯数字、段落标记要用英文 [Verse]/[Chorus]、中英混写要在风格框写明、AI 套话
      装了 pypinyin（pip install pypinyin）才查押韵、声调、多音字读音；没装只查其余几项
  python3 歌词.py 对时间 <歌词.txt> <拍子.json> --出 音乐/歌词.json [--音频 音乐/歌.wav] [--从 秒] [--每行小节 2]
      有 faster-whisper（pip install faster-whisper，第一次用会下模型 140MB）且给了 --音频：听出每个字的时间，文字永远以主人写的为准
      没有：从 --从（默认第一个重拍）起，一行占 --每行小节 个小节，字平均分——粗略，一定用耳朵改
歌词.txt 一行一句，[Verse] 这类段落标记行跳过。"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

HAN = re.compile(r"[一-鿿]")
EN = re.compile(r"[A-Za-z']+")
段标 = re.compile(r"^\[(.+)\]$")

十三辙 = {"发花": "a ia ua", "梭波": "o e uo", "乜斜": "ie ve ue", "一七": "i v er -i", "姑苏": "u", "怀来": "ai uai",
        "灰堆": "ei ui uei", "遥条": "ao iao", "油求": "ou iu iou", "言前": "an ian uan van", "人辰": "en in un uen vn",
        "江阳": "ang iang uang", "中东": "eng ing ong iong ueng"}
韵到辙 = {f: z for z, fs in 十三辙.items() for f in fs.split()}
多音 = set("行长重乐还得地了着为和发只说觉调传少种数相朝倒背空处当好便要看干难应曲薄差教转弹藏露散")
套话 = ["星辰大海", "追逐梦想", "心中的光", "未来可期", "不负韶华", "破茧成蝶", "逆风飞翔", "灵魂深处", "岁月静好",
      "燃烧青春", "勇往直前", "永不放弃", "梦想的翅膀", "照亮前方", "黑夜里的光", "无尽的远方", "世界的尽头",
      "回忆的碎片", "心跳的声音", "奔向远方", "光芒万丈", "热血沸腾", "命运的齿轮", "海阔天空", "不忘初心",
      "心之所向", "一路向前", "璀璨", "绽放", "涅槃", "闪耀"]


def 读歌词(path):
    return [l.strip() for l in Path(path).read_text(encoding="utf-8").splitlines()]


def 音节(line):
    en = sum(max(1, len(re.findall(r"[aeiouy]+", w.lower().rstrip("e")))) for w in EN.findall(line))
    return len(HAN.findall(line)) + en


def 体检(g):
    try:
        from pypinyin import Style, lazy_pinyin, pinyin
    except ImportError:
        pinyin = None
    说唱 = g.说唱 or any(w in g.风格.lower() for w in ("rap", "trap", "hip hop", "hip-hop", "drill", "说唱"))
    小节 = 1 if 说唱 and g.bpm >= 110 else 2
    拍数 = 4 * 小节
    下, 上 = (1.25, 3.5) if 说唱 else (0.75, 1.5)
    问题, 上一辙 = [], None
    风 = g.风格.lower()
    print(f"{'说唱' if 说唱 else '唱'}，{g.bpm:g} 拍／分，一行约 {小节} 小节 = {拍数} 拍 ≈ {拍数 * 60 / g.bpm:.2f} 秒；"
          f"合适字数 {int(下 * 拍数)}～{int(上 * 拍数)}")
    for n, line in enumerate(读歌词(g.歌词), 1):
        if not line:
            continue
        m = 段标.match(line)
        if m:
            上一辙 = None
            if HAN.search(m[1]):
                问题.append(f"第{n}行 段落标记用英文：[{m[1]}] → [Verse]／[Chorus]／[Bridge]")
            continue
        字 = 音节(line)
        每拍 = 字 / 拍数
        合适 = "✅" if 下 <= 每拍 <= 上 else f"⚠ 太挤，删字或拆两行（上限约 {int(上 * 拍数)}）" if 每拍 > 上 else \
            f"⚠ 太空，Suno 会拖长音或自己加词（下限约 {int(下 * 拍数)}）"
        if re.search(r"[（(].*?[)）]", line):
            问题.append(f"第{n}行 有括号：Suno 会把括号里的唱成和声，不想要就去掉")
        if re.search(r"\d", line):
            问题.append(f"第{n}行 有阿拉伯数字：写成汉字（10 → 十），不然读法不定")
        if EN.search(line) and HAN.search(line) and "english" not in 风:
            问题.append(f"第{n}行 中英混写：风格框加 `english and mandarin`")
        问题 += [f"第{n}行 套话「{c}」：换成具体的人、东西、动作" for c in 套话 if c in line]
        尾 = ""
        hz = "".join(HAN.findall(line))
        if pinyin and hz:
            调 = "".join(p[-1] for p in lazy_pinyin(hz, style=Style.TONE3, neutral_tone_with_five=True))
            连 = max((len(x) for x in re.findall(r"3{3,}", 调)), default=0)
            if 连:
                问题.append(f"第{n}行 连着 {连} 个第三声，唱快了容易糊，换一两个字")
            韵 = pinyin(hz[-1], style=Style.FINALS, strict=False)[0][0] or "-i"
            if 韵 == "i" and re.match(r"(zh|ch|sh|r|z|c|s)", lazy_pinyin(hz[-1])[0]):
                韵 = "-i"
            辙 = 韵到辙.get(韵, 韵)
            尾 = f" 辙：{辙}" + (f"（和上一行{上一辙}不押）" if 上一辙 and 辙 != 上一辙 else "")
            上一辙 = 辙
            for c in hz:
                读音 = list(dict.fromkeys(pinyin(c, heteronym=True)[0]))
                if c in 多音 and len(读音) > 1:
                    问题.append(f"第{n}行 多音字「{c}」（{'／'.join(读音)}）：生成后听这个字，读错就换个不歧义的字")
        print(f"{n:>3} {字:>2}字 {每拍:.2f}/拍 {合适}{尾} | {line}")
    if 读歌词(g.歌词) and HAN.search("".join(读歌词(g.歌词))) and g.风格 and not any(
            k in 风 for k in ("mandarin", "chinese", "c-pop", "中文", "国语", "华语")):
        问题.append("风格框没写语言：中文歌加 `mandarin`")
    if not pinyin:
        print("（没装 pypinyin，押韵、声调、多音字没查：pip install pypinyin）")
    print("\n问题：" + ("无" if not 问题 else "\n- " + "\n- ".join(dict.fromkeys(问题))))
    return 1 if 问题 else 0


def 对时间(g):
    拍子 = json.loads(Path(g.拍子).read_text(encoding="utf-8"))
    行们 = [l for l in 读歌词(g.歌词) if l and not 段标.match(l)]
    切 = lambda s: re.findall(r"[A-Za-z0-9']+|[一-鿿]", s)  # noqa: E731
    字们 = [(w, i) for i, l in enumerate(行们) for w in 切(l)]
    时间, 方法 = None, ""
    if g.音频:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            print("没装 faster-whisper，改用平均分（粗略，要用耳朵改）；想更准：pip install faster-whisper")
        else:
            import numpy as np
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reel-brief"))
            import 媒体
            模型 = WhisperModel(g.模型, device="cpu", compute_type="int8")
            段们, _ = 模型.transcribe(媒体.解码音频(g.音频, 16000).astype(np.float32), word_timestamps=True,
                                   initial_prompt=" ".join(行们)[:400])  # 主人的歌词当提示，命中率高些
            听到 = [(t, w.start, w.end) for s in 段们 for w in (s.words or []) for t in 切(w.word)]
            sm = difflib.SequenceMatcher(a=[w.lower() for w, _ in 字们], b=[h[0].lower() for h in 听到], autojunk=False)
            时间 = [None] * len(字们)
            for blk in sm.get_matching_blocks():
                for k in range(blk.size):
                    时间[blk.a + k] = 听到[blk.b + k][1:]
            中 = sum(t is not None for t in 时间) / max(1, len(字们))
            已知 = [k for k, t in enumerate(时间) if t]
            for k in range(len(字们)):  # 没对上的字：在前后对上的字之间按顺序插进去
                if 时间[k] is None:
                    p = max([j for j in 已知 if j < k], default=None)
                    q = min([j for j in 已知 if j > k], default=None)
                    a = 时间[p][1] if p is not None else (时间[q][0] - 0.25 * (q - k) if q is not None else 0.0)
                    b = 时间[q][0] if q is not None else a + 0.25 * (k - (p or 0))
                    lo, hi = (p if p is not None else -1), (q if q is not None else len(字们))
                    t = a + (b - a) * (k - lo) / (hi - lo)
                    时间[k] = (max(0.0, t), max(0.0, t) + 0.2)
            方法 = f"whisper 听的，命中 {中:.0%}" + ("（不到六成，要用耳朵复核）" if 中 < 0.6 else "")
    if 时间 is None:
        小节 = 拍子["小节秒"]
        起 = g.从 if g.从 is not None else (拍子["重拍"][0] if 拍子["重拍"] else 0.0)
        时间 = []
        for i, l in enumerate(行们):
            a = 起 + i * g.每行小节 * 小节
            n = len(切(l))
            步 = g.每行小节 * 小节 * 0.85 / max(1, n)  # 一行的字唱在前 85%，留口气
            时间 += [(a + k * 步, a + (k + 1) * 步) for k in range(n)]
        方法 = f"平均分：从 {起:.2f} 秒起，一行 {g.每行小节} 小节（粗略，要用耳朵改）"
    out = []
    for i, l in enumerate(行们):
        字 = [[w, round(t[0], 3), round(t[1], 3)] for (w, j), t in zip(字们, 时间) if j == i]
        if 字:
            out.append({"行": l, "起": 字[0][1], "止": round(字[-1][2] + 0.3, 3), "字": 字})
    Path(g.出).parent.mkdir(parents=True, exist_ok=True)
    Path(g.出).write_text(json.dumps({"方法": 方法, "行": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK {g.出}：{len(out)} 行 {len(字们)} 个字｜{方法}")
    for r in out:
        print(f"{r['起']:7.2f}–{r['止']:6.2f}  {r['行']}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="歌词体检、歌词对时间")
    sub = ap.add_subparsers(dest="做", required=True)
    a = sub.add_parser("体检")
    a.add_argument("歌词")
    a.add_argument("--bpm", type=float, default=120)
    a.add_argument("--说唱", action="store_true")
    a.add_argument("--风格", default="")
    b = sub.add_parser("对时间")
    b.add_argument("歌词")
    b.add_argument("拍子")
    b.add_argument("--出", default="音乐/歌词.json")
    b.add_argument("--音频")
    b.add_argument("--模型", default="base")
    b.add_argument("--从", type=float)
    b.add_argument("--每行小节", type=float, default=2)
    g = ap.parse_args()
    sys.exit(体检(g) if g.做 == "体检" else 对时间(g))


if __name__ == "__main__":
    main()

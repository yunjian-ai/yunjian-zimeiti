"""口播片清剪：照对时间的结果把主人的录音／录像剪干净——去开头空白、句间停顿按句型压短、念了几遍留最后一遍、半截重来去掉；
有画面的每处剪开的地方交替推近（跳切不显生硬）；声音去低频嗡声、轻降噪。出粗剪＋删改表给主人看（关口：粗剪）。
读：口播/对时间.json（reel-voice/对时间.py 出的）、口播/转写.json 里记的录音位置（或 --录音）、口播/决定.json（可选，主人定的）。
写：口播/粗剪.mp4（只有声音就是 粗剪.wav）、口播/清剪.json（每段从原片哪到哪、每句在新片里的时间，成片和字幕用）、口播/删改表.md。
用法：
  python3 清剪.py 剪 <项目> [--录音 文件] [--推近 1.1] [--不推近]
  python3 清剪.py 剪 <项目> --只按声音      没装转文字时的退路：只按声音压停顿，念错重说不管，请主人在粗剪里看
决定.json 样子：{"删句": [3], "删多出来的": true, "停顿": {"？": 0.42, "。": 0.35, "，": 0.22}}——都可不写；
  漏念的句子本来就没有，不用写；主人要留前一遍的，在对时间那步说，这里不管。"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "reel-brief"))
import 媒体  # noqa: E402

停顿表 = {"？": 0.42, "?": 0.42, "。": 0.35, "！": 0.35, "!": 0.35, "…": 0.35, "：": 0.3, "；": 0.3, "，": 0.22, ",": 0.22, "、": 0.22, "": 0.12}
帧 = 0.01  # 包络 10 毫秒一格
最长停顿 = 0.5


def 包络(音频文件):
    """→ (每 10 毫秒的响度 dB 列表, 有声门槛 dB)。"""
    import numpy as np
    y = 媒体.解码音频(音频文件, sr=16000)
    n = int(len(y) / 160)
    rms = np.sqrt(np.mean(y[:n * 160].reshape(n, 160) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    底, 峰 = float(np.percentile(db, 10)), float(np.percentile(db, 95))
    return db, max(-45.0, min(底 + 12, 峰 - 18))  # 一直有声（底噪大、背景乐）时门槛也不会高过说话声


def 贴边(db, 门, 起, 止, 左界, 右界):
    """转文字给的起止常差 0.1～0.3 秒：起点挪到这句声音真正开始处，止点挪到真正结束处（不越过前后句）。"""
    k = lambda t: max(0, min(len(db) - 1, int(t / 帧)))  # noqa: E731
    a, lo, hi = k(起), k(左界), k(右界)
    if db[a] >= 门:
        while a > lo and max(db[max(lo, a - 8):a]) >= 门:
            a -= 1  # 往前走到前面连着 80 毫秒都安静为止
    else:
        lim = k(min(起 + 0.4, 止))
        while a < lim and db[a] < 门:
            a += 1
    b = k(止)
    if db[b] >= 门:
        while b < hi - 1 and max(db[b + 1:min(hi, b + 9)]) >= 门:
            b += 1  # 往后走到后面连着 80 毫秒都安静为止
    else:
        lim = k(max(止 - 0.4, 起))
        while b > lim and db[b] < 门:
            b -= 1
    return a * 帧, (b + 1) * 帧


def 句内长停(db, 门, a, b):
    """一句里面超过 0.5 秒的安静 → [(停起, 停止)]。"""
    out, s = [], None
    for i in range(int(a / 帧), int(b / 帧)):
        if db[i] < 门:
            s = i if s is None else s
        else:
            if s is not None and (i - s) * 帧 > 最长停顿:
                out.append((s * 帧, i * 帧))
            s = None
    return out


def 说话段(db, 门, 并=0.12):
    """只按声音：有声的地方连成段，中间安静不到 0.12 秒的并起来。"""
    段, s, 静 = [], None, 0
    for i, v in enumerate(db):
        if v >= 门:
            s = i if s is None else s
            静 = 0
        elif s is not None:
            静 += 1
            if 静 * 帧 > 并:
                段.append((s * 帧, (i - 静 + 1) * 帧))
                s, 静 = None, 0
    if s is not None:
        段.append((s * 帧, len(db) * 帧))
    return [(a, b) for a, b in 段 if b - a >= 0.08]


def 找录音(P, 给的):
    if 给的:
        return Path(给的)
    t = P / "口播" / "转写.json"
    if t.exists() and json.loads(t.read_text(encoding="utf-8")).get("录音"):
        return Path(json.loads(t.read_text(encoding="utf-8"))["录音"])
    fs = sorted((P / "录音").glob("*")) if (P / "录音").exists() else []
    if len(fs) != 1:
        sys.exit(f"NO_RECORDING：找不到录音。用 --录音 指定，或者在 {P / '录音'} 里只放一个")
    return fs[0]


def 排段(P, 录音, 决定, 只按声音):
    """→ (要留的句子段 [{号, 段, 句尾, 起, 止, 字幕}], 删掉的说明 [str])"""
    db, 门 = 包络(录音)
    长 = len(db) * 帧
    删 = []
    if 只按声音:
        段 = 说话段(db, 门)
        return [{"号": None, "段": 1, "句尾": "，", "起": a, "止": b, "字幕": ""} for a, b in 段], db, 门, ["只按声音压了停顿；念错重说没处理，请在粗剪里看"]
    对 = json.loads((P / "口播" / "对时间.json").read_text(encoding="utf-8"))
    删句 = set(决定.get("删句", []))
    句们 = []
    for s in 对["句"]:
        if s.get("夹带") or s.get("起") is None:
            if s.get("状态") == "漏念":
                删.append(f"第 {s['号']} 句「{s['字幕']}」录音里没有（漏念），片子里就没有这句")
            continue
        for d in s.get("删掉的遍", []):
            删.append(f"第 {s['号']} 句 {d['起']:.2f}–{d['止']:.2f}「{d['听到']}」：{d['为什么']}")
        if s["号"] in 删句:
            删.append(f"第 {s['号']} 句「{s['字幕']}」：主人说删")
            continue
        句们.append(dict(s))
    for m in 对.get("多出来的", []):
        if 决定.get("删多出来的"):
            删.append(f"{m['起']:.2f}–{m['止']:.2f}「{m['听到']}」：稿子里没有，主人说删")
        else:
            段 = max([s["段"] for s in 句们 if s["起"] <= m["起"]] or [1])
            句们.append({"号": None, "段": 段, "句尾": "，", "起": m["起"], "止": m["止"], "字幕": m["听到"], "多出来的": True})
    句们.sort(key=lambda s: s["起"])
    for i, s in enumerate(句们):
        左 = 句们[i - 1]["止"] if i else 0.0
        右 = 句们[i + 1]["起"] if i + 1 < len(句们) else 长
        s["起"], s["止"] = 贴边(db, 门, s["起"], s["止"], 左, 右)
    return 句们, db, 门, 删


def 剪(P, g):
    录音 = 找录音(P, g.录音)
    if not g.只按声音 and not (P / "口播" / "对时间.json").exists():
        sys.exit(f"NO_ALIGN：还没对时间。先跑 reel-voice/对时间.py 转、对；没装转文字工具就加 --只按声音")
    f = P / "口播" / "决定.json"
    决定 = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    停 = {**停顿表, **决定.get("停顿", {})}
    句们, db, 门, 删 = 排段(P, 录音, 决定, g.只按声音)
    if not 句们:
        sys.exit("NOTHING_LEFT：一句都没留下，看看对时间.md")
    信息 = 媒体.信息(录音)
    有画面 = bool(信息.get("宽"))
    长 = len(db) * 帧

    # 每句前后留多少：句间停顿照句型，前后各一半；原来就比这短的不动（连着不剪）
    段们 = []  # [原起, 原止, 段号]
    for i, s in enumerate(句们):
        前停 = 0.12 if i == 0 else 停.get(句们[i - 1]["句尾"], 0.22)
        后停 = 0.4 if i == len(句们) - 1 else 停.get(s["句尾"], 0.22)
        a = max(0.0, s["起"] - 前停 / 2 if i else s["起"] - 0.12)
        b = min(长, s["止"] + (后停 if i == len(句们) - 1 else 后停 / 2))
        pieces = [(a, b)]
        for x, y in 句内长停(db, 门, s["起"], s["止"]):  # 一句里面停太久的也压短
            last = pieces.pop()
            pieces += [(last[0], x + 0.15), (y - 0.15, last[1])]
        for x, y in pieces:
            if 段们 and x <= 段们[-1][1] + 1e-3:
                段们[-1][1] = max(段们[-1][1], y)  # 原来就连着：不剪
            else:
                段们.append([x, y, s["段"]])
    # 推近：同一段里每剪开一刀，在原大小和推近之间来回换；换段回到原大小
    推 = 1.0 if g.不推近 or not 有画面 else g.推近
    上段, z = None, 1.0
    for 段 in 段们:
        z = 1.0 if 段[2] != 上段 else (推 if z == 1.0 else 1.0)
        段.append(z)
        上段 = 段[2]
    # 新时间轴
    t, 新 = 0.0, []
    for a, b, 段号, z in 段们:
        新.append({"原起": round(a, 3), "原止": round(b, 3), "新起": round(t, 3), "新止": round(t + b - a, 3), "段": 段号, "推近": z})
        t += b - a
    映 = lambda x: next((n["新起"] + x - n["原起"] for n in 新 if n["原起"] - 1e-3 <= x <= n["原止"] + 1e-3), None)  # noqa: E731
    句时 = [{"号": s["号"], "原文": s.get("原文") or s["字幕"], "字幕": s["字幕"], "句尾": s["句尾"], "段": s["段"], "提示": s.get("提示", ""),
            "多出来的": bool(s.get("多出来的")),
            "起": round(映(s["起"]), 3), "止": round(映(s["止"]), 3)} for s in 句们]

    out = P / "口播" / ("粗剪.mp4" if 有画面 else "粗剪.wav")
    渲染(录音, 新, out, 信息, 有画面)
    原长, 新长 = 长, t
    长停 = [(round(a, 2), round(b - a, 2)) for a, b in 静音段(out) if b - a > 最长停顿 + 0.02 and a > 0.05 and b < 新长 - 0.6]
    (P / "口播" / "清剪.json").write_text(json.dumps({"录音": str(录音), "粗剪": str(out), "有画面": 有画面, "原长": round(原长, 3),
                                                   "新长": round(新长, 3), "段": 新, "句": 句时}, ensure_ascii=False, indent=1), encoding="utf-8")
    写删改表(P, 句们, 删, 新, 原长, 新长, 停, 长停, 有画面, g.只按声音)
    print(f"OK 粗剪 {原长:.1f} 秒 → {新长:.1f} 秒，剪开 {len(新) - 1} 处 → {out}")
    print((P / "口播" / "删改表.md").read_text(encoding="utf-8"))
    if 长停:
        print(f"⚠️ 还有超过 {最长停顿} 秒的停顿：{长停}（多半是一句里面停太久、声音门槛没认出来；看删改表、试 决定.json 里调停顿）")
        return 1
    return 0


def 渲染(录音, 段们, out, 信息, 有画面):
    """每段用 -ss/-t 单独读进来（准确切），声音头尾各淡 10 毫秒防爆音；画面按推近放大后裁回原尺寸；接起来，声音去嗡声、轻降噪。"""
    入, 链 = [], []
    W, H = (信息["宽"] // 2 * 2, 信息["高"] // 2 * 2) if 有画面 else (0, 0)
    for i, n in enumerate(段们):
        d = n["原止"] - n["原起"]
        入 += ["-ss", f"{n['原起']:.3f}", "-t", f"{d:.3f}", "-i", 录音]
        链.append(f"[{i}:a]aresample=48000,afade=t=in:d=0.01,afade=t=out:st={max(0, d - 0.01):.3f}:d=0.01,asetpts=PTS-STARTPTS[a{i}]")
        if 有画面:
            z = n["推近"]
            放 = f"scale={int(W * z) // 2 * 2}:{int(H * z) // 2 * 2},crop={W}:{H}," if z != 1.0 else ""
            链.append(f"[{i}:v]{放}scale={W}:{H},setsar=1,fps=30,setpts=PTS-STARTPTS[v{i}]")
    n = len(段们)
    if 有画面:
        链.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a0]")
    else:
        链.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a0]")
    链.append("[a0]highpass=f=80,afftdn=nf=-25[a]")
    参数 = ["-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "veryfast"] if 有画面 else []
    参数 += ["-map", "[a]", "-ar", "48000"] + (["-c:a", "aac", "-b:a", "160k"] if 有画面 else [])
    媒体.跑(*入, "-filter_complex", ";".join(链), *参数, out)


def 静音段(path, 门="-38dB"):
    import re
    err = 媒体.分析("-i", path, "-af", f"silencedetect=n={门}:d=0.3", "-f", "null", "-")
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    return list(zip(starts, ends))


def 写删改表(P, 句们, 删, 新, 原长, 新长, 停, 长停, 有画面, 只按声音):
    L = ["# 删改表（粗剪关口：您看过粗剪、点头了再往下排画面）", "",
         f"- 原来 {原长:.1f} 秒 → 现在 {新长:.1f} 秒；剪开 {len(新) - 1} 处" + ("，同一段里剪开的地方交替推近一点（跳切不显生硬），换段回到原大小" if 有画面 else ""),
         f"- 开头空白去掉 {新[0]['原起']:.2f} 秒；句间停顿按句型留：问句 {停['？']} 秒、句号 {停['。']} 秒、逗号 {停['，']} 秒、没标点 {停['']} 秒（嫌快嫌慢跟我说，记进您的口味）",
         "- 声音：去掉了低频嗡声、轻轻降了噪；响度到成片时统一"]
    if 删:
        L += ["", "**删掉的**："] + [f"- {x}" for x in 删]
    多 = [s for s in 句们 if s.get("多出来的")]
    if 多:
        L += ["", "**稿子里没有、录音里有、先留着的**（要删说一声）："] + [f"- 「{s['字幕']}」" for s in 多]
    if 长停:
        L += ["", f"⚠️ 还有超过 {最长停顿} 秒的停顿（新片里第几秒、多长）：{长停}"]
    if 只按声音:
        L += ["", "⚠️ 这次没转文字，只按声音压了停顿：念错重说的地方还在，请看粗剪时告诉我哪几处删"]
    (P / "口播" / "删改表.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="口播片清剪")
    ap.add_argument("做", choices=["剪"])
    ap.add_argument("项目")
    ap.add_argument("--录音")
    ap.add_argument("--推近", type=float, default=1.1)
    ap.add_argument("--不推近", action="store_true")
    ap.add_argument("--只按声音", action="store_true")
    g = ap.parse_args()
    return 剪(Path(g.项目).resolve(), g)


if __name__ == "__main__":
    sys.exit(main())

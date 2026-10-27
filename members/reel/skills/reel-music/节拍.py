"""扒拍子：一首歌 → 速度、每一拍、每小节第一拍（重拍）、重音、大落点、段落，写成 拍子.json。要 numpy 和 ffmpeg。
用法：python3 节拍.py <歌> [--out 音乐/拍子.json] [--bpm 140] [--shift 1] [--click 音乐/试听.wav]
  --bpm    已知速度（Suno 页面、提示词里写的），防止把 140 听成 70 或 280
  --shift  耳朵听出重拍偏了几拍，就整体往后挪几拍（0～3）
  --click  出一条叠了咔嗒声的试听：重拍高音、普通拍低音、大落点多一声，戴耳机听拍子漂不漂
机器结果只是起点，一定要用耳朵复核（听试听、或者跟着拍手）再往下做分镜。"""
import argparse
import json
import sys
from pathlib import Path

try:
    import numpy as np
except ImportError:
    sys.exit("NO_NUMPY：这个 python3 没装 numpy。先试试别的 python3（比如 /usr/bin/python3、python3.12）有没有装；都没有再问主人一句，同意后 pip install numpy")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reel-brief"))
import 媒体  # noqa: E402

SR, HOP, NFFT = 22050, 512, 1024
FPS = SR / HOP


def 频谱(y):
    """每一帧：全频起音强度、低频（<150Hz，底鼓和贝斯）起音强度、低频能量。"""
    y = np.concatenate([np.zeros(NFFT // 2, np.float32), y, np.zeros(NFFT, np.float32)])
    n = 1 + (len(y) - NFFT) // HOP
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    spec = np.abs(np.fft.rfft(y[idx] * np.hanning(NFFT), axis=1))
    low = np.fft.rfftfreq(NFFT, 1 / SR) < 150
    mag = np.log1p(spec * 10)
    up = np.maximum(0, np.diff(mag, axis=0, prepend=mag[:1]))
    z = lambda a: (a - a.mean()) / (a.std() + 1e-9)  # noqa: E731
    return z(up.sum(1)), z(up[:, low].sum(1)), (spec[:, low] ** 2).sum(1)


def 估速度(起音, 提示=None):
    """自相关看哪个间隔最常重复；连 2 倍、4 倍间隔一起算，再按常见速度（或给的 --bpm）加权，防止听成半速、倍速。"""
    ac = np.correlate(起音, 起音, "full")[len(起音) - 1:]
    ac = ac / (ac[0] + 1e-9)
    中心, 宽 = (提示, 0.15) if 提示 else (115.0, 0.9)
    候选 = np.arange(60, 200.01, 0.25)
    分 = []
    for b in 候选:
        lag = FPS * 60 / b
        s = sum(np.interp(lag * k, np.arange(len(ac)), ac) / k for k in (1, 2, 4))
        分.append(s * np.exp(-0.5 * (np.log2(b / 中心) / 宽) ** 2))
    return float(候选[int(np.argmax(分))])


def 细调(推动, bpm):
    """粗估的速度每 0.25 一档、又受帧长限制，会差 1 拍左右（128 估成 129）；
    在上下 2% 里按 0.02 细扫，取让匀速网格最贴鼓点的那个速度。"""
    xs = np.arange(len(推动))
    最好, 分 = bpm, -1e18
    for b in np.arange(bpm * 0.98, bpm * 1.02, 0.02):
        周期 = FPS * 60 / b
        s = max(np.interp(np.arange(p, len(推动), 周期), xs, 推动).sum() for p in np.arange(0, 周期, 1.0))
        if s > 分:
            最好, 分 = float(b), s
    return 最好


def 找拍(推动, 周期, 帧数):
    """先找相位（拍子从哪一帧起算最贴鼓点），再把每一拍吸到附近 ±6% 内的鼓点上；附近没有明显鼓点（前奏、间奏）就留在匀速网格上。"""
    xs = np.arange(帧数)
    相位们 = np.arange(0, 周期, 0.5)
    p0 = 相位们[int(np.argmax([np.interp(np.arange(p, 帧数, 周期), xs, 推动).sum() for p in 相位们]))]
    门槛 = 推动.mean() + 推动.std()

    def 吸(网格):
        out, 吸上 = [], []
        for k, c in enumerate(网格):
            lo, hi = int(max(0, c - 周期 * 0.06)), int(min(帧数, c + 周期 * 0.06 + 1))
            i = lo + int(np.argmax(推动[lo:hi])) if hi > lo else None
            if i is not None and 推动[i] > 门槛:
                out.append(i / FPS)
                吸上.append((k, i))
            else:
                out.append(c / FPS)
        return out, 吸上

    网格 = np.arange(p0, 帧数, 周期)
    _, 吸上 = 吸(网格)
    if len(吸上) >= 8:  # 用吸上鼓点的拍做直线拟合，把速度和起点再校准一遍，免得越到后面越漂
        k, i = np.array(吸上, dtype=float).T
        周期, p0 = np.polyfit(k, i, 1)
        p0 = p0 % 周期
        if p0 > 0.9 * 周期:  # 第一拍其实在 0 秒附近（略早于 0），别把它丢了
            p0 -= 周期
        网格 = np.arange(p0, 帧数, 周期)
    return 吸(网格)[0], FPS * 60 / 周期


def 分析(path, 提示=None, shift=0):
    y = 媒体.解码音频(path, SR)
    时长 = len(y) / SR
    全, 低, 低能量 = 频谱(y)
    推动 = 全 + 0.5 * 低  # 相位跟着底鼓走，不被反拍的镲带偏
    bpm = 细调(推动, 估速度(全, 提示))
    周期 = FPS * 60 / bpm
    拍, bpm = 找拍(推动, 周期, len(全))
    拍 = [round(max(0.0, t), 3) for t in 拍 if t < 时长 - 0.05]
    周期 = FPS * 60 / bpm
    帧 = [int(t * FPS) for t in 拍]
    峰 = lambda a, i: a[max(0, i - 2):i + 3].max() if i < len(a) else 0  # noqa: E731
    对数低 = np.log(低能量 + 1e-9)
    强 = [峰(低, i) + 0.5 * 峰(对数低, i) for i in 帧]
    起 = int(np.argmax([np.mean(强[k::4]) for k in range(4)])) if len(拍) >= 8 else 0
    起 = (起 + shift) % 4
    重拍 = 拍[起::4]
    重音 = sorted(拍[i] for i in np.argsort([-全[i] if i < len(全) else 0 for i in 帧])[:max(4, len(拍) // 6)])
    # 大落点：这一小节的低频能量比上一小节跳得最多的重拍（副歌进来、鼓重新进来的地方）
    小节能量 = [float(np.mean(对数低[int(t * FPS):int(t * FPS + 周期 * 4)])) if int(t * FPS) < len(对数低) else 0 for t in 重拍]
    跳幅 = {i: 小节能量[i] - 小节能量[i - 1] for i in range(1, len(重拍))}
    门槛 = max(1.0, 0.3 * max(跳幅.values(), default=0))  # 换和弦的小起伏不算，鼓、副歌整体进来才算
    大落点 = sorted(重拍[i] for i in sorted(跳幅, key=lambda i: -跳幅[i])[:3] if 跳幅[i] >= 门槛)
    响度 = np.array([float(np.sqrt(np.mean(y[int(a * SR):max(int(b * SR), int(a * SR) + 1)] ** 2) + 1e-12))
                   for a, b in zip(重拍, 重拍[1:] + [时长])])
    分 = lambda v: int(round(100 * v / (响度.max() + 1e-12)))  # noqa: E731
    段落 = [{"起": 重拍[i], "止": 重拍[i + 4] if i + 4 < len(重拍) else round(时长, 3),
            "能量": 分(响度[i:i + 4].mean())} for i in range(0, len(重拍), 4)]
    return {"音乐": str(path), "时长": round(时长, 3), "bpm": round(bpm, 2), "小节秒": round(4 * 60 / bpm, 3),
            "拍": 拍, "重拍": 重拍, "重音": 重音, "大落点": 大落点, "段落": 段落,
            "校正": {"bpm": 提示, "shift": shift},
            "说明": "机器检测，要用耳朵复核：听 --click 出的试听，重拍错位就加 --shift，速度错成一半或两倍就加 --bpm"}


def 试听(path, 结果, out):
    sr = 44100
    y = 媒体.解码音频(path, sr) * 0.6
    重 = set(结果["重拍"])
    落 = set(结果["大落点"])
    t = np.arange(int(0.035 * sr)) / sr
    for b in 结果["拍"]:
        f = 1600 if b in 重 else 1000
        c = 0.45 * np.sin(2 * np.pi * f * t) * np.exp(-t * 110)
        if b in 落:
            c = c + 0.45 * np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 60)
        s = int(b * sr)
        n = min(len(c), len(y) - s)
        if n > 0:
            y[s:s + n] += c[:n]
    媒体.写音频(out, y / max(1e-9, float(np.abs(y).max())), sr)


def main():
    ap = argparse.ArgumentParser(description="歌 → 拍子.json（每拍、重拍、重音、大落点、段落）")
    ap.add_argument("歌")
    ap.add_argument("--out", default="音乐/拍子.json")
    ap.add_argument("--bpm", type=float, help="已知速度，防止半速、倍速误判")
    ap.add_argument("--shift", type=int, default=0, help="重拍整体后移几拍（耳朵复核后校正）")
    ap.add_argument("--click", help="出一条叠咔嗒声的试听 wav")
    g = ap.parse_args()
    r = 分析(g.歌, g.bpm, g.shift)
    Path(g.out).parent.mkdir(parents=True, exist_ok=True)
    Path(g.out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    if g.click:
        试听(g.歌, r, g.click)
    print(f"速度 {r['bpm']} 拍／分｜一小节 {r['小节秒']} 秒｜{len(r['拍'])} 拍、{len(r['重拍'])} 小节｜时长 {r['时长']} 秒")
    print("大落点（秒）：" + ("、".join(f"{t:.3f}" for t in r["大落点"]) or "没找到明显的（整首能量平），挑能量最高的段落开头当落点"))
    print("段落（每 4 小节，能量 0～100）：" + "；".join(f"{s['起']:.2f}–{s['止']:.2f} 能量{s['能量']}" for s in r["段落"]))
    print(f"写入 {g.out}" + (f"；试听 {g.click}（戴耳机听：重拍高音，大落点多一声）" if g.click else ""))


if __name__ == "__main__":
    main()

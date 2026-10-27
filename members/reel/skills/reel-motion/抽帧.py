"""看视频：每条视频按固定间隔抽帧拼成一行、每格标秒数，几条上下叠成一张联系表，用眼睛判可用窗口。
还会算「画面突变」：和开头比、和上一格比变化最大的时间点（变形、变色、换脸常在这里），只是提示，以眼睛看为准。
用法：python3 抽帧.py 视频/01.mp4 [视频/02.mp4 …] --出 视频/联系表.jpg [--间隔 0.5] [--窗口表 视频/可用窗口.md]
  --间隔   几秒抽一格（默认 0.5；6 秒一条就是 12 格）
  --窗口表 没有这个文件就建一张骨架（每条一行，窗口先写整条、标「待看」），看完联系表再改成真的窗口
要 ffmpeg；算突变要 numpy（没有就只出联系表）。"""
import argparse
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reel-brief"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reel-board"))
import 媒体  # noqa: E402
import 镜头表  # noqa: E402

格宽, 格高 = 270, 270


def 一行(src, 间隔, 列, out, 字体):
    f = 媒体.滤镜路径(字体) if 字体 else None
    标 = (f"drawtext=fontfile={f}:text='%{{eif\\:floor(t)\\:d}}.%{{eif\\:mod(round(t*10)\\,10)\\:d}}s':x=6:y=h-30:fontsize=22:fontcolor=yellow:borderw=2:bordercolor=black,"
         if f else "")
    名 = (f",drawtext=fontfile={f}:text='{Path(src).name.replace(chr(39), '')}':x=8:y=6:fontsize=24:fontcolor=white:"
          f"box=1:boxcolor=black@0.6:boxborderw=4" if f else "")
    vf = (f"fps=1/{间隔}:round=down,scale={格宽}:{格高}:force_original_aspect_ratio=decrease,"
          f"pad={格宽}:{格高}:(ow-iw)/2:(oh-ih)/2:color=0x202020,{标}setpts=N/TB,tile={列}x1:padding=2:color=0x101010{名}")
    媒体.跑("-i", src, "-vf", vf, "-frames:v", "1", out)


def 突变(src, 间隔):
    """[(秒, 和开头差, 和上一格差)]，0～100。"""
    try:
        import numpy as np
    except ImportError:
        return []
    r = subprocess.run([媒体.ffmpeg(), "-v", "error", "-nostdin", "-i", str(src), "-vf", f"fps=1/{间隔}:round=down,scale=32:32",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    a = np.frombuffer(r.stdout, np.uint8)
    a = a[:len(a) // 3072 * 3072].reshape(-1, 3072).astype(float)
    if len(a) < 2:
        return []
    return [(round(i * 间隔, 2), round(float(np.abs(a[i] - a[0]).mean() / 2.55), 1),
             round(float(np.abs(a[i] - a[i - 1]).mean() / 2.55), 1) if i else 0.0) for i in range(len(a))]


def main():
    ap = argparse.ArgumentParser(description="视频 → 联系表＋突变提示")
    ap.add_argument("视频", nargs="+")
    ap.add_argument("--出", default="视频/联系表.jpg")
    ap.add_argument("--间隔", type=float, default=0.5)
    ap.add_argument("--窗口表")
    g = ap.parse_args()
    字体 = 媒体.字体(中文=True)
    长 = {v: 媒体.信息(v)["时长"] for v in g.视频}
    列 = max(2, max(math.ceil(d / g.间隔 - 1e-6) for d in 长.values()))
    out = Path(g.出)
    out.parent.mkdir(parents=True, exist_ok=True)
    行图 = []
    for k, v in enumerate(g.视频):
        p = out.with_name(f".{out.stem}-{k:02d}.png")
        一行(v, g.间隔, 列, p, 字体)
        行图.append(p)
    if len(行图) == 1:
        媒体.跑("-i", 行图[0], "-q:v", "3", out)
    else:
        媒体.跑(*sum([["-i", p] for p in 行图], []), "-filter_complex", f"vstack=inputs={len(行图)}", "-q:v", "3", out)
    for p in 行图:
        p.unlink()
    print(f"OK {out}：{len(g.视频)} 条，每 {g.间隔} 秒一格（每行 {列} 格）。打开看：脸、手、衣服图案、身形从第几秒开始不对")
    for v in g.视频:
        d = 突变(v, g.间隔)
        if not d:
            continue
        跳 = max(d[1:], key=lambda x: x[2])
        漂 = next((x for x in d if x[1] >= 25), None)
        话 = f"{Path(v).name}（{长[v]:.1f} 秒）：变化最猛在 {跳[0]} 秒前后（{跳[2]}）"
        if 漂:
            话 += f"；从 {漂[0]} 秒起和开头差很多（{漂[1]}）——可能变形、变色、换场，重点看这之后"
        print(话)
    if g.窗口表 and not Path(g.窗口表).exists():
        行们 = [[int("".join(c for c in Path(v).stem if c.isdigit()) or k + 1), v, f"0.0–{长[v]:.1f}（待看）", "", ""]
               for k, v in enumerate(g.视频)]
        Path(g.窗口表).write_text("# 可用窗口表\n> 看联系表后把「窗口」改成真能用的那一截（比如 0.0–3.0），写清问题和处理（留／缩短这一刀／重出／退回静帧）。\n\n"
                               + 镜头表.写表(镜头表.窗口表头, 行们) + "\n", encoding="utf-8")
        print(f"窗口表骨架：{g.窗口表}")


if __name__ == "__main__":
    main()

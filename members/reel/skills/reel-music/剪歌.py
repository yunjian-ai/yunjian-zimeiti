"""剪歌：把整首歌剪成短片用的长度，每段都从重拍切到重拍，接缝等功率交叉淡化，开头 5 毫秒淡入，结尾淡出。
用法：
  python3 剪歌.py <原曲> <出.wav> --秒 15 [--拍子 音乐/原曲拍子.json] [--从 47.3]
        自动：凑整小节、最接近 15 秒；不给 --从 就挑能量最高（最燃）的那一段，有大落点的优先让落点落在第 1～2 小节
  python3 剪歌.py <原曲> <出.wav> --段 7.964-14.791,47.369-71.6
        手动：几段拼起来（段落起止从拍子.json 的「重拍」里挑）
剪完会打印「成片时间 = 原曲第几秒」的对照，并写一份 <出>.对照.json（歌词对时间要用）。
剪完一定再跑一次 节拍.py 扒成片的拍子（接缝会让拍子挪一点），分镜按新的拍子.json 做。要 numpy 和 ffmpeg。"""
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

HERE = Path(__file__).resolve().parent


def 挑一段(歌, 拍子, 秒, 从=None):
    重拍 = 拍子["重拍"]
    小节 = 拍子["小节秒"]
    n = max(1, int(round(秒 / 小节)))
    if 从 is not None:
        i = int(np.argmin([abs(t - 从) for t in 重拍]))
        if i + n >= len(重拍) and 重拍[i] + n * 小节 > 拍子["时长"]:
            sys.exit(f"从 {从} 秒往后不够 {n} 小节，换早一点的起点")
        return 重拍[i], 重拍[i + n] if i + n < len(重拍) else round(重拍[i] + n * 小节, 3), "照主人给的起点"
    y = 媒体.解码音频(歌, 11025)
    rms = lambda a, b: float(np.sqrt(np.mean(y[int(a * 11025):max(int(b * 11025), int(a * 11025) + 1)] ** 2)))  # noqa: E731
    候选 = []
    for i in range(len(重拍) - n):
        a, b = 重拍[i], 重拍[i + n]
        落点 = [d - a for d in 拍子.get("大落点", []) if a - 0.05 <= d < a + 2 * 小节 - 0.05]
        # 落点在开头两小节内：一上来就炸，刷视频的人不划走；垫一小节再炸（落在第 2 小节）最好
        加分 = 1.25 if any(x >= 小节 - 0.05 for x in 落点) else 1.1 if 落点 else 1.0
        候选.append((rms(a, b) * 加分, a, b, 落点))
    if not 候选:
        sys.exit(f"整首只有 {len(重拍)} 小节，凑不出 {n} 小节，改短一点或用整首")
    _, a, b, 落点 = max(候选)
    return a, b, f"能量最高的 {n} 小节" + (f"，大落点在成片第 {落点[0]:.2f} 秒" if 落点 else "")


def 剪(src, out, 段, 淡化=0.03, 淡出=0.6):
    parts, labels = [], []
    for i, (a, b) in enumerate(段):
        尾 = 淡化 if i < len(段) - 1 else 0  # 每段尾巴多留一点给交叉淡化吃掉，接缝正好落在重拍上
        parts.append(f"[0:a]atrim={a:.3f}:{b + 尾:.3f},asetpts=PTS-STARTPTS[p{i}]")
        labels.append(f"[p{i}]")
    链, 当前 = [], labels[0]
    for i, 下 in enumerate(labels[1:], 1):
        链.append(f"{当前}{下}acrossfade=d={淡化}:c1=qsin:c2=qsin[x{i}]")
        当前 = f"[x{i}]"
    总 = sum(b - a for a, b in 段)
    fc = ";".join(parts + 链) + f";{当前}afade=t=in:d=0.005,afade=t=out:st={max(0, 总 - 淡出):.3f}:d={淡出}[out]"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    媒体.跑("-i", src, "-filter_complex", fc, "-map", "[out]", "-ar", "48000", *(["-b:a", "320k"] if str(out).endswith(".mp3") else []), out)
    对照, acc = [], 0.0
    for a, b in 段:
        对照.append({"成片起": round(acc, 3), "成片止": round(acc + b - a, 3), "原曲起": a, "原曲止": b, "成片时间等于原曲减": round(a - acc, 3)})
        acc += b - a
    return 总, 对照


def main():
    ap = argparse.ArgumentParser(description="整首歌 → 重拍到重拍的短版")
    ap.add_argument("原曲")
    ap.add_argument("出")
    ap.add_argument("--段", help="手动：a-b,c-d（秒，原曲时间）")
    ap.add_argument("--秒", type=float, help="自动：要多长（凑整小节）")
    ap.add_argument("--拍子", help="原曲的拍子.json；不给就现扒")
    ap.add_argument("--从", type=float, help="自动模式下指定从原曲第几秒附近的重拍开始")
    ap.add_argument("--淡化", type=float, default=0.03)
    ap.add_argument("--淡出", type=float, default=0.6)
    g = ap.parse_args()
    if bool(g.段) == bool(g.秒):
        ap.error("--段 和 --秒 选一个")
    if g.段:
        段 = [tuple(map(float, r.split("-"))) for r in g.段.split(",")]
        理由 = "照给的段落"
    else:
        if g.拍子:
            拍子 = json.loads(Path(g.拍子).read_text(encoding="utf-8"))
        else:
            sys.path.insert(0, str(HERE))
            import importlib
            拍子 = importlib.import_module("节拍").分析(g.原曲)
        a, b, 理由 = 挑一段(g.原曲, 拍子, g.秒, g.从)
        段 = [(a, b)]
        print(f"原曲 {拍子['bpm']} 拍／分，一小节 {拍子['小节秒']} 秒；挑的是 {a:.3f}–{b:.3f}（{理由}）")
    总, 对照 = 剪(g.原曲, g.出, 段, g.淡化, g.淡出)
    Path(str(g.出) + ".对照.json").write_text(json.dumps({"原曲": g.原曲, "段": 对照, "理由": 理由}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK {g.出} 共 {总:.3f} 秒")
    for x in 对照:
        print(f"成片 {x['成片起']:.3f}–{x['成片止']:.3f} = 原曲 {x['原曲起']:.3f}–{x['原曲止']:.3f}（成片时间 = 原曲 − {x['成片时间等于原曲减']:.3f}）")
    拍子出 = Path(g.出).with_name("拍子.json")
    print(f"下一步：python3 {HERE / '节拍.py'} {g.出} --out {拍子出} --click {Path(g.出).with_name('试听.wav')}（剪完再扒一次，戴耳机复核）")


if __name__ == "__main__":
    main()

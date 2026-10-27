"""拍子 → 每刀的切点 → 分镜.md 骨架（时间、素材文件名、大落点那刀都标好；景别、动作、大字这些留给分镜时填）。只用标准库。
用法：python3 切点.py 音乐/拍子.json [--秒 15] [--每刀小节 1] [--开场小节 0] [--快从 7.5 --快刀小节 0.5]
                    [--名 夜跑] [--画幅 9:16] [--出 分镜.md] [--覆盖]
规矩：切点都在重拍上（半小节＝第 3 拍）；开场几小节可以留给纯大字；一刀不短于 0.5 秒，最后一刀不短于 0.8 秒（太短就并进上一刀）。
分镜.md 已经有了就不写（加 --覆盖 才写，旧的先备份成 分镜-旧-时间.md）。"""
import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import 镜头表  # noqa: E402


def 切(拍子, 秒, 每刀, 开场, 快从, 快刀):
    拍 = [t for t in 拍子["拍"] if t < 秒 - 0.3]
    重 = set(拍子["重拍"])
    起 = next((i for i, t in enumerate(拍) if t in 重), 0)
    切点, i = [0.0], 起 + int(开场 * 4)
    if i < len(拍) and 拍[i] > 0.2:
        切点.append(拍[i])
    while True:
        步 = 快刀 if 快从 is not None and 拍[min(i, len(拍) - 1)] >= 快从 - 0.05 else 每刀
        i += max(1, int(round(步 * 4)))
        if i >= len(拍) or 拍[i] > 秒 - 0.8:
            break
        切点.append(拍[i])
    切点 = sorted(set(round(c, 3) for c in 切点))
    刀 = [(a, b) for a, b in zip(切点, 切点[1:] + [round(秒, 3)]) if b - a >= 0.5 or b == round(秒, 3)]
    if len(刀) > 1 and 刀[-1][1] - 刀[-1][0] < 0.8:
        刀[-2:] = [(刀[-2][0], 刀[-1][1])]
    return 刀


def main():
    ap = argparse.ArgumentParser(description="拍子 → 切点和分镜骨架")
    ap.add_argument("拍子")
    ap.add_argument("--秒", type=float, help="成片多长（默认整首歌）")
    ap.add_argument("--每刀小节", type=float, default=1, help="正常段一刀几小节（1 或 2；慢歌 1 小节就够长）")
    ap.add_argument("--开场小节", type=float, default=0, help="开场纯大字占几小节（0＝不要）")
    ap.add_argument("--快从", type=float, help="从第几秒起切快（副歌、大落点）")
    ap.add_argument("--快刀小节", type=float, default=0.5)
    ap.add_argument("--名", default="")
    ap.add_argument("--画幅", default="9:16")
    ap.add_argument("--出", default="分镜.md")
    ap.add_argument("--覆盖", action="store_true")
    g = ap.parse_args()
    拍子 = json.loads(Path(g.拍子).read_text(encoding="utf-8"))
    秒 = min(g.秒 or 拍子["时长"], 拍子["时长"])
    刀 = 切(拍子, 秒, g.每刀小节, g.开场小节, g.快从, g.快刀小节)
    落点 = [d for d in 拍子.get("大落点", []) if d < 秒]
    行们 = []
    for k, (a, b) in enumerate(刀, 1):
        备注 = []
        if g.开场小节 and k == 1:
            备注.append("开场纯大字（不出视频）")
        if any(a - 0.05 <= d < b - 0.05 for d in 落点):
            备注.append("⚡大落点：放最猛的镜头")
        if k == len(刀):
            备注.append("片尾卡")
        素材 = "—" if g.开场小节 and k == 1 else f"视频/{k:02d}.mp4"
        行们.append([k, f"{a:.3f}–{b:.3f}", "【待填】", "", "", "", "", "", "【待填】", 素材, "；".join(备注)])
    out = Path(g.出)
    if out.exists() and not g.覆盖:
        sys.exit(f"EXISTS：{out} 已经有了，主人点过头的分镜不能随手盖掉；确实要重做加 --覆盖（旧的会备份）")
    if out.exists():
        备份 = out.with_name(f"{out.stem}-旧-{datetime.datetime.now().strftime('%m%d-%H%M')}.md")
        备份.write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"旧分镜备份到 {备份}")
    长 = [b - a for a, b in 刀]
    头 = [f"# 《{g.名 or '未命名'}》分镜 · v1",
          f"歌：{拍子.get('音乐', '')} ｜ {拍子['bpm']} 拍／分 ｜ 一小节 {拍子['小节秒']} 秒 ｜ 时长 {秒:.3f} 秒 ｜ 画幅 {g.画幅} ｜ "
          f"大落点 {'、'.join(f'{d:.3f}' for d in 落点) or '无'}",
          "", "## 三行创意", "- 钩子（开头 2 秒让人停下来的那一下）：【待填】", "- 主线（这条片子讲什么变化）：【待填】",
          "- 每句一个画面（歌词或节奏段 → 画面）：【待填】", "", "## 镜头表", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(头) + 镜头表.写表(镜头表.镜头表头, 行们) + "\n", encoding="utf-8")
    print(f"OK {out}：{len(刀)} 刀，一刀 {min(长):.2f}～{max(长):.2f} 秒；大落点在第 "
          f"{'、'.join(str(k) for k, r in enumerate(行们, 1) if '大落点' in r[-1]) or '—'} 刀")
    for k, (a, b) in enumerate(刀, 1):
        print(f"{k:>2}  {a:7.3f}–{b:7.3f}（{b - a:.2f} 秒）")
    print("下一步：填景别、镜头动作、人物动作、表情、主体位置、大字，再跑 体检.py")


if __name__ == "__main__":
    main()

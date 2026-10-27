"""调色：6 套自带色彩（和风格预设一一对应），也能用主人自己的 .cube。要 ffmpeg；导出 .cube 要 numpy。
用法：python3 调色.py 套 <视频或图> <出> --色 街头逆光 [--强度 0.8]
      python3 调色.py 对比 <一帧.jpg> <出.jpg>          同一帧套全部 6 套拼成对比图，给主人挑
      python3 调色.py 导出 <色名> <出.cube> [--级 5]    导出成 .cube（剪映、达芬奇能直接用；--级 4 出小一点的 16³）
      python3 调色.py 列                                列出 6 套和各自的样子
色名也可以直接写一个 .cube 文件的路径。成片.py 用 滤镜(色名, 强度) 拿到同一条调色链。"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reel-brief"))
import 媒体  # noqa: E402

色们 = {  # 名字: (样子, ffmpeg 调色链——只调颜色，不带暗角这类跟位置有关的，好导出 .cube)
    "街头逆光": ("暗部偏青、亮部偏暖，对比略强、饱和略降：夜景、逆光、街头",
             "eq=contrast=1.12:brightness=-0.03:saturation=0.86,colorbalance=rs=-0.05:gs=0.01:bs=0.07:rh=0.07:gh=0.02:bh=-0.06"),
    "赛博霓虹": ("暗部青蓝、亮部品红，高对比高饱和：霓虹、科技、夜店",
             "eq=contrast=1.2:saturation=1.3,colorbalance=rs=-0.06:gs=-0.02:bs=0.12:rh=0.10:gh=-0.07:bh=0.09"),
    "国风": ("暖纸色、暗部带玉青，低饱和柔对比：汉服、山水、茶",
           "eq=contrast=0.94:brightness=0.02:saturation=0.72,colorbalance=rs=-0.02:gs=0.04:bs=0.01:rh=0.05:gh=0.03:bh=-0.04"),
    "复古胶片": ("黑位抬起、轻褪色、暖黄：怀旧、街拍、生活",
             "curves=all='0/0.07 0.5/0.5 1/0.94',eq=saturation=0.8,colorbalance=bs=0.03:rh=0.08:gh=0.04:bh=-0.08"),
    "动漫": ("提亮、高饱和、天空偏冷：二次元、校园、夏天",
           "eq=brightness=0.04:contrast=1.05:saturation=1.3,colorbalance=bs=0.05:bm=0.03"),
    "明亮清新": ("提亮、对比略低、白更白：服装、美妆、日常",
             "eq=brightness=0.05:contrast=0.96:saturation=1.08:gamma=1.05,colorbalance=rh=-0.02:bh=0.03"),
}


def 滤镜(色, 强度=1.0):
    """返回一段能接在滤镜链里的调色（单进单出）。"""
    if not 色 or 色 == "无":
        return "null"
    if str(色).lower().endswith(".cube"):
        if not Path(色).exists():
            sys.exit(f"NO_LUT：找不到 {色}")
        链 = f"lut3d=file={媒体.滤镜路径(Path(色).resolve())}:interp=tetrahedral"
    elif 色 in 色们:
        链 = 色们[色][1]
    else:
        sys.exit(f"NO_LUT：没有「{色}」这套色；可选：{'、'.join(色们)}，或给一个 .cube 文件")
    if 强度 >= 0.999:
        return 链
    return f"split[原][调];[调]{链}[调好];[原][调好]blend=all_expr='A*{1 - 强度:.3f}+B*{强度:.3f}'"


def 套(g):
    图 = g.入.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    媒体.跑("-i", g.入, "-filter_complex", f"[0:v]{滤镜(g.色, g.强度)}[v]", "-map", "[v]", *([] if 图 else
          ["-map", "0:a?", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "copy"]), g.出)
    print(f"OK {g.出}（{g.色}，强度 {g.强度}）")


def 对比(g):
    名 = ["原片"] + list(色们)
    f = 媒体.字体(True)
    fc = f"[0:v]scale=480:-2,split={len(名)}" + "".join(f"[s{i}]" for i in range(len(名))) + ";"
    for i, n in enumerate(名):
        tf = Path(g.出).with_name(f".色名{i}.txt")
        tf.write_text(n, encoding="utf-8")
        字 = f",drawtext=fontfile={媒体.滤镜路径(f)}:textfile={媒体.滤镜路径(tf)}:x=12:y=12:fontsize=30:fontcolor=white:borderw=3" if f else ""
        fc += f"[s{i}]" + ("null" if i == 0 else 滤镜(n).replace("[原]", f"[原{i}]").replace("[调]", f"[调{i}]")) + f"{字}[o{i}];"
    cols = 4
    lay = "|".join(f"{'+'.join(['w0'] * (i % cols)) or '0'}_{'+'.join(['h0'] * (i // cols)) or '0'}" for i in range(len(名)))
    fc += "".join(f"[o{i}]" for i in range(len(名))) + f"xstack=inputs={len(名)}:layout={lay}:fill=black"
    媒体.跑("-i", g.入, "-filter_complex", fc, "-frames:v", "1", "-q:v", "3", g.出)
    for i in range(len(名)):
        Path(g.出).with_name(f".色名{i}.txt").unlink()
    print(f"OK {g.出}：原片＋{len(色们)} 套，请主人挑一套")


def 导出(g):
    import numpy as np
    级 = g.级  # Hald 级数：5 → 25³（默认），4 → 16³（小一些）
    n = 级 * 级
    r = subprocess.run([媒体.ffmpeg(), "-v", "error", "-nostdin", "-f", "lavfi", "-i", f"haldclutsrc=level={级}",
                        "-vf", 滤镜(g.色), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"], capture_output=True)
    if r.returncode:
        sys.exit("FFMPEG_FAILED：" + r.stderr.decode(errors="replace")[-300:])
    c = np.frombuffer(r.stdout, "<u2").reshape(-1, 3)[: n ** 3] / 65535.0
    行 = [f'TITLE "{Path(g.色).stem}"', "# 云间·掠影 调色表", f"LUT_3D_SIZE {n}"] + [f"{x:.5f} {y:.5f} {z:.5f}" for x, y, z in c]
    Path(g.出).parent.mkdir(parents=True, exist_ok=True)
    Path(g.出).write_text("\n".join(行) + "\n", encoding="utf-8")
    print(f"OK {g.出}（{n}³）")


def main():
    ap = argparse.ArgumentParser(description="调色")
    sub = ap.add_subparsers(dest="做", required=True)
    a = sub.add_parser("套")
    a.add_argument("入")
    a.add_argument("出")
    a.add_argument("--色", default="街头逆光")
    a.add_argument("--强度", type=float, default=1.0)
    b = sub.add_parser("对比")
    b.add_argument("入")
    b.add_argument("出")
    c = sub.add_parser("导出")
    c.add_argument("色")
    c.add_argument("出")
    c.add_argument("--级", type=int, default=5, choices=[4, 5, 6])
    sub.add_parser("列")
    g = ap.parse_args()
    if g.做 == "列":
        for k, (样, _) in 色们.items():
            print(f"{k}：{样}")
    else:
        {"套": 套, "对比": 对比, "导出": 导出}[g.做](g)


if __name__ == "__main__":
    main()

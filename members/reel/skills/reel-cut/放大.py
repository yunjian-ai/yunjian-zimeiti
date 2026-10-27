"""放大到 4K：有 Real-ESRGAN（命令 realesrgan-ncnn-vulkan）就逐帧超分，没有就 ffmpeg 高质量放大＋轻锐化（随时能用）。
用法：python3 放大.py 出片/成片.mp4 出片/成片_4K.mp4 [--尺寸 2160x3840] [--只用ffmpeg]
不给 --尺寸：竖版出 2160×3840，横版出 3840×2160。
4K 版给抖音这类收 4K 的平台；视频号码率上限 10Mbps，发视频号用 1080 那版。"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reel-brief"))
import 媒体  # noqa: E402

编码 = ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-maxrate", "40M", "-bufsize", "80M", "-pix_fmt", "yuv420p",
      "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-c:a", "copy", "-movflags", "+faststart"]


def main():
    ap = argparse.ArgumentParser(description="放大到 4K")
    ap.add_argument("入")
    ap.add_argument("出")
    ap.add_argument("--尺寸")
    ap.add_argument("--只用ffmpeg", action="store_true")
    g = ap.parse_args()
    d = 媒体.信息(g.入)
    W, H = (int(x) for x in g.尺寸.split("x")) if g.尺寸 else ((2160, 3840) if d["高"] > d["宽"] else (3840, 2160))
    esr = shutil.which("realesrgan-ncnn-vulkan")
    if esr and not g.只用ffmpeg:
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t) / "a", Path(t) / "b"
            a.mkdir()
            b.mkdir()
            媒体.跑("-i", g.入, a / "%06d.png")
            subprocess.run([esr, "-i", str(a), "-o", str(b), "-n", "realesr-animevideov3", "-s", "2"], check=True)
            媒体.跑("-framerate", d.get("帧率") or 30, "-i", b / "%06d.png", "-i", g.入, "-map", "0:v", "-map", "1:a?",
                   "-vf", f"scale={W}:{H}:flags=lanczos", *编码, g.出)
        怎么 = "Real-ESRGAN 超分"
    else:
        媒体.跑("-i", g.入, "-map", "0:v", "-map", "0:a?", "-vf", f"scale={W}:{H}:flags=lanczos,unsharp=5:5:0.6:5:5:0.0", *编码, g.出)
        怎么 = "ffmpeg 高质量放大＋轻锐化（没装 Real-ESRGAN）"
    print(f"OK {g.出} {W}×{H}（{怎么}）")


if __name__ == "__main__":
    main()

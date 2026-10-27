"""抠像：底片 → 人像遮罩视频（白＝人，黑＝背景），成片.py 用它把大字压在人身后。CPU 就能跑。
要 rembg：pip install "rembg[cpu]"。模型第一次用时自动下载：u2netp 约 5MB（快、边缘粗），u2net_human_seg 约 170MB（人像更细，默认）。
**Grok Bot 在它自己的云端电脑上装，不占主人电脑；在主人本机装之前先问主人同意。** 不装也行：成片.py 没有遮罩就把大字放在人前面。
用法：python3 抠像.py 出片/底片.mp4 出片/遮罩.mp4 [--模型 u2net_human_seg] [--宽 512]
      python3 抠像.py 一张图.png 遮罩.png"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reel-brief"))
import 媒体  # noqa: E402


def 会话(模型):
    try:
        from rembg import new_session
    except ImportError:
        print('MATTE_DEPS_MISSING：没装抠像。Grok Bot 云端直接装：pip install "rembg[cpu]"；'
              "主人本机先问一句（约 170MB），不装就让大字放在人前面", file=sys.stderr)
        sys.exit(3)
    return new_session(模型)


def 一帧(s, rgb):
    import numpy as np
    from PIL import Image
    from rembg import remove
    return np.asarray(remove(Image.fromarray(rgb), session=s, only_mask=True, post_process_mask=True), dtype=np.uint8)


def main():
    ap = argparse.ArgumentParser(description="底片 → 人像遮罩")
    ap.add_argument("入")
    ap.add_argument("出")
    ap.add_argument("--模型", default="u2net_human_seg", help="u2net_human_seg（人像，默认）／u2netp（小而快）／isnet-general-use（宠物、物件）")
    ap.add_argument("--宽", type=int, default=512, help="推理宽度：越小越快，遮罩放大后会羽化边缘")
    g = ap.parse_args()
    s = 会话(g.模型)
    import numpy as np
    if g.入.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        from PIL import Image
        im = Image.open(g.入).convert("RGB")
        W, H = im.size
        m = 一帧(s, np.asarray(im.resize((g.宽, round(H * g.宽 / W / 2) * 2))))
        Image.fromarray(m).resize((W, H)).save(g.出)
        print("OK", g.出)
        return
    d = 媒体.信息(g.入)
    W, H, fps = d["宽"], d["高"], d.get("帧率") or 30
    w = g.宽 if W >= H else round(g.宽 * W / H / 2) * 2
    h = round(H * w / W / 2) * 2
    ff = 媒体.ffmpeg()
    读 = subprocess.Popen([ff, "-v", "error", "-nostdin", "-i", g.入, "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    写 = subprocess.Popen([ff, "-v", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
                         "-vf", f"scale={W}:{H}:flags=bicubic,gblur=sigma=1.5", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", g.出],
                        stdin=subprocess.PIPE)
    n, 每帧 = 0, w * h * 3
    while True:
        buf = 读.stdout.read(每帧)
        if len(buf) < 每帧:
            break
        写.stdin.write(一帧(s, np.frombuffer(buf, np.uint8).reshape(h, w, 3)).tobytes())
        n += 1
        if n % 60 == 0:
            print(f"…{n} 帧", flush=True)
    写.stdin.close()
    写.wait()
    读.wait()
    print(f"OK {g.出}：{n} 帧（推理 {w}×{h}，输出 {W}×{H}）。成片.py 会自动用它")


if __name__ == "__main__":
    main()

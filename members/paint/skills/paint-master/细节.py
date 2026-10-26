"""从原图裁细节、放大；把多格母版板拆成单张。细节特写从主人原图取，不让模型重画（重画会编）。
有 Pillow 用 Pillow；没有就用 macOS 自带的 sips；两样都没有就说清楚，改让模型「只做裁剪和清晰化，不改内容」。
用法：python3 细节.py <原图> --box 左,上,右,下 --out 单张/细节-领口.png [--scale 2]
       （box 可写像素，也可写百分比：--box 30%,10%,70%,40%）
     python3 细节.py <母版板> --grid 2x2 --outdir 单张/ [--prefix 板]      按行从左到右拆，存成 板-1.png…"""
import argparse
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None


def size_of(path):
    if Image:
        with Image.open(path) as im:
            return im.size
    if shutil.which("sips"):
        out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)], capture_output=True, text=True).stdout
        vals = [int(line.split(":")[1]) for line in out.splitlines() if "pixel" in line]
        return vals[0], vals[1]
    raise RuntimeError("NO_TOOL")


def parse_box(text, w, h):
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError("box 要写 4 个数：左,上,右,下")
    vals = []
    for p, full in zip(parts, (w, h, w, h)):
        vals.append(round(float(p[:-1]) / 100 * full) if p.endswith("%") else int(float(p)))
    l, t, r, b = vals
    if not (0 <= l < r <= w and 0 <= t < b <= h):
        raise ValueError(f"box {l},{t},{r},{b} 超出图片范围 {w}x{h} 或左上右下写反了")
    return l, t, r, b


def grid_boxes(w, h, spec):
    cols, rows = (int(x) for x in spec.lower().split("x"))
    if cols < 1 or rows < 1:
        raise ValueError("grid 要写成 列x行，例 2x2")
    cw, rh = w // cols, h // rows
    return [(c * cw, r * rh, (c + 1) * cw, (r + 1) * rh) for r in range(rows) for c in range(cols)]


def read_bmp(path):
    """读无压缩的 24／32 位 BMP，返回 (宽, 高, 每像素字节数, 从上到下的行列表，每行是 BGR(A) 字节)。"""
    d = Path(path).read_bytes()
    off, (w, h, _, bpp, comp) = struct.unpack("<I", d[10:14])[0], struct.unpack("<iiHHI", d[18:34])
    if bpp not in (24, 32) or comp not in (0, 3):
        raise RuntimeError("NO_TOOL")
    px, stride = bpp // 8, (w * bpp // 8 + 3) & ~3
    rows = [d[off + i * stride: off + i * stride + w * px] for i in range(abs(h))]
    return w, abs(h), px, (rows if h < 0 else rows[::-1])


def write_png(path, w, h, rows_rgb):
    raw = b"".join(b"\x00" + r for r in rows_rgb)
    ch = lambda t, x: struct.pack(">I", len(x)) + t + x + struct.pack(">I", zlib.crc32(t + x) & 0xffffffff)  # noqa: E731
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + ch(b"IDAT", zlib.compress(raw, 6)) + ch(b"IEND", b""))


def crop(src, box, out, scale=1.0):
    l, t, r, b = box
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    if Image:
        with Image.open(src) as im:
            part = im.crop(box)
            if scale != 1:
                part = part.resize((round(part.width * scale), round(part.height * scale)), Image.LANCZOS)
            part.save(out)
        return
    # 不用 sips 自带的裁剪：带偏移裁剪时灵时不灵（有的偏移原图不动、退出码还是 0，macOS 26 实测）。
    # 改成 sips 只转成 BMP，裁剪自己按像素做，再写回 PNG。
    with tempfile.TemporaryDirectory() as tmp:
        bmp = Path(tmp) / "src.bmp"
        subprocess.run(["sips", "-s", "format", "bmp", str(src), "--out", str(bmp)], capture_output=True, check=True)
        w, h, px, rows = read_bmp(bmp)
    part = []
    for row in rows[t:b]:
        seg = row[l * px: r * px]
        part.append(bytes(c for i in range(0, len(seg), px) for c in (seg[i + 2], seg[i + 1], seg[i])))
    write_png(out, r - l, b - t, part)
    if scale != 1:
        subprocess.run(["sips", "-z", str(round((b - t) * scale)), str(round((r - l) * scale)), str(out)], capture_output=True, check=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--box")
    ap.add_argument("--out")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--grid")
    ap.add_argument("--outdir")
    ap.add_argument("--prefix", default="格")
    a = ap.parse_args(argv)
    try:
        w, h = size_of(a.src)
    except RuntimeError:
        print("NO_TOOL 这里没有 Pillow 也没有 sips：改让出图模型只裁剪、清晰化这一块，提示词写「不改任何内容」")
        return 3
    try:
        if a.grid:
            outdir = Path(a.outdir or ".")
            for i, box in enumerate(grid_boxes(w, h, a.grid), 1):
                crop(a.src, box, outdir / f"{a.prefix}-{i}.png", a.scale)
                print(f"OK {outdir / f'{a.prefix}-{i}.png'}")
        elif a.box and a.out:
            box = parse_box(a.box, w, h)
            crop(a.src, box, a.out, a.scale)
            print(f"OK {a.out}｜从 {w}x{h} 裁 {box}｜放大 {a.scale} 倍")
        else:
            ap.error("要么 --box 加 --out，要么 --grid 加 --outdir")
    except ValueError as e:
        print("❌", e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""把引擎出的大图裁成平台交付像素、压到大小上限以内；也能只查一张成品合不合规格。
有 Pillow 用 Pillow；没有就用 macOS 自带的 sips（只用它的缩放、居中裁、转 JPEG——带偏移的裁剪不可靠，不用）。
用法：python3 交付.py <大图> --size 1440x1440 --max-mb 5 --out 成品.jpg [--white]
       先等比放大或缩小到「铺满」目标尺寸，再从正中裁掉多出来的；--white 把接近白的背景压成纯白（白底图用）
     python3 交付.py --check <成品> --size 800x800 --max-mb 3 [--white]    只查：像素、大小、白底四角"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "paint-master"))
from 细节 import Image, read_bmp, size_of  # noqa: E402

WHITE_CUT = 245  # 三个通道都 ≥ 这个值就当背景白，压成 255


def corners(path):
    """四个角的像素（RGB）。"""
    if Image:
        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            return [im.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    with tempfile.TemporaryDirectory() as t:
        bmp = Path(t) / "c.bmp"
        subprocess.run(["sips", "-s", "format", "bmp", str(path), "--out", str(bmp)], capture_output=True, check=True)
        w, h, px, rows = read_bmp(bmp)
    pick = lambda r, x: (rows[r][x * px + 2], rows[r][x * px + 1], rows[r][x * px])  # noqa: E731
    return [pick(0, 0), pick(0, w - 1), pick(h - 1, 0), pick(h - 1, w - 1)]


def check(path, size, max_mb, white=False):
    errs = []
    w, h = size_of(path)
    if size and (w, h) != size:
        errs.append(f"像素 {w}x{h}，要的是 {size[0]}x{size[1]}")
    mb = Path(path).stat().st_size / 1024 / 1024
    if max_mb and mb > max_mb:
        errs.append(f"文件 {mb:.2f}MB，超过上限 {max_mb}MB")
    if white:
        bad = [c for c in corners(path) if tuple(c[:3]) != (255, 255, 255)]
        if bad:
            errs.append(f"白底四角不是纯白：{bad[0]}")
    return errs


def fit_pil(src, out, tw, th, white, max_mb):
    with Image.open(src) as im:
        im = im.convert("RGB")
        s = max(tw / im.width, th / im.height)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        l, t = (im.width - tw) // 2, (im.height - th) // 2
        im = im.crop((l, t, l + tw, t + th))
        if white:
            im = im.point(lambda v: 255 if v >= WHITE_CUT else v)  # 每个通道各自压：只把接近白的拉满
        jpg = Path(out).suffix.lower() in (".jpg", ".jpeg")
        for q in (92, 88, 84, 80, 75, 70, 65, 60):
            im.save(out, quality=q) if jpg else im.save(out, optimize=True)
            if not max_mb or not jpg or Path(out).stat().st_size <= max_mb * 1024 * 1024:
                break


def fit_sips(src, out, tw, th, white, max_mb):
    w, h = size_of(src)
    s = max(tw / w, th / h)
    nw, nh = max(tw, round(w * s)), max(th, round(h * s))
    jpg = Path(out).suffix.lower() in (".jpg", ".jpeg")
    with tempfile.TemporaryDirectory() as t:
        mid = Path(t) / "mid.png"
        subprocess.run(["sips", "-z", str(nh), str(nw), str(src), "--out", str(mid)], capture_output=True, check=True)
        subprocess.run(["sips", "-c", str(th), str(tw), str(mid)], capture_output=True, check=True)  # 不带偏移＝居中裁，可靠
        for q in (92, 88, 84, 80, 75, 70, 65, 60):
            args = ["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(q)] if jpg else ["sips", "-s", "format", "png"]
            subprocess.run(args + [str(mid), "--out", str(out)], capture_output=True, check=True)
            if not max_mb or not jpg or Path(out).stat().st_size <= max_mb * 1024 * 1024:
                break
    if white:
        print("⚠️ 没有 Pillow，没法把背景压成纯白；出图时写死纯白背景，交付前用 --check --white 查四角")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--size", required=True)
    ap.add_argument("--max-mb", type=float)
    ap.add_argument("--out")
    ap.add_argument("--white", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    try:
        tw, th = (int(x) for x in a.size.lower().split("x"))
    except ValueError:
        print("❌ --size 写成 宽x高，例 1440x1440")
        return 2
    if not Image and not shutil.which("sips"):
        print("NO_TOOL 这里没有 Pillow 也没有 sips：裁压做不了，交大图并告诉主人要的像素")
        return 3
    if a.check:
        errs = check(a.src, (tw, th), a.max_mb, a.white)
    else:
        if not a.out:
            ap.error("要写 --out")
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        (fit_pil if Image else fit_sips)(a.src, a.out, tw, th, a.white, a.max_mb)
        errs = check(a.out, (tw, th), a.max_mb, a.white and bool(Image))
    for e in errs:
        print("❌", e)
    print(f"✅ {a.out or a.src}｜{tw}x{th}" if not errs else f"共 {len(errs)} 处不合规格")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())

"""把图层（logo、标题、卖点、价格、色块）叠到底图上，出成品。要 Pillow 和一款中文字体。
用法：python3 叠图.py <底图> <图层.json> -o 成品.png [--font 字体文件]
图层.json 格式见 图类写法卡.md 最后一节：坐标、大小是占整张图的比例（0～1），按列表顺序从下往上叠。
  text：自动找框里放得下的最大字号，放不下就按字换行；align 可写 left / center / right（默认 center，和调图网页一致）
  image：src 相对图层.json 所在文件夹，等比放进框里、居中
  rect：色块，color 写 #RRGGBB，opacity 0～1（默认 1）
先裁到交付像素（交付.py）再叠，字最清楚。没有 Pillow 或找不到中文字体：退出码 3，改交底图＋调图网页（paint-adjust），主人在网页里导出成品。"""
import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

FONT_DIRS = ["~/Library/Fonts", "/Library/Fonts", "/System/Library/Fonts", "/System/Library/Fonts/Supplemental",
             "/usr/share/fonts", "/usr/local/share/fonts", "~/.fonts", "~/.local/share/fonts", "~/.yunjian/paint/字体"]
FAMILIES = {  # 图层里写的字体名 -> 文件名里找这些词（按先后）
    "思源宋体": ["SourceHanSerif", "NotoSerifCJK", "NotoSerifSC", "Songti", "STSong"],
    "思源黑体": ["SourceHanSans", "NotoSansCJK", "NotoSansSC", "PingFang", "STHeiti", "Hiragino Sans GB", "wqy"],
    "阿里巴巴普惠体": ["AlibabaPuHuiTi", "Alibaba-PuHuiTi", "PingFang", "NotoSansCJK"],
}
ANY_CJK = ["SourceHanSans", "NotoSansCJK", "NotoSansSC", "PingFang", "STHeiti", "Hiragino Sans GB", "Songti", "wqy", "SourceHanSerif"]


def font_files():
    out = []
    for d in FONT_DIRS:
        p = Path(d).expanduser()
        if p.is_dir():
            out += [f for f in p.rglob("*") if f.suffix.lower() in (".ttf", ".ttc", ".otf")]
    return out


def find_font(name=None, files=None):
    files = files if files is not None else font_files()
    for key in FAMILIES.get(name, []) + ANY_CJK:
        hit = [f for f in files if key.lower() in f.name.lower()]
        if hit:
            return sorted(hit, key=lambda f: ("bold" in f.name.lower(), len(f.name)))[0]
    return None


def wrap(text, font, draw, max_w):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if draw.textlength(cur + ch, font=font) <= max_w or not cur:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    return lines + ([cur] if cur else [])


def fit_text(draw, text, path, box_w, box_h):
    """二分找最大字号：换行后总高度和每行宽度都在框里。"""
    lo, hi, best = 6, max(8, int(box_h)), None
    while lo <= hi:
        size = (lo + hi) // 2
        font = ImageFont.truetype(str(path), size)
        lines = wrap(text, font, draw, box_w)
        line_h = size * 1.25
        if len(lines) * line_h <= box_h and all(draw.textlength(x, font=font) <= box_w for x in lines):
            best, lo = (font, lines, line_h), size + 1
        else:
            hi = size - 1
    return best


def hex_rgb(c, default=(0, 0, 0)):
    c = (c or "").lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) if len(c) >= 6 else default


def compose(base, layers_path, out, font_path=None):
    if not Image:
        print("NO_TOOL 没有 Pillow：改交底图＋调图网页，主人在网页里点导出拿成品")
        return 3
    layers = json.loads(Path(layers_path).read_text(encoding="utf-8"))
    folder = Path(layers_path).parent
    files = font_files() if not font_path else []
    im = Image.open(base).convert("RGBA")
    W, H = im.size
    warns = []
    for L in layers:
        x, y, w, h = (L.get(k, 0) * s for k, s in (("x", W), ("y", H), ("w", W), ("h", H)))
        t = L.get("type")
        if t == "rect":
            over = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(over).rectangle([x, y, x + w, y + h], fill=hex_rgb(L.get("color")) + (round(255 * float(L.get("opacity", 1))),))
            im = Image.alpha_composite(im, over)
        elif t == "image":
            with Image.open(folder / L["src"]) as pic:
                pic = pic.convert("RGBA")
                s = min(w / pic.width, h / pic.height)
                pic = pic.resize((max(1, round(pic.width * s)), max(1, round(pic.height * s))), Image.LANCZOS)
                im.alpha_composite(pic, (round(x + (w - pic.width) / 2), round(y + (h - pic.height) / 2)))
        elif t == "text":
            path = Path(font_path) if font_path else find_font(L.get("font"), files)
            if not path:
                print("NO_FONT 找不到中文字体：改交底图＋调图网页（网页用主人电脑的字体），或 --font 指定字体文件")
                return 3
            draw = ImageDraw.Draw(im)
            got = fit_text(draw, L.get("text", ""), path, w, h)
            if not got:
                warns.append(f"图层「{L.get('id')}」框太小，字放不下")
                continue
            font, lines, line_h = got
            align = L.get("align", "center")
            for i, line in enumerate(lines):
                lw = draw.textlength(line, font=font)
                lx = x + {"center": (w - lw) / 2, "right": w - lw}.get(align, 0)
                draw.text((lx, y + i * line_h), line, font=font, fill=hex_rgb(L.get("color")))
        else:
            warns.append(f"图层「{L.get('id')}」类型「{t}」不认识，跳过")
        if x < 0.04 * W - 1 or y < 0.04 * H - 1 or x + w > 0.96 * W + 1 or y + h > 0.96 * H + 1:
            if t != "rect":
                warns.append(f"图层「{L.get('id')}」离边缘不到 4%，可能被裁、被截断")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(out, quality=92) if Path(out).suffix.lower() in (".jpg", ".jpeg") else im.save(out)
    for w_ in warns:
        print("⚠️", w_)
    print(f"OK {out}｜{W}x{H}｜{len(layers)} 层")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("layers")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--font")
    a = ap.parse_args(argv)
    return compose(a.base, a.layers, a.out, a.font)


if __name__ == "__main__":
    sys.exit(main())

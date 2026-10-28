"""带货片的卡片：用商品图（丹青母版或原图）在本地拼结尾卡、卖点卡——字是脚本写的，不让模型画字（模型画字会错）。要 PIL。
用法：
  python3 卡片.py 结尾 <商品图> -o 静帧/05.png --名 "米白手工开衫" --点 "手工粗针／新西兰羊毛／胡桃木扣" [--价 "¥299"] [--画幅 9:16] [--底 "#F2F0EC"]
  python3 卡片.py 卖点 <商品图> -o 静帧/03.png --点 "手工粗针" [--画幅 9:16]     一张图配一个卖点大字（字在上 30%，避开底部按钮区）
价格、卖点只写主人给的；行动号召按钮由成片.py 叠（不画进卡片，免得两层）。"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import 字体  # noqa: E402

画幅表 = {"9:16": (1080, 1920), "3:4": (1080, 1440), "1:1": (1080, 1080), "16:9": (1920, 1080)}


def 色(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def 贴商品(底, 图路径, 框):
    from PIL import Image
    x0, y0, x1, y1 = 框
    im = Image.open(图路径).convert("RGBA")
    r = min((x1 - x0) / im.width, (y1 - y0) / im.height)
    im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    底.paste(im, (x0 + (x1 - x0 - im.width) // 2, y0 + (y1 - y0 - im.height) // 2), im)


def 居中写(画, text, 字, y, W, 颜色):
    w = 画.textlength(text, font=字)
    画.text(((W - w) / 2, y), text, font=字, fill=颜色)


def 结尾(g, W, H):
    from PIL import Image, ImageDraw, ImageFont
    底 = Image.new("RGB", (W, H), 色(g.底))
    贴商品(底, g.图, (int(W * 0.1), int(H * 0.12), int(W * 0.9), int(H * 0.55)))
    画 = ImageDraw.Draw(底)
    f = 字体.找("中文")
    名字 = ImageFont.truetype(f, int(W * 0.075))
    小 = ImageFont.truetype(f, int(W * 0.045))
    y = H * 0.57
    if g.名:
        居中写(画, g.名, 名字, y, W, (34, 30, 28))
        y += W * 0.11
    点们 = [x.strip() for x in (g.点 or "").replace("|", "／").split("／") if x.strip()]
    if 点们:
        居中写(画, "  ·  ".join(点们), 小, y, W, (90, 80, 72))
        y += W * 0.08
    if g.价:
        居中写(画, g.价, ImageFont.truetype(f, int(W * 0.09)), y, W, (230, 58, 58))
    if y > H * 0.78:
        print("⚠️ 字排到了底部按钮区附近：少写一个卖点或不写价格", file=sys.stderr)
    return 底


def 卖点(g, W, H):
    from PIL import Image, ImageDraw, ImageFont
    底 = Image.new("RGB", (W, H), 色(g.底))
    贴商品(底, g.图, (0, int(H * 0.22), W, int(H * 0.8)))
    画 = ImageDraw.Draw(底)
    字 = ImageFont.truetype(字体.找("中文"), int(W * 0.1))
    居中写(画, (g.点 or "").strip(), 字, H * 0.1, W, (34, 30, 28))
    return 底


def main():
    ap = argparse.ArgumentParser(description="带货片卡片")
    ap.add_argument("种", choices=["结尾", "卖点"])
    ap.add_argument("图")
    ap.add_argument("-o", required=True)
    ap.add_argument("--名", default="")
    ap.add_argument("--点", default="")
    ap.add_argument("--价", default="")
    ap.add_argument("--画幅", default="9:16", choices=list(画幅表))
    ap.add_argument("--底", default="#F2F0EC")
    g = ap.parse_args()
    try:
        import PIL  # noqa: F401
    except ImportError:
        sys.exit("NO_PIL：要 PIL（pip install pillow）。Grok Bot 云端自带；本机没有先问主人一句再装")
    W, H = 画幅表[g.画幅]
    im = (结尾 if g.种 == "结尾" else 卖点)(g, W, H)
    Path(g.o).parent.mkdir(parents=True, exist_ok=True)
    im.save(g.o)
    print(f"OK {g.o}（{W}×{H}）")


if __name__ == "__main__":
    main()

"""卡片：带货片的结尾卡、卖点卡（用商品图），口播片的要点卡、步骤卡、对比表——字都是脚本写的，不让模型画字（模型画字会错）。要 PIL。
用法：
  python3 卡片.py 结尾 <商品图> -o 静帧/05.png --名 "米白手工开衫" --点 "手工粗针／新西兰羊毛／胡桃木扣" [--价 "¥299"] [--画幅 9:16] [--底 "#F2F0EC"]
  python3 卡片.py 卖点 <商品图> -o 静帧/03.png --点 "手工粗针" [--画幅 9:16]     一张图配一个卖点大字（字在上 30%，避开底部按钮区）
  python3 卡片.py 要点 -o 静帧/03.png --题 "冷冻层三格" --点 "主食／肉／零食" [--图 背景.png]   要点最多 4 条
  python3 卡片.py 步骤 -o 静帧/04.png --第 1 --共 3 --题 "全拿出来" --点 "过期的、结霜的，直接扔" [--图 背景.png]
  python3 卡片.py 对比 -o 静帧/05.png --左 "以前" --右 "现在" --点 "塞满关不上|三格一眼找到／23 袋|吃完再买"
  口播卡的标题想更大（比如只有「23 袋」几个字）：加 --字号 1.6（标题放大 1.6 倍，放不下照样自动缩、折两行）
口播片的卡：字照执笔稿原文（一字不改），排在安全区里——右边让出点赞那一列、底部让出文案和按钮区（9:16 推算值，见库 视频规格）；字太长自动缩小，缩到下限还放不下就报出来。
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


def 安全框(W, H):
    """内容只放这里：左 6%、右让出 18%（点赞评论那一列）、上 10%、下让出 28%（文案、按钮）；横屏宽松些。"""
    if W > H:
        return int(W * 0.06), int(H * 0.08), int(W * 0.94), int(H * 0.82)
    return int(W * 0.06), int(H * 0.10), int(W * 0.82), int(H * 0.72)


def 合字(画, text, 宽, 号, 下限=0.6):
    """从 号 往下缩，直到一行放得下；缩到 号×下限 还放不下返回 None。"""
    from PIL import ImageFont
    f = 字体.找("中文")
    n = 号
    while n >= 号 * 下限:
        字 = ImageFont.truetype(f, int(n))
        if 画.textlength(text, font=字) <= 宽:
            return 字
        n *= 0.92
    return None


def 写段(画, text, x, y, 宽, 号, 颜色):
    """一行放得下（字号不小于 0.75 倍）就一行；放不下在靠中间的标点处（没有就正中）折成两行；两行还放不下报出来。返回写完后的 y。"""
    字 = 合字(画, text, 宽, 号, 0.75)
    if 字:
        画.text((x, y), text, font=字, fill=颜色)
        return y + 号 * 1.35
    中 = len(text) / 2
    候 = sorted((m.end() for m in __import__("re").finditer(r"[，、；：,]", text[:-1])), key=lambda k: abs(k - 中)) or [int(中)]
    a, b = text[:候[0]], text[候[0]:]
    字 = 合字(画, max(a, b, key=len), 宽, 号)
    if not 字:
        写不下(text)
    画.text((x, y), a, font=字, fill=颜色)
    画.text((x, y + 字.size * 1.25), b, font=字, fill=颜色)
    return y + 字.size * 2.5 + 号 * 0.1


def 口播底(g, W, H):
    from PIL import Image, ImageEnhance, ImageFilter
    if g.图:
        im = Image.open(g.图).convert("RGB")
        r = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
        im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
        return ImageEnhance.Brightness(im.filter(ImageFilter.GaussianBlur(W // 60))).enhance(0.45), (255, 255, 255), (255, 214, 64)
    return Image.new("RGB", (W, H), 色(g.底)), (34, 30, 28), (214, 84, 40)


def 写不下(text):
    sys.exit(f"TEXT_TOO_LONG：「{text}」在安全区里放不下（字已缩到下限）。请主人删几个字，或拆成两张卡——字照稿子，不替主人改")


def 要点(g, W, H):
    from PIL import ImageDraw
    底, 字色, 亮色 = 口播底(g, W, H)
    画 = ImageDraw.Draw(底)
    x0, y0, x1, y1 = 安全框(W, H)
    宽 = x1 - x0
    点们 = [x.strip() for x in (g.点 or "").replace("|", "／").split("／") if x.strip()]
    if not 点们 or len(点们) > 4:
        sys.exit("BAD_POINTS：要点卡写 1～4 条（多了看不过来，拆成两张）")
    y = y0 + (y1 - y0) * 0.2
    if g.题:
        y = 写段(画, g.题, x0, y, 宽, W * 0.09 * g.字号, 亮色) + W * 0.03
    缩 = W * 0.09 if len(点们) > 1 else 0  # 只有一条不标号
    for i, p in enumerate(点们, 1):
        if 缩:
            画.text((x0, y), f"{i}", font=合字(画, f"{i}", 宽, W * 0.07), fill=亮色)
        y = 写段(画, p, x0 + 缩, y, 宽 - 缩, W * 0.07, 字色) + W * 0.025
    if y > y1:
        写不下("、".join(点们))
    return 底


def 步骤(g, W, H):
    from PIL import ImageDraw
    底, 字色, 亮色 = 口播底(g, W, H)
    画 = ImageDraw.Draw(底)
    x0, y0, x1, y1 = 安全框(W, H)
    宽 = x1 - x0
    中文数 = "零一二三四五六七八九十"
    标 = f"第{中文数[g.第] if g.第 <= 10 else g.第}步"
    y = y0 + (y1 - y0) * 0.2
    if not g.题.startswith(标):  # 稿子原句已经以「第一步」开头就不再重复
        画.text((x0, y), 标, font=合字(画, 标, 宽, W * 0.08), fill=亮色)
        y += W * 0.14
    if g.题:
        y = 写段(画, g.题, x0, y, 宽, W * 0.1 * g.字号, 字色) + W * 0.03
    if g.点:
        y = 写段(画, g.点, x0, y, 宽, W * 0.055, 字色)
    if g.共:  # 进度点：第几步亮，紧跟在字下面（不靠近底部字幕）
        r, cy = W * 0.018, y + W * 0.06
        for k in range(1, g.共 + 1):
            cx = x0 + r + (k - 1) * r * 3.2
            画.ellipse((cx - r, cy - r, cx + r, cy + r), fill=亮色 if k <= g.第 else (150, 150, 150))
    return 底


def 对比(g, W, H):
    from PIL import ImageDraw
    底, 字色, 亮色 = 口播底(g, W, H)
    画 = ImageDraw.Draw(底)
    x0, y0, x1, y1 = 安全框(W, H)
    列宽 = (x1 - x0) // 2 - int(W * 0.02)
    行们 = [x.split("|", 1) for x in (g.点 or "").split("／") if "|" in x]
    if not 行们 or len(行们) > 4:
        sys.exit("BAD_POINTS：对比表写 1～4 行，每行「左|右」，行和行用／隔开")
    y = y0 + (y1 - y0) * 0.2
    for 文, x in ((g.左, x0), (g.右, x0 + 列宽 + int(W * 0.04))):
        画.text((x, y), 文, font=合字(画, 文, 列宽, W * 0.075) or 写不下(文), fill=亮色)
    y += W * 0.14
    画.line((x0 + 列宽 + int(W * 0.02), y - W * 0.02, x0 + 列宽 + int(W * 0.02), y + len(行们) * W * 0.12), fill=字色, width=max(2, W // 300))
    for a, b in 行们:
        for 文, x in ((a.strip(), x0), (b.strip(), x0 + 列宽 + int(W * 0.04))):
            画.text((x, y), 文, font=合字(画, 文, 列宽, W * 0.055) or 写不下(文), fill=字色)
        y += W * 0.12
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
    ap.add_argument("种", choices=["结尾", "卖点", "要点", "步骤", "对比"])
    ap.add_argument("图", nargs="?", help="商品图（结尾、卖点要）；口播卡用 --图 当背景")
    ap.add_argument("--图", dest="背景")
    ap.add_argument("--题", default="")
    ap.add_argument("--第", type=int, default=1)
    ap.add_argument("--共", type=int, default=0)
    ap.add_argument("--字号", type=float, default=1.0)
    ap.add_argument("--左", default="")
    ap.add_argument("--右", default="")
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
    if g.种 in ("结尾", "卖点") and not g.图:
        sys.exit("NO_IMAGE：结尾卡、卖点卡要给商品图")
    if g.种 in ("要点", "步骤", "对比"):
        g.图 = g.背景 or g.图  # 口播卡的背景图：--图 或直接跟在后面都认
    im = {"结尾": 结尾, "卖点": 卖点, "要点": 要点, "步骤": 步骤, "对比": 对比}[g.种](g, W, H)
    Path(g.o).parent.mkdir(parents=True, exist_ok=True)
    im.save(g.o)
    print(f"OK {g.o}（{W}×{H}）")


if __name__ == "__main__":
    main()

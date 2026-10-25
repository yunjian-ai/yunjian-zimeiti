"""把口播稿（形式卡第一节的交稿样子）转成彩色提词卡网页。只用标准库。

给人看：台词大字占主位；左边色条分段（红钩子、橙冲突、黄戳观众、绿转折、蓝结果、紫引导，段多了接着轮）；
==黄底== 是重点句和字幕词；**红字** 是数字和重读；段头〔 〕里的画面、动作、语气是灰色小标签，扫一眼就行。
用法：python3 提词卡.py 稿子.txt [-o 提词卡.html]      稿子用 - 就从标准输入读
     不写 -o 就存在稿子旁边、同名 .html；从标准输入读时存成当前目录的 提词卡.html。"""
import html
import re
import sys
from pathlib import Path

SEG = re.compile(r"^\s*(?:[🟥🟧🟨🟩🟦🟪⬛⬜]\s*)?([①-⑳])\s*([^\s〔0-9]+)\s*([0-9～~\-—.″\"秒 ]*)?\s*(?:〔(.*?)〕)?\s*$")
COLORS = ["#e63946", "#f4a261", "#e9c46a", "#2a9d8f", "#3a86ff", "#8338ec"]
DARK_TEXT = {"#e9c46a"}
CSS = """:root{--bg:#fff;--ink:#1a1a1a;--muted:#8a8a8a;--cue-bg:#f1f1f1;--hl:#ffe45c;--stress:#d62828}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#121212;--ink:#f2f2f2;--muted:#9a9a9a;--cue-bg:#262626;--hl:#c9a800;--stress:#ff6b6b}}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:24px 16px 48px}h1{font-size:24px;margin:0 0 6px}
.meta{color:var(--muted);font-size:14px;margin-bottom:22px}
.seg{border-left:8px solid var(--c);padding:6px 0 6px 16px;margin:0 0 22px}
.head{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:8px}
.tag{background:var(--c);color:var(--t);font-weight:700;font-size:14px;padding:2px 10px;border-radius:4px}
.time{color:var(--muted);font-size:13px}.cue{background:var(--cue-bg);color:var(--muted);font-size:13px;padding:2px 10px;border-radius:999px}
.line{font-size:26px;line-height:1.55;font-weight:500;margin:0}
mark{background:var(--hl);color:inherit;padding:0 3px;border-radius:3px}.stress{color:var(--stress);font-weight:800}
.legend{margin-top:28px;font-size:13px;color:var(--muted);line-height:1.8}"""


def inline(text):
    t = html.escape(text.replace(" / ", "").replace("/", ""))
    t = re.sub(r"==(.+?)==", r"<mark>\1</mark>", t)
    return re.sub(r"\*\*(.+?)\*\*", r'<span class="stress">\1</span>', t)


def parse(text):
    title, meta, segs, cur = "", "", [], None
    for raw in text.splitlines():
        s = raw.strip()
        m = SEG.match(s)
        if m:
            cur = {"no": m.group(1), "name": m.group(2), "time": (m.group(3) or "").strip(), "cue": m.group(4) or "", "lines": []}
            segs.append(cur)
            continue
        if not segs:
            t = re.match(r"^\**标题\**[：:]\s*(.+)", s)
            if t:
                title = t.group(1).strip()
            elif s and not meta:
                meta = s
            continue
        if not s:
            continue
        if re.match(r"^\**(约 ?\d+ ?字|出处|稿型|借用单|钩子链|句长|待问|推算|检查码|引导)", s):
            cur = None  # 交稿说明行开始，台词到此为止
            continue
        if cur is not None:
            cur["lines"].append(s)
    return title, meta, [x for x in segs if x["lines"]]


def render(text):
    title, meta, segs = parse(text)
    if not segs:
        raise SystemExit("没找到分段（段头要像「🟥 ① 钩子 0～3″〔提示〕」）")
    out = [f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
           f"<title>{html.escape(title or '口播提词卡')}</title><style>{CSS}</style></head><body><div class=\"wrap\">",
           f"<h1>{inline(title)}</h1>" if title else "", f'<div class="meta">{html.escape(meta)}</div>' if meta else ""]
    for i, sg in enumerate(segs):
        c = COLORS[i % len(COLORS)]
        t = "#1a1a1a" if c in DARK_TEXT else "#fff"
        out.append(f'<div class="seg" style="--c:{c};--t:{t}"><div class="head"><span class="tag">{sg["no"]} {html.escape(sg["name"])}</span>'
                   + (f'<span class="time">{html.escape(sg["time"])}</span>' if sg["time"] else "")
                   + (f'<span class="cue">{html.escape(sg["cue"])}</span>' if sg["cue"] else "") + "</div>"
                   + "".join(f'<p class="line">{inline(l)}</p>' for l in sg["lines"]) + "</div>")
    out.append('<div class="legend">怎么看：左边色条＝第几段；<mark>黄底</mark>＝重点句、字幕词；<span class="stress">红字</span>＝数字和重读；'
               "灰色小标签＝画面 · 动作 · 语气，扫一眼就行。</div></div></body></html>")
    return "".join(out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    src = argv[0]
    text = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")
    dest = Path(argv[argv.index("-o") + 1]) if "-o" in argv else (Path("提词卡.html") if src == "-" else Path(src).with_suffix(".html"))
    dest.write_text(render(text), encoding="utf-8")
    print(f"提词卡已生成：{dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

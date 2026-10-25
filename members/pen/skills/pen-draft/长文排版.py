"""把长文写作稿（形式卡第二节的交稿样子）转成排版网页，再出一份去掉段落标注的发布版文字。只用标准库。

给人看：网页上有两个按钮——「写作视图」按颜色标出钩子（红）、论点（蓝）、证据（绿）、槽点（橙）、图片位（紫）、收藏件（金），
给主人审稿用；「发布视图」是读者看到的样子。==黄底== 是重点句，**红字** 是数字和重读，★ 💡 ⚠️ 👇 【可以直接抄】各有固定样式。
用法：python3 长文排版.py 稿子.md [-o 排版.html]     稿子用 - 就从标准输入读
     同时在网页旁边存一份「同名-发布版.md」（去掉【钩子】这类标注，留下读者要看的）。"""
import html
import re
import sys
from pathlib import Path

ROLES = {"钩子": "hook", "论点": "point", "证据": "proof", "槽点": "slot", "收藏件": "save"}
ROLE_RE = re.compile(r"^【(钩子|论点|证据|槽点|收藏件)】\s*")
MEDIA_RE = re.compile(r"^👇\s*【(图|图表|视频)】\s*(.*)$")
META_RE = re.compile(r"^\**(约 ?\d+ ?字|出处|待问|推算|平台[：:])")
CSS = """:root{--bg:#fff;--ink:#1d1d1f;--muted:#86868b;--line:#e5e5ea;--card:#f5f5f7;--hl:#ffe45c;--stress:#d62828;
--hook:#e63946;--point:#3a86ff;--proof:#2a9d8f;--slot:#f4a261;--media:#8338ec;--save:#c9a227}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#121212;--ink:#f2f2f2;--muted:#9a9a9a;--line:#2c2c2e;--card:#1c1c1e;--hl:#c9a800;--stress:#ff6b6b}}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;line-height:1.85;font-size:17px}
.wrap{max-width:720px;margin:0 auto;padding:20px 16px 60px}
.bar{position:sticky;top:0;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--line);display:flex;gap:8px;flex-wrap:wrap;z-index:2}
.bar button{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:6px 14px;border-radius:999px;font-size:14px;cursor:pointer}
.bar button.on{background:var(--ink);color:var(--bg)}
h1{font-size:26px;line-height:1.4;margin:22px 0 6px}.sub{color:var(--muted);font-size:14px;margin-bottom:18px}
h2{font-size:22px;margin:34px 0 10px;padding-bottom:6px;border-bottom:2px solid var(--ink)}
h3{font-size:18px;margin:24px 0 8px}h3::before{content:"▍";color:var(--point)}
p{margin:10px 0}mark{background:var(--hl);color:inherit;padding:0 3px;border-radius:3px}.num{color:var(--stress);font-weight:800}
.toc{background:var(--card);border-radius:10px;padding:12px 16px;margin:14px 0}.toc ol{margin:6px 0;padding-left:22px}
.step{margin:8px 0}.tip,.pit{border-radius:10px;padding:10px 14px;margin:12px 0}
.tip{background:rgba(42,157,143,.10)}.pit{background:rgba(230,57,70,.10)}
.copy{background:var(--card);border:1px dashed var(--muted);border-radius:10px;padding:10px 14px;margin:12px 0;font-size:15px;white-space:pre-wrap}
.copy .cap{font-size:12px;color:var(--muted);margin-bottom:4px;white-space:normal}
.media{border:2px dashed var(--media);border-radius:10px;padding:12px 14px;margin:14px 0;color:var(--media);font-size:15px}.media .cap{font-weight:700}
table{border-collapse:collapse;width:100%;font-size:15px;margin:10px 0}td,th{border:1px solid var(--line);padding:6px 8px;text-align:left}th{background:var(--card)}
body.write [data-role]{border-left:5px solid var(--c);padding-left:12px;margin-left:-17px}
body.write [data-role]::before{content:attr(data-role);display:block;width:fit-content;margin:6px 0 -4px;font-size:11px;font-weight:700;color:#fff;background:var(--c);padding:0 8px;border-radius:4px;line-height:1.7}
.r-hook{--c:var(--hook)}.r-point{--c:var(--point)}.r-proof{--c:var(--proof)}.r-slot{--c:var(--slot)}.r-save{--c:var(--save)}
body:not(.write) .note{display:none}.legend{font-size:13px;color:var(--muted);margin-top:30px;line-height:2}
.legend span{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 10px;vertical-align:middle}"""
JS = "function v(w){document.body.classList.toggle('write',!!w);document.getElementById('bw').classList.toggle('on',!!w);document.getElementById('bp').classList.toggle('on',!w);}"


def inline(text):
    t = html.escape(text)
    t = re.sub(r"==(.+?)==", r"<mark>\1</mark>", t)
    return re.sub(r"\*\*(.+?)\*\*", r'<span class="num">\1</span>', t)


def table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows if not re.match(r"^\|?\s*:?-{2,}", r.strip())]
    if not cells:
        return ""
    head = "".join(f"<th>{inline(c)}</th>" for c in cells[0])
    body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
    return f"<table><tr>{head}</tr>{body}</table>"


def render(text):
    lines = text.splitlines()
    title, sub, out, pub = "", "", [], []
    i, role = 0, None
    while i < len(lines):
        s = lines[i].strip()
        if s == "---" or (META_RE.match(s) and title):
            break
        m = re.match(r"^(?:\**标题\**[：:]|#(?!#))\s*(.+)", s)  # 「标题：…」或「# …」都认（10-24 比稿盲看，有写手用 # 起头）
        if m and not title:
            title = re.sub(r"（候选.*?）", "", m.group(1)).strip()
            pub.append(f"# {title}")
            i += 1
            continue
        if not s:
            role = None
            i += 1
            continue
        if title and not sub and not out and re.match(r"^约 ?\d+ ?分钟", s):
            sub = s
            pub.append(s)
            i += 1
            continue
        rm = ROLE_RE.match(s)
        if rm:
            role = rm.group(1)
            s = ROLE_RE.sub("", s)
            if not s:  # 单独一行的标注，管下面的表格或段落
                i += 1
                continue
        attr = f' data-role="{role}" class="r-{ROLES[role]}"' if role else ""
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                pub.append(lines[i].strip())
                i += 1
            out.append(f"<div{attr}>{table(rows)}</div>")
            role = None
            continue
        if s.startswith("### "):
            out.append(f"<h3>{inline(s[4:])}</h3>"); pub.append(s)
        elif s.startswith("## "):
            out.append(f"<h2>{inline(s[3:])}</h2>"); pub.append(s)
        elif re.match(r"^目录[：:]", s):
            items = [x.strip() for x in re.split(r"\s*\d+[.、]\s*|[｜|；;]", re.sub(r"^目录[：:]\s*", "", s)) if x.strip()]  # 编号或｜、；隔开都认
            out.append('<div class="toc"><b>这篇讲这些</b><ol>' + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol></div>")
            pub.append(s)
        elif s.startswith("★"):
            out.append(f'<div class="step">{inline(s)}</div>'); pub.append(s)
        elif s.startswith("💡"):
            out.append(f'<div class="tip">{inline(s)}</div>'); pub.append(s)
        elif s.startswith("⚠️"):
            out.append(f'<div class="pit">{inline(s)}</div>'); pub.append(s)
        elif s.startswith("【可以直接抄】"):
            body = [s.replace("【可以直接抄】", "", 1).strip()]
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^(【|##|★|💡|⚠️|👇|\|)", lines[i + 1].strip()):
                i += 1
                body.append(lines[i].rstrip())
            txt = "\n".join(x for x in body if x)
            out.append(f'<div class="copy"><div class="cap">【可以直接抄】</div>{html.escape(txt)}</div>')
            pub.append("【可以直接抄】" + ("\n" if "\n" in txt else "") + txt)
        elif MEDIA_RE.match(s):
            kind, rest = MEDIA_RE.match(s).groups()
            parts = [x.strip() for x in rest.split("｜") if x.strip()]
            cap = parts[0] if parts else ""
            more = "<br>".join(html.escape(x) for x in parts[1:])
            out.append(f'<div class="media"><div class="cap">👇 {kind}：{html.escape(cap)}</div>{more}</div>')
            pub.append(f"👇 {cap}" + (f"（{kind}位：{'；'.join(parts[1:])}）" if parts[1:] else ""))
        else:
            out.append(f"<div{attr}><p>{inline(s)}</p></div>"); pub.append(s)
        i += 1
    page = (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{html.escape(title or '长文排版')}</title><style>{CSS}</style></head><body class=\"write\"><div class=\"wrap\">"
            '<div class="bar"><button id="bw" class="on" onclick="v(1)">写作视图（标出钩子、论点、槽点、图片位）</button>'
            '<button id="bp" onclick="v(0)">发布视图（读者看到的）</button></div>'
            + (f"<h1>{inline(title)}</h1>" if title else "") + (f'<div class="sub">{html.escape(sub)}</div>' if sub else "")
            + "".join(out)
            + '<div class="legend note">写作视图图例：<span style="background:var(--hook)"></span>钩子<span style="background:var(--point)"></span>论点'
              '<span style="background:var(--proof)"></span>证据<span style="background:var(--slot)"></span>槽点<span style="background:var(--media)"></span>图片／视频／图表位'
              '<span style="background:var(--save)"></span>收藏件　·　<mark>黄底</mark>＝重点句　<span class="num">红字</span>＝数字</div>'
            f"</div><script>{JS}</script></body></html>")
    return page, re.sub(r"==(.+?)==", r"**\1**", "\n\n".join(pub)) + "\n"  # 平台不认 ==，发布版改成加粗


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    src = argv[0]
    text = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")
    dest = Path(argv[argv.index("-o") + 1]) if "-o" in argv else (Path("长文排版.html") if src == "-" else Path(src).with_suffix(".html"))
    page, pub = render(text)
    dest.write_text(page, encoding="utf-8")
    pubf = dest.with_name(dest.stem + "-发布版.md")
    pubf.write_text(pub, encoding="utf-8")
    print(f"排版网页：{dest}\n发布版文字：{pubf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

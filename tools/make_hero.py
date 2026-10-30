"""把底图做成 1600×640 的首页主视觉，并叠上标题（标题、系列、成员一行、出品方都在 config.json 的 hero、brand）。只用标准库，靠本机的 Chrome 无界面模式排版截图。
用法：python3 tools/make_hero.py <底图> [输出=assets/hero.png]"""
import base64
import subprocess
import sys
import tempfile
from pathlib import Path

W, H = 1600, 640
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BRAND, CONFIG  # noqa: E402

TITLE, EN, SUB, CREW = (CONFIG["hero"][k] for k in ("标题", "英文", "副标题", "成员"))


def main(src, out="assets/hero.png"):
    data = base64.b64encode(Path(src).read_bytes()).decode()
    mime = "image/png" if src.lower().endswith(".png") else "image/jpeg"
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#cfe0ea}}
.bg{{position:absolute;inset:0;background:url(data:{mime};base64,{data}) center/101.5% auto no-repeat}}
.fog{{position:absolute;left:330px;top:-40px;width:940px;height:330px;border-radius:50%;
 background:radial-gradient(closest-side,rgba(255,255,255,.62),rgba(255,255,255,0));}}
.t{{position:absolute;top:48px;width:100%;text-align:center;font-family:"Songti SC","STSong","Noto Serif CJK SC",serif;
 font-weight:900;font-size:132px;letter-spacing:28px;color:#1d3c55;text-shadow:0 3px 18px rgba(255,255,255,.9)}}
.e{{position:absolute;top:212px;width:100%;text-align:center;font-family:"Avenir Next","Helvetica Neue",sans-serif;
 font-weight:600;font-size:30px;letter-spacing:18px;color:#2f5674;text-shadow:0 2px 10px rgba(255,255,255,.9)}}
.s{{position:absolute;top:262px;left:50%;transform:translateX(-50%);padding:8px 30px;border-radius:30px;
 background:rgba(255,255,255,.55);font-family:"Songti SC","STSong",serif;font-size:34px;letter-spacing:6px;color:#24445e}}
.c{{position:absolute;top:324px;width:100%;text-align:center;font-family:"Songti SC","STSong",serif;font-size:24px;letter-spacing:5px;color:#2f5674;text-shadow:0 2px 10px rgba(255,255,255,.95)}}
.ai{{position:absolute;right:14px;bottom:10px;font-family:"PingFang SC",sans-serif;font-size:14px;color:rgba(30,50,70,.55)}}
</style></head><body><div class="bg"></div><div class="fog"></div>
<div class="t">{TITLE}</div><div class="e">{EN}</div><div class="s">{SUB}</div><div class="c">{CREW}</div><div class="ai">{BRAND["出品方"]}出品</div></body></html>"""
    with tempfile.TemporaryDirectory() as d:
        page = Path(d) / "hero.html"
        page.write_text(html, encoding="utf-8")
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
                        f"--screenshot={Path(out).resolve()}", page.as_uri()], check=True, capture_output=True)
    print(out, f"{W}×{H}")


if __name__ == "__main__":
    main(*sys.argv[1:])

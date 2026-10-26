"""出一张「拖着调」的网页：底图＋可拖动的图层，主人在浏览器里自己挪、缩放、圈选，导出图片或把改动发回丹青。只用标准库。
用法：python3 调图页.py 底图.png 图层.json -o 调图.html [--title 名字] [--size 750x1000] [--safe x,y,w,h]
图层.json：和 paint-make 的叠图.py 同一个格式（见 paint-make 图类写法卡最后一节）：text、image、rect 三种，
坐标都是占整张图的比例（0～1）。--size 是导出尺寸（照平台规格标准）；不写就用底图原尺寸。
文字图层写了 fontFile（字体文件，相对图层.json）：字体整个嵌进网页，主人电脑没装这款字也照样显示、能双击改字。"""
import argparse
import base64
import json
import mimetypes
from pathlib import Path

HERE = Path(__file__).resolve().parent


def data_uri(p):
    p = Path(p)
    return f"data:{mimetypes.guess_type(p.name)[0] or 'image/png'};base64," + base64.b64encode(p.read_bytes()).decode()


def png_size(p):
    b = Path(p).read_bytes()
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
    i = 2  # JPEG：找 SOF 段
    while i < len(b):
        if b[i] != 0xFF:
            i += 1
            continue
        m, ln = b[i + 1], int.from_bytes(b[i + 2:i + 4], "big")
        if m in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(b[i + 7:i + 9], "big"), int.from_bytes(b[i + 5:i + 7], "big")
        i += 2 + ln
    raise SystemExit(f"读不出图片尺寸：{p}")


def build(base, layers, out, title="", size=None, safe=None):
    w, h = size or png_size(base)
    folder = Path(layers).parent if isinstance(layers, (str, Path)) else Path(".")
    ls = json.loads(Path(layers).read_text(encoding="utf-8")) if isinstance(layers, (str, Path)) else layers
    faces = {}
    for L in ls:
        if L.get("type") == "image" and not str(L.get("src", "")).startswith("data:"):
            L["src"] = data_uri(folder / L["src"])
        if L.get("type") == "text" and L.get("fontFile"):
            f = folder / L.pop("fontFile")
            L["font"] = L.get("font") or f.stem
            fmt = {".otf": "opentype", ".woff2": "woff2", ".woff": "woff"}.get(f.suffix.lower(), "truetype")
            faces[L["font"]] = f'@font-face{{font-family:"{L["font"]}";src:url(data:font/{f.suffix.lower()[1:]};base64,{base64.b64encode(f.read_bytes()).decode()}) format("{fmt}")}}'

    d = {"title": title, "width": w, "height": h, "base": data_uri(base), "layers": ls}
    if safe:
        d["safe"] = dict(zip("xywh", safe))
    page = (HERE / "调图模板.html").read_text(encoding="utf-8").replace("__DATA__", json.dumps(d, ensure_ascii=False).replace("</", "<\\/"))
    if faces:
        page = page.replace("</style>", "\n".join(faces.values()) + "\n</style>", 1)
    Path(out).write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("layers")
    ap.add_argument("-o", "--out", default="调图.html")
    ap.add_argument("--title", default="")
    ap.add_argument("--size")
    ap.add_argument("--safe")
    a = ap.parse_args()
    size = tuple(int(x) for x in a.size.lower().split("x")) if a.size else None
    safe = [float(x) for x in a.safe.split(",")] if a.safe else None
    print(build(a.base, a.layers, a.out, a.title, size, safe))

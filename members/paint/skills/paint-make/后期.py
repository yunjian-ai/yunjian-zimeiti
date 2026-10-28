"""丹青后期：把模型画好的底图交给 PhotoCraft（开源、免费的 Photoshop 式软件）做精确后期——字、价格、角标、圆框、
多颜色、批量、调色、去小瑕疵、白底抠图、放大，出 PNG／JPG，要的话再出能在 Photoshop 里改字的 PSD。只用标准库。
要做什么、不做什么见同目录 `后期卡.md`。找不到也装不上 PhotoCraft：退出码 3，改用 `叠图.py`。

用法（路径都可以是相对路径）：
  python3 后期.py 装                                       找到或下载 PhotoCraft 命令行和中文字体，打印路径
  python3 后期.py 排版 底.jpg 图层.json -o 成品.png [--psd 成品.psd]
  python3 后期.py 批量 底.jpg 图层.json 数据.csv -o 目录 [--psd]   数据第一列「文件名」，其余列名是图层 id，值换掉那层的字（.png/.jpg 结尾换图）
  python3 后期.py 换色 商品透明.png -o 目录 --色 燕麦=32,28,-12 [--色 雾蓝=212,22,-8] [--留深色 130] [--保护 x,y,w,h …]
                                                           色相 0～360、饱和 0～100、明暗 -100～100；--留深色 让扣子这类深色不变（首选）；
                                                           --保护 的框里整块不变（框边会留一条原色，只用在 logo、吊牌这种本来就是一块的地方）
  python3 后期.py 调色 图.jpg -o 出.jpg [--暖 25] [--亮 0.3] [--鲜 20] [--清晰 10]
  python3 后期.py 去瑕疵 图.png --框 x,y,w,h [--框 …] -o 出.png       像素坐标，框住要抹掉的小东西（领标、线头、污点）
  python3 后期.py 抠白底 图.png -o 透明.png [--底色 #D9C7B0]          只用于白底商品图；有背景的照片别用
  python3 后期.py 放大 图.png -o 出.png [--倍 2]
退出码：0 成功；1 出错或自检没过（会说哪一处）；3 没有 PhotoCraft（改用叠图.py）。"""
import argparse
import base64
import csv
import hashlib
import json
import os
import platform
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "0.16.0"
BASE = f"https://github.com/storytold/photocraft/releases/download/v{VERSION}/"
PACKS = {  # 平台 → (官方包名, SHA256, 包里命令行的相对路径)；校验值抄自官方 SHA256SUMS.txt
    ("Darwin", "any"): (f"photocraft-cli-{VERSION}-macos-universal.zip",
                        "ecc6e0aee7990538c99dfcccee989066777ec16cb90d6b2c9e5b136e5c60ae92",  # pragma: allowlist secret（官方 SHA256 校验值，不是密钥）
                        f"photocraft-cli-{VERSION}-macos-universal/photocraft-cli"),
    ("Linux", "x86_64"): (f"photocraft-{VERSION}-linux-x86_64.tar.gz",
                          "7c17f3633ebf7dabf27628e2d2637d918c7c2a5b163b8b90347a78acddf63608",  # pragma: allowlist secret（官方 SHA256 校验值，不是密钥）
                          f"photocraft-{VERSION}-linux-x86_64/bin/photocraft-cli"),
    ("Linux", "aarch64"): (f"photocraft-{VERSION}-linux-aarch64.tar.gz",
                           "9b998376a4876a620842f0456f79695b147950d6f173930ee4d5da751303e10b",  # pragma: allowlist secret（官方 SHA256 校验值，不是密钥）
                           f"photocraft-{VERSION}-linux-aarch64/bin/photocraft-cli"),
    ("Windows", "AMD64"): (f"photocraft-{VERSION}-windows-x64-portable.zip",
                           "3e634f7e3cc95476c369d59ef0cfed3d1dd6fafd3c351ad81a4ddf3bd792e99d",  # pragma: allowlist secret（官方 SHA256 校验值，不是密钥）
                           "photocraft-cli.exe"),
}
HOME = Path.home() / ".yunjian" / "paint"
TOOL_DIR, FONT_DIR = HOME / "工具", HOME / "字体"
CJK_FONTS = {  # 丹青要的中文字体：没有就从官方仓库的镜像下（开源 OFL）
    "NotoSansSC-Bold.otf": "https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@main/Sans/SubsetOTF/SC/NotoSansSC-Bold.otf",
    "NotoSansSC-Black.otf": "https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@main/Sans/SubsetOTF/SC/NotoSansSC-Black.otf",
}
FAMILIES = {  # 图层里写的字体名 → PhotoCraft 里依次找这些字族
    "思源黑体": ["Source Han Sans SC", "Noto Sans SC", "Noto Sans CJK SC", "PingFang SC", "Hiragino Sans GB"],
    "思源宋体": ["Source Han Serif SC", "Noto Serif SC", "Noto Serif CJK SC", "Songti SC"],
    "阿里巴巴普惠体": ["Alibaba PuHuiTi", "AlibabaPuHuiTi", "Noto Sans SC", "Noto Sans CJK SC", "PingFang SC"],
    "Anton": ["Anton"], "Bebas Neue": ["Bebas Neue"], "Barlow Condensed": ["Barlow Condensed"],
}
DEFAULT_FONT = "思源黑体"
WEIGHTS = {"regular": 400, "normal": 400, "medium": 500, "bold": 700, "heavy": 900, "black": 900}


# ───────── 装 ─────────
def find_cli():
    for c in (os.environ.get("PHOTOCRAFT_CLI"), shutil.which("photocraft-cli")):
        if c and Path(c).exists():
            return Path(c)
    hits = sorted(TOOL_DIR.rglob("photocraft-cli*")) if TOOL_DIR.exists() else []
    hits = [h for h in hits if h.is_file() and h.suffix in ("", ".exe")]
    return hits[0] if hits else None


def download(url, dest, sha=None):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "yunjian-paint"})
    h = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total, got, step = int(r.headers.get("Content-Length") or 0), 0, 0
        while True:
            block = r.read(1 << 20)
            if not block:
                break
            f.write(block)
            h.update(block)
            got += len(block)
            if total and got * 10 // total > step:
                step = got * 10 // total
                print(f"  下载 {dest.name} {step * 10}%", flush=True)
    if sha and h.hexdigest() != sha:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"{dest.name} 校验值对不上（可能下载不全或被改过），已删掉")
    tmp.replace(dest)
    return dest


def install_cli():
    sysname, arch = platform.system(), platform.machine()
    pack = PACKS.get((sysname, "any")) or PACKS.get((sysname, arch))
    if not pack:
        raise RuntimeError(f"PhotoCraft 没有 {sysname} {arch} 的命令行包")
    name, sha, inner = pack
    archive = download(BASE + name, TOOL_DIR / name, sha)
    out = TOOL_DIR / name.replace(".tar.gz", "").replace(".zip", "")
    if name.endswith(".zip"):
        if sysname == "Darwin" and shutil.which("ditto"):
            subprocess.run(["ditto", "-x", "-k", str(archive), str(TOOL_DIR)], check=True)
        else:
            with zipfile.ZipFile(archive) as z:
                z.extractall(out if inner.count("/") == 0 else TOOL_DIR)
    else:
        with tarfile.open(archive) as t:
            t.extractall(TOOL_DIR, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    cli = (out / inner) if inner.count("/") == 0 else (TOOL_DIR / inner)
    cli.chmod(0o755)
    archive.unlink(missing_ok=True)
    return cli


def user_font_dir():
    s = platform.system()
    if s == "Darwin":
        return Path.home() / "Library" / "Fonts"
    if s == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Microsoft" / "Windows" / "Fonts"
    return Path.home() / ".fonts"


def font_name(path):
    """读字体文件 name 表：返回 (字族, 字重名)。优先 16/17（排版字族），没有用 1/2。"""
    data = Path(path).read_bytes()
    if data[:4] == b"ttcf":
        data_off = struct.unpack(">I", data[12:16])[0]
    else:
        data_off = 0
    num = struct.unpack(">H", data[data_off + 4:data_off + 6])[0]
    for i in range(num):
        rec = data_off + 12 + 16 * i
        if data[rec:rec + 4] == b"name":
            off = struct.unpack(">I", data[rec + 8:rec + 12])[0]
            break
    else:
        return None, None
    count, sto = struct.unpack(">HH", data[off + 2:off + 6])
    names = {}
    for i in range(count):
        pid, eid, lid, nid, ln, so = struct.unpack(">HHHHHH", data[off + 6 + 12 * i:off + 18 + 12 * i])
        raw = data[off + sto + so:off + sto + so + ln]
        text = raw.decode("utf-16-be", "ignore") if pid in (0, 3) else raw.decode("latin-1", "ignore")
        if nid not in names or (pid == 3 and lid in (0x409, 0x804)):
            names[nid] = text
    return names.get(16) or names.get(1), names.get(17) or names.get(2)


def install_font(path):
    d = user_font_dir()
    d.mkdir(parents=True, exist_ok=True)
    target = d / Path(path).name
    if not target.exists():
        shutil.copy2(path, target)
        if shutil.which("fc-cache"):
            subprocess.run(["fc-cache", "-f", str(d)], capture_output=True)
    return target


def ensure_cjk_font(families):
    if any(f in families for f in FAMILIES["思源黑体"]):
        return False
    for fname, url in CJK_FONTS.items():
        p = FONT_DIR / fname
        if not p.exists():
            download(url, p)
        install_font(p)
    return True


def cmd_install(_a):
    cli = find_cli()
    if not cli:
        print("没找到 PhotoCraft，从官方发布页下载（约 70～90 MB，下完对校验值）…", flush=True)
        try:
            cli = install_cli()
        except Exception as e:  # noqa: BLE001 网络、平台、权限都可能
            print(f"NO_TOOL 装不上 PhotoCraft：{e}。这一单改用 叠图.py")
            return 3
    ver = subprocess.run([str(cli), "--version"], capture_output=True, text=True).stdout.strip()
    with Engine(cli, Path(tempfile.gettempdir())) as e:
        fams = e.families()
    if ensure_cjk_font(fams):
        print("已装中文字体 Noto Sans SC（粗、特粗）")
    print(f"OK PhotoCraft｜{ver}｜{cli}")
    return 0


# ───────── 引擎：PhotoCraft 的 MCP（无界面），读写只限一个临时文件夹 ─────────
class Engine:
    def __init__(self, cli, root):
        self.cli, self.root, self.n, self.styled = str(cli), str(root), 0, set()

    def __enter__(self):
        self.p = subprocess.Popen([self.cli, "mcp", "--automation-read-root", self.root, "--automation-write-root", self.root],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "yunjian-paint", "version": "1"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self

    def __exit__(self, *exc):
        self.p.terminate()

    def _send(self, msg):
        self.p.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.p.stdin.flush()

    def _rpc(self, method, params):
        self.n += 1
        self._send({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params})
        line = self.p.stdout.readline()
        if not line:
            raise RuntimeError("PhotoCraft 没有回应（进程退出了）")
        r = json.loads(line)
        if "error" in r:
            raise RuntimeError(f"{method}: {r['error']}")
        return r["result"]

    def tool(self, _name, **args):
        res = self._rpc("tools/call", {"name": _name, "arguments": args})
        texts = [c["text"] for c in res.get("content", []) if c["type"] == "text"]
        if res.get("isError"):
            raise RuntimeError(f"{_name}: {' '.join(texts)[:300]}")
        imgs = [c["data"] for c in res.get("content", []) if c["type"] == "image"]
        if imgs:
            return base64.b64decode(imgs[0])
        try:
            return json.loads(texts[0]) if texts else None
        except json.JSONDecodeError:
            return texts[0]

    def cmd(self, cid, **params):
        return self.tool("command_run", id=cid, params=params)

    def style(self, layer, sid, **params):
        """给一层加图层样式：第一种不带 add，后面的带 add，不把前面的冲掉。"""
        self.cmd("layer.select", layer=layer)
        self.cmd(sid, **params, **({"add": True} if layer in self.styled else {}))
        self.styled.add(layer)

    def families(self):
        self.tool("doc_new", width=8, height=8)
        fams = self.cmd("type.fonts").get("families", [])
        self.tool("doc_close")
        return fams

    def layers(self):
        out = []

        def walk(ls):
            for L in ls:
                out.append(L)
                walk(L.get("children", []))
        walk(self.tool("doc_inspect")["layers"])
        return out


def need_cli():
    cli = find_cli()
    if not cli:
        print("NO_TOOL 没有 PhotoCraft：先跑 `python3 后期.py 装`；装不上就用 叠图.py")
    return cli


class Work:
    """临时工作夹：输入复制进来、输出写在里面，做完挪到目标位置。主人的其他文件 PhotoCraft 碰不到。"""

    def __enter__(self):
        self.d = Path(tempfile.mkdtemp(prefix="丹青后期-"))
        self.k = 0
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.d, ignore_errors=True)

    def bring(self, src):
        self.k += 1
        dst = self.d / f"in{self.k}{Path(src).suffix.lower()}"
        shutil.copy2(src, dst)
        return str(dst)

    def out(self, target):
        self.k += 1
        return str(self.d / f"out{self.k}{Path(target).suffix.lower()}")

    @staticmethod
    def deliver(tmp, target):
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(tmp, target)


# ───────── 排版 ─────────
def hexc(c, default="#000000"):
    c = (c or default).strip()
    return c if c.startswith("#") else "#" + c


def pick_family(name, fams):
    for f in FAMILIES.get(name or DEFAULT_FONT, [name] if name else []) + FAMILIES[DEFAULT_FONT]:
        if f in fams:
            return f
    return None


def put_text(e, L, box, fams, folder, warns):
    x, y, w, h = box
    style = {}
    if L.get("fontFile"):
        fam, sty = font_name(folder / L["fontFile"])
        install_font(folder / L["fontFile"])
        style.update(font=fam, fontStyle=sty)
    else:
        fam = pick_family(L.get("font"), fams)
        if not fam:
            raise RuntimeError("NO_FONT 找不到中文字体：先跑 `python3 后期.py 装`")
        style["font"] = fam
        if L.get("weight"):
            style["weight"] = WEIGHTS.get(str(L["weight"]).lower(), 700)
    style["color"] = hexc(L.get("color"))
    if L.get("spacing"):
        style["tracking"] = int(L["spacing"])
    if L.get("strike"):
        style["strikethrough"] = True
    vertical = L.get("vertical")
    size = max(6.0, min(h if not vertical else w, 1296) * 0.8)
    text = L.get("text", "")
    if vertical:
        r = e.cmd("type.create", x=x + w / 2, y=y + size, text=text, size=size, orientation="vertical", name=L.get("id", "字"), **style)
    else:
        r = e.cmd("type.create", box=[x, y, w, max(h * 6, 400)], text=text, size=size, align=L.get("align", "center"),
                  name=L.get("id", "字"), **style)
    lid = r["layer"]
    if L.get("leading"):
        e.cmd("type.setStyle", layer=lid, leading=float(L["leading"]))
    for _ in range(40):  # 缩到框里放得下（宽高都不超）
        b = e.cmd("type.info", layer=lid)["bounds"]
        if (b[3] - b[1]) <= h + 1 and (b[2] - b[0]) <= w + 1:
            break
        size *= 0.92
        e.cmd("type.setStyle", layer=lid, size=round(size, 2))
    else:
        warns.append(f"图层「{L.get('id')}」框太小，字放不下")
    if L.get("curve"):
        e.cmd("type.warpText", layer=lid, style="arc", bend=max(-100, min(100, int(L["curve"]))))
    b = e.cmd("type.info", layer=lid)["bounds"]
    dx = (x + (w - (b[2] - b[0])) / 2 - b[0]) if (vertical or L.get("curve")) else 0
    dy = (y + (h - (b[3] - b[1])) / 2 - b[1]) if L.get("middle", True) else (y - b[1])
    e.cmd("type.edit", layer=lid, move=[round(dx, 2), round(dy, 2)])
    return lid


def put_image(e, L, box, folder, work):
    x, y, w, h = box
    src = work.bring(folder / L["src"])
    r = e.tool("doc_place", path=src, center=[x + w / 2, y + h / 2], scale=100, fit=False)
    lid, b = r["layer"], r["bounds"]
    iw, ih = b[2] - b[0], b[3] - b[1]
    shape = L.get("shape")
    s = (max if (shape or L.get("cover")) else min)(w / iw, h / ih) * 100
    if abs(s - 100) > 0.01:
        e.cmd("edit.transform", layer=lid, scaleX=s, scaleY=s)
    if shape == "circle":
        lid = e.cmd("layer.new.frame", x=round(x), y=round(y), width=round(w), height=round(h), shape="ellipse", layer=lid,
                    name=L.get("id", "圆框"))["layer"]
    elif shape == "round":
        clip = e.cmd("shape.create", kind="roundedRect", rect=[x, y, w, h], radii=L.get("radius", min(w, h) * 0.12), fill="#000000",
                     name=L.get("id", "圆角框"))["layer"]
        e.cmd("layer.moveTo", layer=clip, target=lid, position="below")
        e.cmd("layer.createClippingMask", layer=lid)
    return lid


def put_shape(e, L, box):
    x, y, w, h = box
    t = L.get("type")
    fill = None if L.get("fill") is False else hexc(L.get("color"))
    if L.get("gradient"):
        g = L["gradient"]
        fill = {"gradient": {"stops": [[i / (len(g) - 1), c] for i, c in enumerate(g)], "angle": L.get("angle", -90), "style": "linear"}}
    stroke = None
    if L.get("stroke"):
        st = L["stroke"]
        stroke = {"width": st.get("width", 3), "color": hexc(st.get("color")), "align": "inside"}
        if st.get("dash"):
            stroke["dashes"] = [3, 2]
    name = L.get("id", t)
    if t in ("burst", "star"):
        if t == "burst":
            lid = e.cmd("shape.presets.place", preset="Burst", rect=[x, y, w, h], keepAspect=False, fill=fill, name=name)["layer"]
        else:
            lid = e.cmd("shape.create", kind="star", rect=[x, y, w, h], sides=int(L.get("points", 5)), starRatio=0.5, fill=fill,
                        stroke=stroke, name=name)["layer"]
    else:
        kind = "ellipse" if t == "ellipse" else ("roundedRect" if L.get("radius") else "rect")
        args = dict(kind=kind, rect=[x, y, w, h], fill=fill, stroke=stroke, name=name)
        if kind == "roundedRect":
            args["radii"] = L["radius"] * min(w, h) if L["radius"] <= 1 else L["radius"]
        lid = e.cmd("shape.create", **args)["layer"]
        if L.get("notch"):  # 优惠券：左右两边各挖一个半圆缺口
            r = min(h * 0.16, w * 0.08)
            for cx in (x, x + w):
                e.cmd("shape.create", kind="ellipse", rect=[cx - r, y + h / 2 - r, 2 * r, 2 * r], addTo=lid, op="subtract")
            e.cmd("layer.combineShapes.mergeShapeComponents", layer=lid)
    if L.get("rotate"):
        e.cmd("edit.transform", layer=lid, rotate=float(L["rotate"]))
    return lid


BLEND = {"正片叠底": "Multiply", "滤色": "Screen", "叠加": "Overlay", "柔光": "Soft Light", "正常": "Normal"}


def effects(e, lid, L):
    if L.get("opacity") not in (None, 1, 1.0):
        e.cmd("layer.setProps", layer=lid, opacity=float(L["opacity"]))
    if L.get("blend"):  # 印花贴回衣服用正片叠底，吃到褶皱和光影（后期卡第四节）
        e.cmd("layer.setProps", layer=lid, blend=BLEND.get(L["blend"], L["blend"]))
    if L.get("type") == "text" and L.get("gradient"):
        g = L["gradient"]
        e.style(lid, "layer.layerStyle.gradientOverlay", **{"from": hexc(g[0]), "to": hexc(g[-1]), "angle": L.get("angle", 0), "style": "linear"})
    if L.get("outline"):  # 字或图的描边（形状的边用 stroke）
        o = L["outline"]
        e.style(lid, "layer.layerStyle.stroke", size=o.get("width", 3), position="outside", color=hexc(o.get("color"), "#FFFFFF"))
    if L.get("shadow"):
        s = L["shadow"] if isinstance(L["shadow"], dict) else {}
        e.style(lid, "layer.layerStyle.dropShadow", color=hexc(s.get("color")), opacity=s.get("opacity", 35), angle=s.get("angle", 120),
                distance=s.get("distance", 6), size=s.get("size", 12))
    if L.get("glow"):
        g = L["glow"] if isinstance(L["glow"], dict) else {}
        e.style(lid, "layer.layerStyle.outerGlow", color=hexc(g.get("color"), "#FFFFFF"), opacity=g.get("opacity", 75), size=g.get("size", 20))
    if L.get("type") == "text" and L.get("rotate"):
        e.cmd("edit.transform", layer=lid, rotate=float(L["rotate"]))


def compose(e, work, base, layers, folder, outs, fams):
    """在已开的引擎里排一张：返回 (警告, 自检问题)。outs: [(临时输出, 目标)]。"""
    d = e.tool("doc_open", path=work.bring(base))
    W, H = d["width"], d["height"]
    e.cmd("layer.new.layerFromBackground")
    warns, want = [], {}
    for L in layers:
        box = [L.get(k, 0) * s for k, s in (("x", W), ("y", H), ("w", W), ("h", H))]
        t = L.get("type")
        if t == "text":
            lid = put_text(e, L, box, fams, folder, warns)
            want[lid] = L.get("text", "")
        elif t == "image":
            lid = put_image(e, L, box, folder, work)
        elif t in ("rect", "ellipse", "burst", "star"):
            lid = put_shape(e, L, box)
        else:
            warns.append(f"图层「{L.get('id')}」类型「{t}」不认识，跳过")
            continue
        effects(e, lid, L)
        x, y, w, h = box
        if t not in ("rect",) and (x < 0.04 * W - 1 or y < 0.04 * H - 1 or x + w > 0.96 * W + 1 or y + h > 0.96 * H + 1):
            warns.append(f"图层「{L.get('id')}」离边缘不到 4%，可能被裁、被截断")
    # 自检：读回每个文字层，和图层.json 一字不差；尺寸不变
    probs = []
    for lid, text in want.items():
        got = e.cmd("type.info", layer=lid).get("text", "")
        if got.replace("\r", "\n") != text.replace("\r", "\n"):
            probs.append(f"文字层读回不一致：要「{text}」，实际「{got}」")
    d2 = e.tool("doc_inspect")
    if (d2["width"], d2["height"]) != (W, H):
        probs.append(f"尺寸变了：{W}x{H} → {d2['width']}x{d2['height']}")
    for tmp, _target in outs:
        e.tool("doc_save", path=tmp)
    e.tool("doc_close")
    return warns, probs, (W, H)


def load_layers(path):
    layers = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(layers, list):
        raise SystemExit("图层.json 要是一个列表（见图类写法卡最后一节）")
    return layers


def cmd_compose(a):
    cli = need_cli()
    if not cli:
        return 3
    layers = load_layers(a.layers)
    with Work() as wk, Engine(cli, wk.d) as e:
        fams = e.families()
        targets = [a.out] + ([a.psd] if a.psd else [])
        outs = [(wk.out(t), t) for t in targets]
        warns, probs, (W, H) = compose(e, wk, a.base, layers, Path(a.layers).parent, outs, fams)
        for tmp, t in outs:
            Work.deliver(tmp, t)
    for w in warns:
        print("⚠️", w)
    for p in probs:
        print("❌", p)
    print(("OK " if not probs else "没过 ") + "｜".join([*targets, f"{W}x{H}", f"{len(layers)} 层"]))
    return 1 if probs else 0


def cmd_batch(a):
    cli = need_cli()
    if not cli:
        return 3
    base_layers = load_layers(a.layers)
    folder = Path(a.layers).parent
    rows = list(csv.DictReader(open(a.data, encoding="utf-8-sig")))
    bad = 0
    with Work() as wk, Engine(cli, wk.d) as e:
        fams = e.families()
        for row in rows:
            name = (row.pop("文件名", "") or "").strip()
            if not name:
                continue
            layers = json.loads(json.dumps(base_layers))
            for L in layers:
                v = row.get(L.get("id"))
                if v is None or v == "":
                    continue
                if v.lower().endswith((".png", ".jpg", ".jpeg")):
                    L["src"] = str((Path(a.data).parent / v).resolve())
                else:
                    L["text"] = v
            target = str(Path(a.out) / (name if Path(name).suffix else name + ".png"))
            targets = [target] + ([str(Path(target).with_suffix(".psd"))] if a.psd else [])
            outs = [(wk.out(t), t) for t in targets]
            warns, probs, _ = compose(e, wk, a.base, layers, folder, outs, fams)
            for tmp, t in outs:
                Work.deliver(tmp, t)
            bad += bool(probs)
            print(("OK " if not probs else "没过 ") + target + "".join(f"｜⚠️{w}" for w in warns) + "".join(f"｜❌{p}" for p in probs))
    print(f"批量 {len(rows)} 行，没过 {bad} 张")
    return 1 if bad else 0


# ───────── 单张处理 ─────────
def one(a, steps, out=None):
    """打开一张图 → 按 steps 动手 → 存。steps(e, info) 返回附加说明。"""
    cli = need_cli()
    if not cli:
        return 3
    out = out or a.out
    with Work() as wk, Engine(cli, wk.d) as e:
        info = e.tool("doc_open", path=wk.bring(a.image))
        note = steps(e, info) or ""
        tmp = wk.out(out)
        e.tool("doc_save", path=tmp)
        d = e.tool("doc_inspect")
        Work.deliver(tmp, out)
    print(f"OK {out}｜{d['width']}x{d['height']}{('｜' + note) if note else ''}")
    return 0


def rect4(s):
    v = [float(x) for x in s.replace("，", ",").split(",")]
    if len(v) != 4:
        raise argparse.ArgumentTypeError("框写 x,y,w,h 四个数")
    return v


def cmd_recolor(a):
    cli = need_cli()
    if not cli:
        return 3
    Path(a.out).mkdir(parents=True, exist_ok=True)
    with Work() as wk, Engine(cli, wk.d) as e:
        src = wk.bring(a.image)
        for spec in a.color:
            name, _, nums = spec.partition("=")
            hue, sat, light = (float(x) for x in nums.replace("，", ",").split(","))
            e.tool("doc_open", path=src)
            base = e.layers()[0]["id"]
            if a.protect:  # 保护的框不变色：选区＝全图减去这些框，调整层只作用在选区里
                e.cmd("select.all")
                for x, y, w, h in a.protect:
                    e.cmd("select.rect", x=round(x), y=round(y), width=round(w), height=round(h), mode="subtract")
            e.cmd("layer.select", layer=base)
            adj = e.cmd("layer.newAdjustmentLayer.hueSaturation", colorize=True, hue=hue, saturation=sat, lightness=light)
            adj = adj["layer"] if isinstance(adj, dict) and "layer" in adj else e.tool("doc_inspect")["activeLayer"]
            e.cmd("layer.createClippingMask", layer=adj)
            if a.keep_dark:  # 深色（扣子、深色印花）不变色：混合选项里「下一图层」暗于这个亮度的地方不吃调整，过渡 30 级
                k = max(1, min(225, int(a.keep_dark)))
                e.cmd("layer.layerStyle.blendingOptions", layer=adj, blendIf={"channel": "gray", "underlying": [k, k + 30, 255, 255]})
            target = str(Path(a.out) / f"{name}.png")
            tmp = wk.out(target)
            e.tool("doc_save", path=tmp)
            e.tool("doc_close")
            Work.deliver(tmp, target)
            print(f"OK {target}")
    return 0


def cmd_tone(a):
    p = {k: v for k, v in (("temperature", a.暖), ("exposure", a.亮), ("vibrance", a.鲜), ("clarity", a.清晰)) if v}
    if not p:
        print("没给调什么（--暖 --亮 --鲜 --清晰）")
        return 1
    return one(a, lambda e, _i: e.cmd("filter.cameraRaw", **p) and None)


def cmd_spot(a):
    def steps(e, _i):
        strokes = [[[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]] for x, y, w, h in a.框]
        size = max(6, min(min(w, h) for _x, _y, w, h in a.框) / 2)
        r = e.cmd("paint.remove", strokes=strokes, size=round(size), closeLoops=True)
        return f"抹了 {len(a.框)} 处" + (f"（{r.get('damage')}）" if isinstance(r, dict) else "")
    return one(a, steps)


def cmd_cutout(a):
    def steps(e, info):
        W, H = info["width"], info["height"]
        e.cmd("layer.new.layerFromBackground")
        for i, (x, y) in enumerate([(2, 2), (W - 3, 2), (2, H - 3), (W - 3, H - 3)]):
            e.cmd("select.magicWand", x=x, y=y, tolerance=18, contiguous=True, mode="replace" if i == 0 else "add")
        e.cmd("select.modify.expand", by=1)
        e.cmd("edit.clear")
        e.cmd("select.deselect")
        if a.底色:
            e.cmd("layer.new.layer", name="底色")
            e.cmd("edit.fill", contents="color", color=hexc(a.底色))
            e.cmd("layer.arrange.sendToBack")
        return "换了底色 " + a.底色 if a.底色 else "透明底"
    return one(a, steps)


def cmd_upscale(a):
    def steps(e, _i):
        e.cmd("image.imageSize", percent=float(a.倍) * 100, resample="preserveDetails")
        e.cmd("filter.sharpen.smartSharpen", amount=60, radius=1)
    return one(a, steps)


def main(argv=None):
    ap = argparse.ArgumentParser(description="丹青后期（PhotoCraft）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("装")
    p = sub.add_parser("排版")
    p.add_argument("base")
    p.add_argument("layers")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--psd")
    p = sub.add_parser("批量")
    p.add_argument("base")
    p.add_argument("layers")
    p.add_argument("data")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--psd", action="store_true")
    p = sub.add_parser("换色")
    p.add_argument("image")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--色", dest="color", action="append", required=True)
    p.add_argument("--保护", dest="protect", action="append", type=rect4, default=[])
    p.add_argument("--留深色", dest="keep_dark", type=float, default=0, help="比这个亮度（0～255）暗的地方不变色；胡桃木扣这类中深色一般 130，黑扣 70")
    p = sub.add_parser("调色")
    p.add_argument("image")
    p.add_argument("-o", "--out", required=True)
    for k in ("暖", "亮", "鲜", "清晰"):
        p.add_argument(f"--{k}", type=float, default=0)
    p = sub.add_parser("去瑕疵")
    p.add_argument("image")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--框", action="append", type=rect4, required=True)
    p = sub.add_parser("抠白底")
    p.add_argument("image")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--底色")
    p = sub.add_parser("放大")
    p.add_argument("image")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--倍", type=float, default=2)
    a = ap.parse_args(argv)
    fn = {"装": cmd_install, "排版": cmd_compose, "批量": cmd_batch, "换色": cmd_recolor, "调色": cmd_tone,
          "去瑕疵": cmd_spot, "抠白底": cmd_cutout, "放大": cmd_upscale}[a.cmd]
    try:
        return fn(a)
    except RuntimeError as err:
        msg = str(err)
        print(msg if msg.startswith("NO_") else f"❌ {msg}")
        return 3 if msg.startswith("NO_") else 1


if __name__ == "__main__":
    sys.exit(main())

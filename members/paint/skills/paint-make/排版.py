"""丹青排版出图：字多、版式要准的图（海报、长图、价目表、招募图），照锁死清单排，排完逐条对。做法见同目录 `排版卡.md`。
用法：python3 排版.py <需求单.json> <版式.json> -o <输出文件夹> [--底图 底.png] [--档 自动|基础|升级] [--名 成品]
  需求单里要有「锁死清单」（paint-brief 需求单卡第七节），也可以直接给一份锁死清单。
  版式.json 和 图层.json 一样（图类写法卡最后一节），只是字层不写 text，写 "锁": "<文案 id>"——字从锁死清单取，一字不改。
  --底图 要和锁死的尺寸一样大（先用 交付.py 裁好）；不给就用锁死色值里的「底色」铺一张。
两档（自动选，不替主人装软件）：
  升级版：本机找得到 PhotoCraft（photocraft-cli）→ 交 后期.py 排，出 PSD＋PNG＋JPG，从 PSD 读回每个文字层对锁死清单。
  基础版：没有 PhotoCraft（或 --档 基础）→ 叠图.py 排，出 PNG＋JPG，按排进去的字层对锁死清单。
写 排版回执.json，再跑 paint-check 的锁死清单自检。退出码：0 全对；1 版式或锁死清单不对、自检没过；3 没有 Pillow 也没有 PhotoCraft（改交调图网页）。"""
import argparse
import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "paint-check"))
import 叠图  # noqa: E402
import 后期  # noqa: E402
from check_paint import check_lock, load_lock, png_size  # noqa: E402
from check_brief import check_lock_list  # noqa: E402  check_paint 已把 paint-brief 加进路径


def resolve(layers, lock):
    """版式里的字层换成锁死原文；查漏项、没锁的字、不在色值里的颜色。返回 (图层, 问题)。"""
    text = {it["id"]: it["原文"] for it in lock["文案"]}
    allowed = {v.lower() for v in lock["色值"].values()}
    out, errs, used = [], [], set()
    for i, L in enumerate(layers, 1):
        L = dict(L)
        if L.get("type") == "text":
            k = L.get("锁")
            if k is None:
                errs.append(f"版式第 {i} 层是字，却没写「锁」：排版出图的字都要从锁死清单取")
                continue
            if k not in text:
                errs.append(f"版式第 {i} 层锁的「{k}」锁死清单里没有")
                continue
            if "text" in L and L["text"] != text[k]:
                errs.append(f"版式第 {i} 层自己写了字「{L['text']}」，和锁死的「{text[k]}」不一样（删掉 text，只写锁）")
                continue
            L["id"], L["text"] = k, text[k]
            used.add(k)
        if L.get("type") in ("text", "rect") and L.get("color") and L["color"].lower() not in allowed:
            errs.append(f"版式第 {i} 层颜色 {L['color']} 不在锁死的色值里")
        out.append(L)
    for k in text:
        if k not in used:
            errs.append(f"锁死清单的「{k}」版式里没排（漏项）")
    return out, errs


def canvas(path, size, color):
    """没有底图：照锁死尺寸和底色铺一张。"""
    if 叠图.Image:
        叠图.Image.new("RGB", tuple(size), 叠图.hex_rgb(color, (255, 255, 255))).save(path)
        return True
    cli = 后期.find_cli()
    if cli:
        new = json.dumps({"width": size[0], "height": size[1], "background": color})
        return subprocess.run([cli, "run", "--new", new, "--out", str(path)], capture_output=True).returncode == 0
    return False


def to_jpg(png, jpg, cli=None):
    if 叠图.Image:
        with 叠图.Image.open(png) as im:
            im.convert("RGB").save(jpg, quality=92)
        return True
    return bool(cli) and subprocess.run([cli, "convert", str(png), str(jpg)], capture_output=True).returncode == 0


def psd_texts(cli, psd):
    """从 PSD 读回文字层：[{id, text}]（升级版自检用读回的，不用自己排进去的）。"""
    r = subprocess.run([cli, "info", "--compact", str(psd)], capture_output=True, text=True)
    out = []

    def walk(ls):
        for L in ls:
            if L.get("kind") == "Type":
                out.append({"id": L.get("name"), "text": (L.get("text") or {}).get("text", "")})
            walk(L.get("children", []))
    walk(json.loads(r.stdout).get("layers", []) if r.returncode == 0 else [])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="丹青排版出图")
    ap.add_argument("brief")
    ap.add_argument("layout")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--底图", dest="base")
    ap.add_argument("--档", dest="tier", choices=["自动", "基础", "升级"], default="自动")
    ap.add_argument("--名", dest="name", default="成品")
    a = ap.parse_args(argv)

    lock = load_lock(a.brief)
    errs = check_lock_list(lock)
    if errs:
        for e in errs:
            print("❌ 锁死清单：", e)
        return 1
    layers, errs = resolve(json.loads(Path(a.layout).read_text(encoding="utf-8")), lock)
    if errs:
        for e in errs:
            print("❌", e)
        return 1

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cli = 后期.find_cli() if a.tier != "基础" else None
    if a.tier == "升级" and not cli:
        print("⚠️ 没装 PhotoCraft，这单交基础版（PNG＋JPG）；要可改的分层文件，主人同意后再装（排版卡第三节）")
    with tempfile.TemporaryDirectory(prefix="丹青排版-") as tmp:
        tmp = Path(tmp)
        lay = tmp / "图层.json"
        for L in layers:  # 贴图的 src 相对版式文件夹，换成绝对路径
            if L.get("type") == "image" and L.get("src"):
                L["src"] = str((Path(a.layout).parent / L["src"]).resolve())
        lay.write_text(json.dumps(layers, ensure_ascii=False, indent=1), encoding="utf-8")
        base = Path(a.base) if a.base else tmp / "底.png"
        if not a.base and not canvas(base, lock["尺寸"], lock["色值"].get("底色") or next(iter(lock["色值"].values()))):
            print("NO_TOOL 没有 Pillow 也没有 PhotoCraft：改交调图网页（paint-adjust），主人在网页里导出")
            return 3
        size = png_size(base)
        if size and list(size) != list(lock["尺寸"]):
            print(f"❌ 底图 {size[0]}x{size[1]}，锁死的是 {lock['尺寸'][0]}x{lock['尺寸'][1]}：先用 交付.py 裁到尺寸")
            return 1
        png, jpg, psd = out / f"{a.name}.png", out / f"{a.name}.jpg", out / f"{a.name}.psd"
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            if cli:
                code = 后期.main(["排版", str(base), str(lay), "-o", str(png), "--psd", str(psd)])
            else:
                code = 叠图.compose(str(base), str(lay), str(png))
        print(log.getvalue().rstrip())
        if code == 3 and cli:  # PhotoCraft 有但缺中文字体之类：退基础版
            print("⚠️ PhotoCraft 排不了，这单交基础版")
            cli = None
            with contextlib.redirect_stdout(log := io.StringIO()):
                code = 叠图.compose(str(base), str(lay), str(png))
            print(log.getvalue().rstrip())
        if code == 3:
            return 3
        files = [png.name] + ([jpg.name] if to_jpg(png, jpg, cli) else []) + ([psd.name] if cli and psd.exists() else [])
        if cli and psd.exists():
            texts, src = psd_texts(cli, psd), "PSD 读回"
        else:  # 基础版：叠图放不下的字会跳过，算漏
            skipped = {w.split("「")[1].split("」")[0] for w in log.getvalue().splitlines() if "放不下" in w and "「" in w}
            texts, src = [{"id": L["id"], "text": L["text"]} for L in layers if L.get("type") == "text" and L["id"] not in skipped], "排进去的字层"
        colors = {L["id"]: L.get("color") for L in layers if L.get("type") == "text"}
        for t in texts:
            t["color"] = colors.get(t["id"])
        rec = {"档": "升级版" if cli and psd.exists() else "基础版", "尺寸": list(size or lock["尺寸"]), "文件": files, "来源": src,
               "文字层": texts, "色块": [{"id": L.get("id"), "color": L.get("color")} for L in layers if L.get("type") == "rect"]}
        (out / "排版回执.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    errs = check_lock(out, lock)
    for e in errs:
        print("❌", e)
    print(("OK " if not errs else "没过 ") + "｜".join([rec["档"], *files, f"{rec['尺寸'][0]}x{rec['尺寸'][1]}", f"{len(texts)} 段字（{src}）"]))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())

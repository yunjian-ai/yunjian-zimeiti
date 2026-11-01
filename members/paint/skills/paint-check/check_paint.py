"""丹青机械自检：一单的成品对平台规格、对需求单（只用标准库读尺寸；查白底四角要 Pillow 或 sips，没有就提醒）。
用法：python3 check_paint.py <作品文件夹> [--brief 需求单.json] [--table 规格表.json]
      python3 check_paint.py <排版出的文件夹> --lock 需求单.json     排版出图：照 排版回执.json 逐条对锁死清单（文案一字不差、价格一个数、色值、尺寸、禁写）
作品文件夹里要有 交付清单.json：[{"文件": "成品-1.jpg", "第几张": 1, "平台": "抖店", "图类": "1:1 主图"}, …]
  同一张图的几个版本（抖音竖、横两版封面；公众号 2.35:1 和 1:1 两裁）写同一个「第几张」，和需求单比张数时只算一张。
查：文件在不在；像素（主人另给了「像素」就必须一样；和丹青默认交付像素不同只提醒，官方规格才是硬的）；比例；不低于官方下限、不超过上限；文件大小；白底四角；
    和需求单比张数——少了、多了（出了单子上没有的图）都算错；规格表里没有的平台和图类（待核）要停下。
有问题打印 ❌ 并以 1 退出；只有提醒（⚠️）照样算过。"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "paint-adjust"))
from 调图页 import png_size  # noqa: E402  只用标准库读 PNG、JPEG 尺寸
sys.path.insert(0, str(HERE.parent / "paint-brief"))
from check_brief import check_lock_list, prices_in  # noqa: E402  锁死清单的格式和价格写法，两边同一份


ALIAS = {"视频封面": "封面"}  # 交付清单里分得更细的图类，对回需求单菜单里的名字
EXTREME = ["最", "第一", "顶级", "极致", "绝对", "100%", "国家级", "唯一", "首选"]
CONTACT = re.compile(r"1[3-9]\d{9}|微信|VX|vx|加V|wx[:：]|二维码|私信领")


def find_table(arg=None):
    for p in ([Path(arg).expanduser()] if arg else []) + [Path.home() / ".yunjian/paint/库/规格表.json", HERE.parents[1] / "库" / "规格表.json"]:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return None


def ratio_of(text):
    a, b = (float(x) for x in text.split(":"))
    return a / b


def check_one(path, spec, want=None):
    """一张图对一条规格。want＝主人另给的像素 [宽, 高]（优先于交付像素）。"""
    errs, warns = [], []
    try:
        w, h = png_size(path)
    except (SystemExit, OSError, IndexError):
        return [f"{path.name}: 读不出尺寸（不是 png/jpg，或文件坏了）"], warns
    if want:  # 主人明确要的像素：对不上就是错
        if want[0] and w != want[0]:
            errs.append(f"{path.name}: 宽 {w}，主人要 {want[0]}")
        if want[1] and h != want[1]:
            errs.append(f"{path.name}: 高 {h}，主人要 {want[1]}")
    else:  # 丹青默认的交付像素是自己定的，不卡人：官方规格满足就只提醒
        d = spec.get("交付") or [None, None]
        if (d[0] and w != d[0]) or (d[1] and h != d[1]):
            warns.append(f"{path.name}: {w}x{h} 不是丹青默认的 {d[0]}x{d[1] or '?'}；官方规格查下来能传")
    r = w / h
    if "比例" in spec and abs(r - ratio_of(spec["比例"])) > 0.01 * ratio_of(spec["比例"]):
        errs.append(f"{path.name}: 比例 {w}:{h} 不是 {spec['比例']}")
    if "比例范围" in spec:
        lo, hi = spec["比例范围"]
        if not lo - 0.005 <= r <= hi + 0.005:
            errs.append(f"{path.name}: 比例 {r:.3f} 不在官方范围 {lo}～{hi}（宽/高）")
    if "最小" in spec:
        mw, mh = spec["最小"]
        short, long_ = (min(w, h), max(w, h)) if "比例范围" in spec else (w, h)
        if short < mw or long_ < mh:
            errs.append(f"{path.name}: {w}x{h} 低于官方下限 {mw}x{mh}")
    if "最大" in spec and (w > spec["最大"][0] or h > spec["最大"][1]):
        errs.append(f"{path.name}: {w}x{h} 超过官方上限 {spec['最大'][0]}x{spec['最大'][1]}")
    if "宽范围" in spec and not spec["宽范围"][0] <= w <= spec["宽范围"][1]:
        errs.append(f"{path.name}: 宽 {w} 不在 {spec['宽范围'][0]}～{spec['宽范围'][1]}")
    if "高上限" in spec and h > spec["高上限"]:
        errs.append(f"{path.name}: 高 {h} 超过 {spec['高上限']}")
    mb = path.stat().st_size / 1024 / 1024
    if spec.get("上限MB") and mb > spec["上限MB"]:
        errs.append(f"{path.name}: {mb:.2f}MB 超过 {spec['上限MB']}MB")
    if spec.get("白底"):
        try:
            sys.path.insert(0, str(HERE.parent / "paint-make"))
            from 交付 import corners
            bad = [c for c in corners(path) if tuple(c[:3]) != (255, 255, 255)]
            if bad:
                errs.append(f"{path.name}: 白底四角不是纯白 {tuple(bad[0][:3])}")
        except Exception:  # 没有 Pillow 也没有 sips
            warns.append(f"{path.name}: 这里查不了白底四角，交付前请用看图核一眼背景是不是纯白")
    if spec.get("官方未定"):
        warns.append(f"{path.name}: 这种图官方没定统一尺寸，像素是丹青默认的，交付时说一句")
    return errs, warns


def check_folder(folder, table, brief=None):
    folder = Path(folder)
    errs, warns = [], []
    lst = folder / "交付清单.json"
    if not lst.exists():
        return [f"{folder.name}: 没有 交付清单.json"], warns
    items = json.loads(lst.read_text(encoding="utf-8"))
    for it in items:
        key = f"{it.get('平台')}|{it.get('图类')}"
        spec = table.get(key)
        f = folder / str(it.get("文件"))
        if spec is None:
            errs.append(f"{it.get('文件')}: 「{key}」规格表里没有（平台待核或图类写错）——先核规格，不交付")
            continue
        if not f.exists():
            errs.append(f"{it.get('文件')}: 文件不在")
            continue
        e, w = check_one(f, spec, it.get("像素"))
        errs += e
        warns += w
    for lay in sorted(folder.glob("图层*.json")):  # 图层上的字：极限词、联系方式只提醒，主人定
        try:
            texts = [L.get("text", "") for L in json.loads(lay.read_text(encoding="utf-8")) if L.get("type") == "text"]
        except (ValueError, AttributeError):
            warns.append(f"{lay.name}: 读不了")
            continue
        for t in texts:
            hit = [w for w in EXTREME if w in t]
            if hit:
                warns.append(f"{lay.name}: 「{t}」里有「{'、'.join(hit)}」——广告法极限词风险，提醒主人")
            if CONTACT.search(t):
                warns.append(f"{lay.name}: 「{t}」像联系方式——小红书、抖音等禁导流，提醒主人")
    if brief:
        want = Counter()
        for x in brief.get("要什么", []):
            if isinstance(x, dict) and isinstance(x.get("张数"), int):
                want[(x.get("平台"), x.get("图类"))] += x["张数"]
        seen = {}
        for i, it in enumerate(items):
            base = str(it.get("图类", "")).split("·")[0]
            seen.setdefault((it.get("平台"), ALIAS.get(base, base)), set()).add(it.get("第几张", f"文件{i}"))
        got = Counter({k: len(v) for k, v in seen.items()})
        for k, n in want.items():
            if got.get(k, 0) < n:
                errs.append(f"需求单要 {k[0]} {k[1]} {n} 张，只出了 {got.get(k, 0)} 张")
        for k, n in got.items():
            if k not in want and not brief.get("套餐"):
                errs.append(f"出了需求单上没有的图：{k[0]} {k[1]} {n} 张——没要的不出")
            elif k in want and n > want[k] and not brief.get("套餐"):
                errs.append(f"{k[0]} {k[1]} 出了 {n} 张，需求单只要 {want[k]} 张")
    return errs, warns


def load_lock(path):
    """需求单里的「锁死清单」，或单独一份锁死清单。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("锁死清单", data) if isinstance(data, dict) else data


def check_lock(folder, lock):
    """排版出图：照 排版回执.json（排版.py 写的，升级版是从 PSD 读回的文字层）逐条对锁死清单。"""
    folder = Path(folder)
    errs = [f"锁死清单本身不对：{e}" for e in check_lock_list(lock)]
    if errs:
        return errs
    rc = folder / "排版回执.json"
    if not rc.exists():
        return [f"{folder.name}: 没有 排版回执.json（先用 排版.py 排）"]
    rec = json.loads(rc.read_text(encoding="utf-8"))
    size = list(lock["尺寸"])
    if rec.get("尺寸") != size:
        errs.append(f"尺寸不对：锁死 {size[0]}x{size[1]}，排出来 {rec.get('尺寸')}")
    for f in rec.get("文件", []):
        p = folder / f
        if p.suffix.lower() in (".png", ".jpg", ".jpeg"):
            got = png_size(p) if p.exists() else None
            if got is None:
                errs.append(f"{f}: 文件不在或读不了")
            elif list(got) != size:
                errs.append(f"{f}: {got[0]}x{got[1]}，锁死的是 {size[0]}x{size[1]}")
    got = {L.get("id"): L for L in rec.get("文字层", [])}
    for it in lock["文案"]:
        L = got.get(it["id"])
        if L is None:
            errs.append(f"漏了「{it['id']}」：锁死清单有，图上没有（框太小放不下也算漏）")
        elif (L.get("text") or "").replace("\r", "\n") != it["原文"]:
            errs.append(f"「{it['id']}」字不对：锁死「{it['原文']}」，图上「{L.get('text')}」")
    locked = {it["id"] for it in lock["文案"]}
    for k, L in got.items():
        if k not in locked:
            errs.append(f"多了一段没锁死的字「{k}」：「{L.get('text')}」")
    texts = [L.get("text") or "" for L in got.values()]
    found = sorted({float(x) for t in texts for x in prices_in(t)})
    if lock["价格"] is not None and found and found != [float(lock["价格"])]:
        errs.append(f"图上价格 {found}，锁死的只有 {lock['价格']}：一张图只出现一个价")
    if lock["价格"] is None and found:
        errs.append(f"锁死清单没有价格，图上却有 {found}")
    for w in lock["禁写"]:
        for t in texts:
            if w in t:
                errs.append(f"图上「{t}」里有禁写的「{w}」")
    allowed = {v.lower() for v in lock["色值"].values()}
    for L in rec.get("文字层", []) + rec.get("色块", []):
        c = (L.get("color") or "").lower()
        if c and c not in allowed:
            errs.append(f"「{L.get('id')}」用了 {c}，不在锁死的色值 {sorted(allowed)} 里")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--brief")
    ap.add_argument("--table")
    ap.add_argument("--lock", help="需求单（含锁死清单）或锁死清单：对 排版回执.json 逐条查")
    a = ap.parse_args(argv)
    if a.lock:
        errs = check_lock(a.folder, load_lock(a.lock))
        for e in errs:
            print("❌", e)
        print("✅ 锁死清单逐条对上" if not errs else f"共 {len(errs)} 处和锁死清单不符")
        return 1 if errs else 0
    table = find_table(a.table)
    if table is None:
        print("❌ 找不到 规格表.json")
        return 1
    brief = json.loads(Path(a.brief).read_text(encoding="utf-8")) if a.brief else None
    errs, warns = check_folder(a.folder, table, brief)
    for e in errs:
        print("❌", e)
    for w in warns:
        print("⚠️", w)
    print("✅ 机械自检通过" if not errs else f"共 {len(errs)} 处不合格")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())

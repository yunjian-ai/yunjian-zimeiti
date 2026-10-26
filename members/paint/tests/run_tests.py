"""丹青测试：①需求单夹具（check_brief 该抓的抓、不该抓的不抓）②库卡检查要通过 ③反向用例（往库副本里埋错，必须拦住）
④乱输入不崩（装了 hypothesis 才跑）。
用法：python3 members/paint/tests/run_tests.py"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE.parent / "库"
sys.path.insert(0, str(HERE.parent / "skills" / "paint-brief"))
from check_brief import check_brief, check_library, main as check_main  # noqa: E402

fails = 0


def report(ok, name, detail=""):
    global fails
    fails += not ok
    print(("✅ " if ok else "❌ ") + name + (f"  {detail}" if detail and not ok else ""))


# ① 夹具：expect 里每个词都要在报错里出现；expect 为空就必须一处都不报
for f in sorted((HERE / "fixtures").glob("*.json")):
    fx = json.loads(f.read_text(encoding="utf-8"))
    errs = check_brief(fx["doc"], LIB)
    if fx["expect"]:
        ok = all(any(w in e for e in errs) for w in fx["expect"])
    else:
        ok = not errs
    report(ok, f"夹具 {f.stem}", f"得到 {errs}｜{fx['why']}")

# ①¼ 打包：技能子文件夹里的文件也进包（v0.1.x 漏了 paint-master/身份证/，Bot 里拿不到模板）；借来的青鸟卡也在
_rec = json.loads((HERE.parent / "dist" / "recipe.json").read_text(encoding="utf-8"))
_files = {s["name"]: s["files"] for s in _rec["skills"]}
report(all(f"身份证/{k}.md" in _files["paint-master"] for k in ("商品", "人物", "场景", "风格", "品牌")), "打包：身份证模板 5 份都在安装包里")
report({"借用/图片卡.md", "借用/规则卡.md", "单图卡.md"} <= set(_files["paint-make"]) and {"判档卡.md", "系列流程卡.md"} <= set(_files["paint-brief"]),
       "打包：单图卡、判档卡、借来的青鸟两张卡都在安装包里")

# ①½ 命令行：有问题退出码 1，没问题 0
codes = []
for name in ("02-推荐加单没点头.json", "01-合格-只要一张主图.json"):
    tmp = Path(tempfile.mkdtemp()) / "brief.json"
    tmp.write_text(json.dumps(json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))["doc"], ensure_ascii=False), encoding="utf-8")
    codes.append(check_main([str(tmp), "--lib", str(LIB)]))
    shutil.rmtree(tmp.parent)
report(codes == [1, 0], "命令行退出码", f"得到 {codes}")

# ② 公共库本身要过
errs = check_library(LIB)
report(not errs, "库卡检查", "；".join(errs[:5]))


# ③ 反向用例：库副本里埋错，必须拦住
def broken(edit, want):
    with tempfile.TemporaryDirectory() as t:
        lib = Path(t) / "库"
        shutil.copytree(LIB, lib)
        edit(lib)
        got = check_library(lib)
        report(any(want in e for e in got), f"反向：{want}", f"得到 {got[:3]}")


broken(lambda l: (l / "场景/scene-baidi-chunbai.md").write_text(
    (l / "场景/scene-baidi-chunbai.md").read_text(encoding="utf-8").replace("## 注意\n", "## 备注\n"), encoding="utf-8"), "少了「## 注意」")
broken(lambda l: (l / "参考/ref-fengmian-duibi.md").rename(l / "参考/ref-fengmian-duibi-2.md"), "和文件名不一致")
broken(lambda l: (l / "品牌元素/brand-font-puhui.md").unlink(), "库里没有这张卡")
broken(lambda l: (l / "参考/好图标准.md").unlink(), "缺 好图标准.md")

# ④ 乱输入不崩
try:
    from hypothesis import given, settings, strategies as st

    leaf = st.none() | st.booleans() | st.integers() | st.text(max_size=8)
    tree = st.recursive(leaf, lambda c: st.lists(c, max_size=3) | st.dictionaries(st.text(max_size=4), c, max_size=4), max_leaves=12)

    @settings(max_examples=200, database=None, deadline=None)
    @given(st.dictionaries(st.sampled_from(["主体", "平台", "要什么", "套餐", "景", "参考", "品牌元素", "提醒", "主人确认", "版本"]), tree))
    def no_crash(d):
        base = json.loads((HERE / "fixtures" / "01-合格-只要一张主图.json").read_text(encoding="utf-8"))["doc"]
        d = {**base, **d}  # 拿合格单子做底，随机换掉几项，才走得到后面的检查
        try:
            check_brief(d, LIB)
        except (AttributeError, TypeError) as e:
            raise AssertionError(f"乱输入崩了：{e!r}｜{d}")

    no_crash()
    report(True, "乱输入不崩（hypothesis 200 例）")
except ImportError:
    print("（没装 hypothesis，跳过乱输入）")
except AssertionError as e:
    report(False, "乱输入不崩", str(e)[:300])

# ⑤ paint-master：出图尺寸、没密钥、裁图拆格、母版文件夹
sys.path.insert(0, str(HERE.parent / "skills" / "paint-master"))
import os  # noqa: E402
import struct  # noqa: E402
import zlib  # noqa: E402
import check_master  # noqa: E402
import 出图  # noqa: E402
import 细节  # noqa: E402

for size, want_err, want_warn in [("1536x1536", False, False), ("1536x2048", False, False), ("1500x1500", True, False),
                                  ("4000x1024", True, False), ("3072x960", True, False), ("512x512", True, False),
                                  ("2880x1920", False, True), ("auto", False, False), ("1536*1536", True, False)]:
    e, w = 出图.check_size(size)
    report(bool(e) == want_err and bool(w) == want_warn, f"出图尺寸 {size}", f"问题 {e} 提醒 {w}")

key = os.environ.pop("PAINT_IMAGE_API_KEY", None)
report(出图.run("文生图", "test", "/tmp/never.png") == 3, "没设密钥退出码 3（改用 Bot 自带出图）")
if key:
    os.environ["PAINT_IMAGE_API_KEY"] = key


def tiny_png(path, w, h):
    raw = b"".join(b"\x00" + bytes(sum(([x * 255 // w, y * 255 // h, 128] for x in range(w)), [])) for y in range(h))
    ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)  # noqa: E731
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b""))


with tempfile.TemporaryDirectory() as t:
    src = Path(t) / "板.png"
    tiny_png(src, 64, 48)
    code = 细节.main([str(src), "--grid", "2x2", "--outdir", str(Path(t) / "单张"), "--prefix", "板"])
    if code == 3:
        print("（这台机器没有 Pillow 和 sips，裁图测试只验了 NO_TOOL）")
    else:
        sizes = [细节.size_of(Path(t) / "单张" / f"板-{i}.png") for i in range(1, 5)]
        report(code == 0 and sizes == [(32, 24)] * 4, "拆 2x2 板", f"退出 {code} 尺寸 {sizes}")
        # 不光比尺寸，还要裁对地方：第 4 格（右下）左上角像素＝原图 (32, 24)，造图时 R=x*255//64、G=y*255//48
        if not 细节.Image:
            bmp = Path(t) / "4.bmp"
            subprocess.run(["sips", "-s", "format", "bmp", str(Path(t) / "单张" / "板-4.png"), "--out", str(bmp)], capture_output=True)
            _, _, px, rows = 细节.read_bmp(bmp)
            got = (rows[0][2], rows[0][1])
        else:
            with 细节.Image.open(Path(t) / "单张" / "板-4.png") as im:
                got = im.convert("RGB").getpixel((0, 0))[:2]
        report(got == (32 * 255 // 64, 24 * 255 // 48), "拆格裁对了地方（右下格颜色）", f"得到 {got}")
        code = 细节.main([str(src), "--box", "25%,25%,75%,75%", "--out", str(Path(t) / "细节.png"), "--scale", "2"])
        report(code == 0 and 细节.size_of(Path(t) / "细节.png") == (64, 48), "按百分比裁细节并放大 2 倍")
    report(细节.main([str(src), "--box", "50,10,10,40", "--out", str(Path(t) / "x.png")]) in (2, 3), "左右写反要报错")


def make_master(root, state="入库", samples=3, verdict="结论：全对，入库", hole=False, guess="主人确认"):
    f = Path(root) / "开衫"
    for d in ["原件", "单张", "样张"]:
        (f / d).mkdir(parents=True, exist_ok=True)
    (f / "原件" / "a.jpg").write_bytes(b"x")
    (f / "母版板.png").write_bytes(b"x")
    for i in range(samples):
        (f / "样张" / f"{i + 1}.png").write_bytes(b"x")
    color = "【主色】" if hole else "米白 #F2EDE4"
    (f / "身份证.md").write_text(f"---\n种类: 商品\n名字: 开衫\n版本: 1\n状态: {state}\n---\n\n## 不许改（出图时原文贴进提示词）\n- 颜色：{color}\n- 纽扣：5 颗\n\n## 推测（原图看不到）\n- 背面：素面｜{guess}\n", encoding="utf-8")
    (f / "验收.md").write_text(f"轮次：1\n{verdict}\n", encoding="utf-8")
    (f / "版本.md").write_text("v1 首次入库\n", encoding="utf-8")
    return f


for name, kw, want in [("合格入库", {}, None), ("草稿不查样张", {"state": "草稿", "samples": 0, "verdict": "还没验"}, None),
                       ("入库少样张", {"samples": 2}, "样张"), ("入库没验过", {"verdict": "结论：不过（印花）"}, "全对，入库"),
                       ("入库还有占位", {"hole": True}, "没填"),
                       # v1.5：一次性的系列，主人看过母版板说对就能出图，不要 3 张验收样张
                       ("主人确认不要样张", {"state": "主人确认", "samples": 0, "verdict": "还没验"}, None),
                       ("主人确认但推测没看", {"state": "主人确认", "samples": 0, "guess": "推测"}, "推测"),
                       ("主人确认还有占位", {"state": "主人确认", "samples": 0, "hole": True}, "没填"),
                       ("直接出丹青自查过", {"state": "丹青自查", "samples": 0, "verdict": "结论：全对"}, None),
                       ("直接出没自查", {"state": "丹青自查", "samples": 0, "verdict": "还没验"}, "全对"),
                       ("状态乱写", {"state": "已确认"}, "状态只能是")]:
    with tempfile.TemporaryDirectory() as t:
        errs, warns = check_master.check(make_master(t, **kw))
        report((not errs) if want is None else any(want in e for e in errs), f"母版检查：{name}", f"{errs}")
with tempfile.TemporaryDirectory() as t:
    errs, warns = check_master.check(make_master(t, guess="推测"))
    report(not errs and any("推测" in w for w in warns), "母版检查：推测没确认只提醒不拦", f"{errs} {warns}")

# ⑥ paint-make：交付裁压、叠图层
sys.path.insert(0, str(HERE.parent / "skills" / "paint-make"))
import 交付  # noqa: E402
import 叠图  # noqa: E402


def flat_png(path, w, h, rgb):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)  # noqa: E731
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b""))


tool = 交付.Image or shutil.which("sips")
with tempfile.TemporaryDirectory() as t:
    big = Path(t) / "大.png"
    tiny_png(big, 192, 128)
    code = 交付.main([str(big), "--size", "96x96", "--max-mb", "1", "--out", str(Path(t) / "成品.jpg")])
    if not tool:
        report(code == 3, "交付：没有工具时退出码 3")
    else:
        report(code == 0 and 交付.size_of(Path(t) / "成品.jpg") == (96, 96), "交付：铺满后居中裁到 96x96、压成 jpg")
        report(交付.main(["--check", str(Path(t) / "成品.jpg"), "--size", "100x100"]) == 1, "交付：像素不对要拦")
        report(交付.main(["--check", str(Path(t) / "成品.jpg"), "--size", "96x96", "--max-mb", "0.000001"]) == 1, "交付：超过大小上限要拦")
        grey = Path(t) / "近白.png"
        flat_png(grey, 64, 64, (250, 251, 249))
        report(交付.check(grey, (64, 64), None, white=True) != [], "交付：近白背景四角不是纯白要拦")
        if 交付.Image:
            交付.main([str(grey), "--size", "64x64", "--out", str(Path(t) / "白.png"), "--white"])
            report(交付.check(Path(t) / "白.png", (64, 64), None, white=True) == [], "交付：--white 压成纯白")

    layers = Path(t) / "图层.json"
    flat_png(Path(t) / "logo.png", 20, 10, (200, 30, 30))
    layers.write_text(json.dumps([
        {"id": "色块", "type": "rect", "color": "#B4472F", "opacity": 0.8, "x": 0, "y": 0.85, "w": 1, "h": 0.15},
        {"id": "logo", "type": "image", "src": "logo.png", "x": 0.05, "y": 0.05, "w": 0.2, "h": 0.1},
        {"id": "标题", "type": "text", "text": "冬天穿也不扎", "x": 0.1, "y": 0.3, "w": 0.8, "h": 0.2, "color": "#2B2420", "align": "center"},
    ], ensure_ascii=False), encoding="utf-8")
    base = Path(t) / "底.png"
    flat_png(base, 200, 200, (240, 235, 225))
    code = 叠图.main([str(base), str(layers), "-o", str(Path(t) / "叠好.png")])
    if not 叠图.Image or not 叠图.find_font():
        report(code == 3, "叠图：没有 Pillow 或中文字体时退出码 3（改交调图网页）")
    else:
        with 叠图.Image.open(Path(t) / "叠好.png") as im:
            im = im.convert("RGB")
            band, logo_px, mid = im.getpixel((100, 190)), im.getpixel((30, 15)), [im.getpixel((x, 80)) for x in range(20, 180)]
        report(im.size == (200, 200), "叠图：尺寸不变")
        report(band[0] > band[2] + 60, "叠图：底部色块叠上了", f"{band}")
        report(logo_px == (200, 30, 30), "叠图：logo 放进框里", f"{logo_px}")
        report(any(sum(p) < 400 for p in mid), "叠图：标题字画上了（中间一行有深色像素）")
    report(叠图.find_font("思源宋体", files=[Path("/x/PingFang.ttc"), Path("/x/SourceHanSerifSC-Regular.otf")]).name.startswith("SourceHanSerif"),
           "叠图：字体按名字优先找对应字体")
    report(叠图.find_font(None, files=[Path("/x/Arial.ttf")]) is None, "叠图：没有中文字体返回空（不拿英文字体硬画）")
report(叠图.find_font("Anton", files=[Path("/x/PingFang.ttc"), Path("/x/Anton-Regular.ttf")]).name == "Anton-Regular.ttf",
       "叠图：英文特粗窄体 Anton 按名字找得到")

# ⑦ paint-adjust：调图网页生成、收改动（改动记录是 10-25 在浏览器里真拖出来的那段，前后加了主人随手打的字）
sys.path.insert(0, str(HERE.parent / "skills" / "paint-adjust"))
import 收改动  # noqa: E402
import 调图页  # noqa: E402

with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    flat_png(t / "底.png", 120, 160, (240, 235, 225))
    flat_png(t / "logo.png", 20, 10, (200, 30, 30))
    lay = [{"id": "底条", "type": "rect", "color": "#2B2420", "opacity": 0.75, "x": 0, "y": 0.9, "w": 1, "h": 0.1},
           {"id": "logo", "type": "image", "src": "logo.png", "x": 0.05, "y": 0.05, "w": 0.2, "h": 0.1},
           {"id": "标题", "type": "text", "text": "一件开衫穿出三种样子", "x": 0.06, "y": 0.11, "w": 0.88, "h": 0.16, "font": "思源宋体"}]
    (t / "图层.json").write_text(json.dumps(lay, ensure_ascii=False), encoding="utf-8")
    page = 调图页.build(t / "底.png", t / "图层.json", t / "调图.html", "测试", (1080, 1440), [0.04, 0.04, 0.92, 0.92])
    html = Path(page).read_text(encoding="utf-8")
    report("__DATA__" not in html and '"rect"' in html and "data:image/png;base64" in html, "调图网页：数据、色块、图片都嵌进去了")
    (t / "Anton-Regular.ttf").write_bytes(b"\x00\x01\x00\x00fake-font")
    lay2 = lay + [{"id": "大字", "type": "text", "text": "NEON", "x": 0.1, "y": 0.3, "w": 0.8, "h": 0.4, "font": "Anton", "fontFile": "Anton-Regular.ttf"}]
    (t / "图层2.json").write_text(json.dumps(lay2, ensure_ascii=False), encoding="utf-8")
    html2 = Path(调图页.build(t / "底.png", t / "图层2.json", t / "调图2.html", "测试")).read_text(encoding="utf-8")
    report('@font-face{font-family:"Anton"' in html2 and "data:font/ttf;base64," in html2 and '"text": "NEON"' in html2 and "fontFile" not in html2,
           "调图网页：带字体文件的大字嵌进字体、还是文字层（能双击改字）")
    pasted = ('好了，我调好了 {"图":"测试封面","尺寸":[1080,1440],"改动":[{"图层":"标题","类型":"文字","原位置":{"x":0.06,"y":0.11,"w":0.88,"h":0.16},'
              '"新位置":{"x":0.06,"y":0.274,"w":0.88,"h":0.16},"文字":"一件开衫穿出三种样子"},'
              '{"图层":"cut1","类型":"圈选的图里东西","原位置":{"x":0.3,"y":0.4,"w":0.1,"h":0.1},"新位置":{"x":0.6,"y":0.4,"w":0.1,"h":0.1}}],'
              '"待补的空":[{"x":0.3,"y":0.4,"w":0.1,"h":0.1}]} 麻烦出高清')
    (t / "改动.json").write_text(pasted, encoding="utf-8")
    code = 收改动.main([str(t / "图层.json"), str(t / "改动.json"), "-o", str(t / "新图层.json")])
    new = {L["id"]: L for L in json.loads((t / "新图层.json").read_text(encoding="utf-8"))}
    report(code == 0 and new["标题"]["y"] == 0.274 and new["logo"]["y"] == 0.05, "收改动：只改挪过的那层，前后的闲话不影响")
    _, done, cuts, holes, missing = 收改动.apply(lay, json.loads(pasted[pasted.index("{"): pasted.rindex("}") + 1]))
    report(len(cuts) == 1 and len(holes) == 1, "收改动：圈选挪动和待补的空都列出来")
    (t / "坏.json").write_text("我调好了，就是往左挪一点", encoding="utf-8")
    report(收改动.main([str(t / "图层.json"), str(t / "坏.json"), "-o", str(t / "x.json")]) == 1, "收改动：粘的不是改动记录要说清")

# ⑧ paint-check：机械自检（故意塞错的要拦，不该误伤的不拦）
sys.path.insert(0, str(HERE.parent / "skills" / "paint-check"))
import check_paint  # noqa: E402

TABLE = json.loads((LIB / "规格表.json").read_text(encoding="utf-8"))


def work(t, files, items, brief=None, layers=None):
    d = Path(t) / "作品"
    d.mkdir(exist_ok=True)
    for name, (w, h, rgb) in files.items():
        flat_png(d / name, w, h, rgb)
    (d / "交付清单.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    if layers:
        (d / "图层-1.json").write_text(json.dumps(layers, ensure_ascii=False), encoding="utf-8")
    return check_paint.check_folder(d, TABLE, brief)


ok_brief = {"要什么": [{"图类": "1:1 主图", "张数": 1, "平台": "抖店", "来源": "主人"}], "套餐": False}
cases = [
    ("合格的一张主图", {"1.png": (1440, 1440, (200, 180, 160))}, [{"文件": "1.png", "第几张": 1, "平台": "抖店", "图类": "1:1 主图"}], ok_brief, None),
    ("主人要的像素不对", {"1.png": (1024, 1024, (200, 180, 160))}, [{"文件": "1.png", "第几张": 1, "平台": "抖店", "图类": "1:1 主图", "像素": [1440, 1440]}], ok_brief, "主人要 1440"),
    ("低于官方下限", {"1.png": (512, 512, (200, 180, 160))}, [{"文件": "1.png", "第几张": 1, "平台": "抖店", "图类": "1:1 主图"}], ok_brief, "低于官方下限"),
    ("比例错", {"1.png": (1440, 1080, (200, 180, 160))}, [{"文件": "1.png", "第几张": 1, "平台": "抖店", "图类": "1:1 主图", "像素": [1440, 1080]}], ok_brief, "比例"),
    ("多出没要的图", {"1.png": (1440, 1440, (1, 1, 1)), "2.png": (750, 1000, (1, 1, 1))},
     [{"文件": "1.png", "第几张": 1, "平台": "抖店", "图类": "1:1 主图"}, {"文件": "2.png", "第几张": 2, "平台": "抖店", "图类": "3:4 主图"}], ok_brief, "需求单上没有"),
    ("少出", {}, [], {"要什么": [{"图类": "1:1 主图", "张数": 2, "平台": "抖店", "来源": "主人"}], "套餐": False}, "只出了 0 张"),
    ("视频号待核", {"1.png": (1080, 1440, (1, 1, 1))}, [{"文件": "1.png", "第几张": 1, "平台": "视频号", "图类": "封面"}], None, "规格表里没有"),
    ("文件不在", {}, [{"文件": "没有.png", "第几张": 1, "平台": "抖店", "图类": "1:1 主图"}], None, "文件不在"),
    ("抖音一张封面交竖横两版不误报", {"竖.png": (900, 1200, (9, 9, 9)), "横.png": (1200, 900, (9, 9, 9))},
     [{"文件": "竖.png", "第几张": 1, "平台": "抖音", "图类": "视频封面·竖"}, {"文件": "横.png", "第几张": 1, "平台": "抖音", "图类": "视频封面·横"}],
     {"要什么": [{"图类": "封面", "张数": 1, "平台": "抖音", "来源": "主人"}], "套餐": False}, None),
    ("小红书图低于下限", {"1.png": (600, 800, (9, 9, 9))}, [{"文件": "1.png", "第几张": 1, "平台": "小红书", "图类": "封面", "像素": [600, 800]}], None, "低于官方下限"),
]
for name, files, items, brief, want in cases:
    with tempfile.TemporaryDirectory() as t:
        errs, warns = work(t, files, items, brief)
        report((not errs) if want is None else any(want in e for e in errs), f"自检：{name}", f"{errs}")
with tempfile.TemporaryDirectory() as t:
    errs, warns = work(t, {"1.png": (1024, 1024, (9, 9, 9))}, [{"文件": "1.png", "第几张": 1, "平台": "抖店", "图类": "1:1 主图"}])
    report(not errs and any("不是丹青默认" in w for w in warns), "自检：官方能传、只是不是丹青默认像素——只提醒不拦", f"{errs} {warns}")
with tempfile.TemporaryDirectory() as t:
    errs, warns = work(t, {"1.png": (800, 800, (250, 250, 250))}, [{"文件": "1.png", "第几张": 1, "平台": "抖店", "图类": "白底图"}])
    tool_ok = 交付.Image or shutil.which("sips")
    report(any("纯白" in e for e in errs) if tool_ok else any("白底四角" in w for w in warns), "自检：白底不白要拦（查不了就提醒）", f"{errs} {warns}")
with tempfile.TemporaryDirectory() as t:
    errs, warns = work(t, {"1.png": (1440, 1440, (9, 9, 9))}, [{"文件": "1.png", "第几张": 1, "平台": "抖店", "图类": "1:1 主图"}], None,
                       [{"id": "a", "type": "text", "text": "全网最软的开衫"}, {"id": "b", "type": "text", "text": "加微信领券"}, {"id": "c", "type": "text", "text": "柔软不扎"}])
    report(not errs and sum("极限词" in w for w in warns) == 1 and sum("联系方式" in w for w in warns) == 1, "自检：极限词、联系方式只提醒、各一条", f"{errs} {warns}")

# ⑨ paint-library：建我的库、计数不改公共卡、按选中率排、该归纳；单卡检查
sys.path.insert(0, str(HERE.parent / "skills" / "paint-library"))
import 库管  # noqa: E402
from check_brief import check_card  # noqa: E402

with tempfile.TemporaryDirectory() as t:
    root = 库管.build(Path(t) / "我的库")
    report(all((root / d).is_dir() for d in 库管.DIRS) and (root / "喜好.md").exists(), "库管：建好我的库")
    before = (LIB / "场景" / "scene-baidi-rouying.md").read_text(encoding="utf-8")
    for cid, what in [("scene-baidi-rouying", "用过"), ("scene-baidi-rouying", "选中"), ("scene-pengpai-nuanmi", "用过"), ("scene-pengpai-nuanmi", "用过")]:
        库管.bump(root, cid, what)
    report((LIB / "场景" / "scene-baidi-rouying.md").read_text(encoding="utf-8") == before, "库管：计数不改公共库的卡")
    order = 库管.rank(LIB / "场景", root)
    report(order[0] == "scene-baidi-rouying" and order.index("scene-pengpai-nuanmi") < len(order) and len(order) == 9, "库管：选中率高的排前面", f"{order}")
    for i in range(6):
        d = root / "作品" / f"单{i}"
        d.mkdir(parents=True)
        (d / "交付清单.json").write_text(json.dumps([{"文件": "1.png", "平台": "小红书", "图类": "封面"}], ensure_ascii=False), encoding="utf-8")
    report(库管.due(root) == {"封面": 6}, "库管：同类满 5 张该归纳", f"{库管.due(root)}")
    st = 库管.load_stats(root)
    st["_归纳到"] = {"封面": 6}
    库管.save_stats(root, st)
    report(库管.due(root) == {}, "库管：归纳过的不再提")
    report(库管.main(["记", "x", "收藏", str(root)]) == 2, "库管：只认「用过」「选中」")
    bad = Path(t) / "my-ref-x.md"
    bad.write_text((LIB / "参考" / "ref-kapian-jinju.md").read_text(encoding="utf-8").replace("## 为什么好用\n", ""), encoding="utf-8")
    errs = check_card(bad)
    report(any("和文件名不一致" in e for e in errs) and any("为什么好用" in e for e in errs), "单卡检查：id 不对、少小节都报", f"{errs}")
    report(check_card(LIB / "参考" / "ref-kapian-jinju.md") == [], "单卡检查：公共库的卡过")

md = (LIB / "平台规格.md").read_text(encoding="utf-8")
heads = set(re.findall(r"^### (\S+?)(?:（|$)", md, re.M))
pending = {h for h in heads if re.search(rf"^### {h}[^\n]*\n+\*\*待核\*\*", md, re.M)}
plats = {k.split("|")[0] for k in TABLE if "|" in k} - {"朋友圈", "社群"}
report(plats <= heads and not (plats & pending), "规格表和平台规格.md 对得上（待核的平台不进规格表）", f"规格表 {plats} md {heads} 待核 {pending}")

print(("✅ 全部通过" if not fails else f"❌ {fails} 项没过"))
sys.exit(1 if fails else 0)

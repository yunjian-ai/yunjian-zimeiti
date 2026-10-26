"""丹青需求单和库卡检查（只用标准库）。
用法：
  python3 check_brief.py <需求单.json> [--lib 库目录]   查一张需求单
  python3 check_brief.py --library [库目录]             查库里的场景、品牌元素、参考卡
  python3 check_brief.py --card <卡.md>                 只查一张卡（主人收进我的库的参考卡等）
库目录默认先找 ~/.yunjian/paint/库，没有再找本文件往上两级的 库/（开发仓库里）。
有问题打印 ❌ 并以 1 退出；全过打印 ✅。"""
import json
import re
import sys
from pathlib import Path

MENU = ["1:1 主图", "3:4 主图", "白底图", "详情图", "模特上身图", "场景图", "细节图",
        "封面", "文章配图", "信息图", "小红书图文卡片", "海报", "直播封面", "直播头图", "菜单外"]
ZHUTI = ["商品为主", "人物为主", "人＋货", "场景为主", "内容为主"]
BRAND = ["加（主人给）", "加（丹青出方案）", "不加", "待问"]
SOURCE = ["主人", "推荐"]
KEYS = ["版本", "日期", "一句话", "主体", "平台", "用途", "要什么", "套餐", "规格", "景", "品牌元素", "参考", "提醒", "主人确认"]

CARD_KINDS = {  # 库子目录 -> (卡头「类」, 卡头必填字段, 正文必有的小节)
    "场景": ("场景", ["景", "名字", "适用图", "适用主体"], ["什么样", "提示词片段（中）", "提示词片段（英）", "注意"]),
    "品牌元素": ("品牌元素", ["元素", "名字", "适用图"], ["什么样", "怎么做", "平台提醒（只提醒，主人定）", "注意"]),
    "参考": ("参考", ["图类", "名字", "适用平台"], ["什么样", "为什么好用", "怎么出", "注意"]),
}
COMMON = ["id", "类", "版本", "用过", "选中"]


def find_lib(arg=None):
    for p in ([Path(arg).expanduser()] if arg else []) + [Path.home() / ".yunjian/paint/库", Path(__file__).resolve().parents[2] / "库"]:
        if (p / "平台规格.md").exists():
            return p
    return None


def pending_platforms(lib):
    """平台规格.md 里标题下第一段写着「待核」的平台（整家没核的），出图前要停下。"""
    if not lib:
        return set()
    text = (lib / "平台规格.md").read_text(encoding="utf-8")
    out = set()
    for m in re.finditer(r"^### (\S+)[^\n]*\n+([^\n]*)", text, re.M):
        if m.group(2).startswith("**待核**"):
            out.add(m.group(1))
    return out


def check_brief(data, lib=None):
    errs = []
    for k in KEYS:
        if k not in data:
            errs.append(f"缺「{k}」")
    if errs:
        return errs
    if data["主体"] not in ZHUTI:
        errs.append(f"主体「{data['主体']}」不在 {ZHUTI} 里")
    if not isinstance(data["平台"], list) or not data["平台"]:
        errs.append("平台要写成至少一项的列表")
    items = data["要什么"]
    if not isinstance(items, list) or not items:
        errs.append("要什么至少一项（只写主人说到的图）")
        items = []
    pend = pending_platforms(lib)
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            errs.append(f"要什么第 {i} 项要写成 {{\"图类\", \"张数\", \"平台\", \"来源\"}}")
            continue
        if it.get("图类") not in MENU:
            errs.append(f"要什么第 {i} 项图类「{it.get('图类')}」不在菜单里（菜单外的写「菜单外」）")
        if not isinstance(it.get("张数"), int) or it.get("张数", 0) < 1:
            errs.append(f"要什么第 {i} 项张数要是 ≥1 的整数")
        if it.get("来源") not in SOURCE:
            errs.append(f"要什么第 {i} 项来源只能是「主人」或「推荐」")
        if it.get("来源") == "推荐" and not data["主人确认"]:
            errs.append(f"要什么第 {i} 项是推荐加的，主人还没点头——没点头的图类不出")
        if isinstance(it.get("平台"), str) and it["平台"] in pend:
            errs.append(f"要什么第 {i} 项平台「{it['平台']}」规格还没核对官方，先停下核，不出成品")
    if not isinstance(data["套餐"], bool):
        errs.append("套餐只能是 true / false（主人明说整套才是 true）")
    for k in ["景", "参考"]:
        v = data[k]
        if not isinstance(v, dict) or "选" not in v or v.get("来源") not in SOURCE:
            errs.append(f"{k}要写成 {{\"选\": …, \"来源\": \"主人\"/\"推荐\"}}")
    b = data["品牌元素"]
    if not isinstance(b, dict) or b.get("加不加") not in BRAND:
        errs.append(f"品牌元素「加不加」只能是 {BRAND}")
    if not isinstance(data["主人确认"], bool):
        errs.append("主人确认只能是 true / false")
    if not isinstance(data["提醒"], list):
        errs.append("提醒要写成列表（没有就写 []）")
    return errs


def parse_card(text):
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text
    head = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            head[k.strip()] = v.strip()
    return head, text[end + 5:]


def check_card(path):
    """只查一张卡：卡头、类、id 和文件名、正文小节。"""
    head, body = parse_card(Path(path).read_text(encoding="utf-8"))
    if head is None:
        return ["没有卡头（开头 --- 之间）"]
    kinds = {kind: (need, secs) for kind, need, secs in CARD_KINDS.values()}
    if head.get("类") not in kinds:
        return [f"类「{head.get('类')}」不认识，只能是 {list(kinds)}"]
    need, secs = kinds[head["类"]]
    errs = [f"卡头缺「{k}」" for k in COMMON + need if not head.get(k)]
    if head.get("id") != Path(path).stem:
        errs.append(f"id「{head.get('id')}」和文件名不一致")
    errs += [f"少了「## {s}」一节" for s in secs if f"## {s}\n" not in body]
    return errs


def check_library(lib):
    errs, ids = [], {}
    for sub, (kind, need, sections) in CARD_KINDS.items():
        d = lib / sub
        cards = sorted(d.glob("*.md")) if d.is_dir() else []
        cards = [c for c in cards if c.name != "README.md" and not c.name.startswith("好图标准")]
        if len(cards) < 2:
            errs.append(f"{sub}/ 只有 {len(cards)} 张卡，每类至少能挑 2～3 个")
        readme = (d / "README.md").read_text(encoding="utf-8") if (d / "README.md").exists() else ""
        if not readme:
            errs.append(f"{sub}/ 缺 README.md 目录")
        for c in cards:
            head, body = parse_card(c.read_text(encoding="utf-8"))
            rel = f"{sub}/{c.name}"
            if head is None:
                errs.append(f"{rel}: 没有卡头（开头 --- 之间）")
                continue
            for k in COMMON + need:
                if not head.get(k):
                    errs.append(f"{rel}: 卡头缺「{k}」")
            if head.get("类") != kind:
                errs.append(f"{rel}: 类应是「{kind}」，写的是「{head.get('类')}」")
            if head.get("id") != c.stem:
                errs.append(f"{rel}: id「{head.get('id')}」和文件名不一致")
            if head.get("id") in ids:
                errs.append(f"{rel}: id 和 {ids[head['id']]} 重复")
            ids[head.get("id")] = rel
            for s in sections:
                if f"## {s}\n" not in body:
                    errs.append(f"{rel}: 少了「## {s}」一节")
            if readme and head.get("id") not in readme:
                errs.append(f"{rel}: README.md 目录里没列这张")
    for sub in CARD_KINDS:
        readme = lib / sub / "README.md"
        if readme.exists():
            for cid in re.findall(r"\b((?:scene|brand|ref)-[a-z0-9-]+)\b", readme.read_text(encoding="utf-8")):
                if cid not in ids:
                    errs.append(f"{sub}/README.md 列了 {cid}，库里没有这张卡")
    if not (lib / "参考" / "好图标准.md").exists():
        errs.append("参考/ 缺 好图标准.md")
    return errs


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--card":
        errs = check_card(argv[1]) if len(argv) > 1 else ["要写卡的路径"]
        for e in errs:
            print("❌", e)
        print("✅ 通过" if not errs else f"共 {len(errs)} 处问题")
        return 1 if errs else 0
    if argv[0] == "--library":
        lib = find_lib(argv[1] if len(argv) > 1 else None)
        if not lib:
            print("❌ 找不到库（要有 平台规格.md）")
            return 1
        errs = check_library(lib)
    else:
        lib_arg = argv[argv.index("--lib") + 1] if "--lib" in argv else None
        lib = find_lib(lib_arg)
        try:
            data = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"❌ 读不了需求单：{e}")
            return 1
        errs = check_brief(data, lib)
        if not lib:
            print("⚠️ 没找到库，没查平台是不是还没核规格")
    for e in errs:
        print("❌", e)
    print("✅ 通过" if not errs else f"共 {len(errs)} 处问题")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

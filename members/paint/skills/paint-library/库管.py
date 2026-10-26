"""丹青库管：建「我的库」、记用过和选中、按选中率排卡、看哪类图该归纳喜好了。只用标准库。
计数记在 我的库/统计.json，不改公共库的卡（公共库每次更新整体换新，记在卡上会被冲掉）。
用法：python3 库管.py 建 [我的库]                         建好文件夹（已有的不动）
     python3 库管.py 记 <卡id> 用过|选中 [我的库]          计数加一
     python3 库管.py 排 <库目录>/场景 [我的库]             这一类卡按选中率排（没用过的排后面），给挑卡用
     python3 库管.py 该归纳 [我的库]                       同一图类的作品满 5 张、上回归纳后又多了 5 张的，列出来
我的库默认 ~/.yunjian/paint/我的库。"""
import json
import sys
from pathlib import Path

HOME = Path.home() / ".yunjian/paint/我的库"
DIRS = ["母版/商品", "母版/人物", "母版/场景", "母版/风格", "母版/品牌", "母版/版式", "需求单", "作品", "成品", "参考", "收件箱/已处理"]
EVERY = 5


def mine(arg=None):
    return Path(arg).expanduser() if arg else HOME


def load_stats(root):
    p = root / "统计.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except ValueError:
        return {}


def save_stats(root, st):
    root.mkdir(parents=True, exist_ok=True)
    (root / "统计.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def build(root):
    for d in DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
    if not (root / "喜好.md").exists():
        (root / "喜好.md").write_text("# 喜好（同一图类做满 5 张归纳一次；主人说的「以后都这样」也记在这）\n\n", encoding="utf-8")
    return root


def bump(root, cid, what):
    if what not in ("用过", "选中"):
        raise ValueError("只能记「用过」或「选中」")
    st = load_stats(root)
    st.setdefault(cid, {"用过": 0, "选中": 0})[what] += 1
    save_stats(root, st)
    return st[cid]


def rank(folder, root):
    st = load_stats(root)
    cards = [c.stem for c in sorted(Path(folder).glob("*.md")) if c.name != "README.md" and not c.name.startswith("好图标准")]
    mine_cards = [c.stem for c in sorted((root / "参考").glob("*.md"))] if Path(folder).name == "参考" else []
    def key(cid):
        s = st.get(cid, {})
        used, picked = s.get("用过", 0), s.get("选中", 0)
        return (-(picked / used) if used else 1, -picked, cid)  # 选中率高的在前；没用过的排后面
    return sorted(set(cards + mine_cards), key=key)


def due(root):
    """作品文件夹里每单的 交付清单.json 记了图类；同一图类累计满 5、且比上回归纳多了 5 张的，该归纳。"""
    counts = {}
    for lst in (root / "作品").glob("*/交付清单.json"):
        try:
            for it in json.loads(lst.read_text(encoding="utf-8")):
                k = str(it.get("图类", "")).split("·")[0]
                counts[k] = counts.get(k, 0) + 1
        except ValueError:
            continue
    done = load_stats(root).get("_归纳到", {})
    return {k: n for k, n in counts.items() if n >= EVERY and n - done.get(k, 0) >= EVERY}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    try:
        if cmd == "建":
            print(f"OK {build(mine(argv[1] if len(argv) > 1 else None))}")
        elif cmd == "记":
            print(f"OK {argv[1]} {bump(mine(argv[3] if len(argv) > 3 else None), argv[1], argv[2])}")
        elif cmd == "排":
            for cid in rank(argv[1], mine(argv[2] if len(argv) > 2 else None)):
                print(cid)
        elif cmd == "该归纳":
            d = due(mine(argv[1] if len(argv) > 1 else None))
            print("\n".join(f"{k}：{n} 张，该归纳" for k, n in d.items()) or "都还不到")
        else:
            print(__doc__)
            return 2
    except (IndexError, ValueError) as e:
        print("❌", e or "参数不够")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

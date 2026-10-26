"""丹青库管：建「我的库」、记用过和选中、按选中率排卡、看哪类图该归纳喜好了。只用标准库。
计数记在 我的库/统计.json，不改公共库的卡（公共库每次更新整体换新，记在卡上会被冲掉）。
用法：python3 库管.py 建 [我的库]                         建好文件夹（已有的不动）
     python3 库管.py 记 <卡id> 用过|选中 [我的库]          计数加一
     python3 库管.py 排 <库目录>/场景 [我的库]             这一类卡按选中率排（没用过的排后面），给挑卡用
     python3 库管.py 该归纳 [我的库]                       同一图类的作品满 5 张、上回归纳后又多了 5 张的，列出来
     python3 库管.py 上限 <成品张数> [--不花 N] [--新母版 M] [--入库 K]   照公式算系列图出图上限，打出算式
     python3 库管.py 进度 <单名> --现在 … --出图 3/7 --下一步 … [--母版 …] [--等主人定 …] [--记 …] [--库 我的库]
                                                         系列图每走一步跑一次：写 作品/<单名>/进度.md，「经过」里追加一行
     python3 库管.py 进度 <单名> [--库 我的库]               只读，原样打出这单的进度
     python3 库管.py 没做完 [我的库]                       列出还没到「⑤ 交付 ✅」的单，最近动过的在前
我的库默认 ~/.yunjian/paint/我的库。"""
import json
import re
import sys
from datetime import datetime
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


def limit(n, free=0, masters=0, keep=0):
    """系列图出图上限：成品张数 − 能裁、能抠、只排版的 ＋ 新立母版×2（母版板 1、改一次 1）＋ 重画 2 ＋ 入库母版×3（验收样张）。"""
    if min(n, free, masters, keep) < 0 or free > n:
        raise ValueError("张数不对：不花次数的不能比成品还多，也不能是负数")
    parts = [f"成品 {n} 张"] + ([f"− 能裁、能抠的 {free} 张"] if free else []) + ([f"＋ 新母版 {masters}×2"] if masters else []) + ["＋ 重画 2"] + ([f"＋ 入库验收 {keep}×3"] if keep else [])
    total = n - free + masters * 2 + 2 + keep * 3
    return total, " ".join(parts) + f" ＝ {total}"


FIELDS = ["现在", "母版", "出图", "下一步", "等主人定"]
MUST = ["现在", "出图", "下一步"]


def read_progress(path):
    fields, log = {}, []
    if path.exists():
        in_log = False
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## 经过"):
                in_log = True
            elif in_log and line.startswith("- "):
                log.append(line)
            elif not in_log and "：" in line:
                k, v = line.split("：", 1)
                if k in FIELDS:
                    fields[k] = v
    return fields, log


def progress(root, name, new, note=None):
    """合并旧进度、校验必填和出图次数，写回 进度.md；返回（文件内容，提醒）。"""
    path = root / "作品" / name / "进度.md"
    fields, log = read_progress(path)
    fields.update({k: v for k, v in new.items() if v})
    lack = [k for k in MUST if not fields.get(k)]
    if lack:
        raise ValueError("缺：" + "、".join(lack))
    m = re.search(r"(\d+)\s*[/／]\s*(?:上限\s*)?(\d+)", fields["出图"])
    if not m:
        raise ValueError("「出图」写成「用了几次/上限几次」，比如 3/7")
    warn = "⚠️ 出图已超上限，先停下问主人" if int(m.group(1)) > int(m.group(2)) else ""
    log.append(f"- {datetime.now():%m-%d %H:%M} {fields['现在']}" + (f"：{note}" if note else ""))
    text = f"# 进度｜{name}\n" + "".join(f"{k}：{fields.get(k) or '无'}\n" for k in FIELDS) + "\n## 经过\n" + "\n".join(log) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text, warn


def unfinished(root):
    out = []
    for p in sorted((root / "作品").glob("*/进度.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        now = read_progress(p)[0].get("现在", "")
        if not re.search(r"交付\s*✅", now):
            out.append((p.parent.name, now))
    return out


def opts(args, keys):
    got, rest, i = {}, [], 0
    while i < len(args):
        k = args[i][2:] if args[i].startswith("--") else None
        if k in keys:
            if i + 1 >= len(args):
                raise ValueError(f"--{k} 后面要跟内容")
            got[k] = args[i + 1]
            i += 2
        elif k is not None:
            raise ValueError(f"不认识 --{k}")
        else:
            rest.append(args[i])
            i += 1
    return got, rest


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
        elif cmd == "上限":
            o, rest = opts(argv[1:], ["不花", "新母版", "入库"])
            print(limit(int(rest[0]), *(int(o.get(k, 0)) for k in ("不花", "新母版", "入库")))[1])
        elif cmd == "进度":
            o, rest = opts(argv[1:], FIELDS + ["记", "库"])
            root, name = mine(o.pop("库", None)), rest[0]
            note = o.pop("记", None)
            if not o and not note:
                path = root / "作品" / name / "进度.md"
                if not path.exists():
                    raise ValueError(f"没有这单的进度：{path}")
                print(path.read_text(encoding="utf-8"), end="")
            else:
                text, warn = progress(root, name, o, note)
                print(text + (warn and warn + "\n"), end="")
        elif cmd == "没做完":
            print("\n".join(f"{n}｜{now}" for n, now in unfinished(mine(argv[1] if len(argv) > 1 else None))) or "都交付了")
        else:
            print(__doc__)
            return 2
    except (IndexError, ValueError) as e:
        print("❌", e or "参数不够")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""爆款库的目录和索引：从爆款卡卡头、「能借的」招式、收件箱条目生成三样，写稿抽卡、雷达去重都查这同一份。
- 目录.md：一卡一行，人和 AI 写稿前先读它挑卡
- 招式/<位置>.md：同一位置的招汇总，写开头只读 招式/开头.md
- 索引.json：同样的字段给脚本用
- 统计.md：每格的爆款类型分布、各位置最常用的招（归纳打法照它的数写）
用法：python3 建目录.py [库路径…]                       重建（默认就是本文件所在的库）
      python3 建目录.py 精选 [输出文件]                    从公开卡生成 pen-library/招式精选.md（发版前跑）
      python3 建目录.py 查 --平台 抖音 --形式 口播 --稿型 方法 --赛道 知识分享 --话题 收纳 --位置 开头 [--库 我的库 --库 公共底盘]
只用 Python 自带的库（没装 PyYAML 也能跑）。"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_library as cl  # noqa: E402  卡头读法、招式格式都以它为准，两边不会对不上

FIELDS = ["id", "赛道", "平台", "形式", "稿型", "标题", "账号", "链接", "发布日期", "互动", "爆款类型", "标签", "来源", "状态", "好例", "公开"]
PICKS = 10  # 招式精选：每个位置挑几招
# 和守门层冲突的招不进精选：「不是…而是…」这类先立误解再推翻的句式，执笔的去 AI 味卡 A1 禁用（check_pen 当硬错）
PIVOT_LIKE = __import__("re").compile(r"不是[^。！？\n]{0,30}(?:而|就)?是|而不是|并非|与其[^。！？\n]{0,20}不如|以为[^。！？\n]{0,30}其实")


def _card(path, root):
    head, body = cl.split_card(path.read_text(encoding="utf-8"))
    if not isinstance(head, dict):
        return None
    moves, _ = cl.parse_moves(body)
    e = {k: head.get(k) for k in FIELDS}
    e.update(爆款类型=(head.get("爆款判断") or {}).get("类型"), 来源=head.get("来源") or "公共底盘",
             状态=head.get("状态") or "已拆", 好例=bool(head.get("好例")), 标签=head.get("标签") or [],
             招式=[dict(zip(["位置", "公式", "示范", "适用"], m)) for m in moves], 路径=str(path.relative_to(root)))
    return e


def _inbox(path, root):
    head, _ = cl.split_card(path.read_text(encoding="utf-8"))
    if not isinstance(head, dict):
        return None
    e = {k: head.get(k) for k in FIELDS}
    e.update(id=path.stem, 来源=head.get("来源") or head.get("放的人") or "主人丢", 状态="收件箱", 好例=False,
             标签=head.get("标签") or [], 招式=[], 路径=str(path.relative_to(root)))
    return e


def collect(root):
    root = Path(root)
    out = [e for p in sorted((root / "爆款").glob("*/*/*.md")) if (e := _card(p, root))]
    out += [e for p in sorted((root / "收件箱").glob("*.md")) if (e := _inbox(p, root))]
    return out


def _num(v):
    return f"{v / 10000:.1f} 万" if isinstance(v, int) and v >= 10000 else str(v if v is not None else "没抓到")


def build(root):
    root = Path(root)
    entries = collect(root)
    (root / "索引.json").write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# 爆款库目录（建目录.py 自动生成，别手改）", "", "id｜赛道·平台·形式·稿型｜标题｜互动（爆款类型）｜话题｜招数｜来源｜状态", ""]
    for e in entries:
        hd = e.get("互动") or {}
        spots = {}
        for m in e["招式"]:
            spots[m["位置"]] = spots.get(m["位置"], 0) + 1
        lines.append("｜".join([
            str(e["id"]), "·".join(str(e.get(k) or "?") for k in ("赛道", "平台", "形式", "稿型")), str(e.get("标题") or ""),
            f"赞 {_num(hd.get('点赞'))} 藏 {_num(hd.get('收藏'))}（{e.get('爆款类型') or '?'}）",
            "话题：" + "、".join(map(str, e["标签"])), "招：" + ("、".join(f"{k}×{v}" for k, v in spots.items()) or "（未拆）"),
            e["来源"] + ("·好例" if e["好例"] else ""), e["状态"]]))
    (root / "目录.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    d = root / "招式"
    d.mkdir(exist_ok=True)
    for spot in cl.SPOTS:
        rows = [f"- {m['公式']}｜" + (f"示范「{m['示范']}」｜" if m["示范"] else "") + f"适用：{m['适用']}｜{e['id']}（{e['平台']}·{e['形式']}·{e['稿型']}）"
                for e in entries for m in e["招式"] if m["位置"] == spot]
        (d / f"{spot}.md").write_text(f"# 招式 · {spot}（建目录.py 自动生成）\n\n" + ("\n".join(rows) if rows else "（还没有）") + "\n", encoding="utf-8")
    stats(root, entries)
    return entries


def stats(root, entries):
    """统计.md：每格的爆款类型分布、各位置最常用的招——归纳打法时照这些数写（pen-library 第 3 节）。"""
    cells = {}
    for e in entries:
        if e["状态"] == "已拆":
            cells.setdefault((e["赛道"], e["平台"]), []).append(e)
    lines = ["# 爆款库统计（建目录.py 自动生成，别手改）", ""]
    for (t, pl), es in sorted(cells.items()):
        kinds, spots, forms = {}, {}, {}
        for e in es:
            kinds[e.get("爆款类型") or "?"] = kinds.get(e.get("爆款类型") or "?", 0) + 1
            forms[e.get("形式") or "?"] = forms.get(e.get("形式") or "?", 0) + 1
            for m in e["招式"]:
                spots.setdefault(m["位置"], []).append(m["公式"])
        lines += [f"## {t} · {pl}（{len(es)} 张）",
                  "- 形式：" + "、".join(f"{k} {v}" for k, v in sorted(forms.items(), key=lambda kv: -kv[1])),
                  "- 爆款类型：" + "、".join(f"{k} {v}" for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]))]
        for spot in [s for s in SPOT_ORDER if s in spots]:
            lines.append(f"- {spot}的招 {len(spots[spot])} 条，例：" + "；".join(spots[spot][:3]))
        lines.append("")
    (Path(root) / "统计.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def picks(entries, out):
    """招式精选：只从公开卡里挑，每个位置按点赞（好例优先）取前 PICKS 招，写成一个文件放进 pen-library 技能包——Bot 读不到库也能用。"""
    lines = ["# 招式精选（建目录.py 从公共底盘的公开爆款卡自动生成，别手改）", "",
             "> 读不到库（Bot 不能读文件、不能跑命令）时就用这一份：每个位置的招都来自真爆款，只借公式和位置，示范句不搬。", ""]
    pub = [e for e in entries if e.get("公开") and e["状态"] == "已拆"]
    likes = lambda e: (e["好例"], (e.get("互动") or {}).get("点赞") if isinstance((e.get("互动") or {}).get("点赞"), int) else 0)
    for spot in SPOT_ORDER:
        rows = [(e, m) for e in sorted(pub, key=likes, reverse=True) for m in e["招式"]
                if m["位置"] == spot and not PIVOT_LIKE.search(m["公式"] + (m["示范"] or ""))][:PICKS]
        lines.append(f"## {spot}")
        lines += [f"- {m['公式']}｜" + (f"示范「{m['示范']}」｜" if m["示范"] else "") + f"适用：{m['适用']}｜{e['平台']}·{e['形式']}·{e['稿型']}（{e['id']}）"
                  for e, m in rows] or ["（还没有）"]
        lines.append("")
    Path(out).write_text("\n".join(lines), encoding="utf-8")
    return sum(1 for e in pub for _ in e["招式"])


SPOT_ORDER = cl.SPOTS


def query(entries, 平台=None, 形式=None, 稿型=None, 赛道=None, 话题=(), 位置=None, n=5):
    """按 同平台同形式 → 同稿型 → 同赛道 → 话题词重合 → 好例 打分，取前 n；返回 (结果, 放宽了哪几项)。"""
    seen, pool = set(), []
    for e in entries:  # 按链接去重：先给的库（我的库）优先
        if e["状态"] == "归档" or (位置 and not any(m["位置"] == 位置 for m in e["招式"])) or (e.get("链接") and e["链接"] in seen):
            continue
        seen.add(e.get("链接"))
        pool.append(e)
    def score(e):
        tags = set(map(str, e["标签"]))
        return ((e.get("平台") == 平台) * 8 + (e.get("形式") == 形式) * 4 + (e.get("稿型") == 稿型) * 2 + (e.get("赛道") == 赛道) * 2
                + len(tags & set(话题)) + e["好例"] * 3)
    got = sorted(pool, key=score, reverse=True)[:n]
    loose = [k for k, v in (("平台", 平台), ("形式", 形式), ("稿型", 稿型), ("赛道", 赛道)) if v and any(e.get(k) != v for e in got)]
    return got, loose


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["查"]:
        ap = argparse.ArgumentParser()
        for k in ("平台", "形式", "稿型", "赛道", "位置"):
            ap.add_argument(f"--{k}")
        ap.add_argument("--话题", nargs="*", default=[])
        ap.add_argument("--库", action="append", help="可给多个，先给的优先（我的库在前）")
        ap.add_argument("-n", type=int, default=5)
        a = ap.parse_args(argv[1:])
        entries = [e for r in (a.库 or [str(HERE)]) for e in collect(r)]
        got, loose = query(entries, a.平台, a.形式, a.稿型, a.赛道, a.话题, a.位置, a.n)
        for e in got:
            ms = [m for m in e["招式"] if not a.位置 or m["位置"] == a.位置]
            print(f"{e['id']}｜{e['平台']}·{e['形式']}·{e['稿型']}·{e['赛道']}｜{e.get('标题')}｜{e['路径']}")
            for m in ms:
                print(f"    【{m['位置']}】{m['公式']}" + (f"｜示范「{m['示范']}」" if m["示范"] else "") + f"｜适用：{m['适用']}")
        print(("放宽了：" + "、".join(loose)) if loose else ("没抽到" if not got else "都对得上"))
        return
    if argv[:1] == ["精选"]:
        out = argv[1] if len(argv) > 1 else str(HERE.parent / "skills" / "pen-library" / "招式精选.md")
        n = picks(collect(HERE), out)
        print(f"招式精选：从公开卡的 {n} 招里挑，写到 {out}")
        return
    for r in argv or [str(HERE)]:
        es = build(r)
        print(f"{r}：{sum(e['状态'] == '已拆' for e in es)} 张卡、{sum(e['状态'] == '收件箱' for e in es)} 条收件箱，目录和索引已更新")


if __name__ == "__main__":
    main()

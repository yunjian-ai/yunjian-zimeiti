"""执笔爆款库的机械检查。只报不改。
用法：python3 check_library.py [库目录] [--min 10] [--public-min 5] [--strict] [--json]
  默认库目录是本文件所在的文件夹；也可以指主人的「我的库」。
查：卡头过 schema/爆款卡.schema.json；卡身九节都在；id 和文件夹（赛道、平台）对得上、不重复；
    开头摘引不超 50 字、卡身引号里的原文摘引不超 50 字（不收全文）；不夹密钥；同一赛道同一平台里同一账号最多 2 张；发布日期不超时（AI 应用 183 天、其余 365 天，标「经典」的例外）；外文卡有开头中文意思；抖音、视频号、公众号只收中文，X 的 AI 应用不限外文，X 其余赛道外文最多三成；
    每个赛道每个平台的卡数（--min 起算，--strict 时不够就算错；公开卡数对 --public-min）。
退出码：有错为 1。依赖：PyYAML、jsonschema。"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # 主人的 Bot 没装 PyYAML 也要能读卡（建目录.py 靠它）
    yaml = None

HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / "schema" / "爆款卡.schema.json").read_text(encoding="utf-8"))
SECTIONS = ["钩子链", "重点·爆点·槽点·知识点", "手法", "表达特点", "图文和画面", "收藏件和福利", "为什么爆（判断）", "能借的", "不能照搬的"]
TRACKS = {"知识分享": "zs", "带货": "dh", "AI应用": "ai"}
PLATFORMS = {"抖音": "dy", "视频号": "sph", "公众号": "gzh", "X": "x"}
QUOTE_MAX = 50
SECRET = [re.compile(r"BEATAPI_API_KEY\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{8,}"),
          re.compile(r"\bsk-[A-Za-z0-9]{16,}"), re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}")]
QUOTE = re.compile(r"「([^「」]+)」")
SPOTS = ["标题", "开头", "钩子", "爆点", "槽点", "结尾", "收藏件"]
# 「能借的」一招一行：- 【位置】公式｜示范「≤50 字原文」｜适用：…（示范可以没有）。建目录.py 照这个读招式
MOVE = re.compile(r"^- 【(" + "|".join(SPOTS) + r")】([^｜\n]+?)(?:｜示范「([^」]+)」)?｜适用：(\S.*)$")


VAGUE = ["很吸引人", "吸引眼球", "有感染力", "引起共鸣", "抓住注意力", "很有冲击力", "节奏感强", "很有画面感", "直击痛点", "引发思考"]  # 招式里的空话：写了等于没写


def section(body, name):
    m = re.search(rf"^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    return m.group(1) if m else ""


def parse_moves(body):
    """读「能借的」里的招式：[(位置, 公式, 示范, 适用)]；格式不对的行另外返回。"""
    moves, bad = [], []
    for line in section(body, "能借的").splitlines():
        if not line.strip():
            continue
        m = MOVE.match(line.strip())
        (moves.append(m.groups()) if m else bad.append(line.strip()))
    return moves, bad


if yaml:
    class _TextDates(yaml.SafeLoader):
        """日期按文字读，不让 YAML 自动变成日期对象（卡里日期不用加引号）。"""

    _TextDates.yaml_implicit_resolvers = {k: [r for r in v if r[0] != "tag:yaml.org,2002:timestamp"]
                                          for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()}


def _mini_yaml(text):
    """没有 PyYAML 时的简易读法：只认卡头用到的「键: 值」、缩进两格的一层子项、[a, b] 列表、数字和 true/false。"""
    def val(v):
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            return [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
        if v in ("true", "false"):
            return v == "true"
        if len(v) > 1 and v[0] == v[-1] and v[0] in "'\"":
            return v[1:-1]
        return int(v) if re.fullmatch(r"-?\d+", v) else v
    out, cur = {}, None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\s*)([^:\s][^:]*):\s*(.*)$", line)
        if not m:
            continue
        ind, k, v = m.groups()
        if ind and isinstance(cur, dict):
            cur[k.strip()] = val(v)
        elif v == "":
            cur = out[k.strip()] = {}
        else:
            out[k.strip()], cur = val(v), None
    return out


def split_card(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return None, text
    return (yaml.load(m.group(1), Loader=_TextDates) if yaml else _mini_yaml(m.group(1))), m.group(2)


def quote_problems(body, source):
    """「」里只许放原文原样（同音错字可以改正）：逐处到原文里找。省略号拼接的每段都要在；差一两个字的算改错字放过。
    返回原文里找不到的引用（拿引号括自己的话、转述、编的，都在这里）。"""
    import difflib
    sq = lambda t: re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", t)
    whole, bad = sq(source), []
    for q in QUOTE.findall(body):
        s = sq(q)
        if not s or q.strip() in ("没抓到",) or s in whole:
            continue
        parts = [sq(x) for x in re.split(r"…+|\.{3,}", q) if sq(x)]
        if len(parts) > 1 and all(x in whole for x in parts):
            continue
        mt = difflib.SequenceMatcher(None, s, whole, autojunk=False).find_longest_match(0, len(s), 0, len(whole))
        win = whole[max(0, mt.b - mt.a): max(0, mt.b - mt.a) + len(s) + 4]
        if len(s) > 8 and difflib.SequenceMatcher(None, s, win).ratio() >= 0.8:
            continue
        bad.append(q)
    return bad


def check_card(path, seen):
    errs = []
    text = path.read_text(encoding="utf-8")
    for pat in SECRET:
        if pat.search(text):
            errs.append("夹带了像密钥的字符串，删掉（密钥只放主人本机环境变量）")
    head, body = split_card(text)
    if not isinstance(head, dict):
        return errs + ["开头没有 --- 包起来的卡头"], None
    import jsonschema  # 只有查卡头格式时才要它
    v = jsonschema.Draft202012Validator(SCHEMA)
    for e in sorted(v.iter_errors(head), key=lambda e: list(e.path)):
        where = "/".join(str(p) for p in e.path) or "卡头"
        errs.append(f"卡头 {where}：{e.message}")
    # 文件夹是 爆款/<赛道>/<平台>/，和卡头、id 对得上
    parts = path.parts
    if len(parts) >= 3 and isinstance(head.get("id"), str):
        track, plat = parts[-3], parts[-2]
        if head.get("赛道") != track or head.get("平台") != plat:
            errs.append(f"放错文件夹：卡头写 {head.get('赛道')}/{head.get('平台')}，文件在 {track}/{plat}")
        want = f"{PLATFORMS.get(plat, '?')}-{TRACKS.get(track, '?')}-"
        if not head["id"].startswith(want):
            errs.append(f"id {head['id']} 和文件夹对不上，应以 {want} 开头")
        if head["id"] in seen:
            errs.append(f"id {head['id']} 和 {seen[head['id']]} 重复")
        seen[head["id"]] = path.name
    try:  # 时间关：AI 应用 183 天、其余 365 天；标了「经典」（写理由）的例外
        from datetime import date
        pub, got = date.fromisoformat(str(head.get("发布日期"))), date.fromisoformat(str(head.get("采集日期")))
        lim = 183 if head.get("赛道") == "AI应用" else 365
        if (got - pub).days > lim and not head.get("经典"):
            errs.append(f"超时：发布 {pub} 到采集 {got} 已 {(got - pub).days} 天（上限 {lim}）；常青范例要写「经典: 理由」")
    except (ValueError, TypeError):
        pass
    if head.get("语言", "中文") != "中文" and not head.get("开头摘引中文"):
        errs.append("外文卡要写「开头摘引中文」（开头那句的中文意思）")
    for s in SECTIONS:
        if not re.search(rf"^## {re.escape(s)}\s*$", body, re.M):
            errs.append(f"卡身缺「## {s}」一节")
    moves, bad = parse_moves(body)
    for line in bad:
        errs.append(f"「能借的」这行不是招式格式：{line[:30]}…；照「- 【开头】公式｜示范「原文」｜适用：…」写，位置只用{'、'.join(SPOTS)}")
    if not moves and re.search(r"^## 能借的", body, re.M):
        errs.append("「能借的」一招都没有：至少写一招")
    for spot, rule, _, _ in moves:
        bare = re.sub(r"[^\u4e00-\u9fff]", "", rule)
        if len(bare) < 6 or any(v in rule for v in VAGUE) and len(re.sub("|".join(VAGUE), "", bare)) < 8:
            errs.append(f"招式是空话：【{spot}】{rule}——写成换上自己的料就能照做的话（先做什么、再做什么），别写「{'」「'.join(VAGUE[:3])}」这种评价")
    for q in QUOTE.findall(body):
        if len(q) > QUOTE_MAX:
            errs.append(f"原文摘引超过 {QUOTE_MAX} 字（{len(q)} 字）：「{q[:20]}…」；只放拆解和短摘引，不收全文")
    return errs, head


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=str(HERE))
    ap.add_argument("--min", type=int, default=10)
    ap.add_argument("--public-min", type=int, default=5)
    ap.add_argument("--strict", action="store_true", help="每格卡数不够就算错（发版前用）")
    ap.add_argument("--per-author", type=int, default=2, help="同一赛道同一平台里，同一账号最多几张卡")
    ap.add_argument("--原文", help="待拆文件夹的根（每篇一个子文件夹，有 content.md、meta.json）：给了就逐处核对卡里「」引用在原文里找不找得到")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root)
    srcs = {}
    if a.原文:
        for d in Path(a.原文).iterdir():
            if (d / "content.md").exists():
                txt = (d / "content.md").read_text(encoding="utf-8")
                for f in ("tikhub_comments.json",):
                    if (d / f).exists():
                        txt += (d / f).read_text(encoding="utf-8")
                m = re.search(r"^链接: (\S+)", (d / "任务.txt").read_text(encoding="utf-8"), re.M) if (d / "任务.txt").exists() else None
                if m:
                    srcs[m.group(1)] = txt
    cards = sorted((root / "爆款").glob("*/*/*.md"))
    seen, problems, count, public, authors, foreign = {}, {}, {}, {}, {}, {}
    for p in cards:
        errs, head = check_card(p, seen)
        if head and srcs.get(head.get("链接")):
            _, body = split_card(p.read_text(encoding="utf-8"))
            errs += [f"引用在原文里找不到：「{q[:40]}」——「」里只放原文原样（同音错字可以改），自己的概括、标签、公式不加「」" for q in quote_problems(body, srcs[head["链接"]])]
        if errs:
            problems[str(p.relative_to(root))] = errs
        if head and not errs:
            ak = (head["赛道"], head["平台"], head["账号"])
            authors.setdefault(ak, []).append(p.name)
            key = (head["赛道"], head["平台"])
            count[key] = count.get(key, 0) + 1
            if head.get("公开"):
                public[key] = public.get(key, 0) + 1
            if head.get("语言", "中文") != "中文":
                foreign[key] = foreign.get(key, 0) + 1
    for (t, pl, acc), names in authors.items():
        if len(names) > a.per_author:
            problems[f"{t}/{pl}"] = problems.get(f"{t}/{pl}", []) + [f"账号「{acc}」有 {len(names)} 张卡（最多 {a.per_author}）：{'、'.join(names)}；一个号最多收一两篇好的"]
    # 外文比例：抖音、公众号只收中文；X 的 AI 应用优先国外、不设上限；X 其余赛道外文最多三成
    for key, n in foreign.items():
        t, pl = key
        cap_ratio = 0 if pl in ("抖音", "视频号", "公众号") else (1.0 if t == "AI应用" else 0.3)
        if n > cap_ratio * count.get(key, 0):
            rule = "国内平台只收中文" if cap_ratio == 0 else "外文最多三成"
            problems[f"{t}/{pl}"] = problems.get(f"{t}/{pl}", []) + [f"外文卡 {n} 张（共 {count.get(key, 0)} 张）：{rule}"]
    short = []
    for t in TRACKS:
        for pl in PLATFORMS:
            n, pn = count.get((t, pl), 0), public.get((t, pl), 0)
            if n < a.min or pn < a.public_min:
                short.append(f"{t}/{pl}：合格卡 {n}/{a.min}，公开 {pn}/{a.public_min}")
    idx = root / "目录.md"
    newest = max((p.stat().st_mtime for p in cards + sorted((root / "收件箱").glob("*.md"))), default=0)
    stale = newest and (not idx.exists() or idx.stat().st_mtime < newest)
    if stale:
        short.insert(0, "目录过期：有卡或收件箱比目录.md 新，先跑 python3 建目录.py " + str(root))
    if a.json:
        print(json.dumps({"cards": len(cards), "problems": problems, "short": short}, ensure_ascii=False, indent=1))
    else:
        for f, errs in problems.items():
            for e in errs:
                print(f"❌ {f}：{e}")
        for s in short:
            print(("❌ " if a.strict else "⏳ ") + s)
        print(f"共 {len(cards)} 张卡｜有问题 {len(problems)} 张｜不够数 {sum(1 for s in short if not s.startswith('目录过期'))} 格")
    return 1 if problems or (a.strict and short) else 0


if __name__ == "__main__":
    sys.exit(main())

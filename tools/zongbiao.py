"""总表（花名册）：从成员文件读一位成员的登记项，生成岗位说明第 5 段「不做的事找谁」、统筹成员的分流表、首页的小标签／安装表／路线图。
引擎仓库的 tools/registry.py 扫各项目写注册表、改写生成物；validate.py 在开发仓库里查生成物是不是最新的。只用标准库，不读项目配置。

登记项写在成员 DESIGN.md 的「## 总表」一节，一行一项「- 键：值」：
  找我（必填，别人提到你时说的那件事）、第5段（必填，岗位说明第 5 段的模板，{找谁} 处由程序填）、
  称呼、只列（拼音逗号隔开，可写「同系列」；写「无」就一位不列；不写就只列同系列）、分隔（默认「；」）、分享卡、小标签颜色、路线图（首页路线图里的职能）、安装表备注。
生成区域在文件里用 <!-- 总表:名字 --> 和 <!-- /总表:名字 --> 圈出来，只改圈里的。"""
import json
import re
from pathlib import Path

REG = "shared/注册表.json"
FIELDS = ("称呼", "找我", "第5段", "只列", "分隔", "分享卡", "小标签颜色", "路线图", "安装表备注")
REGION = re.compile(r"(<!-- 总表:(\S+?) -->\n)(.*?)([ \t]*<!-- /总表:\2 -->)", re.S)


def _frontmatter(text):
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    out, key = {}, None
    for line in m.group(1).splitlines():
        kv = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if kv:
            key = kv.group(1)
            out[key] = "" if kv.group(2) in (">-", ">", "|") else kv.group(2)
        elif key:
            out[key] = (out[key] + " " + line.strip()).strip()
    return out


def design_fields(m):
    t = (m / "DESIGN.md").read_text(encoding="utf-8") if (m / "DESIGN.md").exists() else ""
    sec = re.search(r"^## 总表[^\n]*\n(.*?)(?=^## |\Z)", t, re.M | re.S)
    out = {}
    for ln in sec.group(1).splitlines() if sec else []:
        kv = re.match(r"^- (\S+?)：(.*)$", ln.strip())
        if kv and kv.group(1) in FIELDS:
            out[kv.group(1)] = kv.group(2).strip()
    return out


def entry(m, cfg):
    """一位成员的登记项（m 是成员文件夹，cfg 是它所在项目的 tools/config.json）。"""
    p = json.loads((m / "profile.json").read_text(encoding="utf-8"))
    head, duty = (p["name"].split("｜") + [""])[:2]
    cn, en = (re.split(r"\s*·\s*", head.strip()) + [""])[:2]
    f = design_fields(m)
    skills = []
    for s in sorted((m / "skills").glob("*/SKILL.md")):
        meta = _frontmatter(s.read_text(encoding="utf-8"))
        skills.append({"名": meta.get("name", s.parent.name), "说明": meta.get("description", "")})
    return {
        "拼音": m.name, "中文": cn, "英文": en, "称呼": f.get("称呼") or cn, "管什么": duty.strip(),
        "系列": cfg.get("系列", ""), "仓库": f"https://github.com/{cfg['github_owner']}/{cfg['repo']}",
        "版本": (m / "VERSION").read_text().strip() if (m / "VERSION").exists() else "",
        "找我": f.get("找我", ""), "第5段": f.get("第5段", ""),
        "只列": [x.strip() for x in re.split(r"[,，、]", f.get("只列", "")) if x.strip()],
        "分隔": f.get("分隔", "；"), "分享卡": f.get("分享卡", ""), "小标签颜色": f.get("小标签颜色", "555555"),
        "路线图": f.get("路线图") or duty.strip(), "安装表备注": f.get("安装表备注", ""),
        "技能": skills, "未发布": m.name in cfg.get("未发布", []),
    }


def problems(e):
    out = []
    if not e["找我"]:
        out.append("DESIGN.md「## 总表」没写「找我」")
    if "{找谁}" not in e["第5段"] and e["只列"] != ["无"]:
        out.append("DESIGN.md「## 总表」的「第5段」要有 {找谁}（一位都不列就写「只列：无」）")
    return out


def published(reg):
    """发布过的成员：项目 config.json「未发布」里的不进别人的第 5 段、分流表和首页（成员规范：只指向已经发布的成员）。"""
    return [x for x in reg["成员"] if not x.get("未发布")]


def find_who(e, reg):
    pick = e["只列"] or ["同系列"]  # 默认只列同系列：系列外的成员不进每次都带的岗位说明，要提的在「只列」里点名（全名单在统筹成员的分流表里）
    others = [x for x in published(reg) if x["拼音"] != e["拼音"] and (x["拼音"] in pick or ("同系列" in pick and x["系列"] == e["系列"]))]
    gap = lambda t: " " if t[-1:].isascii() and t[-1:].isalnum() else ""  # 「配成 Bot 找千机」：英文结尾补个空格
    return e["分隔"].join(f"{x['找我']}{gap(x['找我'])}找{x['称呼']}" for x in others)


def paragraph5(e, reg):
    return e["第5段"].replace("{找谁}", find_who(e, reg))


def regions(reg, repo, self_py, brand):
    """这一个项目（repo＝仓库地址）里各个生成区域该是什么内容。self_py：文件属于哪位成员（首页为空）。"""
    pub = published(reg)
    mine = [x for x in pub if x["仓库"] == repo]
    road = []
    for x in pub:
        if x["仓库"] == repo:
            road.append(f"| {x['系列']} | {x['称呼']} {x['英文']} | {x['路线图']} | ✅ v{x['版本']} |")
        else:
            road.append(f"| {x['系列']} | {x['称呼']} {x['英文']} | {x['管什么']} | ✅ v{x['版本']}，[另一个仓库]({x['仓库']}) |")
    return {
        "小标签": "\n".join(f'  <a href="CHANGELOG.md"><img alt="{x["称呼"]}" src="https://img.shields.io/badge/{x["称呼"]}-v{x["版本"]}-{x["小标签颜色"]}"></a>' for x in mine),
        "安装表": "\n".join(f"   | {x['称呼']} {x['英文']}{x['安装表备注']} | {x['分享卡']} |" for x in mine if x["分享卡"]),
        "路线图": "\n".join(road),
        "分流": "\n".join(f"| {x['找我']} | 可以找{brand}的{x['称呼']} |" for x in pub if x["拼音"] != self_py),
    }


def fill(text, wanted):
    """把圈出来的区域换成 wanted 里的内容；没圈的、wanted 里没有的不动。"""
    return REGION.sub(lambda mm: mm.group(1) + wanted[mm.group(2)] + "\n" + mm.group(4) if mm.group(2) in wanted else mm.group(0), text)


def set_paragraph5(ins, p5):
    paras = ins.split("\n\n")
    paras[-1] = p5
    return "\n\n".join(paras)


def targets(root, reg, repo, brand):
    """这个项目里要生成的 {文件: 生成后的全文}（只列会变的）；root 是项目根。"""
    out = {}
    by = {x["拼音"]: x for x in reg["成员"]}
    for m in sorted((root / "members").iterdir()):
        if m.name not in by or not (m / "profile.json").exists():
            continue
        prof = m / "profile.json"
        p = json.loads(prof.read_text(encoding="utf-8"))
        p["instructions"] = set_paragraph5(p["instructions"], paragraph5(by[m.name], reg))
        out[prof] = json.dumps(p, ensure_ascii=False, indent=2) + "\n"
        want = regions(reg, repo, m.name, brand)
        for f in sorted(m.glob("skills/*/*.md")):
            t = f.read_text(encoding="utf-8")
            if "<!-- 总表:" in t:
                out[f] = fill(t, want)
    readme = root / "发布素材" / "README.md"
    if readme.exists():
        out[readme] = fill(readme.read_text(encoding="utf-8"), regions(reg, repo, "", brand))
    return {f: t for f, t in out.items() if f.read_text(encoding="utf-8") != t}


def check(root, cfg, brand, errors):
    """开发仓库里查：本仓库成员的登记项和注册表一致、生成物是最新的。没有注册表或没有引擎锁（公开仓库）就不查。"""
    root = Path(root)
    if not (root / REG).exists() or not (root / "tools" / "引擎.lock.json").exists():
        return
    reg = json.loads((root / REG).read_text(encoding="utf-8"))
    by = {x["拼音"]: x for x in reg["成员"]}
    for m in sorted((root / "members").iterdir()):
        if not (m / "profile.json").exists() or not (m / "skills").is_dir():
            continue
        e = entry(m, cfg)
        for p in problems(e):
            errors.append(f"[registry] {m.name}: {p}")
        if by.get(m.name) != e:
            errors.append(f"[registry] {m.name}: 和注册表对不上（改了版本、名字、技能或 DESIGN.md 的总表）——在引擎仓库跑 python3 tools/registry.py")
            return
    repo = f"https://github.com/{cfg['github_owner']}/{cfg['repo']}"
    for f in targets(root, reg, repo, brand):
        errors.append(f"[registry] {f.relative_to(root)}: 生成的部分不是最新的——在引擎仓库跑 python3 tools/registry.py，不手改")

"""打包：把一位成员的文件做成 Bot 安装要用的三样东西，放进 members/<成员>/dist/。只用标准库。
- recipe.json：全部技能的完整内容（安装脚本和安装技能读它）
- template.json：Grok Bot 分享卡（只放安装、第一次见面两个技能，外加三条记忆：安装规矩、装完规矩、安装状态）
- install.sh、EXPORT.md：把占位符换成真实的仓库和版本
用法：python3 tools/pack.py [成员 ...]      加 --check 只核对 dist 是不是最新（CI 用），不写文件。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CONFIG, ROOT, parse_frontmatter  # noqa: E402


def placeholders(member):
    version = (ROOT / "members" / member / "VERSION").read_text().strip()
    return version, {"{{OWNER}}": CONFIG["github_owner"], "{{REPO}}": CONFIG["repo"], "{{VERSION}}": version,
                     "{{FEEDBACK}}": CONFIG["feedback_url"]}


def filled(path, table):
    text = path.read_text(encoding="utf-8")
    for key, value in table.items():
        text = text.replace(key, value)
    return text


def collect_skills(member, table):
    out = []
    for folder in sorted(p for p in (ROOT / "members" / member / "skills").iterdir() if p.is_dir()):
        body = filled(folder / "SKILL.md", table)
        meta = parse_frontmatter(body)
        cards = {}
        for extra in sorted(folder.rglob("*")):  # 子文件夹也收（如 paint-master/身份证/），键是相对路径
            rel = extra.relative_to(folder).as_posix()
            if extra.is_file() and rel != "SKILL.md" and not extra.name.startswith(".") and "__pycache__" not in rel:
                cards[rel] = filled(extra, table)
        out.append({"name": meta["name"], "description": meta["description"], "content": body, "files": cards})
    return out


def outputs(member):
    """返回 {要写的文件: 内容}。"""
    base = ROOT / "members" / member
    version, table = placeholders(member)
    skills = collect_skills(member, table)
    profile = json.loads(filled(base / "profile.json", table))
    # memory.md 里空一行隔开的每一段是一条记忆：安装规矩（不变）、安装状态（一行，装完整条换新）
    memory = [e.strip() for e in filled(base / "memory.md", table).split("\n\n") if e.strip()]
    tag = f"{member}-v{version}"
    recipe = dict(member=member, version=version, tag=tag, profile=profile, memory=memory, skills=skills,
                  repo="https://github.com/%s/%s" % (CONFIG["github_owner"], CONFIG["repo"]))
    on_card = {member + "-install", member + "-getting-started"}
    card = dict(
        profile=dict(name=profile["name"], description=profile["instructions"]),
        memory=[dict(kind="log", content=e) for e in memory],
        skills=[dict(name=s["name"], description=s["description"], content=s["content"]) for s in skills if s["name"] in on_card],
        gettingStarted=dict(skill=member + "-install"),
        _meta=dict(member=member, version=version, tag=tag, storefront=profile["description"]),
    )
    as_json = lambda obj: json.dumps(obj, ensure_ascii=False, indent=1) + "\n"
    files = {base / "dist" / "recipe.json": as_json(recipe), base / "dist" / "template.json": as_json(card)}
    for name in ("install.sh", "EXPORT.md"):
        if (base / name).exists():
            files[base / "dist" / name] = filled(base / name, table)
    return files


def main(argv):
    check_only = "--check" in argv
    members = [a for a in argv if not a.startswith("--")] or sorted(
        p.name for p in (ROOT / "members").iterdir() if (p / "skills").is_dir())
    outdated = []
    for member in members:
        for target, content in outputs(member).items():
            current = target.read_text(encoding="utf-8") if target.exists() else None
            if check_only:
                if current != content:
                    outdated.append(str(target.relative_to(ROOT)))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            print(f"写好 {target.relative_to(ROOT)}（{len(content.encode())} 字节）")
    if check_only:
        print("✅ dist 是最新的" if not outdated else "❌ 这些 dist 文件过期了，运行 python3 tools/pack.py：" + "、".join(outdated))
    return 1 if outdated else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""validate / pack / 各成员检查脚本和测试共用的小工具。只用标准库。"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
with open(ROOT / "tools" / "config.json", encoding="utf-8") as _fh:
    CONFIG = json.load(_fh)
BUDGET = json.loads((ROOT / "tools" / "预算.json").read_text(encoding="utf-8"))  # 引擎统一的预算（规划书第八节）
LIM = {"skill_bytes": BUDGET["技能字节"], "skill_warn_bytes": BUDGET["技能提醒字节"], "total_bytes": BUDGET["成员合计字节"],
       "profile_bytes": BUDGET["profile字节"], "description_chars": BUDGET["简介字"]}
BRAND = CONFIG["brand"]  # 品牌：名（开场白「欢迎来到…」）、出品方（简介里要写）、目录（~/.<目录>/、<目录>-backup）


# 公开仓库白名单：tools/publish.py 照它挑文件，tools/validate.py 照它扫——两边用同一份，平时检查不会比发布扫得少
PUBLIC_FILES = ["LICENSE", "CHANGELOG.md", ".gitignore", ".github/workflows/ci.yml", "shared",
                "tools/validate.py", "tools/预算.json", "tools/kernel.py", "tools/zongbiao.py", "tools/wuceng.py", "tools/pack.py", "tools/test_install.py", "tools/config.json", "tools/check_prompt.py", "tools/check_report.py",
                "tools/danzi.py", "tools/test_danzi.py", "tools/make_hero.py", "tools/common.py", "assets/hero.png", "assets/README.md", "assets/wechat-qr.jpg"] + CONFIG.get("public_files_extra", [])
MEMBER_ITEMS = ["profile.json", "memory.md", "VERSION", "install.sh", "skills", "examples", "dist"]
# 成员带的库和工具（有就挑，没有跳过）：只挑公开的部分，清单在 config.json 的 member_extras
MEMBER_EXTRAS = CONFIG.get("member_extras", [])
MEMBER_TEST_ITEMS = ["fixtures", "expected", "run_tests.py", "材料"]


LIB_GENERATED = {"目录.md", "索引.json", "统计.md"}  # 建目录.py 生成的；发布时在公开副本里只用公开卡重建


def is_unpublished(path):
    """不会原样发出去的库文件：没标「公开: true」的爆款卡（发布时删掉），和建目录.py 生成的目录、索引、统计、招式（发布时只用公开卡重建，重建后的由发布扫描查）。"""
    parts = Path(path).parts
    if "库" not in parts:
        return False
    if "爆款" in parts and str(path).endswith(".md"):
        head = Path(path).read_text(encoding="utf-8").split("\n---", 1)[0]
        return not __import__("re").search(r"^公开:\s*true\s*$", head, __import__("re").M)
    return Path(path).name in LIB_GENERATED or "招式" in parts


def is_material(rel):
    """考试材料是要处理的原始资料，原样保留，不做禁用词扫描（2026-10-22 定：扫描只扫自己写的说明，不碰资料原文）。"""
    parts = Path(rel).parts
    return "tests" in parts and "材料" in parts
RENAME = {"发布素材/README.md": "README.md", "发布素材/CONTRIBUTING.md": "CONTRIBUTING.md", **CONFIG.get("rename_extra", {})}



def exam_version(f):
    """考题第一行写的版本号（如「考题 v0.2」）；文件名不统一（考题.md、考题-v0.2.md、考题v0.2.md），按名字排会把旧版排到后面。"""
    m = re.search(r"v(\d+)\.(\d+)", f.read_text(encoding="utf-8").split("\n", 1)[0])
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

def public_picks(root, 含未发布=False):
    """要进公开仓库的 [(开发仓库里的源路径, 公开仓库里的相对路径)]，源可以是文件夹；不检查存不存在。
    在公开仓库里跑时，改名的那几份源文件不在，就直接用改名后的位置。
    config.json「未发布」里的成员（还在开发）发布时跳过；validate 传 含未发布=True 照样扫。"""
    root = Path(root)
    picks = [(root / f, f) for f in PUBLIC_FILES]
    picks += [((root / s) if (root / s).exists() else (root / d), d) for s, d in RENAME.items()]
    for m in sorted((root / "members").iterdir()):
        if not (m / "skills").is_dir() or (m.name in CONFIG.get("未发布", []) and not 含未发布):
            continue
        picks += [(m / i, f"members/{m.name}/{i}") for i in MEMBER_ITEMS]
        picks += [(m / i, f"members/{m.name}/{i}") for i in MEMBER_EXTRAS if (m / i).exists()]
        tests = sorted((m / "tests").glob("考题*.md"), key=exam_version)  # 公开的考题用最新一版（按第一行写的版本号，不按文件名排），统一叫 考题.md
        if tests:
            picks.append((tests[-1], f"members/{m.name}/tests/考题.md"))
        picks += [(m / "tests" / i, f"members/{m.name}/tests/{i}") for i in MEMBER_TEST_ITEMS]
    return picks


def parse_frontmatter(text):
    """解析 SKILL.md 开头的 name 和 description（支持 >- 折叠块）。"""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    meta, key, buf = {}, None, []
    for line in text[4:end].splitlines():
        m = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if m:
            if key:
                meta[key] = " ".join(buf).strip()
            key, val = m.group(1), m.group(2).strip()
            buf = [] if val in (">-", ">", "|") else [val]
        elif key:
            buf.append(line.strip())
    if key:
        meta[key] = " ".join(buf).strip()
    return meta


def norm(t):
    return "".join(t.lower().split())


def hash_hits(text, entries):
    """按哈希名单找词：命中只回显第一个字，不暴露完整词。"""
    t, want, hits = norm(text), {(e["len"], e["sha256"]) for e in entries}, set()
    for n in {e["len"] for e in entries}:
        for i in range(len(t) - n + 1):
            if (n, hashlib.sha256(t[i:i + n].encode()).hexdigest()) in want:
                hits.add(t[i:i + n][:1] + "…")
    return hits


def copy_minimal(root, dst, member, skip):
    """埋错用的副本只放这位成员＋公共部分（根目录文件、tools、shared、发布素材、assets）：埋的错都在这位身上，
    别的成员不用复制、不用检查——原来每例复制整个仓库，一位成员的测试要 30～70 秒。"""
    dst.mkdir(parents=True)
    for f in root.iterdir():
        if f.is_file():
            shutil.copy2(f, dst / f.name)
    for d in ("tools", "shared", "发布素材", "assets", ".github", f"members/{member}"):
        if (root / d).is_dir():
            shutil.copytree(root / d, dst / d, ignore=skip)


def run_negative_cases(member, cases, report):
    """反向用例：每个用例都在一份临时副本里埋一个错，然后跑检查脚本——它必须失败，并且报出这个类别。
    cases 是 [(类别, 埋错的函数), ...]；埋错的函数拿到副本的根目录。"""
    skip = shutil.ignore_patterns(".git", "__pycache__", "发布", "资料", "考试记录")
    has_list = (ROOT / "tools" / "scrub_hashes.json").exists()
    for tag, plant in cases:
        if tag == "private" and not has_list:
            print(f"（跳过「{tag}」：禁用词名单只在开发仓库里，公开仓库没有）")
            continue
        if tag == "export" and not (ROOT / "members" / member / "EXPORT.md").exists():
            print(f"（跳过「{tag}」：导出说明只在开发仓库里，公开仓库没有）")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            copy_root = Path(tmp) / "副本"
            copy_minimal(ROOT, copy_root, member, skip)
            plant(copy_root)
            done = subprocess.run([sys.executable, "tools/validate.py", "."], cwd=copy_root, capture_output=True, text=True)
            caught = done.returncode != 0 and ("[" + tag + "]") in done.stdout
            report(caught, f"埋了一个「{tag}」类的错，检查脚本拦住了")

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
LIM = CONFIG["limits"]


# 公开仓库白名单：tools/publish.py 照它挑文件，tools/validate.py 照它扫——两边用同一份，平时检查不会比发布扫得少
PUBLIC_FILES = ["LICENSE", "CHANGELOG.md", ".gitignore", ".github/workflows/ci.yml", "shared",
                "tools/validate.py", "tools/pack.py", "tools/test_install.py", "tools/config.json", "tools/check_prompt.py", "tools/check_report.py",
                "tools/make_hero.py", "tools/common.py", "assets/hero.png", "assets/hero-底图.png", "assets/hero-底图.html", "assets/README.md", "assets/wechat-qr.jpg"]
MEMBER_ITEMS = ["profile.json", "memory.md", "VERSION", "install.sh", "skills", "examples", "dist"]
# 成员带的库和工具（有就挑，没有跳过）：只挑公开的部分；候选-自用、待拆、归档这些自用的不进
MEMBER_EXTRAS = ["库/README.md", "库/schema", "库/平台", "库/手法", "库/表达", "库/爆款", "库/样卡",
                 "库/check_library.py", "库/test_check_library.py", "库/建目录.py", "库/test_建目录.py", "库/雷达.py", "库/test_雷达.py",
                 "库/目录.md", "库/招式", "库/索引.json", "库/统计.md", "抓取", "库/平台规格.md", "库/规格表.json", "库/场景", "库/品牌元素", "库/参考",
                 "库/视频规格.md", "库/视频规格.json", "库/分镜模板.md", "库/风格预设.md", "库/坑清单.md", "库/真人姿势.md", "库/口播剪辑卡.md",
                 "库/色彩表", "库/音乐"]
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
    """考试材料是要处理的原始资料，原样保留，不做禁用词扫描（杨先生 2026-10-22 定：扫描只扫自己写的说明，不碰资料原文）。"""
    parts = Path(rel).parts
    return "tests" in parts and "材料" in parts
RENAME = {"发布素材/README.md": "README.md", "发布素材/CONTRIBUTING.md": "CONTRIBUTING.md"}


def public_picks(root):
    """要进公开仓库的 [(开发仓库里的源路径, 公开仓库里的相对路径)]，源可以是文件夹；不检查存不存在。
    在公开仓库里跑时，改名的那几份源文件不在，就直接用改名后的位置。"""
    root = Path(root)
    picks = [(root / f, f) for f in PUBLIC_FILES]
    picks += [((root / s) if (root / s).exists() else (root / d), d) for s, d in RENAME.items()]
    for m in sorted((root / "members").iterdir()):
        if not (m / "skills").is_dir():
            continue
        picks += [(m / i, f"members/{m.name}/{i}") for i in MEMBER_ITEMS]
        picks += [(m / i, f"members/{m.name}/{i}") for i in MEMBER_EXTRAS if (m / i).exists()]
        tests = sorted((m / "tests").glob("考题*.md"))  # 公开的考题用最新一版，统一叫 考题.md
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


def run_negative_cases(member, cases, report):
    """反向用例：每个用例都在一份临时副本里埋一个错，然后跑检查脚本——它必须失败，并且报出这个类别。
    cases 是 [(类别, 埋错的函数), ...]；埋错的函数拿到副本的根目录。"""
    skip = shutil.ignore_patterns(".git", "__pycache__", "发布", "资料", "考试记录")
    has_list = (ROOT / "tools" / "scrub_hashes.json").exists()
    for tag, plant in cases:
        if tag == "private" and not has_list:
            print(f"（跳过「{tag}」：禁用词名单只在开发仓库里，公开仓库没有）")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            copy_root = Path(tmp) / "副本"
            shutil.copytree(ROOT, copy_root, ignore=skip)
            plant(copy_root)
            done = subprocess.run([sys.executable, "tools/validate.py", "."], cwd=copy_root, capture_output=True, text=True)
            caught = done.returncode != 0 and ("[" + tag + "]") in done.stdout
            report(caught, f"埋了一个「{tag}」类的错，检查脚本拦住了")

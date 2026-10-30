"""仓库检查（规矩见 shared/成员规范.md 第五节）。只用标准库。
用法：python3 tools/validate.py [仓库根目录]   有错误时退出码为 1，逐条列出。"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BRAND, BUDGET, CONFIG, LIM, MEMBER_EXTRAS, hash_hits, is_material, is_unpublished, norm, parse_frontmatter, public_picks  # noqa: E402
import kernel  # noqa: E402  引擎副本核对
import zongbiao  # noqa: E402  总表：生成物是不是最新的
import wuceng  # noqa: E402  五层上岗检查（shared/岗位说明写法.md 第五节）

GREETING = f"您好，欢迎来到{BRAND['名']}。我是"
REQUIRED = ("install", "update", "getting-started")
LESSON = re.compile(r"第[一二三四五六七八九十0-9]+课")
CARD = re.compile(r"^> 卡类：(事实|口径)(?:｜核对 (\d{4}-\d{2}-\d{2})｜下次核对 (\d{4}-\d{2}-\d{2}))?", re.M)


def over(member, ver, item, msg, errors):
    """超了预算：登记了豁免（同一位、同一项、还是登记时的版本）只提醒，否则报错。豁免在 config.json 的「预算豁免」。"""
    if any(x.get("成员") == member and x.get("项") == item and x.get("版本") == ver for x in CONFIG.get("预算豁免", [])):
        print(f"⚠️ [budget] {msg}（已登记豁免，只在 v{ver}；升版本前要改好）")
    else:
        errors.append(f"[budget] {msg}")


def public_files(root):
    """装进 Bot、放进公开仓库的文件：和 tools/publish.py 用同一份白名单（common.public_picks），
    发布会挑走的每个文件都扫，不论后缀（.md、.json、.py、.sh……）；开发仓库里的内部文档不扫。"""
    seen = set()
    for src, _ in [(root / "README.md", ""), (root / "CHANGELOG.md", ""), (root / "CONTRIBUTING.md", "")] + public_picks(root, 含未发布=True):
        for f in sorted(src.rglob("*")) if src.is_dir() else [src]:
            if f.is_file() and f not in seen and f.name != ".DS_Store" and "__pycache__" not in f.parts:
                seen.add(f)
                yield f


def check_member(m, root, errors):
    name, total = m.name, 0
    ver = (m / "VERSION").read_text().strip() if (m / "VERSION").exists() else ""
    if not re.fullmatch(r"\d+\.\d+\.\d+", ver):
        errors.append(f"[version] {name}: VERSION 缺失或不是 x.y.z")
    for readme in (root / "发布素材" / "README.md", root / "README.md"):  # 首页手动安装命令的标签要跟当前版本（v0.2.1 首页还写着 v0.2.0）
        if readme.exists():
            text = readme.read_text(encoding="utf-8")
            for old in set(re.findall(rf"{name}-v(\d+\.\d+\.\d+)", text)) - {ver}:
                errors.append(f"[version] {readme.relative_to(root)} 里写的是 {name}-v{old}，当前 VERSION 是 {ver}")
            # 小标签、路线图这些写着成员名字的行，版本号也要跟当前版本。首页一行列一位的按中文名认；
            # 一行列好几位、或系列名和成员中文名撞了的，config.json 写 readme_version_by: "en"，按英文名认表格行、路线图那段、小标签
            full = json.loads((m / "profile.json").read_text(encoding="utf-8")).get("name", "") if (m / "profile.json").exists() else ""
            cn, en = (re.split(r"\s*·\s*", re.split(r"\s*｜", full)[0]) + [""])[:2]
            cn = cn.strip()
            if CONFIG.get("readme_version_by") == "en":
                segs = [ln for ln in text.splitlines() if ln.startswith("|") and f" {en} " in ln] if en else []
                segs += [s for ln in text.splitlines() if ln.startswith("- **Roadmap") for s in re.split(r"[;；]|\. ", ln) if en and f" {en}," in s]
                segs += [f"小标签 v{v}" for v in re.findall(rf"badge/{re.escape(cn)}-v(\d+\.\d+\.\d+)-", text)] if cn else []
            else:
                segs = [ln for ln in text.splitlines() if cn and cn in ln and "English" not in ln]
            for seg in segs:
                for old in set(re.findall(r"(?<![\w.-])v(\d+\.\d+\.\d+)", seg)) - {ver}:
                    errors.append(f"[version] {readme.relative_to(root)} 写{cn}的地方还是 v{old}，当前 VERSION 是 {ver}：{seg.strip()[:40]}")
    prof = m / "profile.json"
    if not prof.exists():
        errors.append(f"[profile] {name}: 缺 profile.json")
    else:
        b = prof.stat().st_size
        total += b
        p = json.loads(prof.read_text(encoding="utf-8"))
        for k in ("name", "description", "intro", "instructions"):
            if not p.get(k):
                errors.append(f"[profile] {name}: profile.json 缺 {k}")
        if len(p.get("description", "")) > LIM["description_chars"]:
            errors.append(f"[profile] {name}: description 超过 {LIM['description_chars']} 字符")
        if "出品" in p.get("name", "") or p.get("name", "").count("｜") != 1:
            errors.append(f"[profile] {name}: 名字只写「中文名 · 英文名 ｜ 管什么」，不加出品方（2026-10-22 定）")
        if BRAND["出品方"] not in p.get("description", ""):
            errors.append(f"[profile] {name}: 简介里要写明「{BRAND['出品方']}」出品")
        if b > LIM["profile_bytes"]:  # 和别的预算项一样认豁免：新成员发布、别人第 5 段加一句时，存量超线的跟各自下个小版本改
            over(name, ver, "profile字节", f"{name}: profile.json {b} 字节 > {LIM['profile_bytes']}", errors)
    if (m / "memory.md").exists():
        total += (m / "memory.md").stat().st_size
    skills = sorted(d for d in (m / "skills").iterdir() if d.is_dir())
    names, corpus = {d.name for d in skills}, {}
    # 导出说明（EXPORT.md）里写的卡外技能数要等于实际技能数减 2（卡里只带安装、第一次见面两个）
    exp = m / "EXPORT.md"
    for n in re.findall(r"另外 (\d+) 个技能", exp.read_text(encoding="utf-8") if exp.exists() else ""):
        if int(n) != len(names) - 2:
            errors.append(f"[export] {name}: EXPORT.md 写「另外 {n} 个技能」，实际应为 {len(names) - 2}")
    # 岗位说明（shared/岗位说明写法.md 第五节）
    if prof.exists():
        ins = json.loads(prof.read_text(encoding="utf-8")).get("instructions", "")
        if not ins.startswith("你是"):
            errors.append(f"[instructions] {name}: 岗位说明要以「你是」开头")
        for s in sorted(names - {f"{name}-install", f"{name}-update"}):
            if s not in ins:
                errors.append(f"[instructions] {name}: 岗位说明没派到技能 {s}")
        # 装法三处一致（shared/安装写法.md）：岗位说明、安装记录、安装技能都带同一条安装命令
        cmd = f"{{{{REPO}}}}/{name}-v{{{{VERSION}}}}/members/{name}/dist/install.sh"
        places = {"岗位说明": ins, "memory.md": (m / "memory.md").read_text(encoding="utf-8") if (m / "memory.md").exists() else "",
                  f"{name}-install": (m / "skills" / f"{name}-install" / "SKILL.md").read_text(encoding="utf-8")
                  if (m / "skills" / f"{name}-install" / "SKILL.md").exists() else ""}
        for where, text in places.items():
            if cmd not in text:
                errors.append(f"[install] {name}: {where} 里没有标准安装命令（见 shared/安装写法.md）")
            # 只升不降（shared/安装写法.md 第 4½ 条）：版本号写死在导入时的岗位说明里，写成「不是这一版就装」会在更新后劝主人装回旧版
            if re.search(r"不是 ?(这一版|" + re.escape(name) + r"-v)", text):
                errors.append(f"[install] {name}: {where} 写了「不是某版就装」，要改成「没装或比这一版旧才装」（只升不降）")
            if "不装回" not in text:
                errors.append(f"[install] {name}: {where} 没写「比这一版新就不装回旧版」（只升不降）")
        # 三条记忆（shared/安装写法.md）：平台记忆改不准一条里的几格、一条最多 500 字，所以分「安装规矩」「装完规矩」（不变）和一行「安装状态」（装完、更新完整条换新）
        pj = json.loads(prof.read_text(encoding="utf-8"))
        m_cn = re.match(r"你是(.+?)（", pj.get("instructions", ""))  # 中文名以岗位说明第一句为准，Bot 名字可以另起
        cn = m_cn.group(1) if m_cn else pj.get("name", "").split(" · ")[0]
        entries = [e.strip() for e in places["memory.md"].split("\n\n") if e.strip()]
        if len(entries) != 3 or not entries[0].startswith(f"【{cn}安装规矩】") or not entries[1].startswith(f"【{cn}装完规矩】") or not re.fullmatch(
                f"【{cn}安装状态】现在装的：[^\n｜]+｜上回查新版：[^\n｜]+｜更新方式：[^\n｜]+", entries[2]):
            errors.append(f"[install] {name}: memory.md 要正好三段——「【{cn}安装规矩】…」「【{cn}装完规矩】…」和一行「【{cn}安装状态】现在装的：…｜上回查新版：…｜更新方式：…」")
        # 平台一条记忆最多 500 字，超了后半截悄悄截掉（2026-10-27 实测）；按填好地址和版本号算，留 20 字余量
        for e in entries:
            n = len(e.replace("{{OWNER}}", CONFIG["github_owner"]).replace("{{REPO}}", CONFIG["repo"]).replace("{{VERSION}}", "10.10.10"))
            if n > 480:
                errors.append(f"[install] {name}: memory.md 里「{e[:12]}…」填好后 {n} 字，一条记忆不能超过 480 字（平台到 500 字就截掉）")
        if "安装记录" in ins:
            errors.append(f"[install] {name}: 岗位说明还写着「安装记录」，改成「安装状态」")
        upd = m / "skills" / f"{name}-update" / "SKILL.md"
        for where, text in ((f"{name}-install", places[f"{name}-install"]), (f"{name}-update", upd.read_text(encoding="utf-8") if upd.exists() else "")):
            if f"「{cn}安装状态」" not in text or "整条删掉" not in text:
                errors.append(f"[install] {name}: {where} 要写明把「{cn}安装状态」整条删掉、再写一条新的")
        # 三种基本能力（shared/安装写法.md 第 7～9 条）：体检修复、自动更新的选项和定时任务、反馈由主人自己提交
        utext = upd.read_text(encoding="utf-8") if upd.exists() else ""
        if f"{name}/dist/install.sh | bash -s -- --check" not in places[f"{name}-install"]:
            errors.append(f"[heal] {name}: {name}-install 要有体检命令（install.sh 加 --check）")
        if "更新方式" not in places[f"{name}-install"] or "定时任务" not in utext or "每周检查" not in utext:
            errors.append(f"[update] {name}: 要在装完问更新方式，并在 {name}-update 写定时任务和每周检查")
        if "{{FEEDBACK}}" not in utext or "不替主人提交" not in utext or "隐私" not in utext:
            errors.append(f"[feedback] {name}: {name}-update 要写反馈单：去隐私、给 {{{{FEEDBACK}}}} 链接、不替主人提交")
        for n in re.findall(r"不到 ?(\d+) ?个", ins):
            if int(n) != len(names):
                errors.append(f"[instructions] {name}: 岗位说明写「不到 {n} 个」，实际有 {len(names)} 个技能")
    # 开场白（shared/成员规范.md 第三节）：安装技能、入门技能、安装记录三处都要写着
    for where in (m / "skills" / f"{name}-install" / "SKILL.md", m / "skills" / f"{name}-getting-started" / "SKILL.md", m / "memory.md"):
        if where.exists() and GREETING not in where.read_text(encoding="utf-8"):
            errors.append(f"[greeting] {name}: {where.relative_to(m)} 里没有开场白「{GREETING}…」")
    for d in skills:
        f = d / "SKILL.md"
        if not f.exists():
            errors.append(f"[frontmatter] {d.name}: 没有 SKILL.md")
            continue
        text = f.read_text(encoding="utf-8")
        corpus[d.name] = text
        if d.name.endswith("-getting-started") and "## 演练模式" not in text:
            errors.append(f"[rehearsal] {d.name}: 入门技能缺「## 演练模式」一节（见 shared/成员规范.md）")
        if not d.name.endswith(("-install", "-update")) and re.search(r"写进记忆|存进记忆|写入记忆", text) and "演练" not in text:
            errors.append(f"[rehearsal] {d.name}: 会写记忆，但没写演练模式下只打印")
        meta = parse_frontmatter(text)
        if not meta or not meta.get("name") or not meta.get("description"):
            errors.append(f"[frontmatter] {d.name}: 缺 name 或 description")
        else:
            if meta["name"] != d.name:
                errors.append(f"[frontmatter] {d.name}: 头信息里的名字「{meta['name']}」跟文件夹名对不上")
            if not meta["name"].startswith(name + "-"):
                errors.append(f"[frontmatter] {d.name}: name 必须以 {name}- 开头")
            if len(meta["description"]) > BUDGET["技能说明字"]:  # 技能目录每次都带、平台还会截断，说明要短
                over(name, ver, "技能说明字", f"{d.name}: 说明 {len(meta['description'])} 字，上限 {BUDGET['技能说明字']}", errors)
        for extra in d.iterdir():
            if extra.is_file():
                total += extra.stat().st_size
                if extra.name == "SKILL.md" and extra.stat().st_size > LIM["skill_bytes"]:
                    errors.append(f"[budget] {d.name}/SKILL.md {extra.stat().st_size} 字节 > {LIM['skill_bytes']}")
                elif extra.name == "SKILL.md" and extra.stat().st_size > LIM.get("skill_warn_bytes", 1 << 30):
                    print(f"⚠️ [budget] {d.name}/SKILL.md {extra.stat().st_size} 字节，超过建议的 {LIM['skill_warn_bytes']}（只提醒；硬上限 {LIM['skill_bytes']}）")
            if extra.is_file() and extra.suffix == ".md" and extra.name != "SKILL.md":
                corpus[f"{d.name}/{extra.name}"] = extra.read_text(encoding="utf-8")
    # 骨架没补完（tools/new_member.py 生成的「【待写】」）
    for f in [prof, m / "memory.md", m / "EXPORT.md"] + [p for d in skills for p in d.glob("*.md")]:
        if f.exists() and "【待写】" in f.read_text(encoding="utf-8"):
            errors.append(f"[todo] {name}: {f.relative_to(m)} 里还有「【待写】」")
    # 示例（shared/成员规范.md）：一位虚构主人从头走到尾＋一份全流程演练，开头都标「示例数据（虚构主人）」
    ex = sorted((m / "examples").glob("*.md")) if (m / "examples").is_dir() else []
    if not any("全流程" in f.name for f in ex) or len(ex) < 3:
        errors.append(f"[examples] {name}: 示例要有一位虚构主人走一遍（至少 2 份）＋一份「全流程」演练")
    for f in ex:
        head = "\n".join(f.read_text(encoding="utf-8").splitlines()[:5])
        if "示例数据" not in head and "【示例】" not in head:
            errors.append(f"[examples] {name}/examples/{f.name}: 开头没标「示例数据（虚构主人）」")
    for f in sorted(m.glob("skills/**/*卡*.md")):  # 知识六层：卡标卡类，事实卡带核对日期（到期由体检列出，这里只查写没写对）
        k = CARD.search(f.read_text(encoding="utf-8")[:800])
        if not k or (k[1] == "事实" and not (k[3] and k[3] > k[2])):
            errors.append(f"[card] {name}/{f.relative_to(m)}: 标题下面要写「> 卡类：事实｜核对 日期｜下次核对 日期」（下次晚于核对）或「> 卡类：口径｜…」")
    if len(names) > BUDGET["技能数"]:
        over(name, ver, "技能数", f"{name}: {len(names)} 个技能，上限 {BUDGET['技能数']}（超了拆成员，或把技能并成「技能＋卡」）", errors)
    tpl = m / "dist" / "template.json"
    if tpl.exists():  # 每次对话都带的：指令（分享卡描述）＋自己的记忆＋账号共用记忆（config.json 的「共用记忆字」，实量）
        t = json.loads(tpl.read_text(encoding="utf-8"))
        n = len(t["_meta"]["storefront"]) + 2 + len(t["profile"]["description"]) + sum(len(x["content"]) for x in t["memory"]) + CONFIG.get("共用记忆字", 0)
        if n > BUDGET["Bot常驻字"]:
            over(name, ver, "Bot常驻字", f"{name}: 每次对话都带 {n} 字，上限 {BUDGET['Bot常驻字']}", errors)
    for r in REQUIRED:
        if f"{name}-{r}" not in names:
            errors.append(f"[skills] {name}: 缺必备技能 {name}-{r}")
    if total > LIM["total_bytes"]:
        errors.append(f"[budget] {name}: 合计 {total} 字节 > {LIM['total_bytes']}")
    # 交叉引用：提到的本成员技能名、反引号里的 .md 文件都要存在
    # 只在成员自己的包、共用规范里找（不算考试记录、资料里碰巧同名的文件——那些不随包发出去，公开版里会对不上）
    files = {p.name for d in (root / "members", root / "shared") if d.is_dir() for p in d.rglob("*.md")}
    files |= {n for n in ("README.md", "CHANGELOG.md", "CONTRIBUTING.md") if (root / n).exists()}  # 根目录会公开的这几份也算
    pool = dict(corpus)
    if (m / "memory.md").exists():
        pool["memory.md"] = (m / "memory.md").read_text(encoding="utf-8")
    for src, text in pool.items():
        mentioned = set(re.findall(r"\b" + re.escape(name) + r"-[a-z]{2,}(?:-[a-z]+)*\b", text))
        for ref in mentioned:
            if ref not in names:
                errors.append(f"[xref] {src}: 引用了不存在的技能 {ref}")
        for ref in set(re.findall(r"`([^`/\s]+\.md)`", text)):
            if ref not in files:
                errors.append(f"[xref] {src}: 引用了不存在的文件 {ref}")
        # 装好的公共库里的文件：要在发布白名单里（不然公开仓库没有）、也要写在安装脚本里（不然装不到主人那）——v0.3 口播剪辑卡漏过一次
        inst = (m / "install.sh").read_text(encoding="utf-8") if (m / "install.sh").exists() else ""
        for ref in set(re.findall(r"~/\." + re.escape(BRAND["目录"]) + "/" + re.escape(name) + r"/库/([^`/\s）)，。]+)", text)):
            if not (m / "库" / ref).exists():
                errors.append(f"[xref] {src}: 引用了库里不存在的 {ref}")
            elif f"库/{ref}" not in MEMBER_EXTRAS or (inst and "库" in inst and ref not in inst):
                errors.append(f"[library] {src}: 引用的 库/{ref} 没登记全（tools/common.py 的 MEMBER_EXTRAS、members/{name}/install.sh 的拷贝清单都要有）")
    return total


def main(root):
    root = Path(root).resolve()
    errors = []
    hp = root / "tools" / "scrub_hashes.json"
    entries = json.loads(hp.read_text(encoding="utf-8"))["private"] if hp.exists() else []
    # 两份名单要一致：发布扫描用 禁用词.txt 的明文，这里用 scrub_hashes.json 的哈希；明文里有、哈希里没有的词，这里就会漏
    wp = root / "tools" / "禁用词.txt"
    if wp.exists():
        have = {(e["len"], e["sha256"]) for e in entries}
        for i, w in enumerate((x for x in wp.read_text(encoding="utf-8").splitlines() if x.strip()), 1):
            n = norm(w)
            if (len(n), hashlib.sha256(n.encode()).hexdigest()) not in have:
                errors.append(f"[private] tools/禁用词.txt 第 {i} 个词（首字「{n[:1]}」）不在 scrub_hashes.json 里，用 tools/scrub_hash.py 补上")
    for f in public_files(root):
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # 图片等二进制文件
        rel = f.relative_to(root)
        if is_material(rel) or is_unpublished(f):
            continue  # 没公开的卡和生成的目录不会原样发出去（发布时删掉或只用公开卡重建，重建后的由 publish.py 扫）
        if entries and hash_hits(text, entries):
            errors.append(f"[private] {rel}: 公开文件里有名单上的词（只显示首字）：{'、'.join(sorted(hash_hits(text, entries)))}")
        if LESSON.search(text):
            errors.append(f"[private] {rel}: 公开文件里有「第几课」")
    totals = {}
    for m in sorted((root / "members").iterdir()):
        if (m / "skills").is_dir():
            totals[m.name] = check_member(m, root, errors)
            wuceng.check(m, errors)
    # 借用：从别的项目原样借来的文件，要和正本一字不差；正本不在本机（如 CI）就跳过
    for b in CONFIG.get("borrow", []):
        copy, src = root / b["copy"], (root / b["source"]).resolve()
        if not copy.exists():
            errors.append(f"[borrow] {b['copy']}: 登记了借用，包里却没有这个文件")
        elif not src.exists():
            print(f"ℹ️ [borrow] 正本 {b['source']} 不在这台机器上，跳过比对")
        elif copy.read_bytes() != src.read_bytes():
            errors.append(f"[borrow] {b['copy']}: 和正本 {b['source']} 不一样——正本改了要原样复制过来，不在复制件上改")
    kernel.check(root, errors, CONFIG.get("brand"))
    lf = root / kernel.LOCK
    if lf.exists():  # 引擎自己的预算：工具代码行数、规范份数和大小（只算引擎同步来的副本）
        locked = json.loads(lf.read_text(encoding="utf-8"))["文件"]
        n = sum(len((root / r).read_text(encoding="utf-8").splitlines()) for r in locked if r.endswith(".py") and (root / r).exists())
        if n > BUDGET["引擎代码行"]:
            errors.append(f"[budget] 引擎工具代码 {n} 行，上限 {BUDGET['引擎代码行']}（引擎自己不许变胖）")
        docs = [r for r in locked if r.startswith("shared/") and r.endswith(".md")]
        if len(docs) > BUDGET["引擎规范份数"]:
            errors.append(f"[budget] 引擎规范 {len(docs)} 份，上限 {BUDGET['引擎规范份数']}")
        for r in docs:
            if (root / r).exists() and (root / r).stat().st_size > BUDGET["引擎规范字节"]:
                errors.append(f"[budget] {r} {(root / r).stat().st_size} 字节，引擎规范每份上限 {BUDGET['引擎规范字节']}")
    zongbiao.check(root, CONFIG, BRAND["名"], errors)
    for e in errors:
        print("❌", e)
    print(("✅ 全部通过" if not errors else f"共 {len(errors)} 处问题") + "｜" + "，".join(f"{k} {v} 字节" for k, v in totals.items()))
    return 1 if errors else 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent.parent)
    sys.exit(main(target))

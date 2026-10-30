"""五层上岗检查（规矩见 shared/岗位说明写法.md 第五节）。只用标准库；validate.py 调用，三个仓库放同一份。
还没改造的成员（没有 进度模板.md）只打印一条提醒；有了模板就按错误拦。"""
import json
import re
from pathlib import Path

_B = json.loads((Path(__file__).resolve().parent / "预算.json").read_text(encoding="utf-8"))
MAX_RULES = _B["做法条数"]        # 做法最多几条
MAX_STATE_CHARS = _B["进度字"]    # 进度模板（进度文件）最多几个字
NOT_WORK = ("install", "update", "getting-started")


def rules_count(ins):
    """「做法：」那一段按「；」「。」数条数。"""
    para = next((p for p in ins.split("\n\n") if p.strip().startswith("做法：")), None)
    if para is None:
        return None
    body = para.strip()[len("做法："):]
    return len([x for x in re.split(r"[；。]", body) if x.strip()])


def problems(m):
    """返回这位成员不合五层的地方（每条一句）。"""
    name, out = m.name, []
    prof = m / "profile.json"
    ins = json.loads(prof.read_text(encoding="utf-8")).get("instructions", "") if prof.exists() else ""
    paras = [p for p in ins.split("\n\n") if p.strip()]
    if len(paras) < 2 or "先读进度文件" not in paras[1] or "说一句停在哪" not in paras[1]:
        out.append("岗位说明第 2 段没写「每次接活（含主人说接着、到哪了）先读进度文件、说一句停在哪」")
    if len(paras) < 3 or "先打开对应技能" not in paras[2]:
        out.append("岗位说明第 3 段没写「接到活先打开对应技能照着做」")
    n = rules_count(ins)
    if n is None:
        out.append("岗位说明没有「做法：」一段")
    elif n > MAX_RULES:
        out.append(f"「做法：」一段 {n} 条，最多 {MAX_RULES} 条")
    tpl = m / "进度模板.md"
    if not tpl.exists():
        out.append("缺 进度模板.md")
    elif len(tpl.read_text(encoding="utf-8")) > MAX_STATE_CHARS:
        out.append(f"进度模板.md 超过 {MAX_STATE_CHARS} 字")
    for d in sorted((m / "skills").iterdir()):
        f = d / "SKILL.md"
        if not d.is_dir() or not f.exists() or any(d.name == f"{name}-{x}" for x in NOT_WORK):
            continue
        text = f.read_text(encoding="utf-8")
        for need in ("先读进度", "写进度"):
            if not re.search(rf"(?<!不){need}", text):  # 「不写进度」不算写了（10-29 有一位成员的技能这样漏过）
                out.append(f"{d.name} 没写「{need}」")
    design = m / "DESIGN.md"
    body = design.read_text(encoding="utf-8") if design.exists() else ""
    sec = re.search(r"^## 硬闸[^\n]*\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    if not sec:
        out.append("DESIGN.md 没有「## 硬闸」一节")
    else:
        rows = [ln for ln in sec.group(1).splitlines() if ln.strip().startswith("- ")]
        if not rows:
            out.append("DESIGN.md「## 硬闸」一节是空的")
        for ln in rows:
            if "→" not in ln or not ln.split("→", 1)[1].strip():
                out.append(f"硬闸「{ln.strip()[2:20]}…」没写谁拦（格式：不许做的事 → 谁拦）")
    return out


def check(m, errors):
    found = problems(m)
    if not (m / "进度模板.md").exists():
        if found:
            print(f"⚠️ [wuceng] {m.name}: 还没改成五层上岗，差 {len(found)} 处（只提醒；加了 进度模板.md 就按错误拦）")
        return
    for p in found:
        errors.append(f"[wuceng] {m.name}: {p}（见 shared/岗位说明写法.md）")

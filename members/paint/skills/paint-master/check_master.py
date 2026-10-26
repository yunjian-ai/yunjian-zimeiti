"""查一个母版文件夹齐不齐、能不能入库（只用标准库）。
用法：python3 check_master.py <母版文件夹> [<母版文件夹> …]
身份证「状态」是「草稿」时只查结构；是「入库」时还要：不许改没有占位、3 张样张、验收.md 最后结论「全对，入库」。
有问题打印 ❌ 并以 1 退出；只有提醒（⚠️）照样算过。"""
import re
import sys
from pathlib import Path

KINDS = ["商品", "人物", "场景", "风格", "品牌", "版式", "服装道具", "光影镜头"]
IMG = {".png", ".jpg", ".jpeg", ".webp"}
NEED_BOARD = {"商品", "人物", "场景"}  # 风格用代表图、品牌用原件，不生成母版板
NEED_SAMPLES = {"商品", "人物", "场景", "风格"}


def images(d):
    return [p for p in d.iterdir() if p.suffix.lower() in IMG] if d.is_dir() else []


def parse(text):
    head, body = {}, text
    if text.startswith("---\n") and "\n---\n" in text[4:]:
        end = text.index("\n---\n", 4)
        for line in text[4:end].splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                head[k.strip()] = v.strip()
        body = text[end + 5:]
    sections, cur = {}, None
    for line in body.splitlines():
        if line.startswith("## "):
            cur = line[3:].split("（")[0].strip()
            sections[cur] = []
        elif cur and line.strip().startswith("- "):
            sections[cur].append(line.strip()[2:])
    return head, sections


def check(folder):
    f = Path(folder)
    errs, warns = [], []
    idp = f / "身份证.md"
    if not idp.exists():
        return [f"{f.name}: 没有 身份证.md"], warns
    head, sec = parse(idp.read_text(encoding="utf-8"))
    kind, state = head.get("种类"), head.get("状态")
    for k in ["种类", "名字", "版本", "状态"]:
        if not head.get(k):
            errs.append(f"身份证卡头缺「{k}」")
    if kind and kind not in KINDS:
        errs.append(f"种类「{kind}」不在 {KINDS} 里")
    if state not in ("草稿", "入库"):
        errs.append(f"状态只能是「草稿」或「入库」，写的是「{state}」")
    if not images(f / "原件"):
        errs.append("原件/ 里没有主人给的原图")
    if kind in NEED_BOARD and not (f / "母版板.png").exists() and not images(f / "单张"):
        errs.append("没有 母版板.png，也没有 单张/")
    if "不许改" not in sec:
        errs.append("身份证少了「## 不许改」一节")
    elif not sec["不许改"]:
        errs.append("「不许改」一条都没写")
    if "推测" not in sec:
        errs.append("身份证少了「## 推测」一节（没有推测项也要留这一节，写「无」）")
    if not (f / "版本.md").exists():
        errs.append("没有 版本.md")
    if state == "入库":
        holes = [x for x in sec.get("不许改", []) if "【" in x]
        if holes:
            errs.append(f"入库了「不许改」还有没填的：{holes[0][:30]}")
        if kind in NEED_SAMPLES and len(images(f / "样张")) < 3:
            errs.append(f"入库要 3 张验收样张，样张/ 里只有 {len(images(f / '样张'))} 张")
        if kind in NEED_SAMPLES:
            v = f / "验收.md"
            lines = [x.strip() for x in v.read_text(encoding="utf-8").splitlines() if x.strip()] if v.exists() else []
            if not lines or not re.search(r"结论[:：]\s*全对，入库", lines[-1]):
                errs.append("验收.md 最后一行不是「结论：全对，入库」——没验过不能入库")
        open_guess = [x for x in sec.get("推测", []) if x.endswith("推测")]
        if open_guess:
            warns.append(f"{len(open_guess)} 条推测主人还没看过（入库后给主人看一眼，确认了改「主人确认」）")
    return errs, warns


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    bad = 0
    for folder in argv:
        errs, warns = check(folder)
        for e in errs:
            print(f"❌ {Path(folder).name}: {e}")
        for w in warns:
            print(f"⚠️ {Path(folder).name}: {w}")
        bad += bool(errs)
        print(f"{'✅' if not errs else '❌'} {Path(folder).name}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

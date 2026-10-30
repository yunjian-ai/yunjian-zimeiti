"""协同单子检查（规矩见 shared/协同协议.md、shared/演进环.md）：把 Markdown 里的「### 交接单 · …」「### 回执 · …」「### 收件 · …」解析出来，照 JSON Schema 校验，再查总字数。
用法：python3 tools/danzi.py <文件或文件夹>… [--查产物]   有错误时退出码为 1。
  --查产物：回执「放在哪」里用反引号写的路径（相对单子所在的文件夹，可带 *）要真有文件，不在就报错（收活先查产物在不在）。
装了 jsonschema 就用它校验；没装（Bot 环境只有标准库）用下面的小校验，test_danzi.py 用随机单子比两者结论一致。
Schema 先找同目录（借用进成员包时），再找 ../shared/（项目里）。"""
import glob
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KINDS = ("交接单", "回执", "收件")
HEAD = re.compile(r"(?m)^### (交接单|回执|收件)\s*(?:[·・]\s*(.*))?$")


def schema(kind):
    for d in (HERE, HERE.parent / "shared"):
        if (d / f"{kind}.schema.json").exists():
            return json.loads((d / f"{kind}.schema.json").read_text(encoding="utf-8"))
    raise FileNotFoundError(f"找不到 {kind}.schema.json")


def parse(text):
    """[(种类, 字段字典, 原文)]。栏只认 Schema 里有的名字；不缩进的「- 栏名（说明）：」开新一栏，其余行接在上一栏后面；遇到下一个标题结束。"""
    out = []
    for m in HEAD.finditer(text):
        kind = m.group(1)
        names = set(schema(kind)["properties"]) - {"标题"}
        body = re.split(r"(?m)^#{1,6} ", text[m.end():])[0]
        fields, cur = {"标题": (m.group(2) or "").strip()}, None
        for ln in body.splitlines():
            f = re.match(r"-\s*([^\s：:（(]+)(?:[（(][^）)\n]*[）)])?\s*[：:]\s*(.*)$", ln)
            if f and f.group(1) in names:
                cur = f.group(1)
                fields[cur] = f.group(2).strip()
            elif cur and ln.strip():
                fields[cur] = (fields[cur] + "\n" + ln.strip()).strip()
        out.append((kind, fields, (m.group(0) + body).strip()))
    return out


def mini_errors(sch, obj):
    """小校验：只支持本协议 Schema 用到的几样（object、required、additionalProperties: false、string、minLength、pattern）。"""
    errs = [f"缺栏：{k}" for k in sch.get("required", []) if k not in obj]
    props = sch.get("properties", {})
    for k, v in obj.items():
        p = props.get(k)
        if p is None:
            if sch.get("additionalProperties") is False:
                errs.append(f"多了不认识的栏：{k}")
            continue
        if not isinstance(v, str):
            errs.append(f"{k} 要是文字")
        elif len(v) < p.get("minLength", 0):
            errs.append(f"{k} 是空的")
        elif "pattern" in p and not re.search(p["pattern"], v):
            errs.append(f"{k} 不合格式（要有 {p['pattern']}）")
    return errs


def schema_errors(sch, obj):
    try:
        import jsonschema
    except ImportError:
        return mini_errors(sch, obj)
    return [f"{'.'.join(map(str, e.path)) or '整张'}：{e.message}" for e in jsonschema.Draft202012Validator(sch).iter_errors(obj)]


def check_text(text, where=""):
    errs = []
    for kind, fields, raw in parse(text):
        sch = schema(kind)
        tag = f"[{kind}] {where}「{fields['标题'] or '没写标题'}」"
        errs += [f"{tag} {e}" for e in schema_errors(sch, fields)]
        if len(raw) > sch.get("x-上限字", 10 ** 9):
            errs.append(f"{tag} {len(raw)} 字，上限 {sch['x-上限字']}（产物写进文件，单子里只写路径）")
    return errs


def missing_products(text, base, where=""):
    """回执「放在哪」写的产物不在（路径相对单子所在文件夹，可带 *）。"""
    errs = []
    for kind, fields, _ in parse(text):
        for p in re.findall(r"`([^`]+)`", fields.get("放在哪", "")) if kind == "回执" else []:
            if not glob.glob(str(base / p)):
                errs.append(f"[回执] {where}「{fields['标题'] or '没写标题'}」放在哪：`{p}` 不在（相对 {base}）")
    return errs


def main(args):
    look = "--查产物" in args
    args = [a for a in args if a != "--查产物"] or ["."]
    files = [f for a in args for f in (sorted(Path(a).rglob("*.md")) if Path(a).is_dir() else [Path(a)])]
    errs, n = [], 0
    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")
        n += len(parse(text))
        errs += check_text(text, f"{f}：") + (missing_products(text, f.parent, f"{f}：") if look else [])
    for e in errs:
        print("❌", e)
    if not n:  # 一叠没整理的原话：0 张不算通过（10-30 考试反馈）
        print("⚠️ 一张单子都没找到：标题要写成「### 交接单／回执／收件 · …」；0 张不算通过")
        return 1
    print(("✅ " if not errs else f"共 {len(errs)} 处问题｜") + f"查了 {n} 张单子")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["."]))

"""对试金交出的一份报告做机械检查（规则卡第六节的格式里能用程序验证的部分）。只用标准库。
输入 JSON：{"report": "报告全文"}。输出问题代码：NO_VERDICT / BAD_VERDICT / NO_STANDARD / ISSUE_NO_LEVEL /
ISSUE_NO_EVIDENCE / ISSUE_NO_FIX / VERDICT_CONFLICT / MISSING_GAPS。用法：python3 tools/check_report.py 文件.json ..."""
import json
import re
import sys
from pathlib import Path

VERDICTS = ("可以交", "改完再交", "要重做", "判不了")
ISSUE = re.compile(r"^\s*\d+[.、]\s*(.*)$")


def check(d):
    r, issues = d.get("report", ""), []
    m = re.search(r"【结论】\s*(.+)", r)
    verdict = m.group(1).strip() if m else ""
    if not m:
        issues.append({"code": "NO_VERDICT", "hit": "没有【结论】"})
    elif verdict not in VERDICTS:
        issues.append({"code": "BAD_VERDICT", "hit": verdict[:20]})
    if "【依据的标准】" not in r:
        issues.append({"code": "NO_STANDARD", "hit": "没写依据的标准"})
    block = r.split("【问题清单】", 1)[1] if "【问题清单】" in r else ""
    block = re.split(r"\n【", block)[0]
    severe = False
    for line in block.splitlines():
        mm = ISSUE.match(line)
        if not mm:
            continue
        body = mm.group(1)
        level = next((lv for lv in ("❌", "⚠️", "💡") if body.startswith(lv)), None)
        if not level:
            issues.append({"code": "ISSUE_NO_LEVEL", "hit": body[:20]})
            continue
        severe |= level == "❌"
        if "在哪" not in body or "看到" not in body:
            issues.append({"code": "ISSUE_NO_EVIDENCE", "hit": body[:20]})
        if level in ("❌", "⚠️") and "改法" not in body:
            issues.append({"code": "ISSUE_NO_FIX", "hit": body[:20]})
    if verdict == "可以交" and severe:
        issues.append({"code": "VERDICT_CONFLICT", "hit": "有 ❌ 却判可以交"})
    if verdict == "判不了" and "【还缺什么】" not in r:
        issues.append({"code": "MISSING_GAPS", "hit": "判不了却没写还缺什么"})
    return issues


if __name__ == "__main__":
    for name in sys.argv[1:]:
        found = check(json.loads(Path(name).read_text(encoding="utf-8")))
        print(name, "没问题" if not found else "、".join(f"{x['code']}（{x['hit']}）" for x in found))

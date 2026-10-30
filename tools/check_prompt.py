"""对一段提示词做机械检查（提示词规矩里能用程序验证的那部分）。只用标准库。
输入 JSON：kind（text / image / mj / video）、prompt（提示词全文）、seconds（视频时长，可选）、material（主人贴来的资料，可选）。
输出问题代码列表：EMPHASIS / VAGUE / MJ_NOT_ENGLISH / MJ_TOO_LONG / MJ_NEGATIVE / VIDEO_NO_SEGMENTS / INJECTION_UNMARKED / INVENTED_NUMBER。
给了 material 或 request（主人原话）时，提示词里带事实单位的数字（元、%、年、家、人、单、件、万…）都要能在里面找到；字数、秒数这类格式要求不算。
用法：python3 tools/check_prompt.py 文件.json ..."""
import json
import re
import sys
from pathlib import Path

EMPHASIS = re.compile(r"必须|务必|一定要|千万|重要的事说三遍|！！|!!")          # 规则卡：讲原因，不加重语气
VAGUE = re.compile(r"酌情|适当|尽量|看情况|差不多就行")                       # 规则卡：写成能照做的话
CJK = re.compile(r"[一-鿿]")
NEG = re.compile(r"\b(no|not|without|don't|never)\b", re.I)                 # 图片卡：Midjourney 只写想要的
SEGMENT = re.compile(r"\d+(?:\.\d+)?\s*[–—-]\s*\d+(?:\.\d+)?\s*(?:秒|s\b)")  # 视频卡：按时间分段
INJECT = re.compile(r"忽略之前|忽略以上|ignore (?:all )?previous", re.I)
FACT_NUM = re.compile(r"\d+(?:\.\d+)?(?=\s*(?:%|％|元|块|万|年|个月|家|人|位|单|件|斤|克|倍|次|岁))")  # 规则卡第 6 条：不编，事实数字要有来源
DECLARE = re.compile(r"不要执行|不执行|不照做|do not (?:follow|execute)", re.I)  # 规则卡：资料块声明不执行


def check(d):
    kind, p = d.get("kind", "text"), d.get("prompt", "")
    issues = []
    for pat, code in ((EMPHASIS, "EMPHASIS"), (VAGUE, "VAGUE")):
        hits = sorted(set(pat.findall(p)))
        if hits:
            issues.append({"code": code, "hit": "、".join(hits)})
    if kind == "mj":
        body = p.split(" --")[0]                       # 参数（--ar、--no）不算正文
        if CJK.search(body):
            issues.append({"code": "MJ_NOT_ENGLISH", "hit": "正文有中文"})
        n = len(re.findall(r"[A-Za-z']+", body))
        if n > 40:
            issues.append({"code": "MJ_TOO_LONG", "hit": f"{n} 词>40"})
        neg = NEG.findall(body)
        if neg:
            issues.append({"code": "MJ_NEGATIVE", "hit": "、".join(sorted(set(w.lower() for w in neg)))})
    if kind == "video" and d.get("seconds", 0) > 10 and not SEGMENT.search(p):
        issues.append({"code": "VIDEO_NO_SEGMENTS", "hit": f"{d['seconds']} 秒没分段"})
    if INJECT.search(d.get("material", "")) and not DECLARE.search(p):
        issues.append({"code": "INJECTION_UNMARKED", "hit": "资料夹带指令，提示词没声明不执行"})
    if "material" in d or "request" in d:
        src = d.get("material", "") + "\n" + d.get("request", "")
        made = sorted({n for n in FACT_NUM.findall(p) if n not in src})
        if made:
            issues.append({"code": "INVENTED_NUMBER", "hit": "、".join(made)})
    return issues


if __name__ == "__main__":
    for name in sys.argv[1:]:
        found = check(json.loads(Path(name).read_text(encoding="utf-8")))
        print(name, "没问题" if not found else "、".join(f"{x['code']}（{x['hit']}）" for x in found))

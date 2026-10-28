"""带货片合规体检：查分镜.md 的台词、字幕、花字和 剪辑.json 的价格、行动号召。只报不改——平台内容类规矩只提醒、附出处，由主人定。
查五样：①绝对化用语（广告法第九条）②效果、数字说法有没有出处（对照项目的 卖点.md：主人确认过的卖点和吊牌原文）
       ③站外导流（微信号、二维码、网址）④虚假稀缺（「最后 3 件」「原价 X 今天 Y」）⑤念不念得完（每句 ≤20 字、每刀 ≤2 句、总字数 ≤ 时长×4.5）
用法：python3 合规.py <项目>        退出码 1＝有 ❌（要改了才能出片），0＝只有 ⚠️ 或全过"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "reel-board"))
import 镜头表  # noqa: E402

绝对化 = ["全网最", "史上最", "最好", "最佳", "最低", "最便宜", "最高级", "最舒服", "最好看", "最受欢迎", "第一", "顶级", "极品",
       "国家级", "世界级", "首选", "唯一", "万能", "绝对", "100%有效", "百分百", "永久", "无敌", "王牌", "销量冠军"]
效果 = ["零扎", "不扎", "不起球", "不掉色", "不缩水", "不变形", "不过敏", "抗菌", "抑菌", "防螨", "防水", "速干", "保暖", "显瘦", "瘦",
      "敏感肌", "孕妇", "婴儿", "治", "疗", "保健", "纯羊毛", "纯棉", "真丝", "进口", "原产", "手工"]
导流 = [r"微信", r"[vV]信", r"\bvx\b", r"加[vV]", r"wx", r"二维码", r"扫码", r"私信", r"https?://", r"www\.", r"\.com\b", r"\.cn\b",
      r"1[3-9]\d{9}", r"[A-Za-z][A-Za-z0-9_\-]{5,}_\d+"]
稀缺 = [r"最后\s*[一二两三四五\d]+\s*(?:单|件|个|份|名)", r"(?:仅剩|只剩)\s*[一二两三四五\d]+", r"原价\s*\d+.{0,8}(?:今天|现在)\s*\d+",
      r"(?:马上|立刻)\s*(?:涨价|恢复原价)"]
出处 = "《广告法》第九条（不得使用「国家级」「最高级」「最佳」等用语）；平台规则只提醒，主人定"


def 去标(t):
    return re.sub(r"\*\*", "", t or "").strip()


def 查(P):
    表 = 镜头表.读镜头表(P / "分镜.md")
    if not 表:
        sys.exit(f"NO_TABLE：{P / '分镜.md'} 里没有镜头表")
    卖点 = (P / "卖点.md").read_text(encoding="utf-8") if (P / "卖点.md").exists() else ""
    卖点 = "\n".join(l for l in 卖点.splitlines() if not re.search(r"不写|不能写|别写|禁止|不许|不要写|不用", l))  # 「不能写：纯羊毛」这种行不算出处（Bot 实测发现）
    坏, 提醒 = [], []
    设置 = {}
    if (P / "剪辑.json").exists():
        import json
        设置 = json.loads((P / "剪辑.json").read_text(encoding="utf-8"))
    格们 = []
    for s in 表:
        for 列 in ("台词", "字幕", "花字"):
            t = 去标(s.get(列, ""))
            if t and t not in ("—", "-", "无"):
                格们.append((f"第 {s['号']} 刀{列}", t))
    for 键 in ("价格", "行动", "贴纸"):
        if 设置.get(键):
            格们.append((f"剪辑.json 的{键}", str(设置[键])))
    for 在, t in 格们:
        中 = [w for w in 绝对化 if w in t]
        for w in [w for w in 中 if not any(w != x and w in x for x in 中)]:  # 「最好」「最好看」都中只报长的
            坏.append((在, f"「{w}」是绝对化用语（{t}）", f"换成能证明的说法，比如具体做法、实拍对比；{出处}"))
        for pat in 导流:
            m = re.search(pat, t, re.I)
            if m:
                坏.append((在, f"像站外导流（「{m[0]}」）", "抖音、视频号画面和配音里不放微信号、二维码、网址；下单引导写「点下方小黄车」"))
                break
        for pat in 稀缺:
            m = re.search(pat, t)
            if m:
                提醒.append((在, f"「{m[0]}」像制造紧迫感", "是真的才写，写清时间和数量；不确定就删"))
        for w in 效果:
            if w in t and w not in 卖点:
                提醒.append((在, f"「{w}」是效果或材质说法，卖点.md 里没有出处", "问主人有没有测过、吊牌怎么写；没有就删或换成看得见的画面"))
        for n in re.findall(r"\d+(?:\.\d+)?\s*[%％]|\d+(?:\.\d+)?\s*(?:克|g|小时|天|年|件|颗|针|cm|厘米)", t):
            if re.sub(r"\s", "", n) not in re.sub(r"\s", "", 卖点):
                坏.append((在, f"数字「{n}」卖点.md 和吊牌里没有", "数字只用主人给的和吊牌原文；对不上就改成吊牌上的数，或删掉"))
    总字 = 0
    for s in 表:
        t = 去标(s.get("台词", ""))
        if not t or t in ("—", "-", "无"):
            continue
        总字 += len(re.sub(r"[，。！？、；：,.!?;:\s]", "", t))
        句们 = [x for x in re.split(r"[。！？!?]", t) if x.strip()]
        if len(句们) > 2:
            提醒.append((f"第 {s['号']} 刀台词", f"{len(句们)} 句，一刀最多 2 句", "拆到下一刀，或删一句"))
        for x in re.split(r"[，。！？,!?；;]", t):
            if len(x.strip()) > 20:
                提醒.append((f"第 {s['号']} 刀台词", f"「{x.strip()}」{len(x.strip())} 字一口气念不完", "拆成两句，一句一件事"))
    时长 = 表[-1]["出"]
    if 总字 and 总字 > 时长 * 4.5 + 3:
        提醒.append(("全片", f"台词 {总字} 字，{时长:.0f} 秒约念 {时长 * 4.5:.0f} 字", "删台词，不要把语速加到两成以上"))
    if not 卖点:
        提醒.append(("项目", "没有 卖点.md", "把主人确认过的卖点和吊牌原文写进 卖点.md，数字和效果才有地方对照"))
    return 坏, 提醒


def main():
    ap = argparse.ArgumentParser(description="带货片合规体检")
    ap.add_argument("项目")
    P = Path(ap.parse_args().项目).resolve()
    坏, 提醒 = 查(P)
    for 在, 问题, 改法 in 坏:
        print(f"❌ {在}：{问题} → {改法}")
    for 在, 问题, 改法 in 提醒:
        print(f"⚠️ {在}：{问题} → {改法}")
    print(f"\n毛病 {len(坏)} 条、提醒 {len(提醒)} 条。只报不改：拿去问主人改不改，主人定了再改分镜、重新配音。"
          if 坏 or 提醒 else "PASS：台词、字幕、花字没查出合规问题")
    sys.exit(1 if 坏 else 0)


if __name__ == "__main__":
    main()

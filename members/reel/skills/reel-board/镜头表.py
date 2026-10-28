"""读分镜.md 里的镜头表、视频/可用窗口.md 里的窗口表（切点、体检、成片、检查都用它）。只用标准库。
镜头表认表头关键字，列的顺序、多几列少几列都行：# ｜进–出（秒）｜景别｜场景／机位｜镜头动作｜人物动作｜表情／酷动作｜主体位置｜大字｜素材｜备注
带货片再加四列：台词（配音念的）｜字幕（**关键词**高亮，「／」分段）｜花字（≤10 字）｜卖点（这一刀证明哪个卖点）
口播片（剪辑方案）：# ｜进–出（秒）｜段｜台词（照稿，==重点== **花字** 原样）｜画面（主人出镜／插入什么）｜素材（「—」＝主人出镜，写文件＝插入）｜花字｜备注
  一句一行；连着几行写同一个素材＝一处插入。由 `python3 镜头表.py 口播 <项目>` 从 口播/清剪.json 生成。
可用窗口表：号｜文件｜窗口（秒）｜问题｜处理"""
import re
from pathlib import Path

镜头表头 = ["#", "进–出（秒）", "景别", "场景／机位", "镜头动作", "人物动作", "表情／酷动作", "主体位置", "大字", "素材", "备注"]
带货表头 = ["#", "进–出（秒）", "景别", "镜头动作", "画面", "台词", "字幕", "花字", "卖点", "素材", "备注"]
窗口表头 = ["号", "文件", "窗口（秒）", "问题", "处理"]
口播表头 = ["#", "进–出（秒）", "段", "台词", "画面", "素材", "花字", "备注"]
_认 = [("号", ("#", "号")), ("时间", ("进", "时间")), ("景别", ("景别",)), ("场景", ("场景", "机位")),
      ("镜头动作", ("镜头动作", "运镜", "镜头")), ("表情", ("表情", "酷动作")), ("人物动作", ("人物", "人做", "动作")),
      ("主体位置", ("主体", "位置")), ("段", ("段",)), ("台词", ("台词", "配音", "口播")), ("字幕", ("字幕",)), ("花字", ("花字",)),
      ("卖点", ("卖点", "证明")), ("大字", ("大字", "字")), ("素材", ("素材", "文件")), ("窗口", ("窗口",)),
      ("问题", ("问题",)), ("处理", ("处理",)), ("备注", ("备注",))]
_区间 = re.compile(r"(-?\d+(?:\.\d+)?)\s*[–—\-~～至到]+\s*(-?\d+(?:\.\d+)?)")


def 区间(text):
    """'0.000–1.714' → (0.0, 1.714)；认 – - ~ ～ 至 到。读不出返回 None。"""
    m = _区间.search(text or "")
    return (float(m[1]), float(m[2])) if m else None


def _列名(头):
    out, 用过 = [], set()
    for h in 头:
        名 = h
        for key, kws in _认:
            if key not in 用过 and any(k in h for k in kws):
                名 = key
                break
        用过.add(名)
        out.append(名)
    return out


def 读表(path, 要有=("号",)):
    """读 Markdown 文件里第一张表头含「要有」那几列的表，返回 [{列名: 文字, "行": 行号}]。"""
    if not Path(path).exists():
        import sys
        sys.exit(f"NO_FILE：{path} 还没有（分镜.md 由 reel-board 出，可用窗口.md 由 reel-motion 写）")
    行们 = Path(path).read_text(encoding="utf-8").splitlines()
    for i, l in enumerate(行们):
        if not l.strip().startswith("|") or i + 1 >= len(行们) or not re.match(r"^\s*\|[\s:\-|]+\|\s*$", 行们[i + 1]):
            continue
        名 = _列名([c.strip() for c in l.strip().strip("|").split("|")])
        if not all(k in 名 for k in 要有):
            continue
        out = []
        for j in range(i + 2, len(行们)):
            r = 行们[j].strip()
            if not r.startswith("|"):
                break
            格 = [c.strip() for c in r.strip("|").split("|")]
            d = dict(zip(名, 格 + [""] * (len(名) - len(格))))
            d["行"] = j + 1
            out.append(d)
        return out
    return []


def 读镜头表(path):
    """[{号, 进, 出, 景别, 镜头动作, 人物动作, 表情, 主体位置, 大字, 素材, 场景, 备注, 行}]，按进点排；带货片还有 台词、字幕、花字、卖点。"""
    out = []
    for d in 读表(path, ("号", "时间")):
        r = 区间(d.get("时间", ""))
        if not r:
            continue
        d["进"], d["出"] = r
        d["号"] = re.sub(r"[^\d]", "", d.get("号", "")) or str(len(out) + 1)
        out.append(d)
    return sorted(out, key=lambda d: d["进"])


def 读窗口表(path):
    """{号: {文件, 起, 止, 问题, 处理}}；窗口写「不能用」「重出」的不收。"""
    out = {}
    if not Path(path).exists():
        return out
    for d in 读表(path, ("号", "窗口")):
        r = 区间(d.get("窗口", ""))
        号 = re.sub(r"[^\d]", "", d.get("号", ""))
        if r and 号:
            out[str(int(号))] = {"文件": d.get("素材") or d.get("文件", ""), "起": r[0], "止": r[1],
                                "问题": d.get("问题", ""), "处理": d.get("处理", "")}
    return out


def 写表(头, 行们):
    out = ["| " + " | ".join(头) + " |", "|" + "---|" * len(头)]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in 行们]
    return "\n".join(out)


def 改时间(path, 新):
    """新 = {号: (进, 出)}：只改镜头表「进–出（秒）」那一格，别的字一个不动。返回改了几行。"""
    行们 = Path(path).read_text(encoding="utf-8").splitlines()
    表 = 读表(path, ("号", "时间"))
    if not 表:
        return 0
    头行 = 表[0]["行"] - 3
    名 = _列名([c.strip() for c in 行们[头行].strip().strip("|").split("|")])
    第 = 名.index("时间")
    n = 0
    for d in 表:
        号 = re.sub(r"[^\d]", "", d.get("号", ""))
        if 号 not in 新:
            continue
        格 = 行们[d["行"] - 1].strip().strip("|").split("|")
        进, 出 = 新[号]
        格[第] = f" {进:.2f}–{出:.2f} "
        行们[d["行"] - 1] = "|" + "|".join(格) + "|"
        n += 1
    Path(path).write_text("\n".join(行们) + "\n", encoding="utf-8")
    return n


def 口播方案(P, 覆盖=False):
    """口播/清剪.json → 分镜.md（剪辑方案初稿）：一句一行，时间从这句开口到下一句开口；每段第一行带执笔〔画面〕提示，素材先都写「—」（主人出镜）。
    只有声音（不露脸）的，素材写「【待填】」——每句都要配画面。"""
    import json
    import sys
    清 = Path(P) / "口播" / "清剪.json"
    if not 清.exists():
        sys.exit("NO_ROUGH：还没清剪。先跑 reel-cut/清剪.py 剪，主人点头粗剪后再排画面")
    out = Path(P) / "分镜.md"
    if out.exists() and not 覆盖:
        sys.exit(f"EXISTS：{out} 已经有了（可能主人改过）。真要重新生成加 --覆盖")
    j = json.loads(清.read_text(encoding="utf-8"))
    句们, 行们, 上段 = j["句"], [], None
    for i, s in enumerate(句们):
        进 = 0.0 if i == 0 else s["起"]
        出 = 句们[i + 1]["起"] if i + 1 < len(句们) else j["新长"]
        画面 = "主人出镜" if j["有画面"] else "【待填】"
        if s["段"] != 上段 and s.get("提示"):
            画面 += f"（稿子提示：{s['提示']}）"
        备注 = ("钩子：3 秒内不插画面，要脸" if j["有画面"] else "钩子：放最抓人的画面") if i == 0 else ("稿子里没有、主人多说的" if s.get("多出来的") else "")
        行们.append([i + 1, f"{进:.2f}–{出:.2f}", s["段"], s.get("原文") or s["字幕"], 画面, "—" if j["有画面"] else "【待填】", "—", 备注])
        上段 = s["段"]
    头 = f"# 剪辑方案（口播片，{j['新长']:.1f} 秒）\n\n> 一句一行。要插画面：「素材」写文件（主人的照片视频、静帧/xx.png、卡片），连着几行同一个素材＝一处插入；" \
        "一段最多插 2 处、一处 1.5～4 秒；钩子 3 秒内不插。字幕照「台词」，==重点== 黄色、**花字** 黄色放大。\n\n"
    out.write_text(头 + 写表(口播表头, 行们) + "\n", encoding="utf-8")
    return out, len(行们)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="镜头表工具")
    ap.add_argument("做", choices=["口播"])
    ap.add_argument("项目")
    ap.add_argument("--覆盖", action="store_true")
    g = ap.parse_args()
    f, n = 口播方案(g.项目, g.覆盖)
    print(f"OK {f}：{n} 句一行。下一步：照稿子提示和主人素材填「画面」「素材」，再跑 体检.py 查插入画面规矩")

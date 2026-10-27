"""镜头表体检：把「好看的卡点片」的规矩变成能逐条查的，每条毛病给刀号和改法。只用标准库。
用法：python3 体检.py 分镜.md [--拍子 音乐/拍子.json] [--查素材]
  不给 --拍子：先找同一项目里的 音乐/拍子.json；再没有，就从表上方写的「NNN 拍／分」按从 0 秒起的匀速拍算
查：时间铺满不留缝 ｜ 切点在拍上 ｜ 一刀太短太长 ｜ 素材重复 ｜ 相邻景别相同 ｜ 对口型 ｜ 360 度环绕 ｜ 一刀几个镜头动作 ｜
    姿势不像真人（叉腿、劈叉、深蹲）｜ 大字一刀一个词、不跨刀 ｜ 大字中英混用 ｜ 开头 2 秒钩子 ｜ 大落点那刀
有毛病退出码 1。体检只报不改，改不改、怎么改问主人。"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import 镜头表  # noqa: E402

运镜词 = {"推": "推", "拉": "拉", "移": "移", "摇": "摇", "升": "升", "降": "降", "跟": "跟", "环绕": "环绕", "绕": "环绕",
       "甩": "甩", "旋": "旋转", "变焦": "变焦", "俯冲": "俯冲", "orbit": "环绕", "dolly": "推", "pan": "摇"}
HAN = re.compile(r"[一-鿿]")


def 拍网格(path, 拍子路径):
    p = Path(拍子路径) if 拍子路径 else Path(path).parent / "音乐" / "拍子.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        return d["拍"], d.get("大落点", []), f"按 {p.name}"
    m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*拍\s*[／/]\s*分", Path(path).read_text(encoding="utf-8"))
    if m:
        周期 = 60 / float(m[1])
        return [round(k * 周期, 3) for k in range(int(600 / 周期))], [], f"按表上写的 {m[1]} 拍／分、从 0 秒起算"
    return [], [], "没有拍子（切点在不在拍上没查）"


def 镜头动作数(text):
    t = re.sub(r"(低|高|平|仰|俯)机位|手持|固定|定镜", "", text or "").lower()
    出现 = sorted((t.find(k), v) for k, v in 运镜词.items() if k in t)
    return list(dict.fromkeys(v for _, v in 出现))  # 按出现先后


def 大字词(text):
    t = re.split(r"[（(]", text or "")[0].strip().strip("「」\"'")
    if not t or t in ("—", "-", "无", "【待填】"):
        return t, []
    return t, (t.split() if not HAN.search(t) else [t])


def 查(path, 拍子路径=None, 查素材=False):
    表 = 镜头表.读镜头表(path)
    if not 表:
        sys.exit(f"NO_TABLE：{path} 里没找到镜头表（要有「#」和「进–出（秒）」两列）")
    拍, 落点, 拍来源 = 拍网格(path, 拍子路径)
    坏, 提醒 = [], []
    在拍上 = lambda t: not 拍 or any(abs(t - b) <= 0.07 for b in 拍)  # noqa: E731
    总长 = 表[-1]["出"]
    if abs(表[0]["进"]) > 0.01:
        坏.append(("1", f"第一刀从 {表[0]['进']} 秒开始，前面空着", "第一刀改成从 0 秒起"))
    for x, y in zip(表, 表[1:]):
        if abs(x["出"] - y["进"]) > 0.01:
            坏.append((y["号"], f"和上一刀之间{'有缝' if y['进'] > x['出'] else '重叠'}（{x['出']} → {y['进']}）", "上一刀的出点和这一刀的进点写成同一个数"))
    用过 = {}
    for i, s in enumerate(表):
        号, 长 = s["号"], s["出"] - s["进"]
        if i and not 在拍上(s["进"]):
            近 = min(拍, key=lambda b: abs(b - s["进"]))
            坏.append((号, f"切点 {s['进']} 秒不在拍上", f"挪到最近的拍 {近:.3f} 秒"))
        if 长 < 0.4:
            坏.append((号, f"只有 {长:.2f} 秒，太短看不清", "并进前后一刀，或拉到至少一拍"))
        elif 长 < 0.6:
            提醒.append((号, f"只有 {长:.2f} 秒", "快段连切可以，单独一刀就并进前后一刀"))
        elif 长 > 4.5 and i != len(表) - 1:
            提醒.append((号, f"一刀 {长:.1f} 秒，卡点片里会拖", "拆成两刀，或换个镜头动作更明显的"))
        素材 = s.get("素材", "").strip()
        if 素材 and 素材 not in ("—", "-", "无"):
            if 素材 in 用过:
                坏.append((号, f"素材 {素材} 和第 {用过[素材]} 刀重复", "换一条新素材；同一条要用就写不同的起点"))
            用过.setdefault(素材, 号)
            if 查素材 and not (Path(path).parent / 素材).exists():
                提醒.append((号, f"素材 {素材} 还没有", "出完视频再剪"))
        if i and s.get("景别") and s.get("景别") == 表[i - 1].get("景别") and "待填" not in s["景别"]:
            坏.append((号, f"和上一刀景别都是「{s['景别']}」", "隔开：远、中、特写交替（比如这刀改近景或远景）"))
        人 = s.get("人物动作", "") + s.get("表情", "")
        if re.search(r"对口型|跟着.{0,4}唱|唱歌|张嘴|开口唱|说话", 人):
            坏.append((号, "对口型／张嘴唱", "改成嘴闭着的动作（抬眼、回头、整理袖口），视频模型对不上口型"))
        怪 = re.findall(r"叉腿|叉开|劈叉|深蹲|扎马步|大字型站", 人)
        if 怪:
            坏.append((号, f"姿势不像真人（{'、'.join(怪)}）", "站直、重心放一条腿，或者小步走、靠墙"))
        动 = s.get("镜头动作", "")
        if re.search(r"360|环绕|绕一圈|orbit", 动, re.I):
            坏.append((号, "360 度环绕", "改成半圈以内的弧移或慢推；转一整圈脸和衣服会走样"))
        几个 = 镜头动作数(动)
        if len(几个) >= 2 or re.search(r"先.+再|然后|最后", 动):
            坏.append((号, f"一刀 {max(2, len(几个))} 个镜头动作（{动}）", f"只留一个（比如只留「{几个[0] if 几个 else '推'}」），其余拆到别的刀"))
        字, 词 = 大字词(s.get("大字", ""))
        if len(词) > 1:
            坏.append((号, f"大字「{字}」一刀两个词以上", "一刀一个词，另一个词放下一刀"))
        elif 词 and HAN.search(字) and len(字) > 4:
            提醒.append((号, f"大字「{字}」{len(字)} 个字偏长", "一刀一个词，2～4 个字最好"))
        跨 = re.search(r"到\s*(\d+(?:\.\d+)?)\s*秒", s.get("大字", ""))
        if 跨 and float(跨[1]) > s["出"] + 0.01:
            坏.append((号, f"大字一直显示到 {跨[1]} 秒，跨过了 {s['出']} 秒的切点", "字跟着这一刀走，切点一到就换"))
    中, 英 = [s["号"] for s in 表 if HAN.search(大字词(s.get("大字", ""))[0])], \
        [s["号"] for s in 表 if re.search(r"[A-Za-z]", 大字词(s.get("大字", ""))[0])]
    if 中 and 英 and not re.search(r"中英混用[：:]\s*有意", Path(path).read_text(encoding="utf-8")):
        少 = 中 if len(中) <= len(英) else 英
        坏.append(("、".join(少), f"大字中英混用（{len(英)} 刀英文、{len(中)} 刀中文）", "统一成一种；主人要中英都有，就在分镜开头写一行「中英混用：有意」"))
    if not (大字词(表[0].get("大字", ""))[1] or "钩子" in 表[0].get("备注", "")) and 表[0]["出"] > 0:
        提醒.append(("1", "开头 2 秒没有大字或钩子", "第一刀放大字，或者把最抓人的镜头挪到开头"))
    for d in 落点:
        刀 = next((s for s in 表 if s["进"] - 0.05 <= d < s["出"] - 0.05), None)
        if 刀 and d < 总长:
            提醒.append((刀["号"], f"大落点 {d:.2f} 秒在这一刀", "放全片最猛的镜头（最炸的运镜、最酷的动作）"))
    return 表, 坏, 提醒, 拍来源


def main():
    ap = argparse.ArgumentParser(description="镜头表体检")
    ap.add_argument("分镜")
    ap.add_argument("--拍子")
    ap.add_argument("--查素材", action="store_true")
    g = ap.parse_args()
    表, 坏, 提醒, 拍来源 = 查(g.分镜, g.拍子, g.查素材)
    print(f"{len(表)} 刀，{表[-1]['出']:.2f} 秒；切点{拍来源}")
    for 号, 问题, 改法 in 坏:
        print(f"❌ 第 {号} 刀：{问题} → {改法}")
    for 号, 问题, 改法 in 提醒:
        print(f"⚠️ 第 {号} 刀：{问题} → {改法}")
    print(f"\n毛病 {len(坏)} 条、提醒 {len(提醒)} 条。" + ("体检只报不改：问主人要不要照这些改，不擅自整表重写。" if 坏 else "PASS：可以给主人看分镜（关口 2）。"))
    sys.exit(1 if 坏 else 0)


if __name__ == "__main__":
    main()

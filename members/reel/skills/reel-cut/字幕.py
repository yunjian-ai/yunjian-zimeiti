"""带货片、口播片的字：底部字幕、花字、左上品牌贴纸、价格、行动号召按钮，生成一份 ASS 字幕给 ffmpeg 烧（成片.py 带货、口播模式自动调用）。
口播片：字幕照剪辑方案「台词」那一格（就是稿子原文），一句一条、跟着这句的时间；==重点== 黄色、**花字** 黄色放大；
  一条超过 14 个字拆成两条依次出；句尾的逗号句号不显示（问号叹号留着）。
读：分镜.md 的「字幕」列（没有就用「台词」；**关键词** 换高亮色；「／」分成几段依次出）、「花字」列；剪辑.json 的 贴纸、价格、行动。
位置照安全区（库/视频规格.md 第三节的推算值）：字幕和按钮都在底部 20% 之上、右边留出按钮栏，花字在顶部 15% 处（再高描边会蹭进顶部 10% 的按钮区）。
特写刀字幕挡住货（扣子、印花）：镜头表这一刀的备注写「字幕上」，这一刀的字幕挪到画面上部（花字下面）。
用法：python3 字幕.py <项目> [--画幅 9:16]   单独出 出片/字幕.ass ＋ 字幕.srt，给主人看字、交平台上传字幕文件用"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for d in ("reel-brief", "reel-board", "reel-cut"):
    sys.path.insert(0, str(HERE.parent / d))
import 字体  # noqa: E402
import 镜头表  # noqa: E402

高亮 = "&H0033D7FF&"  # 暖黄（ASS 是 蓝绿红 倒着写）


def 字体名(路径):
    """ASS 要写字体的名字（不是文件名）：用 PIL 读家族名和粗细。字幕引擎认的是老式家族名：常规、粗体、斜体只写家族名，
    Heavy、Medium 这类别的粗细要连粗细一起写（「Source Han Sans CN Heavy」；只写家族名会变方框，10-28 实测）。"""
    try:
        from PIL import ImageFont
        家族, 粗细 = ImageFont.truetype(路径, 20).getname()
    except Exception:
        return "Noto Sans CJK SC"
    return 家族 if 粗细 in ("Regular", "Bold", "Italic", "Bold Italic", "") else f"{家族} {粗细}"


def 秒(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def 转义(text, 放大=False):
    text = text.replace("\\", "＼").replace("{", "（").replace("}", "）")
    text = re.sub(r"==(.+?)==", lambda m: "{\\1c" + 高亮 + "}" + m[1] + "{\\r}", text)
    大 = "\\fscx125\\fscy125" if 放大 else ""
    return re.sub(r"\*\*(.+?)\*\*", lambda m: "{\\1c" + 高亮 + 大 + "}" + m[1] + "{\\r}", text)


def 去标(text):
    return re.sub(r"\*\*|==", "", text)


def 拆行(text, 最多=14):
    """超过 14 个字：在靠中间的逗号顿号处拆，没有就从中间拆（不拆开 ** == 标记里的字）。"""
    if len(去标(text).rstrip("，。、；：,.！？!? ")) <= 最多:  # 句末标点不算长度
        return [text]
    中 = len(text) / 2
    两边有字 = lambda k: 去标(text[:k]).strip() and 去标(text[k:]).strip()  # noqa: E731  切完两边都得有字，不然会原样再进来
    候 = sorted((m.end() for m in re.finditer(r"[，；：,]", text) if 两边有字(m.end())), key=lambda k: abs(k - 中)) or \
        sorted((m.end() for m in re.finditer(r"、", text) if 两边有字(m.end())), key=lambda k: abs(k - 中)) or [int(中)]  # 先逗号分号，没有再顿号
    k = 候[0]
    while 0 < k < len(text) and (text[k - 1:k + 1] in ("**", "==")):
        k += 1  # 不切在标记的两个符号中间
    if not 0 < k < len(text):
        return [text]
    a, b = text[:k], text[k:]
    for 标 in ("**", "=="):  # 切在重点标记里面：前半句补收尾、后半句补开头（整句被 ==…== 包住时也能拆）
        if a.count(标) % 2:
            a, b = a + 标, 标 + b
    return 拆行(a, 最多) + 拆行(b, 最多)


def 空(text):
    return not text or text.strip() in ("—", "-", "无", "【待填】")


def 条目(P, 设置, 总长):
    """[(起, 止, 样式, 文字)]，文字里的 **词** 还没转。"""
    out = []
    表 = 镜头表.读镜头表(P / "分镜.md")
    if 设置.get("类型") == "口播":
        for s in 表:
            字 = re.sub(r"[，。,.]+$", "", s.get("台词", "").strip())
            if not 空(字):
                段 = 拆行(字)
                权 = [max(1, len(去标(x))) for x in 段]
                起, 长 = s["进"], s["出"] - s["进"] - 0.02
                样式 = "SubTop" if "字幕上" in s.get("备注", "") else "Sub"
                for x, w in zip(段, 权):
                    止 = 起 + 长 * w / sum(权)
                    out.append((起, 止, 样式, x))
                    起 = 止
            if not 空(s.get("花字", "")):
                out.append((s["进"] + 0.05, s["出"] - 0.05, "Hook", s["花字"]))
        if 设置.get("片尾引导") and 表:
            out.append((max(表[-1]["进"], 总长 - 2.5), 总长, "CTA", 设置["片尾引导"]))
        return out
    for s in 表:
        进, 出 = s["进"], s["出"]
        字 = s.get("字幕", "")
        if 空(字):
            字 = s.get("台词", "")
        if not 空(字):
            段 = [x.strip() for x in re.split(r"[／|]", 字) if x.strip()]
            权 = [max(1, len(去标(x))) for x in 段]
            起, 长 = 进 + 0.1, max(0.3, 出 - 进 - 0.15)
            样式 = "SubTop" if "字幕上" in s.get("备注", "") else "Sub"
            for x, w in zip(段, 权):
                止 = 起 + 长 * w / sum(权)
                out.append((起, 止, 样式, x))
                起 = 止
        花 = s.get("花字", "")
        if not 空(花):
            out.append((进 + 0.05, 出 - 0.05, "Hook", 花))
    if 设置.get("贴纸"):
        out.append((0.0, 总长, "Tag", 设置["贴纸"]))
    if 表:
        末 = 表[-1]
        if 设置.get("价格"):
            out.append((末["进"] + 0.2, 末["出"], "Price", 设置["价格"]))
        if 设置.get("行动"):
            out.append((末["进"] + 0.3, 末["出"], "CTA", 设置["行动"]))
    return out


def ass(P, 设置, 总长, W, H):
    """写 出片/字幕.ass，返回 (路径, 字体文件夹)。"""
    f = 字体.找("中文", P)
    名 = 字体名(f)
    边 = max(2, round(H * 0.0035))
    样 = [  # 名字, 字号, 主色, 边色, 底色, 粗, 边框样式, 边宽, 阴影, 对齐, 左右边距, 上下边距
        ("Sub", round(H * 0.034), "&H00FFFFFF", "&H00000000", "&H80000000", -1, 1, 边, 1, 2, round(W * 0.1), round(H * 0.26)),
        ("SubTop", round(H * 0.034), "&H00FFFFFF", "&H00000000", "&H80000000", -1, 1, 边, 1, 8, round(W * 0.1), round(H * 0.22)),
        ("Hook", round(H * 0.058), "&H0033D7FF", "&H00000000", "&H80000000", -1, 1, 边 * 2, 2, 8, round(W * 0.08), round(H * 0.15)),  # 0.13 时描边会蹭进顶部 10%（Bot 实测）
        ("Tag", round(H * 0.02), "&H00FFFFFF", "&H00000000", "&H66000000", -1, 3, round(H * 0.006), 0, 7, round(W * 0.07), round(H * 0.105)),
        ("Price", round(H * 0.06), "&H003A3AE6", "&H00FFFFFF", "&H80000000", -1, 1, 边 * 2, 1, 2, round(W * 0.1), round(H * 0.44)),
        ("CTA", round(H * 0.032), "&H00FFFFFF", "&H00005AFF", "&H00005AFF", -1, 3, round(H * 0.012), 0, 2, round(W * 0.1), round(H * 0.36)),
    ]
    头 = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "ScaledBorderAndShadow: yes", "WrapStyle: 0", "",
         "[V4+ Styles]",
         "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
         "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"]
    for n, 号, 主, 边色, 底, 粗, 框, 宽, 影, 对, 左右, 上下 in 样:
        头.append(f"Style: {n},{名},{号},{主},&H000000FF,{边色},{底},{粗},0,0,0,100,100,0,0,{框},{宽},{影},{对},{左右},{左右},{上下},1")
    头 += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for 起, 止, 样式, 文 in 条目(P, 设置, 总长):
        if 止 - 起 < 0.05:
            continue
        特效 = {"Hook": "{\\fad(80,0)\\fscx125\\fscy125\\t(0,160,\\fscx100\\fscy100)}",
              "CTA": "{\\fad(150,0)}", "Price": "{\\fad(120,0)}"}.get(样式, "")
        头.append(f"Dialogue: {0 if 样式.startswith('Sub') else 1},{秒(起)},{秒(止)},{样式},,0,0,0,,{特效}{转义(文, 设置.get('类型') == '口播')}")
    out = P / "出片" / "字幕.ass"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(头) + "\n", encoding="utf-8")
    return out, str(Path(f).parent)


def srt(P, 设置, 总长):
    行, n = [], 0
    for 起, 止, 样式, 文 in 条目(P, 设置, 总长):
        if not 样式.startswith("Sub"):
            continue
        n += 1
        f = lambda t: f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(t * 1000 % 1000):03d}"  # noqa: E731
        行 += [str(n), f"{f(起)} --> {f(止)}", 去标(文), ""]
    out = P / "出片" / "字幕.srt"
    out.write_text("\n".join(行), encoding="utf-8")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="带货片字幕")
    ap.add_argument("项目")
    ap.add_argument("--画幅", default="9:16")
    g = ap.parse_args()
    P = Path(g.项目).resolve()
    宽高 = {"9:16": (1080, 1920), "3:4": (1080, 1440), "1:1": (1080, 1080), "16:9": (1920, 1080)}[g.画幅]
    设置 = json.loads((P / "剪辑.json").read_text(encoding="utf-8")) if (P / "剪辑.json").exists() else {}
    表 = 镜头表.读镜头表(P / "分镜.md")
    总长 = 表[-1]["出"] if 表 else 0
    a, _ = ass(P, 设置, 总长, *宽高)
    print(f"OK {a} ＋ {srt(P, 设置, 总长)}")

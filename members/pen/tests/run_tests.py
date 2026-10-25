"""执笔测试：①夹具（check_pen 该抓的抓、不该抓的不抓）②仓库检查要通过 ③反向用例（往仓库副本里埋错，检查脚本必须拦住）
④乱输入不崩（装了 hypothesis 才跑）。
用法：python3 members/pen/tests/run_tests.py"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE.parent / "skills" / "pen-draft"))
from check_pen import check, main as check_main  # noqa: E402
from common import run_negative_cases  # noqa: E402

fails = 0


def report(ok, name, detail=""):
    global fails
    fails += not ok
    print(("✅ " if ok else "❌ ") + name + (f"  {detail}" if detail and not ok else ""))


# ① 夹具：查出的问题类别必须和 expect 完全一致（不漏报，也不误报）
for f in sorted((HERE / "fixtures").glob("*.json")):
    fx = json.loads(f.read_text(encoding="utf-8"))
    got = sorted({i["code"] for i in check(fx["doc"])})
    report(got == sorted(fx["expect"]), f"夹具 {f.stem}", f"得到 {got} 应为 {fx['expect']}｜{fx['why']}")

# ①½ 命令行：有问题退出码 1，没问题 0
bad, good = HERE / "fixtures" / "12-翻案腔.json", HERE / "fixtures" / "11-第一步不是极限词.json"
codes = []
for fx in (bad, good):
    tmp = HERE / "_tmp_draft.txt"
    tmp.write_text(json.loads(fx.read_text(encoding="utf-8"))["doc"]["body"], encoding="utf-8")
    try:
        codes.append(check_main([str(tmp)]))
    finally:
        tmp.unlink()
report(codes == [1, 0], "命令行退出码：有问题 1、没问题 0", f"得到 {codes}")

# ①¾ 级别：极限词只在带货稿算硬错；待问、概括、句长只提醒
lv = lambda name: sorted({i["level"] for i in check(json.loads((HERE / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))["doc"])})
report(lv("02-极限词") == ["硬"] and lv("18-非带货的最好不算违法") == ["提醒"] and lv("14-编概括") == ["提醒"], "级别：带货极限词硬、非带货提醒、概括提醒")

# ①⅞ 误伤：真人写的文章和口播原话里，翻案腔、名词化、黑话、量产腔不许报（对照集只在开发仓库本机，公开仓库没有就跳过）
import glob, re as _re
REF = Path.home() / "Desktop/云间/起元/资料/对标/写作"
human = [open(f, encoding="utf-8").read() for f in sorted(glob.glob(str(REF / "shuorenhua/evals/human-corpus/HUMAN-*.txt")))]
q = REF / "jianghushuo-oral-skill/references/quotes.md"
if q.exists():
    human.append("\n".join(_re.findall(r"[「“\"]([^」”\"]{8,})[」”\"]", q.read_text(encoding="utf-8"))))
if human:
    bad = [(i["code"], i["text"][:20]) for t in human for i in check({"body": t, "form": "长文", "platform": "公众号"})
           if i["code"] in {"PIVOT", "NOMINAL", "JARGON", "AI_STOCK"}]
    report(not bad, f"真人对照 {len(human)} 份零误伤（翻案腔、名词化、黑话、量产腔）", str(bad[:5]))
else:
    print("（没有真人对照集，跳过①⅞）")

# ② 仓库检查本身要通过
r = subprocess.run([sys.executable, str(ROOT / "tools" / "validate.py"), str(ROOT)], capture_output=True, text=True)
report(r.returncode == 0, "仓库检查通过", r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr)

# ③ 反向用例：埋一个错，validate 必须报出对应类别
SK = Path("members/pen/skills")


def append(rel, text):
    return lambda d: (d / rel).write_text((d / rel).read_text(encoding="utf-8") + text, encoding="utf-8")


def edit(rel, a, b):
    return lambda d: (d / rel).write_text((d / rel).read_text(encoding="utf-8").replace(a, b), encoding="utf-8")


banned = "".join(map(chr, (0x5DE5, 0x5177, 0x7BB1)))  # 名单上的词用码点拼出来，仓库里不出现明文
run_negative_cases("pen", [
    ("budget", append(SK / "pen-draft/SKILL.md", "啊" * 33000)),  # 超 96KB 硬上限（考试记录/技能体量实测-2026-10-23.md）
    ("private", append(SK / "pen-draft/规则卡.md", "\n" + banned + "\n")),
    ("private", append(SK / "pen-draft/check_pen.py", "\n# " + banned + "\n")),
    ("xref", append(SK / "pen-check/SKILL.md", "\n交给 pen-nonexistent。\n")),
    ("xref", append(SK / "pen-angle/SKILL.md", "\n见 `不存在的卡.md`。\n")),
    ("frontmatter", lambda d: (d / SK / "pen-polish/SKILL.md").write_text("没有头部\n", encoding="utf-8")),
    ("version", lambda d: (d / "members/pen/VERSION").write_text("v1\n")),
    ("instructions", edit("members/pen/profile.json", "pen-remake", "某技能")),
    ("instructions", edit("members/pen/profile.json", "不到 15 个", "不到 9 个")),
    ("install", edit("members/pen/memory.md", "不装回旧版", "重装")),
    ("rehearsal", edit(SK / "pen-getting-started/SKILL.md", "## 演练模式", "## 试一试")),
    ("greeting", edit("members/pen/memory.md", "您好，欢迎来到云间。", "你好。")),
], report)

# ④ 乱输入不崩：随便拼稿子和料，只能报问题，不能抛异常
try:
    from hypothesis import given, settings, strategies as st
except ImportError:
    print("（没装 hypothesis，跳过④）")
else:
    pieces = st.sampled_from(["标题：", "【前 3 秒】", "【推算：40－8】", "【问：几年？】", "32 个", "1. ", "/", "**", "全网最", "加我微信",
                              "根治", "家人们", "\n", "。", "，", "约 240 字", "100%", "http://x.cn", "【", "】"])
    text = st.lists(st.one_of(pieces, st.text(max_size=20)), max_size=30).map("".join)

    @settings(max_examples=300, deadline=None, database=None)
    @given(text, st.lists(text, max_size=3), st.sampled_from(["口播", "长文", None]),
           st.one_of(st.none(), st.integers(min_value=1, max_value=600)), st.sampled_from([None, "抖音", "公众号", "X", "小红书"]))
    def no_crash(body, mats, form, sec, plat):
        issues = check({"body": body, "material": mats, "form": form, "seconds": sec, "platform": plat})
        assert isinstance(issues, list) and all({"code", "text", "hint"} <= set(i) for i in issues)
    try:
        no_crash()
        report(True, "乱输入 300 例不崩")
    except Exception as ex:  # noqa: BLE001
        report(False, "乱输入不崩", repr(ex)[:200])

# ⑤ 长文排版：图片位写了文件名就把图嵌进网页；发布版粗体不贴中文标点；没有的图留占位（v0.3.1）
import importlib.util, tempfile  # noqa: E402
_spec = importlib.util.spec_from_file_location("paiban", HERE.parent / "skills" / "pen-draft" / "长文排版.py")
paiban = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(paiban)
with tempfile.TemporaryDirectory() as d:
    (Path(d) / "图1.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 20)
    page, pub = paiban.render("标题：试\n\n有个衣柜，==常穿的只有 9 件。==\n\n👇【图】衣柜｜图1.png\n\n👇【图】没有的图｜图9.png", base=d)
report("data:image/png;base64," in page and "![衣柜](图1.png)" in pub and "**常穿的只有 9 件**。" in pub and "没有的图（图位：图9.png）" in pub,
       "长文排版：图嵌进网页、粗体标点挪外面、缺图留占位", pub[:200])

_bold = {"一行里 **A 很重要**，还有 **B 也重要。**完": "一行里 **A 很重要**，还有 **B 也重要**。完",
         "==常穿的只有 **9** 件。==": "**常穿的只有 9 件**。",
         "**第一步**：装箱。**第二步**：放阳台。": "**第一步**：装箱。**第二步**：放阳台。"}
_got = {k: paiban.render("标题：试\n\n" + k)[1].split("\n\n", 1)[1].strip() for k in _bold}
report(_got == _bold, "长文排版：一行几处加粗不串、== 里套粗体不叠两层（Bot 实测报的毛病）", str({k: v for k, v in _got.items() if v != _bold[k]}))

print("\n" + ("全部通过" if not fails else f"{fails} 项没过"))
sys.exit(1 if fails else 0)

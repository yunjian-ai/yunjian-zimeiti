"""check_library.py 的自测：拿真样卡做底，随机埋一种错，看它拦不拦得住；好卡不误伤。
用法：python3 test_check_library.py"""
import re
import shutil
import sys
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_library as cl  # noqa: E402

GOOD = HERE / "样卡" / "x-ai-001-vibe-coding.md"
# 样卡是 2025 年的帖子，测试里把发布日期临时改近，避开时间关（卡上的真实数据不动）
BASE = GOOD.read_text(encoding="utf-8").replace("发布日期: 2025-02-02", "发布日期: 2026-09-01")
REQUIRED = ["id", "赛道", "平台", "形式", "稿型", "链接", "账号", "发布日期", "采集日期", "数据来源", "标题", "开头摘引", "收录"]
ENUMS = {"赛道": "情感", "平台": "小红书", "形式": "直播", "稿型": "段子", "数据来源": "估的", "收录": "随便"}


def bad_card(kind, pick):
    t = BASE
    if kind == "超时":
        return t.replace("发布日期: 2026-09-01", f"发布日期: 202{pick % 4}-01-01"), "超时"
    if kind == "缺字段":
        k = REQUIRED[pick % len(REQUIRED)]
        return re.sub(rf"^{k}:.*\n", "", t, count=1, flags=re.M), "卡头"
    if kind == "选项填错":
        k = list(ENUMS)[pick % len(ENUMS)]
        return re.sub(rf"^{k}:.*$", f"{k}: {ENUMS[k]}", t, count=1, flags=re.M), "卡头"
    if kind == "摘引超长":
        return t.replace("开头摘引: There's", "开头摘引: " + "长" * (51 + pick % 30) + " There's"), "卡头 开头摘引"
    if kind == "卡身摘引超长":
        return t + "\n「" + "原文" * (26 + pick % 20) + "」\n", "原文摘引超过"
    if kind == "缺小节":
        s = cl.SECTIONS[pick % len(cl.SECTIONS)]
        return t.replace(f"## {s}\n", f"## 别的{pick}\n"), f"缺「## {s}」"
    if kind == "夹密钥":
        return t + "\nBEATAPI_API_" + f"KEY=abcd{pick:08d}efgh\n", "密钥"  # 拆开写，发布扫描不误报
    if kind == "数字乱填":
        return t.replace("点赞: 34174", "点赞: 大概三万"), "卡头 互动/点赞"
    if kind == "日期乱写":
        return t.replace("采集日期: 2026-10-23", "采集日期: 昨天"), "卡头 采集日期"
    if kind == "招式格式错":
        return t.replace("- 【开头】第一句", "- 开头：第一句"), "不是招式格式"
    if kind == "招式空话":
        return t.replace("- 【开头】第一句亮出自己起的新名字，紧跟一句用三个动作讲清它", "- 【开头】开头很吸引人"), "招式是空话"
    raise ValueError(kind)


def run_on(text, folder=("AI应用", "X"), name="x-ai-001-vibe-coding.md", extra=None):
    d = Path(tempfile.mkdtemp())
    try:
        (d / "schema").mkdir()
        shutil.copy(HERE / "schema" / "爆款卡.schema.json", d / "schema")
        p = d / "爆款" / folder[0] / folder[1]
        p.mkdir(parents=True)
        (p / name).write_text(text, encoding="utf-8")
        if extra:
            (p / "copy.md").write_text(extra, encoding="utf-8")
        seen, out = {}, []
        for f in sorted((d / "爆款").glob("*/*/*.md")):
            errs, _ = cl.check_card(f, seen)
            out += errs
        return out
    finally:
        shutil.rmtree(d)


KINDS = ["招式格式错", "招式空话", "超时", "缺字段", "选项填错", "摘引超长", "卡身摘引超长", "缺小节", "夹密钥", "数字乱填", "日期乱写"]


@settings(max_examples=200, deadline=None)
@given(st.sampled_from(KINDS), st.integers(min_value=0, max_value=10_000))
def test_bad_card_is_caught(kind, pick):
    text, needle = bad_card(kind, pick)
    errs = run_on(text)
    assert errs, f"{kind} 没拦住"
    assert any(needle in e for e in errs), f"{kind} 拦了但说法不对：{errs}"


def test_good_card_passes():
    assert run_on(BASE) == []


def test_quote_must_be_in_source():
    src = "说真的，我第一次上门的时候也懵了，那个客厅连坐的地方都没有。你别急着买收纳盒。"
    body = "## 能借的\n- 【开头】先讲现场｜示范「我第一次上门的时候也懵了」｜适用：口播\n标签「结论＋理由＋行动」，转述「客厅乱得没地儿坐」，改错字「我第一次上门的时侯也懵了，那个客厅」，省略「说真的……连坐的地方都没有」\n"
    bad = cl.quote_problems(body, src)
    assert bad == ["结论＋理由＋行动", "客厅乱得没地儿坐"], bad


def test_wrong_folder_and_duplicate():
    assert any("放错文件夹" in e for e in run_on(BASE, folder=("带货", "抖音")))
    assert any("重复" in e for e in run_on(BASE, extra=BASE))


def test_same_author_cap():
    d = Path(tempfile.mkdtemp())
    try:
        (d / "schema").mkdir(); shutil.copy(HERE / "schema" / "爆款卡.schema.json", d / "schema")
        p = d / "爆款" / "AI应用" / "X"; p.mkdir(parents=True)
        for i in (1, 2, 3):
            (p / f"x-ai-00{i}-t.md").write_text(BASE.replace("id: x-ai-001", f"id: x-ai-00{i}"), encoding="utf-8")
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cl.main([str(d)])
        assert code == 1 and "最多 2" in buf.getvalue(), buf.getvalue()
    finally:
        shutil.rmtree(d)


if __name__ == "__main__":
    test_good_card_passes()
    test_quote_must_be_in_source()
    test_wrong_folder_and_duplicate()
    test_same_author_cap()
    test_bad_card_is_caught()
    print(f"✅ 好卡不误伤；{len(KINDS)} 类坏卡 200 例全拦住（含超时）；放错文件夹、id 重复、同一账号超 2 张、引用原文找不到都拦住")

"""danzi.py 的测试（交接单、回执、演进环收件条）：好单子过、各种坏单子拦；装了 jsonschema 和 hypothesis 时，用随机单子比「小校验」和 jsonschema 结论一致。
用法：python3 tools/test_danzi.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import danzi  # noqa: E402

GOOD = """# 某项目交接单

### 交接单 · 第 3 段 · 凝露
- 这一段：③ 蒸馏，派给凝露
- 目标：把访谈稿整理成知识卡
- 用到的料：`资料/访谈.md`
- 边界：只许新建 `03-知识卡/`；
  1. 访谈里的手机号打码
  - 注意：不改原稿
- 交回格式：`03-知识卡/*.md`，回执写在 `03-知识卡/回执.md`
- 验收标准：每张卡有出处；不少于 5 张
- 预算：返工最多 1 次，不花钱
- 结果（收活时填）：

### 回执 · 第 3 段 · 凝露
- 交了什么：7 张知识卡
- 放在哪：`03-知识卡/`
- 自检：每张卡有出处 ✅；不少于 5 张 ✅
- 卡在哪：无
"""

SHOU = """### 收件 · 2026-10-30 · 主人纠正
- 原话：分享卡的发布以后你自己点
- 对应正本：经验笔记「分享卡」第 2 节；记忆「分享卡发布」
- 第几次：2
- 判：更新，旧写法是留给主人点
- 改了哪：经验笔记第 2 节改成自己点（10-29）
- 验：回归不涉及 ✅；预算闸 ✅
"""


def errs(text):
    return danzi.check_text(text)


def main():
    fails = []

    def expect(name, cond):
        print(("✅ " if cond else "❌ ") + name)
        if not cond:
            fails.append(name)

    expect("好单子：两张都过", errs(GOOD) == [] and len(danzi.parse(GOOD)) == 2)
    f = danzi.parse(GOOD)[0][1]
    expect("跨行的内容接在上一栏（含缩进的「- 注意：」）", "手机号打码" in f["边界"] and "不改原稿" in f["边界"])
    expect("栏名后的（说明）不算进栏名，结果可以空", f.get("结果") == "")
    expect("缺预算拦下", any("预算" in e for e in errs(GOOD.replace("- 预算：返工最多 1 次，不花钱\n", ""))))
    expect("目标空着拦下", any("目标" in e for e in errs(GOOD.replace("把访谈稿整理成知识卡", ""))))
    expect("自检没打勾拦下", any("自检" in e for e in errs(GOOD.replace("每张卡有出处 ✅；不少于 5 张 ✅", "都做了"))))
    expect("回执超 500 字拦下", any("上限 500" in e for e in errs(GOOD.replace("7 张知识卡", "很" * 600))))
    expect("交接单超 1500 字拦下", any("上限 1500" in e for e in errs(GOOD.replace("把访谈稿整理成知识卡", "很" * 1600))))
    expect("没有单子的文件不报错", errs("# 普通文件\n- 目标：随便写\n") == [])
    expect("收件条：好的过", errs(SHOU) == [] and danzi.parse(SHOU)[0][0] == "收件")
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write("# 主人的纠正（原话，没整理成收件条）\n1. 周报别写那么长。\n")
    expect("一张单子都没有：不算通过", danzi.main([tf.name]) == 1)
    from pathlib import Path as _P
    d = _P(tempfile.mkdtemp())
    (d / "单子.md").write_text("### 回执 · 第 2 段 · 配图\n- 交了什么：3 张图\n- 放在哪：`图/周三/*.png`\n- 自检：✅ 3 张\n- 卡在哪：无\n", encoding="utf-8")
    expect("--查产物：产物不在要拦", danzi.main([str(d / "单子.md"), "--查产物"]) == 1)
    (d / "图" / "周三").mkdir(parents=True)
    (d / "图" / "周三" / "1.png").write_bytes(b"x")
    expect("--查产物：产物在就过", danzi.main([str(d / "单子.md"), "--查产物"]) == 0)
    expect("不加 --查产物照旧只查格式", danzi.main([str(d / "单子.md")]) == 0)
    expect("收件条：判不是四选一拦下", any("判" in e for e in errs(SHOU.replace("- 判：更新", "- 判：改一下"))))
    expect("收件条：标题没日期拦下", any("标题" in e for e in errs(SHOU.replace("2026-10-30 · ", ""))))
    expect("收件条：第几次不是数字拦下", any("第几次" in e for e in errs(SHOU.replace("- 第几次：2", "- 第几次：好几次"))))
    expect("收件条：没写验拦下", any("验" in e for e in errs(SHOU.replace("- 验：回归不涉及 ✅；预算闸 ✅\n", ""))))
    expect("两种校验各自都认得缺栏", danzi.mini_errors(danzi.schema("回执"), {"标题": "x"}) != [])

    try:
        import jsonschema  # noqa: F401
        from hypothesis import given, settings, strategies as st
    except ImportError:
        print("ℹ️ 没装 jsonschema 或 hypothesis，跳过随机比对")
    else:
        for kind in danzi.KINDS:
            sch = danzi.schema(kind)
            keys = st.sampled_from(sorted(sch["properties"]) + ["多余栏"])
            vals = st.one_of(st.text(max_size=6), st.sampled_from(["", "✅", "⚠️ 部分", "无", "新增 x", "改一下", "2", "2026-10-30 · 错题"]))

            def make(sch):
                @settings(max_examples=400, deadline=None)
                @given(st.dictionaries(keys, vals, max_size=12))
                def same(obj):
                    assert bool(danzi.mini_errors(sch, obj)) == bool(danzi.schema_errors(sch, obj)), obj
                return same

            try:
                make(sch)()
                expect(f"随机 400 张{kind}：小校验和 jsonschema 结论一致", True)
            except AssertionError as e:
                expect(f"随机{kind}比对（反例 {e}）", False)

    print(("全部通过" if not fails else f"{len(fails)} 项没过"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

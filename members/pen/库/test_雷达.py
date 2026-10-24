"""雷达.py 的自测（不上网，喂假数据）：过爆款线的才收、索引里有的链接不重复收、同一账号最多 2 条、收进来就在索引里查得到、写稿抽卡抽得到。"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import 雷达 as radar  # noqa: E402
import 建目录 as idx  # noqa: E402


def item(n, likes):
    return {"链接": f"https://x.com/someone/status/{n}", "标题": f"第 {n} 条", "形式": "帖子", "发布日期": "2026-10-20",
            "互动": {"点赞": likes, "评论": 10, "转发": 5, "收藏": "没抓到"}}


def main():
    d = Path(tempfile.mkdtemp())
    ok = True
    try:
        (d / "雷达.json").write_text(json.dumps({"倍数": 3, "账号": [{"平台": "X", "账号": "someone", "赛道": "AI应用", "话题": ["AI编程"]}]},
                                              ensure_ascii=False), encoding="utf-8")
        # 已经在收件箱里的一条（模拟上周收过）
        (d / "收件箱").mkdir()
        (d / "收件箱" / "old.md").write_text("---\n链接: https://x.com/someone/status/1\n平台: X\n账号: someone\n标签: [AI编程]\n来源: 雷达\n---\n", encoding="utf-8")
        fake = {"someone": [item(1, 90000), item(2, 50000), item(3, 40000), item(4, 800), item(5, 900), item(6, 1000), item(7, 1200)]}
        brief = radar.run(d, fetched=fake, today="2026-10-25")
        files = sorted(p.name for p in (d / "收件箱").glob("*.md"))
        # 中位数 1000 × 3 = 3000：第 1、2、3 条过线；第 1 条索引里有了；同一账号已有 1 条，最多再收 1 条 → 只收第 2 条
        ok &= files == ["2026-10-25-X-2.md", "old.md"]
        print(("✅" if ok else f"❌ {files}") + " ① 过爆款线才收、索引里有的不重复、同一账号最多 2 条")
        es = idx.collect(d)
        got, _ = idx.query(es, 平台="X", 话题=["AI编程"])
        ok2 = any(e["链接"] == "https://x.com/someone/status/2" and e["状态"] == "收件箱" and e["来源"] == "雷达" for e in got)
        ok2 &= "https://x.com/someone/status/2" in (d / "索引.json").read_text(encoding="utf-8")
        print(("✅" if ok2 else "❌") + " ② 雷达收进来的那条已在索引里，写稿抽卡抽得到（状态收件箱、来源雷达）")
        ok3 = "新收 1 条" in brief and "AI编程" in brief
        print(("✅" if ok3 else "❌ " + brief) + " ③ 简报写清新收几条、库里常见话题")
        # 再跑一次：不该再收
        radar.run(d, fetched=fake, today="2026-10-26")
        ok4 = len(list((d / "收件箱").glob("*.md"))) == 2
        print(("✅" if ok4 else "❌") + " ④ 再跑一次不重复收")
        ok &= ok2 and ok3 and ok4
    finally:
        shutil.rmtree(d)
    print("雷达自测全部通过" if ok else "雷达自测没过")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

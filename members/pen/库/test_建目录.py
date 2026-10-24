"""建目录.py 的自测，重点是「通路测试」：雷达条目 → 收件箱 → 索引里查得到 → 拆成卡 → 重建 → 写稿抽卡抽得到、招也取得到。哪一环断了就红。"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import 建目录 as idx  # noqa: E402

CARD = (HERE / "样卡" / "x-ai-001-vibe-coding.md").read_text(encoding="utf-8")
INBOX = """---
链接: https://www.douyin.com/video/7600000000000000001
平台: 抖音
赛道: 知识分享
形式: 口播
账号: 测试账号
标题: 鞋柜最下面一层留给拖鞋
互动: {点赞: 50000, 评论: 800, 转发: 3000, 收藏: 42000}
标签: [收纳, 玄关, 鞋柜]
来源: 雷达
发现日期: 2026-10-25
类型: 链接
放的人: 雷达
---
"""


def card_from_inbox():
    """照收件箱字段拆成卡（模拟 Kimi 拆卡）：字段照抄，补稿型、九节和招式。"""
    c = CARD.replace("id: x-ai-001", "id: dy-zs-001").replace("赛道: AI应用", "赛道: 知识分享").replace("平台: X", "平台: 抖音")
    c = c.replace("形式: 帖子", "形式: 口播").replace("稿型: 观点", "稿型: 方法").replace("标签: [AI编程, 造新词, 亲历]", "标签: [收纳, 玄关, 鞋柜]")
    c = c.replace("来源: 公共底盘", "来源: 雷达")
    return c.replace("- 【开头】第一句亮出", "- 【开头】先说一个反常识的放法｜示范「鞋柜最下面一层留给拖鞋」｜适用：收纳方法\n- 【钩子】第一句亮出")


def main():
    d = Path(tempfile.mkdtemp())
    ok = True
    try:
        (d / "收件箱").mkdir()
        (d / "收件箱" / "2026-10-25-dy-7600000000000000001.md").write_text(INBOX, encoding="utf-8")
        es = idx.build(d)
        hit = [e for e in es if e["状态"] == "收件箱"]
        ok &= len(hit) == 1 and hit[0]["平台"] == "抖音" and "鞋柜" in hit[0]["标签"]
        ok &= "（未拆）" in (d / "目录.md").read_text(encoding="utf-8")
        got, _ = idx.query(es, 平台="抖音", 话题=["鞋柜"])
        ok &= bool(got) and got[0]["状态"] == "收件箱"
        print(("✅" if ok else "❌") + " ① 雷达条目进收件箱，还没拆就能在目录和索引里查到")
        # ② 拆成卡，挪走收件箱条目，重建
        p = d / "爆款" / "知识分享" / "抖音"
        p.mkdir(parents=True)
        (p / "dy-zs-001-xie-gui.md").write_text(card_from_inbox(), encoding="utf-8")
        (d / "收件箱" / "已处理").mkdir()
        shutil.move(str(d / "收件箱" / "2026-10-25-dy-7600000000000000001.md"), d / "收件箱" / "已处理")
        es = idx.build(d)
        card = [e for e in es if e["id"] == "dy-zs-001"]
        ok2 = len(card) == 1 and card[0]["状态"] == "已拆" and card[0]["来源"] == "雷达" and len(es) == 1
        ok2 &= "鞋柜最下面一层留给拖鞋" in (d / "招式" / "开头.md").read_text(encoding="utf-8")
        ok2 &= json.loads((d / "索引.json").read_text(encoding="utf-8"))[0]["id"] == "dy-zs-001"
        print(("✅" if ok2 else "❌") + " ② 拆成卡、重建后：卡在目录里、招进了招式/开头.md、索引.json 对得上、收件箱那条不重复")
        # ③ 写稿抽卡：按平台、形式、稿型、话题、位置抽得到，招也取得到
        got, loose = idx.query(es, 平台="抖音", 形式="口播", 稿型="方法", 赛道="知识分享", 话题=["收纳"], 位置="开头")
        ok3 = bool(got) and got[0]["id"] == "dy-zs-001" and not loose and any(m["位置"] == "开头" for m in got[0]["招式"])
        got2, loose2 = idx.query(es, 平台="视频号", 形式="口播", 位置="开头")
        ok3 &= bool(got2) and "平台" in loose2
        print(("✅" if ok3 else "❌") + " ③ 写稿抽卡：条件对得上就抽到、不放宽；换个平台会说放宽了平台")
        ok &= ok2 and ok3
        # ④ 和检查脚本同一套格式：拆出来的卡过 check_library
        errs, _ = idx.cl.check_card(p / "dy-zs-001-xie-gui.md", {})
        errs = [x for x in errs if "超时" not in x]
        print(("✅" if not errs else "❌ " + "；".join(errs)) + " ④ 拆出来的卡过 check_library")
        ok &= not errs
        # ⑤ 统计、去重、招式精选
        st = (d / "统计.md").read_text(encoding="utf-8")
        ok5 = "知识分享 · 抖音（1 张）" in st and "开头的招" in st
        dup = dict(es[0]); dup["id"] = "我的库里的同一条"
        got, _ = idx.query([dup] + es, 平台="抖音")
        ok5 &= [e["id"] for e in got] == ["我的库里的同一条"]
        out = d / "精选.md"
        ok5 &= idx.picks(es, out) == 0 and "（还没有）" in out.read_text(encoding="utf-8")  # 没标公开的不进精选
        es[0]["公开"] = True
        ok5 &= idx.picks(es, out) == 4 and "鞋柜最下面一层留给拖鞋" in out.read_text(encoding="utf-8")
        print(("✅" if ok5 else "❌") + " ⑤ 统计.md 出来了；同一链接只抽一张、我的库优先；招式精选只收公开卡")
        ok &= ok5
    finally:
        shutil.rmtree(d)
    print("通路测试全部通过" if ok else "通路测试没过")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

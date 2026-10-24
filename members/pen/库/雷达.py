"""对标雷达：盯住主人的对标账号，把新出的爆款收进收件箱——字段和爆款卡卡头同名，进来就在目录和索引里查得到（建目录.py）。
用法：python3 雷达.py [--库 我的库路径] [--看 N] [--只看]        默认库是本文件所在的库
  对标账号写在 <库>/雷达.json：
    {"频率": "每周", "倍数": 3, "付费": false,
     "账号": [{"平台": "X", "账号": "karpathy", "赛道": "AI应用", "话题": ["AI编程"]},
              {"平台": "抖音", "账号": "某某", "sec_uid": "MS4wLjAB…", "赛道": "知识分享", "话题": ["收纳"]}]}
  没写账号：从索引里互动最高的 X 账号当种子（免费），并在简报里列出库里最常见的话题词，建议去搜这些词找新号。
  X 主页先免费抓（常被限流），开了付费就自动改走付费兜底；抖音按账号抓要付费接口（TikHub，每个账号一次约几分钱），「付费」写 true、环境变量有 TIKHUB_API_KEY 才抓；
  别的平台、或没开付费的：简报里提醒主人把这周刷到的爆款链接丢进来。
  爆款线：高于这个号这批作品中位数的「倍数」倍，且过平台底线（X 点赞 1000、抖音 1 万）。
  去重：链接在索引里有了不收；同一平台同一账号索引里已有 2 条不收。"""
import argparse
import json
import os
import re
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "抓取"))
import 建目录 as idx  # noqa: E402

FLOOR = {"X": 1000, "抖音": 10000}
CAP = 2


def fetch_x(acc):
    import requests
    r = requests.get(f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{acc['账号']}",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    if r.status_code == 429:
        raise RuntimeError("X 免费接口被限流（429），过几小时再试，或开付费")
    h = r.text
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', h)
    if not m:
        raise RuntimeError("X 主页没拿到数据")
    out = []
    for e in json.loads(m.group(1))["props"]["pageProps"]["timeline"]["entries"]:
        t = e.get("content", {}).get("tweet")
        if t and not t.get("retweeted_status"):
            out.append({"链接": f"https://x.com/{acc['账号']}/status/{t['id_str']}", "标题": (t.get("full_text") or "")[:60].replace("\n", " "),
                        "互动": {"点赞": t.get("favorite_count"), "评论": t.get("reply_count", "没抓到"), "转发": t.get("retweet_count", "没抓到"), "收藏": "没抓到"},
                        "发布日期": datetime.strptime(t["created_at"], "%a %b %d %H:%M:%S %z %Y").date().isoformat(), "形式": "帖子"})
    return out


def fetch_x_paid(acc):
    """X 付费兜底（TikHub，约 0.001 美元一次）：点赞、收藏、转发、回复、浏览都有。"""
    import tikhub
    d = tikhub.call("/api/v1/twitter/web/fetch_user_post_tweet", {"screen_name": acc["账号"]})
    out = []
    for t in (d.get("data") or {}).get("timeline") or []:
        out.append({"链接": f"https://x.com/{acc['账号']}/status/{t['tweet_id']}", "标题": (t.get("text") or "")[:60].replace("\n", " "),
                    "互动": {"点赞": t.get("favorites"), "评论": t.get("replies"), "转发": t.get("retweets"), "收藏": t.get("bookmarks")},
                    "发布日期": datetime.strptime(t["created_at"], "%a %b %d %H:%M:%S %z %Y").date().isoformat(), "形式": "帖子"})
    return out


def fetch_douyin(acc):
    import tikhub
    d = tikhub.call("/api/v1/douyin/web/fetch_user_post_videos", {"sec_user_id": acc["sec_uid"], "max_cursor": 0, "count": 20})
    out = []
    for a in (d.get("data") or {}).get("aweme_list") or []:
        s = a.get("statistics") or {}
        out.append({"链接": f"https://www.douyin.com/video/{a['aweme_id']}", "标题": (a.get("desc") or "")[:60],
                    "互动": {"点赞": s.get("digg_count"), "评论": s.get("comment_count"), "转发": s.get("share_count"), "收藏": s.get("collect_count")},
                    "发布日期": datetime.fromtimestamp(a.get("create_time", 0), timezone.utc).date().isoformat(), "形式": "口播"})
    return out


def load_config(root):
    p = Path(root) / "雷达.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def seeds(entries, n=5):
    """没配对标号时：索引里点赞最高的 X 账号（链接里能读出用户名，免费抓）。"""
    best = {}
    for e in entries:
        m = re.match(r"https://(?:x|twitter)\.com/([^/]+)/status/", str(e.get("链接") or ""))
        likes = (e.get("互动") or {}).get("点赞")
        if m and isinstance(likes, int):
            best[m.group(1)] = max(best.get(m.group(1), 0), likes)
    return [{"平台": "X", "账号": u, "赛道": next((e["赛道"] for e in entries if f"/{u}/" in str(e.get("链接"))), "")}
            for u, _ in sorted(best.items(), key=lambda kv: -kv[1])[:n]]


def pick(items, mult, plat):
    likes = [i["互动"]["点赞"] for i in items if isinstance(i["互动"].get("点赞"), int)]
    if not likes:
        return []
    line = max(mult * statistics.median(likes), FLOOR.get(plat, 0))
    return sorted([i for i in items if isinstance(i["互动"].get("点赞"), int) and i["互动"]["点赞"] >= line],
                  key=lambda i: -i["互动"]["点赞"])


def entry_text(acc, it, today):
    hd = it["互动"]
    tags = acc.get("话题") or []
    return ("---\n" + f"链接: {it['链接']}\n平台: {acc['平台']}\n赛道: {acc.get('赛道') or ''}\n形式: {it.get('形式') or ''}\n"
            f"账号: {acc['账号']}\n标题: {json.dumps(it['标题'], ensure_ascii=False)}\n"
            f"互动: {{点赞: {hd.get('点赞')}, 评论: {hd.get('评论')}, 转发: {hd.get('转发')}, 收藏: {hd.get('收藏')}}}\n"
            f"标签: [{', '.join(tags)}]\n来源: 雷达\n发现日期: {today}\n发布日期: {it.get('发布日期') or '没抓到'}\n类型: 链接\n放的人: 雷达\n---\n")


def run(root, fetched=None, look=20, dry=False, today=None):
    """fetched：测试用，{账号: [作品…]}，给了就不上网。返回简报文字。"""
    root, today = Path(root), today or date.today().isoformat()
    cfg, entries = load_config(root), idx.collect(root)
    accounts = cfg.get("账号") or seeds(entries)
    mult, paid = cfg.get("倍数", 3), cfg.get("付费", False) and os.environ.get("TIKHUB_API_KEY")
    links = {str(e.get("链接")) for e in entries}
    per = {}
    for e in entries:
        per[(e.get("平台"), e.get("账号"))] = per.get((e.get("平台"), e.get("账号")), 0) + 1
    lines, new, remind = [], 0, []
    for acc in accounts:
        key = (acc["平台"], acc["账号"])
        try:
            if fetched is not None:
                items = fetched.get(acc["账号"], [])
            elif acc["平台"] == "X":
                try:
                    items = fetch_x(acc)
                except Exception:
                    if not paid:
                        raise
                    items = fetch_x_paid(acc)
            elif acc["平台"] == "抖音" and paid and acc.get("sec_uid"):
                items = fetch_douyin(acc)
            else:
                remind.append(f"{acc['平台']}·{acc['账号']}")
                continue
        except Exception as ex:  # 一个号抓不到不拖垮整批
            lines.append(f"- {acc['平台']}·{acc['账号']}：没抓到（{str(ex)[:60]}）")
            continue
        got = 0
        for it in pick(items[:look], mult, acc["平台"]):
            if it["链接"] in links or per.get(key, 0) >= CAP:
                continue
            try:  # 时间关和入库一样：AI 应用 183 天、其余 365 天
                if (date.fromisoformat(today) - date.fromisoformat(it.get("发布日期") or "")).days > (183 if acc.get("赛道") == "AI应用" else 365):
                    continue
            except ValueError:
                pass
            name = f"{today}-{acc['平台']}-{it['链接'].rstrip('/').split('/')[-1]}.md"
            if not dry:
                (root / "收件箱").mkdir(exist_ok=True)
                (root / "收件箱" / name).write_text(entry_text(acc, it, today), encoding="utf-8")
            links.add(it["链接"]); per[key] = per.get(key, 0) + 1; got += 1; new += 1
            lines.append(f"- {acc['平台']}·{acc['账号']}｜{it['标题'][:30]}｜赞 {it['互动']['点赞']}｜{it['链接']}")
        if not got:
            lines.append(f"- {acc['平台']}·{acc['账号']}：这批没有过爆款线的新作品（或已收满 {CAP} 条）")
    if not dry:
        idx.build(root)
    tags = {}
    for e in entries:
        for t in e.get("标签") or []:
            tags[str(t)] = tags.get(str(t), 0) + 1
    out = [f"雷达简报（{today}）：新收 {new} 条进收件箱，已进目录和索引，说「拆」就拆成卡", *lines]
    if remind:
        out.append("这些号我这边抓不了（没开付费或平台不支持），这周刷到它们的爆款，把链接丢给我：" + "、".join(remind))
    if not cfg.get("账号"):
        out.append("还没设对标号，这次用库里点赞最高的号当种子；想换就在 雷达.json 里写上你的对标号" if accounts else
                   "还没设对标号，库里也还没有能当种子的号：把你常看的同行账号告诉我（平台＋账号名），我写进 雷达.json；不设也行，这周刷到爆款把链接丢给我")
    if tags:
        out.append("库里最常见的话题：" + "、".join(k for k, _ in sorted(tags.items(), key=lambda kv: -kv[1])[:5]) + "——可以拿这些词去搜新号")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--库", default=str(HERE))
    ap.add_argument("--看", type=int, default=20, help="每个号看最近几条")
    ap.add_argument("--只看", action="store_true", help="只出简报，不写收件箱")
    a = ap.parse_args(argv)
    print(run(a.库, look=a.看, dry=a.只看))


if __name__ == "__main__":
    main()

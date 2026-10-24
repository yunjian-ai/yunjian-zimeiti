import re
from core import attempt, session, ytdlp_info, fill_from_ytdlp, ts, UA_DESKTOP, Fail
NAME, MATCH = "bilibili", r"(bilibili\.com|b23\.tv)/"
REF = "https://www.bilibili.com"


def guest():
    s = session(UA_DESKTOP, REF)
    d = s.get("https://api.bilibili.com/x/frontend/finger/spi", timeout=20).json()["data"]
    s.cookies.update({"buvid3": d["b_3"], "buvid4": d["b_4"]})  # guest device ids, not an account
    return s


def scrape(res, o):
    if "b23.tv" in res.url:
        res.url = session().get(res.url, timeout=20, allow_redirects=True).url
    bv = (re.search(r"(BV[0-9A-Za-z]{10})", res.url) or [None, None])[1]
    s = guest()
    st = {}

    def view(path="view"):
        r = s.get(f"https://api.bilibili.com/x/web-interface/{path}", params={"bvid": bv}, timeout=20)
        if not r.text.startswith("{"):
            raise Fail("risk-control HTML (datacenter IP)")
        d = r.json()
        if d["code"]:
            raise Fail(d.get("message"))
        put(d["data"])

    def put(v):
        st.update(aid=v["aid"], cid=v["cid"])
        res.title, res.author = v["title"], v["owner"]["name"]
        res.published, res.text = ts(v.get("pubdate")), v.get("desc", "")
        s_ = v["stat"]; res.stats = {"views": s_["view"], "likes": s_["like"], "coins": s_["coin"], "favorites": s_["favorite"], "shares": s_["share"], "comments": s_["reply"], "danmaku": s_["danmaku"]}
        res.images.append(v["pic"].replace("http:", "https:"))

    def html_state():
        h = s.get(f"https://www.bilibili.com/video/{bv}/", timeout=20).text
        m = re.search(r"__INITIAL_STATE__=(\{.*?\});\(function", h)
        if not m:
            raise Fail("no __INITIAL_STATE__")
        import json
        put(json.loads(m.group(1))["videoData"])

    def ytd():
        fill_from_ytdlp(res, ytdlp_info(res.url))
    if not bv:
        raise Fail("only BV video links supported")
    attempt(res, "content", [("api wbi/view (no w_rid needed)", lambda: view("wbi/view")), ("api view (UA+Referer+guest buvid3)", view), ("page __INITIAL_STATE__", html_state), ("yt-dlp", ytd)])

    def play():
        d = s.get("https://api.bilibili.com/x/player/playurl", params={"avid": st["aid"], "cid": st["cid"], "fnval": 16, "qn": 32}, timeout=20).json()["data"]["dash"]
        res.extra["dash_audio"] = d["audio"][0]["baseUrl"]
        res.extra["dash_video"] = sorted(d["video"], key=lambda x: x["bandwidth"])[0]["baseUrl"]
        res.videos.append(("bili_dash", res.url))
    if st:
        attempt(res, "media", [("playurl DASH (guest)", play)])

    if o.with_comments and st:
        def cm():
            d = s.get("https://api.bilibili.com/x/v2/reply", params={"type": 1, "oid": st["aid"], "sort": 1, "ps": 20}, timeout=20).json()
            res.comments = [{"author": r["member"]["uname"], "text": r["content"]["message"], "likes": r["like"], "time": ts(r["ctime"])} for r in (d.get("data") or {}).get("replies") or []]
            if not res.comments:
                raise Fail(f"code {d.get('code')}")
        attempt(res, "comments", [("/x/v2/reply (guest buvid)", cm)])

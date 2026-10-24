import re, json, time
from core import attempt, session, Fail, UA_DESKTOP
NAME, MATCH = "xiaohongshu", r"(xiaohongshu\.com|xhslink\.com)/"
EDITH = "https://edith.xiaohongshu.com"


class Guest:
    """Guest web session signed locally with xhshow (no user account)."""
    def __init__(self):
        from xhshow import Xhshow
        self.x = Xhshow(); a1 = self.x.generate_a1()
        self.s = session(UA_DESKTOP, "https://www.xiaohongshu.com/", {"a1": a1, "webId": self.x.generate_web_id(a1), "xsecappid": "xhs-pc-web"})
        self.s.headers.update({"Origin": "https://www.xiaohongshu.com", "Content-Type": "application/json;charset=UTF-8"})
        self.post("/api/sns/web/v1/login/activate", {})

    def post(self, uri, body):
        h = self.x.sign_headers_post(uri, dict(self.s.cookies), payload=body)
        r = self.s.post(EDITH + uri, data=json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode(), headers=h, timeout=20)
        return r

    def get(self, uri, params):
        h = self.x.sign_headers_get(uri, dict(self.s.cookies), params=params)
        return self.s.get(EDITH + uri, params=params, headers=h, timeout=20)


def orig(url):
    """Rebuild original-resolution image from any xhscdn URL via its trace id."""
    m = re.search(r"/(1040g[0-9a-z]+|[0-9a-z]{30,})(?:!|$|\?)", url or "")
    return f"https://ci.xiaohongshu.com/{m.group(1)}?imageView2/format/jpg" if m else url


def scrape(res, o):
    if "xhslink.com" in res.url:
        res.url = session().get(res.url, timeout=20).url
    nid = (re.search(r"(?:explore|discovery/item|item)/([0-9a-f]{24})", res.url) or [None, None])[1]
    tok = (re.search(r"xsec_token=([^&]+)", res.url) or [None, None])[1]
    g = {}

    def guest():
        g["c"] = Guest()

    def feed_detail():
        if not (nid and tok):
            raise Fail("note URL must include xsec_token (copy full share link)")
        r = g["c"].post("/api/sns/web/v1/feed", {"source_note_id": nid, "image_formats": ["jpg", "webp", "avif"], "extra": {"need_body_topic": "1"}, "xsec_source": "pc_feed", "xsec_token": tok})
        d = r.json()
        items = (d.get("data") or {}).get("items") or []
        if not items:
            raise Fail(f"HTTP {r.status_code} {d.get('code')} (461 = risk control, typical on datacenter IPs)")
        n = items[0]["note_card"]
        res.title, res.text = n.get("title", ""), n.get("desc", "")
        res.author = n["user"].get("nickname", ""); res.published = str(n.get("time", ""))
        ii = n.get("interact_info", {}); res.stats = {"likes": ii.get("liked_count"), "collects": ii.get("collected_count"), "comments": ii.get("comment_count"), "shares": ii.get("share_count")}
        res.images = [orig(i.get("url_default") or i.get("url")) for i in n.get("image_list", [])]

    def note_page():
        if not (nid and tok):
            raise Fail("needs xsec_token")
        r = g["c"].s.get(f"https://www.xiaohongshu.com/explore/{nid}", params={"xsec_token": tok, "xsec_source": "pc_feed"}, timeout=20)
        m = re.search(r"__INITIAL_STATE__=(\{.*?\})</script>", r.text, re.S)
        if "/login" in r.url or not m:
            raise Fail("redirected to login (datacenter IP / risk control)")
        st = json.loads(m.group(1).replace("undefined", "null"))
        n = list(st["note"]["noteDetailMap"].values())[0]["note"]
        res.title, res.text, res.author = n.get("title"), n.get("desc"), n["user"]["nickname"]
        ii = n.get("interactInfo", {}); res.stats = {"likes": ii.get("likedCount"), "collects": ii.get("collectedCount"), "comments": ii.get("commentCount")}
        res.images = [orig(i.get("urlDefault")) for i in n.get("imageList", [])]

    def homefeed():
        body = {"cursor_score": "", "num": 20, "refresh_type": 1, "note_index": 0, "unread_begin_note_id": "", "unread_end_note_id": "", "unread_note_count": 0, "category": "homefeed_recommend", "search_key": "", "need_num": 20, "image_formats": ["jpg", "webp", "avif"], "need_filter_image": False}
        d = g["c"].post("/api/sns/web/v1/homefeed", body).json()
        its = (d.get("data") or {}).get("items") or []
        if not its:
            raise Fail(f"homefeed code {d.get('code')}")
        res.title = "小红书 homefeed (guest)"
        for i in its:
            c = i.get("note_card") or {}
            res.items.append({"title": c.get("display_title", ""), "url": f"https://www.xiaohongshu.com/explore/{i['id']}?xsec_token={i.get('xsec_token')}&xsec_source=pc_feed",
                              "stats": f"likes {c.get('interact_info', {}).get('liked_count')} by {c.get('user', {}).get('nickname') or c.get('user', {}).get('nick_name')}",
                              "cover": orig((c.get("cover") or {}).get("url_default"))})
        if its and not res.images:
            res.images.append(res.items[0]["cover"])
    if not attempt(res, "session", [("xhshow-signed guest session", guest)]):
        return
    if nid:
        attempt(res, "content", [("signed /api/sns/web/v1/feed", feed_detail), ("note page __INITIAL_STATE__", note_page)])
    else:
        attempt(res, "list", [("signed guest homefeed", homefeed)])
    if o.with_comments:
        def cm():
            d = g["c"].get("/api/sns/web/v2/comment/page", {"note_id": nid, "cursor": "", "top_comment_id": "", "image_formats": "jpg,webp,avif", "xsec_token": tok or ""}).json()
            cs = (d.get("data") or {}).get("comments") or []
            if not cs:
                raise Fail(f"code {d.get('code')}")
            res.comments = [{"author": c["user_info"]["nickname"], "text": c["content"], "likes": c.get("like_count")} for c in cs]
        attempt(res, "comments", [("signed comment/page", cm)])

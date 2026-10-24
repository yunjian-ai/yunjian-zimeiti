import re
from core import attempt, get, meta_tag, strip_html, ts, Fail
NAME, MATCH = "wechat", r"mp\.weixin\.qq\.com/"


def scrape(res, o):
    def page():
        h = get(res.url).text
        m = re.search(r'id="js_content"[^>]*>(.*?)</div>\s*<script', h, re.S) or re.search(r'id="js_content"[^>]*>(.*)', h, re.S)
        if not m:
            raise Fail("no #js_content (deleted/blocked article or captcha)")
        body = m.group(1)
        res.title = meta_tag(h, "og:title")
        res.author = (re.search(r'var nickname = htmlDecode\("([^"]*)"', h) or re.search(r'id="js_name">\s*([^<]+)', h) or [0, ""])[1].strip()
        t = re.search(r"var ct = \"(\d+)\"", h) or re.search(r"create_time\s*[:=]\s*['\"]?(\d+)", h)
        res.published = ts(t.group(1)) if t else ""
        res.text = strip_html(body)
        cov = meta_tag(h, "og:image")
        res.images = ([cov] if cov else []) + re.findall(r'data-src="(https://mmbiz\.qpic\.cn[^"]+)"', body)
    attempt(res, "content", [("article HTML #js_content", page)])
    res.extra["note"] = "Read/like counts and comments are not public -> BeatAPI"
    res.needs_beatapi.append("stats")  # 执笔加：阅读、点赞不公开，交给付费兜底（TikHub / BeatAPI）
    if o.with_comments:
        res.needs_beatapi.append("comments")

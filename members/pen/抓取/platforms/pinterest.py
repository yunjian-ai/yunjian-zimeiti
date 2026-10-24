import re, json, subprocess, sys, os
from core import attempt, get, Fail
NAME, MATCH = "pinterest", r"(pinterest\.[a-z.]+|pin\.it)/"


def scrape(res, o):
    def gdl():
        exe = os.path.join(os.path.dirname(sys.executable), "gallery-dl")
        out = subprocess.run([exe, "-j", res.url], capture_output=True, text=True, timeout=90).stdout
        d = [x for x in json.loads(out) if x[0] == 3]
        if not d:
            raise Fail("gallery-dl returned no media")
        m = d[0][2]
        res.title = m.get("title") or m.get("grid_title") or ""; res.text = m.get("description") or ""
        res.author = (m.get("pinner") or {}).get("username", ""); res.published = str(m.get("created_at", ""))
        res.stats = {"saves": m.get("repin_count"), "comments": m.get("comment_count"), "reactions": m.get("reaction_counts")}
        res.images = [x[1] for x in d]

    def oembed():
        d = get("https://www.pinterest.com/oembed.json?url=" + res.url).json()
        res.title = res.title or d.get("title"); res.author = res.author or d.get("author_name")
        if not res.images and d.get("thumbnail_url"):
            res.images.append(d["thumbnail_url"])
    attempt(res, "content", [("gallery-dl -j", gdl), ("oEmbed", oembed)])
    if o.with_comments:
        res.needs_beatapi.append("comments")

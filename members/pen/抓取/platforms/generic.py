from core import attempt, ytdlp_info, fill_from_ytdlp, get, meta_tag
NAME, MATCH = "generic", r"."


def scrape(res, o):
    def ytd():
        fill_from_ytdlp(res, ytdlp_info(res.url))
    def og():
        h = get(res.url).text
        res.title, res.text = meta_tag(h, "og:title"), meta_tag(h, "og:description")
        if meta_tag(h, "og:image"):
            res.images.append(meta_tag(h, "og:image"))
        if not res.title:
            raise RuntimeError("no og tags")
    attempt(res, "content", [("yt-dlp generic", ytd), ("OpenGraph tags", og)])

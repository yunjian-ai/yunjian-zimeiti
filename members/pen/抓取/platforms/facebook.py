import re
from core import attempt, ytdlp_info, fill_from_ytdlp, get, UA_GOOGLEBOT
NAME, MATCH = "facebook", r"(facebook\.com|fb\.watch)/"


def scrape(res, o):
    def ytd():
        fill_from_ytdlp(res, ytdlp_info(res.url))
    def bot():
        h = get(res.url, UA_GOOGLEBOT).text
        for k, pat in (("reactions", r"([\d.,]+[KM]?) reactions"), ("views", r"([\d.,]+[KM]?) views"), ("comments", r"([\d.,]+[KM]?) comments"), ("shares", r"([\d.,]+[KM]?) shares")):
            m = re.search(pat, h)
            if m:
                res.stats[k] = m.group(1)
        if not res.stats:
            raise RuntimeError("no counters in crawler page")
    attempt(res, "content", [("yt-dlp Facebook extractor (public video)", ytd)])
    attempt(res, "stats", [("Googlebot UA page counters", bot)])
    res.extra["note"] = "Cover: if no thumbnail, use --with-media; a frame is grabbed with ffmpeg. Posts/profiles need login -> BeatAPI"
    if o.with_comments:
        res.needs_beatapi.append("comments")

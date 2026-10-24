from core import attempt, ytdlp_info, fill_from_ytdlp
NAME, MATCH = "instagram", r"instagram\.com/"


def scrape(res, o):
    def ytd():
        info = ytdlp_info(res.url, {"getcomments": bool(o.with_comments)})
        entries = list(info.get("entries") or []) if info.get("_type") == "playlist" else []
        fill_from_ytdlp(res, info)
        for e in entries[1:]:
            if e.get("thumbnail"):
                res.images.append(e["thumbnail"])
        if not res.text and not res.stats:
            raise RuntimeError("empty (profile pages need login)")
    attempt(res, "content", [("yt-dlp Instagram extractor (post/reel, guest GraphQL)", ytd)])
    res.extra["note"] = "Images are ~853px; 1080 originals, profiles and comments need login -> BeatAPI"
    if o.with_comments and not res.comments:
        res.needs_beatapi.append("comments")

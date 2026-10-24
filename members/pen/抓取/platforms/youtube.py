from core import attempt, ytdlp_info, fill_from_ytdlp
NAME, MATCH = "youtube", r"(youtube\.com|youtu\.be)/"


def scrape(res, o):
    def meta():
        extra = {"getcomments": True, "extractor_args": {"youtube": {"max_comments": ["20", "all", "0", "0"]}}} if o.with_comments else {}
        extra.update({"writesubtitles": True, "writeautomaticsub": True})
        info = ytdlp_info(res.url, extra)
        fill_from_ytdlp(res, info)
        subs = {**(info.get("automatic_captions") or {}), **(info.get("subtitles") or {})}
        res.extra["subtitle_langs"] = sorted(subs)[:30]
        for lang in ("zh-Hans", "zh", "en", "en-orig"):
            for f in subs.get(lang, []):
                if f.get("ext") == "vtt":
                    res.extra["subtitle_url"] = f["url"]; res.extra["subtitle_lang"] = lang; break
            if "subtitle_url" in res.extra:
                break
    attempt(res, "content", [("yt-dlp", meta)])
    if o.with_comments and not res.comments:
        res.needs_beatapi.append("comments")

"""Optional paid fallback via BeatAPI Capabilities API (https://docs.beatapi.io/capabilities).

- find/inspect/check need no key; run needs env BEATAPI_API_KEY.
- Used by scrape.py only with --fallback-beatapi AND BEATAPI_API_KEY set. The key is never printed or logged.
- CLI:  python beatapi.py find "<platform + action>"      (list references)
        python beatapi.py inspect <reference>               (input schema)
        python beatapi.py check                             (verify every mapped reference still exists)
"""
import os, re, sys, json, requests

API = os.environ.get("BEATAPI_BASE", "https://api.beatapi.io")
SIGNUP_URL = "https://beatapi.io/sign-up"
KEYS_URL = "https://beatapi.io/dashboard/apikeys"
BILLING_URL = "https://beatapi.io/dashboard/billing"
DOCS_URL = "https://docs.beatapi.io/capabilities"


def _rx(p, s):
    m = re.search(p, s or "")
    return m.group(1) if m else None


# (platform, capability) -> (reference, input builder(url, meta) -> dict).
# Search builders read the keyword from env BEATAPI_KEYWORD (scrape.py --search sets it).
# Any builder's output can be extended/overridden with env BEATAPI_INPUT='{"key": "value"}' (for two-step ids such as secUid/user_id).
KW = lambda: os.environ.get("BEATAPI_KEYWORD")
AWEME = lambda u: _rx(r"(\d{15,20})", u)
XHS_NOTE = lambda u: _rx(r"/(?:explore|item|discovery/item)/([0-9a-f]{24})", u)
WEB_READ = ("data:web.read", lambda u, m: {"urls": [u]})
REFS = {
    # 抖音
    ("douyin", "content"): ("data:douyin.app.v3.fetch_one_video", lambda u, m: {"aweme_id": AWEME(u)}),
    ("douyin", "comments"): ("data:douyin.app.v3.fetch_video_comments", lambda u, m: {"aweme_id": AWEME(u), "count": 20}),
    ("douyin", "profile"): ("data:douyin.web.handler_user_profile", lambda u, m: {"sec_user_id": _rx(r"/user/([\w-]+)", u)}),
    ("douyin", "list"): ("data:douyin.web.fetch_user_post_videos", lambda u, m: {"sec_user_id": _rx(r"/user/([\w-]+)", u)}),
    ("douyin", "search"): ("data:douyin.app.v3.open_douyin_app_to_keyword_search", lambda u, m: {"keyword": KW()}),
    # 小红书
    ("xiaohongshu", "content"): ("data:xiaohongshu.web_v3.fetch_note_detail", lambda u, m: {"note_id": XHS_NOTE(u), "xsec_token": _rx(r"xsec_token=([^&]+)", u)}),
    ("xiaohongshu", "comments"): ("data:xiaohongshu.app_v2.get_note_comments", lambda u, m: {"note_id": XHS_NOTE(u)}),
    ("xiaohongshu", "profile"): ("data:xiaohongshu.web_v3.fetch_user_info", lambda u, m: {"user_id": _rx(r"/user/profile/([0-9a-f]{24})", u)}),
    ("xiaohongshu", "list"): ("data:xiaohongshu.app_v2.get_user_posted_notes", lambda u, m: {"user_id": _rx(r"/user/profile/([0-9a-f]{24})", u)} if "/user/profile/" in u else {"share_text": u}),
    ("xiaohongshu", "search"): ("data:xiaohongshu.app_v2.search_notes", lambda u, m: {"keyword": KW()}),
    # TikTok
    ("tiktok", "comments"): ("data:tiktok.app.v3.fetch_video_comments", lambda u, m: {"aweme_id": _rx(r"/video/(\d+)", u), "count": 20}),
    ("tiktok", "profile"): ("data:tiktok.web.fetch_user_profile", lambda u, m: {"uniqueId": _rx(r"tiktok\.com/@([\w.-]+)", u)}),
    ("tiktok", "list"): ("data:tiktok.web.fetch_user_post", lambda u, m: {}),  # needs secUid from profile -> BEATAPI_INPUT
    ("tiktok", "search"): ("data:tiktok.app.v3.fetch_general_search_result", lambda u, m: {"keyword": KW()}),
    # Instagram
    ("instagram", "comments"): ("data:instagram.v2.fetch_post_comments", lambda u, m: {"code_or_url": u}),
    ("instagram", "list"): ("data:instagram.v2.fetch_user_posts", lambda u, m: {"username": _rx(r"instagram\.com/([\w.]+)/?(?:$|\?)", u)}),
    ("instagram", "search"): ("data:instagram.v2.general_search", lambda u, m: {"keyword": KW()}),
    # X
    ("x", "comments"): ("data:twitter.web.fetch_post_comments", lambda u, m: {"tweet_id": _rx(r"/status/(\d+)", u)}),
    ("x", "list"): ("data:twitter.web.fetch_user_post_tweet", lambda u, m: {"screen_name": _rx(r"(?:twitter|x)\.com/(\w{1,15})", u)}),
    ("x", "search"): ("data:twitter.web.fetch_search_timeline", lambda u, m: {"keyword": KW()}),
    # YouTube
    ("youtube", "comments"): ("data:youtube.web_v2.get_video_comments", lambda u, m: {"video_id": _rx(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", u)}),
    ("youtube", "subtitles"): ("data:youtube.web_v2.get_video_captions", lambda u, m: {"video_id": _rx(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", u), "format": "srt"}),
    ("youtube", "list"): ("data:youtube.web_v2.get_channel_videos", lambda u, m: {"channel_id": _rx(r"/channel/(UC[\w-]{22})", u)}),
    ("youtube", "search"): ("data:youtube.web_v2.get_general_search", lambda u, m: {"search_query": KW()}),
    # B站
    ("bilibili", "comments"): ("data:bilibili.web.fetch_video_comments", lambda u, m: {"bv_id": _rx(r"(BV[0-9A-Za-z]{10})", u)}),
    ("bilibili", "list"): ("data:bilibili.web.fetch_user_post_videos", lambda u, m: {"uid": _rx(r"space\.bilibili\.com/(\d+)", u)}),
    ("bilibili", "search"): ("data:bilibili.web.fetch_general_search", lambda u, m: {"keyword": KW()}),
    # 公众号
    ("wechat", "stats"): ("data:wechat_mp.v2.fetch_article_stats", lambda u, m: {"url": u}),
    ("wechat", "comments"): ("data:wechat_mp.v2.fetch_article_comments", lambda u, m: {"url": u}),
    ("wechat", "content"): ("data:wechat_mp.v2.fetch_article_detail_h5", lambda u, m: {"url": u}),
    # Threads
    ("threads", "comments"): ("data:threads.web.fetch_post_detail_v2", lambda u, m: {"url": u}),
    ("threads", "content"): ("data:threads.web.fetch_post_detail_v2", lambda u, m: {"url": u}),
    ("threads", "profile"): ("data:threads.web.fetch_user_info", lambda u, m: {"username": _rx(r"threads\.(?:net|com)/@([\w.]+)", u)}),
    ("threads", "list"): ("data:threads.web.fetch_user_posts", lambda u, m: {}),  # needs user_id from profile -> BEATAPI_INPUT
    ("threads", "search"): ("data:threads.web.search_recent", lambda u, m: {"query": KW()}),
    # LinkedIn (content is routed by URL type, see route())
    ("linkedin", "content"): ("data:linkedin.web_v2.get_post_detail", lambda u, m: {"url": u}),
    ("linkedin", "comments"): ("data:linkedin.web_v2.get_post_comments", lambda u, m: {"urn": _rx(r"activity[-:](\d{15,})", u)}),
    ("linkedin", "profile"): ("data:linkedin.web_v2.get_user_profile", lambda u, m: {"url": u}),
    ("linkedin", "company"): ("data:linkedin.web_v2.get_company_profile", lambda u, m: {"url": u}),
    ("linkedin", "list"): ("data:linkedin.web_v2.get_user_posts", lambda u, m: {"url": u}),
    ("linkedin", "company_posts"): ("data:linkedin.web_v2.get_company_posts", lambda u, m: {"url": u}),
    ("linkedin", "job"): ("data:linkedin.web_v2.get_job_detail", lambda u, m: {"url": u}),
    ("linkedin", "search"): ("data:linkedin.web_v2.search_jobs", lambda u, m: {"keywords": KW()}),
    # Reddit (rarely needed)
    ("reddit", "search"): ("data:reddit.app.fetch_dynamic_search", lambda u, m: {"query": KW()}),
    # Generic web reader (no dedicated capability)
    ("facebook", "content"): WEB_READ, ("facebook", "comments"): WEB_READ, ("facebook", "stats"): WEB_READ,
    ("pinterest", "content"): WEB_READ, ("pinterest", "comments"): WEB_READ,
    ("medium", "content"): WEB_READ, ("medium", "comments"): WEB_READ, ("medium", "stats"): WEB_READ,
    ("generic", "content"): WEB_READ,
}


def route(platform, cap, url):
    """Pick the most specific capability for a URL (e.g. LinkedIn profile vs company vs job vs post)."""
    u = url or ""
    if platform == "linkedin" and cap in ("content", "profile", "list"):
        if "/jobs/" in u:
            return "job"
        if "/company/" in u:
            return "company" if cap != "list" else "company_posts"
        if "/in/" in u:
            return "profile" if cap == "content" else cap
    if platform in ("tiktok", "threads", "douyin", "xiaohongshu", "instagram") and cap == "content" and (
            "/user/" in u or re.search(r"(tiktok\.com/@[\w.-]+/?$|threads\.(net|com)/@[\w.]+/?$|instagram\.com/[\w.]+/?$)", u)):
        return "profile" if (platform, "profile") in REFS else "list"
    if platform == "x" and cap == "profile":
        return "list"
    return cap


def capability_name(platform, cap, url=None):
    cap = route(platform, cap, url)
    env = os.environ.get(f"BEATAPI_REF_{platform.upper()}_{cap.upper()}")
    if env:
        return env
    if (platform, cap) in REFS:
        return REFS[(platform, cap)][0]
    return None  # unmapped: use `python beatapi.py find "<platform> <cap>"`


def hint(platform, cap, url=None):
    ref = capability_name(platform, cap, url)
    have_key = bool(os.environ.get("BEATAPI_API_KEY"))
    lines = [f"  >> '{cap}' failed with all free methods -> paid fallback: BeatAPI " + (f"capability {ref}" if ref else f"(no mapped capability; run: python beatapi.py find \"{platform} {cap}\")")]
    if not have_key:
        lines.append(f"     Setup: sign up {SIGNUP_URL} -> create key {KEYS_URL} -> top up in dashboard {BILLING_URL}")
        lines.append("     Then: put your key in the env var BEATAPI_API_KEY  (in Grok Bot: ask the bot for a secret-input card named BEATAPI_API_KEY)")
    lines.append("     Rerun with --fallback-beatapi")
    return "\n".join(lines)


def _post(path, body, key=None):
    h = {"Content-Type": "application/json"}
    if key:
        h["Authorization"] = "Bearer " + key
    r = requests.post(API + path, headers=h, json=body, timeout=120)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"error": {"code": f"http_{r.status_code}", "message": r.text[:200]}}


def find(query, limit=8):
    _, d = _post("/v1/capabilities/search", {"query": query, "limit": limit})
    return (d.get("data") or {}).get("data") or []


def inspect(reference):
    return _post("/v1/capabilities/inspect", {"reference": reference})[1]


def run(platform, cap, url, out_path, meta=None):
    key = os.environ.get("BEATAPI_API_KEY")
    if not key:
        raise RuntimeError("BEATAPI_API_KEY not set")
    cap = route(platform, cap, url)
    ref = capability_name(platform, cap, url)
    if not ref:
        raise RuntimeError(f'no mapped capability; run: python beatapi.py find "{platform} {cap}"')
    builder = REFS.get((platform, cap), (None, lambda u, m: {"url": u}))[1]
    inp = {k: v for k, v in (builder(url, meta or {}) or {}).items() if v not in (None, "")}
    if os.environ.get("BEATAPI_INPUT"):
        inp.update(json.loads(os.environ["BEATAPI_INPUT"]))
    code, d = _post("/v1/capabilities/run", {"reference": ref, "operation": "start", "input": inp, "view": "full"}, key)
    json.dump(d, open(out_path, "w"), ensure_ascii=False, indent=1)
    if code >= 400 or "error" in d:
        e = d.get("error") or {}
        raise RuntimeError(f"BeatAPI {code} {e.get('code')}: {e.get('message', '')[:160]} (request_id {e.get('request_id')})")
    return ref


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "find":
        for c in find(" ".join(sys.argv[2:])):
            print(f"{c['reference']}\n    {c.get('title')} | {c.get('readiness')} | input: {c.get('signature')}")
    elif cmd == "inspect":
        d = inspect(sys.argv[2]); x = d.get("data", d)
        print(json.dumps({k: x.get(k) for k in ("reference", "readiness", "input_schema", "error")}, ensure_ascii=False, indent=1))
    elif cmd == "check":
        cache, bad = {}, 0
        for (p, c), (ref, _) in sorted(REFS.items()):
            if ref not in cache:
                d = inspect(ref); cache[ref] = "MISSING" if "error" in d else (d.get("data") or {}).get("readiness")
            bad += cache[ref] == "MISSING"
            print(f"{p:<12}{c:<14}{ref:<56}{cache[ref]}")
        print(f"{len(REFS)} mappings, {len(cache)} unique references, {bad} missing"); sys.exit(1 if bad else 0)

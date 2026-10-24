"""Shared helpers: HTTP, downloads, yt-dlp wrapper, unified Result + writers."""
import json, os, re, html, subprocess, shutil, datetime as dt
import requests

UA_DESKTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
UA_ANDROID = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
UA_GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
UA_FBEXT = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
TIMEOUT = 25


class Fail(Exception):
    """A free method failed; message explains why."""


class Result:
    def __init__(self, platform, url):
        self.platform, self.url = platform, url
        self.title = self.author = self.published = self.text = ""
        self.stats = {}          # likes/comments/shares/views/...
        self.images = []         # remote URLs (best quality first)
        self.videos = []         # remote URLs or ("ytdlp", url)
        self.comments = []       # [{author,text,likes,time}]
        self.items = []          # list pages: [{title,url,time,stats}]
        self.extra = {}
        self.methods = []        # (capability, method, ok, note)
        self.media_files = []
        self.needs_beatapi = []  # capability names

    def log(self, cap, method, ok, note=""):
        self.methods.append({"capability": cap, "method": method, "ok": ok, "note": str(note)[:300]})
        print(f"  [{'OK ' if ok else 'FAIL'}] {cap:<9} via {method}" + (f" -- {note}" if note and not ok else ""))

    def to_meta(self):
        d = {k: v for k, v in self.__dict__.items() if k != "videos"}
        d["videos"] = [v if isinstance(v, str) else v[1] for v in self.videos]
        return d


def session(ua=UA_DESKTOP, referer=None, cookies=None):
    s = requests.Session()
    s.headers["User-Agent"] = ua
    if referer:
        s.headers["Referer"] = referer
    if cookies:
        s.cookies.update(cookies)
    return s


def get(url, ua=UA_DESKTOP, s=None, **kw):
    s = s or session(ua)
    r = s.get(url, timeout=TIMEOUT, **kw)
    return r


def ts(x):
    try:
        if isinstance(x, (int, float)) or str(x).isdigit():
            t = dt.datetime.fromtimestamp(int(x), dt.timezone.utc)
        else:
            t = dt.datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(x or "")


def meta_tag(h, prop):
    m = re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"' % re.escape(prop), h)
    return html.unescape(m.group(1)) if m else ""


def strip_html(s):
    s = re.sub(r"<br\s*/?>|</p>", "\n", s or "")
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def have_ffmpeg():
    return shutil.which("ffmpeg") is not None


class _Quiet:
    def debug(self, m): pass
    def warning(self, m): pass
    def error(self, m): pass


def ytdlp_info(url, extra=None):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "logger": _Quiet(), "skip_download": True, "ignore_no_formats_error": True}
    opts.update(extra or {})
    with yt_dlp.YoutubeDL(opts) as y:
        return y.extract_info(url, download=False)


def ytdlp_download(url, outdir, audio_only=False, max_mb=60):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "outtmpl": os.path.join(outdir, "video.%(ext)s"),
            "noprogress": True,
            "format": f"b[filesize<{max_mb}M]/b[filesize_approx<{max_mb}M]/b[height<=480]/w/bv*[height<=480]+ba/bv*+ba"}
    if audio_only:
        opts.update({"format": "ba/b", "outtmpl": os.path.join(outdir, "audio.%(ext)s"),
                     "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}] if have_ffmpeg() else []})
    with yt_dlp.YoutubeDL(opts) as y:
        y.download([url])
    return [os.path.join(outdir, f) for f in os.listdir(outdir) if f.startswith("audio" if audio_only else "video")]


def download(url, path, ua=UA_DESKTOP, referer=None, max_bytes=None):
    h = {"User-Agent": ua}
    if referer:
        h["Referer"] = referer
    if max_bytes:
        h["Range"] = f"bytes=0-{max_bytes}"
    if url.startswith("http://"):
        url = "https://" + url[7:]
    with requests.get(url, headers=h, timeout=60, stream=True) as r:
        if r.status_code not in (200, 206):
            raise Fail(f"HTTP {r.status_code}")
        with open(path, "wb") as f:
            for c in r.iter_content(65536):
                f.write(c)
    if os.path.getsize(path) < 500:
        raise Fail("file too small")
    return path


def extract_audio(video, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-c:a", "libmp3lame", out], check=True)
    return out


def transcribe(audio, lang=None, model="small"):
    import numpy as np
    from faster_whisper import WhisperModel
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", audio, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    prompt = "以下是普通话的句子，使用简体中文。" if lang == "zh" else None  # 执笔加：中文平台固定中文、偏向简体
    segs, _ = WhisperModel(model, device="cpu", compute_type="int8").transcribe(a, language=lang, initial_prompt=prompt)
    text = "\n".join(f"[{s.start:.1f}s] {s.text.strip()}" for s in segs)
    if lang == "zh":
        try:  # 执笔加：繁体兜底转简体（opencc-python-reimplemented，没装就跳过）
            from opencc import OpenCC
            text = OpenCC("t2s").convert(text)
        except ImportError:
            pass
    return text


def write_outputs(res, out):
    os.makedirs(out, exist_ok=True)
    st = " / ".join(f"{k} {v}" for k, v in res.stats.items() if v not in (None, ""))
    L = [f"# {res.title or '(no title)'}", "", f"- Platform: {res.platform}", f"- Author: {res.author}",
         f"- Published: {res.published}", f"- Stats: {st}", f"- URL: {res.url}", ""]
    if res.text:
        L += ["## Text", "", res.text, ""]
    if res.items:
        L += ["## Items", ""] + [f"- [{i.get('time','')}] {i.get('title','')[:200]} {i.get('url','')} {i.get('stats','')}" for i in res.items[:100]] + [""]
    if res.comments:
        L += ["## Comments", ""] + [f"- **{c.get('author','')}** ({c.get('likes','')}): {str(c.get('text','')).strip()[:500]}" for c in res.comments] + [""]
    if res.media_files:
        L += ["## Media", ""] + [f"- {os.path.basename(p)}" for p in res.media_files]
        img = [p for p in res.media_files if p.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
        if img:
            L += ["", f"![cover]({os.path.basename(img[0])})"]
    if res.needs_beatapi:
        L += ["", "## Needs BeatAPI fallback", ""] + [f"- {c}" for c in res.needs_beatapi]
    open(os.path.join(out, "content.md"), "w").write("\n".join(L) + "\n")
    json.dump(res.to_meta(), open(os.path.join(out, "meta.json"), "w"), ensure_ascii=False, indent=2, default=str)


def attempt(res, cap, chain):
    """Try free methods in order. chain = [(name, callable)]. Returns True on first success."""
    for name, fn in chain:
        try:
            fn()
            res.log(cap, name, True)
            return True
        except Exception as e:  # noqa
            res.log(cap, name, False, f"{type(e).__name__}: {e}")
    res.needs_beatapi.append(cap)
    return False


def fill_from_ytdlp(res, info):
    if info.get("_type") == "playlist" and info.get("entries"):
        first = next(iter(info["entries"]))
        info = {**first, **{k: v for k, v in info.items() if v and k in ("description", "title")}} if first else info
    res.title = res.title or info.get("title") or ""
    res.author = res.author or info.get("uploader") or info.get("channel") or ""
    res.published = res.published or ts(info.get("timestamp") or info.get("upload_date") or "")
    res.text = res.text or info.get("description") or ""
    for k in ("view_count", "like_count", "comment_count", "repost_count"):
        if info.get(k) is not None:
            v = info[k]
            # TikTok's web API serialises some counters as signed 32-bit ints,
            # so values > 2^31-1 wrap negative (e.g. -1894967296 == 2.4B).
            if isinstance(v, int) and -2**31 <= v < 0:
                v += 2**32
            if isinstance(v, int) and v >= 0:
                res.stats[k.replace("_count", "s")] = v
    th = info.get("thumbnail") or (sorted(info.get("thumbnails") or [{}], key=lambda t: t.get("width") or 0)[-1].get("url"))
    if th:
        res.images.append(th)
    if info.get("formats") or info.get("url"):
        res.videos.append(("ytdlp", info.get("webpage_url") or res.url))
    if info.get("comments"):
        res.comments = [{"author": c.get("author"), "text": c.get("text"), "likes": c.get("like_count"), "time": ts(c.get("timestamp"))} for c in info["comments"]]
    if info.get("duration"):
        res.extra["duration"] = info["duration"]

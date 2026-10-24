#!/usr/bin/env python3
"""Omni scraper: python scrape.py <url> [--out dir] [--with-media] [--with-comments] [--transcribe] [--fallback-beatapi]"""
import argparse, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core
from core import Result, download, write_outputs
from platforms import detect


def fetch_media(res, out, o):
    os.makedirs(out, exist_ok=True)
    ref = {"bilibili": "https://www.bilibili.com/", "douyin": None}.get(res.platform)
    ua = core.UA_ANDROID if res.platform == "douyin" else core.UA_DESKTOP
    for i, u in enumerate([u for u in res.images if u][: o.max_images]):
        ext = ".webp" if ".webp" in u.split("?")[0] else ".jpg"
        try:
            res.media_files.append(download(u, os.path.join(out, f"image_{i:02d}{ext}"), ua, ref)); res.log("image", f"download #{i}", True)
        except Exception as e:
            res.log("image", f"download #{i}", False, e)
    for v in res.videos[:1]:
        try:
            if res.platform == "bilibili":
                a = download(res.extra["dash_audio"], os.path.join(out, "audio.m4s"), ua, ref, max_bytes=o.max_mb * 2**20)
                vv = download(res.extra["dash_video"], os.path.join(out, "video.m4s"), ua, ref, max_bytes=o.max_mb * 2**20)
                if core.have_ffmpeg():
                    import subprocess
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vv, "-i", a, "-c", "copy", os.path.join(out, "video.mp4")])
                    res.media_files.append(os.path.join(out, "video.mp4")); os.remove(vv)
                    core.extract_audio(a, os.path.join(out, "audio.mp3")); os.remove(a); res.media_files.append(os.path.join(out, "audio.mp3"))
                else:
                    res.media_files += [a, vv]
            elif isinstance(v, tuple):
                res.media_files += core.ytdlp_download(v[1], out, max_mb=o.max_mb)
            elif res.platform == "wechat_channels":  # 执笔加：视频号分段下载（整段要会被限速），前 128KB 加密，下完解开
                from platforms import channels
                res.media_files.append(channels.decrypt_file(channels.download(v, os.path.join(out, "video.mp4"), o.max_mb * 2**20), res.extra["decode_key"]))
            else:
                res.media_files.append(download(v, os.path.join(out, "video.mp4"), ua, ref, max_bytes=o.max_mb * 2**20))
            res.log("video", "download", True)
        except Exception as e:
            res.log("video", "download", False, e); res.needs_beatapi.append("video")
    vids = [p for p in res.media_files if p.endswith((".mp4", ".webm", ".mkv"))]
    if vids and core.have_ffmpeg():
        try:
            if not any(p.endswith(".mp3") for p in res.media_files):
                res.media_files.append(core.extract_audio(vids[0], os.path.join(out, "audio.mp3")))
            if not any(p.lower().endswith((".jpg", ".webp", ".png")) for p in res.media_files):
                import subprocess
                fr = os.path.join(out, "frame.jpg"); subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", vids[0], "-frames:v", "1", fr])
                if os.path.exists(fr):
                    res.media_files.append(fr)
        except Exception as e:
            res.log("audio", "ffmpeg", False, e)
    if res.extra.get("subtitle_url"):
        try:
            res.media_files.append(download(res.extra["subtitle_url"], os.path.join(out, f"subtitle.{res.extra['subtitle_lang']}.vtt")))
        except Exception as e:
            res.log("subtitles", "download", False, e); res.needs_beatapi.append("subtitles")
    if o.transcribe:
        mp3 = [p for p in res.media_files if p.endswith(".mp3")]
        if mp3:
            try:
                t = core.transcribe(mp3[0], lang="zh" if res.platform in ("douyin", "wechat", "bilibili", "wechat_channels") else None, model=o.whisper_model)
                open(os.path.join(out, "transcript.txt"), "w").write(t); res.media_files.append(os.path.join(out, "transcript.txt")); res.log("transcript", "faster-whisper", True)
            except Exception as e:
                res.log("transcript", "faster-whisper", False, e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url"); ap.add_argument("--out")
    ap.add_argument("--with-media", action="store_true"); ap.add_argument("--with-comments", action="store_true")
    ap.add_argument("--transcribe", action="store_true", help="faster-whisper on extracted audio (needs --with-media)")
    ap.add_argument("--whisper-model", default="small"); ap.add_argument("--max-mb", type=int, default=None, help="下载上限；默认 60，加了 --transcribe 默认 2000（整条下，不然逐字稿会少后半段）"); ap.add_argument("--max-images", type=int, default=20)
    ap.add_argument("--search", metavar="KEYWORD", help="keyword search on the URL's platform (no free method; BeatAPI only)")
    ap.add_argument("--fallback-beatapi", action="store_true", help="use BeatAPI for failed capabilities (needs env BEATAPI_API_KEY)")
    ap.add_argument("--fallback-tikhub", action="store_true", help="执笔加：免费拿不到的项用 TikHub 补（要环境变量 TIKHUB_API_KEY，会花钱）")
    o = ap.parse_args()
    o.max_mb = o.max_mb or (2000 if o.transcribe else 60)  # 执笔加：转逐字稿要整条音频
    mod = detect(o.url)
    res = Result(mod.NAME, o.url.strip())
    out = o.out or os.path.join("output", f"{mod.NAME}_{time.strftime('%Y%m%d_%H%M%S')}")
    print(f"[{mod.NAME}] {o.url}")
    if o.search:
        os.environ["BEATAPI_KEYWORD"] = o.search
        res.title = f"search: {o.search}"; res.log("search", "free", False, "no free keyword search for this platform")
        res.needs_beatapi.append("search")
    try:
        if not o.search:
            mod.scrape(res, o)
    except Exception as e:
        res.log("content", "setup", False, e); res.needs_beatapi.append("content")
    if o.with_media and (res.images or res.videos):
        fetch_media(res, out, o)
    res.needs_beatapi = sorted(set(res.needs_beatapi))
    if res.needs_beatapi:
        import beatapi
        filled = []
        for cap in res.needs_beatapi:
            ref = beatapi.capability_name(res.platform, cap, res.url)
            if o.fallback_tikhub and os.environ.get("TIKHUB_API_KEY"):
                import tikhub
                try:
                    os.makedirs(out, exist_ok=True)
                    _, d = tikhub.run(res.platform, cap, res.url, os.path.join(out, f"tikhub_{cap}.json"), res.to_meta())
                    tikhub.merge(res, res.platform, cap, d); res.log(cap, f"TikHub {tikhub.path_of(ref)}", True); filled.append(cap)
                except Exception as e:
                    res.log(cap, "TikHub", False, e)
            elif o.fallback_beatapi and os.environ.get("BEATAPI_API_KEY"):
                try:
                    os.makedirs(out, exist_ok=True)
                    beatapi.run(res.platform, cap, res.url, os.path.join(out, f"beatapi_{cap}.json"), res.to_meta()); res.log(cap, f"BeatAPI {ref}", True)
                except Exception as e:
                    res.log(cap, f"BeatAPI {ref}", False, e)
            else:
                import tikhub
                print(tikhub.hint(res.platform, cap, res.url))
    if res.needs_beatapi:
        res.needs_beatapi = [c for c in res.needs_beatapi if c not in filled]  # 执笔加：TikHub 补上的不再算缺
    write_outputs(res, out)
    print(f"  -> {out}/content.md, meta.json ({len(res.media_files)} media files)")
    return 0 if not any(c in res.needs_beatapi for c in ("content", "profile", "list", "session")) else 2


if __name__ == "__main__":
    sys.exit(main())

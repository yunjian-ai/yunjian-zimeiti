"""视频号（执笔加，omniscraper 原版没有这个平台）。
免费：无头 Chrome 打开分享短链，页面自己调 finder-preview/api/feed/get_feed_info（直接请求会被拒），
      拿到作者、发布时间、四项互动数、封面、exportId。视频地址和文案网页上不给。
付费（--fallback-tikhub）：TikHub wechat_channels/v2/fetch_video_detail（$0.01/次）拿视频地址、解密钥匙、账号 username。
视频号的视频前 131072 字节加了密：和 ISAAC64(decode_key) 的密钥流异或，decrypt_file() 解开。"""
import json, os, re
from core import Fail, ts
NAME, MATCH = "wechat_channels", r"(weixin\.qq\.com/sph/|channels\.weixin\.qq\.com/)"
UA_IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
TIKHUB = os.environ.get("TIKHUB_BASE", "https://api.tikhub.io") + "/api/v1/wechat_channels/v2/"


def short_id(url):
    m = re.search(r"weixin\.qq\.com/sph/([A-Za-z0-9]+)|[?&]id=([A-Za-z0-9]+)", url)
    if not m:
        raise Fail("cannot find 视频号 short id in URL")
    return m.group(1) or m.group(2)


def feed_info_browser(sid):
    """无头 Chrome 开预览页，截下页面自己发的 get_feed_info 返回。要 playwright 和本机 Chrome（或 playwright 自带的 chromium）。"""
    from playwright.sync_api import sync_playwright
    got = {}
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            b = p.chromium.launch(headless=True)
        pg = b.new_context(user_agent=UA_IPHONE, viewport={"width": 390, "height": 844}).new_page()

        def on_resp(r):
            if "/api/feed/get_feed_info" in r.url:
                try:
                    got["d"] = r.json()
                except Exception:
                    pass
        pg.on("response", on_resp)
        pg.goto(f"https://channels.weixin.qq.com/finder-preview/pages/sph?id={sid}", wait_until="networkidle", timeout=45000)
        pg.wait_for_timeout(1500)
        b.close()
    d = got.get("d") or {}
    if d.get("errCode") not in (0, None) or not (d.get("data") or {}).get("feedInfo"):
        raise Fail(f"get_feed_info: {d.get('errMsg') or 'no response'}")
    return d["data"]


def tikhub_detail(sid, export_id=""):
    import requests
    key = os.environ.get("TIKHUB_API_KEY")
    if not key:
        raise Fail("TIKHUB_API_KEY not set")
    body = {"export_id": export_id, "raw": False} if export_id else {"share_url": f"https://weixin.qq.com/sph/{sid}", "raw": False}
    r = requests.post(TIKHUB + "fetch_video_detail", json=body, headers={"Authorization": f"Bearer {key}"}, timeout=40)
    d = r.json()
    if r.status_code >= 400 or d.get("code") != 200 or not d.get("data"):
        raise Fail(f"TikHub {r.status_code}: {str(d.get('message') or d.get('detail'))[:160]}")
    return d["data"]


def scrape(res, o):
    sid = short_id(res.url)
    res.url = f"https://weixin.qq.com/sph/{sid}"
    res.extra["short_id"] = sid

    def free_page():
        d = feed_info_browser(sid)
        f, a = d["feedInfo"], d.get("authorInfo") or {}
        res.author = a.get("nickname", ""); res.published = ts(f.get("createtime"))
        res.title = res.text = f.get("description", "")
        # 对着页面核过：fav 是「点赞 👍」，like 是「爱心 ❤」（和字段名字面意思相反）
        res.stats = {"likes": f.get("favCountFmt"), "hearts": f.get("likeCountFmt"),
                     "shares": f.get("forwardCountFmt"), "comments": f.get("commentCountFmt")}
        if f.get("coverUrl"):
            res.images.append(f["coverUrl"])
        res.images += [p.get("url") for p in f.get("picInfo") or [] if p.get("url")]
        res.extra["export_id"] = (d.get("sceneInfo") or {}).get("dynamicExportId", "")
    attempt_ok = _attempt(res, "content", [("finder-preview get_feed_info (headless Chrome)", free_page)])

    if not getattr(o, "fallback_tikhub", False):
        res.log("video", "free", False, "网页不给视频地址和文案；加 --fallback-tikhub 用 TikHub fetch_video_detail（$0.01）")
        res.needs_beatapi.append("video")
        return

    def paid_detail():
        x = tikhub_detail(sid, res.extra.get("export_id", ""))
        m = x.get("media") or {}
        res.author = res.author or x.get("nickname", ""); res.published = res.published or ts(x.get("create_time"))
        res.title = res.title or x.get("title") or x.get("description") or ""
        res.text = res.text or x.get("description") or ""
        if not attempt_ok:
            res.stats = {"likes": x.get("fav_count"), "hearts": x.get("like_count"),
                         "shares": x.get("forward_count"), "comments": x.get("comment_count")}
        if m.get("url"):
            res.videos.append(m["url"] + (m.get("url_token") or ""))
        if m.get("cover_url") and not res.images:
            res.images.append(m["cover_url"] + (m.get("cover_url_token") or ""))
        res.extra.update({"decode_key": m.get("decode_key"), "duration": m.get("duration"),
                          "username": x.get("username"), "object_id": str(x.get("id") or "")})
    if _attempt(res, "video", [("TikHub fetch_video_detail", paid_detail)]) and "content" in res.needs_beatapi:
        res.needs_beatapi.remove("content")


def _attempt(res, cap, chain):
    from core import attempt
    return attempt(res, cap, chain)


# ---- 解密：ISAAC64（Bob Jenkins 公开算法） ----
_M = (1 << 64) - 1


def _mix(a, b, c, d, e, f, g, h):
    a = (a - e) & _M; f ^= h >> 9; h = (h + a) & _M
    b = (b - f) & _M; g ^= (a << 9) & _M; a = (a + b) & _M
    c = (c - g) & _M; h ^= b >> 23; b = (b + c) & _M
    d = (d - h) & _M; a ^= (c << 15) & _M; c = (c + d) & _M
    e = (e - a) & _M; b ^= d >> 14; d = (d + e) & _M
    f = (f - b) & _M; c ^= (e << 20) & _M; e = (e + f) & _M
    g = (g - c) & _M; d ^= f >> 17; f = (f + g) & _M
    h = (h - d) & _M; e ^= (g << 14) & _M; g = (g + h) & _M
    return [a, b, c, d, e, f, g, h]


def keystream(seed, n=131072):
    mm, rsl = [0] * 256, [0] * 256
    rsl[0] = seed & _M
    x = [0x9e3779b97f4a7c13] * 8
    for _ in range(4):
        x = _mix(*x)
    for src in (rsl, mm):
        for i in range(0, 256, 8):
            x = _mix(*[(x[j] + src[i + j]) & _M for j in range(8)]); mm[i:i + 8] = x
    st = {"a": 0, "b": 0, "c": 0}

    def isaac():
        st["c"] = (st["c"] + 1) & _M; st["b"] = (st["b"] + st["c"]) & _M
        a, b = st["a"], st["b"]
        for i in range(256):
            v = mm[i]; s = i & 3
            a = (~(a ^ ((a << 21) & _M))) & _M if s == 0 else a ^ (a >> 5) if s == 1 else a ^ ((a << 12) & _M) if s == 2 else a ^ (a >> 33)
            a = (mm[(i + 128) & 255] + a) & _M
            y = (mm[(v >> 3) & 255] + a + b) & _M; mm[i] = y
            b = (mm[(y >> 11) & 255] + v) & _M; rsl[i] = b
        st["a"], st["b"] = a, b
    out = bytearray()
    while len(out) < n:
        isaac()
        for i in range(255, -1, -1):
            out += rsl[i].to_bytes(8, "big")
    return bytes(out[:n])


def download(url, path, max_bytes=None, step=2 * 2**20):
    """一次要整个文件时服务器按播放速度限流（约 24KB/秒）；分成 2MB 一段顺序要，约 400KB/秒以上。"""
    import requests
    if url.startswith("https://"):
        url = "http://" + url[8:]  # 实测 http 比 https 快
    pos, total = 0, None
    with open(path, "wb") as f:
        while total is None or pos < total:
            end = pos + step - 1
            if max_bytes:
                end = min(end, max_bytes - 1)
            r = requests.get(url, headers={"Range": f"bytes={pos}-{end}", "User-Agent": UA_IPHONE}, timeout=60)
            if r.status_code not in (200, 206) or not r.content:
                raise Fail(f"HTTP {r.status_code} at {pos}")
            f.write(r.content); pos += len(r.content)
            cr = r.headers.get("Content-Range", "")
            total = int(cr.rsplit("/", 1)[1]) if "/" in cr and cr.rsplit("/", 1)[1].isdigit() else pos
            if max_bytes:
                total = min(total, max_bytes)
    return path


def decrypt_file(path, decode_key, n=131072):
    with open(path, "r+b") as f:
        head = f.read(n)
        ks = keystream(int(decode_key), len(head))
        f.seek(0); f.write(bytes(a ^ b for a, b in zip(head, ks)))
    with open(path, "rb") as f:
        if f.read(12)[4:8] != b"ftyp":
            raise Fail("解密后不是 mp4（decode_key 不对或文件不完整）")
    return path

"""TikHub 付费兜底（执笔加的，国内能用支付宝付款）。
和 beatapi.py 用同一张接口对照表：BeatAPI 的接口名 data:douyin.app.v3.fetch_video_comments
就是 TikHub 的 /api/v1/douyin/app/v3/fetch_video_comments。密钥只从环境变量 TIKHUB_API_KEY 读，不打印。
先用 GET；返回 405 就改用 POST（JSON），公众号统计就要 POST。"""
import json
import os

import requests

import beatapi

BASE = os.environ.get("TIKHUB_BASE", "https://api.tikhub.io")


def path_of(ref):
    """data:douyin.app.v3.fetch_video_comments -> /api/v1/douyin/app/v3/fetch_video_comments"""
    return "/api/v1/" + ref.split(":", 1)[1].replace(".", "/")


def call(path, params, key=None, timeout=60):
    key = key or os.environ.get("TIKHUB_API_KEY")
    if not key:
        raise RuntimeError("TIKHUB_API_KEY not set")
    h = {"Authorization": f"Bearer {key}"}
    r = requests.get(BASE + path, params=params, headers=h, timeout=timeout)
    if r.status_code in (400, 404, 405, 422):  # 只收 POST 的接口对 GET 不一定回 405（公众号统计回 400，10-24 实测），一律再用 POST 试
        r = requests.post(BASE + path, json=params, headers={**h, "Content-Type": "application/json"}, timeout=timeout)
    try:
        d = r.json()
    except ValueError:
        d = {"raw": r.text[:500]}
    if r.status_code >= 400 or d.get("code") not in (200, None):
        raise RuntimeError(f"TikHub {r.status_code}: {str(d.get('message') or d.get('detail'))[:160]}")
    return d


def run(platform, cap, url, out_path, meta=None):
    cap = beatapi.route(platform, cap, url)
    ref = beatapi.capability_name(platform, cap, url)
    if not ref:
        raise RuntimeError(f"没有对应接口：{platform} {cap}")
    builder = beatapi.REFS.get((platform, cap), (None, lambda u, m: {"url": u}))[1]
    params = {k: v for k, v in (builder(url, meta or {}) or {}).items() if v not in (None, "")}
    d = call(path_of(ref), params)
    json.dump(d, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return ref, d


def merge(res, platform, cap, d):
    """把常用字段并进结果：评论进 res.comments，公众号阅读点赞进 res.stats。拿不到就不动。"""
    x = d.get("data") or {}
    if cap == "comments" and platform == "douyin":
        res.comments = [{"author": (c.get("user") or {}).get("nickname", ""), "text": c.get("text", ""),
                         "likes": c.get("digg_count")} for c in x.get("comments") or []]
        if x.get("total") is not None:
            res.stats.setdefault("comments", x.get("total"))
    elif cap == "stats" and platform == "wechat":
        for src, dst in (("read_num", "reads"), ("old_like_count", "old_likes"), ("like_count", "likes"),
                         ("share_count", "shares"), ("comment_count", "comments"), ("collect_count", "collects")):
            if x.get(src) is not None:
                res.stats[dst] = x[src]
        res.extra["stats_note"] = "公众号：old_likes 一般是点赞，likes 一般是在看（官方没写明，照字段原名记）"


def hint(platform, cap, url=None):
    ref = beatapi.capability_name(platform, cap, url)
    path = "/api/v1/wechat_channels/v2/fetch_video_detail（$0.01/次）" if platform == "wechat_channels" else (path_of(ref) if ref else '没有对应接口')
    return (f"  >> '{cap}' 免费方法拿不到 -> 可用 TikHub（支付宝可付）：{path}\n"
            f"     开通：user.tikhub.io 注册 → 控制台拿密钥 → 充值；密钥存本机环境变量 TIKHUB_API_KEY，不进聊天\n"
            f"     然后加 --fallback-tikhub 重跑（会花钱，先问主人）")

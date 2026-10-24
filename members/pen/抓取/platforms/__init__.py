import re
from . import channels, youtube, bilibili, x, wechat, douyin, xiaohongshu, tiktok, instagram, facebook, threads, linkedin, reddit, pinterest, telegram, medium, substack, bluesky, generic
ALL = [channels, youtube, bilibili, x, wechat, douyin, xiaohongshu, tiktok, instagram, facebook, threads, linkedin, reddit, pinterest, telegram, medium, substack, bluesky]


def detect(url):
    for m in ALL:
        if re.search(m.MATCH, url, re.I):
            return m
    return generic

"""丹青出图引擎：调 GPT Image 接口（文生图；带参考图的图生图／改图）。只用标准库。
密钥只从环境变量 PAINT_IMAGE_API_KEY 读，不打印、不写进任何文件；没设就退出码 3，改用 Bot 自带的出图。
可选：PAINT_IMAGE_BASE（默认 https://api.openai.com/v1，用兼容接口的中转站就换成它的地址）、PAINT_IMAGE_MODEL（默认 gpt-image-2）。
用法：python3 出图.py 文生图 "提示词" -o 输出.png [-s 1536x1536] [-q low|medium|high]
     python3 出图.py 图生图 "提示词" -r 参考1.png [-r 参考2.png …] -o 输出.png [同上]
     python3 出图.py 查尺寸 1536x2048        只查尺寸合不合规，不出图"""
import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
MAX_REFS = 8  # 官方上限 16；越多越稀，主角那几张最准


def check_size(size):
    """GPT Image 2 官方尺寸规则：两边都是 16 的倍数、最长边小于 3840、长短边比不超过 3:1、总像素 655,360～8,294,400。
    返回 (问题列表, 提醒列表)。"""
    if size == "auto":
        return [], []
    try:
        w, h = (int(x) for x in size.lower().split("x"))
    except ValueError:
        return [f"尺寸「{size}」要写成 宽x高，例 1536x2048"], []
    errs, warns = [], []
    if w % 16 or h % 16:
        errs.append(f"{w}x{h}：两边都要是 16 的倍数")
    if max(w, h) >= 3840:
        errs.append(f"{w}x{h}：最长边要小于 3840")
    if min(w, h) <= 0 or max(w, h) / min(w, h) > 3:
        errs.append(f"{w}x{h}：长短边比不能超过 3:1")
    if not 655360 <= w * h <= 8294400:
        errs.append(f"{w}x{h}：总像素要在 655,360～8,294,400 之间")
    if max(w, h) > 2560 and not errs:
        warns.append(f"{w}x{h}：超过 2560 官方标为实验性，可能不稳定；要高清可先出 2K 再放大")
    return errs, warns


def multipart(fields, files):
    b = uuid.uuid4().hex
    out = b""
    for k, v in fields.items():
        out += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for k, p in files:
        out += (f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{Path(p).name}\"\r\n"
                f"Content-Type: {mimetypes.guess_type(p)[0] or 'image/png'}\r\n\r\n").encode() + Path(p).read_bytes() + b"\r\n"
    return out + f"--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}"


def run(mode, prompt, out, refs=(), size="1536x1536", quality="medium"):
    key = os.environ.get("PAINT_IMAGE_API_KEY")
    if not key:
        print("NO_KEY 没设 PAINT_IMAGE_API_KEY：这次改用 Bot 自带的出图，提示词照用")
        return 3
    errs, warns = check_size(size)
    for w in warns:
        print("⚠️", w)
    if errs:
        print("❌", "；".join(errs))
        return 2
    if mode == "图生图" and not refs:
        print("❌ 图生图至少要一张参考图（-r）")
        return 2
    if len(refs) > MAX_REFS:
        print(f"❌ 参考图 {len(refs)} 张太多，最多 {MAX_REFS} 张：主角放第一张，其余挑最要紧的")
        return 2
    base = os.environ.get("PAINT_IMAGE_BASE", "https://api.openai.com/v1").rstrip("/") + "/images/"
    fields = {"model": os.environ.get("PAINT_IMAGE_MODEL", "gpt-image-2"), "prompt": prompt, "size": size, "quality": quality, "n": 1}
    if mode == "文生图":
        data, ctype, url = json.dumps(fields).encode(), "application/json", base + "generations"
    else:
        data, ctype = multipart(fields, [("image[]", r) for r in refs])
        url = base + "edits"
    t = time.time()
    req = urllib.request.Request(url, data=data, headers={"Authorization": "Bearer " + key, "Content-Type": ctype, "User-Agent": UA})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=400))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:300].replace(key, "***")
        print(f"❌ 接口返回 {e.code}：{msg}")
        return 1
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"❌ 连不上出图接口：{e}")
        return 1
    item = d["data"][0]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    if item.get("b64_json"):
        Path(out).write_bytes(base64.b64decode(item["b64_json"]))
    else:
        with urllib.request.urlopen(urllib.request.Request(item["url"], headers={"User-Agent": UA}), timeout=180) as r:
            Path(out).write_bytes(r.read())
    print(f"OK {out}｜{round(time.time() - t)} 秒｜{size}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["文生图", "图生图", "查尺寸"])
    ap.add_argument("prompt", help="提示词；查尺寸时写尺寸")
    ap.add_argument("-o", "--out")
    ap.add_argument("-r", "--ref", action="append", default=[])
    ap.add_argument("-s", "--size", default="1536x1536")
    ap.add_argument("-q", "--quality", default="medium", choices=["low", "medium", "high"])
    a = ap.parse_args(argv)
    if a.mode == "查尺寸":
        errs, warns = check_size(a.prompt)
        for m in errs:
            print("❌", m)
        for m in warns:
            print("⚠️", m)
        if not errs:
            print("✅ 尺寸可以")
        return 1 if errs else 0
    if not a.out:
        ap.error("出图要写 -o 输出文件")
    return run(a.mode, a.prompt, a.out, a.ref, a.size, a.quality)


if __name__ == "__main__":
    sys.exit(main())

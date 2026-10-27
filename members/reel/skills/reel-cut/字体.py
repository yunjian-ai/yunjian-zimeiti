"""大字用的粗体字：英文 Anton、中文思源黑体 Heavy（都是 SIL OFL 1.1 开源许可，可商用）。只用标准库。
找字体的顺序：项目里的 字体/（主人自己的字体放这，有就优先用）→ 已下好的 ~/.yunjian/reel/字体/ → 联网下载 → 系统自带的粗体。
用法：python3 字体.py 找 [中文|英文] [--项目 <项目目录>]     打印要用的字体路径
      python3 字体.py 下                                   两款都下好（中文约 9MB，英文约 0.2MB）
别的脚本：from 字体 import 挑; 挑("NIGHT") / 挑("夜跑", 项目目录)"""
import argparse
import functools
import os
import sys
import time
import urllib.request
from pathlib import Path

存 = Path(os.environ.get("REEL_HOME", Path.home() / ".yunjian" / "reel")) / "字体"
GH = "https://github.com"
开源 = {
    "英文": ("Anton-Regular.ttf", f"{GH}/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf"),
    "中文": ("SourceHanSansCN-Heavy.otf", f"{GH}/adobe-fonts/source-han-sans/raw/release/SubsetOTF/CN/SourceHanSansCN-Heavy.otf"),
}
系统 = {
    "中文": ["/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
           "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
           "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"],
    "英文": ["/System/Library/Fonts/Supplemental/Impact.ttf", "/System/Library/Fonts/Helvetica.ttc",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
}


def 是中文(text):
    return any(ord(c) > 0x2E80 for c in text or "")


def 下(种):
    名, 网址 = 开源[种]
    f = 存 / 名
    if f.exists() and f.stat().st_size > 10000:
        return f
    存.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(f".{os.getpid()}.part")  # 几个进程同时下也不互相覆盖
    限 = time.time() + 180  # 网慢时最多等 3 分钟，下不完先用系统字体，下回再下
    with urllib.request.urlopen(网址, timeout=30) as r, open(tmp, "wb") as out:
        while True:
            块 = r.read(1 << 16)
            if not 块:
                break
            out.write(块)
            if time.time() > 限:
                raise OSError("下载超过 3 分钟（网慢）")
    tmp.rename(f)
    return f


@functools.lru_cache(maxsize=None)  # 一次运行里只找（下载）一次，下不下来也不反复等
def 找(种="中文", 项目=None, 联网=True):
    if 项目 and (Path(项目) / "字体").is_dir():
        自己的 = sorted(p for p in (Path(项目) / "字体").iterdir() if p.suffix.lower() in (".ttf", ".otf", ".ttc"))
        if 自己的:
            return str(自己的[0])
    f = 存 / 开源[种][0]
    if f.exists():
        return str(f)
    if 联网:
        try:
            return str(下(种))
        except OSError as e:
            print(f"（字体没下下来：{e}；先用系统自带的）", file=sys.stderr)
    for p in 系统[种] + (系统["中文"] if 种 == "英文" else []):
        if os.path.exists(p):
            return p
    sys.exit("NO_FONT：没找到能用的粗体字。把一个 .ttf/.otf 放进项目的 字体/ 文件夹再重跑")


def 挑(text, 项目=None):
    """有中日韩字就用中文粗体，否则用英文粗体。"""
    return 找("中文" if 是中文(text) else "英文", 项目)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="找大字用的粗体字")
    ap.add_argument("做", choices=["找", "下"])
    ap.add_argument("种", nargs="?", default="中文", choices=["中文", "英文"])
    ap.add_argument("--项目")
    g = ap.parse_args()
    if g.做 == "下":
        for k in 开源:
            print(k, 下(k))
    else:
        print(找(g.种, g.项目))

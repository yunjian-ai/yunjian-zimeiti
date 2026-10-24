"""本地的视频、录音直接转逐字稿（免费，本机跑，不上传）：主人手机里存的口播、录音、下载下来的视频都能用。
用法：.venv/bin/python 转文字.py <文件> [<文件> …] [--语言 zh] [--模型 small] [--out 目录]
  每个文件写出同名的 <名字>.逐字稿.txt（放 --out，默认放在文件旁边），也打印出来。
  中文固定转简体；口播用 small（准）、着急用 tiny（快但错字多）；第一次用会下载语音模型。
  要先装好 faster-whisper 和 ffmpeg（装法见 使用说明.md 第一节）；没装就会告诉你怎么装，或改用剪映「识别字幕」、飞书妙记。"""
import argparse
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def ensure_ffmpeg():
    """PATH 里没有 ffmpeg 时，用 imageio-ffmpeg 自带的那份（装依赖时一起装了）。"""
    if shutil.which("ffmpeg"):
        return True
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        link = Path(exe).with_name("ffmpeg")
        if not link.exists():
            os.symlink(exe, link)
        os.environ["PATH"] = str(link.parent) + os.pathsep + os.environ.get("PATH", "")
        return True
    except Exception:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--语言", default="zh", help="zh 中文（默认，转简体）；外文写 en 等；写 auto 让它自己认")
    ap.add_argument("--模型", default="small")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        sys.exit("还没装语音识别：在 抓取 文件夹里运行 .venv/bin/pip install faster-whisper imageio-ffmpeg numpy opencc-python-reimplemented；"
                 "装不上就用剪映「识别字幕」或飞书妙记转好，把文字贴给执笔")
    if not ensure_ffmpeg():
        sys.exit("没找到 ffmpeg：运行 .venv/bin/pip install imageio-ffmpeg 再试")
    from core import transcribe
    for f in a.files:
        p = Path(f).expanduser()
        if not p.exists():
            print(f"找不到文件：{p}")
            continue
        text = transcribe(str(p), lang=None if a.语言 == "auto" else a.语言, model=a.模型)
        out = Path(a.out).expanduser() if a.out else p.parent
        out.mkdir(parents=True, exist_ok=True)
        dest = out / f"{p.stem}.逐字稿.txt"
        dest.write_text(text + "\n", encoding="utf-8")
        print(f"== {p.name} → {dest}\n{text}\n")


if __name__ == "__main__":
    main()

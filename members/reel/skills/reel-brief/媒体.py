"""掠影各脚本共用：找 ffmpeg、跑 ffmpeg、读视频信息、把音频解码成数组。别的技能的脚本这样引：
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reel-brief")); import 媒体
ffmpeg 找法：环境变量 REEL_FFMPEG → 系统 ffmpeg → imageio-ffmpeg 自带的（pip install imageio-ffmpeg，约 21MB）。
不用 ffprobe（imageio-ffmpeg 不带它），视频信息从 `ffmpeg -i` 的输出里读。"""
import functools
import os
import re
import shutil
import subprocess
import sys


def _候选():
    if os.environ.get("REEL_FFMPEG"):
        yield os.environ["REEL_FFMPEG"]
    if shutil.which("ffmpeg"):
        yield shutil.which("ffmpeg")
    try:
        import imageio_ffmpeg
        yield imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    import glob  # 别的 Python 装过 imageio-ffmpeg 也认（带着自己 Python 的软件里跑时常见）
    for pat in ("~/Library/Python/*/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-*",
                "~/.local/lib/python*/site-packages/imageio_ffmpeg/binaries/ffmpeg-*", "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        yield from (p for p in glob.glob(os.path.expanduser(pat)) if os.access(p, os.X_OK))


@functools.lru_cache(maxsize=None)
def ffmpeg():
    """有的 ffmpeg 没带写字功能（drawtext，要 libfreetype），出不了大字：挑第一个带 drawtext 的。"""
    见过 = []
    for p in _候选():
        r = subprocess.run([p, "-hide_banner", "-filters"], capture_output=True, text=True, errors="replace")
        if " drawtext " in r.stdout:
            return p
        见过.append(p)
    if 见过:
        sys.exit(f"NO_FFMPEG：找到的 ffmpeg（{见过[0]}）没带写字功能（drawtext）。先问主人一句，同意后 pip install imageio-ffmpeg（约 21MB，自带完整 ffmpeg），再重跑")
    sys.exit("NO_FFMPEG：没找到 ffmpeg。先问主人一句，同意后运行 pip install imageio-ffmpeg（约 21MB，免费），再重跑")


def 跑(*参数, 安静=True):
    """跑一条 ffmpeg，出错就把最后几行报出来退出。返回 stderr 文本（滤镜的统计结果在这里）。"""
    cmd = [ffmpeg(), "-hide_banner", "-nostdin", "-y", *map(str, 参数)]
    if 安静:
        cmd[1:1] = ["-loglevel", "error"]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode:
        sys.exit("FFMPEG_FAILED：" + "\n".join(r.stderr.strip().splitlines()[-6:]))
    return r.stderr


def 分析(*参数):
    """跑一条只看不写的 ffmpeg（ebur128、blackdetect 这类），返回完整 stderr。"""
    r = subprocess.run([ffmpeg(), "-hide_banner", "-nostdin", *map(str, 参数)], capture_output=True, text=True, errors="replace")
    return r.stderr


def 信息(path):
    """{时长, 宽, 高, 帧率, 视频编码, 像素格式, 色彩, 码率kbps, 有音轨, 采样率}；不是媒体文件就退出。"""
    err = 分析("-i", path)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    if not m:
        sys.exit(f"NOT_MEDIA：{path} 读不出来（不是音视频文件，或者文件坏了）")
    d = {"时长": int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]), "有音轨": " Audio: " in err}
    b = re.search(r"bitrate: (\d+) kb/s", err)
    d["码率kbps"] = int(b[1]) if b else None
    v = re.search(r"Stream #\S+.*?: Video: (\w+).*", err)
    if v:
        line = v[0]
        d["视频编码"] = v[1]
        wh = re.search(r", (\d{2,5})x(\d{2,5})", line)
        d["宽"], d["高"] = (int(wh[1]), int(wh[2])) if wh else (None, None)
        fps = re.search(r"([\d.]+) fps", line) or re.search(r"([\d.]+) tbr", line)
        d["帧率"] = float(fps[1]) if fps else None
        pf = re.search(r"Video: \w+[^,]*, (\w+)(\(([^)]*)\))?", line)
        d["像素格式"] = pf[1] if pf else None
        d["色彩"] = pf[3] if pf and pf[3] else ""
    a = re.search(r"Audio: \w+.*?, (\d+) Hz, ([^,]+)", err)
    d["采样率"] = int(a[1]) if a else None
    声 = a[2].strip() if a else ""
    d["声道"] = {"mono": 1, "stereo": 2}.get(声) or (int(re.match(r"(\d+)", 声)[1]) if re.match(r"\d+", 声) else (6 if "5.1" in 声 else None))
    return d


def 解码音频(path, sr=22050, 起=None, 长=None):
    """音频 → 单声道 float32 数组（要 numpy）。"""
    import numpy as np
    pre = (["-ss", f"{起:.3f}"] if 起 else []) + (["-t", f"{长:.3f}"] if 长 else [])
    r = subprocess.run([ffmpeg(), "-v", "error", "-nostdin", *pre, "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True)
    if r.returncode or not r.stdout:
        sys.exit(f"NOT_MEDIA：{path} 解不出声音")
    return np.frombuffer(r.stdout, dtype=np.float32)


def 写音频(path, y, sr):
    """float 数组 → wav（或按扩展名转 mp3）。"""
    import numpy as np
    pcm = (np.clip(y, -1, 1) * 32767).astype("<i2").tobytes()
    p = subprocess.run([ffmpeg(), "-v", "error", "-nostdin", "-y", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "-",
                        *(["-b:a", "192k"] if str(path).endswith(".mp3") else []), str(path)], input=pcm, capture_output=True)
    if p.returncode:
        sys.exit("FFMPEG_FAILED：" + p.stderr.decode(errors="replace")[-400:])


def 字体(中文=True):
    """给标签用的随便一款字体（大字用 reel-cut/字体.py 挑）：系统里有啥用啥。"""
    for f in (["/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
               "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"] if 中文 else []) + \
             ["/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(f):
            return f
    for root in (os.path.expanduser("~/.yunjian/reel/字体"), "/usr/share/fonts", "/Library/Fonts"):
        for dp, _, fs in os.walk(root):
            for f in fs:
                if f.lower().endswith((".ttf", ".otf", ".ttc")):
                    return os.path.join(dp, f)
    return None


def 滤镜路径(p):
    """放进 ffmpeg 滤镜参数里的路径：用单引号包起来（空格、冒号、逗号都安全），路径里本身的单引号转义。"""
    return "'" + str(p).replace("\\", "/").replace("'", "'\\''") + "'"

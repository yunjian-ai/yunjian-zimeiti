"""合成掠影自带的 3 首免版权曲（程序一个音一个音合成，云间工作室出品，CC0 公共领域，可商用、不用署名）。
用法：python3 做曲.py [输出目录]      要 numpy 和 ffmpeg（找法同 reel-brief/媒体.py）
三首都是：前 2 小节只有和弦垫（开场大字用），第 3 小节鼓和贝斯一起进来（大落点），结尾 1 小节收。"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 44100
曲们 = [  # 文件名, 速度, 小节数, 每小节根音（MIDI）, 鼓型
    ("夜行-128", 128, 16, [45, 41, 48, 43], "街头"),
    ("晴天-112", 112, 14, [48, 43, 45, 41], "轻快"),
    ("慢灯-86", 86, 11, [50, 46, 43, 45], "慢"),
]


def 频(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def 包络(n, 起=0.004, 衰=0.25):
    t = np.arange(n) / SR
    return np.minimum(1, t / 起) * np.exp(-t / 衰)


def 底鼓(n):
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 35)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * 包络(n, 0.002, 0.22)


def 拍手(n, rng):
    x = rng.standard_normal(n)
    e = sum(包络(n, 0.001, 0.012) * (np.arange(n) >= int(k * 0.011 * SR)) for k in range(3))
    return x * (e + 包络(n, 0.001, 0.12) * 0.6) * 0.5


def 镲(n, rng):
    x = np.diff(np.concatenate([[0], rng.standard_normal(n)]))
    return x * 包络(n, 0.001, 0.03) * 0.3


def 做(名, bpm, 小节数, 根们, 型, 出):
    rng = np.random.default_rng(sum(map(ord, 名)))
    拍 = 60 / bpm
    格 = 拍 / 4
    总 = int(SR * 小节数 * 4 * 拍) + SR
    混 = np.zeros(总)

    def 放(sig, t, g):
        i = int(t * SR)
        j = min(总, i + len(sig))
        混[i:j] += sig[: j - i] * g

    for b in range(小节数):
        根 = 根们[b % len(根们)]
        前奏, 尾 = b < 2, b == 小节数 - 1
        for s in range(16):
            t = (b * 16 + s) * 格
            if 前奏 or 尾:
                continue
            if 型 == "街头":
                if s in (0, 6, 10):
                    放(底鼓(int(SR * 0.4)), t, 0.95)
                if s in (4, 12):
                    放(拍手(int(SR * 0.25), rng), t, 0.55)
                if s % 2 == 0 or s in (13, 15):
                    放(镲(int(SR * 0.05), rng), t, 0.55)
            elif 型 == "轻快":
                if s % 4 == 0:
                    放(底鼓(int(SR * 0.35)), t, 0.9)
                if s in (4, 12):
                    放(拍手(int(SR * 0.2), rng), t, 0.4)
                if s % 4 == 2:
                    放(镲(int(SR * 0.08), rng), t, 0.8)
            else:
                if s in (0, 9):
                    放(底鼓(int(SR * 0.4)), t, 0.8)
                if s in (4, 12):
                    放(拍手(int(SR * 0.25), rng), t, 0.3)
                if s % 2 == 0:
                    放(镲(int(SR * 0.04), rng), t, 0.3)
            if s in (0, 3, 8, 11):  # 贝斯
                n = int(SR * 格 * 2.5)
                tt = np.arange(n) / SR
                放(np.tanh(1.8 * np.sin(2 * np.pi * 频(根 - 12) * tt)) * 包络(n, 0.005, 0.25), t, 0.32)
            if 型 != "慢" and s in (2, 6, 10, 14):  # 小琶音
                n = int(SR * 格 * 1.5)
                tt = np.arange(n) / SR
                放(np.sin(2 * np.pi * 频(根 + 12 + (0, 3, 7, 10)[s // 4]) * tt) * 包络(n, 0.003, 0.12), t, 0.08)
        n = int(SR * 4 * 拍)  # 和弦垫：每小节一个小三和弦
        tt = np.arange(n) / SR
        垫 = sum(np.sin(2 * np.pi * 频(根 + k) * tt) + 0.25 * np.sin(2 * np.pi * 频(根 + k) * 2.003 * tt) for k in (12, 15, 19))
        放(垫 * np.minimum(1, tt / 0.25) * np.minimum(1, (n / SR - tt) / 0.25), b * 4 * 拍, 0.05 if not 前奏 else 0.09)
    混 = 混[: int(SR * 小节数 * 4 * 拍)]
    淡 = int(SR * 1.0)
    混[-淡:] *= np.linspace(1, 0, 淡)
    混 = 混 / (np.abs(混).max() + 1e-9) * 0.9
    ff = os.environ.get("REEL_FFMPEG") or shutil.which("ffmpeg")
    if not ff:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    mp3 = Path(出) / f"{名}.mp3"
    subprocess.run([ff, "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-", "-ac", "2", "-b:a", "128k",
                    "-metadata", f"title={名}", "-metadata", "artist=云间工作室", "-metadata", "copyright=CC0 1.0",
                    str(mp3)], input=(混 * 32767).astype("<i2").tobytes(), check=True)
    print(mp3, f"{bpm} 拍／分", f"{小节数 * 4 * 拍:.1f} 秒")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent)
    Path(out).mkdir(parents=True, exist_ok=True)
    for x in 曲们:
        做(*x, out)

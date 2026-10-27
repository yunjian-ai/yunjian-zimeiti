"""掠影项目进度：看项目文件夹里有什么、哪几个关口主人点过头，说清到哪一步、下一步找哪个技能（换了对话也能接着做）。只用标准库。
用法：python3 进度.py 看 <项目目录>                 三行：在哪、下一步、要守的主人纠正（再列 8 步）
      python3 进度.py 记 <项目目录> "原话"          主人拍板的话原样记进 进度/原话.md（带北京时间）
      python3 进度.py 纠正 <项目目录> "原话"        主人纠正的话原样记下，以后每次「看」都报出来
      python3 进度.py 关口 <项目目录> <关口> 过|撤   需求／锁定／分镜／前三张／粗剪／成片
      python3 进度.py 后台 <项目目录> <名字> -- <命令…>   超过 2 分钟的活放后台，日志在 进度/后台/
      python3 进度.py 后台看 <项目目录>              后台任务还在不在跑"""
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

BJ = datetime.timezone(datetime.timedelta(hours=8))
关口们 = ("需求", "锁定", "分镜", "前三张", "粗剪", "成片")


def 现在():
    return datetime.datetime.now(BJ).strftime("%Y-%m-%d %H:%M 北京时间")


def 有(d, *式):
    return any(any(d.glob(g)) for g in 式)


def 读关口(d):
    f = d / "进度" / "关口.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def 静帧数(d):
    """(已有几张, 一共要几张)：要几张＝镜头表里素材不是「—」的刀数（没有镜头表就算 0）。"""
    有张 = len({p.stem for p in (d / "静帧").glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg")}) if (d / "静帧").is_dir() else 0
    要 = 0
    if (d / "分镜.md").exists():
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reel-board"))
        import 镜头表
        要 = sum(1 for s in 镜头表.读镜头表(d / "分镜.md") if s.get("素材", "").strip() not in ("", "—", "-", "无"))
    return 有张, 要


def 八步(d):
    g = 读关口(d)
    有张, 要张 = 静帧数(d)
    静帧下一步 = (f"reel-still：前三张已过，接着出第 {有张 + 1} 张（静帧 {有张}/{要张}），一张一张出、一张一张核"
               if "前三张" in g else "reel-still：先出 3 张给主人看，过了跑 `关口 . 前三张 过` 再批量")
    return [  # （名字, 做完没有, 下一步）
        ("1 需求和额度", "需求" in g, "reel-brief：一条消息问完、报额度，主人回了跑 `关口 . 需求 过`"),
        ("2 锁人锁货锁场景（关口 1）", "锁定" in g, "reel-lock：三视图、脸、锁定清单、4 张试镜、场景两视角，主人确认跑 `关口 . 锁定 过`"),
        ("3 歌和拍子", 有(d, "音乐/拍子.json"), "reel-music：剪歌、扒拍子、复核，写 音乐/拍子.json"),
        ("4 分镜（关口 2）", 有(d, "分镜.md") and "分镜" in g, "reel-board：切点、镜头表、体检，主人点头跑 `关口 . 分镜 过`"),
        ("5 静帧（先 3 张）", 有张 > 0 and "前三张" in g and 有张 >= 要张, 静帧下一步),
        ("6 视频和可用窗口", 有(d, "视频/可用窗口.md"), "reel-motion：报额度，一条一条出，抽帧看，写 视频/可用窗口.md"),
        ("7 粗剪", "粗剪" in g, "reel-cut：先出几帧和联系表，主人点头跑 `关口 . 粗剪 过`"),
        ("8 成片和质检（关口 3）", "成片" in g, "reel-check：机器检查＋坑清单＋自评，主人确认跑 `关口 . 成片 过`"),
    ]


def 读纠正(d):
    f = d / "进度" / "纠正.md"
    return [l[2:].split("：", 1)[-1] for l in f.read_text(encoding="utf-8").splitlines() if l.startswith("- ")] if f.exists() else []


def 读后台(d):
    f = d / "进度" / "后台" / "清单.jsonl"
    out = []
    for line in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        r = json.loads(line)
        try:
            os.kill(r["pid"], 0)
            r["在跑"] = True
        except OSError:
            r["在跑"] = False
        out.append(r)
    return out


def 看(d):
    步 = 八步(d)
    没做 = [s for s in 步 if not s[1]]
    在哪 = 没做[0][0] if 没做 else "全部做完"
    print(f"在哪：{在哪}（{len(步) - len(没做)}/{len(步)}）")
    print("下一步：" + (没做[0][2] if 没做 else "成片交给主人，发布由主人自己点"))
    纠 = 读纠正(d)
    print("要守的纠正：" + ("；".join(f"「{x}」" for x in 纠) if 纠 else "无"))
    print()
    for name, done, _ in 步:
        print(("✅ " if done else "⬜ ") + name)
    跑 = [r["名字"] for r in 读后台(d) if r["在跑"]]
    if 跑:
        print("后台还在跑：" + "，".join(跑) + "（告诉主人好了说「继续」）")


def 追加(f, 行):
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a", encoding="utf-8") as h:
        h.write(行 + "\n")


def main(a):
    if len(a) < 2:
        sys.exit(__doc__)
    cmd, d = a[0], Path(a[1])
    d.mkdir(parents=True, exist_ok=True)
    if cmd == "看":
        看(d)
    elif cmd in ("记", "纠正") and len(a) >= 3:
        追加(d / "进度" / ("原话.md" if cmd == "记" else "纠正.md"), f"- {现在()}：{a[2]}")
        print("已记下")
    elif cmd == "关口" and len(a) >= 4 and a[2] in 关口们 and a[3] in ("过", "撤"):
        g = 读关口(d)
        if a[3] == "过":
            g[a[2]] = 现在()
        else:
            g.pop(a[2], None)
        f = d / "进度" / "关口.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
        print("关口：" + ("、".join(g) or "都没过"))
    elif cmd == "后台" and "--" in a and len(a) >= 5:
        名, argv = a[2], a[a.index("--") + 1:]
        日志 = d / "进度" / "后台" / f"{名}.log"
        日志.parent.mkdir(parents=True, exist_ok=True)
        p = subprocess.Popen(argv, stdout=open(日志, "w"), stderr=subprocess.STDOUT, start_new_session=True, cwd=d)
        追加(d / "进度" / "后台" / "清单.jsonl", json.dumps({"名字": 名, "pid": p.pid, "日志": str(日志), "开始": 现在(), "命令": argv}, ensure_ascii=False))
        print(f"后台开始 {名}（pid {p.pid}），日志 {日志}。告诉主人大概要等几分钟，好了说「继续」。")
    elif cmd == "后台看":
        for r in 读后台(d):
            print(("在跑 " if r["在跑"] else "跑完了 ") + f"{r['名字']} {r['开始']} {r['日志']}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])

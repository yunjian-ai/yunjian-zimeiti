"""掠影项目的机械检查：项目文件夹里每份文件格式对不对、该填的填没填。只用标准库。
用法：python3 check_reel.py <项目目录>
查：需求.md 六项 ｜ 锁定/ 三份清单（取最新一版，旧版留着）｜ 音乐/拍子.json ｜ 分镜.md（关口点过头的不许还有【待填】）｜
    视频/可用窗口.md（不许还有「待看」、处理要写）。有 ❌ 退出码 1。内容好不好由技能里的核对清单判，这里只管格式。"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "reel-board"))
import 镜头表  # noqa: E402

需求项 = ["类型", "平台", "画幅", "时长", "风格", "预算"]
清单项 = {
    "人物清单": ["发型", "脸", "上装", "下装", "鞋", "必须出现", "禁止"],
    "货品清单": ["品名", "颜色", "图案", "版型", "必须出现", "禁止"],
    "场景清单": ["场景", "灯光", "背景", "地面", "禁止"],
}


def 字段(text, 名):
    m = re.search(rf"^[-*]\s*{名}[^：:\n]*[：:]\s*(.*)$", text, re.M)
    return m[1].strip() if m else None


def 最新版(d, 名):
    vs = sorted(d.glob(f"{名}-v*.md"), key=lambda p: int(re.sub(r"\D", "", p.stem.split("-v")[-1]) or 0))
    return vs[-1] if vs else (d / f"{名}.md" if (d / f"{名}.md").exists() else None)


def 查(P):
    好, 坏 = [], []
    关 = json.loads((P / "进度" / "关口.json").read_text(encoding="utf-8")) if (P / "进度" / "关口.json").exists() else {}
    f = P / "需求.md"
    if f.exists():
        t = f.read_text(encoding="utf-8")
        缺 = [k for k in 需求项 if not 字段(t, k)]
        (坏 if 缺 else 好).append(f"需求.md{'缺：' + '、'.join(缺) if 缺 else ' 六项齐'}")
    elif "需求" in 关:
        坏.append("需求关口点过了，但没有 需求.md")
    d = P / "锁定"
    for 名, 项 in 清单项.items():
        f = 最新版(d, 名) if d.is_dir() else None
        if not f:
            if "锁定" in 关 and 名 != "货品清单":
                坏.append(f"锁定关口点过了，但没有 锁定/{名}-v1.md")
            continue
        t = f.read_text(encoding="utf-8")
        缺 = [k for k in 项 if not 字段(t, k)]
        (坏 if 缺 else 好).append(f"{f.name}{'缺：' + '、'.join(缺) if 缺 else ' 齐'}")
    f = P / "音乐" / "拍子.json"
    if f.exists():
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            缺 = [k for k in ("bpm", "小节秒", "拍", "重拍", "大落点", "时长") if k not in j]
            速度 = j.get("bpm")
            (坏 if 缺 else 好).append(f"拍子.json{'缺：' + '、'.join(缺) if 缺 else f' {速度} 拍／分'}")
        except ValueError:
            坏.append("拍子.json 不是合法 JSON，重跑 节拍.py")
    f = P / "分镜.md"
    if f.exists():
        t = f.read_text(encoding="utf-8")
        表 = 镜头表.读镜头表(f)
        if not 表:
            坏.append("分镜.md 里没有镜头表（要有「#」和「进–出（秒）」两列）")
        elif "分镜" in 关 and "【待填】" in t:
            坏.append("分镜主人点过头了，表里还有【待填】")
        else:
            好.append(f"分镜.md {len(表)} 刀" + ("（还有【待填】，填完给主人看）" if "【待填】" in t else ""))
    f = P / "视频" / "可用窗口.md"
    if f.exists():
        行 = 镜头表.读表(f, ("号", "窗口"))
        待 = [r["号"] for r in 行 if "待看" in r.get("窗口", "") or not 镜头表.区间(r.get("窗口", ""))]
        没处理 = [r["号"] for r in 行 if not r.get("处理", "").strip()]
        if 待:
            坏.append(f"可用窗口表第 {'、'.join(待)} 条还没看（窗口写真实能用的一截）")
        if 没处理:
            坏.append(f"可用窗口表第 {'、'.join(没处理)} 条「处理」没写（留／缩短这一刀／重出／退回静帧）")
        镜 = 镜头表.读镜头表(P / "分镜.md") if (P / "分镜.md").exists() else []
        有窗 = {re.sub(r"\D", "", r.get("号", "")).lstrip("0") for r in 行}
        缺窗 = [s["号"] for s in 镜 if s.get("素材", "").strip().startswith("视频/") and s["号"].lstrip("0") not in 有窗]
        if 缺窗:
            坏.append(f"镜头表第 {'、'.join(缺窗)} 刀用视频，可用窗口表里还没有这几刀")
        if not 待 and not 没处理 and not 缺窗:
            好.append(f"可用窗口表 {len(行)} 条齐")
    return 好, 坏


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    好, 坏 = 查(Path(sys.argv[1]))
    for x in 好:
        print("✅ " + x)
    for x in 坏:
        print("❌ " + x)
    print("PASS" if not 坏 else f"共 {len(坏)} 处要改")
    sys.exit(1 if 坏 else 0)

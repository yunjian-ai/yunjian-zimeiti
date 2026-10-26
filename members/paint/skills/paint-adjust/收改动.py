"""主人在调图网页里点「把改动发给丹青」复制的那段，粘回来后照它改图层。只用标准库。
用法：python3 收改动.py <图层.json> <改动.json 或 -（从标准输入读）> -o <新图层.json>
做三件事：①文字、图案、色块图层照「新位置」「文字」改；②圈选挪动的图里东西列出来（要从底图裁出来当新图层）；
③「待补的空」列出来，交给出图模型把那几块补自然（改图写法：只补这几块，其余一律不动）。
改完用 paint-make 的 叠图.py 按交付像素重新叠，出高清版。"""
import json
import sys
from pathlib import Path


def apply(layers, change):
    by_id = {L.get("id"): L for L in layers}
    done, cuts, missing = [], [], []
    for c in change.get("改动", []):
        lid, now = c.get("图层"), c.get("新位置") or {}
        if c.get("类型") == "圈选的图里东西":
            cuts.append({"原位置": c.get("原位置"), "新位置": now})
            continue
        L = by_id.get(lid)
        if L is None:
            missing.append(lid)
            continue
        for k in ("x", "y", "w", "h"):
            if isinstance(now.get(k), (int, float)):
                L[k] = round(min(max(float(now[k]), -1.0), 2.0), 4)
        if "文字" in c and L.get("type") == "text":
            L["text"] = c["文字"]
        done.append(lid)
    holes = [h for h in change.get("待补的空", []) if all(isinstance(h.get(k), (int, float)) for k in "xywh")]
    return layers, done, cuts, holes, missing


def main(argv):
    if len(argv) < 4 or "-o" not in argv:
        print(__doc__)
        return 2
    layers = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    raw = sys.stdin.read() if argv[1] == "-" else Path(argv[1]).read_text(encoding="utf-8")
    try:
        change = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])  # 主人粘的时候前后可能带了别的字
    except ValueError:
        print("❌ 没认出改动记录：请主人在网页里点「把改动发给丹青」→「复制」，整段粘回来")
        return 1
    layers, done, cuts, holes, missing = apply(layers, change)
    out = argv[argv.index("-o") + 1]
    Path(out).write_text(json.dumps(layers, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK {out}｜改了 {len(done)} 层：{'、'.join(map(str, done)) or '无'}")
    for c in cuts:
        print(f"CUT 圈选挪动：从 {c['原位置']} 挪到 {c['新位置']}——从底图裁原位置那块（paint-master 的 细节.py）当新图层放到新位置")
    for h in holes:
        print(f"HOLE 待补：x={h['x']} y={h['y']} w={h['w']} h={h['h']}（占整张图的比例）——交出图模型只补这一块")
    for m in missing:
        print(f"⚠️ 改动里的图层「{m}」在图层.json 里没有，跳过")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

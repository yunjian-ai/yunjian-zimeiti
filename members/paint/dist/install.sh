#!/usr/bin/env bash
# 丹青安装脚本（tools/pack.py 填好版本后生成 dist/install.sh）。不需要 gh，不需要登录。
# 装、更新、修复：curl -fsSL https://raw.githubusercontent.com/yunjian-ai/yunjian-zimeiti/paint-v0.4.0/members/paint/dist/install.sh | bash
# 只体检、不改：  在 bash 后面加 -s -- --check
# 当 Skill 用：   在 bash 前面加 PAINT_SKILL_DIR=技能目录（比如 ~/.claude/skills）
export GIT_TERMINAL_PROMPT=0
MODE=${1:-install}
T=paint-v0.4.0; R=https://github.com/yunjian-ai/yunjian-zimeiti
RAW=https://raw.githubusercontent.com/yunjian-ai/yunjian-zimeiti/$T/members/paint/dist/recipe.json
W=/tmp/yunjian-$T; RJ=/tmp/recipe-$T.json; rm -rf "${W:?}"
git clone -q --depth 1 --branch "$T" "$R" "$W" 2>/dev/null && cp "$W/members/paint/dist/recipe.json" "$RJ" \
  || curl -fsSL "$RAW" -o "$RJ" || { echo "FETCH_FAILED $R"; exit 1; }
# 技能目录：可用 PAINT_SKILL_DIR 指定；否则找 Grok Bot 的技能目录
D=${PAINT_SKILL_DIR:-}
if [ -z "$D" ]; then
  for cand in /home/box/agent-data/workflows /home/box/sand-data/workflows; do [ -d "$cand" ] && { D=$cand; break; }; done
fi
python3 - "$RJ" "$D" "$MODE" <<'PY'
import hashlib, json, os, sys, time
r = json.load(open(sys.argv[1], encoding="utf-8")); d, mode = sys.argv[2], sys.argv[3]
assert r["version"] == "0.4.0", "版本不对"
ok = [s for s in r["skills"] if s["name"].startswith("paint-") and len(s["content"].encode()) <= 98304]
assert len(ok) == len(r["skills"]), "技能校验没过"
if not d:
    print("NO_SKILL_DIR", len(ok), sys.argv[1]); sys.exit(0)
# 原版：每个技能文件该有的内容；装完在 paint-install 里留一份「装了哪版、每个文件的指纹」
want = {}
for s in ok:
    want[s["name"] + "/SKILL.md"] = s["content"]
    for n, t in s.get("files", {}).items():
        want[s["name"] + "/" + n] = t
fp = lambda t: hashlib.sha256(t.encode()).hexdigest()[:16]
same = lambda a, b: a is not None and b is not None and [x.rstrip() for x in a.replace("\r\n", "\n").strip().split("\n")] == [x.rstrip() for x in b.replace("\r\n", "\n").strip().split("\n")]  # 平台存技能时会动换行和行尾空白，这种不算改过
state_file = os.path.join(d, "paint-install", ".yunjian-installed.json")
try:
    old = json.load(open(state_file, encoding="utf-8"))
except Exception:
    old = {}
def now(rel):
    try:
        return open(os.path.join(d, rel), encoding="utf-8").read()
    except Exception:
        return None
if mode == "--check":
    missing = [k for k in want if now(k) is None]
    changed = [k for k in want if now(k) is not None and not same(now(k), want[k])]
    print("CHECK", "OK" if not missing and not changed else "PROBLEM", "装的版本", old.get("version", "不知道"), "对照", r["tag"])
    print("MISSING", ",".join(missing) or "-")
    print("CHANGED", ",".join(changed) or "-")
    sys.exit(0)
# 装：主人自己改过的文件（和上回装的原样不一样）先备份，再换成原版
backup = os.path.join(os.path.expanduser("~"), "yunjian-backup", "paint-" + time.strftime("%Y%m%d-%H%M%S"))
saved = []
for k, t in want.items():
    cur = now(k)
    if cur is not None and not same(cur, t) and old.get("files", {}).get(k) not in (None, fp(cur)):
        os.makedirs(os.path.dirname(os.path.join(backup, k)), exist_ok=True)
        open(os.path.join(backup, k), "w", encoding="utf-8").write(cur); saved.append(k)
    os.makedirs(os.path.dirname(os.path.join(d, k)), exist_ok=True)
    open(os.path.join(d, k), "w", encoding="utf-8").write(t)
json.dump({"version": r["version"], "tag": r["tag"], "installed": time.strftime("%Y-%m-%d"),
           "files": {k: fp(t) for k, t in want.items()}}, open(state_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("INSTALLED", len(ok), d)
if saved:
    print("BACKUP", backup, ",".join(saved))
print("NEXT 收尾照新装的 paint-install 第 3 步做；记忆里没有「丹青安装规矩」，就把下面 RULE 后面那段原样存成一条")
print("RULE", r["memory"][0])
PY
# 公共库（克隆成功才有；整份换新）。「我的库」只建不碰
H=${PAINT_HOME:-$HOME/.yunjian/paint}; L="$W/members/paint/库"
if [ "$MODE" = "--check" ]; then
  [ -f "$H/库/README.md" ] && [ -f "$H/库/规格表.json" ] && echo "LIBRARY OK $H/库" || echo "LIBRARY MISSING $H/库"
elif [ -d "$L" ]; then
  rm -rf "$H/库.new" && mkdir -p "$H/库.new"
  for i in README.md 平台规格.md 规格表.json 场景 品牌元素 参考; do [ -e "$L/$i" ] && cp -R "$L/$i" "$H/库.new/"; done
  rm -rf "$H/库" && mv "$H/库.new" "$H/库"
  python3 "$D/paint-library/库管.py" 建 "$H/我的库" >/dev/null 2>&1 || mkdir -p "$H/我的库"
  echo "LIBRARY $H/库（我的库：$H/我的库，没动）"
else
  echo "LIBRARY_SKIPPED 克隆仓库没成功，库没装；技能照样能用，挑景、品牌元素、参考时会说没用上库"
fi

"""安装脚本实测（shared/安装写法.md 第 7 条）：各位成员的 dist/install.sh 在临时文件夹里走一遍
装 → 体检 OK → 删一个、改一个 → 体检报出来 → 重装修好、改过的先备份 → 再体检 OK；升级时没改过的旧文件不备份；只差换行和行尾空白不算改过。
只用标准库，不联网（直接跑脚本里的 Python 那段，配方用本地 dist/recipe.json）。
用法：python3 tools/test_install.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from common import BRAND  # noqa: E402
DIR = BRAND["目录"]  # 安装脚本里的 ~/.<目录>/、<目录>-backup、.<目录>-installed.json


def run(code, recipe, skills, mode, home):
    env = dict(os.environ, HOME=str(home))
    out = subprocess.run([sys.executable, "-c", code, str(recipe), str(skills), mode],
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    return out.stdout


def check_member(member):
    sh = (ROOT / "members" / member / "dist" / "install.sh").read_text(encoding="utf-8")
    code = sh.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    recipe = ROOT / "members" / member / "dist" / "recipe.json"
    r = json.loads(recipe.read_text(encoding="utf-8"))
    first, second = r["skills"][0]["name"], r["skills"][-1]["name"]
    with tempfile.TemporaryDirectory() as tmp:
        home, skills = Path(tmp), Path(tmp) / "skills"
        skills.mkdir()
        assert run(code, recipe, skills, "install", home).startswith(f"INSTALLED {len(r['skills'])} ")
        assert run(code, recipe, skills, "--check", home).startswith("CHECK OK")
        # 主人改了一个、删了一个
        (skills / first / "SKILL.md").write_text("主人自己改的", encoding="utf-8")
        (skills / second / "SKILL.md").unlink()
        out = run(code, recipe, skills, "--check", home)
        assert out.startswith("CHECK PROBLEM"), out
        assert f"{second}/SKILL.md" in out.split("MISSING", 1)[1].split("\n")[0], out
        assert f"{first}/SKILL.md" in out.split("CHANGED", 1)[1].split("\n")[0], out
        out = run(code, recipe, skills, "install", home)
        assert "BACKUP" in out and f"{first}/SKILL.md" in out, out
        backup = next((home / f"{DIR}-backup").iterdir()) / first / "SKILL.md"
        assert backup.read_text(encoding="utf-8") == "主人自己改的"
        assert run(code, recipe, skills, "--check", home).startswith("CHECK OK")
        # 升级：文件是上一版的原样（指纹对得上）→ 不备份
        state = skills / f"{member}-install" / f".{DIR}-installed.json"
        st = json.loads(state.read_text(encoding="utf-8"))
        (skills / first / "SKILL.md").write_text("上一版的原样", encoding="utf-8")
        import hashlib
        st["files"][f"{first}/SKILL.md"] = hashlib.sha256("上一版的原样".encode()).hexdigest()[:16]
        state.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        assert "BACKUP" not in run(code, recipe, skills, "install", home)
        # 平台存技能时动了换行、行尾空白（内容一样）→ 体检 OK、不备份（10-25 Grok Bot 实测误备份过）
        sk = skills / first / "SKILL.md"
        sk.write_text(sk.read_text(encoding="utf-8").replace("\n", "  \r\n") + "\n\n", encoding="utf-8")
        st = json.loads(state.read_text(encoding="utf-8"))
        st["files"][f"{first}/SKILL.md"] = "别的指纹"
        state.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        assert run(code, recipe, skills, "--check", home).startswith("CHECK OK")
        assert "BACKUP" not in run(code, recipe, skills, "install", home)
    print(f"✅ {member}：装、体检、修复、备份、升级不误备份、换行空白不算改过")


if __name__ == "__main__":
    for m in sorted(p.name for p in (ROOT / "members").iterdir() if (p / "dist" / "install.sh").exists()):
        check_member(m)
    print("全部通过")

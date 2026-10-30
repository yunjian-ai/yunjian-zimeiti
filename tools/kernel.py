"""引擎副本的指纹和核对：引擎仓库的 tools/sync_kernel.py 写锁文件，各项目的 validate.py 照锁文件查。只用标准库，不读项目配置。"""
import hashlib
import json
from pathlib import Path

LOCK = "tools/引擎.lock.json"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def fingerprint(engine, home):
    """引擎源文件＋这一家的配置（品牌、共用规范）合起来的指纹：任何一处改了，各项目的副本就算旧了。"""
    engine = Path(engine)
    h = hashlib.sha256()
    for top in (engine / "引擎", engine / "config" / home):
        for p in sorted(top.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store":
                h.update(p.relative_to(engine).as_posix().encode())
                h.update(p.read_bytes())
    return h.hexdigest()


def check(root, errors, brand=None):
    """副本没被直接改过、品牌和锁的一致；引擎仓库在本机时，再查副本是不是旧了。没有锁文件（公开仓库）就不查。"""
    root = Path(root)
    lf = root / LOCK
    if not lf.exists():
        return
    lock = json.loads(lf.read_text(encoding="utf-8"))
    for rel, want in lock["文件"].items():
        f = root / rel
        if not f.exists():
            errors.append(f"[kernel] {rel}: 引擎副本不见了，在引擎仓库跑 tools/sync_kernel.py")
        elif sha(f.read_bytes()) != want:
            errors.append(f"[kernel] {rel}: 引擎副本被直接改过——改引擎仓库的正本再同步，不在副本上改")
    if brand is not None and brand != lock["品牌"]:
        errors.append("[kernel] tools/config.json 的 brand 和引擎锁的不一样——品牌改引擎仓库 config/<家>/品牌.json 再同步")
    engine = (root / lock["引擎位置"]).resolve()
    if not (engine / "引擎" / "VERSION").exists():
        print("ℹ️ [kernel] 引擎仓库不在这台机器上，跳过新旧比对")
        return
    if fingerprint(engine, lock["家"]) != lock["引擎指纹"]:
        errors.append(f"[kernel] 引擎有新改动（这里锁的是 v{lock['版本']}），在引擎仓库跑 python3 tools/sync_kernel.py 同步过来")

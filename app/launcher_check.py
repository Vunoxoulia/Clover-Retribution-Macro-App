import glob
import importlib
import os
import sys

PACKAGES = ["customtkinter", "mss", "numpy", "cv2", "keyboard", "pynput", "pywinctl", "screeninfo", "PIL", "requests"]


def damaged_app_files():
    here = os.path.dirname(os.path.abspath(__file__))
    bad = []
    for p in glob.glob(os.path.join(here, "**", "*.py"), recursive=True):
        try:
            with open(p, "rb") as f:
                src = f.read()
            if b"\0" in src:
                bad.append(os.path.relpath(p, os.path.dirname(here)))
            else:
                compile(src, p, "exec")
        except (OSError, SyntaxError, ValueError):
            bad.append(os.path.relpath(p, os.path.dirname(here)))
    for name in ("main.py", "gui.py", "utils.py", "settings.py", "logic_base.py"):
        if not os.path.exists(os.path.join(here, name)):
            bad.append(os.path.join("app", name) + " (missing)")
    return bad


def broken_packages():
    bad = []
    for m in PACKAGES:
        try:
            importlib.import_module(m)
        except Exception as e:
            bad.append(f"{m}: {str(e)[:100]}")
    return bad


if __name__ == "__main__":
    app = damaged_app_files()
    if app:
        print("\n".join("      " + p for p in app))
        sys.exit(2)
    pk = broken_packages()
    if pk:
        print("\n".join("      " + p for p in pk))
        sys.exit(3)
    sys.exit(0)

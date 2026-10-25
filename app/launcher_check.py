"""Run by Windows_Launcher.bat before the macro starts: are the files OK?

Exit 0 = fine. Exit 2 = the macro's own files are damaged (re-download). Exit 3 = an installed package is
damaged / won't load (the launcher reinstalls them). The problems are printed, one per line.
Damage usually means null bytes: a download / unzip / install that was cut off, antivirus, or a cloud-sync
placeholder. Python then only says "source code string cannot contain null bytes" at the import line."""
import glob
import importlib
import os
import sys

# the packages the macro imports when it starts (the text reader loads later and has its own message)
PACKAGES = ["customtkinter", "mss", "numpy", "cv2", "keyboard", "pynput", "pywinctl", "screeninfo", "PIL", "requests"]


def damaged_app_files():
    here = os.path.dirname(os.path.abspath(__file__))
    bad = []
    for p in glob.glob(os.path.join(here, "**", "*.py"), recursive=True):
        try:
            with open(p, "rb") as f:
                src = f.read()
            # null bytes = damaged; not readable as Python = cut off part way (download / unzip stopped early)
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

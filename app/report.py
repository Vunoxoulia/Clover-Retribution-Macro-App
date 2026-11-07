import copy
import json
import os
import platform
import sys
import time
import zipfile

PACKAGES = ("customtkinter", "mss", "numpy", "opencv-python", "keyboard", "rapidocr_onnxruntime", "onnxruntime",
            "pynput", "pywinctl", "screeninfo", "Pillow", "requests")
HIDDEN = "(removed)"
MAX_SHOTS = 10


def private_removed(settings):
    s = copy.deepcopy(settings)
    ev = s.get("event_notifier")
    if isinstance(ev, dict):
        for k in ("webhook", "mention", "people", "window_ps"):
            if ev.get(k):
                ev[k] = HIDDEN
        for e in ev.get("events") or []:
            if isinstance(e, dict):
                for k in ("mention", "role"):
                    if e.get(k):
                        e[k] = HIDDEN
    for k in [k for k in s if k.endswith("server_code") and s[k]]:
        s[k] = HIDDEN
    return s


def system_info(version):
    from importlib import metadata
    lines = [f"VunVun's Macro {version}", f"Saved {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"Python {platform.python_version()} {64 if sys.maxsize > 2 ** 32 else 32}-bit ({sys.executable})",
             f"Windows {platform.platform()} ({platform.machine()})", "", "Packages:"]
    for p in PACKAGES:
        try:
            lines.append(f"  {p} {metadata.version(p)}")
        except Exception:
            lines.append(f"  {p} - not found")
    return "\n".join(lines) + "\n"


def save_report(path, settings, version):
    from settings import get_base_path
    import applog
    base = get_base_path()
    put = []
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("system.txt", system_info(version))
        put.append("system info")
        log = applog.log_path()
        for f in (log, log + ".1"):
            if os.path.exists(f):
                z.write(f, os.path.basename(f))
        if os.path.exists(log):
            put.append("log")
        z.writestr("settings (private things removed).json", json.dumps(private_removed(settings), indent=2))
        put.append("settings without your webhook / IDs / codes")
        shots = os.path.join(base, "debug")
        if os.path.isdir(shots):
            pics = sorted((os.path.join(shots, f) for f in os.listdir(shots) if f.lower().endswith(".png")),
                          key=os.path.getmtime, reverse=True)[:MAX_SHOTS]
            for f in pics:
                z.write(f, "debug/" + os.path.basename(f))
            if pics:
                put.append(f"{len(pics)} debug screenshot(s)")
    return put

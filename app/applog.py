import os
import platform
import sys
import threading
import time

MAX_BYTES = 1_000_000
_path = None


def log_path():
    if _path:
        return _path
    from settings import get_base_path
    return os.path.join(get_base_path(), "logs", "macro.log")


class _Tee:

    def __init__(self, console, fh, lock):
        self.console, self.fh, self.lock = console, fh, lock
        self.line_start = True

    def write(self, text):
        if self.console is not None:
            try:
                self.console.write(text)
            except Exception:
                try:
                    self.console.write(text.encode("ascii", "replace").decode())
                except Exception:
                    pass
        with self.lock:
            try:
                for part in text.splitlines(keepends=True):
                    if self.line_start:
                        self.fh.write(time.strftime("%Y-%m-%d %H:%M:%S  "))
                    self.fh.write(part)
                    self.line_start = part.endswith("\n")
                self.fh.flush()
            except Exception:
                pass
        return len(text)

    def flush(self):
        for f in (self.console, self.fh):
            try:
                if f is not None:
                    f.flush()
            except Exception:
                pass

    def isatty(self):
        return False

    @property
    def encoding(self):
        return getattr(self.console, "encoding", "utf-8") or "utf-8"


def start(version=""):
    global _path
    try:
        path = log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > MAX_BYTES:
            os.replace(path, path + ".1")
        fh = open(path, "a", encoding="utf-8", errors="replace")
    except Exception:
        return
    _path = path
    lock = threading.Lock()
    sys.stdout = _Tee(sys.stdout, fh, lock)
    sys.stderr = _Tee(sys.stderr, fh, lock)
    bits = 64 if sys.maxsize > 2 ** 32 else 32
    print(f"===== VunVun's Macro {version} started - Python {platform.python_version()} {bits}-bit, "
          f"{platform.platform()} =====")


def open_log():
    path = log_path()
    if not os.path.exists(path):
        return False
    try:
        os.startfile(path)
        return True
    except Exception:
        return False

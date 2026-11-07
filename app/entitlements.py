import hashlib
import importlib.abc
import importlib.util
import json
import os
import sys
import threading
import time

LICENSE_SERVER = "https://cloverretributionprivatemacros.onrender.com"
SERVER_PUBLIC_KEY = ""

_checked = {}
_CACHE_SECS = 300
_lock = threading.Lock()


def available():
    return bool(LICENSE_SERVER) or bool(_dev_addons())


def machine_id():
    parts = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as k:
            parts.append(winreg.QueryValueEx(k, "MachineGuid")[0])
    except Exception:
        pass
    try:
        import subprocess
        out = subprocess.run(["wmic", "baseboard", "get", "serialnumber"], capture_output=True, text=True,
                             timeout=5, creationflags=0x08000000).stdout
        line = [l.strip() for l in out.splitlines() if l.strip() and "serialnumber" not in l.lower()]
        if line:
            parts.append(line[0])
    except Exception:
        pass
    if not parts:
        import uuid
        parts.append(f"{uuid.getnode():x}")
    return hashlib.sha256("|".join(parts).encode("utf-8", "replace")).hexdigest()[:32]


def _data(name):
    from settings import get_base_path
    return os.path.join(get_base_path(), name)


def read_key():
    try:
        with open(_data("access_key.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def save_key(key):
    try:
        with open(_data("access_key.txt"), "w", encoding="utf-8") as f:
            f.write((key or "").strip())
        _checked.clear()
        _save_cache([])
        return True
    except Exception:
        return False


def _load_cache():
    try:
        with open(_data("addons_unlocked.json"), encoding="utf-8") as f:
            return [a for a in json.load(f) if isinstance(a, dict) and a.get("name")]
    except Exception:
        return []


def _save_cache(addons):
    try:
        with open(_data("addons_unlocked.json"), "w", encoding="utf-8") as f:
            json.dump([{k: a.get(k) for k in ("name", "title", "icon", "desc")} for a in addons], f)
    except Exception:
        pass


def _dev_dir():
    try:
        with open(_data("private_addons_dir.txt"), encoding="utf-8") as f:
            path = f.read().strip().strip('"')
        return path or None
    except Exception:
        return None


def _manifest(folder):
    try:
        with open(os.path.join(folder, "manifest.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _dev_addons():
    d = _dev_dir()
    out = []
    if d and os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            m = _manifest(os.path.join(d, name))
            if m:
                out.append({"name": name, "title": m.get("title", name), "icon": m.get("icon", "✦"),
                            "desc": m.get("desc", ""), "dev": True})
    return out


def known_addons():
    out = _dev_addons()
    have = {a["name"] for a in out}
    if read_key():
        out += [a for a in _load_cache() if a["name"] not in have]
    return out


def addon_title(name):
    return next((a.get("title") or name for a in known_addons() if a["name"] == name), name)


def _ask_server(addon, key, want_code):
    if not LICENSE_SERVER or not key:
        return None
    import requests
    url = LICENSE_SERVER.rstrip("/") + "/check"
    body = {"addon": addon or "", "key": key, "machine": machine_id(), "version": 2, "code": bool(want_code)}
    last = None
    for attempt in range(2):
        try:
            r = requests.post(url, json=body, timeout=(10, 90))
            if r.status_code == 429:
                return {"ok": False, "busy": True, "reason": "too many checks - wait a few minutes"}
            if r.status_code != 200:
                return {"ok": False, "busy": True, "reason": f"server said {r.status_code}"}
            data = r.json()
            return data if _reply_ok(data) else {"ok": False, "reason": "reply couldn't be verified"}
        except Exception as e:
            last = f"couldn't reach the server ({type(e).__name__})"
    return {"ok": False, "reason": last}


def _reply_ok(data):
    if not SERVER_PUBLIC_KEY:
        return True
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        import base64
        sig = base64.b64decode(data.get("sig", ""))
        signed = f"{data.get('ok')}|{data.get('addon')}|{data.get('machine')}|{data.get('exp')}".encode()
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(SERVER_PUBLIC_KEY)).verify(sig, signed)
        return True
    except Exception:
        return False


def refresh_addons():
    key = read_key()
    if not key:
        _save_cache([])
        return known_addons(), "no key entered"
    reply = _ask_server("", key, want_code=False)
    if reply is None:
        return known_addons(), "no server"
    if reply.get("ok") and reply.get("addon"):
        meta = reply.get("meta") or {}
        _save_cache([{"name": reply["addon"], "title": meta.get("title", reply["addon"]),
                      "icon": meta.get("icon", "✦"), "desc": meta.get("desc", "")}])
        _checked[reply["addon"]] = (True, time.time())
    elif not reply.get("busy") and "couldn't reach" not in (reply.get("reason") or ""):
        _save_cache([])
    return known_addons(), reply.get("reason", "ok")


def check(addon):
    if any(a["name"] == addon for a in _dev_addons()):
        return True, "your own add-on"
    hit = _checked.get(addon)
    if hit and time.time() - hit[1] < _CACHE_SECS:
        return hit[0], "cached"
    key = read_key()
    if not key:
        return False, "no key entered"
    reply = _ask_server(addon, key, want_code=False)
    ok = bool(reply and reply.get("ok"))
    if not (reply or {}).get("busy"):
        _checked[addon] = (ok, time.time())
    return ok, (reply or {}).get("reason", "ok" if ok else "key not accepted")


class _MemoryModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self):
        self.sources = {}

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.sources:
            return importlib.util.spec_from_loader(fullname, self, origin=f"<addon:{fullname}>")
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(compile(self.sources[module.__name__], module.__spec__.origin, "exec"), module.__dict__)


_MEMORY = _MemoryModules()


def _install(sources):
    with _lock:
        if _MEMORY not in sys.meta_path:
            sys.meta_path.insert(0, _MEMORY)
        for name in sources:
            sys.modules.pop(name, None)
        _MEMORY.sources.update(sources)


def load_addon(name):
    import base64
    base = _dev_dir()
    d = os.path.join(base, name) if base else ""
    m = _manifest(d) if d else None
    if m:
        sources = {}
        for f in os.listdir(d):
            if f.endswith(".py"):
                with open(os.path.join(d, f), encoding="utf-8") as fh:
                    sources[f[:-3]] = fh.read()
        entry = m.get("entry")
    else:
        reply = _ask_server(name, read_key(), want_code=True)
        if not reply or not reply.get("ok"):
            return None, (reply or {}).get("reason", "no key entered")
        if reply.get("modules"):
            sources = {k: base64.b64decode(v).decode("utf-8") for k, v in reply["modules"].items()}
            entry = reply.get("entry")
        elif reply.get("code"):
            entry = f"addon_{name}"
            sources = {entry: base64.b64decode(reply["code"]).decode("utf-8")}
        else:
            return None, "the server sent no code"
    if not entry or entry not in sources:
        return None, "the add-on has no entry module"
    try:
        _install(sources)
        mod = importlib.import_module(entry)
        _checked[name] = (True, time.time())
        return mod, "ok"
    except Exception as e:
        print(f"Add-on '{name}' failed to start: {type(e).__name__}: {e}")
        return None, f"it failed to start ({type(e).__name__})"

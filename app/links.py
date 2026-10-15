"""Links (videos, Discord, donate...) read from links.txt in the GitHub repo, so they can be changed
without a new release.

Order of preference: the copy downloaded from GitHub this start  →  the last downloaded copy
(links_cache.txt)  →  the links.txt shipped with the app  →  the defaults below.
The download runs in the background with a short timeout, so the app never waits for it."""
import os
import threading

REMOTE_URL = "https://raw.githubusercontent.com/Vunoxoulia/Clover-Retribution-Macro-App/main/app/links.txt"
CACHE_FILE = "links_cache.txt"

DEFAULTS = {
    "video_library": "https://youtu.be/oTvYkCcnIrc",
    "video_mining": "https://youtu.be/mD85aJdDbfE",
    "video_fishing": "https://youtu.be/a_4odPOc3e4",
    "video_skill": "https://youtu.be/CwSAvulD4Ac",
    "video_events": "https://youtu.be/Ye4gGTp7fzE",
    "youtube": "https://www.youtube.com/@Vunoxoulia",
    "discord": "https://discord.com/invite/VRMB4djfzp",
    "donate_robux": "https://www.roblox.com/communities/34022778/The-Manga-Corner#!/store",
    "donate_money": "https://ko-fi.com/vunoxoulia",
}

_links = dict(DEFAULTS)
_lock = threading.Lock()


def _base():
    from settings import get_base_path
    return get_base_path()


def parse(text):
    """'name = link' lines -> {name: link}. Only http(s) links are accepted."""
    out = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip().lower(), val.strip()
        if key and val.startswith(("https://", "http://")):
            out[key] = val
    return out


def _apply(text):
    found = parse(text)
    if found:
        with _lock:
            _links.update(found)
    return found


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def load_local():
    """Shipped links.txt, then the newer downloaded copy on top of it."""
    from settings import get_app_path
    _apply(_read(os.path.join(get_app_path(), "links.txt")))
    _apply(_read(os.path.join(_base(), CACHE_FILE)))


def refresh_async():
    """Fetch links.txt from GitHub in the background; keep a copy for offline starts."""
    def run():
        try:
            import requests
            r = requests.get(REMOTE_URL, timeout=6)
            if r.status_code == 200 and _apply(r.text):
                with open(os.path.join(_base(), CACHE_FILE), "w", encoding="utf-8") as f:
                    f.write(r.text)
        except Exception:
            pass                                         # offline: keep the local links
    threading.Thread(target=run, daemon=True).start()


def get(key):
    """The current link for `key` (always returns something usable)."""
    with _lock:
        return _links.get(key) or DEFAULTS.get(key, "")


def open_link(key):
    import webbrowser
    url = get(key)
    if url:
        webbrowser.open(url)


load_local()

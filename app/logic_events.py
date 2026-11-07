import re
import time
import copy
import threading
import keyboard
import pywinctl
import cv2
import numpy as np
from utils import SpatialUtils, RobloxInputDriver

DEFAULT_EVENTS = [
    ("Bandit Lord", "whispers rise"), ("Warlord", "warlord"), ("Khamsin", "khamsin"),
    ("Desert Village Rumor", "might not survive"), ("Craftsman", "craftsman"),
    ("Corrupt Night", "consumed by corruption"), ("Mana Wisp", "mana fluttering"),
    ("Radiant Wisp", "radiant wisp"), ("Blood Wisp", "blood wisp"), ("Wind Wisp", "wind wisp"),
    ("Shadowhand Rift", "shadowhand"), ("Devil Rift", "feels off"), ("Spirit Rift", "strange energy"),
    ("Giant Demon Assault", "giant demon"), ("Ayato", "veil shimmers"),
    ("One Star Dragon Ball", "single star"), ("Two Star Dragon Ball", "two stars align"),
    ("Three Star Dragon Ball", "three stars blaze"), ("Four Star Dragon Ball", "four stars glow"),
    ("Five Star Dragon Ball", "five stars radiate"), ("Six Star Dragon Ball", "six stars shimmer"),
    ("Seven Star Dragon Ball", "seven stars"), ("Blessed Sphere", "blessed sphere"),
]

DEFAULT_CFG = {
    "enabled": False,
    "webhook": "",
    "window_ps": {},
    "window_world": {},
    "mention": "",
    "window_chat": {},
    "interval": 60,
    "cooldown": 120,
    "event_lines_only": True,
    "clear_chat": False,
    "clear_cmd": "/clear",
    "sound_on_alert": False,
    "clear_in_global": True,
    "hover_chat": True,
    "unreadable_warn": 10,
    "chat_ping": 300,
    "chat_ping_post": True,
    "chat_ping_mention": "",
    "events": [{"enabled": True, "name": n, "keyword": k, "mention": ""} for n, k in DEFAULT_EVENTS],
}


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def compact(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def clean_for_ocr(rgb):
    v = rgb.max(axis=2).astype(np.float32)
    sat = (rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2)).astype(np.float32)
    v = np.clip(v + 0.35 * sat, 0, 255)
    bg = cv2.GaussianBlur(v, (0, 0), 9)
    v = np.clip((v - bg) * 2.2 + 40, 0, 255).astype(np.uint8)
    h, w = v.shape
    v = cv2.resize(v, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)
    return cv2.cvtColor(255 - v, cv2.COLOR_GRAY2RGB)


def grab_window(hwnd):
    try:
        import ctypes
        import ctypes.wintypes as wt
        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        r = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        if w <= 0 or h <= 0:
            return None
        hdc = user32.GetWindowDC(hwnd)
        mdc = gdi32.CreateCompatibleDC(hdc)
        bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
        gdi32.SelectObject(mdc, bmp)
        ok = user32.PrintWindow(hwnd, mdc, 2)

        class BIH(ctypes.Structure):
            _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                        ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                        ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                        ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]
        bi = BIH(biSize=ctypes.sizeof(BIH), biWidth=w, biHeight=-h, biPlanes=1, biBitCount=32)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
        gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(hwnd, hdc)
        if not ok:
            return None
        img = np.frombuffer(buf, np.uint8).reshape(h, w, 4)[:, :, 2::-1].copy()
        return None if img.max() < 8 else img
    except Exception:
        return None


def roblox_windows():
    try:
        wins = [w for w in pywinctl.getWindowsWithTitle("Roblox") if w.title.strip() == "Roblox"]
    except Exception:
        return []
    wins = [w for w in wins if w.width > 200 and w.height > 200 and not getattr(w, "isMinimized", False)]
    return sorted(wins, key=lambda w: (round(w.top / 200), w.left))


def role_text(r):
    r = (r or "").strip()
    if r.startswith("<@&"):
        return r
    digits = re.sub(r"[^0-9]", "", r)
    return f"<@&{digits}>" if len(digits) >= 15 else ""


def mention_text(m):
    m = (m or "").strip()
    if not m:
        return ""
    if m.startswith("<@"):
        return m
    m = m.lstrip("@")
    if m.lower().startswith("role:"):
        m = "&" + m[5:].strip()
    if m.startswith("&") and m[1:].isdigit():
        return f"<@&{m[1:]}>"
    if m.isdigit():
        return f"<@{m}>"
    return "@" + m


class EventWatcher:

    def __init__(self):
        self.settings = None
        self.utils = SpatialUtils()
        self.running = False
        self._thread = None
        self._counts = {}
        self._last_post = {}
        self._prev_lines = {}
        self._retry = {}
        self.on_log = None
        self.last_lines = []
        self.last_raw_lines = 0
        self.last_raw_sig = ()
        self.recent = []
        self._readable_at = {}
        self._changed_at = {}
        self._sig = {}
        self._bad = {}
        self._pinged = {}
        self._last_wins = {}
        self._outbox = []

    def attach(self, settings):
        self.settings = settings

    @property
    def cfg(self):
        st = self.settings.settings
        cfg = st.get("event_notifier")
        if not cfg:
            cfg = st["event_notifier"] = copy.deepcopy(DEFAULT_CFG)
        if "chat_ping" not in cfg:
            cfg["chat_ping"] = int(round(float(cfg.get("unreadable_warn", 10) or 0) * 60))
        for k, v in DEFAULT_CFG.items():
            cfg.setdefault(k, copy.deepcopy(v))
        if float(cfg.get("interval") or 0) < 15:
            cfg["interval"] = 60
        fixes = {("Bandit Lord", "bandit lord"): "whispers rise",
                 ("Desert Village Rumor", "desert village"): "might not survive"}
        for ev in cfg["events"]:
            new = fixes.get((ev.get("name"), (ev.get("keyword") or "").strip().lower()))
            if new:
                ev["keyword"] = new
            ev.setdefault("role", "")
        self._import_roles(cfg)
        return cfg

    def _import_roles(self, cfg):
        import os, json
        from settings import get_base_path
        path = os.path.join(get_base_path(), "event_roles_import.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                roles = json.load(f)
            for ev in cfg["events"]:
                if ev.get("name") in roles:
                    ev["role"] = str(roles[ev["name"]])
            self.settings.save()
            os.remove(path)
            print(f"[Events] Imported role pings for {len(roles)} event(s).")
        except Exception as e:
            print(f"[Events] Role import failed: {e}")

    def save(self):
        self.settings.save()

    def log(self, msg):
        print(f"[Events] {msg}")
        if self.on_log:
            try:
                self.on_log(msg)
            except Exception:
                pass

    @staticmethod
    def window_number(w):
        for i, x in enumerate(roblox_windows(), start=1):
            if x.getHandle() == w.getHandle():
                return i
        return 0

    def set_window_chat(self, n, x1, y1, x2, y2):
        wins = roblox_windows()
        if not 1 <= n <= len(wins):
            return False
        w = wins[n - 1]
        self.cfg.setdefault("window_chat", {})[str(n)] = [x1 - w.left, y1 - w.top, x2 - w.left, y2 - w.top]
        self.save()
        return True

    def chat_region(self, w, win_no=None):
        if win_no is None:
            win_no = self.window_number(w)
        own = self.cfg.get("window_chat", {}).get(str(win_no))
        if own:
            return [w.left + own[0], w.top + own[1], w.left + own[2], w.top + own[3]]
        return None

    def has_chat_area(self):
        return bool(self.cfg.get("window_chat"))

    def _snap(self, w, region):
        img = grab_window(w.getHandle()) if hasattr(w, "getHandle") else None
        if img is not None:
            x1, y1, x2, y2 = (region[0] - w.left, region[1] - w.top, region[2] - w.left, region[3] - w.top)
            crop = img[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
            if crop.size:
                return crop
        return self.utils.capture_screen(region)

    def _capture_with_hover(self, region, w=None):
        snap = (lambda: self._snap(w, region)) if w is not None else (lambda: self.utils.capture_screen(region))
        if not self.cfg.get("hover_chat", True):
            return snap()
        from pynput.mouse import Controller as MouseController
        mouse = MouseController()
        cx, cy = (region[0] + region[2]) // 2, (region[1] + region[3]) // 2
        with RobloxInputDriver._lock:
            back = mouse.position
            RobloxInputDriver.move_to(cx, cy)
            time.sleep(0.05)
            RobloxInputDriver.move_to(cx + 3, cy + 3)
            time.sleep(float(self.cfg.get("hover_wait", 0.6)))
            shot = snap()
            RobloxInputDriver.move_to(int(back[0]), int(back[1]))
        return shot

    def read_lines(self, w, win_no=None):
        self.last_raw_lines = 0
        self.last_raw_sig = ()
        region = self.chat_region(w, win_no)
        if not region:
            return []
        self.utils._init_ocr()
        if not self.utils.ocr_reader:
            self.last_raw_lines = 0
            self.log(self.utils.ocr_error or "Text reading (OCR) couldn't start.")
            return []
        try:
            shot = self._capture_with_hover(region, w)
            res, _ = self.utils.ocr_reader(clean_for_ocr(shot))
        except Exception as e:
            self.log(f"OCR error: {e}")
            return []
        boxes = [(min(p[1] for p in b), min(p[0] for p in b), t) for b, t, conf in (res or []) if float(conf) > 0.4]
        self.last_raw_lines = len(boxes)
        self.last_raw_sig = tuple(t for _, _, t in sorted(boxes))
        lines = []
        for _, _, t in sorted(boxes):
            if lines and not t.lstrip().startswith("["):
                lines[-1] += " " + t
            else:
                lines.append(t)
        if self.cfg.get("event_lines_only", True):
            lines = [t for t in lines if any(tag in compact(t)[:10] for tag in self.EVENT_TAGS)]
        return lines

    EVENT_TAGS = ("event", "leak")

    def new_since_last(self, key, lines):
        cur = [compact(t) for t in lines]
        prev = self._prev_lines.get(key)
        self._prev_lines[key] = cur
        if prev is None or not cur:
            return None
        if cur == prev:
            return []
        for k in range(min(len(prev), len(cur)), 0, -1):
            if prev[-k:] == cur[:k]:
                return lines[k:]
        return None

    def count_events(self, lines):
        counts = {}
        normed = [compact(t) for t in lines]
        for ev in self.cfg["events"]:
            kw = compact(ev.get("keyword", ""))
            if kw:
                counts[ev["name"]] = sum(1 for t in normed if kw in t)
        return counts

    def ps_for(self, win_no):
        return self.cfg.get("window_ps", {}).get(str(win_no), "").strip()

    WORLDS = ("Clover Kingdom", "Jungle")

    def world_for(self, win_no):
        w = self.cfg.get("window_world", {}).get(str(win_no), self.WORLDS[0])
        return w if w in self.WORLDS else self.WORLDS[0]

    def format_message(self, ev, win_no=1):
        msg = ev["name"]
        msg += f" - {self.world_for(win_no)}"
        ps = self.ps_for(win_no)
        if ps:
            msg += f" - {ps}"
        pings = [mention_text(x) for x in (ev.get("mention") or self.cfg.get("mention") or "").split()]
        pings += [role_text(x) for x in (ev.get("role") or "").replace(",", " ").split()]
        if pings:
            msg += " " + " ".join(p for p in pings if p)
        return msg

    WEBHOOK_ERRORS = {
        400: "Discord rejected the message (bad format)",
        401: "the webhook link is wrong (unauthorized) - copy it again from Discord",
        403: "this webhook isn't allowed to post in that channel",
        404: "the webhook was deleted or the link is wrong - make a new one in Discord and paste it again",
    }

    def post(self, text):
        self.last_post_error = ""
        url = self.cfg.get("webhook", "").strip()
        if not url:
            self.last_post_error = "no Discord webhook set"
            self.log("No Discord webhook set — not sent.")
            return False
        if not url.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/",
                               "https://ptb.discord.com/api/webhooks/", "https://canary.discord.com/api/webhooks/")):
            self.last_post_error = "that isn't a Discord webhook link (it should start with https://discord.com/api/webhooks/)"
            self.log(f"Not sent: {self.last_post_error}")
            return False
        import requests
        if len(text) > 1990:
            text = text[:1987] + "..."
        for attempt in range(3):
            try:
                r = requests.post(url, json={"content": text,
                                             "allowed_mentions": {"parse": ["users", "roles", "everyone"]}},
                                  timeout=8)
            except Exception as e:
                self.last_post_error = f"couldn't reach Discord ({type(e).__name__}) - check your internet"
                self.log(f"Not sent: {self.last_post_error}")
                return False
            if r.status_code in (200, 204):
                return True
            if r.status_code == 429 and attempt < 2:
                try:
                    wait = float(r.json().get("retry_after", 1.0))
                except Exception:
                    wait = 1.0
                time.sleep(min(10.0, max(0.5, wait)))
                continue
            reason = self.WEBHOOK_ERRORS.get(r.status_code, "Discord refused it")
            if r.status_code == 429:
                reason = "Discord is rate-limiting this webhook - try again in a minute"
            self.last_post_error = f"{reason} (error {r.status_code})"
            self.log(f"Not sent: {self.last_post_error}. Discord said: {r.text[:120]}")
            return False
        return False

    @staticmethod
    def _tap(key, hold=0.04):
        from utils import press_key
        press_key(key, True)
        time.sleep(hold)
        press_key(key, False)

    @staticmethod
    def _type_char(ch, hold=0.04):
        import ctypes
        user32 = ctypes.windll.user32
        res = user32.VkKeyScanW(ctypes.c_wchar(ch))
        if res == -1:
            keyboard.write(ch)
            return
        vk, mods = res & 0xFF, (res >> 8) & 0xFF
        held = [m for bit, m in ((1, 0x10), (2, 0x11), (4, 0x12)) if mods & bit]
        for m in held:
            user32.keybd_event(m, user32.MapVirtualKeyW(m, 0), 0, 0)
        sc = user32.MapVirtualKeyW(vk, 0)
        user32.keybd_event(vk, sc, 0, 0)
        time.sleep(hold)
        user32.keybd_event(vk, sc, 2, 0)
        for m in reversed(held):
            user32.keybd_event(m, user32.MapVirtualKeyW(m, 0), 2, 0)

    @staticmethod
    def _select_all():
        import ctypes
        user32 = ctypes.windll.user32
        user32.keybd_event(0x11, 0x1D, 0, 0)
        user32.keybd_event(0x41, user32.MapVirtualKeyW(0x41, 0), 0, 0)
        time.sleep(0.04)
        user32.keybd_event(0x41, user32.MapVirtualKeyW(0x41, 0), 2, 0)
        user32.keybd_event(0x11, 0x1D, 2, 0)

    @staticmethod
    def focus_window(hwnd, timeout=1.5):
        import ctypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        if user32.GetForegroundWindow() == hwnd:
            return True
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
        fg = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg, None)
        me = kernel32.GetCurrentThreadId()
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
        attached = fg_thread and fg_thread != me and user32.AttachThreadInput(me, fg_thread, True)
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(me, fg_thread, False)
        end = time.time() + timeout
        while time.time() < end:
            if user32.GetForegroundWindow() == hwnd:
                return True
            time.sleep(0.05)
        return False

    def find_chat_tabs(self, w):
        key = str(self.window_number(w))
        saved = self.cfg.setdefault("window_tabs", {}).get(key)
        if saved and "here" in saved and "global" in saved:
            return {k: (w.left + v[0], w.top + v[1]) for k, v in saved.items()}
        own = self.cfg.get("window_chat", {}).get(key)
        if own:
            x1, y1, x2, y2 = own
            area = [w.left + max(0, x1 - 40), w.top + max(0, y1 - 160), w.left + x2 + 40, w.top + y1 + 90]
        else:
            area = [w.left, w.top, w.left + w.width // 2, w.top + w.height // 2]
        cx, cy = (area[0] + area[2]) // 2, (area[1] + area[3]) // 2
        RobloxInputDriver.move_to(cx, cy)
        time.sleep(0.05)
        RobloxInputDriver.move_to(cx + 3, cy + 3)
        time.sleep(0.6)
        found = {}
        for box, text, conf in self.utils.get_text_from_region(area):
            t = compact(text)
            name = "here" if t == "here" or t.endswith("here") and len(t) <= 6 else \
                   "global" if "global" in t and len(t) <= 9 else None
            if name and conf > 0.4 and name not in found:
                bx = sum(p[0] for p in box) / len(box)
                by = sum(p[1] for p in box) / len(box)
                found[name] = (int(area[0] + bx), int(area[1] + by))
        return found

    def clear_chat(self, w):
        import ctypes
        try:
            prev = ctypes.windll.user32.GetForegroundWindow()
            cmd = self.cfg.get("clear_cmd", "/clear") or "/clear"
            with RobloxInputDriver._lock:
                if not self.focus_window(w.getHandle()):
                    self.log(f"/clear skipped for window {self.window_number(w)}: Windows wouldn't switch to it.")
                    return
                time.sleep(0.3)
                tabs = {}
                if self.cfg.get("clear_in_global", True):
                    tabs = self.find_chat_tabs(w)
                    if "global" in tabs:
                        RobloxInputDriver.glide_click(*tabs["global"], duration=0.05)
                        time.sleep(0.35)
                    else:
                        self.log(f"Window {self.window_number(w)}: couldn't find the Global tab - clearing in the current tab.")
                self._type_char("/")
                time.sleep(0.3)
                self._select_all()
                time.sleep(0.05)
                self._tap("backspace")
                time.sleep(0.1)
                for ch in cmd:
                    self._type_char(ch)
                    time.sleep(0.03)
                time.sleep(0.25)
                self._tap("enter", hold=0.1)
                time.sleep(0.3)
                if "global" in tabs and "here" in tabs:
                    RobloxInputDriver.glide_click(*tabs["here"], duration=0.05)
                    time.sleep(0.25)
                self.log(f"Chat cleared ({cmd}{' in Global' if 'global' in tabs else ''}) in window {self.window_number(w)}.")
            if prev and prev != w.getHandle():
                self.focus_window(prev, timeout=0.5)
        except Exception as e:
            self.log(f"/clear failed: {e}")

    def note(self, name, win_no, what):
        self.recent.append((time.time(), name, win_no, what))
        del self.recent[:-30]

    def chat_alive(self, w, win_no):
        if self.last_raw_lines:
            return True
        tabs = self.cfg.get("window_tabs", {}).get(str(win_no)) or {}
        for name in ("here", "global"):
            if name in tabs:
                x, y = w.left + tabs[name][0], w.top + tabs[name][1]
                try:
                    for _, text, conf in self.utils.get_text_from_region([x - 45, y - 14, x + 45, y + 14]):
                        if conf > 0.4 and name in compact(text):
                            return True
                except Exception:
                    pass
        return False

    def _ping(self, key, win_no, alive, post):
        limit = float(self.cfg.get("chat_ping", 300) or 0)
        now = time.time()
        self._readable_at.setdefault(key, now)
        self._changed_at.setdefault(key, now)
        if alive:
            self._readable_at[key] = now
            if self.last_raw_sig != self._sig.get(key):
                self._sig[key], self._changed_at[key] = self.last_raw_sig, now
        problem = None
        if limit > 0 and now - self._readable_at[key] >= limit:
            problem = (f"can't be read for {int(now - self._readable_at[key])} s - is the chat closed, covered or "
                       f"moved? (Chat area on the Events page)")
        elif limit > 0 and self.last_raw_lines and now - self._changed_at[key] >= limit:
            problem = f"hasn't changed for {int(now - self._changed_at[key])} s - is Roblox frozen or disconnected?"
        self._bad[key] = self._bad.get(key, 0) + 1 if problem else 0
        if problem and self._bad[key] >= 2 and key not in self._pinged:
            self._pinged[key] = problem
            self._alert(f"Window {win_no}: chat {problem}", win_no, post)
        elif not problem and key in self._pinged:
            del self._pinged[key]
            self._alert(f"Window {win_no}: chat is OK again.", win_no, post, warning=False)

    def _ping_closed(self, wins, post):
        if float(self.cfg.get("chat_ping", 300) or 0) <= 0:
            self._last_wins = {w.getHandle(): n for n, w in enumerate(wins, start=1)}
            return
        now = {w.getHandle(): n for n, w in enumerate(wins, start=1)}
        for key, n in self._last_wins.items():
            if key not in now:
                self._pinged[key] = "gone"
                self._alert(f"Roblox window {n} is gone (closed or minimized) - its events aren't read any more.",
                            n, post)
        for key, n in now.items():
            if self._pinged.get(key) == "gone":
                del self._pinged[key]
                self._readable_at[key] = self._changed_at[key] = time.time()
                self._alert(f"Roblox window {n} is back.", n, post, warning=False)
        self._last_wins = now

    def _alert(self, msg, win_no, post, warning=True):
        self.log(("WARNING: " if warning else "") + msg)
        self.note("(chat ping)", win_no, "warning" if warning else "OK again")
        if post and self.cfg.get("chat_ping_post", True):
            text = "[Event Notifier] " + msg
            if warning:
                who = (self.cfg.get("chat_ping_mention") or self.cfg.get("mention") or "").split()
                pings = [mention_text(x) for x in who]
                if any(pings):
                    text += " " + " ".join(p for p in pings if p)
            self._outbox.append(text)
        if warning and self.cfg.get("sound_on_alert", False):
            from utils import play_sound
            play_sound("event")

    def test_event(self, ev):
        name = ev.get("name") or "event"
        kw = compact(ev.get("keyword", ""))
        hit = None
        if kw and self.has_chat_area():
            with RobloxInputDriver._lock:
                for win_no, w in enumerate(roblox_windows(), start=1):
                    lines = self.read_lines(w, win_no)
                    line = next((t for t in lines if kw in compact(t)), None)
                    if line:
                        hit = (win_no, line)
                        break
        if hit:
            win_no, line = hit
            ok = self.post("[TEST - found in chat] " + self.format_message(ev, win_no))
            self.note(name, win_no, "test (found in chat)" + ("" if ok else " - NOT posted"))
            return (f"'{name}' FOUND in window {win_no}'s chat: '{line[:60]}' - "
                    + ("posted a test to Discord." if ok else f"couldn't post: {self.last_post_error}"))
        ok = self.post("[TEST] " + self.format_message(ev, 1))
        self.note(name, 1, "test message" + ("" if ok else " - NOT posted"))
        why = ("its words aren't in any chat right now" if kw and self.has_chat_area()
               else "no chat area set" if kw else "it has no chat words")
        return (f"'{name}': {why}, so a test message was sent instead - "
                + ("check Discord for it and its pings." if ok else f"couldn't post: {self.last_post_error}"))

    def start(self):
        if self.running:
            return
        self.running = True
        self._counts.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.log("Event alerts ON")

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.log("Event alerts OFF")

    def scan_once(self, post=True):
        with RobloxInputDriver._lock:
            found = self._read_all(post)
        new = self._post_found(found, post)
        if post and new and self.cfg.get("clear_chat"):
            with RobloxInputDriver._lock:
                for w in {id(w): w for _, w in new}.values():
                    self.clear_chat(w)
                    time.sleep(0.4)
                    self.read_lines(w, self.window_number(w))
                    if self.last_raw_lines == 0:
                        for ev in self.cfg["events"]:
                            self._counts[(w.getHandle(), ev["name"])] = 0
        return new

    def _read_all(self, post=True):
        self._outbox = []
        found = []
        wins = roblox_windows()
        self._ping_closed(wins, post)
        for win_no, w in enumerate(wins, start=1):
            key = w.getHandle()
            lines = self.read_lines(w, win_no)
            self.last_lines = lines
            if self.last_raw_lines == 0:
                if len(wins) > 1:
                    self.log(f"Window {win_no}: chat not readable this check")
                self._ping(key, win_no, self.chat_alive(w, win_no), post)
                continue
            self._ping(key, win_no, True, post)
            counts = self.count_events(lines)
            new_lines = self.new_since_last(key, lines)
            new_counts = self.count_events(new_lines) if new_lines is not None else {}
            for ev in self.cfg["events"]:
                n, prev = counts.get(ev["name"], 0), self._counts.get((key, ev["name"]))
                self._counts[(key, ev["name"])] = n
                if prev is None:
                    prev = 0
                if (n > prev or new_counts.get(ev["name"], 0) > 0) and ev.get("enabled", True):
                    found.append((ev, w, win_no))
        if len(wins) > 1:
            self.log("Checked " + ", ".join(f"window {i}" for i in range(1, len(wins) + 1)) +
                     (": " + ", ".join(f"{ev['name']} (window {n})" for ev, _, n in found) if found else ": nothing new"))
        return found

    def _post_found(self, found, post=True):
        new = []
        retry = [(ev, w, n) for ev, w, n, _ in self._retry.values()] if post else []
        retried = {(ev["name"], w.getHandle()) for ev, w, _ in retry}
        for ev, w, win_no in retry + [x for x in found if (x[0]["name"], x[1].getHandle()) not in retried]:
            key = (ev["name"], w.getHandle())
            if key not in self._retry and \
                    time.time() - self._last_post.get(key, 0) < float(self.cfg.get("cooldown", 120)):
                continue
            new.append((ev, w))
            msg = self.format_message(ev, win_no)
            if not post:
                continue
            if self.post(msg):
                self._last_post[key] = time.time()
                self._retry.pop(key, None)
                self.log(f"Posted: {msg}")
                self.note(ev["name"], win_no, "posted")
            else:
                tries = self._retry.get(key, [None, None, None, 0])[3] + 1
                why = getattr(self, "last_post_error", "") or "?"
                if tries < 3:
                    self._retry[key] = [ev, w, win_no, tries]
                    self.log(f"Detected {ev['name']} (not posted - trying again next check)")
                else:
                    self._retry.pop(key, None)
                    self._last_post[key] = time.time()
                    self.log(f"Detected {ev['name']} (not posted after 3 tries)")
                self.note(ev["name"], win_no, "NOT posted: " + why)
        if post:
            for msg in self._outbox:
                self.post(msg)
        self._outbox = []
        if post and new and self.cfg.get("sound_on_alert", False):
            from utils import play_sound
            play_sound("event")
        return new

    _holders = set()
    _scan_lock = threading.Lock()

    def hold(self, who):
        self._holders.add(who)

    def release(self, who):
        self._holders.discard(who)

    def checkpoint(self, who):
        if not self.running or not self.has_chat_area():
            return
        self.log(f"Checking events ({who} between rounds)…")
        try:
            with self._scan_lock:
                self.scan_once()
        except Exception as e:
            self.log(f"Scan error: {e}")

    def _loop(self):
        while self.running:
            try:
                if not self.has_chat_area():
                    self.log("Set a chat box for each window first (Chat on the Events page).")
                    self.running = False
                    break
                if not self._holders:
                    with self._scan_lock:
                        self.scan_once()
            except Exception as e:
                self.log(f"Scan error: {e}")
            end = time.time() + float(self.cfg.get("interval", 60))
            while self.running and time.time() < end:
                time.sleep(0.1)


WATCHER = EventWatcher()

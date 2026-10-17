import re
import time
import copy
import threading
import keyboard
import pywinctl
import requests
import cv2
import numpy as np
from utils import SpatialUtils, RobloxInputDriver

# name, keyword (just needs to be inside the chat line), notify on/off
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
    "enabled": False,          # the always-on toggle (like Always Click OK)
    "webhook": "",
    "window_ps": {},           # "1", "2", ... (screen order) -> that window's PS code
    "window_world": {},        # "1", "2", ... -> "Clover Kingdom" or "Jungle" (shown in the message)
    "mention": "",             # @user pinged on every alert (an event's own @user replaces it)
    "window_chat": {},         # "1", "2", ... -> that window's own chat box (pixels from its top-left)
    "interval": 60,            # seconds between scans (OCR is heavy: 1 min keeps the game smooth)
    "cooldown": 120,           # seconds before the same event can be posted again
    "event_lines_only": True,  # ignore player chat: only lines that start with [Event]
    "clear_chat": False,       # type /clear after an alert
    "clear_cmd": "/clear",     # or "/cls"
    "sound_on_alert": False,   # play a Windows sound when an event is posted (optional, off by default)
    "clear_in_global": True,   # /clear doesn't always work in 'Here': click Global, clear, click Here again
    "hover_chat": True,        # move the mouse onto the chat before reading (it fades out otherwise)
    "unreadable_warn": 5,      # minutes a window's chat can be unreadable before a warning (0 = never)
    "events": [{"enabled": True, "name": n, "keyword": k, "mention": ""} for n, k in DEFAULT_EVENTS],
}


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def compact(s):
    """Lowercase letters/digits only. OCR often drops the spaces on coloured chat lines
    ("Awindwisphasappeared"), so keywords are matched with spaces removed on both sides."""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def clean_for_ocr(rgb):
    """Make chat text of ANY colour (green, purple, white) stand out from the see-through chat
    background: keep what's brighter than its surroundings, enlarge, dark text on white."""
    v = rgb.max(axis=2).astype(np.float32)                       # brightest channel lights up coloured text
    sat = (rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2)).astype(np.float32)
    v = np.clip(v + 0.35 * sat, 0, 255)                          # coloured text gets an extra push
    bg = cv2.GaussianBlur(v, (0, 0), 9)                          # local background brightness
    v = np.clip((v - bg) * 2.2 + 40, 0, 255).astype(np.uint8)
    h, w = v.shape
    v = cv2.resize(v, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)
    return cv2.cvtColor(255 - v, cv2.COLOR_GRAY2RGB)


def grab_window(hwnd):
    """Picture of a window's own content (RGB), even when other windows cover it.
    Returns None if Windows can't give it (then the caller falls back to the screen)."""
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
        ok = user32.PrintWindow(hwnd, mdc, 2)            # 2 = PW_RENDERFULLCONTENT, needed for GPU games

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
        img = np.frombuffer(buf, np.uint8).reshape(h, w, 4)[:, :, 2::-1].copy()   # BGRA -> RGB
        return None if img.max() < 8 else img               # all black = capture not supported
    except Exception:
        return None


def roblox_windows():
    """Every open Roblox game window (title exactly 'Roblox', not browser tabs etc.)."""
    try:
        wins = [w for w in pywinctl.getWindowsWithTitle("Roblox") if w.title.strip() == "Roblox"]
    except Exception:
        return []
    wins = [w for w in wins if w.width > 200 and w.height > 200 and not getattr(w, "isMinimized", False)]
    # Number windows by where they sit on screen (top row first, then left to right),
    # so "Window 2" stays the same window as long as you don't rearrange them.
    return sorted(wins, key=lambda w: (round(w.top / 200), w.left))


def check_mentions(text):
    """Split what's typed into an @user box into (pingable, names_that_wont_ping)."""
    ok, bad = [], []
    for part in (text or "").replace(",", " ").split():
        digits = re.sub(r"[<@&!>]|^role:", "", part, flags=re.I)
        (ok if digits.isdigit() and len(digits) >= 15 else bad).append(part)
    return ok, bad


def role_text(r):
    """A role ID typed in an event's Role box -> <@&ID> (anything already formatted is kept)."""
    r = (r or "").strip()
    if r.startswith("<@&"):
        return r
    digits = re.sub(r"[^0-9]", "", r)
    return f"<@&{digits}>" if len(digits) >= 15 else ""


def mention_text(m):
    """'' / a user ID / a role ID with & / an already formatted <@...> -> Discord mention."""
    m = (m or "").strip()
    if not m:
        return ""
    if m.startswith("<@"):
        return m
    m = m.lstrip("@")                          # "@123" / "@&123" typed by hand
    if m.lower().startswith("role:"):
        m = "&" + m[5:].strip()
    if m.startswith("&") and m[1:].isdigit():
        return f"<@&{m[1:]}>"                  # role ping
    if m.isdigit():
        return f"<@{m}>"                       # user ping
    return "@" + m                             # a plain name: shown as text, Discord can't ping it


class EventWatcher:
    """Reads the chat box of every Roblox window and posts new events to a Discord webhook.

    No repeats: for each window and each event it counts how many chat lines contain the keyword.
    Only when that count GOES UP (a new line appeared) is it new — so a line sitting in chat for
    minutes is posted once, and several different events at the same time are all posted.
    A per-window cooldown stops one window posting the same event twice in a row.
    One shared instance (WATCHER) keeps running while you switch between macros."""

    def __init__(self):
        self.settings = None
        self.utils = SpatialUtils()
        self.running = False
        self._thread = None
        self._counts = {}          # (window handle, event name) -> lines seen last scan
        self._last_post = {}       # (event name, window) -> time posted
        self.on_log = None         # GUI callback
        self.last_lines = []
        self.last_raw_lines = 0
        self.recent = []           # [(time, event name, window no, what happened)] newest last
        self._readable_at = {}     # window handle -> last time its chat had readable text
        self._warned = set()       # windows already warned about (until readable again)

    # ---------- config ----------
    def attach(self, settings):
        self.settings = settings

    @property
    def cfg(self):
        st = self.settings.settings
        cfg = st.get("event_notifier")
        if not cfg:
            cfg = st["event_notifier"] = copy.deepcopy(DEFAULT_CFG)
        for k, v in DEFAULT_CFG.items():
            cfg.setdefault(k, copy.deepcopy(v))
        if float(cfg.get("interval") or 0) < 15:      # old 2 s default made the game lag
            cfg["interval"] = 60
        # old default keywords that also matched an event's END message
        fixes = {("Bandit Lord", "bandit lord"): "whispers rise",           # "The Bandit Lord vanishes..."
                 ("Desert Village Rumor", "desert village"): "might not survive"}  # "...disappeared from the Desert Village"
        for ev in cfg["events"]:
            new = fixes.get((ev.get("name"), (ev.get("keyword") or "").strip().lower()))
            if new:
                ev["keyword"] = new
            ev.setdefault("role", "")
        self._import_roles(cfg)
        return cfg

    def _import_roles(self, cfg):
        """One-time: event_roles_import.json ({event name: role ID}) next to the app fills the
        Role boxes of those events, then the file is deleted."""
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

    # ---------- chat area ----------
    @staticmethod
    def window_number(w):
        """1-based screen-order number of this Roblox window (same numbering as the Windows list)."""
        for i, x in enumerate(roblox_windows(), start=1):
            if x.getHandle() == w.getHandle():
                return i
        return 0

    def set_window_chat(self, n, x1, y1, x2, y2):
        """Chat box for ONE window, saved as pixels from that window's top-left corner
        (Roblox's chat keeps its size when the window is resized, so pixels fit better than %)."""
        wins = roblox_windows()
        if not 1 <= n <= len(wins):
            return False
        w = wins[n - 1]
        self.cfg.setdefault("window_chat", {})[str(n)] = [x1 - w.left, y1 - w.top, x2 - w.left, y2 - w.top]
        self.save()
        return True

    def chat_region(self, w, win_no=None):
        """win_no: pass the number the caller already uses for this window, so the chat box and the
        PS code can never come from two different windows."""
        if win_no is None:
            win_no = self.window_number(w)
        own = self.cfg.get("window_chat", {}).get(str(win_no))
        if own:                                          # this window has its own chat box
            return [w.left + own[0], w.top + own[1], w.left + own[2], w.top + own[3]]
        return None                                      # no chat box set for this window: it isn't read

    def has_chat_area(self):
        return bool(self.cfg.get("window_chat"))

    # ---------- reading ----------
    def _snap(self, w, region):
        """The chat box from the Roblox window's OWN picture (works when Discord etc. covers it);
        falls back to the screen if Windows can't capture that window."""
        img = grab_window(w.getHandle()) if hasattr(w, "getHandle") else None
        if img is not None:
            x1, y1, x2, y2 = (region[0] - w.left, region[1] - w.top, region[2] - w.left, region[3] - w.top)
            crop = img[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
            if crop.size:
                return crop
        return self.utils.capture_screen(region)

    def _capture_with_hover(self, region, w=None):
        """Roblox fades the chat out after a while; hovering it brings it back. So: move the mouse onto
        the chat, wait for it to fade in, take the picture, then put the mouse back where it was."""
        snap = (lambda: self._snap(w, region)) if w is not None else (lambda: self.utils.capture_screen(region))
        if not self.cfg.get("hover_chat", True):
            return snap()
        from pynput.mouse import Controller as MouseController
        mouse = MouseController()
        cx, cy = (region[0] + region[2]) // 2, (region[1] + region[3]) // 2
        with RobloxInputDriver._lock:                    # don't fight a running macro's clicks
            back = mouse.position
            RobloxInputDriver.move_to(cx, cy)
            time.sleep(0.05)
            RobloxInputDriver.move_to(cx + 3, cy + 3)    # a small wiggle so Roblox registers the hover
            time.sleep(float(self.cfg.get("hover_wait", 0.6)))
            shot = snap()
            RobloxInputDriver.move_to(int(back[0]), int(back[1]))
        return shot

    def read_lines(self, w, win_no=None):
        region = self.chat_region(w, win_no)
        if not region:
            return []
        self.utils._init_ocr()
        if not self.utils.ocr_reader:
            self.last_raw_lines = 0
            self.log(self.utils.ocr_error or "Text reading (OCR) couldn't start.")   # usually: Visual C++ missing
            return []
        try:
            shot = self._capture_with_hover(region, w)
            res, _ = self.utils.ocr_reader(clean_for_ocr(shot))
        except Exception as e:
            self.log(f"OCR error: {e}")
            return []
        boxes = [(min(p[1] for p in b), min(p[0] for p in b), t) for b, t, conf in (res or []) if float(conf) > 0.4]
        self.last_raw_lines = len(boxes)                # ANY text at all (System, Tips...)? 0 = chat not readable
        lines = []
        for _, _, t in sorted(boxes):                    # top to bottom
            if lines and not t.lstrip().startswith("["):
                lines[-1] += " " + t                      # wrapped continuation of the line above
            else:
                lines.append(t)
        if self.cfg.get("event_lines_only", True):
            lines = [t for t in lines if "event" in compact(t)[:10]]
        return lines

    def count_events(self, lines):
        """{event name: how many lines mention its keyword}"""
        counts = {}
        normed = [compact(t) for t in lines]
        for ev in self.cfg["events"]:
            kw = compact(ev.get("keyword", ""))
            if kw:
                counts[ev["name"]] = sum(1 for t in normed if kw in t)
        return counts

    # ---------- posting ----------
    def ps_for(self, win_no):
        """This window's PS code (empty = the message is just the event name)."""
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
        """Send one message to the Discord webhook. Retries when Discord says 'slow down' (429).
        On failure the reason is kept in self.last_post_error (shown by Send test)."""
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
        if len(text) > 1990:                              # Discord's limit is 2000 characters
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
            if r.status_code == 429 and attempt < 2:      # rate limited: wait as long as Discord asks
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
        keyboard.press(key)
        time.sleep(hold)
        keyboard.release(key)

    @staticmethod
    def _type_char(ch, hold=0.04):
        """Type one character using the CURRENT keyboard layout (QWERTY, AZERTY, QWERTZ...).
        Windows says which key + Shift/Ctrl/Alt makes it; e.g. "/" is Shift+":" on AZERTY.
        (The keyboard library would press the base key without Shift and type ":" instead.)"""
        import ctypes
        user32 = ctypes.windll.user32
        res = user32.VkKeyScanW(ctypes.c_wchar(ch))      # c_wchar: the keyboard library declares it WCHAR
        if res == -1:                                    # this layout can't type it: fall back
            keyboard.write(ch)
            return
        vk, mods = res & 0xFF, (res >> 8) & 0xFF
        held = [m for bit, m in ((1, 0x10), (2, 0x11), (4, 0x12)) if mods & bit]   # Shift, Ctrl, Alt (Ctrl+Alt = AltGr)
        for m in held:
            user32.keybd_event(m, user32.MapVirtualKeyW(m, 0), 0, 0)
        sc = user32.MapVirtualKeyW(vk, 0)
        user32.keybd_event(vk, sc, 0, 0)
        time.sleep(hold)
        user32.keybd_event(vk, sc, 2, 0)                 # 2 = key up
        for m in reversed(held):
            user32.keybd_event(m, user32.MapVirtualKeyW(m, 0), 2, 0)

    @staticmethod
    def _select_all():
        """Ctrl+A by virtual key, which is "select all" on every layout."""
        import ctypes
        user32 = ctypes.windll.user32
        user32.keybd_event(0x11, 0x1D, 0, 0)             # Ctrl down
        user32.keybd_event(0x41, user32.MapVirtualKeyW(0x41, 0), 0, 0)
        time.sleep(0.04)
        user32.keybd_event(0x41, user32.MapVirtualKeyW(0x41, 0), 2, 0)
        user32.keybd_event(0x11, 0x1D, 2, 0)             # Ctrl up

    @staticmethod
    def focus_window(hwnd, timeout=1.5):
        """Really bring a window to the front so key presses go to it. Windows normally blocks a
        background app from stealing focus; tapping Alt first (what Alt+Tab does) and briefly attaching
        to the current foreground thread lets SetForegroundWindow through. Returns True once it's in front."""
        import ctypes
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        if user32.GetForegroundWindow() == hwnd:
            return True
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)                   # SW_RESTORE
        fg = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg, None)
        me = kernel32.GetCurrentThreadId()
        user32.keybd_event(0x12, 0, 0, 0)                # Alt down
        user32.keybd_event(0x12, 0, 2, 0)                # Alt up
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
        """Where the chat's 'Here' and 'Global' tabs are in this window: the spots picked with Tabs on the
        Events page, or (not picked yet) read with OCR just above the window's chat box.
        Returns {"here": (x, y), "global": (x, y)} in screen pixels (missing ones left out)."""
        key = str(self.window_number(w))
        saved = self.cfg.setdefault("window_tabs", {}).get(key)
        if saved and "here" in saved and "global" in saved:
            return {k: (w.left + v[0], w.top + v[1]) for k, v in saved.items()}
        own = self.cfg.get("window_chat", {}).get(key)
        if own:
            x1, y1, x2, y2 = own
            area = [w.left + max(0, x1 - 40), w.top + max(0, y1 - 160), w.left + x2 + 40, w.top + y1 + 90]
        else:                                            # no chat box set: chat sits in the top-left
            area = [w.left, w.top, w.left + w.width // 2, w.top + w.height // 2]
        cx, cy = (area[0] + area[2]) // 2, (area[1] + area[3]) // 2
        RobloxInputDriver.move_to(cx, cy)                # hovering brings the faded chat back
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
        return found                                     # OCR is only the fallback; picked tabs are what's saved

    def clear_chat(self, w):
        """Focus this Roblox window and type /clear (or /cls) in its chat, then give focus back.
        'In Global': /clear doesn't always work in the 'Here' tab, so click Global → clear → click Here again."""
        import ctypes
        try:
            prev = ctypes.windll.user32.GetForegroundWindow()
            cmd = self.cfg.get("clear_cmd", "/clear") or "/clear"
            with RobloxInputDriver._lock:                # nothing else may click or type until this is done
                if not self.focus_window(w.getHandle()):
                    self.log(f"/clear skipped for window {self.window_number(w)}: Windows wouldn't switch to it.")
                    return
                time.sleep(0.3)                          # let Roblox take the keyboard
                tabs = {}
                if self.cfg.get("clear_in_global", True):
                    tabs = self.find_chat_tabs(w)
                    if "global" in tabs:
                        RobloxInputDriver.click_at(*tabs["global"], duration=0.05)
                        time.sleep(0.35)
                    else:
                        self.log(f"Window {self.window_number(w)}: couldn't find the Global tab - clearing in the current tab.")
                self._type_char("/")                     # opens the chat box (Shift+: on AZERTY)
                time.sleep(0.3)
                # Sometimes that opening "/" also lands in the box (-> "//clear"), so empty it first
                self._select_all()
                time.sleep(0.05)
                self._tap("backspace")
                time.sleep(0.1)
                for ch in cmd:
                    self._type_char(ch)                  # layout-aware, so it's "/clear" on AZERTY too
                    time.sleep(0.03)
                time.sleep(0.25)                         # let the text box catch up before sending
                self._tap("enter", hold=0.1)             # a quick tap gets missed by Roblox's chat
                time.sleep(0.3)
                if "global" in tabs and "here" in tabs:
                    RobloxInputDriver.click_at(*tabs["here"], duration=0.05)   # back to 'Here'
                    time.sleep(0.25)
                self.log(f"Chat cleared ({cmd}{' in Global' if 'global' in tabs else ''}) in window {self.window_number(w)}.")
            if prev and prev != w.getHandle():
                self.focus_window(prev, timeout=0.5)     # hand focus back (best effort)
        except Exception as e:
            self.log(f"/clear failed: {e}")

    # ---------- extras: recent list, unreadable chat, test ----------
    def note(self, name, win_no, what):
        self.recent.append((time.time(), name, win_no, what))
        del self.recent[:-30]

    def _check_unreadable(self, key, win_no, post):
        """Warn once when a window's chat has had no readable text for a while (moved / closed chat)."""
        mins = float(self.cfg.get("unreadable_warn", 5) or 0)
        first = self._readable_at.setdefault(key, time.time())
        if mins <= 0 or key in self._warned or time.time() - first < mins * 60:
            return
        self._warned.add(key)
        msg = (f"Can't read the chat in window {win_no} for {int(mins)} min - events there are being missed. "
               f"Is the chat closed, covered or moved? Set its Chat area again on the Events page.")
        self.log("WARNING: " + msg)
        self.note("(chat unreadable)", win_no, "warning")
        if post:
            self.post("[Event Notifier] " + msg)

    def test_event(self, ev):
        """Test one event. If its words are in a window's chat RIGHT NOW, that real line is used (proves the
        reading works too); otherwise a test message is posted with the same text and pings.
        Returns a short result for the page."""
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

    # ---------- loop ----------
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
        """One pass over every Roblox window. Returns [(event, window)] that were new.
        Holds the shared input lock for the WHOLE check (reads, posts, /clear), so a running
        Skill Macro rotation waits until it's completely done instead of pressing keys in between."""
        with RobloxInputDriver._lock:
            return self._scan_once(post)

    def _scan_once(self, post=True):
        found = []
        wins = roblox_windows()
        for win_no, w in enumerate(wins, start=1):
            key = w.getHandle()
            lines = self.read_lines(w, win_no)
            self.last_lines = lines
            if self.last_raw_lines == 0:
                # Nothing readable (chat faded, covered, or not drawn): keep what we knew.
                # Treating it as "0 events" would make every old line look new on the next check.
                if len(wins) > 1:
                    self.log(f"Window {win_no}: chat not readable this check")
                self._check_unreadable(key, win_no, post)
                continue
            self._readable_at[key] = time.time()
            self._warned.discard(key)
            counts = self.count_events(lines)
            for ev in self.cfg["events"]:
                n, prev = counts.get(ev["name"], 0), self._counts.get((key, ev["name"]))
                self._counts[(key, ev["name"])] = n
                if prev is None:
                    prev = 0                              # first look: events already in chat count too
                if n > prev and ev.get("enabled", True):
                    found.append((ev, w, win_no))
        if len(wins) > 1:
            self.log("Checked " + ", ".join(f"window {i}" for i in range(1, len(wins) + 1)) +
                     (": " + ", ".join(f"{ev['name']} (window {n})" for ev, _, n in found) if found else ": nothing new"))
        new = []
        for ev, w, win_no in found:
            # The cooldown counts per window: each window can post the same event on its own
            key = (ev["name"], w.getHandle())
            if time.time() - self._last_post.get(key, 0) < float(self.cfg.get("cooldown", 120)):
                continue
            self._last_post[key] = time.time()
            new.append((ev, w))
            msg = self.format_message(ev, win_no)
            if post and self.post(msg):
                self.log(f"Posted: {msg}")
                self.note(ev["name"], win_no, "posted")
            elif post:
                self.log(f"Detected {ev['name']} (not posted)")
                self.note(ev["name"], win_no, "NOT posted: " + (getattr(self, "last_post_error", "") or "?"))
        if post and new and self.cfg.get("sound_on_alert", False):
            from utils import play_sound
            play_sound("event")                          # once per check, however many events were new
        if post and new and self.cfg.get("clear_chat"):
            for w in {id(w): w for _, w in new}.values():
                self.clear_chat(w)
                time.sleep(0.4)
                self.read_lines(w, self.window_number(w))
                if self.last_raw_lines == 0:             # confirmed empty: start counting from 0 again
                    for ev in self.cfg["events"]:
                        self._counts[(w.getHandle(), ev["name"])] = 0
        return new

    # ---------- pausing for Mining / Library ----------
    # Those macros walk and click; a check moves the mouse, switches windows and types /clear.
    # So while one runs, timed checks pause and the macro calls checkpoint() between rounds instead.
    _holders = set()
    _scan_lock = threading.Lock()

    def hold(self, who):
        """A macro started: no timed checks until release(), only checkpoint() calls."""
        self._holders.add(who)

    def release(self, who):
        self._holders.discard(who)

    def checkpoint(self, who):
        """Called by a macro at a safe moment (lap done / minigame done): check events now."""
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
                if not self._holders:                    # Mining/Library running: they call checkpoint()
                    with self._scan_lock:
                        self.scan_once()
            except Exception as e:
                self.log(f"Scan error: {e}")
            end = time.time() + float(self.cfg.get("interval", 60))
            while self.running and time.time() < end:
                time.sleep(0.1)


WATCHER = EventWatcher()     # shared by every macro window, keeps running between them

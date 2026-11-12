import mss
import os
import numpy as np
import cv2
import keyboard
import time
import threading
import pywinctl
import sys
import ctypes
import random
from pynput.mouse import Button, Controller as MouseController

IS_WINDOWS = sys.platform.startswith('win')

_cv2_imread, _cv2_imwrite = cv2.imread, cv2.imwrite


def _imread(path, flags=cv2.IMREAD_COLOR):
    try:
        data = np.fromfile(path, dtype=np.uint8)
        return cv2.imdecode(data, flags) if data.size else None
    except Exception:
        return _cv2_imread(path, flags)


def _imwrite(path, img, params=None):
    try:
        ok, buf = cv2.imencode(os.path.splitext(path)[1] or ".png", img, params or [])
        if ok:
            buf.tofile(path)
        return bool(ok)
    except Exception:
        return _cv2_imwrite(path, img, params or [])


if cv2.imread is _cv2_imread:
    cv2.imread, cv2.imwrite = _imread, _imwrite

_HELD_KEYS = set()
_HELD_NAMES = set()
_HELD_LOCK = threading.Lock()

if IS_WINDOWS:
    PUL = ctypes.POINTER(ctypes.c_ulong)

    class MouseInput(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long),
                    ("dy", ctypes.c_long),
                    ("mouseData", ctypes.c_ulong),
                    ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", PUL)]

    class KeyBdInput(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_ushort),
                    ("wScan", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", PUL)]

    class HardwareInput(ctypes.Structure):
        _fields_ = [("uMsg", ctypes.c_ulong),
                    ("wParamL", ctypes.c_short),
                    ("wParamH", ctypes.c_ushort)]

    class Input_I(ctypes.Union):
        _fields_ = [("mi", MouseInput),
                    ("ki", KeyBdInput),
                    ("hi", HardwareInput)]

    class Input(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong),
                    ("ii", Input_I)]

    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1
    _ARROWS = {"up": (0x26, 0x48), "down": (0x28, 0x50), "left": (0x25, 0x4B), "right": (0x27, 0x4D)}

    def scan_key(sc, down, extended=False, vk=0):
        flags = 0x0008 | (0x0001 if extended else 0) | (0 if down else 0x0002)
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.ki = KeyBdInput(vk, sc, flags, 0, ctypes.pointer(extra))
        x = Input(ctypes.c_ulong(INPUT_KEYBOARD), ii_)
        ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))
        with _HELD_LOCK:
            if down:
                _HELD_KEYS.add((sc, bool(extended), vk))
            else:
                _HELD_KEYS.discard((sc, bool(extended), vk))

    def release_all_keys():
        with _HELD_LOCK:
            held = list(_HELD_KEYS)
            names = list(_HELD_NAMES)
        for sc, ext, vk in held:
            try:
                scan_key(sc, False, extended=ext, vk=vk)
            except Exception:
                pass
        for n in names:
            try:
                keyboard.release(n)
            except Exception:
                pass
        with _HELD_LOCK:
            _HELD_NAMES.clear()
        return len(held) + len(names)

    def press_key(name, down):
        if isinstance(name, int):
            scan_key(name, down)
            return
        n = str(name).lower()
        if n in _ARROWS:
            arrow_key(n, down)
            return
        sc = key_scan_code(n)
        if sc:
            scan_key(sc, down)
        elif down:
            keyboard.press(n)
            with _HELD_LOCK:
                _HELD_NAMES.add(n)
        else:
            keyboard.release(n)
            with _HELD_LOCK:
                _HELD_NAMES.discard(n)

    def tap_scan(sc, hold=0.05):
        scan_key(sc, True)
        time.sleep(hold)
        scan_key(sc, False)

    def arrow_key(name, down):
        vk, sc = _ARROWS[name]
        scan_key(sc, down, extended=True, vk=vk)

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_VIRTUALDESK = 0x4000

_QWERTY_SC = {c: i for i, c in enumerate("1234567890-=", start=2)}
_QWERTY_SC.update({c: i for i, c in enumerate("qwertyuiop[]", start=16)})
_QWERTY_SC.update({c: i for i, c in enumerate("asdfghjkl;'`", start=30)})
_QWERTY_SC.update({c: i for i, c in enumerate(r"\zxcvbnm,./", start=43)})
_SPECIAL_SC = {"space": 0x39, "shift": 0x2A, "left shift": 0x2A, "right shift": 0x36, "enter": 0x1C, "esc": 0x01,
               "escape": 0x01, "tab": 0x0F, "ctrl": 0x1D, "left ctrl": 0x1D, "alt": 0x38, "left alt": 0x38,
               "backspace": 0x0E, "f11": 0x57, "f12": 0x58}
_SPECIAL_SC.update({f"f{i}": 0x3A + i for i in range(1, 11)})
_NAME_BY_SC = {v: k for k, v in _QWERTY_SC.items()}
_NAME_BY_SC.update({0x39: "space", 0x2A: "shift", 0x36: "shift"})


def key_scan_code(name):
    n = str(name).lower()
    return _QWERTY_SC.get(n) or _SPECIAL_SC.get(n)


_VK_NAMES = {"space": 0x20, "enter": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09, "backspace": 0x08,
             "shift": 0x10, "left shift": 0xA0, "right shift": 0xA1, "ctrl": 0x11, "left ctrl": 0xA2,
             "right ctrl": 0xA3, "alt": 0x12, "left alt": 0xA4, "right alt": 0xA5, "up": 0x26, "down": 0x28,
             "left": 0x25, "right": 0x27, "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
             "page up": 0x21, "page down": 0x22, "caps lock": 0x14}
_VK_NAMES.update({f"f{i}": 0x6F + i for i in range(1, 25)})


def key_vk(name):
    n = str(name or "").strip().lower()
    if n in _VK_NAMES:
        return _VK_NAMES[n]
    sc = key_scan_code(n)
    try:
        if sc:
            vk = ctypes.windll.user32.MapVirtualKeyW(sc, 1)
            if vk:
                return vk
        if len(n) == 1:
            r = ctypes.windll.user32.VkKeyScanW(ord(n))
            if r != -1:
                return r & 0xFF
    except Exception:
        pass
    return None


def _async_key_state(vk):
    return ctypes.windll.user32.GetAsyncKeyState(vk)


def key_down(name):
    vk = key_vk(name)
    if vk is None:
        try:
            return keyboard.is_pressed(name)
        except Exception:
            return False
    try:
        return bool(_async_key_state(vk) & 0x8000)
    except Exception:
        return False


KEY_BACKUP = {"fired": 0}
_KW_LOCK = threading.Lock()
_KW = []
_KW_THREAD = [None]
_KW_POLL = 0.025


def _kw_loop():
    from types import SimpleNamespace
    while True:
        time.sleep(_KW_POLL)
        with _KW_LOCK:
            entries = list(_KW)
        now = time.time()
        for en in entries:
            try:
                down = bool(_async_key_state(en["vk"]) & 0x8000)
            except Exception:
                continue
            if down and not en["down"]:
                en["down"], en["pressed_at"], en["pending"] = True, now, True
            elif not down:
                en["down"] = False
                en["armed"] = True
            if en["pending"] and now - en["pressed_at"] >= 0.15:
                en["pending"] = False
                if en["last_hook"] < en["pressed_at"] - 0.3:
                    en["backup_fired"] = now
                    KEY_BACKUP["fired"] += 1
                    if KEY_BACKUP["fired"] == 1:
                        print("Keys: the keyboard hook missed a press - the backup key check is handling it.")
                    try:
                        en["callback"](SimpleNamespace(name=en["name"], event_type="down", backup=True,
                                                       scan_code=key_scan_code(en["name"]) or 0))
                    except Exception as e:
                        print(f"Key backup ({en['name']}): {e}")


def on_key(name, callback, suppress=False):
    name = str(name).strip().lower()
    vk = key_vk(name)
    held = False
    if vk:
        try:
            held = bool(_async_key_state(vk) & 0x8000)
        except Exception:
            held = False
    en = {"name": name, "vk": vk, "callback": callback, "down": held, "pending": False,
          "pressed_at": 0.0, "last_hook": 0.0, "backup_fired": 0.0, "armed": not held}

    def hooked(e):
        now = time.time()
        en["last_hook"] = now
        if not en["armed"]:
            if en["vk"] and _async_key_state(en["vk"]) & 0x8000:
                return
            en["armed"] = True
        handled = en["backup_fired"] >= en["pressed_at"] > 0
        if handled and (en["down"] or now - en["backup_fired"] < 0.3
                        or getattr(e, "time", now) <= en["backup_fired"] + 0.05):
            return
        callback(e)
    en["hooked"] = hooked
    en["hook"] = keyboard.on_press_key(name, hooked, suppress=suppress)
    if en["vk"]:
        with _KW_LOCK:
            _KW.append(en)
            if _KW_THREAD[0] is None or not _KW_THREAD[0].is_alive():
                _KW_THREAD[0] = threading.Thread(target=_kw_loop, daemon=True)
                _KW_THREAD[0].start()
    return en


def remove_key(handle):
    try:
        keyboard.unhook(handle["hook"])
    except Exception:
        pass
    with _KW_LOCK:
        _KW[:] = [x for x in _KW if x is not handle]


def clear_keys():
    try:
        keyboard.unhook_all()
    except Exception:
        pass
    with _KW_LOCK:
        _KW.clear()


def wait_any_key(stop, callback, skip_modifiers=True):
    from types import SimpleNamespace
    skip = {0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C} if skip_modifiers else set()
    codes = [vk for vk in range(0x08, 0xFF) if vk not in skip and vk not in (0x01, 0x02, 0x04, 0x05, 0x06)]

    def run():
        u = ctypes.windll.user32
        was = {vk: bool(_async_key_state(vk) & 0x8000) for vk in codes}
        while not stop.is_set():
            time.sleep(0.02)
            for vk in codes:
                down = bool(_async_key_state(vk) & 0x8000)
                if down and not was[vk]:
                    sc = u.MapVirtualKeyW(vk, 0)
                    buf = ctypes.create_unicode_buffer(32)
                    u.GetKeyNameTextW(sc << 16, buf, 32)
                    name = (buf.value or f"key {vk}").lower()
                    if not stop.is_set():
                        callback(SimpleNamespace(name="esc" if vk == 0x1B else name, scan_code=sc,
                                                 event_type="down", backup=True))
                    return
                was[vk] = down
    threading.Thread(target=run, daemon=True).start()


_MODIFIERS = ((0x11, "ctrl"), (0x10, "shift"), (0x12, "alt"))
_MODIFIER_VKS = {0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C}


def _recorded_name(vk):
    for name, code in _VK_NAMES.items():
        if code == vk:
            return name
    u = ctypes.windll.user32
    sc = u.MapVirtualKeyW(vk, 0)
    if sc in _NAME_BY_SC:
        return _NAME_BY_SC[sc]
    buf = ctypes.create_unicode_buffer(32)
    u.GetKeyNameTextW(sc << 16, buf, 32)
    return (buf.value or f"key {vk}").lower()


def record_keys(done, timeout=10.0):
    codes = [vk for vk in range(0x08, 0xFF) if vk not in _MODIFIER_VKS]

    def run():
        was = {vk: bool(_async_key_state(vk) & 0x8000) for vk in codes}
        held = []
        end = time.time() + timeout
        while time.time() < end:
            time.sleep(0.01)
            now = [name for vk, name in _MODIFIERS if _async_key_state(vk) & 0x8000]
            held += [name for name in now if name not in held]
            for vk in codes:
                down = bool(_async_key_state(vk) & 0x8000)
                if down and not was[vk]:
                    done(None if vk == 0x1B and not now else "+".join(now + [_recorded_name(vk)]))
                    return
                was[vk] = down
            if held and not now:
                done("+".join(held))
                return
        done(None)
    threading.Thread(target=run, daemon=True).start()


def position_name(ev):
    sc = getattr(ev, "scan_code", None)
    if sc in _NAME_BY_SC and not getattr(ev, "is_keypad", False):
        return _NAME_BY_SC[sc]
    return (ev.name or "").lower()


SOUNDS = {"done": "SystemAsterisk", "event": "SystemExclamation"}


SOUND_TYPES = (".mp3", ".wav", ".wma", ".m4a", ".mp4", ".aac")


def custom_sound(kind):
    try:
        from settings import SpatialSettings, get_base_path
        rel = (SpatialSettings().get("sound_files") or {}).get(kind)
        if rel:
            path = rel if os.path.isabs(rel) else os.path.join(get_base_path(), rel)
            if os.path.exists(path):
                return path
    except Exception:
        pass
    return None


def _mci(cmd):
    buf = ctypes.create_unicode_buffer(256)
    return ctypes.windll.winmm.mciSendStringW(cmd, buf, 255, 0), buf.value


def play_sound(kind="event"):
    path = custom_sound(kind)
    if path and IS_WINDOWS:
        try:
            alias = f"vv_{kind}"
            _mci(f"close {alias}")
            err, _ = _mci(f'open "{path}" type mpegvideo alias {alias}')
            if err == 0:
                _mci(f"play {alias}")
                return
        except Exception:
            pass
    try:
        import winsound
        winsound.PlaySound(SOUNDS.get(kind, "SystemDefault"), winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        try:
            print("\a", end="", flush=True)
        except Exception:
            pass


class RobloxInputDriver:
    _mouse = MouseController()
    _lock = threading.RLock()

    @classmethod
    def move_to(cls, x, y):
        with cls._lock:
            if IS_WINDOWS:
                left = ctypes.windll.user32.GetSystemMetrics(76)                      
                top = ctypes.windll.user32.GetSystemMetrics(77)                       
                width = ctypes.windll.user32.GetSystemMetrics(78)                      
                height = ctypes.windll.user32.GetSystemMetrics(79)                     
                
                if width <= 0:
                    width = ctypes.windll.user32.GetSystemMetrics(0)                            
                if height <= 0:
                    height = ctypes.windll.user32.GetSystemMetrics(1)                             
                
                nx = int((x - left) * 65535 / (width - 1)) if width > 1 else 0
                ny = int((y - top) * 65535 / (height - 1)) if height > 1 else 0
                
                extra = ctypes.c_ulong(0)
                ii_ = Input_I()
                ii_.mi = MouseInput(nx, ny, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, 0, ctypes.pointer(extra))
                move_input = Input(ctypes.c_ulong(INPUT_MOUSE), ii_)
                ctypes.windll.user32.SendInput(1, ctypes.pointer(move_input), ctypes.sizeof(move_input))
            else:
                cls._mouse.position = (int(x), int(y))

    @staticmethod
    def click_delay():
        try:
            from settings import SpatialSettings
            return max(0.0, float(SpatialSettings().get("click_delay", 1.0)))
        except (TypeError, ValueError, Exception):
            return 1.0

    @classmethod
    def glide_click(cls, x, y, settle=None, button='left', duration=0.04, glide=0.25):
        x, y = int(x), int(y)
        settle = cls.click_delay() if settle is None else max(0.0, float(settle))
        with cls._lock:
            cls.glide_to(x, y, glide)
            time.sleep(settle)
            cls.click_at(x, y, duration, button)

    @classmethod
    def glide_to(cls, x, y, glide=0.12):
        x, y = int(x), int(y)
        with cls._lock:
            sx, sy = cls._mouse.position
            steps = max(6, int(glide / 0.012))
            for k in range(1, steps + 1):
                t = k / steps
                t = t * (2 - t)
                cls.move_to(int(sx + (x - sx) * t), int(sy + (y - sy) * t))
                time.sleep(glide / steps)
            for dx in (2, -2, 0):
                cls.move_to(x + dx, y)
                time.sleep(0.03)

    @classmethod
    def click_at(cls, x, y, duration=0.03, button='left'):
        with cls._lock:
            if IS_WINDOWS:
                cls.move_to(x, y)
                time.sleep(0.02)
                
                extra = ctypes.c_ulong(0)
                if button == 'left':
                    flags_down = MOUSEEVENTF_LEFTDOWN
                    flags_up = MOUSEEVENTF_LEFTUP
                else:
                    flags_down = MOUSEEVENTF_RIGHTDOWN
                    flags_up = MOUSEEVENTF_RIGHTUP

                ii_down = Input_I()
                ii_down.mi = MouseInput(0, 0, 0, flags_down, 0, ctypes.pointer(extra))
                input_down = Input(ctypes.c_ulong(INPUT_MOUSE), ii_down)
                ctypes.windll.user32.SendInput(1, ctypes.pointer(input_down), ctypes.sizeof(input_down))
                
                time.sleep(duration + random.uniform(0.005, 0.015))
                
                ii_up = Input_I()
                ii_up.mi = MouseInput(0, 0, 0, flags_up, 0, ctypes.pointer(extra))
                input_up = Input(ctypes.c_ulong(INPUT_MOUSE), ii_up)
                ctypes.windll.user32.SendInput(1, ctypes.pointer(input_up), ctypes.sizeof(input_up))
            else:
                cls.move_to(x, y)
                time.sleep(0.015) 
                pynput_button = Button.left if button == 'left' else Button.right
                cls._mouse.press(pynput_button)
                time.sleep(duration)
                cls._mouse.release(pynput_button)

OCR_HELP = ("Text reading (OCR) couldn't start. Install the Microsoft Visual C++ Redistributable (x64): "
            "https://aka.ms/vs/17/release/vc_redist.x64.exe  then restart the macro.")


class _SmallTextReader:
    MIN_SIDE = 120

    def __init__(self, engine):
        self.engine = engine

    _lock = threading.Lock()

    def __call__(self, img, *args, **kwargs):
        if isinstance(img, np.ndarray) and img.ndim >= 2 and 0 < min(img.shape[:2]) < self.MIN_SIDE:
            f = self.MIN_SIDE / min(img.shape[:2])
            big = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
            with self._lock:
                res, elapse = self.engine(big, *args, **kwargs)
            if res:
                res = [[[[p[0] / f, p[1] / f] for p in r[0]]] + list(r[1:]) for r in res]
            return res, elapse
        with self._lock:
            return self.engine(img, *args, **kwargs)


CAPTURE = {"mode": "screen"}


def _not_blank(img):
    return img is not None and img.size > 0 and int(img[::7, ::7, :3].max()) > 0


class _BitmapInfo(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32),
                ("bmiColors", ctypes.c_uint32 * 3)]


def _gdi():
    if getattr(_gdi, "f", None) is None:
        from ctypes import wintypes as w
        u, g = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32")
        sig = ((u.GetWindowRect, w.BOOL, [w.HWND, ctypes.POINTER(w.RECT)]),
               (u.GetWindowDC, w.HDC, [w.HWND]), (u.ReleaseDC, ctypes.c_int, [w.HWND, w.HDC]),
               (u.PrintWindow, w.BOOL, [w.HWND, w.HDC, w.UINT]), (u.IsIconic, w.BOOL, [w.HWND]),
               (g.CreateCompatibleDC, w.HDC, [w.HDC]),
               (g.CreateCompatibleBitmap, w.HBITMAP, [w.HDC, ctypes.c_int, ctypes.c_int]),
               (g.SelectObject, w.HGDIOBJ, [w.HDC, w.HGDIOBJ]), (g.DeleteObject, w.BOOL, [w.HGDIOBJ]),
               (g.DeleteDC, w.BOOL, [w.HDC]),
               (g.GetDIBits, ctypes.c_int, [w.HDC, w.HBITMAP, w.UINT, w.UINT, ctypes.c_void_p, ctypes.c_void_p,
                                            w.UINT]))
        for fn, res, args in sig:
            fn.restype, fn.argtypes = res, args
        _gdi.f = (u, g, w)
    return _gdi.f


def window_shot(hwnd):
    try:
        u, g, w = _gdi()
        r = w.RECT()
        if not u.GetWindowRect(hwnd, ctypes.byref(r)) or u.IsIconic(hwnd):
            return None, None
        wd, ht = r.right - r.left, r.bottom - r.top
        if wd <= 0 or ht <= 0:
            return None, None
        hdc = u.GetWindowDC(hwnd)
        mem = g.CreateCompatibleDC(hdc)
        bmp = g.CreateCompatibleBitmap(hdc, wd, ht)
        old = g.SelectObject(mem, bmp)
        try:
            u.PrintWindow(hwnd, mem, 2)
            bmi = _BitmapInfo(biSize=40, biWidth=wd, biHeight=-ht, biPlanes=1, biBitCount=32, biCompression=0)
            buf = ctypes.create_string_buffer(wd * ht * 4)
            if not g.GetDIBits(mem, bmp, 0, ht, buf, ctypes.byref(bmi), 0):
                return None, None
            img = np.frombuffer(buf, np.uint8).reshape(ht, wd, 4).copy()
            img[:, :, 3] = 255
            return img, (r.left, r.top)
        finally:
            g.SelectObject(mem, old)
            g.DeleteObject(bmp)
            g.DeleteDC(mem)
            u.ReleaseDC(hwnd, hdc)
    except Exception as e:
        print(f"Window picture: {e}")
        return None, None


_RW_CACHE = {"t": 0.0, "list": []}


def _roblox_rects():
    now = time.time()
    if now - _RW_CACHE["t"] > 1.0:
        out = []
        try:
            u, g, w = _gdi()
            for h, _ in roblox_windows():
                r = w.RECT()
                if u.GetWindowRect(h, ctypes.byref(r)):
                    out.append((h, (r.left, r.top, r.right, r.bottom)))
        except Exception:
            pass
        _RW_CACHE["t"], _RW_CACHE["list"] = now, out
    return _RW_CACHE["list"]


def window_region(l, t, r, b):
    best, hit = 0, None
    for h, (wl, wt, wr, wb) in _roblox_rects():
        area = max(0, min(r, wr) - max(l, wl)) * max(0, min(b, wb) - max(t, wt))
        if area > best:
            best, hit = area, h
    if hit is None:
        return None
    img, at = window_shot(hit)
    if img is None:
        return None
    out = np.zeros((max(1, b - t), max(1, r - l), 4), np.uint8)
    out[:, :, 3] = 255
    x1, y1 = max(l, at[0]), max(t, at[1])
    x2, y2 = min(r, at[0] + img.shape[1]), min(b, at[1] + img.shape[0])
    if x2 > x1 and y2 > y1:
        out[y1 - t:y2 - t, x1 - l:x2 - l] = img[y1 - at[1]:y2 - at[1], x1 - at[0]:x2 - at[0]]
    return out


def backup_screen_image(size):
    from PIL import Image
    canvas, any_ = Image.new("RGB", size, (0, 0, 0)), False
    for h, _ in _roblox_rects():
        img, at = window_shot(h)
        if img is not None:
            canvas.paste(Image.fromarray(img[:, :, 2::-1].copy()), at)
            any_ = True
    return canvas if any_ else None


class _ThreadGrabber:
    def __init__(self):
        self.sct = (getattr(mss, "MSS", None) or mss.mss)()

    def __del__(self):
        try:
            self.sct.close()
        except Exception:
            pass


class SpatialUtils:
    ocr_error = ""
    def __init__(self):
        self._thread_local = threading.local()
        self._key_lock = threading.RLock()
        self.ocr_reader = None

    @property
    def sct(self):
        g = getattr(self._thread_local, "grabber", None)
        if g is None:
            g = self._thread_local.grabber = _ThreadGrabber()
        return g.sct

    def _grab(self, monitor):
        l, t = int(monitor["left"]), int(monitor["top"])
        r, b = l + int(monitor["width"]), t + int(monitor["height"])
        if CAPTURE["mode"] == "window":
            img = window_region(l, t, r, b)
            if _not_blank(img):
                return img
        try:
            img, err = np.array(self.sct.grab(monitor)), None
        except Exception as e:
            img, err = None, e
        if _not_blank(img):
            return img
        alt = window_region(l, t, r, b)
        if _not_blank(alt):
            if CAPTURE["mode"] != "window":
                CAPTURE["mode"] = "window"
                print("Screenshots: the normal screen copy came back black - using the backup "
                      "(Windows draws the Roblox window) from now on.")
            return alt
        if img is None:
            if alt is not None:
                return alt
            raise err
        return img

    _shared_ocr = None
    _ocr_lock = threading.Lock()

    @classmethod
    def load_ocr(cls):
        with cls._ocr_lock:
            if cls._shared_ocr is None:
                try:
                    from rapidocr_onnxruntime import RapidOCR
                    try:
                        cls._shared_ocr = _SmallTextReader(RapidOCR(det_model_path=None, det_limit_type="max",
                                                                    det_limit_side_len=2000, use_angle_cls=False))
                    except Exception:
                        cls._shared_ocr = _SmallTextReader(RapidOCR())
                    print("RapidOCR initialized")
                except Exception as e:
                    print(f"OCR (RapidOCR) Initialization error: {e}")
                    SpatialUtils.ocr_error = OCR_HELP
                    cls._shared_ocr = False
        return cls._shared_ocr

    _ocr_tested = None

    @classmethod
    def ocr_works(cls):
        if cls._ocr_tested is not None:
            return cls._ocr_tested
        reader = cls.load_ocr()
        ok = False
        if reader:
            try:
                img = np.full((60, 360, 3), 30, np.uint8)
                cv2.putText(img, "Clover Training", (12, 42), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
                res, _ = reader(img)
                text = " ".join(r[1] for r in (res or [])).lower()
                ok = "clover" in text or "training" in text
                if not ok:
                    SpatialUtils.ocr_error = f"Text reading started but read the test words as '{text}'."
            except Exception as e:
                SpatialUtils.ocr_error = f"{OCR_HELP} (error: {e})"
        cls._ocr_tested = ok
        return ok

    @classmethod
    def ocr_read_screen(cls, img):
        import re
        reader = cls.load_ocr()
        if not reader or img is None or not img.size:
            return False, [], []
        try:
            res, _ = reader(img)
        except Exception:
            return False, [], []
        lines = [t[1].strip() for t in (res or [])]
        worded = [ln for ln in lines if re.search(r"[A-Za-z]{4,}", ln)]
        if len(worded) >= 3:
            cls._ocr_tested = True
        return len(worded) >= 3, worded, lines

    @classmethod
    def preload_ocr(cls):
        threading.Thread(target=cls.ocr_works, daemon=True).start()

    def _init_ocr(self):
        if self.ocr_reader is None:
            self.ocr_reader = SpatialUtils.load_ocr()

    def get_text_from_region(self, region, upscale=2):
        self._init_ocr()
        if not self.ocr_reader:
            return []
            
        img = self.capture_screen(region)
        
        if upscale > 1:
            h, w = img.shape[:2]
            img = cv2.resize(img, (w * upscale, h * upscale), interpolation=cv2.INTER_CUBIC)
        
        try:
            
            results, elapse = self.ocr_reader(img)
            
            final_results = []
            if results:
                for res in results:
                    bbox, text, conf = res
                    
                    if upscale > 1:
                        bbox = [[p[0] / upscale, p[1] / upscale] for p in bbox]
                    final_results.append((bbox, text, float(conf)))
            
            return final_results
        except Exception as e:
            print(f"RapidOCR Error: {e}")
            return []

    def capture_screen(self, region=None):
        if region:
            
            monitor = {
                "top": int(region[1]), 
                "left": int(region[0]), 
                "width": int(region[2] - region[0]), 
                "height": int(region[3] - region[1])
            }
        else:
            try:
                
                windows = [w for w in pywinctl.getAllWindows() if is_roblox_title(w.title)]
                if windows:
                    
                    active = pywinctl.getActiveWindow()
                    target = active if active and is_roblox_title(active.title) else windows[0]
                    
                    monitor = {
                        "top": target.top,
                        "left": target.left,
                        "width": target.width,
                        "height": target.height
                    }
                else:
                    monitor = self.sct.monitors[1]
            except Exception:
                monitor = self.sct.monitors[1]
        
        img = self._grab(monitor)
        
        return cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)

    def capture_screen_bgr(self, region=None):
        if region:
            from overlay import take_frozen
            frozen = take_frozen(region)
            if frozen is not None:
                return frozen
            monitor = {
                "top": int(region[1]), 
                "left": int(region[0]), 
                "width": int(region[2] - region[0]), 
                "height": int(region[3] - region[1])
            }
        else:
            try:
                windows = [w for w in pywinctl.getAllWindows() if is_roblox_title(w.title)]
                if windows:
                    active = pywinctl.getActiveWindow()
                    target = active if active and is_roblox_title(active.title) else windows[0]
                    monitor = {
                        "top": target.top,
                        "left": target.left,
                        "width": target.width,
                        "height": target.height
                    }
                else:
                    monitor = self.sct.monitors[1]
            except Exception:
                monitor = self.sct.monitors[1]
        
        img = self._grab(monitor)
        
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def pixel_search_region(self, region, target_color, tolerance=10, img=None, is_bgr=False):
        if img is None:
            img = self.capture_screen(region)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        else:
            if is_bgr:
                img_bgr = img
            else:
                img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        r, g, b = self._parse_target_color(target_color)
        lower = np.array([max(0, b - tolerance), max(0, g - tolerance), max(0, r - tolerance)])
        upper = np.array([min(255, b + tolerance), min(255, g + tolerance), min(255, r + tolerance)])
        
        mask = cv2.inRange(img_bgr, lower, upper)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        centers = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= 2: 
                cx, cy, w, h = cv2.boundingRect(contour)
                centers.append((region[0] + cx + w // 2, region[1] + cy + h // 2))
                
        if centers:
            centers.sort(key=lambda p: p[1])
            return centers
        return None

    def pixel_search_existing_frame(self, img_rgb, region, target_color, tolerance=15):
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        
        r, g, b = self._parse_target_color(target_color)
        lower = np.array([max(0, b - tolerance), max(0, g - tolerance), max(0, r - tolerance)], dtype="uint8")
        upper = np.array([min(255, b + tolerance), min(255, g + tolerance), min(255, r + tolerance)], dtype="uint8")
        
        mask = cv2.inRange(img_bgr, lower, upper)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            if cv2.contourArea(contour) > 10: 
                cx, cy, w, h = cv2.boundingRect(contour)
                center_x = cx + (w // 2)
                center_y = cy + (h // 2)
                return (region[0] + center_x, region[1] + center_y)
                
        return None

    def image_search(self, image_path, region=None, threshold=0.8):
        try:
            template = cv2.imread(image_path)
            if template is None:
                return None
            template = cv2.cvtColor(template, cv2.COLOR_BGR2RGB)
            th, tw = template.shape[:2]

            img = self.capture_screen(region)
            
            res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val >= threshold:
                center_x = max_loc[0] + tw // 2
                center_y = max_loc[1] + th // 2
                
                if region:
                    return (region[0] + center_x, region[1] + center_y)
                return (center_x, center_y)
        except Exception as e:
            print(f"Image search error: {e}")
        return None

    def mouse_move(self, x, y):
        RobloxInputDriver.move_to(x, y)

    def send_key(self, key, duration=0.05):
        with self._key_lock:
            press_key(key, True)
            time.sleep(duration)
            press_key(key, False)

    def find_color_hsv_x(self, region, target_rgb, hue_tol=10, sat_min=50, val_min=50, min_area=0):
        img_rgb = self.capture_screen(region)
        img_hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
        
        target_img = np.uint8([[list(target_rgb)]])
        target_hsv = cv2.cvtColor(target_img, cv2.COLOR_RGB2HSV)[0][0]
        
        target_hue = target_hsv[0]
        
        lower = np.array([max(0, target_hue - hue_tol), sat_min, val_min])
        upper = np.array([min(179, target_hue + hue_tol), 255, 255])
        
        mask = cv2.inRange(img_hsv, lower, upper)
        
        if min_area > 0:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            valid_mask = np.zeros_like(mask)
            for cnt in contours:
                if cv2.contourArea(cnt) >= min_area:
                    cv2.drawContours(valid_mask, [cnt], -1, 255, -1)
            mask = valid_mask

        coords = np.column_stack(np.where(mask > 0))
        if len(coords) > 0:
            avg_x = np.mean(coords[:, 1])
            return region[0] + int(avg_x)
        return None

    def _parse_target_color(self, target_color):
        if isinstance(target_color, str):
            target_color = target_color.lstrip('#')
            if len(target_color) == 6:
                return tuple(int(target_color[i:i+2], 16) for i in (0, 2, 4))
        return target_color

def _process_elevated(pid):
    import ctypes
    from ctypes import wintypes
    k32, adv = ctypes.windll.kernel32, ctypes.windll.advapi32
    h = k32.OpenProcess(0x1000, False, int(pid))
    if not h:
        return None
    try:
        tok = wintypes.HANDLE()
        if not adv.OpenProcessToken(h, 0x0008, ctypes.byref(tok)):
            return True
        try:
            val, size = wintypes.DWORD(), wintypes.DWORD()
            if adv.GetTokenInformation(tok, 20, ctypes.byref(val), ctypes.sizeof(val), ctypes.byref(size)):
                return bool(val.value)
            return None
        finally:
            k32.CloseHandle(tok)
    finally:
        k32.CloseHandle(h)


def roblox_admin_problem():
    try:
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin():
            return ""
        import pywinctl
        for w in pywinctl.getAllWindows():
            if is_roblox_title(w.title):
                pid = w.getPID() if hasattr(w, "getPID") else None
                if pid and _process_elevated(pid):
                    return ("Roblox is running as ADMINISTRATOR, so Windows blocks the macro's key presses "
                            "and clicks.\n\nClose Roblox and open it normally (not 'Run as administrator', "
                            "and untick 'Run this program as an administrator' in its Properties > "
                            "Compatibility), then start the macro again.")
        return ""
    except Exception:
        return ""


def is_roblox_title(title):
    return (title or "").strip() == "Roblox"


def _top_window_at(x, y):
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    h = u.WindowFromPoint(wintypes.POINT(int(x), int(y)))
    if not h:
        return 0, ""
    h = u.GetAncestor(h, 2) or h
    buf = ctypes.create_unicode_buffer(256)
    u.GetWindowTextW(h, buf, 256)
    return h, buf.value


def roblox_window_at(x, y):
    try:
        h, title = _top_window_at(x, y)
        return h if is_roblox_title(title) else 0
    except Exception:
        return -1


def window_center(hwnd):
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    box, corner = wintypes.RECT(), wintypes.POINT(0, 0)
    if not hwnd or not u.GetClientRect(wintypes.HWND(hwnd), ctypes.byref(box)) or box.right < 2 or box.bottom < 2 \
            or not u.ClientToScreen(wintypes.HWND(hwnd), ctypes.byref(corner)):
        return None
    return corner.x + box.right // 2, corner.y + box.bottom // 2


def roblox_windows():
    try:
        import pywinctl
        out = []
        for w in pywinctl.getAllWindows():
            if is_roblox_title(w.title) and getattr(w, "isVisible", True):
                h = w.getHandle() if hasattr(w, "getHandle") else None
                if h:
                    out.append((int(h), w.title))
        return out
    except Exception:
        return []


def last_roblox():
    import ctypes
    from ctypes import wintypes
    wins = {h for h, _ in roblox_windows()}
    stack = []
    walk = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(lambda h, _: stack.append(h) or True)
    ctypes.windll.user32.EnumWindows(walk, 0)
    return next((h for h in stack if h in wins), 0)


def go_to_roblox(log=print):
    hwnd = last_roblox()
    if not hwnd or not focus_roblox(hwnd):
        log("Couldn't switch to Roblox - is it open?")
        return 0
    n = len(roblox_windows())
    if n > 1:
        log(f"{n} Roblox windows are open - using the one you clicked last.")
    time.sleep(0.5)
    return hwnd


def focus_roblox(prefer=0):
    import ctypes
    u = ctypes.windll.user32
    wins = [h for h, _ in roblox_windows()]
    if not wins:
        return False
    fg = u.GetForegroundWindow()
    if fg in wins and (not prefer or fg == prefer):
        return True
    target = prefer if prefer in wins else last_roblox() or wins[0]
    try:
        from logic_events import EventWatcher
        return bool(EventWatcher.focus_window(target, timeout=1.0))
    except Exception:
        return False


HOTKEYS_ROBLOX_ONLY = False


def on_hotkey(key, callback, debounce=0.4, always=None):
    key = str(key or "").strip().lower()
    if not key:
        return None
    *mods, main = [k.strip() for k in key.split("+")]
    last = [0.0]

    def fire(_e):
        if any(not key_down(m) for m in mods):
            return
        if HOTKEYS_ROBLOX_ONLY and not foreground_roblox() and not (always and always()):
            return
        if time.time() - last[0] > debounce:
            last[0] = time.time()
            callback()
    return on_key(main, fire)


def foreground_roblox():
    import ctypes
    fg = ctypes.windll.user32.GetForegroundWindow()
    return fg if fg in [h for h, _ in roblox_windows()] else 0


def check_capture():
    _RW_CACHE["t"] = 0.0
    rects = _roblox_rects()
    out = {"roblox": bool(rects), "screen_ok": False, "backup_ok": False, "mode": CAPTURE["mode"]}
    if not rects:
        return out
    _, (l, t, r, b) = rects[0]
    try:
        with (getattr(mss, "MSS", None) or mss.mss)() as sct:
            out["screen_ok"] = _not_blank(np.array(sct.grab({"left": l, "top": t, "width": r - l, "height": b - t})))
    except Exception:
        pass
    out["backup_ok"] = _not_blank(window_region(l, t, r, b))
    if not out["screen_ok"] and out["backup_ok"]:
        CAPTURE["mode"] = out["mode"] = "window"
    return out


def check_keys(timeout=6.0):
    got = {"hook": False, "backup": False}
    first = []

    def hooked(ev):
        if ev.event_type == "down":
            got["hook"] = True
            first.append(time.time())
    try:
        h = keyboard.hook(hooked)
    except Exception:
        h = None
    codes = [vk for vk in range(0x08, 0xFF) if vk not in (0x01, 0x02, 0x04, 0x05, 0x06)]
    was = {vk: bool(_async_key_state(vk) & 0x8000) for vk in codes}
    end = time.time() + timeout
    try:
        while time.time() < end:
            time.sleep(0.02)
            for vk in codes:
                down = bool(_async_key_state(vk) & 0x8000)
                if down and not was[vk]:
                    got["backup"] = True
                    first.append(time.time())
                was[vk] = down
            if first and time.time() - first[0] > 0.5:
                break
    finally:
        if h is not None:
            try:
                keyboard.unhook(h)
            except Exception:
                pass
    return {**got, "pressed": bool(first), "fired": KEY_BACKUP["fired"]}

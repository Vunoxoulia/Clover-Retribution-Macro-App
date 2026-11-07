import atexit
import json
import os
import shutil
import sys
import threading

_SAVE_LOCK = threading.RLock()
SAVE_DELAY = 0.5
_PENDING = {}
_FLUSHERS = {}


def flush_all():
    with _SAVE_LOCK:
        waiting = [f for f, t in _PENDING.items() if t is not None]
        for f in waiting:
            _PENDING.pop(f).cancel()
    for f in waiting:
        try:
            _FLUSHERS[f]()
        except Exception as e:
            print(f"Error saving settings: {e}")


atexit.register(flush_all)


SETTINGS_VERSION = 1


def fill_defaults(s):
    hk = s.setdefault("hotkeys", {})
    for action, key in (("test_path", "f3"), ("test_find", "f4"), ("test_full", "f5"),
                        ("test_open", "f7"), ("record", "f9")):
        hk.setdefault(action, key)


def _migrate_1(s):
    hk = s.setdefault("hotkeys", {})
    if hk.get("stop") == "f7":
        hk.pop("stop")
        hk["test_open"] = "f7"


MIGRATIONS = {1: _migrate_1}


def get_app_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_root_path():
    return os.path.dirname(get_app_path())


USER_DATA_NAMES = ("settings.json", "settings.json.bak", "settings.json.broken", "settings.json.tmp",
                   "links_cache.txt", "ok_template.png", "event_roles_import.json",
                   "routes", "routes_library", "smart_templates", "library_templates", "sounds",
                   "tundra_route.json", "tundra_home.png", "tundra_snapshots")


def get_base_path():
    d = os.path.join(get_root_path(), "data")
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    if not getattr(get_base_path, "_migrated", False):
        get_base_path._migrated = True
        migrate_old_data(get_root_path(), d)
    return d


def migrate_old_data(root, data):
    import shutil
    for name in USER_DATA_NAMES:
        old, new = os.path.join(root, name), os.path.join(data, name)
        if not os.path.exists(old):
            continue
        try:
            if not os.path.exists(new):
                shutil.move(old, new)
            elif os.path.isdir(old) and os.path.isdir(new):
                for r, _, files in os.walk(old):
                    rel = os.path.relpath(r, old)
                    os.makedirs(os.path.join(new, rel), exist_ok=True)
                    for f in files:
                        t = os.path.join(new, rel, f)
                        if not os.path.exists(t):
                            shutil.move(os.path.join(r, f), t)
                shutil.rmtree(old, ignore_errors=True)
        except Exception as e:
            print(f"Couldn't move {name} into data/: {e}")

_SHARED = {}


class SpatialSettings:
    def __init__(self, filename="settings.json"):
        self.base_path = get_base_path()
        self.filename = os.path.join(self.base_path, filename)
        if self.filename in _SHARED:
            self.settings = _SHARED[self.filename]
            return
        self.settings = {
            "settings_version": SETTINGS_VERSION,
            "use_ocr": False,
            "move_names": ["", "", ""],
            "clover_colors": {
                "bronze": (198, 62, 37),
                "silver": (164, 178, 178),
                "gold": (255, 180, 51)
            },
            "color_tolerance": 25,
            "hotkeys": {
                "start": "f6",
                "test_btn": "f1",
                "test_color": "f2",
                "test_movement": "f2",
                "test_path": "f3",
                "test_find": "f4",
                "test_full": "f5",
                "test_open": "f7",
                "record": "f9"
            },
            "positions": {
                "clover_training": [0, 0],
                "skip_button": [0, 0],
                "move_1": [0, 0],
                "move_2": [0, 0],
                "move_3": [0, 0],
                "anti_hotkey": [0, 0],
                "anti_menu": [0, 0],
                "anti_party": [0, 0]
            },
            "regions": {
                "score": [0, 0, 0, 0],
                "move_menu": [0, 0, 0, 0],
                "quest_region": [0, 0, 0, 0],
                "tundra_detection_region": [0, 0, 0, 0],
                "gold_clover_1": [0, 0, 0, 0],
                "gold_clover_2": [0, 0, 0, 0],
                "gold_clover_3": [0, 0, 0, 0],
                "anti_hotkey": [0, 0, 0, 0],
                "anti_main": [0, 0, 0, 0],
                "anti_party": [0, 0, 0, 0],
                "minigame_bar": [0, 0, 0, 0],
                "ok_button": [0, 0, 0, 0],
                "ok_scan_area": [0, 0, 0, 0],
                "ok_click_pos": [0, 0],
                "fishing_click_pos": [0, 0]
            },
            "bar_color": [95, 153, 98],
            "fish_color": [188, 187, 144],
            "total_gold": 0,
            "move_stats": [0, 0, 0],
            "resolved_move_names": ["", "", ""],
            "resolved_move_positions": [None, None, None],
            "speed_multiplier": 1.0,
            "sprinting_delay": 0.25,
            "active_route": "",
            "home_tolerance": 30,
            "arrival_wait": 1.5,
            "max_node_misses": 2,
            "dialogue_jump_delay": 0.3,
            "dialogue_retry_delay": 0.5,
            "node_timers": {
                "start": {"mine_hold": 0.0, "mine_wait": 0.0, "steps": [
                    {"key": "a", "seconds": 0.15}, {"key": "w", "seconds": 1.0}, {"key": "a", "seconds": 0.15}]},
                "1": {"mine_hold": 3.0, "mine_wait": 1.75, "steps": [
                    {"key": "d", "seconds": 0.23}, {"key": "s", "seconds": 0.0}]},
                "2": {"mine_hold": 3.0, "mine_wait": 1.75, "steps": [
                    {"key": "d", "seconds": 4.0}]},
                "3": {"mine_hold": 3.0, "mine_wait": 1.75, "steps": [
                    {"key": "s", "seconds": 0.25}, {"key": "d", "seconds": 0.55}]},
                "4": {"mine_hold": 3.0, "mine_wait": 1.75, "steps": [
                    {"key": "w", "seconds": 1.5}, {"key": "d", "seconds": 0.3}]},
                "5": {"mine_hold": 3.0, "mine_wait": 1.75, "steps": [
                    {"key": "d", "seconds": 12.0}]},
                "6": {"mine_hold": 3.0, "mine_wait": 1.75, "steps": [
                    {"key": "d", "seconds": 1.0}, {"key": "w", "seconds": 0.4}, {"key": "d", "seconds": 0.1}]},
                "7": {"mine_hold": 3.0, "mine_wait": 1.75, "steps": [
                    {"key": "a", "seconds": 0.2}, {"key": "w", "seconds": 1.0}]},
                "8": {"mine_hold": 3.0, "mine_wait": 1.75, "steps": [
                    {"key": "a", "seconds": 1.25}]},
                "9": {"mine_hold": 3.0, "mine_wait": 1.75, "steps": [
                    {"key": "a", "seconds": 0.5}, {"key": "s", "seconds": 2.5},
                    {"key": "a", "seconds": 1.55}, {"key": "s", "seconds": 3.6}]},
                "10": {"mine_hold": 3.0, "mine_wait": 1.75, "steps": [
                    {"key": "a", "seconds": 0.70}, {"key": "s", "seconds": 2.4}, {"key": "d", "seconds": 0.35}]},
                "11": {"mine_hold": 3.0, "mine_wait": 1.75, "steps": [
                    {"key": "a", "seconds": 1.35}, {"key": "s", "seconds": 2.0}]},
                "return": {"mine_hold": 0.0, "mine_wait": 0.0, "steps": [
                    {"key": "w", "seconds": 5.0}, {"key": "a", "seconds": 7.0},
                    {"key": "w", "seconds": 3.0}, {"key": "a", "seconds": 7.0},
                    {"key": "a", "seconds": 0.15}, {"key": "w", "seconds": 1.0}, {"key": "a", "seconds": 0.15}]}
            }
        }
        _SHARED[self.filename] = self.settings
        self.load()

    def _read(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load(self):
        if not os.path.exists(self.filename):
            if not os.path.exists(self.filename + ".bak"):
                return
            try:
                shutil.copy2(self.filename + ".bak", self.filename)
                print("settings.json was missing - restored it from settings.json.bak.")
            except OSError:
                pass
        try:
            data = self._read(self.filename if os.path.exists(self.filename) else self.filename + ".bak")
        except Exception as e:
            print(f"Error loading settings: {e}")
            data = None
            try:
                os.replace(self.filename, self.filename + ".broken")
            except OSError:
                pass
            if os.path.exists(self.filename + ".bak"):
                try:
                    data = self._read(self.filename + ".bak")
                    print("Loaded the settings backup (settings.json.bak) instead.")
                except Exception as e2:
                    print(f"Backup couldn't be read either: {e2}")
        if data:
            self.settings.update(data)
            self._migrate(int(data.get("settings_version") or 0))
        fill_defaults(self.settings)

    def _migrate(self, from_version):
        if from_version >= SETTINGS_VERSION:
            return
        try:
            if os.path.exists(self.filename):
                shutil.copy2(self.filename, f"{self.filename}.v{from_version}.bak")
        except OSError:
            pass
        for v in range(from_version + 1, SETTINGS_VERSION + 1):
            step = MIGRATIONS.get(v)
            if step:
                try:
                    step(self.settings)
                except Exception as e:
                    print(f"Settings upgrade step {v} failed: {e}")
        self.settings["settings_version"] = SETTINGS_VERSION
        print(f"Settings upgraded from version {from_version} to {SETTINGS_VERSION}.")
        self.save()

    def save(self):
        with _SAVE_LOCK:
            t = _PENDING.get(self.filename)
            if t is not None and t.is_alive():
                return
            t = threading.Timer(SAVE_DELAY, self._write)
            t.daemon = True
            _PENDING[self.filename] = t
            _FLUSHERS[self.filename] = self._write
            t.start()

    def flush(self):
        with _SAVE_LOCK:
            t = _PENDING.pop(self.filename, None)
            if t is None:
                return
            t.cancel()
        self._write()

    def _write(self):
        with _SAVE_LOCK:
            _PENDING.pop(self.filename, None)
            tmp = f"{self.filename}.{threading.get_ident()}.tmp"
            try:
                text = None
                for _ in range(3):
                    try:
                        text = json.dumps(self.settings, indent=4)
                        break
                    except RuntimeError:
                        continue
                if text is None:
                    return
                with open(tmp, 'w', encoding='utf-8') as f:
                    f.write(text)
                if os.path.exists(self.filename):
                    try:
                        shutil.copy2(self.filename, self.filename + ".bak")
                    except OSError:
                        pass
                os.replace(tmp, self.filename)
            except Exception as e:
                print(f"Error saving settings: {e}")
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()
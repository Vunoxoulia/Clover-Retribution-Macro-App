import json
import os
import sys

# Folder layout (only the launcher sits in the main folder):
#   Windows_Launcher.bat
#   app/   the program (code, icon, built-in routes, links.txt)  - replaced by updates
#   data/  YOUR stuff (settings, routes, pictures, sounds)       - never touched by updates
#   docs/  patch notes and guides

def get_app_path():
    """The program folder (app/)."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_root_path():
    """The main folder - the one with Windows_Launcher.bat."""
    return os.path.dirname(get_app_path())


# Everything the user saved. Older versions kept these next to the launcher; they're moved into data/.
USER_DATA_NAMES = ("settings.json", "settings.json.bak", "settings.json.broken", "settings.json.tmp",
                   "links_cache.txt", "ok_template.png", "event_roles_import.json",
                   "routes", "routes_library", "smart_templates", "library_templates", "sounds",
                   "tundra_route.json", "tundra_home.png", "tundra_snapshots")


def get_base_path():
    """Where the user's data lives (data/). Made on first use; old data from the main folder is moved in."""
    d = os.path.join(get_root_path(), "data")
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    if not getattr(get_base_path, "_migrated", False):
        get_base_path._migrated = True
        migrate_old_data(get_root_path(), d)
    return d


def migrate_old_data(root, data):
    """One-time: move the user's files from the main folder (old layout) into data/ - nothing is lost."""
    import shutil
    for name in USER_DATA_NAMES:
        old, new = os.path.join(root, name), os.path.join(data, name)
        if not os.path.exists(old):
            continue
        try:
            if not os.path.exists(new):
                shutil.move(old, new)
            elif os.path.isdir(old) and os.path.isdir(new):
                for r, _, files in os.walk(old):          # merge: only add what data/ doesn't have yet
                    rel = os.path.relpath(r, old)
                    os.makedirs(os.path.join(new, rel), exist_ok=True)
                    for f in files:
                        t = os.path.join(new, rel, f)
                        if not os.path.exists(t):
                            shutil.move(os.path.join(r, f), t)
                shutil.rmtree(old, ignore_errors=True)
        except Exception as e:
            print(f"Couldn't move {name} into data/: {e}")

# Every part of the app (hub, each macro, Skill Macro, Event Notifier) gets the SAME settings dict.
# Before, each had its own copy and saving an older copy wiped newer changes (e.g. Skill Macro loadouts).
_SHARED = {}


class SpatialSettings:
    def __init__(self, filename="settings.json"):
        self.base_path = get_base_path()
        self.filename = os.path.join(self.base_path, filename)
        if self.filename in _SHARED:
            self.settings = _SHARED[self.filename]
            return
        self.settings = {
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
                "stop": "f7",
                "pause": "f8",
                "test_btn": "f1",
                "test_color": "f2",
                "test_movement": "f2",
                "test_path": "f3",
                "test_find": "f4",
                "test_full": "f5"
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
        """Read settings.json into the shared dict (in place, so every part of the app sees it).
        If the file is broken (e.g. the PC shut down mid-save), use the backup instead of starting
        empty - an empty start would overwrite everything on the next save."""
        if not os.path.exists(self.filename):
            return
        try:
            data = self._read(self.filename)
        except Exception as e:
            print(f"Error loading settings: {e}")
            data = None
            try:
                os.replace(self.filename, self.filename + ".broken")      # keep it, don't overwrite it
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
            # hotkeys are replaced as a whole on load: re-add actions added since that file was saved
            self.settings["hotkeys"].setdefault("test_path", "f3")
            self.settings["hotkeys"].setdefault("test_find", "f4")
            self.settings["hotkeys"].setdefault("test_full", "f5")

    def save(self):
        """Write to a temp file, then swap it in: a crash can't leave a half-written settings.json.
        The previous good file is kept as settings.json.bak."""
        tmp = self.filename + ".tmp"
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
            if os.path.exists(self.filename):
                try:
                    os.replace(self.filename, self.filename + ".bak")
                except OSError:
                    pass
            os.replace(tmp, self.filename)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()
import json
import os
import sys

def get_base_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

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
                "refresh": "f5",
                "test_btn": "f1",
                "test_color": "f2",
                "test_movement": "f2",
                "test_path": "f3"
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
            "smart_movement": True,
            "active_route": "",
            "home_tolerance": 30,
            "motion_threshold": 2.5,
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
import json
import os
import sys

def get_base_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

class SpatialSettings:
    def __init__(self, filename="settings.json"):
        self.base_path = get_base_path()
        self.filename = os.path.join(self.base_path, filename)
        self.settings = {
            "use_ocr": False,
            "move_names": ["", "", ""],
            "clover_colors": {
                "bronze": (251, 197, 170),
                "silver": (187, 197, 197),
                "gold": (251, 198, 108)
            },
            "color_tolerance": 25,
            "hotkeys": {
                "start": "f6",
                "stop": "f7",
                "pause": "f8",
                "refresh": "f5",
                "test_btn": "f1",
                "test_color": "f2",
                "test_movement": "f2"
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
            "node_timers": {
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
            }
        }
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    self.settings.update(data)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()
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
                "clover_training": [0, 0]
            },
            "regions": {
                "score": [0, 0, 0, 0],
                "move_menu": [0, 0, 0, 0],
                "gold_clover_1": [0, 0, 0, 0],
                "gold_clover_2": [0, 0, 0, 0],
                "gold_clover_3": [0, 0, 0, 0]
            },
            "total_xp": 0,
            "move_stats": [0, 0, 0]
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

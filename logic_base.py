import threading
import time
import random  
import numpy as np
import math
import keyboard
import pywinctl
from pynput.mouse import Button, Controller as MouseController
from screeninfo import get_monitors
from utils import SpatialUtils

import sys
IS_WINDOWS = sys.platform.startswith('win')

if IS_WINDOWS:
    import ctypes

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
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004

class RobloxInputDriver:
    _mouse = MouseController()

    @classmethod
    def move_to(cls, x, y):
        if IS_WINDOWS:
            width = ctypes.windll.user32.GetSystemMetrics(0)
            height = ctypes.windll.user32.GetSystemMetrics(1)
            
            nx = int(x * 65535 / (width - 1))
            ny = int(y * 65535 / (height - 1))
            
            extra = ctypes.c_ulong(0)
            ii_ = Input_I()
            ii_.mi = MouseInput(nx, ny, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, ctypes.pointer(extra))
            move_input = Input(ctypes.c_ulong(INPUT_MOUSE), ii_)
            ctypes.windll.user32.SendInput(1, ctypes.pointer(move_input), ctypes.sizeof(move_input))
        else:
            cls._mouse.position = (int(x), int(y))

    @classmethod
    def click_at(cls, x, y, duration=0.03):
        if IS_WINDOWS:
            cls.move_to(x, y)
            time.sleep(0.02)
            
            extra = ctypes.c_ulong(0)
            ii_down = Input_I()
            ii_down.mi = MouseInput(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, ctypes.pointer(extra))
            input_down = Input(ctypes.c_ulong(INPUT_MOUSE), ii_down)
            ctypes.windll.user32.SendInput(1, ctypes.pointer(input_down), ctypes.sizeof(input_down))
            
            time.sleep(duration + random.uniform(0.005, 0.015))
            
            ii_up = Input_I()
            ii_up.mi = MouseInput(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, ctypes.pointer(extra))
            input_up = Input(ctypes.c_ulong(INPUT_MOUSE), ii_up)
            ctypes.windll.user32.SendInput(1, ctypes.pointer(input_up), ctypes.sizeof(input_up))
        else:
            cls.move_to(x, y)
            time.sleep(0.015) 
            cls._mouse.press(Button.left)
            time.sleep(duration)
            cls._mouse.release(Button.left)

class BaseLogic:
    def __init__(self, app):
        self.app = app
        self.utils = SpatialUtils()
        self.running = False
        self.paused = False
        self.thread = None
        self._mouse = MouseController()

    def start(self):
        if not self.running:
            self.running = True
            self.paused = False
            self.thread = threading.Thread(target=self.main_loop, daemon=True)
            self.thread.start()
            self.app.log("Macro thread started")

    def stop(self):
        if not self.running:
            return
            
        self.running = False
        self.app.log("Stopping macro...")
        if self.thread:
            self.thread.join(timeout=1.0)
        self.app.log("Macro stopped")

    def wait_for_roblox_focus(self):
        if self.check_focus():
            return True
            
        self.app.log("Waiting for Roblox... (Focus the game!)")
        while self.running:
            if self.check_focus():
                self.app.log("Roblox focus detected!")
                return True
            time.sleep(0.5)
        return False

    def check_focus(self):
        try:
            active_window = pywinctl.getActiveWindow()
            if active_window:
                title = active_window.title
                return "Roblox" in title
        except Exception:
            pass
        return False

    def get_cursor_pos(self):
        return self._mouse.position

    def smooth_move(self, target_x, target_y, duration=0.15):
        try:
            start_x, start_y = self.get_cursor_pos()
        except Exception:
            return  
            
        dx = target_x - start_x
        dy = target_y - start_y
        distance = np.hypot(dx, dy)
        
        if distance == 0:
            return
        
        steps = max(6, int(distance / random.randint(15, 30)))
        sleep_per_step = duration / steps

        for i in range(1, steps + 1):
            if not self.running:
                break
            t = i / steps
            t = t * (2 - t)  
            
            current_x = int(start_x + dx * t)
            current_y = int(start_y + dy * t)
            
            RobloxInputDriver.move_to(current_x, current_y)
            time.sleep(sleep_per_step)
            
        RobloxInputDriver.move_to(target_x, target_y)
        time.sleep(0.015)

    def human_click(self, x, y, duration=0.15):
        self.smooth_move(x, y, duration=duration)
        RobloxInputDriver.click_at(x, y, duration=random.uniform(0.02, 0.04))

    def handle_ok_popup(self):
        """Scans the screen for an 'Ok' button and clicks it if found."""
        try:
            import win32api, win32con
            screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            full_screen = [0, 0, screen_w, screen_h]
            
            results = self.utils.get_text_from_region(full_screen)
            for bbox, text, conf in results:
                if text.strip() == "Ok":
                    cx = int(np.mean([p[0] for p in bbox]))
                    cy = int(np.mean([p[1] for p in bbox]))
                    self.app.log(f"Detected 'Ok' popup at ({cx}, {cy}). Clicking...")
                    
                    old_x, old_y = self.get_cursor_pos()
                    RobloxInputDriver.click_at(cx, cy, duration=0.05)
                    time.sleep(0.1)
                    RobloxInputDriver.move_to(old_x, old_y)
                    return True
        except Exception as e:
            self.app.log(f"Error checking for 'Ok' popup: {e}")
        return False

    def main_loop(self):
        """To be overridden by subclasses"""
        pass

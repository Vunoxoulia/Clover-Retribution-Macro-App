import threading
import time
import win32gui
import win32api  
import win32con  
import random  
import numpy as np
import ctypes
import math
import keyboard
from utils import SpatialUtils


PUL = ctypes.POINTER(ctypes.c_ulong)

class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class Input_I(ctypes.Union):
    _fields_ = [("mi", MouseInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

class RobloxInputDriver:
    
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_ABSOLUTE = 0x8000

    @staticmethod
    def _send_input(inputs):
        n_inputs = len(inputs)
        input_array = (Input * n_inputs)(*inputs)
        ctypes.windll.user32.SendInput(n_inputs, ctypes.byref(input_array), ctypes.sizeof(Input))

    @classmethod
    def move_to(cls, x, y):
        
        screen_width = ctypes.windll.user32.GetSystemMetrics(0)
        screen_height = ctypes.windll.user32.GetSystemMetrics(1)
        normalized_x = int((x * 65535) / screen_width)
        normalized_y = int((y * 65535) / screen_height)

        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        ii_.mi = MouseInput(normalized_x, normalized_y, 0, cls.MOUSEEVENTF_MOVE | cls.MOUSEEVENTF_ABSOLUTE, 0, ctypes.pointer(extra))
        cls._send_input([Input(ctypes.c_ulong(0), ii_)])

    @classmethod
    def click_at(cls, x, y, duration=0.03):
        
        cls.move_to(x, y)
        time.sleep(0.01) 

        extra = ctypes.c_ulong(0)
        down_ii = Input_I()
        down_ii.mi = MouseInput(0, 0, 0, cls.MOUSEEVENTF_LEFTDOWN, 0, ctypes.pointer(extra))
        
        up_ii = Input_I()
        up_ii.mi = MouseInput(0, 0, 0, cls.MOUSEEVENTF_LEFTUP, 0, ctypes.pointer(extra))

        cls._send_input([Input(ctypes.c_ulong(0), down_ii)])
        time.sleep(duration)
        cls._send_input([Input(ctypes.c_ulong(0), up_ii)])

class BaseLogic:
    def __init__(self, app):
        self.app = app
        self.utils = SpatialUtils()
        self.running = False
        self.paused = False
        self.thread = None

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
            
        self.app.log("Waiting for Roblox focus...")
        while self.running:
            if self.check_focus():
                self.app.log("Roblox focus detected!")
                return True
            time.sleep(0.5)
        return False

    def check_focus(self):
        hwnd = win32gui.GetForegroundWindow()
        text = win32gui.GetWindowText(hwnd)
        return "Roblox" in text

    def smooth_move(self, target_x, target_y, duration=0.15):
        try:
            start_x, start_y = win32api.GetCursorPos()
        except Exception:
            return  
            
        dx = target_x - start_x
        dy = target_y - start_y
        distance = np.hypot(dx, dy)
        
        if distance == 0:
            return

        steps = max(4, int(distance / random.randint(20, 40)))
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

    def main_loop(self):
        
        pass

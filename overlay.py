import tkinter as tk

class Overlay:
    def __init__(self, callback):
        self.callback = callback
        self.root = tk.Toplevel()
        self.root.attributes('-alpha', 0.5)
        self.root.attributes('-topmost', True)
        self.root.attributes('-fullscreen', True)
        self.root.config(cursor="cross")
        
        self.canvas = tk.Canvas(self.root, cursor="cross", bg="grey")
        self.canvas.pack(fill="both", expand=True)
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        
        self.root.bind("<ButtonPress-1>", self.on_button_press)
        self.root.bind("<B1-Motion>", self.on_move_press)
        self.root.bind("<ButtonRelease-1>", self.on_button_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, 
                                               fill='red', outline='white', width=1)

    def on_move_press(self, event):
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x, end_y = (event.x, event.y)
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        self.root.destroy()
        self.callback(x1, y1, x2, y2)

class PersistentOverlay:
    def __init__(self, x1, y1, x2, y2, color="red"):
        self.root = tk.Toplevel()
        self.root.overrideredirect(True)
        self.root.attributes('-alpha', 0.5)
        self.root.attributes('-topmost', True)
        
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        self.root.geometry(f"{width}x{height}+{x1}+{y1}")
        self.root.config(bg=color)
        
        
        self.root.update()
        
        
        try:
            import sys
            import ctypes
            
            # Only apply Windows-specific overlay settings on Windows
            if sys.platform.startswith('win'):
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                if hwnd == 0: 
                    hwnd = self.root.winfo_id()
                    
                
                style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)
        except Exception as e:
            print(f"Overlay click-through error: {e}")

    def destroy(self):
        try:
            self.root.destroy()
        except:
            pass

class PointSelector:
    def __init__(self, callback):
        self.callback = callback
        self.root = tk.Toplevel()
        self.root.attributes('-alpha', 0.5)
        self.root.attributes('-topmost', True)
        self.root.attributes('-fullscreen', True)
        self.root.config(cursor="cross")
        
        self.root.bind("<Button-1>", self.on_click)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def on_click(self, event):
        x, y = event.x, event.y
        self.root.destroy()
        self.callback(x, y)

class ColorPicker:
    def __init__(self, callback):
        self.callback = callback
        self.root = tk.Toplevel()
        self.root.attributes('-alpha', 0.5)
        self.root.attributes('-topmost', True)
        self.root.attributes('-fullscreen', True)
        self.root.config(cursor="crosshair")
        
        self.root.bind("<Button-1>", self.on_click)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def on_click(self, event):
        import PIL.ImageGrab
        x, y = event.x, event.y
        
        img = PIL.ImageGrab.grab(bbox=(x, y, x + 1, y + 1))
        color = img.getpixel((0, 0))
        self.root.destroy()
        self.callback(color)

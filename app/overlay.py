import tkinter as tk


class _FrozenScreen:
    """Fullscreen picker that shows a clean screenshot instead of a see-through tint.
    Colours read from it are the real on-screen colours (no grey/white wash)."""
    HINT = ""

    def __init__(self, cursor="cross"):
        import PIL.ImageGrab
        from PIL import ImageTk
        self.shot = PIL.ImageGrab.grab().convert("RGB")  # taken before our window appears
        self.root = tk.Toplevel()
        self.root.attributes('-topmost', True)
        self.root.attributes('-fullscreen', True)
        self.root.config(cursor=cursor)
        self.canvas = tk.Canvas(self.root, cursor=cursor, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self._photo = ImageTk.PhotoImage(self.shot)
        self.canvas.create_image(0, 0, image=self._photo, anchor="nw")
        if self.HINT:
            self._label(self.shot.width // 2, 24, self.HINT + "   (Esc to cancel)")
        self.root.bind("<Escape>", lambda e: self.cancel())
        self.root.protocol("WM_DELETE_WINDOW", self.cancel)     # Alt+F4 counts as cancel too
        self.root.focus_force()

    def cancel(self):
        """Close without picking. The macro window was hidden for the pick and normally comes back in
        the pick callback, which never runs on cancel - so bring it back here."""
        app_window = self.root.master
        self.root.destroy()
        try:
            app_window.deiconify()
            app_window.lift()
            app_window.focus_force()
        except Exception:
            pass

    def _label(self, x, y, text, anchor="n"):
        t = self.canvas.create_text(x, y, text=text, fill="white", font=("Arial", 12, "bold"), anchor=anchor)
        x1, y1, x2, y2 = self.canvas.bbox(t)
        bg = self.canvas.create_rectangle(x1 - 8, y1 - 4, x2 + 8, y2 + 4, fill="#111", outline="#0d6efd")
        self.canvas.tag_raise(t, bg)
        return bg, t

    def pixel(self, x, y):
        x = min(max(0, x), self.shot.width - 1)
        y = min(max(0, y), self.shot.height - 1)
        return self.shot.getpixel((x, y))


class Overlay(_FrozenScreen):
    HINT = "Drag a box around the area"

    def __init__(self, callback):
        super().__init__("cross")
        self.callback = callback
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.root.bind("<ButtonPress-1>", self.on_button_press)
        self.root.bind("<B1-Motion>", self.on_move_press)
        self.root.bind("<ButtonRelease-1>", self.on_button_release)

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y,
                                                 outline='#ff3b3b', width=2, dash=(4, 2))

    def on_move_press(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

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


class RecordingBadge:
    """A small red '● REC 0:12 · Ctrl+P to stop' badge on top of the game while a route is recorded.
    It NEVER takes keyboard focus (or the keys you press would stop reaching Roblox / the recording),
    clicks go straight through it, and it isn't in the taskbar."""

    def __init__(self, x, y):
        import time as _t
        self._t0 = _t.time()
        self._time = _t.time
        self.root = tk.Toplevel()
        self.root.withdraw()                              # never shown the normal (focus-taking) way
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(bg="#b02a37")
        self.lbl = tk.Label(self.root, text="", bg="#b02a37", fg="white", font=("Arial", 13, "bold"), padx=14, pady=5)
        self.lbl.pack()
        self._tick(first=True)
        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        self.root.geometry(f"+{int(x - w / 2)}+{int(y)}")
        self.root.update_idletasks()
        self._show_without_focus()

    def _show_without_focus(self):
        try:
            import sys, ctypes
            if not sys.platform.startswith("win"):
                self.root.deiconify(); return
            u = ctypes.windll.user32
            hwnd = int(self.root.wm_frame(), 16) or u.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            # LAYERED | TRANSPARENT (click-through) | TOOLWINDOW (no taskbar) | TOPMOST | NOACTIVATE
            ex = u.GetWindowLongW(hwnd, -20) | 0x80000 | 0x20 | 0x80 | 0x8 | 0x08000000
            u.SetWindowLongW(hwnd, -20, ex)
            u.SetLayeredWindowAttributes(hwnd, 0, 235, 2)            # slightly see-through
            u.ShowWindow(hwnd, 4)                                     # SW_SHOWNOACTIVATE
            u.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x1 | 0x2 | 0x10)   # topmost, no move/size, NO activate
            self.hwnd = hwnd
        except Exception as e:
            print(f"Recording badge error: {e}")

    def _tick(self, first=False):
        try:
            secs = int(self._time() - self._t0)
            self.lbl.configure(text=f"● REC  {secs // 60}:{secs % 60:02d}   ·   Ctrl+P to stop")
            self.root.after(500, self._tick)
        except Exception:
            pass

    def destroy(self):
        try:
            self.root.destroy()
        except Exception:
            pass


class PointSelector(_FrozenScreen):
    HINT = "Click the spot"

    def __init__(self, callback):
        super().__init__("crosshair")
        self.callback = callback
        self.root.bind("<Button-1>", self.on_click)

    def on_click(self, event):
        x, y = event.x, event.y
        self.root.destroy()
        self.callback(x, y)


class ColorPicker(_FrozenScreen):
    HINT = "Click the colour to pick"
    ZOOM, GRID = 10, 11  # magnifier: 11x11 pixels shown 10x larger

    def __init__(self, callback):
        super().__init__("crosshair")
        self.callback = callback
        self._mag_photo = None
        self._mag_items = []
        self.root.bind("<Motion>", self.on_motion)
        self.root.bind("<Button-1>", self.on_click)

    def on_motion(self, event):
        """Live magnifier + swatch next to the cursor so you can hit the exact pixel."""
        from PIL import Image, ImageTk
        for item in self._mag_items:
            self.canvas.delete(item)
        x, y, half = event.x, event.y, self.GRID // 2
        crop = self.shot.crop((x - half, y - half, x + half + 1, y + half + 1))
        size = self.GRID * self.ZOOM
        self._mag_photo = ImageTk.PhotoImage(crop.resize((size, size), Image.NEAREST))
        ox = x + 20 if x + 20 + size < self.shot.width else x - 20 - size
        oy = y + 20 if y + 20 + size + 30 < self.shot.height else y - 20 - size - 30
        c = half * self.ZOOM
        r, g, b = self.pixel(x, y)
        self._mag_items = [
            self.canvas.create_rectangle(ox - 2, oy - 2, ox + size + 2, oy + size + 30, fill="#111", outline="#0d6efd"),
            self.canvas.create_image(ox, oy, image=self._mag_photo, anchor="nw"),
            self.canvas.create_rectangle(ox + c, oy + c, ox + c + self.ZOOM, oy + c + self.ZOOM, outline="#ff3b3b", width=2),
            self.canvas.create_rectangle(ox + 4, oy + size + 6, ox + 24, oy + size + 24,
                                         fill=f"#{r:02x}{g:02x}{b:02x}", outline="white"),
            self.canvas.create_text(ox + 30, oy + size + 15, text=f"{r}, {g}, {b}", fill="white",
                                    font=("Arial", 10, "bold"), anchor="w"),
        ]

    def on_click(self, event):
        color = self.pixel(event.x, event.y)
        self.root.destroy()
        self.callback(color)

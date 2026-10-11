"""Shared look for every macro window, so the same kind of control looks and behaves the same everywhere."""
import customtkinter as ctk

BLUE, BLUE_HOVER = "#0d6efd", "#0b5ed7"
GREEN, GREEN_HOVER = "#198754", "#157347"
GREY, GREY_HOVER = "#343a40", "#495057"
TEXT_DIM = "#adb5bd"

CARD = dict(fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
BTN = dict(height=30, font=("Arial", 12), fg_color="#495057", hover_color="#343a40", corner_radius=6)
BTN_BLUE = dict(height=30, font=("Arial", 12), fg_color=BLUE, hover_color=BLUE_HOVER, corner_radius=6)
TITLE_FONT = ("Arial", 16, "bold")


def sound_picker(parent, kind):
    """🎵 Choose sound… / ▶ / Reset for one alert sound. The file is copied into the app's 'sounds' folder
    so updates never delete it. kind = 'event' or 'done'."""
    import os, shutil
    from tkinter import filedialog
    from settings import SpatialSettings, get_base_path
    from utils import play_sound, custom_sound, SOUND_TYPES
    st = SpatialSettings()
    f = ctk.CTkFrame(parent, fg_color="transparent")
    name = ctk.CTkLabel(f, text="", font=("Arial", 12), text_color=TEXT_DIM)

    def show():
        p = custom_sound(kind)
        name.configure(text=os.path.basename(p) if p else "Windows sound")

    def choose():
        path = filedialog.askopenfilename(title="Pick a sound", parent=parent.winfo_toplevel(),
                                          filetypes=[("Sound files", " ".join("*" + e for e in SOUND_TYPES)),
                                                     ("All files", "*.*")])
        if not path:
            return
        folder = os.path.join(get_base_path(), "sounds")
        os.makedirs(folder, exist_ok=True)
        dest = os.path.join(folder, f"{kind}_{os.path.basename(path)}")
        try:
            if os.path.abspath(path) != os.path.abspath(dest):
                shutil.copy2(path, dest)
        except Exception:
            return
        st.settings.setdefault("sound_files", {})[kind] = os.path.relpath(dest, get_base_path())
        st.save()
        show()
        play_sound(kind)

    def reset():
        st.settings.setdefault("sound_files", {}).pop(kind, None)
        st.save()
        show()

    ctk.CTkButton(f, text="🎵 Choose sound…", width=118, height=26, command=choose, **{k: v for k, v in BTN.items() if k != "height"}).pack(side="left")
    ctk.CTkButton(f, text="▶", width=30, height=26, command=lambda: play_sound(kind), **{k: v for k, v in BTN.items() if k != "height"}).pack(side="left", padx=4)
    ctk.CTkButton(f, text="Reset", width=50, height=26, command=reset, **{k: v for k, v in BTN.items() if k != "height"}).pack(side="left")
    name.pack(side="left", padx=6)
    show()
    return f


def save_while_typing(widget, save, delay=400):
    """Save a text box shortly after you stop typing, so you don't have to press Enter or click
    somewhere else first (closing the window right after typing used to lose the text)."""
    def later(event=None):
        if event is not None and event.keysym in ("Return", "Tab", "Escape"):
            return                                   # those have their own handlers
        job = getattr(widget, "_save_job", None)
        if job:
            try:
                widget.after_cancel(job)
            except Exception:
                pass

        def run():
            widget._save_job = None
            try:
                if widget.winfo_exists():
                    save()
            except Exception:
                pass
        widget._save_job = widget.after(delay, run)
    widget.bind("<KeyRelease>", later, add="+")
    widget.bind("<<Paste>>", lambda e: widget.after(50, later), add="+")


def big_toggle(parent, command):
    """The main ON/OFF switch of a page (Always Click OK, Event alerts...): full width and easy to hit."""
    return ctk.CTkButton(parent, text="", height=40, corner_radius=8, font=("Arial", 13, "bold"),
                         border_width=1, border_color="#495057", command=command)


def style_toggle(btn, on, name, icon_on="🔔", icon_off="🔕"):
    """Green with 'ON' when running, grey with 'OFF' when not, same wording on every page."""
    if on:
        btn.configure(text=f"{icon_on}  {name}: ON   (click to turn off)", fg_color=GREEN, hover_color=GREEN_HOVER,
                      text_color="#ffffff", border_color=GREEN)
    else:
        btn.configure(text=f"{icon_off}  {name}: OFF   (click to turn on)", fg_color=GREY, hover_color=GREY_HOVER,
                      text_color="#e9ecef", border_color="#495057")

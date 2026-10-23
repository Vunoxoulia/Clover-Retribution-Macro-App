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


def _fit_wrapped_labels():
    """A label's wraplength is a fixed number, so on a narrower card (or a smaller window) its text was cut
    off at both sides. Keep every wrapped label at most as wide as the space its parent really gives it."""
    init = ctk.CTkLabel.__init__

    def __init__(self, master=None, *args, **kw):
        init(self, master, *args, **kw)
        want = kw.get("wraplength") or 0
        if not want or master is None:
            return

        def fit(_e=None):
            try:
                pad = self.pack_info().get("padx", 0) if self.winfo_manager() == "pack" else 0
                pad = sum(pad) if isinstance(pad, (tuple, list)) else int(pad) * 2
                room = (master.winfo_width() - pad - 12) / self._get_widget_scaling()
                if room > 40 and abs(min(want, room) - self.cget("wraplength")) > 2:
                    self.configure(wraplength=min(want, room))
            except Exception:
                pass
        master.bind("<Configure>", fit, add="+")
        self.bind("<Map>", fit, add="+")               # a card rebuilt in place never resizes, so fit on show too
    ctk.CTkLabel.__init__ = __init__


_fit_wrapped_labels()


def sound_picker(parent, kind):
    """Choose sound… / ▶ / Reset for one alert sound. The file is copied into the app's 'sounds' folder
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

    ctk.CTkButton(f, text="Choose sound…", width=118, height=26, command=choose, **{k: v for k, v in BTN.items() if k != "height"}).pack(side="left")
    ctk.CTkButton(f, text="▶", width=30, height=26, command=lambda: play_sound(kind), **{k: v for k, v in BTN.items() if k != "height"}).pack(side="left", padx=4)
    ctk.CTkButton(f, text="Reset", width=50, height=26, command=reset, **{k: v for k, v in BTN.items() if k != "height"}).pack(side="left")
    name.pack(side="left", padx=6)
    show()
    return f


def help_box(card, text, title):
    """A small '?' right after a card's title; clicking it shows / hides the explanation under the title,
    so the page isn't a wall of text. Returns the help label (its text can be changed later)."""
    lbl = ctk.CTkLabel(card, text=text, font=("Arial", 12), text_color="#cfe2ff", fg_color="#1b2b40",
                       corner_radius=6, justify="left", anchor="w", wraplength=420)
    row = title                                      # the title's line inside the card (title or its row frame)
    while row.master is not card:
        row = row.master

    def flip():
        if lbl.winfo_manager():
            lbl.pack_forget()
            q.configure(fg_color="transparent", text_color="#adb5bd")
        else:
            lbl.pack(after=row, fill="x", padx=8, pady=(2, 4), ipadx=6, ipady=4)
            q.configure(fg_color="#0d6efd", text_color="#ffffff")
    q = ctk.CTkButton(card, text="?", width=20, height=20, corner_radius=10, font=("Arial", 11, "bold"),
                      fg_color="transparent", border_width=1, border_color="#6c757d", text_color="#adb5bd",
                      hover_color="#2b3035", command=flip)
    q.place(in_=title, relx=1.0, x=8, rely=0.5, anchor="w")
    if title.winfo_manager() == "pack":              # leave room for the '?' so it never covers a neighbour
        padx = title.pack_info().get("padx", 0)
        left, right = padx if isinstance(padx, (tuple, list)) else (padx, padx)
        title.pack_configure(padx=(left, int(right) + 30))
    return lbl


def fast_scroll_frame(parent, **pack_kw):
    """A scrolling page. customtkinter's scrollbar forces update_idletasks() on every redraw, which makes Tk
    re-run the whole page layout several times per click; the scrollbar doesn't need it."""
    sf = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    sf.pack(fill="both", expand=True, **pack_kw)
    sb_canvas = getattr(getattr(sf, "_scrollbar", None), "_canvas", None)
    if sb_canvas is not None:
        sb_canvas.update_idletasks = lambda: None
    return sf


def seconds_combo(parent, values, current, save):
    """A number box: pick from the list or type any number. save(text) runs on pick, Enter, click-away
    and while typing."""
    cb = ctk.CTkComboBox(parent, values=values, width=70, height=26, command=save)
    cb.set(f"{current:g}")
    store = lambda *_: save(cb.get())
    cb._entry.bind("<FocusOut>", store)
    cb._entry.bind("<Return>", store)
    save_while_typing(cb._entry, store)
    return cb


def save_while_typing(widget, save, delay=120):
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


def style_toggle(btn, on, name, icon_on="", icon_off=""):
    """Green with 'ON' when running, grey with 'OFF' when not, same wording on every page."""
    if on:
        btn.configure(text=f"{icon_on}  {name}: ON   (click to turn off)", fg_color=GREEN, hover_color=GREEN_HOVER,
                      text_color="#ffffff", border_color=GREEN)
    else:
        btn.configure(text=f"{icon_off}  {name}: OFF   (click to turn on)", fg_color=GREY, hover_color=GREY_HOVER,
                      text_color="#e9ecef", border_color="#495057")

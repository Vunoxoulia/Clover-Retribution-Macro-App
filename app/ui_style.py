import os
import time
import ctypes
import customtkinter as ctk

FONT = "Bahnschrift"
try:
    from customtkinter.windows.widgets.core_rendering.draw_engine import DrawEngine
    DrawEngine.preferred_drawing_method = "polygon_shapes"
except Exception:
    pass
import theme
theme.install(os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme_grimoire.json"))

BLUE, BLUE_HOVER = "#1c8f52", "#16743f"
GREEN, GREEN_HOVER = "#1f9d55", "#187a43"
GREY, GREY_HOVER = "#2a3a33", "#34463d"
TEXT_DIM = "#a39d86"

CARD = dict(fg_color="#15201b", border_color="#2a3a33", border_width=1, corner_radius=8)
BTN = dict(height=30, font=(FONT, 12), fg_color="#34463d", hover_color="#2a3a33", corner_radius=6)


def _fit_wrapped_labels():
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
        self.bind("<Map>", fit, add="+")
    ctk.CTkLabel.__init__ = __init__


_fit_wrapped_labels()


def sound_picker(parent, kind):
    import os, shutil
    from tkinter import filedialog
    from settings import SpatialSettings, get_base_path
    from utils import play_sound, custom_sound, SOUND_TYPES
    st = SpatialSettings()
    f = ctk.CTkFrame(parent, fg_color="transparent")
    name = ctk.CTkLabel(f, text="", font=(FONT, 12), text_color=TEXT_DIM)

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
    lbl = ctk.CTkLabel(card, text=text, font=(FONT, 12), text_color="#e8dfc5", fg_color="#1a2a22",
                       corner_radius=6, justify="left", anchor="w", wraplength=420)
    row = title
    while row.master is not card:
        row = row.master

    def flip():
        if lbl.winfo_manager():
            lbl.pack_forget()
            q.configure(fg_color="transparent", text_color="#a39d86")
        else:
            lbl.pack(after=row, fill="x", padx=8, pady=(2, 4), ipadx=6, ipady=4)
            q.configure(fg_color="#1c8f52", text_color="#ffffff")
    q = ctk.CTkButton(card, text="?", width=20, height=20, corner_radius=10, font=(FONT, 11, "bold"),
                      fg_color="transparent", border_width=1, border_color="#6f7a6e", text_color="#a39d86",
                      hover_color="#22302a", command=flip)
    q.place(in_=title, relx=1.0, x=8, rely=0.5, anchor="w")
    if title.winfo_manager() == "pack":
        padx = title.pack_info().get("padx", 0)
        left, right = padx if isinstance(padx, (tuple, list)) else (padx, padx)
        title.pack_configure(padx=(left, int(right) + 30))
    return lbl


def dialog_keys(win, ok=None):
    import tkinter as tk

    def esc(e):
        try:
            cmd = win.protocol("WM_DELETE_WINDOW")
            win.tk.eval(cmd) if cmd else win.destroy()
        except Exception:
            pass
        return "break"

    def enter(e):
        if not isinstance(e.widget, tk.Text):
            ok()
            return "break"
    win.bind("<Escape>", esc)
    if ok:
        win.bind("<Return>", enter)


def faster_resizing(root):
    try:
        from ctypes import wintypes
        u = ctypes.windll.user32
        get, put = u.GetClassLongPtrW, u.SetClassLongPtrW
        get.restype, get.argtypes = ctypes.c_size_t, [wintypes.HWND, ctypes.c_int]
        put.restype, put.argtypes = ctypes.c_size_t, [wintypes.HWND, ctypes.c_int, ctypes.c_size_t]
        root.update_idletasks()
        top = u.GetParent(root.winfo_id()) or root.winfo_id()
        for h in (top, root.winfo_id()):
            put(h, -26, get(h, -26) & ~0x3)
    except Exception:
        pass


class SmoothScrollFrame(ctk.CTkScrollableFrame):
    STEP = 64

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self._scrollbar.configure(command=self._bar_scroll)
        except Exception:
            pass

    def _bar_scroll(self, *args):
        self._bar_args = args
        if not getattr(self, "_bar_job", None):
            self._bar_job = self.after(8, self._apply_bar)

    def _apply_bar(self):
        self._bar_job = None
        try:
            self._parent_canvas.yview(*self._bar_args)
            self.update_idletasks()
        except Exception:
            pass
        self._repaint_soon()

    def _repaint_soon(self):
        job = getattr(self, "_repaint_job", None)
        if job:
            self.after_cancel(job)
        self._repaint_job = self.after(120, self._final_repaint)

    def _final_repaint(self):
        self._repaint_job = None
        self._repaint()

    def _repaint(self):
        try:
            import ctypes
            ctypes.windll.user32.RedrawWindow(self._parent_canvas.winfo_id(), None, None, 0x1 | 0x4 | 0x80)
        except Exception:
            pass

    def _mouse_wheel_all(self, event):
        if getattr(self, "_shift_pressed", False) or not self.check_if_master_is_canvas(event.widget):
            return super()._mouse_wheel_all(event)
        self._wheel_px = getattr(self, "_wheel_px", 0.0) - event.delta / 120 * self.STEP
        if not getattr(self, "_wheel_job", None):
            self._wheel_job = self.after(12, self._apply_wheel)

    MAX_PER_FRAME = 96

    def _apply_wheel(self):
        self._wheel_job = None
        px = max(-self.MAX_PER_FRAME, min(self.MAX_PER_FRAME, int(self._wheel_px)))
        self._wheel_px -= px
        try:
            cv = self._parent_canvas
            top, bottom = cv.yview()
            if (px > 0 and bottom >= 1.0) or (px < 0 and top <= 0.0) or (top, bottom) == (0.0, 1.0):
                self._wheel_px = 0.0
                return
            if px:
                if str(cv.cget("yscrollincrement")) != "1":
                    cv.configure(yscrollincrement=1)
                cv.yview_scroll(px, "units")
                self.update_idletasks()
            if abs(self._wheel_px) >= 1:
                self._wheel_job = self.after(12, self._apply_wheel)
            else:
                self._repaint_soon()
        except Exception:
            self._wheel_px = 0.0


def fast_scroll_frame(parent, **pack_kw):
    sf = SmoothScrollFrame(parent, fg_color="transparent")
    sf.pack(fill="both", expand=True, **pack_kw)
    sb_canvas = getattr(getattr(sf, "_scrollbar", None), "_canvas", None)
    if sb_canvas is not None:
        sb_canvas.update_idletasks = lambda: None
    return sf


def seconds_combo(parent, values, current, save):
    cb = ctk.CTkComboBox(parent, values=values, width=70, height=26, command=save)
    cb.set(f"{current:g}")
    store = lambda *_: save(cb.get())
    cb._entry.bind("<FocusOut>", store)
    cb._entry.bind("<Return>", store)
    save_while_typing(cb._entry, store)
    return cb


def save_while_typing(widget, save, delay=120):
    def later(event=None):
        if event is not None and event.keysym in ("Return", "Tab", "Escape"):
            return
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
    return ctk.CTkButton(parent, text="", height=40, corner_radius=8, font=(FONT, 13, "bold"),
                         border_width=1, border_color="#34463d", command=command)


def style_toggle(btn, on, name, icon_on="", icon_off=""):
    if on:
        btn.configure(text=f"{icon_on}  {name}: ON   (click to turn off)", fg_color=GREEN, hover_color=GREEN_HOVER,
                      text_color="#ffffff", border_color=GREEN)
    else:
        btn.configure(text=f"{icon_off}  {name}: OFF   (click to turn on)", fg_color=GREY, hover_color=GREY_HOVER,
                      text_color="#e8dfc5", border_color="#34463d")


STATE_MARK = {"done": ("✓", "#1f9d55"), "missing": ("✗", "#d9534f"), "unknown": ("·", "#8f8a76")}


_CHEVRONS = {}


def _chevron(down, color="#e8dfc5", size=12):
    key = (down, color, size)
    if key not in _CHEVRONS:
        try:
            from PIL import Image, ImageDraw
            big = size * 4
            pic = Image.new("RGBA", (big, big), (0, 0, 0, 0))
            rgb = tuple(int(theme.c(color)[i:i + 2], 16) for i in (1, 3, 5))
            pts = ([(big * .25, big * .3), (big * .75, big * .3), (big * .5, big * .75)] if down else
                   [(big * .3, big * .2), (big * .78, big * .5), (big * .3, big * .8)])
            ImageDraw.Draw(pic).polygon(pts, fill=rgb + (255,))
            pic = pic.resize((size, size), Image.LANCZOS)
            _CHEVRONS[key] = ctk.CTkImage(light_image=pic, dark_image=pic, size=(size, size))
        except Exception:
            _CHEVRONS[key] = None
    return _CHEVRONS[key]


class StepCard(ctk.CTkFrame):
    def __init__(self, parent, number, title, build=None, text=""):
        super().__init__(parent, **CARD)
        self._build, self.opened = build, False
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=8, pady=6)
        self.mark = ctk.CTkLabel(head, text="·", width=22, font=(FONT, 15, "bold"), text_color="#8f8a76")
        self.mark.pack(side="left")
        self.title = ctk.CTkButton(head, text=f"{number}  {title}", anchor="w", height=32, font=(FONT, 13, "bold"),
                                   fg_color="transparent", hover_color="#22302a", text_color="#e8dfc5",
                                   command=self.toggle)
        self.title.pack(side="left", fill="x", expand=True)
        self.actions = ctk.CTkFrame(head, fg_color="transparent", width=1, height=1)
        self.actions.pack(side="right")
        self.open_btn = ctk.CTkButton(self.actions, text="Open", image=_chevron(False), compound="right", width=80,
                                      height=28, font=(FONT, 12, "bold"), fg_color=GREY, hover_color=GREY_HOVER,
                                      text_color="#e8dfc5", command=self.toggle)
        self.open_btn.pack(side="right", padx=(6, 0))
        self.text = ctk.CTkLabel(self, text=text, font=(FONT, 12), text_color=TEXT_DIM, anchor="w", justify="left",
                                 wraplength=460)
        if text:
            self.text.pack(fill="x", padx=38, pady=(0, 6))
        self.body = ctk.CTkFrame(self, fg_color="transparent", height=1)
        for w in (head, self.mark, self.text):
            w.configure(cursor="hand2")
            w.bind("<Button-1>", lambda e: self.toggle(), add="+")
        self.title.configure(cursor="hand2")
        self.bind("<Enter>", lambda e: self._hover(True), add="+")
        self.bind("<Leave>", lambda e: self.after(30, self._leave_check), add="+")

    def _hover(self, on):
        try:
            self.configure(border_color=BLUE if on else CARD["border_color"])
        except Exception:
            pass

    def _leave_check(self):
        try:
            w = self.winfo_containing(*self.winfo_pointerxy())
        except Exception:
            w = None
        if w is None or not str(w).startswith(str(self)):
            self._hover(False)

    def set_state(self, state, text=None):
        ch, col = STATE_MARK.get(state, STATE_MARK["unknown"])
        self.mark.configure(text=ch, text_color=col)
        if text is None:
            return
        self.text.configure(text=text)
        if not text:
            self.text.pack_forget()
        elif not self.text.winfo_manager():
            kw = {"before": self.body} if self.body.winfo_manager() else {}
            self.text.pack(fill="x", padx=38, pady=(0, 6), **kw)

    def add_button(self, text, command, width=90):
        b = ctk.CTkButton(self.actions, text=text, width=width, command=command, **BTN)
        b.pack(side="left", padx=(6, 0))
        return b

    def toggle(self):
        self.show(not self.body.winfo_manager())

    def show(self, on=True):
        if on:
            if not self.opened and self._build:
                self.opened = True
                try:
                    self._build(self.body)
                except Exception as e:
                    print(f"Couldn't build this setup step: {e}")
            self.body.pack(fill="x", padx=4, pady=(0, 6))
        else:
            self.body.pack_forget()
        self.open_btn.configure(text="Close" if on else "Open", image=_chevron(on))


def make_collapsible(card, is_open, on_change=None):
    slaves = card.pack_slaves()
    if len(slaves) < 2:
        return None
    head, rows = slaves[0], [(w, w.pack_info()) for w in slaves[1:]]
    state = {"open": bool(is_open)}
    btn = ctk.CTkButton(head, text="", compound="right", width=80, height=28, font=(FONT, 12, "bold"),
                        fg_color=GREY, hover_color=GREY_HOVER, text_color="#e8dfc5")

    def apply():
        for w, info in rows:
            w.pack_forget()
        if state["open"]:
            for w, info in rows:
                if w.winfo_exists():
                    w.pack(**{k: v for k, v in info.items() if k != "in"})
        btn.configure(text="Close" if state["open"] else "Open", image=_chevron(state["open"]))

    def flip(_e=None):
        state["open"] = not state["open"]
        apply()
        if on_change:
            on_change(state["open"])
    btn.configure(command=flip)
    btn.pack(side="right")
    for w in [head] + [c for c in head.winfo_children() if isinstance(c, ctk.CTkLabel)]:
        w.configure(cursor="hand2")
        w.bind("<Button-1>", flip, add="+")
    apply()
    return btn


class OptionGroup(ctk.CTkFrame):
    def __init__(self, parent, title, advanced=False):
        super().__init__(parent, **CARD)
        self.advanced = advanced
        self.head = ctk.CTkLabel(self, text=title + ("   (Advanced)" if advanced else ""), font=(FONT, 13, "bold"),
                                 anchor="w")
        self.head.pack(fill="x", padx=8, pady=(6, 2))
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="x", padx=8, pady=(0, 8))
        self._pack = {"fill": "x", "pady": 4}

    def words(self):
        out, todo = [], [self]
        while todo:
            w = todo.pop()
            todo.extend(w.winfo_children())
            try:
                t = w.cget("text")
            except Exception:
                continue
            if isinstance(t, str) and t:
                out.append(t)
        return " ".join(out).lower()

    def place_me(self, **pack_kw):
        self._pack = pack_kw or self._pack
        self.pack(**self._pack)

    def matches(self, query, show_advanced):
        if self.advanced and not show_advanced:
            return False
        words = self.words()
        return all(q in words for q in (query or "").lower().split())


def search_box(parent, groups, get_advanced=lambda: True, on_change=None):
    e = ctk.CTkEntry(parent, placeholder_text="Search settings (e.g. wait, sound, colour)", height=32, font=(FONT, 12))

    def run(*_):
        hits = [g for g in groups if g.matches(e.get(), get_advanced())]
        for g in groups:
            g.pack_forget()
        for g in hits:
            g.pack(**g._pack)
        if on_change:
            on_change(len(hits))
    e.bind("<KeyRelease>", run, add="+")
    e.refresh = run
    return e


class StatusBar(ctk.CTkFrame):
    def __init__(self, parent, on_toggle, key="F6"):
        super().__init__(parent, **CARD)
        self.key = key
        self.button = ctk.CTkButton(self, text="", width=150, height=36, font=(FONT, 13, "bold"), command=on_toggle)
        self.button.pack(side="left", padx=8, pady=8)
        self.state = ctk.CTkLabel(self, text="", font=(FONT, 13, "bold"), width=90, anchor="w")
        self.state.pack(side="left", padx=(4, 0))
        self.activity = ctk.CTkLabel(self, text="", font=(FONT, 12), text_color=TEXT_DIM, anchor="w")
        self.activity.pack(side="left", fill="x", expand=True, padx=8)
        self.set_running(False)

    def set_running(self, on):
        if on:
            self.button.configure(text=f"■  Stop  ({self.key})", fg_color="#b83a2f", hover_color="#962e25")
            self.state.configure(text="RUNNING", text_color="#1f9d55")
        else:
            self.button.configure(text=f"▶  Start  ({self.key})", fg_color=GREEN, hover_color=GREEN_HOVER)
            self.state.configure(text="STOPPED", text_color=TEXT_DIM)

    def set_activity(self, text):
        self.activity.configure(text=text)


class RecentLog(ctk.CTkFrame):
    COLORS = {"info": "#e8dfc5", "warning": "#e6b84f", "problem": "#f08a7e"}

    def __init__(self, parent, lines=20, height=220):
        super().__init__(parent, **CARD)
        import collections
        self.lines = collections.deque(maxlen=lines)
        self.box = ctk.CTkTextbox(self, height=height, font=(FONT, 12), wrap="word", fg_color="#121b17")
        self.box.pack(fill="both", expand=True, padx=6, pady=6)
        for k, col in self.COLORS.items():
            self.box.tag_config(k, foreground=theme.c(col))
        self.box.configure(state="disabled")

    def add(self, msg, kind="info"):
        import time
        self.lines.append((time.strftime("%H:%M:%S"), str(msg), kind))
        self.show()

    def fill(self, lines):
        self.lines.extend(lines)
        self.show()

    def show(self):
        self.box.configure(state="normal")
        self.box.delete("1.0", "end")
        for t, msg, kind in self.lines:
            self.box.insert("end", f"{t}  {msg}\n", kind if kind in self.COLORS else "info")
        self.box.see("end")
        self.box.configure(state="disabled")


def general_settings(parent, settings):
    note = ctk.CTkLabel(parent, text="These settings change every macro, not just this one.", font=(FONT, 12),
                        text_color=TEXT_DIM, anchor="w")
    note.pack(fill="x", padx=12, pady=(10, 2))

    mk = ctk.CTkFrame(parent, **CARD); mk.pack(fill="x", padx=8, pady=4)
    t = ctk.CTkLabel(mk, text="Mouse and keys", font=(FONT, 13, "bold"), anchor="w")
    t.pack(anchor="w", padx=8, pady=(6, 2))
    help_box(mk, "Wait before each click: after the mouse arrives on a button, the macro waits this long before "
                 "clicking, so Roblox notices the mouse first. Raise it if clicks get missed.\n"
                 "Keep Roblox in focus: if another window comes to the front, the macro brings Roblox back "
                 "before pressing keys.", t)
    row = ctk.CTkFrame(mk, fg_color="transparent"); row.pack(anchor="w", padx=12, pady=2)
    ctk.CTkLabel(row, text="Wait before each click", font=(FONT, 12)).pack(side="left")

    def save_delay(v):
        try:
            settings.set("click_delay", max(0.0, float(str(v).strip())))
        except (TypeError, ValueError):
            pass
    seconds_combo(row, ["0.3", "0.5", "0.75", "1", "1.5", "2"], float(settings.get("click_delay", 1.0)),
                  save_delay).pack(side="left", padx=6)
    ctk.CTkLabel(row, text="s (after the mouse arrives)", font=(FONT, 12), text_color=TEXT_DIM).pack(side="left")
    _setting_box(mk, settings, "force_roblox_focus", "Keep Roblox in focus (brings it back to the front)")
    ctk.CTkFrame(mk, fg_color="transparent", height=4).pack()

    ck = ctk.CTkFrame(parent, **CARD); ck.pack(fill="x", padx=8, pady=4)
    t = ctk.CTkLabel(ck, text="Screenshots and keys", font=(FONT, 13, "bold"), anchor="w")
    t.pack(anchor="w", padx=8, pady=(6, 2))
    help_box(ck, "The macros see the game with screenshots and listen for your hotkeys with a key hook. On some PCs "
                 "one of those doesn't work (black screenshots, hotkeys that don't react) - then a backup way is used "
                 "by itself. Check shows which way works on this PC. Keep Roblox open (not minimized) for it.", t)
    row = ctk.CTkFrame(ck, fg_color="transparent"); row.pack(fill="x", padx=12, pady=(2, 2))
    result = ctk.CTkLabel(ck, text="", font=(FONT, 12), justify="left", anchor="w", wraplength=420)

    def check():
        btn.configure(state="disabled")
        result.configure(text="Checking screenshots... then press any letter key (like A) within 6 s.",
                         text_color=TEXT_DIM)
        if not result.winfo_manager():
            result.pack(fill="x", padx=12, pady=(0, 6))

        def work():
            import utils
            cap = utils.check_capture()
            parent.after(0, lambda: result.configure(
                text="Screenshots checked - now press any letter key (like A) within 6 s.", text_color="#e6b84f"))
            keys = utils.check_keys(6.0)
            parent.after(0, lambda: show(cap, keys))
        import threading
        threading.Thread(target=work, daemon=True).start()

    def show(cap, keys):
        if not result.winfo_exists():
            return
        if not cap["roblox"]:
            shots = "Screenshots: open Roblox (not minimized) and check again."
        elif cap["screen_ok"]:
            shots = "Screenshots: ✓ work normally."
        elif cap["backup_ok"]:
            shots = "Screenshots: the normal way gives black pictures here - ✓ the backup works and is used now."
        else:
            shots = "Screenshots: ✗ both ways give black pictures - is Roblox minimized or covered by a full-screen app?"
        if not keys["pressed"]:
            ks = "Keys: no key press seen in 6 s - press Check again and tap a key."
        elif keys["hook"]:
            ks = "Keys: ✓ hotkeys work normally."
        elif keys["backup"]:
            ks = "Keys: the key hook doesn't work here (blocked?) - ✓ the backup works and is used by itself."
        else:
            ks = "Keys: ✗ neither way saw the key - if Roblox runs as administrator, run the macro as administrator too."
        bad = (cap["roblox"] and not (cap["screen_ok"] or cap["backup_ok"])) or (keys["pressed"] and not keys["hook"]
                                                                                  and not keys["backup"])
        result.configure(text=f"{shots}\n{ks}", text_color="#f08a7e" if bad else "#7ee0a6")
        btn.configure(state="normal")
    btn = ctk.CTkButton(row, text="Check", width=90, height=26, command=check)
    btn.pack(side="left")

    lf = ctk.CTkFrame(parent, **CARD); lf.pack(fill="x", padx=8, pady=4)
    t = ctk.CTkLabel(lf, text="Look and feel", font=(FONT, 13, "bold"), anchor="w")
    t.pack(anchor="w", padx=8, pady=(6, 2))
    help_box(lf, "The badge is a small label on top of the game that says what the macro is doing. Turning it "
                 "off can help on slow PCs. Colours (theme) are picked on the main menu.", t)
    _setting_box(lf, settings, "show_action_badge", "Show what the macro is doing on top of the game")
    tips = ctk.CTkFrame(lf, fg_color="transparent"); tips.pack(fill="x", padx=12, pady=(2, 6))
    tips_note = ctk.CTkLabel(tips, text="", font=(FONT, 12), text_color=TEXT_DIM)

    def tips_again():
        settings.set("tour_done", False)
        tips_note.configure(text="They show next time the main menu opens.")
    ctk.CTkButton(tips, text="Show tips again", width=120, height=26, command=tips_again,
                  **{k: v for k, v in BTN.items() if k != "height"}).pack(side="left")
    tips_note.pack(side="left", padx=8)


def _setting_box(parent, settings, key, text, default=True):
    var = ctk.BooleanVar(value=bool(settings.get(key, default)))
    ctk.CTkCheckBox(parent, text=text, variable=var, font=(FONT, 12),
                    command=lambda: settings.set(key, bool(var.get()))).pack(anchor="w", padx=12, pady=2)


class Checklist:
    def __init__(self, holder, root, get_problems, is_shown, steps, video=None, before_steps=None):
        self.root, self.get_problems, self.is_shown, self.defs = root, get_problems, is_shown, steps
        self._job = None
        top = ctk.CTkFrame(holder, fg_color="transparent"); top.pack(fill="x", padx=10, pady=(8, 2))
        self.progress = ctk.CTkLabel(top, text="", font=(FONT, 13, "bold"), anchor="w", justify="left",
                                     wraplength=380)
        self.progress.pack(side="left")
        if video:
            import links
            ctk.CTkButton(top, text="▶ Video", width=64, height=24, font=(FONT, 11, "bold"), fg_color="#2a3a33",
                          hover_color="#34463d", text_color="#ff6b6b",
                          command=lambda: links.open_link(video)).pack(side="right")
        if before_steps:
            before_steps(holder)
        self.steps = {}
        for n, title, _ids, build, _info, help_text in steps:
            st = StepCard(holder, n, title, self._flush(build))
            st.pack(fill="x", padx=8, pady=3)
            if help_text:
                help_box(st, help_text, st.title)
            self.steps[n] = st

    @staticmethod
    def _flush(build):
        def run(body):
            build(body)
            for w in body.pack_slaves():
                if w.pack_info().get("padx") not in (0, "0"):
                    w.pack_configure(padx=0)
        return run

    def build_all(self):
        for st in self.steps.values():
            if not st.opened:
                st.show(True)
                st.show(False)

    def owner(self, pid):
        return next((n for n, _t, ids, _b, _i, _h in self.defs if any(pid.startswith(i) for i in ids)), None)

    def refresh(self, open_first=False):
        if self._job:
            try:
                self.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        try:
            if not self.progress.winfo_exists():
                return
        except Exception:
            return
        try:
            probs = self.get_problems()
        except Exception as e:
            print(f"Setup check failed: {e}")
            probs = None
        if probs is not None:
            done = checked = 0
            first_missing = None
            for n, _title, ids, _b, info, _h in self.defs:
                mine = [p for p in probs if self.owner(p["id"]) == n]
                if ids:
                    checked += 1
                    if mine:
                        state, text = "missing", "\n".join(p["text"] for p in mine)
                        first_missing = first_missing or n
                    else:
                        state, text = "done", info("done")
                        done += 1
                else:
                    state, text = "unknown", info("unknown")
                st = self.steps[n]
                if getattr(st, "_shown_state", None) != (state, text):
                    st._shown_state = (state, text)
                    st.set_state(state, text)
            other = [p for p in probs if self.owner(p["id"]) is None]
            msg = f"Setup: {done} of {checked} checked steps done" if done < checked else "Setup: ready to start"
            if other:
                msg += "\nAlso: " + "; ".join(p["short"] for p in other)
            if self.progress.cget("text") != msg:
                self.progress.configure(text=msg)
            if open_first:
                self.steps[first_missing or min(self.steps)].show(True)
        if self.is_shown():
            self._job = self.root.after(1500, self.refresh)


def msg_kind(msg):
    m = str(msg).lower()
    if m.startswith("can't start") or any(w in m for w in ("error", "failed", "couldn't", "could not")):
        return "problem"
    if any(w in m for w in ("not found", "retry", "warning", "⚠", "missing", "gave up", "giving up", "timed out")):
        return "warning"
    return "info"


def _clock(sec):
    sec = int(max(0, sec))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


class RunPanel(ctk.CTkFrame):
    def __init__(self, parent, root, is_running, counters, get_problems, fix, open_log, recent=()):
        super().__init__(parent, fg_color="transparent")
        self.root, self.is_running, self.counters = root, is_running, counters
        self.get_problems, self.fix = get_problems, fix
        row = ctk.CTkFrame(self, fg_color="transparent"); row.pack(fill="x", padx=4, pady=(0, 4))
        self.time_lbl = ctk.CTkLabel(row, text="", font=(FONT, 12, "bold"), anchor="w")
        self.time_lbl.pack(side="left")
        self.count_lbl = ctk.CTkLabel(row, text="", font=(FONT, 12), text_color=TEXT_DIM, anchor="e")
        self.count_lbl.pack(side="right")
        self.stop_box = ctk.CTkFrame(self, **CARD)
        self.stop_lbl = ctk.CTkLabel(self.stop_box, text="", font=(FONT, 12), anchor="w", justify="left", wraplength=420)
        self.stop_lbl.pack(side="left", fill="x", expand=True, padx=8, pady=6)
        self.fix_btn = ctk.CTkButton(self.stop_box, text="Fix it  →", width=90, height=28, fg_color=BLUE,
                                     hover_color=BLUE_HOVER)
        self.head = ctk.CTkFrame(self, fg_color="transparent"); self.head.pack(fill="x", padx=4, pady=(2, 2))
        ctk.CTkLabel(self.head, text="Recent messages", font=(FONT, 12, "bold")).pack(side="left")
        ctk.CTkButton(self.head, text="Open full log", width=100, height=24, command=open_log,
                      **{k: v for k, v in BTN.items() if k != "height"}).pack(side="right")
        self.log_view = RecentLog(self, lines=20, height=140)
        self.log_view.pack(fill="both", expand=True)
        self.log_view.fill(list(recent))
        self._was, self._started, self._ended = None, None, None
        self._tick()

    def add(self, entry):
        try:
            if self.winfo_exists():
                self.log_view.fill([entry])
        except Exception:
            pass

    def _tick(self):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        now = time.time()
        running = bool(self.is_running())
        if running and self._was is not True:
            self._started, self._ended = now, None
            self.stop_box.pack_forget()
        elif not running and self._was is True:
            self._ended = now
            self._show_stopped(now - (self._started or now))
        self._was = running
        if running:
            t = f"Running for {_clock(now - self._started)}"
        elif self._started and self._ended:
            t = f"Last run: {_clock(self._ended - self._started)}"
        else:
            t = "Not started yet"
        parts = []
        for label, fn in self.counters:
            try:
                v = fn()
            except Exception:
                v = None
            if v is not None:
                parts.append(f"{label}: {v}")
        c = "   ·   ".join(parts)
        if self.time_lbl.cget("text") != t:
            self.time_lbl.configure(text=t)
        if self.count_lbl.cget("text") != c:
            self.count_lbl.configure(text=c)
        self.root.after(1000, self._tick)

    def _show_stopped(self, dur):
        lines = [f"Stopped after {_clock(dur)}."]
        if self.log_view.lines:
            lines.append("Last message: " + self.log_view.lines[-1][1])
        try:
            probs = self.get_problems() or []
        except Exception:
            probs = []
        self.fix_btn.pack_forget()
        if probs:
            lines.append("Setup still missing: " + "; ".join(p["short"] for p in probs))
            go = next((p["go"] for p in probs if p.get("go")), None)
            if go:
                self.fix_btn.configure(command=lambda g=go: self.fix(g))
                self.fix_btn.pack(side="right", padx=8)
        self.stop_lbl.configure(text="\n".join(lines))
        self.stop_box.pack(fill="x", padx=4, pady=(0, 4), before=self.head)

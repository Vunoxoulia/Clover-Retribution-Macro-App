"""Umbral Abyss Stone -> Moves page: the Skill Macro's move cards (own copy, own snapshots) + the kill check."""
import threading
import time

import customtkinter as ctk

from gui_smart import SmartMacroGUI, CARD, BTN, BLUE
from overlay import PointSelector
from ui_style import help_box, save_while_typing

AIM_NAMES = {"jug": "Juggernaut", "move": "Fixed spot", "none": "Don't move"}


class UmbralMovesPage(SmartMacroGUI):
    """Built inside the Umbral window's Moves tab. Uses the Skill Macro's card code on Umbral's own move list."""

    def __init__(self, gui, tab):                        # not SmartMacroGUI.__init__: no window of its own
        self.gui = gui
        self.root = gui.root
        self.settings = gui.settings
        self.logic = gui.logic.skills                    # UmbralMoves (Skill Macro engine, Umbral's settings)
        self.overlays = []
        self._expanded = set()
        self._cards = {}
        self.build(tab)

    def log(self, msg):
        self.gui.log(msg)

    # ---------- page ----------
    def build(self, p):
        rot = self.cfg["rotation"]
        top = ctk.CTkFrame(p, **CARD); top.pack(fill="x", padx=15, pady=4)
        t = ctk.CTkLabel(top, text="Moves", font=("Arial", 14, "bold"), text_color="#0d6efd")
        t.pack(anchor="w", padx=8, pady=(8, 4))
        help_box(top, "Works like the Skill Macro's rotation, during a fight only: it casts the highest READY move "
                      "(top of the list first) again and again until the Juggernaut is dead. READY = the slot's icon "
                      "matches its snapshot (take them while every move is off cooldown).\n"
                      "Each move: mouse move (Aim) -> delay before -> key -> click (if ticked) -> delay after.\n"
                      "Aim: Juggernaut = onto it (it follows it), Fixed spot = a point you pick, Don't move = "
                      "wherever the mouse is.", t)
        row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(2, 8))
        ctk.CTkButton(row, text="Auto find hotbar", width=130, height=28, **BLUE,
                      command=self.auto_tune).pack(side="left", padx=(0, 4))
        ctk.CTkButton(row, text="Hotbar region", width=110, height=28, **BLUE,
                      command=lambda: self.pick_region(rot, "region", after=self.build_cards)).pack(side="left", padx=4)
        ctk.CTkLabel(row, text="Slots", font=("Arial", 12, "bold")).pack(side="left", padx=(8, 2))
        self._pick(row, rot, "slot_count", [str(i) for i in range(1, 11)], 56, int, editable=False,
                   on_save=self.build_cards).pack(side="left")
        row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(0, 8))
        snap = ctk.CTkButton(row, text="Snapshot all", width=110, height=28, **BLUE, command=self.snapshot_all)
        snap.pack(side="left", padx=(0, 4))
        self.gui._mark("umbral_snap", snap)
        ctk.CTkButton(row, text="Snapshots", width=90, **BTN, command=self.view_snapshots).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Test", width=60, **BTN, command=self.test_rotation).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Show slots", width=80, **BTN, command=self.flash_slots).pack(side="left", padx=4)

        self.cards_box = ctk.CTkFrame(p, fg_color="transparent")
        self.cards_box.pack(fill="x", padx=15, pady=(4, 0))
        self.build_cards()

        self.build_fight(p)
        self.build_kill(p)

    def build_fight(self, p):
        fc = ctk.CTkFrame(p, **CARD); fc.pack(fill="x", padx=15, pady=(8, 4))
        t = ctk.CTkLabel(fc, text="Fight", font=("Arial", 14, "bold"), text_color="#0d6efd")
        t.pack(anchor="w", padx=8, pady=(8, 4))
        help_box(fc, "Give up after: fighting longer than this without a confirmed kill -> respawn and go to the "
                     "next location.", t)
        row = ctk.CTkFrame(fc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(0, 10))
        ctk.CTkLabel(row, text="Give up after", font=("Arial", 12)).pack(side="left")
        self.gui._num_combo(row, "umbral_reset_secs", ["8", "10", "15", "20", "30", "45", "60"],
                            float(self.settings.get("umbral_reset_secs", 15)), minimum=3.0).pack(side="left", padx=6)
        ctk.CTkLabel(row, text="s", font=("Arial", 12)).pack(side="left")

    def build_kill(self, p):
        kc = ctk.CTkFrame(p, **CARD); kc.pack(fill="x", padx=15, pady=4)
        t = ctk.CTkLabel(kc, text="Kill check", font=("Arial", 14, "bold"), text_color="#0d6efd")
        t.pack(anchor="w", padx=8, pady=(8, 4))
        help_box(kc, "Killing it shows a reward popup (mastery / EXP). Drag a box over where that popup shows: after "
                     "each move the macro reads it (like the Skill Macro's Items) and counts the kill as soon as one "
                     "of your words is there. Words: comma-separated, upper / lower case doesn't matter.\n"
                     "No box set = the old way: its colour is gone twice in a row.\n"
                     "Test reads the box right now and shows what it read.", t)
        row = ctk.CTkFrame(kc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row, text="Popup box", width=90, anchor="w", font=("Arial", 12, "bold")).pack(side="left")
        kb = ctk.CTkButton(row, text="Set box", width=80, height=28, **BLUE,
                           command=lambda: self.gui.pick_region("umbral_kill_region"))
        kb.pack(side="left", padx=4)
        self.gui._mark("umbral_killbox", kb)
        ctk.CTkButton(row, text="Clear", width=60, **BTN, command=self._clear_kill_box).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Test", width=60, **BTN,
                      command=lambda: self.gui._run_test(self.gui.logic.test_kill_check)).pack(side="left", padx=4)
        self.kill_lbl = ctk.CTkLabel(row, text="", font=("Arial", 12)); self.kill_lbl.pack(side="left", padx=6)
        self.show_kill_box()
        row = ctk.CTkFrame(kc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(2, 10))
        ctk.CTkLabel(row, text="Kill words", width=90, anchor="w", font=("Arial", 12, "bold")).pack(side="left")
        e = ctk.CTkEntry(row, width=260, font=("Arial", 12), placeholder_text="mastery, exp")
        e.insert(0, ", ".join(self.logic.kill_words()))
        e.pack(side="left", padx=4)
        store = lambda *_: self.settings.set("umbral_kill_words",
                                             [w.strip() for w in e.get().split(",") if w.strip()])
        e.bind("<FocusOut>", store)
        save_while_typing(e, store)

    def show_kill_box(self):
        r = self.logic.kill_region()
        self.kill_lbl.configure(text=f"set ({r[2] - r[0]}x{r[3] - r[1]})" if r else "not set (uses the colour)",
                                text_color="#75b798" if r else "#adb5bd")

    def _clear_kill_box(self):
        self.settings.settings.setdefault("regions", {}).pop("umbral_kill_region", None)
        self.settings.save()
        self.show_kill_box()

    # ---------- move cards: the Skill Macro's, plus an Aim row ----------
    def _make_opts(self, parent, slot, m):
        box = super()._make_opts(parent, slot, m)
        for row in box.winfo_children():                 # the order hint is in the help box; here it got cut off
            for w in row.winfo_children():
                if isinstance(w, ctk.CTkLabel) and str(w.cget("text")).startswith("mouse move"):
                    w.destroy()
        refresh = lambda: self._update_summary(slot)
        r = ctk.CTkFrame(box, fg_color="transparent"); r.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(r, text="Aim", font=("Arial", 12)).pack(side="left", padx=(8, 4))
        xy = ctk.CTkLabel(r, text="", font=("Arial", 12), text_color="#ced4da")
        pick = ctk.CTkButton(r, text="Pick spot", width=80, **BTN)

        def show():
            mode = m.get("mouse_mode", "jug")
            pick.pack_forget(); xy.pack_forget()
            if mode == "move":
                pick.pack(side="left", padx=4)
                xy.configure(text=self._xy_text(m)); xy.pack(side="left", padx=4)

        def set_mode(v):
            self._set(m, "mouse_mode", {name: k for k, name in AIM_NAMES.items()}[v])
            show(); refresh()

        def picked(x, y):
            self.root.deiconify()
            m["x"], m["y"] = x, y
            self.save()
            show()
        pick.configure(command=lambda: (self._hide(), PointSelector(picked)))
        seg = ctk.CTkSegmentedButton(r, values=list(AIM_NAMES.values()), height=26, font=("Arial", 12),
                                     command=set_mode)
        seg.set(AIM_NAMES.get(m.get("mouse_mode", "jug"), "Juggernaut"))
        seg.pack(side="left")
        show()
        return box

    @staticmethod
    def move_summary(slot, m, has_snapshot):
        text = SmartMacroGUI.move_summary(slot, m, has_snapshot).replace(" · aim", "").replace("aim", "")
        aim = {"move": "aim: fixed spot", "none": "no aim"}.get(m.get("mouse_mode", "jug"))
        parts = [x for x in (text if text != "default" else "", aim) if x]
        return " · ".join(parts) or "default"

    def auto_tune(self):
        """Auto find hotbar: switches to Roblox, finds the hotbar and points the slots at your filled ones."""
        def run():
            if not self.gui.logic.wait_focus_for_test():
                return
            if not self.logic.auto_find_hotbar():
                return
            self.root.after(0, lambda: (self.build_cards(), self.flash_slots()))
            self.log("Hotbar found. Press Snapshot all while every move is ready.")
        threading.Thread(target=run, daemon=True).start()

    def _hide(self):
        self.root.withdraw()
        self.root.update()
        time.sleep(0.2)

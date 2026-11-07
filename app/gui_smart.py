import os
import time
import threading
import links
import customtkinter as ctk
import tkinter as tk
import keyboard

from settings import SpatialSettings
from overlay import Overlay, PointSelector, PersistentOverlay
from logic_smart import SmartMacroLogic
from gui import SidebarNav, NAV_ICONS, NAV_GROUPS, StartCheck
from ui_style import dialog_keys, FONT, save_while_typing, fast_scroll_frame, help_box, general_settings, RunPanel, msg_kind, \
    make_collapsible, _chevron, GREY, GREY_HOVER


CARD = dict(fg_color="#15201b", border_color="#2a3a33", border_width=1, corner_radius=8)
BTN = dict(height=26, font=(FONT, 12), fg_color="#34463d", hover_color="#2a3a33")
BLUE = dict(fg_color="#1c8f52", hover_color="#16743f")
RED = dict(fg_color="#7a2620", hover_color="#5e1d18")
MOUSE_MODES = ["none", "move", "target"]


def index_obj(lst, obj):
    return next(i for i, x in enumerate(lst) if x is obj)


def remove_obj(lst, obj):
    del lst[index_obj(lst, obj)]


def forget_looks_window(root, c, after):
    import creature
    from PIL import Image
    win = ctk.CTkToplevel(root)
    win.title("Saved looks")
    dialog_keys(win)
    win.transient(root); win.resizable(False, False); win.after(150, win.lift)
    ctk.CTkLabel(win, text="Tick the looks to forget", font=(FONT, 14, "bold")).pack(anchor="w", padx=14, pady=(12, 6))
    ticks = []
    for look in c.get("looks") or []:
        row = ctk.CTkFrame(win, fg_color="transparent"); row.pack(fill="x", padx=14, pady=3)
        tick = ctk.BooleanVar(value=False)
        ticks.append(tick)
        ctk.CTkCheckBox(row, text="", variable=tick, width=24).pack(side="left")
        pic = creature.read_look_picture(look.get("pic") or "")
        if pic is not None:
            im = Image.fromarray(pic)
            ctk.CTkLabel(row, text="", image=ctk.CTkImage(light_image=im, dark_image=im, size=im.size)
                         ).pack(side="left", padx=(0, 8))
        if not look.get("color1"):
            ctk.CTkLabel(row, text="Stands out" if look.get("odd") else "Old dark shape (not used)",
                         font=(FONT, 12)).pack(side="left")
            continue
        for col in (look.get("color1"), look.get("color2")):
            if col:
                ctk.CTkLabel(row, text="", width=26, height=22, corner_radius=4,
                             fg_color="#%02x%02x%02x" % tuple(col)).pack(side="left", padx=2)
        ctk.CTkLabel(row, text="Colours", font=(FONT, 12)).pack(side="left", padx=6)

    def forget():
        numbers = [i for i, tick in enumerate(ticks) if tick.get()]
        win.destroy()
        if numbers:
            creature.forget_looks(c, numbers)
            after(len(numbers))
    row = ctk.CTkFrame(win, fg_color="transparent"); row.pack(fill="x", padx=14, pady=(10, 12))
    ctk.CTkButton(row, text="Cancel", width=80, command=win.destroy, **BTN).pack(side="right")
    ok = ctk.CTkButton(row, text="Forget ticked", width=110, command=forget, **{**BTN, **BLUE})
    ok.pack(side="right", padx=6)
    dialog_keys(win, ok=ok.invoke)
    win.grab_set()


class SmartMacroGUI(StartCheck):
    def __init__(self, root, title="Skill Macro", on_back=None, **_):
        self.root = root
        self.on_back = on_back
        self.root.title(title)
        from gui import fit_window
        self._fitted_width = fit_window(self.root, 920, 720, 920, 480)
        self.settings = SpatialSettings()
        self.logic = SmartMacroLogic(self)
        self.overlays = []
        self._expanded = set()
        self._sfs = {}
        self._switches = {}
        self._cards = {}
        import collections
        self._recent = collections.deque(maxlen=20)
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        if self.cfg["rotation"]["enabled"] and self.cfg["combos"]["enabled"]:
            self.cfg["combos"]["enabled"] = False
            self.save()
        self.setup_ui()
        self.register_hotkeys()

    @property
    def cfg(self):
        return self.logic.cfg

    def save(self):
        self.settings.save()

    def setup_ui(self):
        ctk.set_appearance_mode("dark")
        self.nav = SidebarNav(self.root, self.root.title())
        if self._fitted_width < 920:
            self.root.after_idle(lambda: self.nav.set_collapsed(True))
        bar = ctk.CTkFrame(self.nav.content, **CARD)
        bar.pack(fill="x", pady=(0, 8))
        self.toggle_btn = ctk.CTkButton(bar, text="", width=170, font=(FONT, 13, "bold"), command=self.toggle_with_check)
        self.toggle_btn.pack(side="left", padx=8, pady=8)
        self.status_label = ctk.CTkLabel(bar, text="Status: idle", font=(FONT, 12, "bold"), anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True, padx=8)

        lb = ctk.CTkFrame(self.nav.content, **CARD); lb.pack(fill="x", pady=(0, 8))
        btn = dict(height=28, font=(FONT, 12), fg_color="#34463d", hover_color="#2a3a33")
        ctk.CTkLabel(lb, text="Loadout:", font=(FONT, 13, "bold")).pack(side="left", padx=(10, 6), pady=6)
        self.loadout_menu = ctk.CTkOptionMenu(lb, values=["Default"], width=180, command=self.select_loadout)
        self.loadout_menu.pack(side="left")
        ctk.CTkButton(lb, text="New", width=50, command=self.new_loadout, **btn).pack(side="left", padx=(6, 2))
        ctk.CTkButton(lb, text="Rename", width=64, command=self.rename_loadout, **btn).pack(side="left", padx=2)
        ctk.CTkButton(lb, text="Delete", width=56, command=self.delete_loadout,
                      **{**btn, "hover_color": "#b83a2f"}).pack(side="left", padx=2)
        ctk.CTkButton(lb, text="Export", width=76, command=self.export_loadout, **btn).pack(side="left", padx=(10, 2))
        ctk.CTkButton(lb, text="Import", width=76, command=self.import_loadout, **btn).pack(side="left", padx=2)
        self._refresh_loadout_menu()
        self.on_state_change(False)

        NAV_ICONS.setdefault("Target", "◎")
        self.nav.add_grouped(["Rotation", "Target", "Skill Combo", "Logs", "Items", "Timers", "Events", "Pop Up", "Settings",
                              "General"], {**NAV_GROUPS, "Settings": "Options", "Target": "Setup"})
        if self.on_back:
            self.nav.footer_button("←  Back to Menu", self.go_back)
        self._setup_lines = {}
        for name in ("Rotation", "Skill Combo"):
            lbl = ctk.CTkLabel(self.nav.tab(name), text="", font=(FONT, 12, "bold"), anchor="w", justify="left",
                               wraplength=600)
            lbl.pack(fill="x", padx=12, pady=(6, 0))
            self._setup_lines[name] = lbl
            self.nav.on_show(name, self._refresh_setup_line)
        self.build_rotation()
        self._mark("skill_slots", self._sfs["Rotation"])
        self._refresh_setup_line()
        from logic_events import WATCHER
        WATCHER.attach(self.settings)

        def events():
            from gui_events import EventsPage
            self.events_page = EventsPage(self.nav.tab("Events"), self.root, self.settings)

        from gui import OkPopupPage
        self.ok_page = OkPopupPage(self.root, self.nav.tab("Pop Up"), self.settings, self.log, build=False)
        for name, fn in (("Pop Up", self.ok_page.build_page), ("Target", self.build_target),
                         ("Skill Combo", self.build_combos), ("Items", self.build_items),
                         ("Timers", self.build_timers), ("Settings", self.build_settings), ("Events", events), ("Logs", self.build_run),
                         ("General", lambda: general_settings(self._page("General"), self.settings))):
            self.nav.lazy(name, fn)

    def toggle_with_check(self):
        if self.logic.running:
            self.logic.toggle()
        else:
            self._start_with_check()

    def _sync_start_btn(self):
        pass

    def _refresh_setup_line(self):
        job = getattr(self, "_setup_job", None)
        if job:
            self.root.after_cancel(job)
            self._setup_job = None
        try:
            probs = self.logic.setup_problems()
        except Exception as e:
            print(f"Setup check failed: {e}")
            probs = []
        text, col = (("✗  " + " ".join(p["text"] for p in probs), "#f08a7e") if probs
                     else ("✓  Setup: ready to start", "#1f9d55"))
        for lbl in self._setup_lines.values():
            if lbl.winfo_exists() and lbl.cget("text") != text:
                lbl.configure(text=text, text_color=col)
        if self.nav.get() in self._setup_lines:
            self._setup_job = self.root.after(1500, self._refresh_setup_line)

    def _page(self, name):
        if name not in self._sfs:
            self._sfs[name] = fast_scroll_frame(self.nav.tab(name), padx=4, pady=4)
        sf = self._sfs[name]
        for w in sf.winfo_children():
            w.destroy()
        return sf

    EXCLUSIVE = {"rotation": "combos", "combos": "rotation"}

    def _switch(self, parent, text, section):
        sw = ctk.CTkSwitch(parent, text=text, font=(FONT, 13, "bold"),
                           command=lambda: self.set_enabled(section, bool(sw.get())))
        if self.cfg[section]["enabled"]:
            sw.select()
        self._switches[section] = sw
        return sw

    def set_enabled(self, section, on):
        self.cfg[section]["enabled"] = on
        other = self.EXCLUSIVE.get(section)
        if on and other and self.cfg[other]["enabled"]:
            self.cfg[other]["enabled"] = False
            if other in self._switches:
                self._switches[other].deselect()
            names = {"rotation": "Rotation", "combos": "Skill Combo"}
            self.log(f"{names[section]} on — {names[other]} turned off (only one can run at a time)")
        self.save()
        if self.logic.running:
            self.logic.stop()
            self.logic.start()

    def _set(self, d, key, value, cast=None):
        if cast:
            try:
                value = cast(value)
            except (TypeError, ValueError):
                return False
        d[key] = value
        self.save()
        return True

    def _entry(self, parent, d, key, width=60, cast=None, placeholder="", on_save=None):
        e = ctk.CTkEntry(parent, width=width, font=(FONT, 12), placeholder_text=placeholder)
        if d.get(key) not in (None, ""):
            e.insert(0, str(d[key]))

        def commit(_=None):
            if self._set(d, key, e.get().strip(), cast) and on_save:
                on_save()
        e.bind("<FocusOut>", commit)
        e.bind("<Return>", commit)
        if key not in ("hotkey", "trigger"):
            save_while_typing(e, lambda: self._set(d, key, e.get().strip(), cast))
        return e

    def _xy_text(self, d):
        return f"({d.get('x', 0)}, {d.get('y', 0)})"

    def _mouse_controls(self, parent, d, on_save=None, on_mode=None):
        lbl = ctk.CTkLabel(parent, text=self._xy_text(d), font=(FONT, 12), text_color="#cfc6ab", width=80)

        def picked(x, y):
            self.root.deiconify()
            d["x"], d["y"] = x, y
            if d.get("mouse_mode", "none") == "none":
                d["mouse_mode"] = "move"
                om.set("move")
            self.save()
            lbl.configure(text=self._xy_text(d))
            if on_save:
                on_save()
        om = ctk.CTkOptionMenu(parent, values=MOUSE_MODES, width=80, height=26,
                               command=lambda v: (self._set(d, "mouse_mode", v), on_mode and on_mode()))
        om.set(d.get("mouse_mode", "none"))
        pick = ctk.CTkButton(parent, text="Pick XY", width=64, **BTN,
                             command=lambda: (self._hide(), PointSelector(picked)))
        return om, pick, lbl

    def _m1_box(self, parent, d, on_save=None, with_delay=True):
        from logic_smart import SmartMacroLogic
        SmartMacroLogic.migrate_click(d)
        f = ctk.CTkFrame(parent, fg_color="transparent")
        box = ctk.CTkCheckBox(f, text="Click after the key", width=150, font=(FONT, 12))
        box.pack(side="left")
        btn = ctk.CTkSegmentedButton(f, values=["M2", "M1"], width=76, height=24, font=(FONT, 12, "bold"),
                                     command=lambda v: (self._set(d, "click_btn", v.lower()), on_save and on_save()))
        btn.set(SmartMacroLogic.click_name(d))
        delay = ctk.CTkFrame(f, fg_color="transparent")
        ctk.CTkLabel(delay, text="after", font=(FONT, 12)).pack(side="left", padx=(0, 2))
        d.setdefault("m1_delay", 0.3)
        self._pick(delay, d, "m1_delay", ["0", "0.05", "0.1", "0.15", "0.2", "0.3", "0.5", "1"], 60,
                   on_save=on_save).pack(side="left")
        ctk.CTkLabel(delay, text="s", font=(FONT, 12)).pack(side="left", padx=(2, 0))
        hold = ctk.CTkFrame(f, fg_color="transparent")
        ctk.CTkLabel(hold, text="then wait", font=(FONT, 12)).pack(side="left", padx=(6, 2))
        d.setdefault("after_click", 0.1)
        self._pick(hold, d, "after_click", ["0", "0.05", "0.1", "0.15", "0.2", "0.3", "0.5"], 60,
                   on_save=on_save).pack(side="left")
        ctk.CTkLabel(hold, text="s", font=(FONT, 12)).pack(side="left", padx=(2, 0))

        def show():
            for w in (btn, delay, hold):
                w.pack_forget()
            if d.get("click"):
                btn.pack(side="left", padx=(0, 4))
                if with_delay:
                    delay.pack(side="left", padx=(2, 0))
                hold.pack(side="left")

        def flip():
            self._set(d, "click", bool(box.get()))
            show()
            if on_save:
                on_save()
        box.configure(command=flip)
        if d.get("click"):
            box.select()
        show()
        return f

    def _hide(self):
        self.root.withdraw()
        self.root.update()
        time.sleep(0.2)

    def pick_region(self, d, key, after=None, while_hidden=None):
        self._hide()

        def done(x1, y1, x2, y2):
            d[key] = [x1, y1, x2, y2]
            self.save()
            if while_hidden:
                self.root.update()
                time.sleep(0.15)
                try:
                    while_hidden()
                except Exception as e:
                    self.log(f"Couldn't take the picture: {e}")
            self.root.deiconify()
            if after:
                after()
        Overlay(done)

    def _pick(self, parent, d, key, values, width=70, cast=float, editable=True, on_save=None):
        def commit(v=None):
            v = (combo.get() if v is None else v).strip()
            if self._set(d, key, 0 if v in ("off", "—") else v, cast) and on_save:
                on_save()
        cur = d.get(key, values[0])
        if "off" in values and not cur:
            cur = "off"
        elif isinstance(cur, (int, float)) and not isinstance(cur, bool):
            cur = f"{cur:g}"
        else:
            cur = str(cur)
        if editable:
            combo = ctk.CTkComboBox(parent, values=values, width=width, height=26, command=commit)
            combo._entry.bind("<FocusOut>", lambda e: commit())
            combo._entry.bind("<Return>", lambda e: commit())
            save_while_typing(combo._entry, lambda: (lambda v: self._set(d, key, 0 if v in ("off", "—") else v, cast))(
                combo.get().strip()))
        else:
            combo = ctk.CTkOptionMenu(parent, values=values, width=width, height=26, command=commit)
        combo.set(cur)
        return combo

    def _ordered_moves(self):
        moves = list(enumerate(self.logic.moves(), start=1))
        moves.sort(key=lambda sm: (int(sm[1]["priority"] or 99), sm[0]))
        for i, (_, m) in enumerate(moves, start=1):
            m["priority"] = i
        return moves

    def move_priority(self, m, delta):
        order = [mm for _, mm in self._ordered_moves()]
        i = order.index(m)
        j = i + delta
        if 0 <= j < len(order):
            order[i]["priority"], order[j]["priority"] = order[j]["priority"], order[i]["priority"]
            self.save()
            moves = self.logic.moves()
            a, b = self._cards[moves.index(m) + 1], self._cards[moves.index(order[j]) + 1]
            a["frame"].pack_configure(**({"before": b["frame"]} if delta < 0 else {"after": b["frame"]}))
            self._refresh_ranks()

    def build_rotation(self):
        rot = self.cfg["rotation"]
        p = self._page("Rotation")
        top = ctk.CTkFrame(p, **CARD); top.pack(fill="x", pady=4)
        head = ctk.CTkFrame(top, fg_color="transparent"); head.pack(fill="x", padx=10, pady=(8, 0))
        t = ctk.CTkLabel(head, text="AFK Skill Rotation", font=(FONT, 16, "bold"), text_color="#1c8f52")
        t.pack(side="left")
        self._switch(head, "Enabled", "rotation").pack(side="left", padx=16)
        self._help_btn(top, "Rotation")
        help_box(top, "Casts the highest READY move (top of the list first). READY = its icon matches the snapshot.", t)
        row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 4))
        ctk.CTkButton(row, text="Hotbar region", width=140, height=28, **BLUE,
                      command=lambda: self.pick_region(rot, "region")).pack(side="left", padx=3)
        ctk.CTkLabel(row, text="Slots", font=(FONT, 12, "bold")).pack(side="left", padx=(8, 2))
        self._pick(row, rot, "slot_count", [str(i) for i in range(1, 11)], 56, int, editable=False,
                   on_save=self.build_cards).pack(side="left")
        ctk.CTkButton(row, text="Snapshot all", width=140, height=28, **BLUE,
                      command=self.snapshot_all).pack(side="left", padx=(10, 3))
        row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(row, text="Auto find hotbar", width=150, height=28, **BLUE,
                      command=self.auto_tune).pack(side="left", padx=3)
        ctk.CTkButton(row, text="Test", width=56, **BTN, command=self.test_rotation).pack(side="left", padx=3)
        ctk.CTkButton(row, text="Show", width=56, **BTN, command=self.flash_slots).pack(side="left", padx=3)

        self.build_aim_panel(p)
        tip = ctk.CTkFrame(p, fg_color="transparent"); tip.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(tip, text="Meditation, anti screen-shake, mana skin and reset lag are on the Timers page.",
                     font=(FONT, 11), text_color="#a39d86").pack(side="left", padx=6)
        sh = ctk.CTkFrame(p, fg_color="transparent"); sh.pack(fill="x", pady=(6, 0))
        ctk.CTkButton(sh, text="Snapshots", width=96, **BTN, command=self.view_snapshots).pack(side="right", padx=3)
        ctk.CTkLabel(sh, text="Retake or draw a slot's box in Snapshots", font=(FONT, 11),
                     text_color="#a39d86").pack(side="right", padx=6)
        self.cards_box = ctk.CTkFrame(p, fg_color="transparent")
        self.cards_box.pack(fill="x", pady=(4, 0))
        self.build_cards()

    def build_timers(self):
        p = self._page("Timers")
        t = ctk.CTkLabel(p, text="Timers", font=(FONT, 16, "bold"), text_color="#1c8f52")
        t.pack(anchor="w", padx=10, pady=(8, 0))
        ctk.CTkLabel(p, text="Each one is off until you switch it on. They run while the macro runs.",
                     font=(FONT, 12), text_color="#a39d86").pack(anchor="w", padx=10, pady=(0, 2))
        self._timers_next = ctk.CTkLabel(p, text="", font=(FONT, 12, "bold"), text_color="#e6b84f", anchor="w")
        self._timers_next.pack(anchor="w", padx=10, pady=(0, 4))
        self._tick_timers()
        opened = self.__dict__.setdefault("_timers_open", set())
        for name, build in (("meditation", self.build_meditation), ("anti_shake", self.build_anti_shake),
                            ("mana_skin", self.build_mana_skin),
                            ("reset_lag", self.build_reset_lag)):
            build(p)
            make_collapsible(p.pack_slaves()[-1], name in opened,
                             lambda on, n=name: opened.add(n) if on else opened.discard(n))

    def _tick_timers(self):
        lbl = getattr(self, "_timers_next", None)
        if lbl is None or not lbl.winfo_exists():
            return
        if not self.logic.running:
            lbl.configure(text="Next: - (counting starts when you press Start)")
        else:
            parts = []
            for kind, name in (("anti_shake", "anti screen-shake"), ("mana_skin", "mana skin"),
                               ("reset_lag", "reset lag")):
                left = self.logic.timer_due_in(kind)
                if left is not None:
                    parts.append(f"{name} {int(left) // 60}:{int(left) % 60:02d}")
            if self.logic.med().get("enabled"):
                parts.append("meditation when mana runs out")
            lbl.configure(text="Next: " + (" · ".join(parts) if parts else "nothing switched on"))
        self.root.after(1000, self._tick_timers)

    def build_meditation(self, parent):
        d = self.logic.med()
        card = ctk.CTkFrame(parent, **CARD); card.pack(fill="x", pady=4)
        head = ctk.CTkFrame(card, fg_color="transparent"); head.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(head, text="Meditation", font=(FONT, 13, "bold")).pack(side="left")
        sw = ctk.CTkSwitch(head, text="", width=40, command=lambda: self._set(d, "enabled", bool(sw.get())))
        if d["enabled"]:
            sw.select()
        sw.pack(side="left", padx=8)
        self._med_summary = ctk.CTkLabel(head, text="", font=(FONT, 12), text_color="#a39d86")
        self._med_summary.pack(side="left", padx=4)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=10, pady=(0, 8))
        self._med_settings(body)
        self._update_med_summary()
        self._med_card = card

    def _update_med_summary(self):
        lbl = getattr(self, "_med_summary", None)
        if lbl is None or not lbl.winfo_exists():
            return
        d = self.logic.med()
        if not d["region"][2] > d["region"][0]:
            lbl.configure(text="refills mana when it runs out — Open it and set the mana bar", text_color="#e6b84f")
            return
        out = {"weapon": "Weapon", "grimoire": "Grimoire", "both": "Weapon + Grimoire"}.get(d["out"], "Weapon")
        lbl.configure(text=f"at {float(d.get('below', 5)):g}% mana · {out} out · keys "
                           f"{'/'.join(k.upper() for k, _ in self.logic.meditation_steps()['away'])} + {d['key'].upper()}",
                      text_color="#a39d86")

    def build_anti_shake(self, parent):
        d = self.logic.anti_shake()
        card = ctk.CTkFrame(parent, **CARD); card.pack(fill="x", pady=4)
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(row, text="Anti screen-shake", font=(FONT, 13, "bold")).pack(side="left")
        sw = ctk.CTkSwitch(row, text="", width=40, command=lambda: self._set(d, "enabled", bool(sw.get())))
        if d["enabled"]:
            sw.select()
        sw.pack(side="left", padx=8)
        word = lambda t: ctk.CTkLabel(row, text=t, font=(FONT, 12)).pack(side="left", padx=(2, 2))
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=10, pady=(0, 2))
        word("Every")
        self._pick(row, d, "every", ["10", "15", "20", "30", "45", "60", "120"], 58).pack(side="left")
        word("s, press")
        self._entry(row, d, "key", 30).pack(side="left")
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=10, pady=(0, 6))
        word("then wait")
        self._pick(row, d, "between", ["0.25", "0.5", "0.75", "1", "1.5", "2"], 58).pack(side="left")
        word("s, press it again, wait")
        self._pick(row, d, "after", ["0", "0.25", "0.5", "1", "1.5"], 58).pack(side="left")
        word("s")
        row2 = ctk.CTkFrame(card, fg_color="transparent"); row2.pack(fill="x", padx=10, pady=(0, 8))
        r = d.get("check_region") or [0, 0, 0, 0]
        has = r[2] > r[0] and r[3] > r[1]
        status = ctk.CTkLabel(row2, text=("Check: on - after the presses, if that spot still looks like the skill "
                                          "tree it presses ',' again" if has else
                                          "Check: off - open the skill tree (,) and pick a spot that only looks like "
                                          "that IN the skill tree"),
                              font=(FONT, 11), text_color="#7ee0a6" if has else "#a39d86",
                              wraplength=430, justify="left")

        shot = {}

        def take():
            shot["ok"] = self.logic.save_anti_shake_ref()

        def picked():
            ok = shot.get("ok", False)
            status.configure(text=("Check: on - saved how that spot looks in the skill tree" if ok
                                   else "Couldn't take the picture - try again"),
                             text_color="#7ee0a6" if ok else "#f08a7e")

        def clear():
            d["check_region"] = [0, 0, 0, 0]; self.save()
            status.configure(text="Check: off", text_color="#a39d86")
        ctk.CTkButton(row2, text="Pick spot", width=90, height=24,
                      command=lambda: self.pick_region(d, "check_region", after=picked, while_hidden=take)).pack(side="left")
        ctk.CTkButton(row2, text="X", width=26, height=24, fg_color="#34463d",
                      command=clear).pack(side="left", padx=4)

        def test():
            self._hide()
            try:
                res = self.logic.anti_shake_back_to_normal()
            finally:
                self.root.deiconify()
            text, col = {True: ("Not in skill tree", "#7ee0a6"),
                         False: ("In skill tree", "#e6b84f"),
                         None: ("Pick a spot first", "#f08a7e")}[res]
            status.configure(text=text, text_color=col)
            self.log(text)
        ctk.CTkButton(row2, text="Test", width=50, height=24, fg_color="#34463d",
                      command=test).pack(side="left", padx=(0, 4))
        status.pack(side="left", padx=6)

    def build_mana_skin(self, parent):
        d = self.logic.mana_skin()
        card = ctk.CTkFrame(parent, **CARD); card.pack(fill="x", pady=4)
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(row, text="Mana skin", font=(FONT, 13, "bold")).pack(side="left")
        sw = ctk.CTkSwitch(row, text="", width=40, command=lambda: self._set(d, "enabled", bool(sw.get())))
        if d["enabled"]:
            sw.select()
        sw.pack(side="left", padx=8)
        word = lambda t: ctk.CTkLabel(row, text=t, font=(FONT, 12)).pack(side="left", padx=(2, 2))
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=10, pady=(0, 8))
        word("Every")
        self._pick(row, d, "every", ["60", "120", "180", "300", "600", "900"], 64).pack(side="left")
        word("s:  Ctrl+T → wait")
        self._pick(row, d, "between", ["0.5", "1", "1.5", "2", "3"], 58).pack(side="left")
        word("s → Ctrl+T")

    def build_reset_lag(self, parent):
        d = self.logic.reset_lag()
        card = ctk.CTkFrame(parent, **CARD); card.pack(fill="x", pady=4)
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=10, pady=(8, 2))
        title = ctk.CTkLabel(row, text="Reset lag", font=(FONT, 13, "bold")); title.pack(side="left")
        sw = ctk.CTkSwitch(row, text="", width=40, command=lambda: self._set(d, "enabled", bool(sw.get())))
        if d["enabled"]:
            sw.select()
        sw.pack(side="left", padx=8)
        word = lambda r, t: ctk.CTkLabel(r, text=t, font=(FONT, 12)).pack(side="left", padx=(2, 2))
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=10, pady=(0, 2))
        word(row, "Every")
        self._pick(row, d, "every", ["10", "15", "20", "30", "45", "60", "120"], 58).pack(side="left")
        word(row, "min: menu button → line")
        self._entry(row, d, "text", 90).pack(side="left")
        word(row, "→ OK")
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=10, pady=(0, 2))
        word(row, "Wait")
        self._pick(row, d, "wait", ["0.5", "1", "1.5", "2", "3"], 58).pack(side="left")
        word(row, "s between the clicks")
        row2 = ctk.CTkFrame(card, fg_color="transparent"); row2.pack(fill="x", padx=10, pady=(2, 8))
        from logic_smart import RESET_LAG_PIC
        status = ctk.CTkLabel(row2, text="", font=(FONT, 11))

        def show():
            has = os.path.exists(RESET_LAG_PIC)
            status.configure(text="menu button captured" if has else "capture the menu button (the ☰ in the top bar)",
                             text_color="#7ee0a6" if has else "#f08a7e")

        def capture():
            self._hide()

            def done(x1, y1, x2, y2):
                def save():
                    ok = self.logic.capture_reset_lag_button([x1, y1, x2, y2])
                    self.root.deiconify()
                    self.log("Reset lag: menu button captured." if ok else "Capture failed - drag a bigger box.")
                    show()
                self.root.after(300, save)
            Overlay(done)

        def test():
            def run():
                from logic_base import BaseLogic
                if not BaseLogic.wait_focus_for_test(self.logic.app.ok_page.logic):
                    return
                self.logic._testing_reset_lag = True
                try:
                    self.logic.do_reset_lag()
                finally:
                    self.logic._testing_reset_lag = False
            threading.Thread(target=run, daemon=True).start()
        ctk.CTkButton(row2, text="Capture menu button", width=150, height=24, command=capture).pack(side="left")
        ctk.CTkButton(row2, text="Test", width=50, height=24, fg_color="#34463d", command=test).pack(side="left", padx=4)
        status.pack(side="left", padx=6)
        show()
        help_box(card, "Every that many minutes it clicks the menu button (found by the picture you capture), then "
                       "the line with your text (e.g. Main Menu), then the OK that pops up - that resets the game's "
                       "lag. The OK is found with the OK button picture from the Pop Up page. Anything it can't find "
                       "is skipped (nothing is clicked blindly). Test runs it once now.", title)

    def _med_settings(self, body):
        d = self.logic.med()

        def section(title):
            ctk.CTkLabel(body, text=title, font=(FONT, 13, "bold")).pack(anchor="w", pady=(6, 2))

        section("When to meditate")
        row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x", pady=2)

        def pick_bar():
            def after():
                self._update_med_summary()
                self._fill_med_bar_btn(bar_btn)
            self.pick_region(d, "region", after=after)
        bar_btn = ctk.CTkButton(row, text="", width=120, height=28, command=pick_bar)
        bar_btn.pack(side="left")
        self._fill_med_bar_btn(bar_btn)
        ctk.CTkLabel(row, text="Meditate at", font=(FONT, 12)).pack(side="left", padx=(12, 2))
        self._pick(row, d, "below", ["5", "10", "15", "20", "25", "30", "40", "50"], 58,
                   on_save=self._update_med_summary).pack(side="left")
        ctk.CTkLabel(row, text="% mana or less", font=(FONT, 12)).pack(side="left", padx=(2, 0))
        ctk.CTkButton(row, text="Test", width=56, **BTN, command=self.test_mana).pack(side="right")
        self.mana_lbl = ctk.CTkLabel(body, text="", font=(FONT, 12))
        self.mana_lbl.pack(anchor="w")

        section("What you fight with")
        row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x", pady=2)
        names = {"weapon": "Weapon", "grimoire": "Grimoire", "both": "Both"}
        seg = ctk.CTkSegmentedButton(row, values=list(names.values()), height=26, font=(FONT, 12),
                                     command=lambda v: (self._set(d, "out", {n: k for k, n in names.items()}[v]),
                                                        self._med_steps_ui(), self._update_med_summary()))
        seg.set(names.get(d["out"], "Weapon"))
        seg.pack(side="left")
        for label, key in (("weapon", "weapon_key"), ("grimoire", "grimoire_key"), ("meditate", "key")):
            ctk.CTkLabel(row, text=label, font=(FONT, 12)).pack(side="left", padx=(12, 2))
            self._entry(row, d, key, 34, lambda v: v.lower(),
                        on_save=lambda: (self._med_steps_ui(), self._update_med_summary())).pack(side="left")

        section("Timing")
        row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text="All waits", font=(FONT, 12, "bold")).pack(side="left", padx=(0, 4))
        self._pick(row, d, "key_delay", ["0.5", "0.75", "1", "1.5", "2", "3"], 60,
                   on_save=lambda: (d.__setitem__("waits", {}), self.save(), self._med_steps_ui())).pack(side="left")
        ctk.CTkLabel(row, text="s (sets every wait below)", font=(FONT, 12), text_color="#a39d86").pack(side="left", padx=4)
        ctk.CTkLabel(row, text="Give up after", font=(FONT, 12)).pack(side="left", padx=(16, 2))
        self._pick(row, d, "max_wait", ["30", "60", "90", "120", "180", "300"], 60, float).pack(side="left")
        ctk.CTkLabel(row, text="s", font=(FONT, 12)).pack(side="left", padx=(2, 0))
        row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x", pady=2)
        stuck = ctk.CTkLabel(row, text="Stuck fix: same move", font=(FONT, 12))
        stuck.pack(side="left", padx=(0, 4))
        help_box(body, "When the same move casts this many times in a row, it presses the weapon / grimoire key, "
                       "then the meditation key, and repeats until another move casts.", stuck)
        self._pick(row, d, "stuck_after", ["off", "10", "15", "20", "30", "50"], 60, int).pack(side="left")
        ctk.CTkLabel(row, text="times in a row", font=(FONT, 12), text_color="#a39d86").pack(side="left", padx=4)
        self._med_steps =ctk.CTkFrame(body, fg_color="transparent"); self._med_steps.pack(fill="x", pady=(4, 0))
        self._med_steps_ui()

    def _fill_med_bar_btn(self, btn):
        d = self.logic.med()
        has = d["region"][2] > d["region"][0]
        btn.configure(text="Mana bar" if has else "Mana bar",
                      fg_color="#1f9d55" if has else "#1c8f52", hover_color="#187a43" if has else "#16743f")

    def _med_steps_ui(self):
        box = getattr(self, "_med_steps", None)
        if box is None or not box.winfo_exists():
            return
        for w in box.winfo_children():
            w.destroy()
        d = self.logic.med()
        waits = d.setdefault("waits", {})
        steps = self.logic.meditation_steps()
        opts = ["0", "0.25", "0.5", "0.75", "1", "1.5", "2", "3"]

        def wait_box(parent, name):
            if name not in waits:
                waits[name] = float(d.get("key_delay", 1.0))
            self._pick(parent, waits, name, opts, 52).pack(side="left")
            ctk.CTkLabel(parent, text="s", font=(FONT, 11), text_color="#a39d86").pack(side="left", padx=(1, 2))

        def key(parent, k, color="#b5e8c9"):
            ctk.CTkLabel(parent, text=f"→ {k.upper()}", font=(FONT, 12, "bold"), text_color=color).pack(side="left", padx=(2, 6))

        r1 = ctk.CTkFrame(box, fg_color="transparent"); r1.pack(fill="x", pady=1)
        ctk.CTkLabel(r1, text="Start:", width=70, anchor="w", font=(FONT, 12)).pack(side="left", padx=(3, 0))
        wait_box(r1, "start")
        for k, name in steps["away"]:
            key(r1, k); wait_box(r1, name)
        key(r1, d["key"], "#7ee0a6"); wait_box(r1, "sit")
        ctk.CTkLabel(r1, text="… until mana is full", font=(FONT, 12), text_color="#a39d86").pack(side="left", padx=4)
        r2 = ctk.CTkFrame(box, fg_color="transparent"); r2.pack(fill="x", pady=1)
        ctk.CTkLabel(r2, text="When full:", width=70, anchor="w", font=(FONT, 12)).pack(side="left", padx=(3, 0))
        key(r2, d["key"], "#7ee0a6"); wait_box(r2, "stand")
        for k, name in steps["back"]:
            key(r2, k); wait_box(r2, name)

    def test_mana(self):
        r = self.logic.mana_reading()
        if r is None:
            self.mana_lbl.configure(text="set the mana bar first", text_color="#f08a7e")
            return
        fill, left, right = r
        low = self.logic.mana_empty()
        state = "FULL" if right else ("would meditate" if low else "in use")
        self.mana_lbl.configure(text=f"mana {fill * 100:.0f}% · {state}",
                                text_color="#7ee0a6" if right else ("#e6b84f" if low else "#cfc6ab"))

    def build_aim_panel(self, parent):
        self._aim_sel = set()
        self._aim_mode = "move"
        card = ctk.CTkFrame(parent, **CARD); card.pack(fill="x", pady=4)
        head = ctk.CTkFrame(card, fg_color="transparent"); head.pack(fill="x", padx=10, pady=(6, 0))
        t = ctk.CTkLabel(head, text="Mouse aim", font=(FONT, 13, "bold"))
        t.pack(side="left")
        help_box(card, "Optional. Tick slots, then Pick spot. Order: move mouse → delay before → press → M2/M1 (if ticked) "
                       "→ delay after. At target = onto the creature set on the Target page, wherever it is at that "
                       "moment (looked up again before every cast). Clear = use wherever the mouse is.", t)
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=4)
        self.aim_chips_box = ctk.CTkFrame(row, fg_color="transparent", width=1, height=1)
        self.aim_chips_box.pack(side="left")
        ctk.CTkButton(row, text="Clear", width=70, **BTN, command=self.clear_aim).pack(side="right", padx=3)
        ctk.CTkButton(row, text="At target", width=90, **BTN, command=self.aim_at_target).pack(side="right", padx=3)
        ctk.CTkButton(row, text="Pick spot", width=100, height=28, **BLUE, command=self.pick_aim).pack(side="right", padx=3)
        self.aim_info = ctk.CTkLabel(card, text="", font=(FONT, 12), text_color="#cfc6ab", justify="left", anchor="w",
                                     wraplength=660)
        self.aim_info.pack(fill="x", padx=12, pady=(0, 6))
        self._build_aim_chips()

    def _build_aim_chips(self):
        for w in self.aim_chips_box.winfo_children():
            w.destroy()
        self._aim_chips = {}
        ctk.CTkLabel(self.aim_chips_box, text="Slots", font=(FONT, 12)).pack(side="left", padx=(0, 4))
        for slot, _ in enumerate(self.logic.moves(), start=1):
            b = ctk.CTkButton(self.aim_chips_box, text=str(slot), width=28, height=28, corner_radius=14,
                              font=(FONT, 12, "bold"), border_width=2, command=lambda s=slot: self.toggle_aim_slot(s))
            b.pack(side="left", padx=2)
            self._aim_chips[slot] = b
        self._aim_sel &= set(self._aim_chips)
        self._refresh_aim()

    def toggle_aim_slot(self, slot):
        self._aim_sel ^= {slot}
        self._refresh_aim()

    def pick_aim(self):
        if not self._aim_sel:
            self.log("Tick one or more slot numbers under Mouse aim first.")
            return
        slots = sorted(self._aim_sel)
        self._hide()

        def done(x, y):
            self.root.deiconify()
            for s in slots:
                self.logic.moves()[s - 1].update(mouse_mode=self._aim_mode, x=x, y=y)
            self.save()
            self.log(f"Aim spot ({x}, {y}) set for slot(s) {', '.join(map(str, slots))}.")
            self._aim_sel.clear()
            self._aim_changed(slots)
        PointSelector(done)

    def aim_at_target(self):
        if not self._aim_sel:
            self.log("Tick one or more slot numbers under Mouse aim first.")
            return
        slots = sorted(self._aim_sel)
        for s in slots:
            self.logic.moves()[s - 1]["mouse_mode"] = "target"
        self.save()
        c = self.logic.creature()
        self.log(f"Slot(s) {', '.join(map(str, slots))} now aim at '{self.logic.target().get('creature')}'"
                 + ("." if c.get("color1") else " - pick its colour on the Target page first."))
        self._aim_sel.clear()
        self._aim_changed(slots)

    def clear_aim(self):
        if not self._aim_sel:
            self.log("Tick the slots to clear first (they'll use wherever the mouse is).")
            return
        slots = sorted(self._aim_sel)
        for s in slots:
            self.logic.moves()[s - 1]["mouse_mode"] = "none"
        self.save()
        self._aim_sel.clear()
        self._aim_changed(slots)

    def _aim_changed(self, slots):
        self._refresh_aim()
        for s in slots:
            self._refresh_opts(s)
            self._update_summary(s)

    def _refresh_aim(self):
        moves = self.logic.moves()
        for slot, b in self._aim_chips.items():
            aimed = moves[slot - 1]["mouse_mode"] != "none"
            b.configure(fg_color="#1c8f52" if slot in self._aim_sel else "#2a3a33",
                        border_color="#4fd1c5" if aimed else "#2a3a33")
        groups = {}
        for slot, m in enumerate(moves, start=1):
            if m["mouse_mode"] == "target":
                groups.setdefault(("target",), []).append(str(slot))
            elif m["mouse_mode"] != "none":
                groups.setdefault((m["x"], m["y"], m["mouse_mode"]), []).append(str(slot))
        lines = [(f"at the target → slot {', '.join(s)}" if k == ("target",) else
                  f"({k[0]}, {k[1]}) {k[2]} → slot {', '.join(s)}") for k, s in groups.items()]
        self.aim_info.configure(text="   ·   ".join(lines) if lines else
                                "No aim set — every move uses wherever the mouse already is.")

    def build_cards(self):
        for w in self.cards_box.winfo_children():
            w.destroy()
        self.score_labels, self._cards = {}, {}
        self._cards_gen = gen = getattr(self, "_cards_gen", 0) + 1
        moves = list(enumerate(self.logic.moves(), start=1))

        def step(i=0):
            if gen != self._cards_gen:
                return
            try:
                if not self.cards_box.winfo_exists():
                    return
            except Exception:
                return
            for slot, m in moves[i:i + 2]:
                self._cards[slot] = self._make_card(slot, m)
                self._cards[slot]["frame"].pack(fill="x", pady=3)
            if i + 2 < len(moves):
                self.root.after(1, lambda: step(i + 2))
                return
            for w in self._cards.values():
                w["frame"].pack_forget()
            self._layout_cards()
            if hasattr(self, "aim_chips_box"):
                self._build_aim_chips()
            self.save()
        step()

    def _layout_cards(self):
        for slot, _ in self._ordered_moves():
            self._cards[slot]["frame"].pack(fill="x", pady=3)
        self._refresh_ranks()

    def _refresh_ranks(self):
        ordered = self._ordered_moves()
        for rank, (slot, m) in enumerate(ordered, start=1):
            w = self._cards[slot]
            state = (rank, m["enabled"], rank > 1, rank < len(ordered))
            if w.get("state") == state:
                continue
            w["state"] = state
            w["badge"].configure(text=str(rank), fg_color="#1c8f52" if m["enabled"] else "#34463d")
            w["up"].configure(text_color="#ffffff" if rank > 1 else "#6f7a6e")
            w["down"].configure(text_color="#ffffff" if rank < len(ordered) else "#6f7a6e")

    def toggle_options(self, slot):
        w, m = self._cards[slot], self.logic.moves()[slot - 1]
        if not m["enabled"] and slot not in self._expanded:
            return
        if slot in self._expanded:
            self._expanded.discard(slot)
            if w["opts"] is not None:
                w["opts"].pack_forget()
        else:
            self._expanded.add(slot)
            if w["opts"] is None:
                w["opts"] = self._make_opts(w["frame"], slot, m)
            w["opts"].pack(fill="x", padx=(40, 6), pady=(0, 6))
        self._style_card(slot)

    def toggle_enabled(self, slot, on):
        m = self.logic.moves()[slot - 1]
        self._set(m, "enabled", on)
        if not on and slot in self._expanded:
            self.toggle_options(slot)
        self._style_card(slot)
        self._refresh_ranks()

    def _style_card(self, slot):
        w, m = self._cards[slot], self.logic.moves()[slot - 1]
        open_ = slot in self._expanded
        w["gear"].configure(text="Less ▴" if open_ else "More ▾", fg_color="#1c8f52" if open_ else "#34463d",
                            text_color="#ffffff" if m["enabled"] else "#6f7a6e")
        self._update_summary(slot)

    def _update_summary(self, slot):
        w, m = self._cards.get(slot), self.logic.moves()[slot - 1]
        if not w:
            return
        if not m["enabled"]:
            text = "off"
        elif slot in self._expanded:
            text = ""
        else:
            text = self.move_summary(slot, m, self.logic.has_template(slot))
        w["summary"].configure(text=text)
        if text and text != "default":
            if not w["summary"].winfo_manager():
                w["summary"].pack(fill="x", padx=(40, 6), pady=(0, 6), after=w["top"])
        elif w["summary"].winfo_manager():
            w["summary"].pack_forget()

    @staticmethod
    def move_summary(slot, m, has_snapshot):
        parts = []
        if float(m.get("delay_before") or 0):
            parts.append(f"before {float(m['delay_before']):g}s")
        if float(m.get("delay_after") or 0):
            parts.append(f"after {float(m['delay_after']):g}s")
        if int(m.get("repeat") or 1) > 1:
            parts.append(f"×{m['repeat']} every {float(m.get('repeat_delay', 0.15)):g}s")
        if m.get("click"):
            parts.append(f"+ {SmartMacroLogic.click_name(m)} after {float(m.get('m1_delay', 0.3)):g}s")
        if has_snapshot and float(m.get("ready_at") or 0):
            parts.append(f"ready at {float(m['ready_at']):g}")
        if m.get("mouse_mode", "none") != "none":
            parts.append("aim")
        if not has_snapshot and float(m.get("cooldown") or 0):
            parts.append(f"cd {float(m['cooldown']):g}s")
        return " · ".join(parts) or "default"

    def _make_card(self, slot, m):
        arrow = dict(width=26, height=13, font=(FONT, 9), fg_color="#34463d", hover_color="#2a3a33")
        c = ctk.CTkFrame(self.cards_box, **CARD)
        r1 = ctk.CTkFrame(c, fg_color="transparent"); r1.pack(fill="x", padx=6, pady=6)
        badge = ctk.CTkLabel(r1, text="", width=26, height=26, corner_radius=13, font=(FONT, 13, "bold"),
                             text_color="#ffffff")
        badge.pack(side="left", padx=(0, 4))
        arrows = ctk.CTkFrame(r1, fg_color="transparent"); arrows.pack(side="left")
        up = ctk.CTkButton(arrows, text="▲", command=lambda: self.move_priority(m, -1), **arrow); up.pack()
        down = ctk.CTkButton(arrows, text="▼", command=lambda: self.move_priority(m, 1), **arrow); down.pack()
        cb = ctk.CTkCheckBox(r1, text=f"Slot {slot}", width=70, font=(FONT, 12, "bold"),
                             command=lambda: self.toggle_enabled(slot, bool(cb.get())))
        if m["enabled"]:
            cb.select()
        cb.pack(side="left", padx=(6, 0))
        self._entry(r1, m, "name", 120, placeholder="Name (optional)").pack(side="left", padx=4)
        ctk.CTkLabel(r1, text="Key", font=(FONT, 12)).pack(side="left", padx=(4, 2))
        self._pick(r1, m, "key", [str(i % 10) for i in range(1, 11)], 52, str).pack(side="left")
        has = self.logic.has_template(slot)
        gear = ctk.CTkButton(r1, text="More ▾", width=66, height=26, font=(FONT, 12), fg_color="#34463d",
                             hover_color="#2a3a33", command=lambda: self.toggle_options(slot))
        gear.pack(side="right", padx=2)
        score = ctk.CTkLabel(r1, text="" if has else "no img", width=64, font=(FONT, 12),
                             text_color="#f08a7e", image=self._thumb(slot))
        score.pack(side="right", padx=2)
        self.score_labels[slot] = score
        result = ctk.CTkLabel(r1, text="", width=1, font=(FONT, 12))
        result.pack(side="right", padx=(2, 4))
        self._test_labels = getattr(self, "_test_labels", {})
        self._test_labels[slot] = result
        score.configure(cursor="hand2")
        score.bind("<Button-1>", lambda e: self.show_snapshot(slot))
        summary = ctk.CTkLabel(c, text="", font=(FONT, 12), text_color="#cfc6ab", anchor="w", justify="left")
        tk.Misc.bind(c, "<Configure>", lambda e, s=summary: s.winfo_exists() and s.configure(
            wraplength=max(80, e.width - 60)), "+")
        self._cards[slot] = w = {"frame": c, "badge": badge, "up": up, "down": down, "gear": gear,
                                 "summary": summary, "opts": None, "top": r1}
        if slot in self._expanded and m["enabled"]:
            w["opts"] = self._make_opts(c, slot, m)
            w["opts"].pack(fill="x", padx=(40, 6), pady=(0, 6))
        self._style_card(slot)
        return w

    def _make_opts(self, parent, slot, m):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        refresh = lambda: self._update_summary(slot)

        def lab(row, t):
            ctk.CTkLabel(row, text=t, font=(FONT, 12)).pack(side="left", padx=(8, 2))
        delays = ["0", "0.05", "0.1", "0.2", "0.3", "0.5", "0.8", "1", "1.5", "2", "3"]
        r1 = ctk.CTkFrame(box, fg_color="transparent"); r1.pack(fill="x", pady=(0, 2))
        lab(r1, "Delay before (s)")
        self._pick(r1, m, "delay_before", delays, 64, on_save=refresh).pack(side="left")
        lab(r1, "Delay after (s)")
        self._pick(r1, m, "delay_after", delays, 64, on_save=refresh).pack(side="left")
        ctk.CTkLabel(r1, text="mouse move → before → key → click → after", font=(FONT, 11),
                     text_color="#cfc6ab").pack(side="left", padx=10)
        r2 = ctk.CTkFrame(box, fg_color="transparent"); r2.pack(fill="x", pady=(2, 0))
        lab(r2, "Repeat")
        gap = ctk.CTkFrame(r2, fg_color="transparent", width=1, height=1)

        def fill_gap():
            for w in gap.winfo_children():
                w.destroy()
            if int(m.get("repeat") or 1) > 1:
                ctk.CTkLabel(gap, text="every", font=(FONT, 12)).pack(side="left", padx=(6, 2))
                self._pick(gap, m, "repeat_delay", ["0.1", "0.15", "0.2", "0.25", "0.3", "0.5", "1"], 60,
                           on_save=refresh).pack(side="left")
                ctk.CTkLabel(gap, text="s", font=(FONT, 12)).pack(side="left", padx=(2, 0))
        self._pick(r2, m, "repeat", ["1", "2", "3", "4", "5"], 50, int, editable=False,
                   on_save=lambda: (fill_gap(), refresh())).pack(side="left")
        gap.pack(side="left")
        fill_gap()
        r3 = ctk.CTkFrame(box, fg_color="transparent"); r3.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(r3, text="", width=14).pack(side="left")
        self._m1_box(r3, m, on_save=refresh).pack(side="left")
        if self.logic.has_template(slot):
            lab(r2, "Ready at")
            self._pick(r2, m, "ready_at", ["off", "0.5", "0.6", "0.7", "0.75", "0.8", "0.85", "0.9", "0.95"], 64,
                       on_save=refresh).pack(side="left")
        if not self.logic.has_template(slot):
            lab(r2, "Cooldown (s)")
            self._pick(r2, m, "cooldown", ["off", "5", "10", "15", "20", "30", "45", "60"], 64, on_save=refresh).pack(side="left")

        return box

    def _refresh_opts(self, slot):
        w = self._cards.get(slot)
        if not w or w["opts"] is None:
            return
        w["opts"].destroy()
        w["opts"] = None
        if slot in self._expanded:
            w["opts"] = self._make_opts(w["frame"], slot, self.logic.moves()[slot - 1])
            w["opts"].pack(fill="x", padx=(40, 6), pady=(0, 6))

    def _thumb(self, slot, height=28):
        try:
            from PIL import Image
            path = self.logic.template_path(slot)
            if not os.path.exists(path):
                return None
            im = Image.open(path).convert("RGB")
            w = max(1, int(im.width * height / max(1, im.height)))
            return ctk.CTkImage(light_image=im, dark_image=im, size=(min(w, 64), height))
        except Exception:
            return None

    def draw_slot_box(self, slot):
        m = self.logic.moves()[slot - 1]
        self.log(f"Slot {slot}: drag a box around the INSIDE of its hotbar box (the skill must be ready).")

        def done():
            self.logic._templates.clear()
            self.snapshot([slot])
            if getattr(self, "_snap_win", None) is not None and self._snap_win.winfo_exists():
                self.view_snapshots()
        self.pick_region(m, "box", after=done)

    def reset_slot_box(self, slot):
        self.logic.moves()[slot - 1]["box"] = None
        self.save()
        self.logic._templates.clear()
        self.snapshot([slot])

    def show_snapshot(self, slot):
        path = self.logic.template_path(slot)
        if not os.path.exists(path):
            self.log(f"Slot {slot} has no snapshot yet - press (or to draw its box).")
            return
        try:
            from PIL import Image
            im = Image.open(path).convert("RGB")
        except Exception:
            return
        scale = max(1, min(6, 300 // max(1, max(im.width, im.height))))
        big = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        win = ctk.CTkToplevel(self.root)
        win.title(f"Slot {slot} snapshot ({im.width}x{im.height} px)")
        dialog_keys(win)
        win.transient(self.root); win.after(150, win.lift)
        ctk.CTkLabel(win, text="", image=ctk.CTkImage(light_image=big, dark_image=big, size=big.size)).pack(padx=12, pady=12)
        own = bool(self.logic.moves()[slot - 1].get("box"))
        ctk.CTkLabel(win, text=("Your own drawn box" if own else "Automatic box") + f" · {im.width}x{im.height} px",
                     font=(FONT, 11), text_color="#a39d86").pack(pady=(0, 10))

    def view_snapshots(self):
        old = getattr(self, "_snap_win", None)
        if old is not None and old.winfo_exists():
            old.destroy()
        win = ctk.CTkToplevel(self.root)
        win.title(f"Snapshots - {self.logic.active_loadout()}")
        dialog_keys(win)
        win.transient(self.root); win.after(150, win.lift)
        self._snap_win = win
        ctk.CTkLabel(win, text="What each slot looks like when READY (click one to see it big). Retake one while that "
                               "skill is off cooldown, or draw your own box around just the inside of its hotbar box.",
                     font=(FONT, 12), text_color="#cfc6ab").pack(anchor="w", padx=12, pady=(10, 6))
        grid = ctk.CTkFrame(win, fg_color="transparent"); grid.pack(padx=10, pady=(0, 10))
        moves = self.logic.moves()
        for i, m in enumerate(moves, start=1):
            cell = ctk.CTkFrame(grid, fg_color="#15201b", corner_radius=6)
            cell.grid(row=(i - 1) // 5, column=(i - 1) % 5, padx=4, pady=4)
            ctk.CTkLabel(cell, text=f"Slot {i}" + (f" · {m['name'][:12]}" if m.get("name") else ""),
                         font=(FONT, 11, "bold")).pack(padx=6, pady=(4, 2))
            img = self._thumb(i, height=72)
            pic = ctk.CTkLabel(cell, text="" if img else "no snapshot", image=img, width=90, height=72,
                               text_color="#f08a7e", cursor="hand2")
            pic.pack(padx=6)
            pic.bind("<Button-1>", lambda e, slot=i: self.show_snapshot(slot))

            def retake(slot=i):
                win.destroy()
                self.snapshot([slot])
                self.root.after(300, self.view_snapshots)
            ctk.CTkButton(cell, text="Retake", width=80, command=retake, **BTN).pack(padx=6, pady=(4, 2))

            def draw(slot=i):
                win.destroy()
                self.draw_slot_box(slot)
            ctk.CTkButton(cell, text="Draw box", width=80, command=draw, **BTN).pack(padx=6, pady=2)
            if m.get("box"):
                def auto(slot=i):
                    win.destroy()
                    self.reset_slot_box(slot)
                    self.root.after(300, self.view_snapshots)
                ctk.CTkButton(cell, text="↺ Auto box", width=80, command=auto, **BTN).pack(padx=6, pady=(2, 6))
            else:
                ctk.CTkLabel(cell, text="", height=4).pack()

    def snapshot_all(self):
        self.logic.clear_drawn_boxes()
        self.snapshot(None)

    def snapshot(self, slots):
        if not self.logic.slot_regions():
            self.log("Set the hotbar region first.")
            return
        self._hide()
        n = self.logic.capture_templates(slots)
        self.root.deiconify()
        self.log(f"Saved {n} ready snapshot(s).")
        for slot in (slots or list(self._cards)):
            self._refresh_snapshot(slot)

    def _refresh_snapshot(self, slot):
        w = self._cards.get(slot)
        if not w:
            return
        img = self._thumb(slot)
        self.score_labels[slot].configure(text="" if img else "no img", image=img, text_color="#f08a7e")
        if img is None:
            self.score_labels[slot]._image = None
        self._refresh_opts(slot)
        self._update_summary(slot)

    def test_rotation(self):
        scores = self.logic.read_slots()
        if not scores:
            self.log("Set the hotbar region first.")
            return
        for slot, s in scores.items():
            lbl = getattr(self, "_test_labels", {}).get(slot)
            if not lbl or not lbl.winfo_exists():
                continue
            thr = self.logic.slot_threshold(slot)
            if s is None:
                lbl.configure(text="no img", text_color="#f08a7e")
            else:
                lbl.configure(text=f"{'ready' if s >= thr else 'cd'} {s:.2f}/{thr:.2f}",
                              text_color="#7ee0a6" if s >= thr else "#e6b84f")
        pick = self.logic.pick_move(scores)
        self.log(f"Would cast: {pick[1]['name'] or 'slot ' + str(pick[0])}" if pick else "Nothing ready.")

    def auto_tune(self):
        if self.logic.running:
            self.log("Stop the macro first (F6), then Auto find hotbar.")
            return

        def run():
            from utils import go_to_roblox
            hwnd = go_to_roblox(self.log)
            if not hwnd:
                return
            self.logic._roblox_hwnd = hwnd
            if not self.logic.auto_find_hotbar():
                self.log("Couldn't find the hotbar in this Roblox window - set it with Hotbar region.")
                return
            self.root.after(0, lambda: (self.build_cards(), self.flash_slots()))
            self.log("Hotbar region moved onto your slots. If your skills changed, press Snapshot all "
                     "while they're all ready.")
        threading.Thread(target=run, daemon=True).start()

    def flash_slots(self):
        for o in self.overlays:
            o.destroy()
        self.overlays = [PersistentOverlay(*r, color="cyan") for r in self.logic.slot_regions()]
        self.root.after(2500, lambda: [o.destroy() for o in self.overlays])

    def build_combos(self):
        cc = self.cfg["combos"]
        p = self._page("Skill Combo")
        top = ctk.CTkFrame(p, **CARD); top.pack(fill="x", pady=4)
        t = ctk.CTkLabel(top, text="Skill Combo", font=(FONT, 16, "bold"), text_color="#1c8f52")
        t.pack(anchor="w", padx=10, pady=(8, 0))
        self._help_btn(top, "Skill Combo")
        help_box(top, "You press the trigger key, the steps play top to bottom. Every press is followed by its "
                      "wait, so skills have time to cast. 'Send trigger too' = your key still works normally.", t)
        row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=8, pady=6)
        self._switch(row, "Enabled", "combos").pack(side="left", padx=4)
        ctk.CTkButton(row, text="+ Add Combo", width=110, height=28, **BLUE, command=self.add_combo).pack(side="left", padx=4)

        self.combo_box = ctk.CTkFrame(p, fg_color="transparent")
        self.combo_box.pack(fill="x")
        for combo in cc["list"]:
            self._combo_card(self.combo_box, combo)
        self._empty_note(self.combo_box, cc["list"], "No combos yet - press + Add Combo, then set its trigger key and steps.")

    def _combos_changed(self):
        self.save()
        if self.logic.running and self.cfg["combos"]["enabled"]:
            self.logic._hook_combos()

    @staticmethod
    def _new_step():
        return {"key": "", "delay": 0.3, "repeat": 1, "mouse_mode": "none", "x": 0, "y": 0, "click": False}

    def add_combo(self):
        combo = {"enabled": True, "trigger": "", "passthrough": True, "steps": [self._new_step()]}
        self.cfg["combos"]["list"].append(combo)
        self._combos_changed()
        self.__dict__.setdefault("_open_combos", set()).add(id(combo))
        self._combo_card(self.combo_box, combo)

    def _combo_card(self, parent, combo):
        self._empty_note(parent, [combo], "")
        c = ctk.CTkFrame(parent, **CARD); c.pack(fill="x", pady=4)
        r = ctk.CTkFrame(c, fg_color="transparent"); r.pack(fill="x", padx=6, pady=6)
        en = ctk.CTkCheckBox(r, text="On", width=50, command=lambda: (self._set(combo, "enabled", bool(en.get())), self._combos_changed()))
        if combo.get("enabled", True):
            en.select()
        en.pack(side="left")
        ctk.CTkLabel(r, text="Trigger key", font=(FONT, 12, "bold")).pack(side="left", padx=(4, 2))
        self._entry(r, combo, "trigger", 50, lambda v: v.lower(), on_save=self._combos_changed).pack(side="left")
        pt = ctk.CTkCheckBox(r, text="Send trigger too",
                             command=lambda: (self._set(combo, "passthrough", bool(pt.get())), self._combos_changed()))
        if combo.get("passthrough", True):
            pt.select()
        pt.pack(side="left", padx=8)

        def remove():
            remove_obj(self.cfg["combos"]["list"], combo); self._combos_changed(); c.destroy()
            self._empty_note(parent, self.cfg["combos"]["list"], "No combos yet - press + Add Combo, then set its trigger key and steps.")
        ctk.CTkButton(r, text="Delete", width=60, height=26, **RED, command=remove).pack(side="right")

        opened = self.__dict__.setdefault("_open_combos", set())
        body = ctk.CTkFrame(c, fg_color="transparent")
        count = ctk.CTkLabel(r, text="", font=(FONT, 12), text_color="#a39d86")
        state = {"built": False}

        def show_count():
            n = len(combo["steps"])
            count.configure(text=f"{n} step{'s' if n != 1 else ''}")

        def build_body():
            steps_box = ctk.CTkFrame(body, fg_color="transparent"); steps_box.pack(fill="x")
            for step in combo["steps"]:
                self._step_row(steps_box, combo, step)

            def add_step():
                step = self._new_step()
                combo["steps"].append(step)
                self._combos_changed()
                self._step_row(steps_box, combo, step)
                show_count()
            ctk.CTkButton(body, text="+ Step", width=70, **BTN, command=add_step).pack(anchor="w", padx=10, pady=6)

        def set_open(on):
            if on and not state["built"]:
                state["built"] = True
                build_body()
            if on:
                body.pack(fill="x")
                opened.add(id(combo))
            else:
                body.pack_forget()
                opened.discard(id(combo))
            toggle.configure(text="Close" if on else "Steps", image=_chevron(on))
            show_count()
        toggle = ctk.CTkButton(r, text="", compound="right", width=78, height=26, font=(FONT, 12, "bold"),
                               fg_color=GREY, hover_color=GREY_HOVER, text_color="#e8dfc5",
                               command=lambda: set_open(not body.winfo_manager()))
        toggle.pack(side="right", padx=4)
        count.pack(side="right", padx=4)
        set_open(id(combo) in opened)

    def _step_row(self, box, combo, step):
        s = ctk.CTkFrame(box, fg_color="#101814", corner_radius=6); s.pack(fill="x", padx=10, pady=2)
        line = ctk.CTkFrame(s, fg_color="transparent"); line.pack(fill="x")
        s.num = ctk.CTkLabel(line, text=f"Step {index_obj(combo['steps'], step) + 1}", width=52, font=(FONT, 12, "bold"))
        s.num.pack(side="left", padx=4)

        def word(t):
            ctk.CTkLabel(line, text=t, font=(FONT, 12)).pack(side="left", padx=(6, 4))
        word("Press")
        key_box = self._pick(line, step, "key", [str(i % 10) for i in range(1, 11)], 92, str)
        key_box.pack(side="left", pady=4)

        def record():
            from utils import record_keys
            rec.configure(text="Press...")
            rec.focus_set()

            def done(name):
                def show():
                    try:
                        rec.configure(text="Record")
                        if name:
                            key_box.set(name)
                            self._set(step, "key", name)
                    except Exception:
                        pass
                self.root.after(0, show)
            record_keys(done)
        rec = ctk.CTkButton(line, text="Record", width=62, **BTN, command=record)
        rec.pack(side="left", padx=(4, 0))

        def wait_text(n=None):
            n = int(step.get("repeat") or 1) if n is None else n
            if step.get("click"):
                c = SmartMacroLogic.click_name(step)
                return f"{c} after each" if n > 1 else f"then {c} after"
            return "wait after each" if n > 1 else "then wait"

        def set_times(v):
            n = int(v.split()[0])
            self._set(step, "repeat", n)
            wait_word.configure(text=wait_text(n))
        times = ctk.CTkOptionMenu(line, values=["1 time", "2 times", "3 times", "4 times", "5 times"], width=88, height=26,
                                  command=set_times)
        n = int(step.get("repeat") or 1)
        times.set(f"{n} time" + ("s" if n > 1 else ""))
        times.pack(side="left", padx=4)
        wait_word = ctk.CTkLabel(line, text=wait_text(n), font=(FONT, 12), width=104, anchor="w")
        wait_word.pack(side="left", padx=(6, 4))
        wait = ctk.CTkComboBox(line, values=["0 s", "0.1 s", "0.2 s", "0.3 s", "0.5 s", "1 s", "1.5 s", "2 s"],
                               width=78, height=26)

        def set_wait(v=None):
            v = (wait.get() if v is None else v).replace("s", "").strip()
            self._set(step, "delay", v or 0, float)
        wait.configure(command=set_wait)
        wait._entry.bind("<FocusOut>", lambda e: set_wait()); wait._entry.bind("<Return>", lambda e: set_wait())
        save_while_typing(wait._entry, set_wait)
        wait.set(f"{float(step.get('delay') or 0):g} s")
        wait.pack(side="left")

        def rm():
            remove_obj(combo["steps"], step); self._combos_changed(); s.destroy()
            for i, row in enumerate(box.winfo_children(), start=1):
                row.num.configure(text=f"Step {i}")
        ctk.CTkButton(line, text="X", width=26, height=24, **RED, command=rm).pack(side="right", padx=4)

        extra_lbl = ctk.CTkLabel(line, text="", font=(FONT, 12), text_color="#cfc6ab")
        more = {"box": None, "open": False}

        def recap():
            wait_word.configure(text=wait_text())
            parts = []
            if step.get("mouse_mode", "none") != "none":
                parts.append("aim")
            extra_lbl.configure(text="" if more["open"] else " · ".join(parts))

        def toggle():
            if more["box"] is None:
                b = ctk.CTkFrame(s, fg_color="transparent")
                self._m1_box(b, step, on_save=recap, with_delay=False).pack(side="left", padx=(62, 2))
                ctk.CTkLabel(b, text="Mouse", font=(FONT, 12)).pack(side="left", padx=(10, 2))
                for w in self._mouse_controls(b, step, on_save=recap, on_mode=recap):
                    w.pack(side="left", padx=2)
                ctk.CTkLabel(b, text="Aim wait (s)", font=(FONT, 12)).pack(side="left", padx=(10, 2))
                self._pick(b, step, "aim_wait", ["0.05", "0.1", "0.2", "0.3", "0.5", "1"], 64).pack(side="left")
                more["box"] = b
            more["open"] = not more["open"]
            if not more["open"]:
                more["box"].pack_forget(); gear.configure(text="More ▾", fg_color="#34463d")
            else:
                more["box"].pack(fill="x", pady=(0, 4)); gear.configure(text="Less ▴", fg_color="#1c8f52")
            recap()
        gear = ctk.CTkButton(line, text="More ▾", width=66, height=24, font=(FONT, 12), fg_color="#34463d",
                             hover_color="#2a3a33", command=toggle)
        gear.pack(side="right", padx=2)
        extra_lbl.pack(side="left", padx=10)
        recap()

    def build_target(self):
        lg = self.logic
        t = lg.target()
        p = self._page("Target")
        top = ctk.CTkFrame(p, **CARD); top.pack(fill="x", pady=4)
        title = ctk.CTkLabel(top, text="Target", font=(FONT, 16, "bold"), text_color="#1c8f52")
        title.pack(anchor="w", padx=10, pady=(8, 0))
        help_box(top, "With Target on, the Rotation only casts while your creature is on screen. It waits; when the "
                      "creature shows up it presses the 'When it's found' keys once, waits, then casts your moves for "
                      "as long as it stays. When it's gone it stops casting at once, presses the 'When it's gone' keys "
                      "once and waits for the next one. Your Start / Stop key turns it all on and off.", title)
        row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=8, pady=6)
        sw = ctk.CTkSwitch(row, text="Only cast while the target is on screen", font=(FONT, 13, "bold"),
                           command=lambda: (self._set(t, "enabled", bool(sw.get())), self._refresh_setup_line()))
        if t.get("enabled"):
            sw.select()
        sw.pack(side="left", padx=4)
        self._mark("skill_target_on", sw)
        row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkLabel(row, text="Start / Stop key", font=(FONT, 12, "bold")).pack(side="left", padx=4)
        self._entry(row, self.cfg, "hotkey", 80, lambda v: v.lower(),
                    on_save=lambda: (self.register_hotkeys(), self.on_state_change(self.logic.running))).pack(side="left")
        ctk.CTkLabel(row, text="e.g. x, f6 or ctrl+x (the same key as on Settings)", font=(FONT, 11),
                     text_color="#a39d86").pack(side="left", padx=8)

        self._creature_card(p)
        tc = ctk.CTkFrame(p, **CARD); tc.pack(fill="x", pady=4)
        tt = ctk.CTkLabel(tc, text="Timing", font=(FONT, 14, "bold"), text_color="#f3ecd8")
        tt.pack(anchor="w", padx=10, pady=(8, 0))
        help_box(tc, "Look every: how often it checks. Found after: that many looks in a row must see it (one stray "
                     "match doesn't count). Gone after: that long without seeing it (a spell flashing over it doesn't "
                     "count as gone). Wait before skills: after the 'found' keys.", tt)
        for items in ((("Look every", "poll", ["0.1", "0.25", "0.5", "1"], float, "s"),
                       ("Found after", "seen_after", ["1", "2", "3", "5"], int, "looks")),
                      (("Gone after", "lost_after", ["0.5", "1", "1.5", "3", "5"], float, "s"),
                       ("Wait before skills", "start_delay", ["0", "0.25", "0.5", "1", "2"], float, "s"))):
            row = ctk.CTkFrame(tc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
            for label, key, values, cast, unit in items:
                ctk.CTkLabel(row, text=label, width=120, anchor="w", font=(FONT, 12)).pack(side="left", padx=4)
                self._pick(row, t, key, values, 64, cast).pack(side="left")
                ctk.CTkLabel(row, text=unit, width=40, anchor="w", font=(FONT, 12)).pack(side="left", padx=4)
        ctk.CTkFrame(tc, fg_color="transparent", height=6).pack()

        for key, label, hint in (("found_steps", "When it's found", "Played once when the creature shows up, before "
                                  "the first skill (e.g. lock on, take out your grimoire). Stops early if it leaves."),
                                 ("lost_steps", "When it's gone", "Played once when the creature is gone, then it "
                                  "waits for the next one (e.g. put things away, walk back, jump).")):
            kc = ctk.CTkFrame(p, **CARD); kc.pack(fill="x", pady=4)
            kt = ctk.CTkLabel(kc, text=label, font=(FONT, 14, "bold"), text_color="#f3ecd8")
            kt.pack(anchor="w", padx=10, pady=(8, 0))
            help_box(kc, hint + " Each step: the key, how many times, and the wait after it - like Skill Combo.", kt)
            holder = {"steps": t.setdefault(key, [])}
            box = ctk.CTkFrame(kc, fg_color="transparent"); box.pack(fill="x")
            for step in holder["steps"]:
                self._step_row(box, holder, step)
            empty = "No keys - nothing is pressed here."
            self._empty_note(box, holder["steps"], empty)

            def add(holder=holder, box=box):
                st = self._new_step()
                holder["steps"].append(st)
                self.save()
                self._empty_note(box, [st], "")
                self._step_row(box, holder, st)
            ctk.CTkButton(kc, text="+ Step", width=70, **BTN, command=add).pack(anchor="w", padx=10, pady=6)

    def _creature_card(self, p):
        lg = self.logic
        t = lg.target()
        cc = ctk.CTkFrame(p, **CARD); cc.pack(fill="x", pady=4)
        ct = ctk.CTkLabel(cc, text="Creature", font=(FONT, 14, "bold"), text_color="#f3ecd8")
        ct.pack(anchor="w", padx=10, pady=(8, 0))
        help_box(cc, "Easiest: press Teach and drag a box around the creature - it picks the colours and numbers "
                     "itself and checks them on that screen. Each Teach saves a look, and it's found when any look fits: "
                     "by day what stands out from the background, at night its colours. So teach it once by day and "
                     "once at night, then press Test to see what it picks. If it picks a tree or a black figure, "
                     "set an Area around where the creature usually is. The Area has to be much bigger than the "
                     "creature. "
                     "By hand: Colour 1 = something only this creature has (e.g. its glowing marks). Colour 2 (optional) = "
                     "a colour that sits right on it (e.g. its body): then both must be together, so a red rock next "
                     "to a dark wall doesn't count. Tol = how much the colour may change with fog / night (higher = "
                     "looser). Area = where to look (empty = the whole Roblox window). Test looks once, right now.", ct)
        row = ctk.CTkFrame(cc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=6)
        names = lambda: list(t.setdefault("creatures", {})) or [t.get("creature") or "Creature 1"]
        lg.creature()
        menu = ctk.CTkOptionMenu(row, values=names(), width=180, height=26,
                                 command=lambda v: (self._set(t, "creature", v), self.build_target()))
        menu.set(t.get("creature") or names()[0])
        menu.pack(side="left", padx=4)

        def new():
            n = self._ask("New creature", "Name of the creature to look for:")
            if n and n.strip():
                t["creature"] = n.strip()
                lg.creature()
                self.save(); self.build_target()

        def rename():
            old = t.get("creature")
            n = self._ask("Rename creature", f"New name for '{old}':", old)
            if n and n.strip() and n.strip() not in t["creatures"]:
                t["creatures"][n.strip()] = t["creatures"].pop(old)
                t["creature"] = n.strip()
                self.save(); self.build_target()

        def delete():
            if len(t["creatures"]) <= 1:
                self.log("That's the only creature - make another one first.")
                return
            t["creatures"].pop(t.get("creature"), None)
            t["creature"] = next(iter(t["creatures"]))
            self.save(); self.build_target()
        for text, fn in (("New", new), ("Rename", rename), ("Delete", delete)):
            ctk.CTkButton(row, text=text, width=64, **BTN, command=fn).pack(side="left", padx=2)
        c = lg.creature()
        row = ctk.CTkFrame(cc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(2, 4))
        n_ex = len(c.get("looks") or [])
        tb = ctk.CTkButton(row, text="Teach" if not n_ex else "Teach again", width=110, **BLUE,
                           command=self._teach_target)
        tb.pack(side="left", padx=4)
        self._mark("skill_target_teach", tb)
        if n_ex:
            ctk.CTkButton(row, text="Forget looks", width=110, **BTN, command=self._forget_teach).pack(side="left", padx=2)
        ctk.CTkLabel(row, text=(f"{n_ex} look{'s' if n_ex != 1 else ''} saved" if n_ex else
                                "drag a box around it in game"), font=(FONT, 12), text_color="#a39d86").pack(side="left", padx=8)
        note = ctk.CTkFrame(cc, fg_color="transparent", height=1); note.pack(fill="x", padx=12)
        self._target_note = ctk.CTkLabel(note, text="", font=(FONT, 12), text_color="#cfc6ab", wraplength=560,
                                         justify="left", anchor="w")
        self._target_say(getattr(self, "_target_msg", ""))
        for i in (1, 2):
            row = ctk.CTkFrame(cc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(row, text=f"Colour {i}" + (" (optional)" if i == 2 else ""), width=120, anchor="w",
                         font=(FONT, 12, "bold")).pack(side="left", padx=4)
            col = c.get(f"color{i}")
            sw_ = ctk.CTkLabel(row, text="", width=26, height=22, corner_radius=4,
                               fg_color=("#%02x%02x%02x" % tuple(col)) if col else "#2a3a33")
            sw_.pack(side="left", padx=4)
            pick = ctk.CTkButton(row, text="Pick", width=56, **BLUE, command=lambda i=i: self._pick_target_color(i))
            pick.pack(side="left", padx=2)
            self._mark(f"skill_target_c{i}", pick)
            if i == 2 and col:
                ctk.CTkButton(row, text="Clear", width=56, **BTN,
                              command=lambda: (self._set(c, "color2", None), self.build_target())).pack(side="left", padx=2)
            ctk.CTkLabel(row, text="Tol", font=(FONT, 12)).pack(side="left", padx=(10, 2))
            self._pick(row, c, f"tol{i}", ["20", "30", "40", "60", "80"], 60, int).pack(side="left")
            ctk.CTkLabel(row, text="min px", font=(FONT, 12)).pack(side="left", padx=(10, 2))
            self._pick(row, c, f"min{i}", ["3", "5", "10", "20", "40"], 60, int).pack(side="left")
        row = ctk.CTkFrame(cc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(4, 8))
        area = c.get("area") or [0, 0, 0, 0]
        has = area[2] > area[0] and area[3] > area[1]
        ctk.CTkButton(row, text="Set area", width=80, **BLUE,
                      command=lambda: self.pick_region(c, "area", after=self.build_target)).pack(side="left", padx=4)
        if has:
            ctk.CTkButton(row, text="Clear", width=56, **BTN,
                          command=lambda: (self._set(c, "area", [0, 0, 0, 0]), self.build_target())).pack(side="left")
        ctk.CTkLabel(row, text=f"area {area[2] - area[0]}x{area[3] - area[1]}" if has else "whole window",
                     font=(FONT, 12), text_color="#7ee0a6" if has else "#a39d86").pack(side="left", padx=6)
        ctk.CTkButton(row, text="Test", width=60, **BTN, command=self._test_target).pack(side="right", padx=4)
        row = ctk.CTkFrame(cc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(0, 8))
        me = ctk.CTkCheckBox(row, text="Skip my own character (middle of the screen)", font=(FONT, 12),
                             command=lambda: self._set(c, "skip_me", bool(me.get())))
        if c.get("skip_me", True):
            me.select()
        me.pack(side="left", padx=4)

    def _teach_target(self):
        import creature
        from overlay import Overlay, take_frozen, clip_to_shot
        from logic_events import roblox_windows
        lg = self.logic
        name = lg.target().get("creature")
        self._hide()

        def say(msg):
            self.log(msg)
            self._target_say(msg)

        def done(x1, y1, x2, y2):
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            win = next(([w.left, w.top, w.left + w.width, w.top + w.height] for w in roblox_windows()
                        if w.left <= cx < w.left + w.width and w.top <= cy < w.top + w.height), None)
            if win is None:
                self.root.deiconify()
                say("Teach: drag the box inside the Roblox window.")
                return
            win = clip_to_shot(win)
            img = take_frozen(win)
            self.root.deiconify()
            if img is None:
                say("Teach: couldn't get the picture - try again.")
                return
            W, H = win[2] - win[0], win[3] - win[1]
            c = lg.creature()
            a = list(c.get("area") or [0, 0, 0, 0])
            area = [a[0] - win[0], a[1] - win[1], a[2] - win[0], a[3] - win[1]] if a[2] > a[0] and a[3] > a[1] else None
            sample = {"img": img, "box": [x1 - win[0], y1 - win[1], x2 - win[0], y2 - win[1]], "full_size": (W, H),
                      "skip_me_window": [0, 0, W, H] if c.get("skip_me", True) else None}
            self.log(f"Teach: learning '{name}'...")

            def work():
                looks, report = creature.teach_look(sample, area)

                def show():
                    if looks:
                        pic = creature.look_picture(img, sample["box"])
                        for look in looks:
                            if look.get("color1"):
                                c.update(look)
                            look["pic"] = pic
                        c.setdefault("looks", []).extend(looks)
                        del c["looks"][:-creature.MAX_LOOKS]
                        self.save()
                        say("Teach: " + report + " Teach it again at night too.")
                    else:
                        say("Teach: " + report)
                    self.build_target()
                self.root.after(0, show)
            threading.Thread(target=work, daemon=True).start()
        Overlay(done)

    def _forget_teach(self):
        def after(n):
            self.save()
            self.log(f"Teach: {n} look{'s' if n != 1 else ''} forgotten.")
            self.build_target()
        forget_looks_window(self.root, self.logic.creature(), after)

    def _pick_target_color(self, i):
        from overlay import ColorPicker
        c = self.logic.creature()
        self._hide()

        def done(color):
            self.root.deiconify()
            self._set(c, f"color{i}", [int(v) for v in color][:3])
            self.log(f"Target colour {i}: {tuple(int(v) for v in color)[:3]}")
            self.build_target()
        ColorPicker(done)

    def _test_target(self):
        def run():
            from utils import focus_roblox
            focus_roblox(getattr(self.logic, "_roblox_hwnd", 0))
            time.sleep(0.5)
            box, said = self.logic.test_target()
            self.root.after(0, lambda: self._test_result(box, said))
        threading.Thread(target=run, daemon=True).start()

    def _test_result(self, box, said):
        self._target_say(said)
        if box:
            from overlay import outline_box
            sides = outline_box(*box)
            self.root.after(3000, lambda: [s.destroy() for s in sides])

    def _target_say(self, msg):
        self._target_msg = msg
        try:
            if msg:
                self._target_note.configure(text=msg)
                self._target_note.pack(anchor="w", pady=(0, 4))
        except Exception:
            pass

    def build_items(self):
        it = self.cfg["items"]
        p = self._page("Items")
        top = ctk.CTkFrame(p, **CARD); top.pack(fill="x", pady=4)
        t = ctk.CTkLabel(top, text="Item Auto-Use (OCR) — optional", font=(FONT, 16, "bold"), text_color="#1c8f52")
        t.pack(anchor="w", padx=10, pady=(8, 0))
        self._help_btn(top, "Items")
        help_box(top, "Watches the pickup messages (like \"Obtained Copper!\"). When a name from your list shows up, "
                      "its key is pressed once, then M1 to use it. Drag the scan area over where those messages appear.", t)
        row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=8, pady=6)
        self._switch(row, "Enabled", "items").pack(side="left", padx=4)
        has_area = self.logic.items_region() is not None
        ctk.CTkButton(row, text="Set Scan Area", width=130, height=28, **BLUE,
                      command=lambda: self.pick_region(it, "region", after=self.build_items)).pack(side="left", padx=4)
        ctk.CTkLabel(row, text="set" if has_area else "not set", font=(FONT, 12),
                     text_color="#7ee0a6" if has_area else "#f08a7e").pack(side="left", padx=(0, 6))
        ctk.CTkButton(row, text="Test OCR", width=80, **BTN, command=self.test_items).pack(side="left", padx=4)
        ctk.CTkButton(row, text="+ Add Item", width=90, height=28, **BLUE, command=self.add_item).pack(side="left", padx=4)
        self.ocr_label = ctk.CTkLabel(top, text="", font=(FONT, 12), text_color="#cfc6ab", wraplength=560, justify="left")
        self.ocr_label.pack(anchor="w", padx=10, pady=(0, 6))

        self.items_box = ctk.CTkFrame(p, fg_color="transparent")
        self.items_box.pack(fill="x")
        for item in it["list"]:
            self._item_row(item)
        self._empty_note(self.items_box, it["list"], "No items yet - press + Add Item and type the name from the pickup message.")

    def _empty_note(self, box, items, text):
        old = getattr(box, "_empty", None)
        if old is not None and old.winfo_exists():
            old.destroy()
        box._empty = None
        if not items:
            box._empty = ctk.CTkLabel(box, text=text, font=(FONT, 12), text_color="#a39d86")
            box._empty.pack(anchor="w", padx=12, pady=8)

    def _item_row(self, item):
        it = self.cfg["items"]
        self._empty_note(self.items_box, [item], "")
        card = ctk.CTkFrame(self.items_box, **CARD); card.pack(fill="x", pady=2)
        r = ctk.CTkFrame(card, fg_color="transparent"); r.pack(fill="x", pady=(4, 0))
        ctk.CTkButton(r, text="Delete", width=60, height=26, **RED,
                      command=lambda: (remove_obj(it["list"], item), self.save(), card.destroy(),
                                       self._empty_note(self.items_box, it["list"], "No items yet - press + Add Item and type the name from the pickup message."))).pack(side="right", padx=6)
        en = ctk.CTkCheckBox(r, text="", width=24, command=lambda: self._set(item, "enabled", bool(en.get())))
        if item.get("enabled", True):
            en.select()
        en.pack(side="left", padx=6)
        ctk.CTkLabel(r, text="When").pack(side="left", padx=(4, 4))
        self._entry(r, item, "name", 180, placeholder="e.g. Copper").pack(side="left", fill="x", expand=True, pady=2)
        ctk.CTkLabel(r, text="shows up, press").pack(side="left", padx=(8, 4))
        self._pick(r, item, "key", [str(i % 10) for i in range(1, 11)], 56, str).pack(side="left", padx=(0, 4))
        r2 = ctk.CTkFrame(card, fg_color="transparent"); r2.pack(fill="x", padx=(36, 6), pady=(2, 6))
        m1 = ctk.CTkCheckBox(r2, text="then M1", width=80, font=(FONT, 12),
                             command=lambda: self._set(item, "click", bool(m1.get())))
        if item.get("click", True):
            m1.select()
        m1.pack(side="left")
        ctk.CTkLabel(r2, text="cooldown").pack(side="left", padx=(12, 4))
        self._pick(r2, item, "cooldown", ["0", "1", "2", "3", "5", "10", "15", "30", "60"], 60, float).pack(side="left")
        ctk.CTkLabel(r2, text="s").pack(side="left", padx=(3, 0))

    def add_item(self):
        item = {"enabled": True, "name": "", "key": "9", "click": True, "cooldown": 0}
        self.cfg["items"]["list"].append(item)
        self.save()
        self._item_row(item)

    def test_items(self):
        if not self.logic.items_region():
            self.log("Set the scan area first."); return
        self.ocr_label.configure(text="Reading…")

        def run():
            texts = self.logic.read_items()
            hits = [i["name"] for i in self.logic.match_items(texts)]
            why = self.logic.utils.ocr_error if self.logic.utils.ocr_reader is False else ""
            if why:
                self._safe_set(self.ocr_label, text=why)
                return
            self._safe_set(self.ocr_label,
                           text=f"Read: {', '.join(texts) or '(nothing)'}\nMatches: {', '.join(hits) or 'none'}")
        threading.Thread(target=run, daemon=True).start()

    def build_settings(self):
        p = self._page("Settings")
        c = ctk.CTkFrame(p, **CARD); c.pack(fill="x", pady=4)
        t = ctk.CTkLabel(c, text="General", font=(FONT, 16, "bold"), text_color="#1c8f52")
        t.pack(anchor="w", padx=10, pady=8)
        self._help_btn(c, "Settings")
        help_box(c, "The hotkey starts every feature whose 'Enabled' switch is on. Rotation and Skill Combo "
                    "can't both be on - enabling one turns the other off. Items works with either.", t)
        r = ctk.CTkFrame(c, fg_color="transparent"); r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(r, text="Start / Stop hotkey", font=(FONT, 12, "bold")).pack(side="left", padx=4)
        self._entry(r, self.cfg, "hotkey", 80, lambda v: v.lower(),
                    on_save=lambda: (self.register_hotkeys(), self.on_state_change(self.logic.running))).pack(side="left")
        only = ctk.BooleanVar(value=bool(self.settings.get("hotkeys_roblox_only", False)))

        def set_only():
            import utils
            self.settings.set("hotkeys_roblox_only", bool(only.get()))
            utils.HOTKEYS_ROBLOX_ONLY = bool(only.get())
        ctk.CTkCheckBox(c, text="Hotkey only works while Roblox is the focused window", variable=only,
                        font=(FONT, 12), command=set_only).pack(anchor="w", padx=14, pady=2)
        sw = ctk.CTkSwitch(c, text="Only act while Roblox is the focused window", font=(FONT, 12),
                           command=lambda: self._set(self.cfg, "only_when_focused", bool(sw.get())))
        if self.cfg.get("only_when_focused", True):
            sw.select()
        sw.pack(anchor="w", padx=12, pady=(4, 6))
        r2 = ctk.CTkFrame(c, fg_color="transparent"); r2.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkLabel(r2, text="Rotation match strictness", font=(FONT, 12, "bold")).pack(side="left", padx=4)
        self._pick(r2, self.cfg["rotation"], "threshold", ["0.75", "0.8", "0.85", "0.9", "0.95"], 70).pack(side="left")
        ctk.CTkLabel(r2, text="used by slots without their own 'Ready at'", font=(FONT, 12),
                     text_color="#cfc6ab").pack(side="left", padx=6)
        ctk.CTkFrame(c, fg_color="transparent", height=6).pack()

    def _help_btn(self, card, section):
        ctk.CTkButton(card, text="▶ Video", width=64, height=24, font=(FONT, 11, "bold"), fg_color="#2a3a33",
                      hover_color="#34463d", text_color="#ff6b6b",
                      command=lambda: links.open_link("video_skill")).place(relx=1.0, x=-10, y=8, anchor="ne")

    def _refresh_loadout_menu(self):
        self.loadout_menu.configure(values=list(self.logic.loadouts()))
        self.loadout_menu.set(self.logic.active_loadout())

    def _ask(self, title, text, initial=""):
        d = ctk.CTkInputDialog(title=title, text=text)
        try:
            if initial:
                d._entry.insert(0, initial)
        except Exception:
            pass
        name = d.get_input()
        return name.strip() if name else ""

    def _loadout_switched(self):
        was_running = self.logic.running
        if was_running:
            self.logic.stop()
        self._expanded.clear()
        if self.cfg["rotation"]["enabled"] and self.cfg["combos"]["enabled"]:
            self.cfg["combos"]["enabled"] = False
        self._switches.clear()
        self.build_rotation()
        for name, fn in (("Skill Combo", self.build_combos), ("Items", self.build_items), ("Timers", self.build_timers)):
            if name not in self.nav._builders:
                fn()
        self._refresh_loadout_menu()
        self.save()
        if was_running:
            self.logic.start()

    def select_loadout(self, name):
        if self.logic.switch_loadout(name):
            self._loadout_switched()
            self.log(f"Loadout '{name}' loaded.")

    def new_loadout(self):
        name = self._ask("New loadout", "Name for the new loadout (starts empty - your current loadout stays saved):")
        if not name:
            return
        if name in self.logic.loadouts():
            self.log(f"A loadout called '{name}' already exists.")
            return
        self.logic.new_loadout(name)
        self._loadout_switched()
        self.log(f"Loadout '{name}' created (empty) — press Auto find hotbar, then Snapshot all.")

    def export_loadout(self):
        from tkinter import filedialog, messagebox
        import setup_share
        name = self.logic.active_loadout()
        path = filedialog.asksaveasfilename(parent=self.root, title="Export loadout", defaultextension=".zip",
                                            initialfile=f"{name} - Skill loadout.zip",
                                            filetypes=[("Setup file", "*.zip")])
        if not path:
            return
        try:
            setup_share.export_skill_loadout(self.logic, path)
        except Exception as e:
            messagebox.showerror("Export", f"Couldn't export: {e}", parent=self.root); return
        self.log(f"Loadout '{name}' exported (settings + snapshots) - send the .zip to share it.")

    def import_loadout(self):
        from tkinter import filedialog, messagebox
        import setup_share
        path = filedialog.askopenfilename(parent=self.root, title="Import loadout",
                                          filetypes=[("Setup file", "*.zip")])
        if not path:
            return
        try:
            name = setup_share.import_skill_loadout(self.logic, path)
        except Exception as e:
            messagebox.showerror("Import", f"Couldn't import: {e}", parent=self.root); return
        self._loadout_switched()
        messagebox.showinfo("Import", f"Loadout '{name}' added and selected (your other loadouts are untouched)."
                                      "\n\nIts hotbar region and snapshots come from the other person's screen - "
                                      "if yours differs, press Auto find hotbar, then Snapshot all.",
                            parent=self.root)

    def rename_loadout(self):
        old = self.logic.active_loadout()
        new = self._ask("Rename loadout", f"New name for '{old}':", old)
        if not new or new == old:
            return
        if not self.logic.rename_loadout(old, new):
            self.log(f"Couldn't rename — '{new}' already exists.")
            return
        self._refresh_loadout_menu()
        self.log(f"Renamed to '{new}'.")

    def delete_loadout(self):
        from tkinter import messagebox
        name = self.logic.active_loadout()
        if len(self.logic.loadouts()) == 1:
            self.log("That's the only loadout — make another one before deleting this.")
            return
        if not messagebox.askyesno("Delete loadout", f"Delete loadout '{name}' and its snapshots?", parent=self.root):
            return
        self.logic.delete_loadout(name)
        self._loadout_switched()
        self.log(f"Deleted '{name}'. Now using '{self.logic.active_loadout()}'.")

    def register_hotkeys(self):
        import utils
        utils.clear_keys()
        from utils import on_hotkey
        utils.HOTKEYS_ROBLOX_ONLY = bool(self.settings.get("hotkeys_roblox_only", False))
        try:
            on_hotkey(self.cfg["hotkey"], always=lambda: bool(self.logic.running),
                      callback=lambda: self.logic.toggle() if self.logic.running
                      else self.root.after(0, self._start_with_check))
        except Exception as e:
            self.log(f"Hotkey error: {e}")
        if self.logic.running and self.cfg["combos"]["enabled"]:
            self.logic._hook_combos()

    def on_state_change(self, running):
        if not running:
            try:
                from overlay import show_action
                self.root.after(0, lambda: show_action(self, "", False))
            except Exception:
                pass
        hk = self.cfg["hotkey"].upper()
        def apply():
            if not self.toggle_btn.winfo_exists():
                return
            if running:
                self.toggle_btn.configure(text=f"■ Stop ({hk})", fg_color="#d9483b", hover_color="#b83a2f")
            else:
                self.toggle_btn.configure(text=f"▶ Start ({hk})", fg_color="#1f9d55", hover_color="#187a43")
        self.root.after(0, apply)

    def _safe_set(self, widget, **kw):
        def apply():
            try:
                if widget.winfo_exists():
                    widget.configure(**kw)
            except Exception:
                pass
        try:
            self.root.after(0, apply)
        except Exception:
            pass

    def log(self, msg):
        self._safe_set(self.status_label, text=f"Status: {msg}")
        try:
            self.root.after(0, lambda m=msg: self._remember(m))
        except Exception:
            pass
        try:
            from overlay import show_action
            self.root.after(0, lambda m=msg: show_action(self, m, bool(self.logic.running)))
        except Exception:
            pass
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode("ascii", "replace").decode())

    def _remember(self, msg):
        entry = (time.strftime("%H:%M:%S"), str(msg), msg_kind(msg))
        self._recent.append(entry)
        panel = getattr(self, "run_panel", None)
        if panel is not None:
            panel.add(entry)

    def build_run(self):
        from gui import open_log_file
        tab = self.nav.tab("Logs")
        self.run_panel = RunPanel(tab, self.root, lambda: self.logic.running,
                                  [("Casts", lambda: sum(self.logic.cast_count.values()))],
                                  self.logic.setup_problems, lambda go: self.point_to(*go),
                                  lambda: open_log_file(self.root), self._recent)
        self.run_panel.pack(fill="both", expand=True, padx=8, pady=8)

    def go_back(self):
        self.logic.stop()
        if getattr(self, "ok_page", None):
            self.ok_page.close()
        from utils import clear_keys
        clear_keys()
        if self.on_back:
            self.on_back()

    def exit_app(self):
        self.logic.stop()
        if getattr(self, "ok_page", None):
            self.ok_page.close()
        self.root.destroy()

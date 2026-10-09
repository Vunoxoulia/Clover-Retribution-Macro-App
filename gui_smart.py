import time
import threading
import webbrowser
import customtkinter as ctk
import keyboard

SKILL_VIDEO = "https://youtu.be/CwSAvulD4Ac"
from settings import SpatialSettings
from overlay import Overlay, PointSelector, PersistentOverlay
from logic_smart import SmartMacroLogic
from gui_guide import SetupGuide
from gui import SidebarNav, NAV_ICONS

NAV_ICONS.update({"Rotation": "🔁", "Skill Combo": "⚔", "Items": "🧪", "Settings": "⚙"})

CARD = dict(fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
BTN = dict(height=26, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")
BLUE = dict(fg_color="#0d6efd", hover_color="#0b5ed7")
RED = dict(fg_color="#842029", hover_color="#6a1a21")
MOUSE_MODES = ["none", "move"]


# Steps/items/combos can be identical dicts, and list.index/remove match by content.
# These match the exact object so a row always edits / deletes its own entry.
def index_obj(lst, obj):
    return next(i for i, x in enumerate(lst) if x is obj)


def remove_obj(lst, obj):
    del lst[index_obj(lst, obj)]


class SmartMacroGUI:
    def __init__(self, root, title="Skill Macro", on_back=None, **_):
        self.root = root
        self.on_back = on_back
        self.root.title(title)
        self.root.geometry("920x720")
        self.settings = SpatialSettings()
        self.logic = SmartMacroLogic(self)
        self.overlays = []
        self._expanded = set()       # move cards whose ⚙ options are open
        self._sfs = {}               # page name -> its persistent scroll frame
        self._switches = {}          # section -> its Enabled switch
        self._cards = {}             # slot -> widgets of its move card
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        if self.cfg["rotation"]["enabled"] and self.cfg["combos"]["enabled"]:
            self.cfg["combos"]["enabled"] = False      # older settings could have both on
            self.save()
        self.setup_ui()
        self.register_hotkeys()

    @property
    def cfg(self):
        return self.logic.cfg

    def save(self):
        self.settings.save()

    # ---------- shell ----------
    def setup_ui(self):
        ctk.set_appearance_mode("dark")
        self.nav = SidebarNav(self.root, self.root.title())
        bar = ctk.CTkFrame(self.nav.content, **CARD)
        bar.pack(fill="x", pady=(0, 8))
        self.toggle_btn = ctk.CTkButton(bar, text="", width=170, font=("Arial", 13, "bold"), command=self.logic.toggle)
        self.toggle_btn.pack(side="left", padx=8, pady=8)
        self.status_label = ctk.CTkLabel(bar, text="Status: idle", font=("Arial", 12, "bold"), anchor="w")
        ctk.CTkButton(bar, text="❓ Setup Guide", width=120, font=("Arial", 12, "bold"), fg_color="#0dcaf0",
                      hover_color="#31d2f2", text_color="#000000", command=lambda: self.open_guide()).pack(side="right", padx=8)
        self.status_label.pack(side="left", fill="x", expand=True, padx=8)

        # Loadouts: saved builds (moves, aim, combos, items + snapshots), like the Mining routes
        lb = ctk.CTkFrame(self.nav.content, **CARD); lb.pack(fill="x", pady=(0, 8))
        btn = dict(height=28, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")
        ctk.CTkLabel(lb, text="🎒 Loadout:", font=("Arial", 13, "bold")).pack(side="left", padx=(10, 6), pady=6)
        self.loadout_menu = ctk.CTkOptionMenu(lb, values=["Default"], width=180, command=self.select_loadout)
        self.loadout_menu.pack(side="left")
        ctk.CTkButton(lb, text="New", width=50, command=self.new_loadout, **btn).pack(side="left", padx=(6, 2))
        ctk.CTkButton(lb, text="Rename", width=64, command=self.rename_loadout, **btn).pack(side="left", padx=2)
        ctk.CTkButton(lb, text="Delete", width=56, command=self.delete_loadout,
                      **{**btn, "hover_color": "#bb2d3b"}).pack(side="left", padx=2)
        ctk.CTkLabel(lb, text="= a saved build",
                     font=("Arial", 12), text_color="#ced4da").pack(side="left", padx=10)
        self._refresh_loadout_menu()
        self.on_state_change(False)

        NAV_ICONS["Events"] = "📣"
        NAV_ICONS["OK Popup"] = "🔔"
        for name in ["Rotation", "Skill Combo", "Items", "Events", "OK Popup", "Settings"]:
            self.nav.add(name)
        if self.on_back:
            ctk.CTkButton(self.nav.footer, text="←  Back to Menu", anchor="w", height=32, fg_color="transparent",
                          border_color="#495057", border_width=1, hover_color="#2b3035", text_color="#e9ecef",
                          command=self.go_back).pack(fill="x")
        self.build_rotation()
        self.build_combos()
        self.build_items()
        self.build_settings()
        from gui_events import EventsPage
        self.events_page = EventsPage(self.nav.tab("Events"), self.root, self.settings)
        from gui import OkPopupPage
        self.ok_page = OkPopupPage(self.root, self.nav.tab("OK Popup"), self.settings, self.log)

    def _page(self, name):
        """The page's scroll area, created once (rebuilding it is slow and loses the scroll position)."""
        if name not in self._sfs:
            sf = ctk.CTkScrollableFrame(self.nav.tab(name), fg_color="transparent")
            sf.pack(fill="both", expand=True, padx=4, pady=4)
            # customtkinter's scrollbar forces update_idletasks() on every redraw, which makes Tk re-run
            # the whole page layout several times per click. The scrollbar doesn't need it.
            sb_canvas = getattr(getattr(sf, "_scrollbar", None), "_canvas", None)
            if sb_canvas is not None:
                sb_canvas.update_idletasks = lambda: None
            self._sfs[name] = sf
        sf = self._sfs[name]
        for w in sf.winfo_children():
            w.destroy()
        return sf

    # Rotation (AFK) and Skill Combo (manual) can't run together: turning one on turns the other off.
    EXCLUSIVE = {"rotation": "combos", "combos": "rotation"}

    def _switch(self, parent, text, section):
        sw = ctk.CTkSwitch(parent, text=text, font=("Arial", 13, "bold"),
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
        if self.logic.running:                      # apply right away
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
        e = ctk.CTkEntry(parent, width=width, font=("Arial", 12), placeholder_text=placeholder)
        if d.get(key) not in (None, ""):
            e.insert(0, str(d[key]))

        def commit(_=None):
            if self._set(d, key, e.get().strip(), cast) and on_save:
                on_save()
        e.bind("<FocusOut>", commit)
        e.bind("<Return>", commit)
        return e

    def _xy_text(self, d):
        return f"({d.get('x', 0)}, {d.get('y', 0)})"

    def _mouse_controls(self, parent, d, on_save=None, on_mode=None):
        lbl = ctk.CTkLabel(parent, text=self._xy_text(d), font=("Arial", 12), text_color="#ced4da", width=80)

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

    def _m1_box(self, parent, d, on_save=None):
        """'then M1' tick box: one left click right after the key (like Items)."""
        from logic_smart import SmartMacroLogic
        SmartMacroLogic.migrate_click(d)
        box = ctk.CTkCheckBox(parent, text="then M1", width=80, font=("Arial", 12))
        box.configure(command=lambda: (self._set(d, "click", bool(box.get())), on_save and on_save()))
        if d.get("click"):
            box.select()
        return box

    def _hide(self):
        self.root.withdraw()
        self.root.update()
        time.sleep(0.2)

    def pick_region(self, d, key, after=None):
        self._hide()

        def done(x1, y1, x2, y2):
            self.root.deiconify()
            d[key] = [x1, y1, x2, y2]
            self.save()
            if after:
                after()
        Overlay(done)

    # ---------- rotation ----------
    def _pick(self, parent, d, key, values, width=70, cast=float, editable=True, on_save=None):
        """Dropdown of common values; editable ones also accept a typed value."""
        def commit(v=None):
            v = (combo.get() if v is None else v).strip()
            if self._set(d, key, 0 if v in ("off", "—") else v, cast) and on_save:
                on_save()
        cur = d.get(key, values[0])
        cur = "off" if "off" in values and not cur else str(cur)
        if editable:
            combo = ctk.CTkComboBox(parent, values=values, width=width, height=26, command=commit)
            combo._entry.bind("<FocusOut>", lambda e: commit())
            combo._entry.bind("<Return>", lambda e: commit())
        else:
            combo = ctk.CTkOptionMenu(parent, values=values, width=width, height=26, command=commit)
        combo.set(cur)
        return combo

    def _ordered_moves(self):
        """Moves sorted by priority, with priorities normalised to 1..n."""
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
            # Move just this one card next to its neighbour instead of re-packing the whole list
            a["frame"].pack_configure(**({"before": b["frame"]} if delta < 0 else {"after": b["frame"]}))
            self._refresh_ranks()

    def build_rotation(self):
        rot = self.cfg["rotation"]
        p = self._page("Rotation")
        top = ctk.CTkFrame(p, **CARD); top.pack(fill="x", pady=4)
        head = ctk.CTkFrame(top, fg_color="transparent"); head.pack(fill="x", padx=10, pady=(8, 0))
        ctk.CTkLabel(head, text="AFK Skill Rotation", font=("Arial", 16, "bold"), text_color="#0d6efd").pack(side="left")
        self._switch(head, "Enabled", "rotation").pack(side="left", padx=16)
        self._help_btn(top, "Rotation")
        ctk.CTkLabel(top, text="Casts the highest READY move (top of the list first). READY = its icon matches the snapshot.",
                     font=("Arial", 12), text_color="#ced4da").pack(anchor="w", padx=10)
        row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 8))
        ctk.CTkButton(row, text="① 🔲 Hotbar region", width=140, height=28, **BLUE,
                      command=lambda: self.pick_region(rot, "region")).pack(side="left", padx=3)
        ctk.CTkLabel(row, text="② Slots", font=("Arial", 12, "bold")).pack(side="left", padx=(8, 2))
        self._pick(row, rot, "slot_count", [str(i) for i in range(1, 11)], 56, int, editable=False,
                   on_save=self.build_cards).pack(side="left")
        ctk.CTkButton(row, text="③ 📸 Snapshot all", width=140, height=28, **BLUE,
                      command=self.snapshot_all).pack(side="left", padx=(10, 3))
        ctk.CTkButton(row, text="Show", width=56, **BTN, command=self.flash_slots).pack(side="right", padx=3)
        ctk.CTkButton(row, text="Test", width=56, **BTN, command=self.test_rotation).pack(side="right", padx=3)
        ctk.CTkButton(row, text="🪄 Auto-tune", width=100, height=28, **BLUE,
                      command=self.auto_tune).pack(side="right", padx=3)

        self.build_aim_panel(p)
        self.cards_box = ctk.CTkFrame(p, fg_color="transparent")
        self.cards_box.pack(fill="x", pady=(4, 0))
        self.build_cards()

    # ---------- shared mouse aim ----------
    def build_aim_panel(self, parent):
        """Tick several slots and give them one aim spot in one go; Clear = use wherever the mouse is."""
        self._aim_sel = set()
        self._aim_mode = "move"
        card = ctk.CTkFrame(parent, **CARD); card.pack(fill="x", pady=4)
        head = ctk.CTkFrame(card, fg_color="transparent"); head.pack(fill="x", padx=10, pady=(6, 0))
        ctk.CTkLabel(head, text="🎯 Mouse aim", font=("Arial", 13, "bold")).pack(side="left")
        ctk.CTkLabel(head, text="optional — tick slots, then Pick spot. Order: move mouse → delay before → press → M1 (if ticked) → delay after.",
                     font=("Arial", 12), text_color="#ced4da").pack(side="left", padx=8)
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=4)
        self.aim_chips_box = ctk.CTkFrame(row, fg_color="transparent", width=1, height=1)
        self.aim_chips_box.pack(side="left")
        ctk.CTkButton(row, text="✖ Clear", width=70, **BTN, command=self.clear_aim).pack(side="right", padx=3)
        ctk.CTkButton(row, text="🎯 Pick spot", width=100, height=28, **BLUE, command=self.pick_aim).pack(side="right", padx=3)
        self.aim_info = ctk.CTkLabel(card, text="", font=("Arial", 12), text_color="#ced4da", justify="left", anchor="w",
                                     wraplength=660)
        self.aim_info.pack(fill="x", padx=12, pady=(0, 6))
        self._build_aim_chips()

    def _build_aim_chips(self):
        for w in self.aim_chips_box.winfo_children():
            w.destroy()
        self._aim_chips = {}
        ctk.CTkLabel(self.aim_chips_box, text="Slots", font=("Arial", 12)).pack(side="left", padx=(0, 4))
        for slot, _ in enumerate(self.logic.moves(), start=1):
            b = ctk.CTkButton(self.aim_chips_box, text=str(slot), width=28, height=28, corner_radius=14,
                              font=("Arial", 12, "bold"), border_width=2, command=lambda s=slot: self.toggle_aim_slot(s))
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
        """Chip colours (blue = ticked, cyan ring = has a spot) and the 'which slots aim where' list."""
        moves = self.logic.moves()
        for slot, b in self._aim_chips.items():
            aimed = moves[slot - 1]["mouse_mode"] != "none"
            b.configure(fg_color="#0d6efd" if slot in self._aim_sel else "#343a40",
                        border_color="#0dcaf0" if aimed else "#343a40")
        groups = {}
        for slot, m in enumerate(moves, start=1):
            if m["mouse_mode"] != "none":
                groups.setdefault((m["x"], m["y"], m["mouse_mode"]), []).append(str(slot))
        lines = [f"({x}, {y}) {mode} → slot {', '.join(s)}" for (x, y, mode), s in groups.items()]
        self.aim_info.configure(text="   ·   ".join(lines) if lines else
                                "No aim set — every move uses wherever the mouse already is.")

    def build_cards(self):
        """(Re)create every move card — only needed when the slot count changes."""
        for w in self.cards_box.winfo_children():
            w.destroy()
        self.score_labels, self._cards = {}, {}
        for slot, m in enumerate(self.logic.moves(), start=1):
            self._cards[slot] = self._make_card(slot, m)
        self._layout_cards()
        if hasattr(self, "aim_chips_box"):
            self._build_aim_chips()                  # slot count may have changed
        self.save()

    def _layout_cards(self):
        """Put the existing cards in priority order and refresh their rank badges / arrows."""
        for slot, _ in self._ordered_moves():
            self._cards[slot]["frame"].pack(fill="x", pady=3)
        self._refresh_ranks()

    def _refresh_ranks(self):
        """Update rank badges and ▲▼ states, touching only widgets whose value changed."""
        ordered = self._ordered_moves()
        for rank, (slot, m) in enumerate(ordered, start=1):
            w = self._cards[slot]
            state = (rank, m["enabled"], rank > 1, rank < len(ordered))
            if w.get("state") == state:
                continue
            w["state"] = state
            w["badge"].configure(text=str(rank), fg_color="#0d6efd" if m["enabled"] else "#495057")
            # Dim instead of state="disabled": changing a CTkButton's state costs ~300 ms each
            w["up"].configure(text_color="#ffffff" if rank > 1 else "#6c757d")
            w["down"].configure(text_color="#ffffff" if rank < len(ordered) else "#6c757d")

    def toggle_options(self, slot):
        w, m = self._cards[slot], self.logic.moves()[slot - 1]
        if not m["enabled"] and slot not in self._expanded:
            return                                   # ⚙ is greyed out while the slot is off
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
        w["gear"].configure(text="⚙ ▴" if open_ else "⚙ ▾", fg_color="#0d6efd" if open_ else "#495057",
                            text_color="#ffffff" if m["enabled"] else "#6c757d")
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

    @staticmethod
    def move_summary(slot, m, has_snapshot):
        """One-line recap of a move's non-default options, shown while its card is folded."""
        parts = []
        if float(m.get("delay_before") or 0):
            parts.append(f"before {float(m['delay_before']):g}s")
        if float(m.get("delay_after") or 0):
            parts.append(f"after {float(m['delay_after']):g}s")
        if int(m.get("repeat") or 1) > 1:
            parts.append(f"×{m['repeat']} every {float(m.get('repeat_delay', 0.15)):g}s")
        if m.get("click"):
            parts.append("+ M1")
        if has_snapshot and float(m.get("ready_at") or 0):
            parts.append(f"ready at {float(m['ready_at']):g}")
        if m.get("mouse_mode", "none") != "none":
            parts.append("🎯 aim")
        if not has_snapshot and float(m.get("cooldown") or 0):
            parts.append(f"cd {float(m['cooldown']):g}s")
        return " · ".join(parts) or "default"

    def _make_card(self, slot, m):
        arrow = dict(width=26, height=13, font=("Arial", 9), fg_color="#495057", hover_color="#343a40")
        c = ctk.CTkFrame(self.cards_box, **CARD)
        r1 = ctk.CTkFrame(c, fg_color="transparent"); r1.pack(fill="x", padx=6, pady=6)
        badge = ctk.CTkLabel(r1, text="", width=26, height=26, corner_radius=13, font=("Arial", 13, "bold"),
                             text_color="#ffffff")
        badge.pack(side="left", padx=(0, 4))
        arrows = ctk.CTkFrame(r1, fg_color="transparent"); arrows.pack(side="left")
        up = ctk.CTkButton(arrows, text="▲", command=lambda: self.move_priority(m, -1), **arrow); up.pack()
        down = ctk.CTkButton(arrows, text="▼", command=lambda: self.move_priority(m, 1), **arrow); down.pack()
        cb = ctk.CTkCheckBox(r1, text=f"Slot {slot}", width=70, font=("Arial", 12, "bold"),
                             command=lambda: self.toggle_enabled(slot, bool(cb.get())))
        if m["enabled"]:
            cb.select()
        cb.pack(side="left", padx=(6, 0))
        self._entry(r1, m, "name", 120, placeholder="Name (optional)").pack(side="left", padx=4)
        ctk.CTkLabel(r1, text="Key", font=("Arial", 12)).pack(side="left", padx=(4, 2))
        self._pick(r1, m, "key", [str(i % 10) for i in range(1, 11)], 52, str).pack(side="left")
        has = self.logic.has_template(slot)
        gear = ctk.CTkButton(r1, text="⚙ ▾", width=44, height=26, font=("Arial", 12), fg_color="#495057",
                             hover_color="#343a40", command=lambda: self.toggle_options(slot))
        gear.pack(side="right", padx=2)
        ctk.CTkButton(r1, text="📸", width=32, command=lambda: self.snapshot([slot]), **BTN).pack(side="right", padx=2)
        score = ctk.CTkLabel(r1, text="✔" if has else "no img", width=64, font=("Arial", 12),
                             text_color="#75b798" if has else "#ea868f")
        score.pack(side="right", padx=2)
        self.score_labels[slot] = score
        summary = ctk.CTkLabel(r1, text="", font=("Arial", 12), text_color="#ced4da", anchor="w")
        summary.pack(side="left", padx=8, fill="x", expand=True)
        self._cards[slot] = w = {"frame": c, "badge": badge, "up": up, "down": down, "gear": gear,
                                 "summary": summary, "opts": None}
        if slot in self._expanded and m["enabled"]:
            w["opts"] = self._make_opts(c, slot, m)
            w["opts"].pack(fill="x", padx=(40, 6), pady=(0, 6))
        self._style_card(slot)
        return w

    def _make_opts(self, parent, slot, m):
        """The ⚙ panel of one card (built the first time it's opened)."""
        box = ctk.CTkFrame(parent, fg_color="transparent")
        refresh = lambda: self._update_summary(slot)

        def lab(row, t):
            ctk.CTkLabel(row, text=t, font=("Arial", 12)).pack(side="left", padx=(8, 2))
        delays = ["0", "0.05", "0.1", "0.2", "0.3", "0.5", "0.8", "1", "1.5", "2", "3"]
        r1 = ctk.CTkFrame(box, fg_color="transparent"); r1.pack(fill="x", pady=(0, 2))
        lab(r1, "⏱ Delay before (s)")
        self._pick(r1, m, "delay_before", delays, 64, on_save=refresh).pack(side="left")
        lab(r1, "⏱ Delay after (s)")
        self._pick(r1, m, "delay_after", delays, 64, on_save=refresh).pack(side="left")
        ctk.CTkLabel(r1, text="mouse → before → key → after", font=("Arial", 11),
                     text_color="#ced4da").pack(side="left", padx=10)
        r2 = ctk.CTkFrame(box, fg_color="transparent"); r2.pack(fill="x", pady=(2, 0))
        lab(r2, "Repeat")
        gap = ctk.CTkFrame(r2, fg_color="transparent", width=1, height=1)   # "every [x] s", only when Repeat > 1

        def fill_gap():
            for w in gap.winfo_children():
                w.destroy()
            if int(m.get("repeat") or 1) > 1:
                ctk.CTkLabel(gap, text="every", font=("Arial", 12)).pack(side="left", padx=(6, 2))
                self._pick(gap, m, "repeat_delay", ["0.1", "0.15", "0.2", "0.25", "0.3", "0.5", "1"], 60,
                           on_save=refresh).pack(side="left")
                ctk.CTkLabel(gap, text="s", font=("Arial", 12)).pack(side="left", padx=(2, 0))
        self._pick(r2, m, "repeat", ["1", "2", "3", "4", "5"], 50, int, editable=False,
                   on_save=lambda: (fill_gap(), refresh())).pack(side="left")
        gap.pack(side="left")
        fill_gap()
        self._m1_box(r2, m, on_save=refresh).pack(side="left", padx=(12, 0))
        if self.logic.has_template(slot):
            lab(r2, "Ready at")
            self._pick(r2, m, "ready_at", ["off", "0.5", "0.6", "0.7", "0.75", "0.8", "0.85", "0.9", "0.95"], 64,
                       on_save=refresh).pack(side="left")
        if not self.logic.has_template(slot):
            lab(r2, "Cooldown (s)")
            self._pick(r2, m, "cooldown", ["off", "5", "10", "15", "20", "30", "45", "60"], 64, on_save=refresh).pack(side="left")

        return box

    def _refresh_opts(self, slot):
        """Rebuild one card's ⚙ panel (its rows depend on snapshot / aim), keeping it open if it was."""
        w = self._cards.get(slot)
        if not w or w["opts"] is None:
            return
        w["opts"].destroy()
        w["opts"] = None
        if slot in self._expanded:
            w["opts"] = self._make_opts(w["frame"], slot, self.logic.moves()[slot - 1])
            w["opts"].pack(fill="x", padx=(40, 6), pady=(0, 6))

    def snapshot_all(self):
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
        """Update one card after its snapshot changed (status + whether Cooldown is offered)."""
        w = self._cards.get(slot)
        if not w:
            return
        has = self.logic.has_template(slot)
        self.score_labels[slot].configure(text="✔" if has else "no img", text_color="#75b798" if has else "#ea868f")
        self._refresh_opts(slot)                     # Cooldown row depends on the snapshot
        self._update_summary(slot)

    def test_rotation(self):
        scores = self.logic.read_slots()
        if not scores:
            self.log("Set the hotbar region first.")
            return
        for slot, s in scores.items():
            lbl = self.score_labels.get(slot)
            if not lbl:
                continue
            thr = self.logic.slot_threshold(slot)
            if s is None:
                lbl.configure(text="no img", text_color="#ea868f")
            else:
                lbl.configure(text=f"{'ready' if s >= thr else 'cd'} {s:.2f}/{thr:.2f}",
                              text_color="#75b798" if s >= thr else "#ffc107")
        pick = self.logic.pick_move(scores)
        self.log(f"Would cast: {pick[1]['name'] or 'slot ' + str(pick[0])}" if pick else "Nothing ready.")

    def auto_tune(self):
        """One button: find the hotbar in the Roblox window you click into (filled slots only),
        snapshot it, then cast each move once (ready → cooldown) to learn its own 'Ready at'."""
        if self.logic.running:
            self.log("Stop the macro first (F6), then Auto-tune.")
            return
        self.log("Auto-tune: click into the Roblox window you'll AFK in - starts in 3 s. It finds the hotbar, "
                 "waits for each move to be ready, snapshots it and casts it once.")

        def run():
            time.sleep(3)
            if not self.logic._focused():
                self.log("Auto-tune cancelled: Roblox wasn't the focused window.")
                return
            found = self.logic.auto_find_hotbar()
            if not found:
                # don't tune a region that may be wrong: that would overwrite good snapshots
                self.log("Auto-tune stopped: couldn't find the hotbar in this Roblox window. "
                         "Set it with ① 🔲 Hotbar region, then Auto-tune again.")
                return
            self.root.after(0, lambda: (self.build_cards(), self.flash_slots()))   # show where it found the slots
            time.sleep(1.0)
            time.sleep(0.5)
            res = self.logic.auto_tune(alive=lambda: not self.logic.running)
            ok = [s for s, (r, _) in res.items() if r == "ok"]
            why = {"busy": "icon never stopped changing", "same": "nothing changed after its key (did it cast?)",
                   "skip": "no key"}
            bad = [f"slot {s}: {why.get(r, r)}" for s, (r, _) in res.items() if r != "ok"]
            self.log(f"Auto-tune done: {len(ok)}/{len(res)} slot(s) tuned"
                     + (f" ({'; '.join(bad)})" if bad else "") + ". Press Test to check.")
            self.root.after(300, lambda: [self._refresh_snapshot(s) for s in res if s in self._cards])
        threading.Thread(target=run, daemon=True).start()

    def flash_slots(self):
        for o in self.overlays:
            o.destroy()
        self.overlays = [PersistentOverlay(*r, color="cyan") for r in self.logic.slot_regions()]
        self.root.after(2500, lambda: [o.destroy() for o in self.overlays])

    # ---------- combos ----------
    def build_combos(self):
        cc = self.cfg["combos"]
        p = self._page("Skill Combo")
        top = ctk.CTkFrame(p, **CARD); top.pack(fill="x", pady=4)
        ctk.CTkLabel(top, text="Skill Combo", font=("Arial", 16, "bold"), text_color="#0d6efd").pack(anchor="w", padx=10, pady=(8, 0))
        self._help_btn(top, "Skill Combo")
        ctk.CTkLabel(top, text="You press the trigger key, the steps play top to bottom. Every press is followed by its "
                               "wait, so skills have time to cast. 'Send trigger too' = your key still works normally.",
                     font=("Arial", 12), text_color="#ced4da", wraplength=560, justify="left").pack(anchor="w", padx=10)
        row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=8, pady=6)
        self._switch(row, "Enabled", "combos").pack(side="left", padx=4)
        ctk.CTkButton(row, text="+ Add Combo", width=110, height=28, **BLUE, command=self.add_combo).pack(side="left", padx=4)

        self.combo_box = ctk.CTkFrame(p, fg_color="transparent")
        self.combo_box.pack(fill="x")
        for combo in cc["list"]:
            self._combo_card(self.combo_box, combo)

    def _combos_changed(self):
        self.save()
        if self.logic.running and self.cfg["combos"]["enabled"]:
            self.logic._hook_combos()

    @staticmethod
    def _new_step():
        return {"key": "", "delay": 0.1, "repeat": 1, "mouse_mode": "none", "x": 0, "y": 0, "click": False}

    def add_combo(self):
        combo = {"enabled": True, "trigger": "", "passthrough": True, "steps": [self._new_step()]}
        self.cfg["combos"]["list"].append(combo)
        self._combos_changed()
        self._combo_card(self.combo_box, combo)

    def _combo_card(self, parent, combo):
        c = ctk.CTkFrame(parent, **CARD); c.pack(fill="x", pady=4)
        r = ctk.CTkFrame(c, fg_color="transparent"); r.pack(fill="x", padx=6, pady=6)
        en = ctk.CTkCheckBox(r, text="On", width=50, command=lambda: (self._set(combo, "enabled", bool(en.get())), self._combos_changed()))
        if combo.get("enabled", True):
            en.select()
        en.pack(side="left")
        ctk.CTkLabel(r, text="Trigger key", font=("Arial", 12, "bold")).pack(side="left", padx=(4, 2))
        self._entry(r, combo, "trigger", 50, lambda v: v.lower(), on_save=self._combos_changed).pack(side="left")
        pt = ctk.CTkCheckBox(r, text="Send trigger too",
                             command=lambda: (self._set(combo, "passthrough", bool(pt.get())), self._combos_changed()))
        if combo.get("passthrough", True):
            pt.select()
        pt.pack(side="left", padx=8)

        def remove():
            remove_obj(self.cfg["combos"]["list"], combo); self._combos_changed(); c.destroy()
        ctk.CTkButton(r, text="Delete", width=60, height=26, **RED, command=remove).pack(side="right")

        steps_box = ctk.CTkFrame(c, fg_color="transparent"); steps_box.pack(fill="x")
        for step in combo["steps"]:
            self._step_row(steps_box, combo, step)

        def add_step():
            step = self._new_step()
            combo["steps"].append(step)
            self._combos_changed()
            self._step_row(steps_box, combo, step)
        ctk.CTkButton(c, text="+ Step", width=70, **BTN, command=add_step).pack(anchor="w", padx=10, pady=6)

    def _step_row(self, box, combo, step):
        """One step, read as a sentence: Press [key] [N times], then wait [s].  ⚙ = hold click / mouse."""
        s = ctk.CTkFrame(box, fg_color="#1a1d20", corner_radius=6); s.pack(fill="x", padx=10, pady=2)
        line = ctk.CTkFrame(s, fg_color="transparent"); line.pack(fill="x")
        s.num = ctk.CTkLabel(line, text=f"Step {index_obj(combo['steps'], step) + 1}", width=52, font=("Arial", 12, "bold"))
        s.num.pack(side="left", padx=4)

        def word(t):
            ctk.CTkLabel(line, text=t, font=("Arial", 12)).pack(side="left", padx=(6, 4))
        word("Press")
        self._pick(line, step, "key", [str(i % 10) for i in range(1, 11)], 56, str).pack(side="left", pady=4)
        def wait_text(n):
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
        wait_word = ctk.CTkLabel(line, text=wait_text(n), font=("Arial", 12), width=104, anchor="w")
        wait_word.pack(side="left", padx=(6, 4))
        wait = ctk.CTkComboBox(line, values=["0 s", "0.1 s", "0.2 s", "0.3 s", "0.5 s", "1 s", "1.5 s", "2 s"],
                               width=78, height=26)

        def set_wait(v=None):
            v = (wait.get() if v is None else v).replace("s", "").strip()
            self._set(step, "delay", v or 0, float)
        wait.configure(command=set_wait)
        wait._entry.bind("<FocusOut>", lambda e: set_wait()); wait._entry.bind("<Return>", lambda e: set_wait())
        wait.set(f"{float(step.get('delay') or 0):g} s")
        wait.pack(side="left")

        def rm():
            remove_obj(combo["steps"], step); self._combos_changed(); s.destroy()
            for i, row in enumerate(box.winfo_children(), start=1):      # renumber the rest
                row.num.configure(text=f"Step {i}")
        ctk.CTkButton(line, text="✕", width=26, height=24, **RED, command=rm).pack(side="right", padx=4)

        # Extras (hold click / mouse) folded away like the Rotation cards
        extra_lbl = ctk.CTkLabel(line, text="", font=("Arial", 12), text_color="#ced4da")
        more = {"box": None, "open": False}

        def recap():
            parts = []
            if step.get("click"):
                parts.append("+ M1")
            if step.get("mouse_mode", "none") != "none":
                parts.append("🎯 aim")
            extra_lbl.configure(text="" if more["open"] else " · ".join(parts))

        def toggle():
            if more["box"] is None:
                b = ctk.CTkFrame(s, fg_color="transparent")
                self._m1_box(b, step, on_save=recap).pack(side="left", padx=(62, 2))
                ctk.CTkLabel(b, text="Mouse", font=("Arial", 12)).pack(side="left", padx=(10, 2))
                for w in self._mouse_controls(b, step, on_save=recap, on_mode=recap):
                    w.pack(side="left", padx=2)
                ctk.CTkLabel(b, text="Aim wait (s)", font=("Arial", 12)).pack(side="left", padx=(10, 2))
                self._pick(b, step, "aim_wait", ["0.05", "0.1", "0.2", "0.3", "0.5", "1"], 64).pack(side="left")
                more["box"] = b
            more["open"] = not more["open"]
            if not more["open"]:
                more["box"].pack_forget(); gear.configure(text="⚙ ▾", fg_color="#495057")
            else:
                more["box"].pack(fill="x", pady=(0, 4)); gear.configure(text="⚙ ▴", fg_color="#0d6efd")
            recap()
        gear = ctk.CTkButton(line, text="⚙ ▾", width=44, height=24, font=("Arial", 12), fg_color="#495057",
                             hover_color="#343a40", command=toggle)
        gear.pack(side="right", padx=2)
        extra_lbl.pack(side="left", padx=10)
        recap()

    # ---------- items ----------
    def build_items(self):
        it = self.cfg["items"]
        p = self._page("Items")
        top = ctk.CTkFrame(p, **CARD); top.pack(fill="x", pady=4)
        ctk.CTkLabel(top, text="Item Auto-Use (OCR) — optional", font=("Arial", 16, "bold"), text_color="#0d6efd").pack(anchor="w", padx=10, pady=(8, 0))
        self._help_btn(top, "Items")
        ctk.CTkLabel(top, text="Watches the pickup messages (like \"Obtained Copper!\"). When a name from your list shows up, "
                               "its key is pressed once, then M1 to use it. Drag the scan area over where those messages appear.",
                     font=("Arial", 12), text_color="#ced4da", wraplength=600, justify="left").pack(anchor="w", padx=10)
        row = ctk.CTkFrame(top, fg_color="transparent"); row.pack(fill="x", padx=8, pady=6)
        self._switch(row, "Enabled", "items").pack(side="left", padx=4)
        has_area = self.logic.items_region() is not None
        ctk.CTkButton(row, text="🔲 Set Scan Area", width=130, height=28, **BLUE,
                      command=lambda: self.pick_region(it, "region", after=self.build_items)).pack(side="left", padx=4)
        ctk.CTkLabel(row, text="✔ set" if has_area else "not set", font=("Arial", 12),
                     text_color="#75b798" if has_area else "#ea868f").pack(side="left", padx=(0, 6))
        ctk.CTkButton(row, text="Test OCR", width=80, **BTN, command=self.test_items).pack(side="left", padx=4)
        ctk.CTkButton(row, text="+ Add Item", width=90, height=28, **BLUE, command=self.add_item).pack(side="left", padx=4)
        self.ocr_label = ctk.CTkLabel(top, text="", font=("Arial", 12), text_color="#ced4da", wraplength=560, justify="left")
        self.ocr_label.pack(anchor="w", padx=10, pady=(0, 6))

        self.items_box = ctk.CTkFrame(p, fg_color="transparent")
        self.items_box.pack(fill="x")
        for item in it["list"]:
            self._item_row(item)

    def _item_row(self, item):
        it = self.cfg["items"]
        r = ctk.CTkFrame(self.items_box, **CARD); r.pack(fill="x", pady=2)
        en = ctk.CTkCheckBox(r, text="", width=24, command=lambda: self._set(item, "enabled", bool(en.get())))
        if item.get("enabled", True):
            en.select()
        en.pack(side="left", padx=6)
        ctk.CTkLabel(r, text="When").pack(side="left", padx=(4, 4))
        self._entry(r, item, "name", 220, placeholder="e.g. Copper").pack(side="left", pady=6)
        ctk.CTkLabel(r, text="shows up, press").pack(side="left", padx=(8, 4))
        self._pick(r, item, "key", [str(i % 10) for i in range(1, 11)], 56, str).pack(side="left")
        m1 = ctk.CTkCheckBox(r, text="then M1", width=80, font=("Arial", 12),
                             command=lambda: self._set(item, "click", bool(m1.get())))
        if item.get("click", True):
            m1.select()
        m1.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(r, text="cooldown").pack(side="left", padx=(12, 4))
        self._pick(r, item, "cooldown", ["0", "1", "2", "3", "5", "10", "15", "30", "60"], 60, float).pack(side="left")
        ctk.CTkLabel(r, text="s").pack(side="left", padx=(3, 0))
        ctk.CTkButton(r, text="Delete", width=60, height=26, **RED,
                      command=lambda: (remove_obj(it["list"], item), self.save(), r.destroy())).pack(side="right", padx=6)

    def add_item(self):
        item = {"enabled": True, "name": "", "key": "9", "click": True, "cooldown": 0}
        self.cfg["items"]["list"].append(item)
        self.save()
        self._item_row(item)

    def test_items(self):
        it = self.cfg["items"]
        if not self.logic.items_region():
            self.log("Set the scan area first."); return
        self.ocr_label.configure(text="Reading…")

        def run():
            texts = self.logic.read_items()
            hits = [i["name"] for i in self.logic.match_items(texts)]
            why = self.logic.utils.ocr_error if self.logic.utils.ocr_reader is False else ""   # Visual C++ missing
            if why:
                self._safe_set(self.ocr_label, text=why)
                return
            self._safe_set(self.ocr_label,
                           text=f"Read: {', '.join(texts) or '(nothing)'}\nMatches: {', '.join(hits) or 'none'}")
        threading.Thread(target=run, daemon=True).start()

    # ---------- settings ----------
    def build_settings(self):
        p = self._page("Settings")
        c = ctk.CTkFrame(p, **CARD); c.pack(fill="x", pady=4)
        ctk.CTkLabel(c, text="General", font=("Arial", 16, "bold"), text_color="#0d6efd").pack(anchor="w", padx=10, pady=8)
        self._help_btn(c, "Settings")
        r = ctk.CTkFrame(c, fg_color="transparent"); r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(r, text="Start / Stop hotkey", font=("Arial", 12, "bold")).pack(side="left", padx=4)
        self._entry(r, self.cfg, "hotkey", 80, lambda v: v.lower(),
                    on_save=lambda: (self.register_hotkeys(), self.on_state_change(self.logic.running))).pack(side="left")
        sw = ctk.CTkSwitch(c, text="Only act while Roblox is the focused window", font=("Arial", 12),
                           command=lambda: self._set(self.cfg, "only_when_focused", bool(sw.get())))
        if self.cfg.get("only_when_focused", True):
            sw.select()
        sw.pack(anchor="w", padx=12, pady=(4, 6))
        r2 = ctk.CTkFrame(c, fg_color="transparent"); r2.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkLabel(r2, text="Rotation match strictness", font=("Arial", 12, "bold")).pack(side="left", padx=4)
        self._pick(r2, self.cfg["rotation"], "threshold", ["0.75", "0.8", "0.85", "0.9", "0.95"], 70).pack(side="left")
        ctk.CTkLabel(r2, text="used by slots without their own 'Ready at' (Auto-tune sets those)", font=("Arial", 12),
                     text_color="#ced4da").pack(side="left", padx=6)
        ctk.CTkLabel(c, text="The hotkey starts every feature whose 'Enabled' switch is on. Rotation and Skill Combo "
                             "can't both be on — enabling one turns the other off. Items works with either.",
                     font=("Arial", 12), text_color="#ced4da").pack(anchor="w", padx=12, pady=(0, 10))

    def open_guide(self, section=None):
        SetupGuide.show(self.root, section)

    def _help_btn(self, card, section):
        ctk.CTkButton(card, text="? Help", width=60, height=24, font=("Arial", 11, "bold"), fg_color="#343a40",
                      hover_color="#495057", text_color="#0dcaf0",
                      command=lambda: self.open_guide(section)).place(relx=1.0, x=-10, y=8, anchor="ne")
        ctk.CTkButton(card, text="▶ Video", width=64, height=24, font=("Arial", 11, "bold"), fg_color="#343a40",
                      hover_color="#495057", text_color="#ff6b6b",
                      command=lambda: webbrowser.open(SKILL_VIDEO)).place(relx=1.0, x=-76, y=8, anchor="ne")

    # ---------- loadouts ----------
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
        """Reload every page from the newly active loadout (keeps the macro running if it was)."""
        was_running = self.logic.running
        if was_running:
            self.logic.stop()
        self._expanded.clear()
        if self.cfg["rotation"]["enabled"] and self.cfg["combos"]["enabled"]:
            self.cfg["combos"]["enabled"] = False
        self._switches.clear()
        self.build_rotation()
        self.build_combos()
        self.build_items()
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
        self.log(f"Loadout '{name}' created (empty) — press 🪄 Auto-tune or set the hotbar and snapshot for this build.")

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

    # ---------- app hooks ----------
    def register_hotkeys(self):
        keyboard.unhook_all()
        try:
            keyboard.add_hotkey(self.cfg["hotkey"], self.logic.toggle)
        except Exception as e:
            self.log(f"Hotkey error: {e}")
        if self.logic.running and self.cfg["combos"]["enabled"]:
            self.logic._hook_combos()

    def on_state_change(self, running):
        hk = self.cfg["hotkey"].upper()
        def apply():
            if not self.toggle_btn.winfo_exists():
                return
            if running:
                self.toggle_btn.configure(text=f"■ Stop ({hk})", fg_color="#dc3545", hover_color="#bb2d3b")
            else:
                self.toggle_btn.configure(text=f"▶ Start ({hk})", fg_color="#198754", hover_color="#157347")
        self.root.after(0, apply)

    def _safe_set(self, widget, **kw):
        """Update a label from any thread; skip it if the page was closed meanwhile (switched macro)."""
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
            print(msg)
        except UnicodeEncodeError:                       # console without UTF-8 (arrows, emoji)
            print(msg.encode("ascii", "replace").decode())

    def go_back(self):
        self.logic.stop()
        self.ok_page.close()
        keyboard.unhook_all()
        if self.on_back:
            self.on_back()

    def exit_app(self):
        self.logic.stop()
        self.ok_page.close()
        self.root.destroy()

import customtkinter as ctk
import tkinter as tk
from settings import SpatialSettings
from overlay import Overlay, PointSelector, ColorPicker, PersistentOverlay
from updater import SpatialUpdater
from logic_library import LibraryLogic
from logic_mining import MiningLogic
from logic_fishing import FishingLogic
import keyboard
from theme import c
from ui_style import Checklist,  FONT, big_toggle, style_toggle, save_while_typing, sound_picker, fast_scroll_frame, seconds_combo, help_box, SmoothScrollFrame
import os
import links
import time
import threading


class RoutePages:
    def setup_mining_checklist(self):
        holder = fast_scroll_frame(self.tabview.tab("Setup"))
        steps = ((1, "Route", ("mining_route",), self._mining_route_step,
                  lambda s: f"Route: {self.route_menu.get()}" if self._alive("route_menu") else "", None),
                 (2, "Ore times", (), self._mining_path_step,
                  lambda s: "Optional: check each ore's keys and mining time.", None))
        self._checklist = Checklist(holder, self.root, self.logic.setup_problems,
                                    lambda: self.tabview.get() == "Setup", steps, video="video_mining")
        self.refresh_routes()
        self.tabview.on_show("Setup", lambda: self._checklist.refresh())
        self._checklist.refresh(open_first=True)

    def _mining_route_step(self, tab):
        btn = dict(height=28, font=(FONT, 12), fg_color="#34463d", hover_color="#2a3a33")
        rc = self._route_card(tab, None, None,
                         "Test Path (F2)", self.logic.test_movement,
                         f"Recording: stand at the start, press {self.logic.rec_key()}, walk the loop, TAP E once at each ore, "
                         f"pause ~0.5s at corners (checkpoints), press {self.logic.rec_key()} again back at the start.")
        share = ctk.CTkFrame(rc, fg_color="transparent"); share.pack(fill="x", padx=6, pady=(0, 6))
        ctk.CTkButton(share, text="Import route", width=100, command=self._import_route, **btn).pack(side="right")
        ctk.CTkButton(share, text="Export route", width=100, command=self._export_route, **btn).pack(side="right", padx=4)
        self.refresh_routes()

    def _mining_path_step(self, tab):
        head = ctk.CTkFrame(tab, fg_color="transparent"); head.pack(fill="x", padx=15, pady=(2, 0))
        t = ctk.CTkLabel(head, text="Recorded Path", font=(FONT, 14, "bold"))
        t.pack(side="left")
        help_box(tab, "Each ore shows the keys you held to walk there (edit the hold time if you need to) "
                      "and how long to mine.", t)
        self.route_panel = SmoothScrollFrame(tab, fg_color="#101814", corner_radius=8, height=340)
        self.route_panel.pack(fill="x", padx=15, pady=(0, 8))
        self.route_expanded = {}
        self.refresh_routes()

    def setup_mining_options(self):
        group = self._options_page()
        mc = group("Laps")
        btn = dict(height=28, font=(FONT, 12), fg_color="#34463d", hover_color="#2a3a33")
        t = mc.master.head
        help_box(mc.master, "Wait before each lap: a pause at the start spot before walking again.\n"
                     "Pop up wait: how long an ore with 'wait for a pop up' (Setup -> Ore times) waits at most.\n"
                     "Wait for Interact: at the start spot, wait until the 'E Interact' prompt shows (the ore is "
                     "back), then walk. Set area = a small box round the prompt (lighter on the PC); no box = the "
                     "lower middle of the Roblox window.\n"
                     "Press ',': presses ',' twice at the start to lock the camera top-down, facing the way the "
                     "route was recorded. Turn off if your camera is already set.", t)
        self._num_row(mc, "Wait before each lap", "mining_lap_delay", ["0", "1", "2", "3", "5", "10", "30"],
                      float(self.settings.get("mining_lap_delay", 0)), 0.0, label_width=150, unit="s")
        self._num_row(mc, "Pop up wait (at most)", "mining_popup_wait", ["5", "10", "15", "30", "60"],
                      float(self.settings.get("mining_popup_wait", 30)), 30.0, minimum=1, label_width=150, unit="s")
        row = ctk.CTkFrame(mc, fg_color="transparent"); row.pack(fill="x", padx=0, pady=(6, 2))
        arow = ctk.CTkFrame(mc, fg_color="transparent")

        def flip_wait():
            on = bool(wait_sw.get())
            self.settings.set("mining_wait_interact", on)
            arow.pack(fill="x", padx=0, pady=(0, 4), after=row) if on else arow.pack_forget()
        wait_sw = ctk.CTkSwitch(row, text="Wait for Interact at the start", font=(FONT, 12), command=flip_wait)
        if self.settings.get("mining_wait_interact", False): wait_sw.select()
        wait_sw.pack(side="left")
        ctk.CTkButton(arow, text="Set area", width=80, command=lambda: self.pick_region("mining_interact"),
                      **{**btn, "fg_color": "#1c8f52", "hover_color": "#16743f"}).pack(side="left", padx=(42, 4))
        ctk.CTkButton(arow, text="Clear", width=56, command=self._clear_interact_area, **btn).pack(side="left")
        ctk.CTkButton(arow, text="Test", width=56, command=self._test_interact, **btn).pack(side="left", padx=4)
        self.interact_area_lbl = ctk.CTkLabel(arow, text="", font=(FONT, 12))
        self.interact_area_lbl.pack(side="left", padx=6)
        self._show_interact_area()
        if wait_sw.get():
            arow.pack(fill="x", padx=0, pady=(0, 4), after=row)
        row = ctk.CTkFrame(mc, fg_color="transparent"); row.pack(fill="x", padx=0, pady=(2, 4))
        comma = ctk.CTkSwitch(row, text="Press ',' when starting", font=(FONT, 12),
                              command=lambda: self.settings.set("mining_press_comma", bool(comma.get())))
        if self.settings.get("mining_press_comma", True): comma.select()
        comma.pack(side="left")

    def _route_card(self, tab, test1_text, test1_fn, test2_text, test2_fn, tip):
        btn = dict(height=28, font=(FONT, 12), fg_color="#34463d", hover_color="#2a3a33")
        rc = ctk.CTkFrame(tab, fg_color="#15201b", border_color="#2a3a33", border_width=1, corner_radius=8)
        rc.pack(fill="x", padx=15, pady=(8, 4))
        row = ctk.CTkFrame(rc, fg_color="transparent"); row.pack(fill="x", padx=6, pady=(6, 2))
        route_lbl = ctk.CTkLabel(row, text="Route", font=(FONT, 13, "bold"))
        route_lbl.pack(side="left", padx=(0, 6))
        help_box(rc, tip + " Built-in routes can't be recorded over: recording on one makes a new route "
                         "of your own.", route_lbl)
        self.route_menu = ctk.CTkOptionMenu(row, values=["(none)"], width=150, command=self._select_route)
        self.route_menu.pack(side="left")
        ctk.CTkButton(row, text="New", width=50, command=self._new_route, **btn).pack(side="left", padx=(6, 2))
        ctk.CTkButton(row, text="Rename", width=64, command=self._rename_route, **btn).pack(side="left", padx=2)
        ctk.CTkButton(row, text="Delete", width=56, command=self._delete_route,
                      **{**btn, "hover_color": "#b83a2f"}).pack(side="left", padx=2)
        row = ctk.CTkFrame(rc, fg_color="transparent"); row.pack(fill="x", padx=6, pady=(2, 6))
        self.rec_label = ctk.CTkLabel(row, text="", font=(FONT, 12, "bold"))
        self.rec_label.pack(side="left")
        ctk.CTkButton(row, text=test2_text, width=110, command=lambda: self._run_test(test2_fn), **btn).pack(side="right")
        if test1_text:
            ctk.CTkButton(row, text=test1_text, width=136, command=lambda: self._run_test(test1_fn), **btn).pack(side="right", padx=4)
        ctk.CTkFrame(rc, fg_color="transparent", height=2).pack()
        return rc

    def _export_route(self):
        from tkinter import filedialog
        name = self.logic.active_route()
        if not name or not self.logic.load_route():
            self.log("Nothing to export: pick a recorded route first.")
            return
        path = filedialog.asksaveasfilename(parent=self.root, title="Export route", defaultextension=".zip",
                                            initialfile=f"{name}.zip", filetypes=[("Route", "*.zip")])
        if path:
            ok = self.logic.export_route(path, name)
            self.log(f"Route '{name}' exported - others use Import route." if ok else "Couldn't export that route.")

    def _import_route(self):
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(parent=self.root, title="Import route", filetypes=[("Route", "*.zip")])
        if not path:
            return
        try:
            name = self.logic.import_route(path)
        except Exception as e:
            messagebox.showerror("Import route", str(e), parent=self.root)
            return
        self.refresh_routes()
        self.log(f"Route imported as '{name}'. Test Path (F2) to check it lines up for you.")

    def _alive(self, attr):
        w = getattr(self, attr, None)
        try:
            return w is not None and bool(w.winfo_exists())
        except Exception:
            return False

    def refresh_routes(self):
        if not self._alive("route_menu"):
            return
        for i, om in enumerate(getattr(self, "location_menus", [])):
            try:
                om.configure(values=["(none)"] + self.logic.list_routes())
                cur = self.logic.location_routes()[i]
                om.set(cur if cur in self.logic.list_routes() else "(none)")
            except Exception:
                pass
        routes = self.logic.list_routes()
        active = self.logic.active_route()
        self.route_menu.configure(values=routes or ["(none)"])
        self.route_menu.set(active or "(none)")
        self.set_recording_ui(self.logic.is_recording())
        if self._alive("route_panel"):
            self.build_route_panel()
        if self._alive("_stand_box"):
            self._stand_box.pack(fill="x") if self.logic.is_locked() else self._stand_box.pack_forget()

    def set_recording_ui(self, recording):
        self._rec_badge(recording)
        if not self._alive("rec_label"):
            return
        if recording:
            self.rec_label.configure(text=f"● RECORDING… ({self.logic.rec_key()} to finish)", text_color="#f08a7e")
            return
        r = self.logic.load_route()
        if r:
            n_cp = sum(len(sg.get("checkpoints", [])) for sg in r["segments"]) + len(r["return"].get("checkpoints", []))
            what = (f"{r['ores']} ores, {n_cp} checkpoints" if "Mining" in self.root.title()
                    else f"recorded ({sum(s['duration'] for s in r['segments']) or r['return']['duration']:.1f}s walk)")
            lock = self.logic.is_locked()
            self.rec_label.configure(text=(f"built-in · {what}" if lock else what), text_color="#7ee0a6")
        else:
            builtins = list(self.logic._builtins()) if hasattr(self.logic, "_builtins") else []
            if builtins:
                self.rec_label.configure(text=f"Not recorded — '{builtins[0]}' will be used ({self.logic.rec_key()} to record your own)",
                                         text_color="#e6b84f")
            else:
                self.rec_label.configure(text=f"Not recorded yet — press {self.logic.rec_key()}", text_color="#cfc6ab")

    def _rec_badge(self, on):
        old = getattr(self, "_badge", None)
        if old is not None:
            old.destroy(); self._badge = None
        if on:
            try:
                l, t, r, b = self.logic.get_roblox_window_region()
                from overlay import RecordingBadge
                self._badge = RecordingBadge((l + r) / 2, t + 40, key=self.logic.rec_key())
            except Exception as e:
                print(f"REC badge: {e}")

    def _select_route(self, name):
        if name in self.logic.list_routes():
            self.logic.set_active_route(name)
            self.refresh_routes()

    def _new_route(self):
        name = self._ask("New route", "Name for the new route (e.g. Tundra, Cave):")
        if name and self.logic.create_route(name):
            self.refresh_routes()
            self.log(f"Route '{name}' created. Stand at its start spot and press {self.logic.rec_key()} to record.")
        elif name:
            self.log("That name is empty or already used.")

    def _rename_route(self):
        old = self.logic.active_route()
        if not old: return
        if self.logic.is_locked(old):
            self.log(f"'{old}' is built in and can't be renamed. Press New to make your own route."); return
        new = self._ask("Rename route", f"New name for '{old}':", old)
        if new and self.logic.rename_route(old, new):
            self.refresh_routes()
        elif new:
            self.log("That name is empty or already used.")

    def _delete_route(self):
        from tkinter import messagebox
        name = self.logic.active_route()
        if self.logic.is_locked(name):
            self.log(f"'{name}' is built in and can't be deleted."); return
        if name and messagebox.askyesno("Delete route", f"Delete route '{name}' and its recording?"):
            self.logic.delete_route(name)
            self.refresh_routes()
            self.log(f"Route '{name}' deleted.")

    @staticmethod
    def _holds(seg):
        holds, open_ = [], {}
        for i, (t, key, kind) in enumerate(seg["events"]):
            if kind == "down":
                open_[key] = (t, len(holds))
                holds.append({"key": key, "start": t, "dur": None, "up": None})
            elif key in open_:
                t0, h = open_.pop(key)
                holds[h].update(dur=t - t0, up=i)
        return [h for h in holds if h["dur"] is not None]

    def build_route_panel(self):
        for w in self.route_panel.winfo_children():
            w.destroy()
        route = self.logic.load_route()
        if not route:
            ctk.CTkLabel(self.route_panel, text=f"No recording for this route yet.\nStand at the start spot in-game and press {self.logic.rec_key()}.",
                         font=(FONT, 12), text_color="#cfc6ab").pack(pady=20)
            return
        if route["segments"]:
            first = route["segments"][0]
            bar = ctk.CTkFrame(self.route_panel, fg_color="#15201b", border_color="#e6b84f", border_width=1, corner_radius=8)
            bar.pack(fill="x", padx=4, pady=(3, 6))
            r = ctk.CTkFrame(bar, fg_color="transparent"); r.pack(fill="x", padx=8, pady=(8, 4))
            ctk.CTkLabel(r, text="All ores:", font=(FONT, 12, "bold"), text_color="#e6b84f").pack(side="left", padx=(0, 8))
            boxes = {}
            for label, field in (("Mining Secs:", "mine_hold"), ("Waiting Secs:", "mine_wait")):
                ctk.CTkLabel(r, text=label, font=(FONT, 12, "bold")).pack(side="left", padx=(0, 2))
                e = ctk.CTkEntry(r, width=52, font=(FONT, 12))
                e.insert(0, f"{float(first.get(field, 3.0 if field == 'mine_hold' else 1.75)):.2f}")
                e.pack(side="left", padx=(0, 10))
                boxes[field] = e
            r = ctk.CTkFrame(bar, fg_color="transparent"); r.pack(fill="x", padx=8, pady=(0, 8))
            allpop = ctk.CTkCheckBox(r, text="wait for pop up", font=(FONT, 12))
            if all(sg.get("wait_popup") for sg in route["segments"]):
                allpop.select()
            allpop.pack(side="left", padx=(0, 8))
            ctk.CTkButton(r, text="Apply to all", width=100, height=28, font=(FONT, 12), fg_color="#1c8f52",
                          hover_color="#16743f",
                          command=lambda: self._apply_all_ores({f: w.get() for f, w in boxes.items()},
                                                               bool(allpop.get()))).pack(side="right")
        items = [(f"Ore {i}", i - 1, seg) for i, seg in enumerate(route["segments"], start=1)]
        items.append(("Return to start", "return", route["return"]))
        for title, key, seg in items:
            c = ctk.CTkFrame(self.route_panel, fg_color="#15201b", border_color="#2a3a33", border_width=1, corner_radius=8)
            c.pack(fill="x", padx=4, pady=3)
            summary = f"{title}   ·   walk {seg['duration']:.1f}s   ·   {len(seg.get('checkpoints', []))} checkpoints"
            open_ = self.route_expanded.get(key, False)
            hb = ctk.CTkButton(c, text=f"{summary}   {'▾' if open_ else '▸'}", anchor="w", height=32, corner_radius=6,
                               font=(FONT, 13, "bold"), fg_color="#22302a", hover_color="#2a3a33")
            hb.pack(fill="x", padx=6, pady=6)
            body = ctk.CTkFrame(c, fg_color="transparent")

            def flip(k=key, body=body, seg=seg, hb=hb, summary=summary):
                now = not self.route_expanded.get(k, False)
                self.route_expanded[k] = now
                hb.configure(text=f"{summary}   {'▾' if now else '▸'}")
                if now:
                    if not body.winfo_children():
                        self._fill_route_body(body, k, seg)
                    body.pack(fill="x", padx=8, pady=(0, 6))
                else:
                    body.pack_forget()
            hb.configure(command=flip)
            if open_:
                self._fill_route_body(body, key, seg)
                body.pack(fill="x", padx=8, pady=(0, 6))

    def _fill_route_body(self, body, key, seg):
        if True:
            if key != "return":
                r = ctk.CTkFrame(body, fg_color="transparent"); r.pack(fill="x", pady=(0, 4))
                for label, field in (("Mining Secs:", "mine_hold"), ("Waiting Secs:", "mine_wait")):
                    ctk.CTkLabel(r, text=label, font=(FONT, 12, "bold")).pack(side="left", padx=(0, 2))
                    e = ctk.CTkEntry(r, width=52, font=(FONT, 12))
                    e.insert(0, f"{float(seg.get(field, 3.0 if field == 'mine_hold' else 1.75)):.2f}")
                    e.pack(side="left", padx=(0, 10))
                    e.bind("<FocusOut>", lambda ev, k=key, f=field, w=e: self._save_seg_value(k, f, w.get()))
                    save_while_typing(e, lambda k=key, f=field, w=e: self._save_seg_value(k, f, w.get()))
                wp = ctk.CTkCheckBox(r, text="After mining: wait for a pop up", font=(FONT, 12))
                wp.configure(command=lambda k=key, w=wp: self._save_seg_flag(k, "wait_popup", bool(w.get())))
                if seg.get("wait_popup"):
                    wp.select()
                wp.pack(side="left", padx=(6, 0))
                if key >= 1 and getattr(self.logic, "ROUTE_TARGET", "") == "ore" and not self.logic.is_locked():
                    rr = ctk.CTkFrame(body, fg_color="transparent"); rr.pack(fill="x", pady=(0, 4))
                    ctk.CTkButton(rr, text=f"Re-record from ore {key + 1}", width=150, height=26, font=(FONT, 12),
                                  fg_color="#34463d", hover_color="#2a3a33",
                                  command=lambda n=key + 1: self._rerecord_from(n)).pack(side="left")
                    ctk.CTkLabel(rr, text="keeps ore 1" if key == 1 else f"keeps ores 1-{key}", font=(FONT, 11),
                                 text_color="#a39d86").pack(side="left", padx=8)
            ctk.CTkLabel(body, text="Walk (key · starts at · hold secs):", font=(FONT, 12, "bold")).pack(anchor="w")
            for h in self._holds(seg):
                r = ctk.CTkFrame(body, fg_color="#22302a", corner_radius=6); r.pack(fill="x", pady=1)
                ctk.CTkLabel(r, text=h["key"].upper(), width=46, font=(FONT, 13, "bold"), text_color="#b5e8c9").pack(side="left", padx=6)
                ctk.CTkLabel(r, text=f"at {h['start']:.2f}s", width=80, font=(FONT, 12), text_color="#cfc6ab").pack(side="left")
                e = ctk.CTkEntry(r, width=60, font=(FONT, 12)); e.insert(0, f"{h['dur']:.2f}"); e.pack(side="left", padx=6, pady=3)
                e.bind("<FocusOut>", lambda ev, k=key, h=h, w=e: self._save_hold(k, h, w.get()))
                save_while_typing(e, lambda k=key, h=h, w=e: self._save_hold(k, h, w.get()))

    def _rerecord_from(self, n):
        from tkinter import messagebox
        if self.logic.is_recording():
            self.log(f"Already recording - press {self.logic.rec_key()} in Roblox to finish that one first.")
            return
        if not messagebox.askokcancel(
                f"Re-record from ore {n}",
                f"Ores 1-{n - 1} are kept as they are.\n\n"
                f"1. In Roblox, stand exactly where you mine ore {n - 1}.\n"
                f"2. Press OK - it switches to Roblox and starts recording.\n"
                f"3. Walk on, TAP E at each ore, walk back to the start and press {self.logic.rec_key()}.\n\n"
                f"If you stop without walking, nothing changes.",
                parent=self.root):
            return

        def start():
            if not self.logic.wait_focus_for_test():
                return
            self.logic.toggle_recording(from_ore=n)
        threading.Thread(target=start, daemon=True).start()

    def _route_seg(self, route, key):
        return route["return"] if key == "return" else route["segments"][key]

    def _save_seg_value(self, key, field, text):
        route = self.logic.load_route()
        try:
            self._route_seg(route, key)[field] = max(0.0, float(text))
            self.logic.save_route(route)
        except (ValueError, TypeError, IndexError):
            pass

    def _apply_all_ores(self, values, wait_popup):
        if self.logic.is_locked(self.logic.active_route()):
            self.log("This route is built in and can't be changed. Press New to make your own route.")
            return
        route = self.logic.load_route()
        if not route:
            return
        try:
            nums = {f: max(0.0, float(v)) for f, v in values.items()}
        except (TypeError, ValueError):
            self.log("Type a number in Mining Secs and Waiting Secs first.")
            return
        for seg in route["segments"]:
            seg.update(nums)
            seg["wait_popup"] = wait_popup
        self.logic.save_route(route)
        self.log(f"All {len(route['segments'])} ores: mining {nums['mine_hold']:g}s, waiting {nums['mine_wait']:g}s"
                 + (", wait for pop up" if wait_popup else "") + ".")
        self.build_route_panel()

    def _save_seg_flag(self, key, field, on):
        route = self.logic.load_route()
        try:
            self._route_seg(route, key)[field] = bool(on)
            self.logic.save_route(route)
        except (IndexError, KeyError, TypeError):
            pass

    def _save_hold(self, key, hold, text):
        route = self.logic.load_route()
        try:
            dur = max(0.0, float(text))
        except ValueError:
            return
        seg = self._route_seg(route, key)
        ev = seg["events"][hold["up"]]
        ev[0] = round(hold["start"] + dur, 3)
        seg["events"].sort(key=lambda e: e[0])
        seg["duration"] = round(max(seg["duration"], ev[0]), 3)
        self.logic.save_route(route)
        self.build_route_panel()

    FISH_BLUE = dict(height=28, font=(FONT, 12), fg_color="#1c8f52", hover_color="#16743f")
    FISH_GREY = dict(height=28, font=(FONT, 12), fg_color="#34463d", hover_color="#2a3a33")

    def setup_fishing_checklist(self):
        holder = fast_scroll_frame(self.tabview.tab("Setup"))
        regions = lambda: self.settings.get("regions", {}) or {}

        def at(key):
            v = regions().get(key) or []
            return f"Set at ({v[0]}, {v[1]})." if len(v) >= 2 and any(v) else "Set."

        def click_pos(body):
            row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x", padx=10, pady=(2, 6))
            b = ctk.CTkButton(row, text="Pick click position", width=150,
                              command=lambda: self.pick_point("fishing_click_pos"), **self.FISH_BLUE)
            b.pack(side="left")
            self._mark("fishing_click_pos", b)

        def bar(body):
            row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x", padx=10, pady=(2, 6))
            b = ctk.CTkButton(row, text="Drag the minigame bar", width=170,
                              command=lambda: self.pick_region("minigame_bar"), **self.FISH_BLUE)
            b.pack(side="left")
            self._mark("minigame_bar", b)

        def colours(body):
            for key, label, attr, default, test, hk in (
                    ("bar_color", "Bar", "bar", (0, 255, 0), self.logic.test_bar_detection, "F1"),
                    ("fish_color", "Fish", "fish", (255, 255, 255), self.logic.test_fish_detection, "F2")):
                row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x", padx=10, pady=2)
                ctk.CTkLabel(row, text=label, width=50, anchor="w", font=(FONT, 12, "bold")).pack(side="left")
                col = self.settings.get(key, default)
                prev = ctk.CTkFrame(row, width=18, height=18, fg_color='#%02x%02x%02x' % tuple(col), corner_radius=4)
                prev.pack(side="left", padx=5)
                lbl = ctk.CTkLabel(row, text=str(col), font=(FONT, 12), text_color="#e8dfc5")
                lbl.pack(side="left")
                setattr(self, f"{attr}_preview", prev)
                setattr(self, f"{attr}_color_lbl", lbl)
                ctk.CTkButton(row, text=f"Test ({hk})", width=70, command=lambda fn=test: self._run_test(fn),
                              **self.FISH_GREY).pack(side="right", padx=(4, 0))
                ctk.CTkButton(row, text="Pick", width=56, command=lambda k=key: self.pick_color(k),
                              **self.FISH_BLUE).pack(side="right")
            row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x", padx=10, pady=(4, 6))
            ctk.CTkLabel(row, text="Tolerance", width=70, anchor="w", font=(FONT, 12, "bold")).pack(side="left")
            self.fishing_tolerance_slider = ctk.CTkSlider(row, from_=1, to=100, number_of_steps=99,
                                                          command=self.update_tolerance)
            self.fishing_tolerance_slider.set(self.settings.get("color_tolerance", 25))
            self.fishing_tolerance_slider.pack(side="left", fill="x", expand=True, padx=6)
            self.fishing_tolerance_val_label = ctk.CTkLabel(row, text=f"Value: {int(self.fishing_tolerance_slider.get())}",
                                                            width=70, font=(FONT, 12, "bold"))
            self.fishing_tolerance_val_label.pack(side="left")

        def test(body):
            row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x", padx=10, pady=(2, 6))
            ctk.CTkButton(row, text="Test full tracking", width=150,
                          command=lambda: self._run_test(self.logic.test_detection), **self.FISH_BLUE).pack(side="left")

        steps = ((1, "Click position", ("fishing_click_pos",), click_pos, lambda s: at("fishing_click_pos"),
                  "Where to click to cast and reel."),
                 (2, "Minigame bar", ("fishing_minigame_bar",), bar, lambda s: "Box set.",
                  "Drag a box around the fishing bar while the minigame is showing. Show Scan Areas (Options) "
                  "draws it on screen."),
                 (3, "Colours", (), colours, lambda s: "Pick the bar's and the fish's colour, then Test each.",
                  "Pick the bar's colour and the fish's colour from the minigame. Test checks each one now. "
                  "Tolerance = how far a colour may drift: not found? raise it; finds wrong things? lower it."),
                 (4, "Test", (), test, lambda s: "Run this once the steps above are done.",
                  "Test full tracking follows the fish with the bar for a moment, without fishing."))
        self._checklist = Checklist(holder, self.root, self.logic.setup_problems,
                                    lambda: self.tabview.get() == "Setup", steps, video="video_fishing")
        self.tabview.on_show("Setup", lambda: self._checklist.refresh())
        self._checklist.refresh(open_first=True)

    def setup_fishing_options(self):
        group = self._options_page()
        b = group("Scan areas")
        self.overlay_switch = ctk.CTkSwitch(b, text="Show Scan Areas", command=self.toggle_overlays, font=(FONT, 12))
        self.overlay_switch.pack(anchor="w", padx=4, pady=2)
        b = group("Colours", advanced=True)
        row = ctk.CTkFrame(b, fg_color="transparent"); row.pack(fill="x", padx=4, pady=2)
        ctk.CTkButton(row, text="Reset to defaults", width=140, fg_color="#7a2620", hover_color="#5e1d18", height=28,
                      font=(FONT, 12), command=self.reset_fishing_defaults).pack(side="right")
        t = ctk.CTkLabel(row, text="Put the colours and tolerance back to the built-in ones", font=(FONT, 12),
                         justify="left", anchor="w", wraplength=260)
        t.pack(side="left", fill="x", expand=True)

    def reset_fishing_defaults(self):
        self.settings.set("bar_color", [95, 153, 98])
        self.settings.set("fish_color", [188, 187, 144])
        self.settings.set("color_tolerance", 25)

        if hasattr(self, "bar_preview"):
            self.bar_preview.configure(fg_color='#5f9962')
            self.bar_color_lbl.configure(text="[95, 153, 98]")
            self.fish_preview.configure(fg_color='#bcbb90')
            self.fish_color_lbl.configure(text="[188, 187, 144]")
        if hasattr(self, 'fishing_tolerance_slider'):
            self.fishing_tolerance_slider.set(25)
        if hasattr(self, 'fishing_tolerance_val_label'):
            self.fishing_tolerance_val_label.configure(text="Value: 25")
        self.log("Fishing Defaults Restored")

    def update_tolerance(self, val):
        self.settings.set("color_tolerance", int(val))
        if hasattr(self, 'clover_tolerance_val_label'):
            self.clover_tolerance_val_label.configure(text=f"Value: {int(val)}")
        if hasattr(self, 'fishing_tolerance_val_label'):
            self.fishing_tolerance_val_label.configure(text=f"Value: {int(val)}")
        if hasattr(self, 'tundra_tolerance_val_label'):
            self.tundra_tolerance_val_label.configure(text=f"Value: {int(val)}")
        if hasattr(self, 'clover_tolerance_slider'):
            self.clover_tolerance_slider.set(int(val))
        if hasattr(self, 'fishing_tolerance_slider'):
            self.fishing_tolerance_slider.set(int(val))
        if hasattr(self, 'tundra_tolerance_slider'):
            self.tundra_tolerance_slider.set(int(val))

    def _show_interact_area(self):
        r = self.settings.get("regions", {}).get("mining_interact") or [0, 0, 0, 0]
        own = r[2] > r[0] and r[3] > r[1]
        self.interact_area_lbl.configure(text=f"area set ({r[2] - r[0]}x{r[3] - r[1]})" if own else "no area (lower middle)",
                                         text_color="#7ee0a6" if own else "#a39d86")

    def _clear_interact_area(self):
        self.settings.settings.setdefault("regions", {}).pop("mining_interact", None)
        self.settings.save()
        self._show_interact_area()

    def _test_interact(self):
        def run():
            seen = self.logic.interact_visible()
            self.log("Interact prompt: seen" if seen else "Interact prompt: NOT seen (stand where it shows, or set the area)")
        threading.Thread(target=run, daemon=True).start()

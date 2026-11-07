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
from ui_style import dialog_keys, FONT, big_toggle, style_toggle, save_while_typing, sound_picker, fast_scroll_frame, seconds_combo, help_box
import os
import links
import time
import threading


class PopupPages:
    def _ok_card(self, parent, step, title, desc):
        card = ctk.CTkFrame(parent, fg_color="#15201b", border_color="#2a3a33", border_width=1, corner_radius=8)
        card.pack(fill="x", padx=16, pady=5)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(8, 0))
        t = ctk.CTkLabel(head, text=f"{step}. {title}", font=(FONT, 13, "bold"), text_color="#f3ecd8")
        t.pack(side="left")
        status = ctk.CTkLabel(head, text="", font=(FONT, 11, "bold"))
        status.pack(side="right")
        help_box(card, desc, t)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(4, 8))
        return status, row

    def setup_ok_tab(self):
        tab = fast_scroll_frame(self.tabview.tab("Pop Up"))
        t = ctk.CTkLabel(tab, text="Pop Up Detection", font=(FONT, 18, "bold"), text_color="#1c8f52")
        t.pack(pady=(12, 8))
        help_box(tab, "Shared by every macro, so you only set it up once. Every pop up in the list is clicked while "
                      "a macro runs. Always Click Pop Ups also clicks them when no macro is running.", t)
        if not hasattr(self, "_always_ok_on"):
            self._always_ok_on = False
        self._ok_toggles = getattr(self, "_ok_toggles", [])
        ok_toggle = big_toggle(tab, self.toggle_always_ok)
        ok_toggle.pack(pady=(0, 8), fill="x", padx=20)
        self._ok_toggles.append(ok_toggle)
        style_toggle(ok_toggle, self._always_ok_on, "Always Click Pop Ups")
        if not hasattr(self, "always_ok_btn"):
            self.always_ok_btn = ok_toggle
        btn_kw = dict(height=28, font=(FONT, 12), fg_color="#1c8f52", hover_color="#16743f")

        card = ctk.CTkFrame(tab, fg_color="#15201b", border_color="#2a3a33", border_width=1, corner_radius=8)
        card.pack(fill="x", padx=16, pady=5)
        head = ctk.CTkFrame(card, fg_color="transparent"); head.pack(fill="x", padx=10, pady=(8, 0))
        tl = ctk.CTkLabel(head, text="Pop ups to click", font=(FONT, 13, "bold"), text_color="#f3ecd8")
        tl.pack(side="left")
        help_box(card, "OK button is the usual Roblox OK pop up. Add any other pop up that gets in the way (e.g. "
                       "Delayed Packages). Edit gives each one a picture and what to click; Test looks for it now.", tl)
        self._popup_box = ctk.CTkFrame(card, fg_color="transparent"); self._popup_box.pack(fill="x", padx=6)
        self._ok_row()
        for pp in self.logic.popups():
            self._popup_row(pp)
        ctk.CTkButton(card, text="+ Add pop up", width=120, command=self._add_popup, **btn_kw).pack(
            anchor="w", padx=10, pady=(4, 10))

        mc = ctk.CTkFrame(tab, fg_color="#15201b", border_color="#2a3a33", border_width=1, corner_radius=8)
        mc.pack(fill="x", padx=16, pady=5)
        head = ctk.CTkFrame(mc, fg_color="transparent"); head.pack(fill="x", padx=10, pady=(8, 0))
        tm = ctk.CTkLabel(head, text="How exact the picture must be", font=(FONT, 13, "bold"), text_color="#f3ecd8")
        tm.pack(side="left")
        help_box(mc, "Used by every pop up in the list. Lower it if a pop up is missed, raise it if something is "
                     "clicked when no pop up is open.", tm)
        row = ctk.CTkFrame(mc, fg_color="transparent"); row.pack(fill="x", padx=10, pady=(4, 8))
        thr = float(self.settings.get("ok_match_threshold", 0.80))
        self.ok_thr_label = ctk.CTkLabel(row, text=f"Match: {int(thr * 100)}%", width=80, font=(FONT, 12))
        self.ok_thr_label.pack(side="right")
        slider = ctk.CTkSlider(row, from_=0.5, to=0.98, number_of_steps=48, width=120, command=self._update_ok_threshold)
        slider.set(thr)
        slider.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.refresh_ok_status()

    def _ok_row(self):
        BTN_ = dict(height=28, font=(FONT, 12), fg_color="#34463d", hover_color="#2a3a33")
        BLUE_ = dict(height=28, font=(FONT, 12), fg_color="#1c8f52", hover_color="#16743f")
        box = ctk.CTkFrame(self._popup_box, fg_color="#101814", corner_radius=6); box.pack(fill="x", padx=4, pady=3)
        r1 = ctk.CTkFrame(box, fg_color="transparent"); r1.pack(fill="x", padx=6, pady=6)
        ctk.CTkFrame(r1, fg_color="transparent", width=24, height=24).pack(side="left")
        ctk.CTkLabel(r1, text="OK button", width=96, anchor="w", font=(FONT, 12, "bold")).pack(side="left", padx=4)
        self._ok_row_pic = ctk.CTkLabel(r1, text="")
        self._ok_row_pic.pack(side="left", padx=6)
        ctk.CTkButton(r1, text="Test", width=50, command=lambda: self._run_test(self.logic.test_ok_popup),
                      **BTN_).pack(side="right", padx=(4, 0))
        ctk.CTkButton(r1, text="Edit…", width=60, command=self._ok_editor, **BLUE_).pack(side="right")
        self._ok_row_info = ctk.CTkLabel(box, text="", font=(FONT, 11), anchor="w")
        self._ok_row_info.pack(fill="x", padx=40, pady=(0, 6))

    def _ok_editor(self):
        old = getattr(self, "_ok_win", None)
        if old is not None and old.winfo_exists():
            old.deiconify(); old.lift()
            return
        win = self._ok_win = ctk.CTkToplevel(self.root)
        win.title("Pop up - OK button")
        dialog_keys(win)
        win.geometry("520x470")
        win.transient(self.root)
        win.after(150, win.lift)
        body = fast_scroll_frame(win)
        btn_kw = dict(height=28, font=(FONT, 12), fg_color="#1c8f52", hover_color="#16743f")
        sub_kw = dict(height=28, width=70, font=(FONT, 12), fg_color="#34463d", hover_color="#2a3a33")

        def out_of_the_way(fn):
            win.withdraw()
            fn()

        self.ok_btn_status, row = self._ok_card(body, 1, "Picture of the OK button",
            "Open an OK popup in Roblox, then drag a tight box around the OK button.")
        ctk.CTkButton(row, text="Capture", command=lambda: out_of_the_way(self.pick_ok_button), **btn_kw).pack(side="left")
        self.ok_preview = ctk.CTkLabel(row, text="")
        self.ok_preview.pack(side="left", padx=12)

        self.ok_area_status, row = self._ok_card(body, 2, "Where to look  (optional)",
            "Where to look for the button. Default: the whole screen. Set a smaller area to make it lighter.")
        ctk.CTkButton(row, text="Set Area", command=lambda: out_of_the_way(lambda: self.pick_region("ok_scan_area")),
                      **btn_kw).pack(side="left")
        ctk.CTkButton(row, text="Clear", command=lambda: self._clear_ok_setting("ok_scan_area", [0, 0, 0, 0]),
                      **sub_kw).pack(side="left", padx=6)
        self.ok_area_switch = ctk.CTkSwitch(row, text="Show on screen", font=(FONT, 12), command=self.toggle_ok_area_overlay)
        self.ok_area_switch.pack(side="left", padx=6)

        self.ok_click_status, row = self._ok_card(body, 3, "Where to click  (optional)",
            "A fixed point to click when the popup is found. Defaults to the button itself.")
        ctk.CTkButton(row, text="Set Spot", command=lambda: out_of_the_way(lambda: self.pick_point("ok_click_pos")),
                      **btn_kw).pack(side="left")
        ctk.CTkButton(row, text="Clear", command=lambda: self._clear_ok_setting("ok_click_pos", [0, 0]),
                      **sub_kw).pack(side="left", padx=6)

        _, row = self._ok_card(body, 4, "Test", "Looks for the OK pop up on the screen now (How exact: on the Pop Up page).")
        ctk.CTkButton(row, text="▶ Test Now", command=lambda: self._run_test(self.logic.test_ok_popup),
                      **btn_kw).pack(side="left")

        def close():
            if self._ok_switch_on():
                self.ok_area_switch.deselect()
                self.toggle_ok_area_overlay()
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", close)
        self.refresh_ok_status()

    def _add_popup(self):
        name = self._ask("Add pop up", "Name of the pop up (e.g. Delayed Packages):")
        if name is None:
            return
        self._popup_row(self.logic.add_popup(name.strip() or "Pop up"))

    def _popup_thumb(self, path, size=(160, 30)):
        try:
            from PIL import Image
            im = Image.open(path).convert("RGB")
            im.thumbnail(size)
            return ctk.CTkImage(light_image=im, dark_image=im, size=im.size)
        except Exception:
            return None

    def _popup_summary(self, pp):
        if not self.logic.has_popup_picture(pp):
            return "needs a picture - press Edit", "#f08a7e"
        n = len(pp.get("steps") or [])
        if n:
            return f"then does {n} step{'s' if n > 1 else ''}", "#7ee0a6"
        if any(pp["click"]):
            return f"then clicks ({pp['click'][0]}, {pp['click'][1]})", "#7ee0a6"
        return "then clicks where it's found", "#7ee0a6"

    def _popup_row(self, pp):
        BTN_ = dict(height=28, font=(FONT, 12), fg_color="#34463d", hover_color="#2a3a33")
        BLUE_ = dict(height=28, font=(FONT, 12), fg_color="#1c8f52", hover_color="#16743f")
        box = ctk.CTkFrame(self._popup_box, fg_color="#101814", corner_radius=6); box.pack(fill="x", padx=4, pady=3)
        r1 = ctk.CTkFrame(box, fg_color="transparent"); r1.pack(fill="x", padx=6, pady=6)
        on = ctk.CTkCheckBox(r1, text="", width=24, command=lambda: (pp.__setitem__("enabled", bool(on.get())),
                                                                     self.settings.save()))
        if pp["enabled"]:
            on.select()
        on.pack(side="left")
        name = ctk.CTkEntry(r1, width=96, font=(FONT, 12)); name.insert(0, pp["name"]); name.pack(side="left", padx=4)
        store = lambda *_: (pp.__setitem__("name", name.get().strip() or "Pop up"), self.settings.save())
        name.bind("<FocusOut>", store); save_while_typing(name, store)
        pic = ctk.CTkLabel(r1, text=""); pic.pack(side="left", padx=6)
        info = ctk.CTkLabel(box, text="", font=(FONT, 11), anchor="w")
        ctk.CTkButton(r1, text="Delete", width=60, fg_color="#7a2620", hover_color="#5e1d18", height=28,
                      font=(FONT, 12), command=lambda: (self.logic.remove_popup(pp), box.destroy())).pack(side="right")
        ctk.CTkButton(r1, text="Test", width=50, command=lambda: self._run_test(lambda: self.logic.test_popup(pp)),
                      **BTN_).pack(side="right", padx=4)
        ctk.CTkButton(r1, text="Edit…", width=60, command=lambda: self._popup_editor(pp, show), **BLUE_).pack(side="right")

        def show():
            if not box.winfo_exists():
                return
            img = self._popup_thumb(self.logic.popup_path(pp), (56, 20)) if self.logic.has_popup_picture(pp) else None
            pic.configure(image=img, text="")
            pic._img = img
            txt, col = self._popup_summary(pp)
            info.configure(text=txt, text_color=col)
        info.pack(fill="x", padx=40, pady=(0, 6))
        show()

    def _popup_editor(self, pp, on_change):
        old = getattr(self, "_popup_win", None)
        if old is not None and old.winfo_exists():
            old.destroy()
        win = ctk.CTkToplevel(self.root)
        self._popup_win = win
        win.title(f"Pop up - {pp['name']}")
        dialog_keys(win)
        win.geometry("560x600")
        win.transient(self.root)
        win.after(150, win.lift)
        BTN_ = dict(height=28, font=(FONT, 12), fg_color="#34463d", hover_color="#2a3a33")
        BLUE_ = dict(height=28, font=(FONT, 12), fg_color="#1c8f52", hover_color="#16743f")
        body = fast_scroll_frame(win)

        def section(title, help_text):
            card = ctk.CTkFrame(body, fg_color="#15201b", border_color="#2a3a33", border_width=1, corner_radius=8)
            card.pack(fill="x", padx=10, pady=5)
            t = ctk.CTkLabel(card, text=title, font=(FONT, 13, "bold"), text_color="#f3ecd8")
            t.pack(anchor="w", padx=10, pady=(8, 0))
            help_box(card, help_text, t)
            row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=10, pady=(4, 8))
            return card, row

        def pick_box(then):
            win.withdraw()
            self._hide_for_pick()

            def done(x1, y1, x2, y2):
                def back():
                    then([int(x1), int(y1), int(x2), int(y2)])
                    self.root.deiconify()
                    if win.winfo_exists():
                        win.deiconify(); win.lift()
                    refresh()
                self.root.after(300, back)
            Overlay(done)

        def pick_point(then):
            win.withdraw()
            self._hide_for_pick()

            def done(x, y):
                then([int(x), int(y)])
                self.settings.save()
                self.root.deiconify()
                if win.winfo_exists():
                    win.deiconify(); win.lift()
                refresh()
            PointSelector(done)

        _, row = section("1. Picture", "Open the pop up in Roblox, press Capture and drag a box around something "
                                       "ONLY that pop up shows (its title is best). This is how it's recognised.")

        def cap_a(r):
            ok = self.logic.capture_popup(pp, r)
            self.log(f"Pop up '{pp['name']}': picture saved." if ok else "Capture failed - drag a bigger box.")
        ctk.CTkButton(row, text="Capture", width=80, command=lambda: pick_box(cap_a), **BLUE_).pack(side="left")
        pic_a = ctk.CTkLabel(row, text="", font=(FONT, 12)); pic_a.pack(side="left", padx=10)

        _, row = section("2. Scan area  (optional)", "Only look for it inside this box - drag one a bit bigger than "
                                                     "where its picture shows. No area = the whole screen.")

        def set_area(r):
            pp["area"] = r
            self.settings.save()

        def clear_area():
            pp["area"] = [0, 0, 0, 0]
            self.settings.save()
            refresh()
        ctk.CTkButton(row, text="Set area", width=80, command=lambda: pick_box(set_area), **BLUE_).pack(side="left")
        ctk.CTkButton(row, text="Clear", width=60, command=clear_area, **BTN_).pack(side="left", padx=6)
        area_lbl = ctk.CTkLabel(row, text="", font=(FONT, 12)); area_lbl.pack(side="left", padx=8)

        card, row = section("3. Then do", "No steps: it clicks the Click spot, or right where the picture was "
                            "found if there's no spot.\n\nWith steps it does them in order, like a combo: each step "
                            "waits, looks for its own picture (e.g. a button inside the pop up) and clicks it - or "
                            "clicks its own spot instead. If a step's picture isn't on screen it stops there and "
                            "doesn't click anything else.")
        ctk.CTkButton(row, text="Click spot", width=90,
                      command=lambda: pick_point(lambda xy: pp.__setitem__("click", xy)), **BLUE_).pack(side="left")
        ctk.CTkButton(row, text="Clear", width=60,
                      command=lambda: (pp.__setitem__("click", [0, 0]), self.settings.save(), refresh()),
                      **BTN_).pack(side="left", padx=6)
        spot_lbl = ctk.CTkLabel(row, text="", font=(FONT, 12)); spot_lbl.pack(side="left", padx=8)
        steps_box = ctk.CTkFrame(card, fg_color="transparent"); steps_box.pack(fill="x", padx=6)

        def add_step():
            self.logic.new_step(pp)
            draw_steps()
            refresh()
        ctk.CTkButton(card, text="+ Add step", width=110, command=add_step, **BLUE_).pack(anchor="w", padx=10, pady=(4, 10))

        def draw_steps():
            for w in steps_box.winfo_children():
                w.destroy()
            for n, st in enumerate(pp.get("steps") or [], start=1):
                step_row(n, st)

        def step_row(n, st):
            r = ctk.CTkFrame(steps_box, fg_color="#101814", corner_radius=6); r.pack(fill="x", padx=4, pady=3)
            ctk.CTkLabel(r, text=f"Step {n}", width=50, font=(FONT, 12, "bold")).pack(side="left", padx=(6, 2), pady=6)
            ctk.CTkLabel(r, text="wait", font=(FONT, 11), text_color="#a39d86").pack(side="left")

            def save_wait(v):
                try:
                    st["wait"] = max(0.0, float(v))
                    self.settings.save()
                except (TypeError, ValueError):
                    pass
            seconds_combo(r, ["0", "0.5", "1", "2", "3", "5"], float(st.get("wait", 1.0)), save_wait).pack(side="left", padx=4)

            def cap(rg):
                ok = self.logic.capture_step_picture(pp, st, rg)
                self.log(f"Pop up '{pp['name']}': step {n} picture saved." if ok else "Capture failed - drag a bigger box.")
            ctk.CTkButton(r, text="Picture", width=66, command=lambda: pick_box(cap), **BLUE_).pack(side="left", padx=2)
            ctk.CTkButton(r, text="Spot", width=50,
                          command=lambda: pick_point(lambda xy: st.__setitem__("click", xy)), **BTN_).pack(side="left", padx=2)
            ctk.CTkButton(r, text="X", width=28, fg_color="#7a2620", hover_color="#5e1d18", height=28,
                          command=lambda: (self.logic.remove_step(pp, st), draw_steps(), refresh())).pack(side="right", padx=6)
            lbl = ctk.CTkLabel(r, text="", font=(FONT, 11)); lbl.pack(side="left", padx=6)
            img = self._popup_thumb(self.logic.step_path(pp, st), (90, 24)) if self.logic.has_step_picture(pp, st) else None
            if any(st["click"]):
                txt, col = f"clicks ({st['click'][0]}, {st['click'][1]})", "#7ee0a6"
            elif img:
                txt, col = "clicks it", "#7ee0a6"
            else:
                txt, col = "needs a picture or spot", "#f08a7e"
            lbl.configure(image=img, text=txt, compound="left", text_color=col)
            lbl._img = img

        def refresh():
            if not win.winfo_exists():
                return
            img = self._popup_thumb(self.logic.popup_path(pp)) if self.logic.has_popup_picture(pp) else None
            pic_a.configure(image=img, text="" if img else "no picture yet", text_color="#f08a7e")
            pic_a._img = img
            a = self.logic.popup_area(pp)
            area_lbl.configure(text=f"its area ({a[2] - a[0]}x{a[3] - a[1]})" if a else "whole screen",
                               text_color="#7ee0a6" if a else "#a39d86")
            if pp.get("steps"):
                spot_lbl.configure(text="(steps are used)", text_color="#6f7a6e")
            else:
                spot_lbl.configure(text=f"clicks ({pp['click'][0]}, {pp['click'][1]})" if any(pp["click"])
                                   else "clicks where it's found", text_color="#7ee0a6")
            draw_steps()
            on_change()

        bottom = ctk.CTkFrame(win, fg_color="transparent"); bottom.pack(fill="x", padx=10, pady=8)
        ctk.CTkButton(bottom, text="▶ Test", width=80,
                      command=lambda: self._run_test(lambda: self.logic.test_popup(pp)), **BTN_).pack(side="left")
        ctk.CTkButton(bottom, text="Done", width=80, command=win.destroy, **BLUE_).pack(side="right")
        refresh()

    def _update_ok_threshold(self, val):
        self.settings.set("ok_match_threshold", round(float(val), 2))
        self.ok_thr_label.configure(text=f"Match: {int(float(val) * 100)}%")

    def _ok_switch_on(self):
        sw = getattr(self, "ok_area_switch", None)
        try:
            return sw is not None and sw.winfo_exists() and sw.get() == 1
        except Exception:
            return False

    def _clear_ok_setting(self, key, empty):
        self.settings.settings["regions"][key] = empty
        self.settings.save()
        if key == "ok_scan_area" and self._ok_switch_on():
            self.toggle_ok_area_overlay()
        self.refresh_ok_status()

    def refresh_ok_status(self):
        regions = self.settings.get("regions", {})
        is_set = lambda k: any(v != 0 for v in regions.get(k, [0]))
        good, muted = "#7ee0a6", "#6f7a6e"
        tpl_ok = is_set("ok_button") and os.path.exists(self.logic._ok_template_path())
        info = getattr(self, "_ok_row_info", None)
        if info is not None and info.winfo_exists():
            if not tpl_ok:
                txt, col = "needs a picture - press Edit", "#f08a7e"
            else:
                pos = regions.get("ok_click_pos", [0, 0])
                txt = f"then clicks ({pos[0]}, {pos[1]})" if is_set("ok_click_pos") else "then clicks the button"
                if is_set("ok_scan_area"):
                    txt += " · looks in your area"
                col = good
            info.configure(text=txt, text_color=col)
            img = self._popup_thumb(self.logic._ok_template_path(), (56, 20)) if tpl_ok else None
            self._ok_row_pic.configure(image=img, text="")
            self._ok_row_pic._img = img
        win = getattr(self, "_ok_win", None)
        if win is None or not win.winfo_exists():
            return
        if win.state() == "withdrawn":
            win.deiconify(); win.lift()
        self.ok_btn_status.configure(text="Captured" if tpl_ok else "Not set",
                                     text_color=good if tpl_ok else "#f08a7e")
        self.ok_area_status.configure(text="Custom" if is_set("ok_scan_area") else "Default",
                                      text_color=good if is_set("ok_scan_area") else muted)
        pos = regions.get("ok_click_pos", [0, 0])
        self.ok_click_status.configure(text=f"({pos[0]}, {pos[1]})" if is_set("ok_click_pos") else "Default",
                                       text_color=good if is_set("ok_click_pos") else muted)
        try:
            from PIL import Image
            if tpl_ok:
                img = Image.open(self.logic._ok_template_path())
                img.thumbnail((140, 40))
                self._ok_preview_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self.ok_preview.configure(image=self._ok_preview_img)
        except Exception:
            pass

    def toggle_always_ok(self):
        self._always_ok_on = not self._always_ok_on
        for b in getattr(self, "_ok_toggles", [self.always_ok_btn]):
            style_toggle(b, self._always_ok_on, "Always Click Pop Ups")
        if self._always_ok_on:
            self.logic.start_global_ok_scanner()
        else:
            self.logic.stop_global_ok_scanner()

    def pick_ok_button(self):
        self._hide_for_pick()
        Overlay(lambda x1, y1, x2, y2: self.root.after(300, lambda: self._save_ok_button(x1, y1, x2, y2)))

    def _save_ok_button(self, x1, y1, x2, y2):
        self.settings.settings["regions"]["ok_button"] = [x1, y1, x2, y2]
        self.settings.save()
        ok = self.logic.capture_ok_template([x1, y1, x2, y2])
        self.root.deiconify()
        self.log("OK button captured." if ok else "OK button capture failed — try a larger box.")
        self.refresh_ok_status()

    def toggle_ok_area_overlay(self):
        old = self.overlays.pop("_ok_area", None)
        if old: old.destroy()
        if not self._ok_switch_on():
            return
        rect = self.logic.get_ok_search_region()
        if rect and not any(v != 0 for v in self.settings.get("regions", {}).get("ok_scan_area", [0, 0, 0, 0])):
            self.log("No Scan Area set: the whole screen is scanned (nothing to draw).")
            self.ok_area_switch.deselect()
        elif rect:
            self.overlays["_ok_area"] = PersistentOverlay(rect[0], rect[1], rect[2], rect[3], color="orange")
        else:
            self.log("No OK scan area yet — set one or capture the OK button first.")
            self.ok_area_switch.deselect()

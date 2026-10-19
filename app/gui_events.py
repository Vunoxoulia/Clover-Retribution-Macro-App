import time
import webbrowser
import links
import threading
import customtkinter as ctk
from overlay import Overlay, PointSelector
from logic_events import WATCHER, roblox_windows
from logic_base import BaseLogic
from ui_style import big_toggle, style_toggle, save_while_typing, sound_picker

CARD = dict(fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
BTN = dict(height=28, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")
BLUE = dict(fg_color="#0d6efd", hover_color="#0b5ed7")
RED = dict(fg_color="#842029", hover_color="#6a1a21")


class EventsPage:
    """The Events page. Lives in every macro (like OK Popup) and in the standalone Event Notifier.
    The watcher itself is shared, so the ON toggle keeps working when you switch macros."""

    def __init__(self, parent, root, settings):
        self.root = root
        WATCHER.attach(settings)
        WATCHER.on_log = self._log
        self.cfg = WATCHER.cfg
        sf = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        sf.pack(fill="both", expand=True, padx=4, pady=4)
        # same scrollbar speed-up as the Skill Macro pages
        sb_canvas = getattr(getattr(sf, "_scrollbar", None), "_canvas", None)
        if sb_canvas is not None:
            sb_canvas.update_idletasks = lambda: None
        self.sf = sf
        # Always OFF when the app opens; you turn it on yourself. Once on, it stays on while you switch macros.
        self._seen_windows = None
        self.build()
        self.root.after(3000, self._watch_windows)

    # ---------- helpers ----------
    def _log(self, msg):
        def show():
            try:
                if self.status.winfo_exists():
                    self.status.configure(text=msg)
            except Exception:
                pass                             # this macro's window was closed; the watcher keeps going
        try:
            self.root.after(0, show)
        except Exception:
            pass

    def _save(self):
        WATCHER.save()

    def _entry(self, parent, d, key, width, placeholder="", show=None, on_save=None):
        e = ctk.CTkEntry(parent, width=width, font=("Arial", 12), placeholder_text=placeholder, show=show)
        if d.get(key):
            e.insert(0, str(d[key]))

        def store():
            d[key] = e.get().strip()
            self._save()

        def commit(_=None):
            store()
            if on_save:
                on_save(d[key])
        e.bind("<FocusOut>", commit)
        e.bind("<Return>", commit)
        save_while_typing(e, store)                  # saved while you type, no click-away needed
        return e

    # ---------- layout ----------
    def build(self):
        cfg, p = self.cfg, self.sf
        top = ctk.CTkFrame(p, **CARD); top.pack(fill="x", pady=4)
        head = ctk.CTkFrame(top, fg_color="transparent"); head.pack(fill="x", padx=10, pady=(8, 0))
        ctk.CTkLabel(head, text="Event Notifier", font=("Arial", 16, "bold"), text_color="#0d6efd").pack(side="left")
        ctk.CTkButton(head, text="▶ Video", width=64, height=24, font=("Arial", 11, "bold"), fg_color="#343a40",
                      hover_color="#495057", text_color="#ff6b6b",
                      command=lambda: links.open_link("video_events")).pack(side="right")
        ctk.CTkLabel(top, text="Posts the [Event] / [Leak] lines from every Roblox window's chat to Discord. Keeps running in every macro.",
                     font=("Arial", 12), text_color="#ced4da", wraplength=420, justify="left").pack(anchor="w", padx=10)
        self.toggle = big_toggle(top, self.flip)
        self.toggle.pack(fill="x", padx=10, pady=(8, 4))
        self._style_toggle()

        ctk.CTkLabel(top, text="", height=2).pack()

        # ---- what happened lately ----
        rc = self._section(p, "Last events")
        self.recent_box = ctk.CTkLabel(rc, text="", font=("Consolas", 11), text_color="#ced4da",
                                       justify="left", anchor="w")
        self.recent_box.pack(fill="x", padx=10, pady=(0, 8))
        self._recent_tick()

        # ---- Discord ----
        dc = self._section(p, "Discord")
        row = ctk.CTkFrame(dc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(2, 2))
        ctk.CTkLabel(row, text="Webhook", width=70, anchor="w", font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkButton(row, text="Send test", width=80, command=self.send_test, **BTN).pack(side="right", padx=(6, 0))
        self._entry(row, cfg, "webhook", 200, "https://discord.com/api/webhooks/...", show="•").pack(side="left", fill="x", expand=True)
        row = ctk.CTkFrame(dc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row, text="Ping", width=70, anchor="w", font=("Arial", 12, "bold")).pack(side="left")
        self._people_button(row, cfg, "mention", "every alert", wide=True).pack(side="left", fill="x", expand=True)
        self.mention_hint = ctk.CTkLabel(dc, text="",
                                         font=("Arial", 12), text_color="#ced4da", wraplength=340, justify="left",
                                         anchor="w")
        self.mention_hint.pack(fill="x", padx=(86, 8), pady=(0, 4))

        # ---- Checking ----
        ck = self._section(p, "Checking the chat")
        row = ctk.CTkFrame(ck, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(2, 2))
        ctk.CTkLabel(row, text="Check every", font=("Arial", 12)).pack(side="left")
        iv_opts = {"15 s": 15, "30 s": 30, "1 min": 60, "2 min": 120, "5 min": 300}
        iv = ctk.CTkOptionMenu(row, values=list(iv_opts), width=78, height=26,
                               command=lambda v: (self.cfg.__setitem__("interval", iv_opts[v]), self._save()))
        iv.set(next((k for k, v in iv_opts.items() if v == int(cfg.get("interval", 60))), "1 min"))
        iv.pack(side="left", padx=(4, 12))
        ctk.CTkLabel(row, text="Same event again after", font=("Arial", 12)).pack(side="left")
        cd = ctk.CTkOptionMenu(row, values=["1 min", "2 min", "5 min", "10 min"], width=84, height=26,
                               command=lambda v: (self.cfg.__setitem__("cooldown", int(v.split()[0]) * 60), self._save()))
        cd.set(f"{int(cfg.get('cooldown', 120)) // 60} min")
        cd.pack(side="left", padx=(4, 0))
        only = ctk.CTkCheckBox(ck, text="Only [Event] / [Leak] lines (ignore player chat)", font=("Arial", 12),
                               command=lambda: (self.cfg.__setitem__("event_lines_only", bool(only.get())), self._save()))
        if cfg.get("event_lines_only", True):
            only.select()
        only.pack(anchor="w", padx=10, pady=(6, 2))
        hov = ctk.CTkCheckBox(ck, text="Move the mouse onto the chat before reading (it fades out otherwise)",
                              font=("Arial", 12),
                              command=lambda: (self.cfg.__setitem__("hover_chat", bool(hov.get())), self._save()))
        if cfg.get("hover_chat", True):
            hov.select()
        hov.pack(anchor="w", padx=10, pady=2)
        sound_row = ctk.CTkFrame(ck, fg_color="transparent")

        def flip_sound():
            self.cfg["sound_on_alert"] = bool(snd.get()); self._save()
            sound_row.pack(anchor="w", padx=38, pady=(0, 2), after=snd) if snd.get() else sound_row.pack_forget()
        snd = ctk.CTkCheckBox(ck, text="Play a sound when an event is posted", font=("Arial", 12), command=flip_sound)
        if cfg.get("sound_on_alert", False):
            snd.select()
        snd.pack(anchor="w", padx=10, pady=2)
        sound_picker(sound_row, "event").pack(anchor="w")
        if snd.get():
            sound_row.pack(anchor="w", padx=38, pady=(0, 2), after=snd)
        row = ctk.CTkFrame(ck, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row, text="Warn when a window's chat can't be read for", font=("Arial", 12)).pack(side="left")
        uw_opts = {"never": 0, "3 min": 3, "5 min": 5, "10 min": 10, "15 min": 15}
        uw = ctk.CTkOptionMenu(row, values=list(uw_opts), width=80, height=26,
                               command=lambda v: (self.cfg.__setitem__("unreadable_warn", uw_opts[v]), self._save()))
        uw.set(next((k for k, v in uw_opts.items() if v == int(cfg.get("unreadable_warn", 10) or 0)), "10 min"))
        uw.pack(side="left", padx=4)
        row = ctk.CTkFrame(ck, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkButton(row, text="Test read", width=80, command=self.test_read, **BTN).pack(side="left")
        self.win_lbl = ctk.CTkLabel(row, text="", font=("Arial", 12), text_color="#ced4da")
        self.win_lbl.pack(side="left", padx=8)
        self._refresh_area()
        ctk.CTkLabel(ck, text="", height=4).pack()

        # ---- Clear chat ----
        cc = self._section(p, "Clear the chat after an alert")
        row = ctk.CTkFrame(cc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(2, 2))
        clr = ctk.CTkCheckBox(row, text="Clear it, using", font=("Arial", 12),
                              command=lambda: (self.cfg.__setitem__("clear_chat", bool(clr.get())), self._save(),
                                               self._show_clear_options()))
        if cfg.get("clear_chat"):
            clr.select()
        clr.pack(side="left")
        cmd = ctk.CTkOptionMenu(row, values=["/clear", "/cls"], width=80, height=26,
                                command=lambda v: (self.cfg.__setitem__("clear_cmd", v), self._save()))
        cmd.set(cfg.get("clear_cmd", "/clear"))
        cmd.pack(side="left", padx=6)
        # only shown while clearing is on
        self._clear_opts = ctk.CTkFrame(cc, fg_color="transparent")
        glb = ctk.CTkCheckBox(self._clear_opts, text="Type it in the Global tab, then go back to Here", font=("Arial", 12),
                              command=lambda: (self.cfg.__setitem__("clear_in_global", bool(glb.get())), self._save(),
                                               self._show_clear_options()))
        if cfg.get("clear_in_global", True):
            glb.select()
        glb.pack(anchor="w", padx=2, pady=(4, 2))
        self._tabs_hint = ctk.CTkLabel(self._clear_opts, text="Set each window's tabs below (Here / Global tabs).",
                                       font=("Arial", 12), text_color="#adb5bd")
        ctk.CTkLabel(cc, text="", height=4).pack(side="bottom")

        # ---- one PS code per Roblox window ----
        wc = ctk.CTkFrame(p, **CARD); wc.pack(fill="x", pady=4)
        wh = ctk.CTkFrame(wc, fg_color="transparent"); wh.pack(fill="x", padx=10, pady=(8, 0))
        ctk.CTkLabel(wh, text="Roblox windows", font=("Arial", 13, "bold")).pack(side="left")
        ctk.CTkButton(wh, text="↻ Refresh", width=80, command=self.build_windows, **BTN).pack(side="right")
        ctk.CTkButton(wh, text="Show all", width=90, command=self.show_all_windows,
                      **{**BTN, **BLUE}).pack(side="right", padx=6)
        ctk.CTkLabel(wc, text="Numbered top-left first. Show = which window is which.",
                     font=("Arial", 12), text_color="#ced4da", wraplength=420, justify="left").pack(anchor="w", padx=10)
        self.win_box = ctk.CTkFrame(wc, fg_color="transparent"); self.win_box.pack(fill="x", padx=8, pady=(4, 8))
        self._show_clear_options()                       # also builds the window list

        self.status = ctk.CTkLabel(p, text="", font=("Arial", 12, "bold"), text_color="#75b798", anchor="w",
                                   wraplength=420, justify="left")
        self.status.pack(fill="x", padx=8, pady=(2, 2))

        lh = ctk.CTkFrame(p, fg_color="transparent"); lh.pack(fill="x", padx=4, pady=(6, 2))
        ctk.CTkLabel(lh, text="Events", font=("Arial", 14, "bold")).pack(side="left", padx=4)
        ctk.CTkButton(lh, text="+ Add event", width=100, command=self.add_event, **{**BTN, **BLUE}).pack(side="right")
        ctk.CTkLabel(p, text="name · chat words · ping · role ID · Test",
                     font=("Arial", 12), text_color="#adb5bd").pack(anchor="w", padx=8)
        bulk = ctk.CTkFrame(p, fg_color="transparent"); bulk.pack(fill="x", padx=4, pady=(2, 0))
        ctk.CTkButton(bulk, text="Tick shown", width=84, command=lambda: self._tick_shown(True), **BTN).pack(side="left", padx=2)
        ctk.CTkButton(bulk, text="Untick shown", width=94, command=lambda: self._tick_shown(False), **BTN).pack(side="left", padx=2)
        ctk.CTkButton(bulk, text="Import list", width=84, command=self.import_events, **BTN).pack(side="right", padx=2)
        ctk.CTkButton(bulk, text="Export list", width=84, command=self.export_events, **BTN).pack(side="right", padx=2)
        # search + pages, so a long list doesn't mean scrolling forever
        sr = ctk.CTkFrame(p, fg_color="transparent"); sr.pack(fill="x", padx=4, pady=(4, 2))
        self._search = ctk.CTkEntry(sr, placeholder_text="Search events (name or words)...", height=28,
                                    font=("Arial", 12))
        self._search.pack(side="left", fill="x", expand=True, padx=(4, 6))
        self._search.bind("<KeyRelease>", lambda e: (setattr(self, "_page_no", 0), self.render_events()))
        ctk.CTkButton(sr, text="Clear", width=56, command=lambda: (self._search.delete(0, "end"),
                                                                  setattr(self, "_page_no", 0),
                                                                  self.render_events()), **BTN).pack(side="left")
        self.list_box = ctk.CTkFrame(p, fg_color="transparent"); self.list_box.pack(fill="x")
        pg = ctk.CTkFrame(p, fg_color="transparent"); pg.pack(fill="x", pady=(4, 2))
        self._prev = ctk.CTkButton(pg, text="Prev", width=60, command=lambda: self._turn(-1), **BTN)
        self._prev.pack(side="left", padx=(4, 4))
        self._page_lbl = ctk.CTkLabel(pg, text="", font=("Arial", 12))
        self._page_lbl.pack(side="left", padx=6)
        self._next = ctk.CTkButton(pg, text="Next", width=60, command=lambda: self._turn(1), **BTN)
        self._next.pack(side="left", padx=4)
        self._page_no = 0
        self.render_events()

    PER_PAGE = 8

    def _matching_events(self):
        q = (self._search.get() if hasattr(self, "_search") else "").strip().lower()
        evs = self.cfg["events"]
        if not q:
            return evs
        return [e for e in evs if q in (e.get("name") or "").lower() or q in (e.get("keyword") or "").lower()]

    def render_events(self):
        """Show one page of (matching) events."""
        for w in self.list_box.winfo_children():
            w.destroy()
        evs = self._matching_events()
        pages = max(1, -(-len(evs) // self.PER_PAGE))
        self._page_no = max(0, min(getattr(self, "_page_no", 0), pages - 1))
        start = self._page_no * self.PER_PAGE
        for ev in evs[start:start + self.PER_PAGE]:
            self._event_row(ev)
        if not evs:
            ctk.CTkLabel(self.list_box, text="No event matches that search.", font=("Arial", 12),
                         text_color="#adb5bd").pack(pady=8)
        total = len(self.cfg["events"])
        self._page_lbl.configure(text=f"Page {self._page_no + 1} of {pages}   ·   "
                                      + (f"{len(evs)} of {total} events" if len(evs) != total else f"{total} events"))
        self._prev.configure(state="normal" if self._page_no > 0 else "disabled")
        self._next.configure(state="normal" if self._page_no < pages - 1 else "disabled")

    def _turn(self, step):
        self._page_no = getattr(self, "_page_no", 0) + step
        self.render_events()

    def _show_clear_options(self):
        """Global-tab option + tab buttons only make sense while 'Clear it' is ticked."""
        on = bool(self.cfg.get("clear_chat"))
        if on:
            self._clear_opts.pack(fill="x", padx=8)
        else:
            self._clear_opts.pack_forget()
        if on and self.cfg.get("clear_in_global", True):
            self._tabs_hint.pack(anchor="w", padx=28, pady=(0, 4))
        else:
            self._tabs_hint.pack_forget()
        if hasattr(self, "win_box"):
            self.build_windows()

    def _section(self, parent, title):
        """One card with a bold title: Discord / Checking / Clear chat."""
        card = ctk.CTkFrame(parent, **CARD); card.pack(fill="x", pady=4)
        ctk.CTkLabel(card, text=title, font=("Arial", 13, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        return card

    def _event_row(self, ev):
        r = ctk.CTkFrame(self.list_box, **CARD); r.pack(fill="x", pady=2)
        cb = ctk.CTkCheckBox(r, text="", width=24, command=lambda: (ev.__setitem__("enabled", bool(cb.get())), self._save()))
        if ev.get("enabled", True):
            cb.select()
        cb.pack(side="left", padx=(8, 2), pady=5)
        self._entry(r, ev, "name", 88, "Event name").pack(side="left", padx=2)
        self._entry(r, ev, "keyword", 88, "keyword").pack(side="left", padx=2)

        def remove():
            lst = self.cfg["events"]
            del lst[next(i for i, x in enumerate(lst) if x is ev)]
            self._save()
            self.render_events()
        ctk.CTkButton(r, text="X", width=26, height=26, command=remove, **RED).pack(side="right", padx=(2, 6))
        ctk.CTkButton(r, text="Test", width=40, command=lambda: self.test_event(ev),
                      **BTN).pack(side="right", padx=2)
        self._people_button(r, ev, "mention", ev.get("name") or "this event").pack(side="left", padx=2)
        self._entry(r, ev, "role", 90, "role ID",
                    on_save=lambda v, n=ev: self._check_role(v, n.get("name") or "this event")
                    ).pack(side="left", padx=2, fill="x", expand=True)

    def _check_role(self, value, where):
        from logic_events import role_text
        bad = [x for x in (value or "").replace(",", " ").split() if not role_text(x)]
        if bad:
            self._log(f"Role for {where}: {', '.join(bad)} isn't a role ID. Server Settings → Roles → "
                      f"right-click the role → Copy Role ID (Developer Mode on).")
        elif value:
            self._log(f"{where} will ping {len(value.replace(',', ' ').split())} role(s).")

    # ---------- actions ----------
    def _style_toggle(self):
        style_toggle(self.toggle, WATCHER.running, "Event alerts", icon_on="", icon_off="")

    def flip(self):
        if WATCHER.running:
            WATCHER.stop()
            self.cfg["enabled"] = False
        else:
            if not WATCHER.has_chat_area():
                self._log("Press Chat next to each Roblox window first.")
                return
            WATCHER.start()
            self.cfg["enabled"] = True
        self._save()
        self._style_toggle()

    def test_event(self, ev):
        """Test one event: uses the real chat line if its words are in a chat now, else posts a test message."""
        self._log(f"Testing '{ev.get('name') or 'event'}'... (reading the chat first)")

        def run():
            try:
                msg = WATCHER.test_event(ev)
            except Exception as e:
                msg = f"Test failed: {e}"
            self._log(msg)
            self._refresh_recent()
        threading.Thread(target=run, daemon=True).start()

    def _tick_shown(self, on):
        """Tick / untick every event the search shows (all of them when there's no search) - e.g. search
        'wisp' then Tick shown = all Wisps on."""
        evs = self._matching_events()
        for ev in evs:
            ev["enabled"] = on
        self._save()
        self.render_events()
        self._log(f"{'Ticked' if on else 'Unticked'} {len(evs)} event(s).")

    def export_events(self):
        import json
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(parent=self.root, title="Export event list", defaultextension=".json",
                                            initialfile="Event list.json", filetypes=[("Event list", "*.json")])
        if not path:
            return
        keep = ("name", "keyword")            # only what the event IS - never roles or people (privacy)
        data = {"type": "event_list", "events": [{k: ev[k] for k in keep if ev.get(k) not in (None, "")}
                                                 for ev in self.cfg["events"]]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        self._log(f"Exported {len(data['events'])} events - share the file, others use Import list.")

    def import_events(self):
        """Add the file's events; ones with the same name are updated (your webhook / windows aren't touched)."""
        import json
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(parent=self.root, title="Import event list", filetypes=[("Event list", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("events") if isinstance(data, dict) else data
            assert isinstance(items, list)
        except Exception:
            messagebox.showerror("Import", "That file isn't an event list.", parent=self.root)
            return
        by_name = {(ev.get("name") or "").strip().lower(): ev for ev in self.cfg["events"]}
        added = updated = 0
        for it in items:
            if not isinstance(it, dict) or not (it.get("name") or "").strip():
                continue
            clean = {k: it[k] for k in ("name", "keyword") if k in it}   # roles / people never come from a file
            cur = by_name.get(clean["name"].strip().lower())
            if cur is not None:
                cur.update(clean); updated += 1
            else:
                clean.setdefault("enabled", True); clean.setdefault("keyword", ""); clean.setdefault("mention", "")
                self.cfg["events"].append(clean); added += 1
        self._save()
        self.render_events()
        self._log(f"Imported: {added} new, {updated} updated.")

    def _refresh_recent(self):
        """The 'Last events' list (newest first)."""
        def show():
            try:
                if not self.recent_box.winfo_exists():
                    return
            except Exception:
                return
            items = list(reversed(WATCHER.recent))[:10]
            text = "\n".join(f"{time.strftime('%H:%M', time.localtime(t))}  {name}  (window {n})  -  {what}"
                              for t, name, n, what in items) or "Nothing yet - events show up here when they're posted."
            self.recent_box.configure(text=text)
        try:
            self.root.after(0, show)
        except Exception:
            pass

    def _recent_tick(self):
        self._refresh_recent()
        try:
            if self.recent_box.winfo_exists():
                self.root.after(5000, self._recent_tick)
        except Exception:
            pass

    def add_event(self):
        ev = {"enabled": True, "name": "", "keyword": "", "mention": ""}
        self.cfg["events"].append(ev)
        self._save()
        if hasattr(self, "_search"):
            self._search.delete(0, "end")                 # show it: no filter, last page
        self._page_no = 10 ** 6
        self.render_events()

    # ---------- people (saved Discord users to ping) ----------
    def _people(self):
        return self.cfg.setdefault("people", [])

    def _people_label(self, value, wide):
        ids = (value or "").split()
        if not ids:
            return "nobody — click to pick" if wide else "+ ping"
        names = {p["id"]: p["name"] for p in self._people()}
        shown = [names.get(i.strip("<@!&>"), i) for i in ids]
        if wide:
            return "" + ", ".join(shown)
        return f"{len(shown)} ping" if len(shown) == 1 else f"{len(shown)} pings"

    def _people_button(self, parent, d, key, where, wide=False):
        btn = ctk.CTkButton(parent, text=self._people_label(d.get(key), wide), width=200 if wide else 52, height=28,
                            anchor="w" if wide else "center", font=("Arial", 12), fg_color="#343638",
                            hover_color="#495057", border_width=1, border_color="#565b5e")
        btn.configure(command=lambda: PeoplePicker(self, d, key, where,
                                                   lambda: btn.configure(text=self._people_label(d.get(key), wide))))
        return btn

    def _check_mention(self, value, where=None):
        """Warn right away when a NAME was typed: webhooks can only ping by ID."""
        from logic_events import check_mentions
        ok, bad = check_mentions(value)
        if bad:
            text = (f"{', '.join(bad)} won't ping{' (' + where + ')' if where else ''}: Discord needs the ID, "
                    f"not the name. Turn on Developer Mode (Settings → Advanced), right-click the user → Copy User ID. "
                    f"Role: right-click it → Copy Role ID, put & in front.")
            color = "#ffc107"
        elif ok:
            kinds = ["role" if "&" in x else "user" for x in ok]
            text, color = f"will ping {len(ok)} {'/'.join(sorted(set(kinds)))}{'s' if len(ok) > 1 else ''}", "#75b798"
        else:
            text, color = "", "#adb5bd"
        if where is None:
            self.mention_hint.configure(text=text, text_color=color)
        elif bad:
            self._log(text)

    def pick_window_chat(self, n):
        """Drag the chat box of ONE window."""
        self.root.withdraw(); self.root.update(); time.sleep(0.2)

        def done(x1, y1, x2, y2):
            self.root.deiconify()
            if WATCHER.set_window_chat(n, x1, y1, x2, y2):
                self._log(f"Window {n}'s chat area saved. Press Show to check the yellow box.")
            else:
                self._log(f"Window {n} isn't open any more — press ↻ Refresh.")
            self.build_windows()
        Overlay(done)

    def pick_window_tabs(self, n):
        """Click this window's chat 'Here' tab, then its 'Global' tab (used by /clear in Global).
        Saved per window, relative to the window, so moving it doesn't break them."""
        wins = roblox_windows()
        if not 1 <= n <= len(wins):
            self._log(f"Window {n} isn't open any more — press ↻ Refresh.")
            return
        w = wins[n - 1]
        self.root.withdraw(); self.root.update(); time.sleep(0.2)
        picked = {}

        def got_global(x, y):
            picked["global"] = [x - w.left, y - w.top]
            self.root.deiconify()
            self.cfg.setdefault("window_tabs", {})[str(n)] = picked
            self._save()
            self._log(f"Window {n}: Here and Global tabs saved - /clear will click Global, clear, then click Here.")
            self.build_windows()

        def got_here(x, y):
            picked["here"] = [x - w.left, y - w.top]
            type("PickGlobal", (PointSelector,), {"HINT": f"Window {n}: now click the GLOBAL tab"})(got_global)
        type("PickHere", (PointSelector,), {"HINT": f"Window {n}: click the HERE tab of its chat"})(got_here)

    def _window_key(self):
        try:
            return tuple(w.getHandle() for w in roblox_windows())
        except Exception:
            return ()

    def _watch_windows(self):
        """Every 3 s: if Roblox windows opened/closed/were re-ordered, rebuild the list by itself
        (only when something changed, so typing a PS code isn't interrupted)."""
        try:
            if not self.win_box.winfo_exists():
                return                                   # this page was closed
        except Exception:
            return
        if self._window_key() != self._seen_windows:
            self.build_windows()
        self.root.after(3000, self._watch_windows)

    def build_windows(self):
        for w in self.win_box.winfo_children():
            w.destroy()
        wins = roblox_windows()
        self._seen_windows = tuple(w.getHandle() for w in wins)
        if not wins:
            ctk.CTkLabel(self.win_box, text="No Roblox window found yet — it shows up here a few seconds after Roblox opens.",
                         font=("Arial", 12), text_color="#ea868f", wraplength=400, justify="left").pack(anchor="w", padx=4)
            return
        ps = self.cfg.setdefault("window_ps", {})
        for i, w in enumerate(wins, start=1):
            card = ctk.CTkFrame(self.win_box, fg_color="#1a1d20", corner_radius=6); card.pack(fill="x", pady=3)
            r = ctk.CTkFrame(card, fg_color="transparent"); r.pack(fill="x", padx=6, pady=(5, 2))
            ctk.CTkLabel(r, text=f"Window {i}", width=72, anchor="w", font=("Arial", 12, "bold")).pack(side="left")
            worlds = self.cfg.setdefault("window_world", {})
            seg = ctk.CTkSegmentedButton(r, values=list(WATCHER.WORLDS), height=26, font=("Arial", 12),
                                         command=lambda v, n=i: (self.cfg["window_world"].__setitem__(str(n), v),
                                                                 self._save()))
            seg.set(WATCHER.world_for(i))
            seg.pack(side="left")
            ctk.CTkButton(r, text="Show", width=70, command=lambda win=w, n=i: self.show_window(win, n),
                          **BTN).pack(side="right", padx=(6, 0))
            r2 = ctk.CTkFrame(card, fg_color="transparent"); r2.pack(fill="x", padx=6, pady=(0, 2))
            ctk.CTkLabel(r2, text="PS code", width=72, anchor="w", font=("Arial", 12)).pack(side="left")
            self._entry(r2, ps, str(i), 140, f"PS code for window {i}").pack(side="left", fill="x", expand=True)
            r3 = ctk.CTkFrame(card, fg_color="transparent"); r3.pack(fill="x", padx=6, pady=(2, 6))
            ctk.CTkLabel(r3, text="", width=72).pack(side="left")
            green = {"fg_color": "#198754", "hover_color": "#157347"}
            own = str(i) in self.cfg.get("window_chat", {})
            ctk.CTkButton(r3, text="Chat box" if own else "Drag chat box", width=130,
                          command=lambda n=i: self.pick_window_chat(n),
                          **{**BTN, **(green if own else BLUE)}).pack(side="left")
            if self.cfg.get("clear_chat") and self.cfg.get("clear_in_global", True):   # only used by /clear in Global
                tabs = self.cfg.get("window_tabs", {}).get(str(i), {})
                has_tabs = "here" in tabs and "global" in tabs
                ctk.CTkButton(r3, text="Here / Global tabs" if has_tabs else "Set Here / Global tabs", width=160,
                              command=lambda n=i: self.pick_window_tabs(n),
                              **{**BTN, **(green if has_tabs else {})}).pack(side="left", padx=6)
        if hasattr(self, "win_lbl"):
            self._refresh_area()

    def _label_window(self, w, n, secs=3.0):
        """Big 'WINDOW n' tag in the middle of that Roblox window, plus a cyan frame around it."""
        import tkinter as tk
        tops = []
        # frame: four thin cyan bars along the window's edges
        for x, y, ww, hh in ((w.left, w.top, w.width, 6), (w.left, w.top + w.height - 6, w.width, 6),
                             (w.left, w.top, 6, w.height), (w.left + w.width - 6, w.top, 6, w.height)):
            t = tk.Toplevel(self.root); t.overrideredirect(True); t.attributes("-topmost", True)
            t.configure(bg="#0dcaf0"); t.geometry(f"{max(1, ww)}x{max(1, hh)}+{x}+{y}")
            tops.append(t)
        region = WATCHER.chat_region(w)
        if region:                                       # the chat box this window is read from (yellow)
            x1, y1, x2, y2 = region
            for x, y, ww, hh in ((x1, y1, x2 - x1, 3), (x1, y2 - 3, x2 - x1, 3), (x1, y1, 3, y2 - y1), (x2 - 3, y1, 3, y2 - y1)):
                b = tk.Toplevel(self.root); b.overrideredirect(True); b.attributes("-topmost", True)
                b.configure(bg="#ffc107"); b.geometry(f"{max(1, ww)}x{max(1, hh)}+{x}+{y}")
                tops.append(b)
        t = tk.Toplevel(self.root); t.overrideredirect(True); t.attributes("-topmost", True)
        t.configure(bg="#0d6efd")
        tk.Label(t, text=f"WINDOW {n}", font=("Arial", 40, "bold"), fg="white", bg="#0d6efd", padx=30, pady=14).pack()
        tk.Label(t, text=self.cfg.get("window_ps", {}).get(str(n), "") or "(no PS code yet)",
                 font=("Arial", 14), fg="white", bg="#0d6efd", pady=(0)).pack(pady=(0, 10))
        t.update_idletasks()
        t.geometry(f"+{w.left + (w.width - t.winfo_width()) // 2}+{w.top + (w.height - t.winfo_height()) // 2}")
        tops.append(t)
        self.root.after(int(secs * 1000), lambda: [x.destroy() for x in tops if x.winfo_exists()])

    def show_window(self, w, n):
        try:
            self._label_window(w, n)
            self._log(f"Window {n} is labelled on screen.")
        except Exception as e:
            self._log(f"Couldn't show window {n}: {e}")

    def show_all_windows(self):
        wins = roblox_windows()
        for i, w in enumerate(wins, start=1):
            try:
                self._label_window(w, i)
            except Exception:
                pass
        self._log(f"Labelled {len(wins)} Roblox window(s)." if wins else "No Roblox window open.")

    def _refresh_area(self):
        n = len(roblox_windows())
        self.win_lbl.configure(text=f"{n} Roblox window{'s' if n != 1 else ''} found")

    def test_read(self):
        self._refresh_area()
        if not WATCHER.has_chat_area():
            self._log("Press Chat next to each Roblox window first."); return
        self._log("Reading chat…")

        def run():
            parts = []
            for i, w in enumerate(roblox_windows(), start=1):
                lines = WATCHER.read_lines(w, i)
                hits = [n for n, c in WATCHER.count_events(lines).items() if c]
                parts.append(f"Window {i}: {len(lines)} event line(s) read" +
                             (f" → {', '.join(hits)}" if hits else " → no listed events"))
            self._log("\n".join(parts) or "No Roblox window found.")
        threading.Thread(target=run, daemon=True).start()

    def send_test(self):
        """Read the chat of every Roblox window NOW and send what it really finds (marked [TEST])."""
        if not self.cfg.get("webhook", "").strip():
            self._log("Paste the Discord webhook first."); return
        self._log("Reading chat and sending a test…")

        def run():
            from logic_events import compact
            msgs, total_lines = [], 0
            wins = roblox_windows() if WATCHER.has_chat_area() else []
            for win_no, w in enumerate(wins, start=1):
                lines = WATCHER.read_lines(w, win_no)
                total_lines += len(lines)
                for ev in self.cfg["events"]:
                    kw = compact(ev.get("keyword", ""))
                    hit = next((t for t in lines if kw and kw in compact(t)), None)
                    if hit and ev.get("enabled", True):
                        msgs.append(f"[TEST] {WATCHER.format_message(ev, win_no)}\n> Window {win_no} chat: {hit}")
            if not msgs:
                if not WATCHER.has_chat_area():
                    why = "no chat box set yet (Chat next to each window)"
                elif not wins:
                    why = "no Roblox window found"
                else:
                    why = (f"read {total_lines} [Event] / [Leak] line(s) in {len(wins)} window(s), "
                           f"none match your event list right now")
                self._log(f"Nothing sent — {why}.")      # only shown here, not posted to Discord
                return
            sent = sum(1 for m in msgs if WATCHER.post(m))
            if sent == len(msgs):
                self._log(f"Sent {sent} test message(s): " + " | ".join(m.splitlines()[0] for m in msgs))
            else:
                why = getattr(WATCHER, "last_post_error", "") or "check the webhook"
                self._log(f"Only {sent}/{len(msgs)} sent — {why}.")
        threading.Thread(target=run, daemon=True).start()


class PeoplePicker(ctk.CTkToplevel):
    """Tick who to ping. People are saved once (name + Discord ID) and shared by every event."""

    def __init__(self, page, d, key, where, on_done):
        super().__init__(page.root)
        self.page, self.d, self.key, self.on_done = page, d, key, on_done
        self.title(f"Who to ping — {where}")
        self.geometry("380x440")
        self.attributes("-topmost", True)
        self.configure(fg_color="#1e2124")
        self.chosen = set((d.get(key) or "").split())
        ctk.CTkLabel(self, text=f"Ping for: {where}", font=("Arial", 14, "bold"), text_color=BLUE["fg_color"]
                     ).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(self, text="Tick everyone who should be pinged.", font=("Arial", 12),
                     text_color="#ced4da").pack(anchor="w", padx=14)
        self.box = ctk.CTkScrollableFrame(self, fg_color="#212529", height=200)
        self.box.pack(fill="both", expand=True, padx=12, pady=8)
        add = ctk.CTkFrame(self, fg_color="transparent"); add.pack(fill="x", padx=12)
        self.name_e = ctk.CTkEntry(add, width=110, placeholder_text="Name")
        self.name_e.pack(side="left")
        self.id_e = ctk.CTkEntry(add, width=160, placeholder_text="Discord user ID")
        self.id_e.pack(side="left", padx=6)
        ctk.CTkButton(add, text="+ Add", width=60, command=self.add, **{**BTN, **BLUE}).pack(side="left")
        self.msg = ctk.CTkLabel(self, text="ID: Discord → Developer Mode on → right-click the person → Copy User ID",
                                font=("Arial", 11), text_color="#ced4da", wraplength=350, justify="left")
        self.msg.pack(anchor="w", padx=14, pady=(4, 0))
        ctk.CTkButton(self, text="Done", width=100, command=self.done, **{**BTN, **BLUE}).pack(pady=10)
        self.fill()
        self.grab_set()

    def fill(self):
        for w in self.box.winfo_children():
            w.destroy()
        people = self.page._people()
        if not people:
            ctk.CTkLabel(self.box, text="No one saved yet — add someone below.", font=("Arial", 12),
                         text_color="#ced4da").pack(pady=10)
        for p in people:
            r = ctk.CTkFrame(self.box, fg_color="transparent"); r.pack(fill="x", pady=1)
            var = ctk.BooleanVar(value=p["id"] in self.chosen)
            ctk.CTkCheckBox(r, text=f"{p['name']}", variable=var, font=("Arial", 12),
                            command=lambda pid=p["id"], v=var: (self.chosen.add(pid) if v.get() else self.chosen.discard(pid))
                            ).pack(side="left")
            ctk.CTkLabel(r, text=p["id"], font=("Arial", 11), text_color="#ced4da").pack(side="left", padx=6)
            ctk.CTkButton(r, text="X", width=26, height=24, command=lambda pp=p: self.remove(pp), **RED).pack(side="right")

    def add(self):
        name, pid = self.name_e.get().strip(), self.id_e.get().strip().strip("<@!>")
        if not pid.isdigit() or len(pid) < 15:
            self.msg.configure(text="That's not a user ID (a long number). Usernames like rushe7201 can't be pinged.",
                               text_color="#ffc107")
            return
        people = self.page._people()
        if any(p["id"] == pid for p in people):
            self.msg.configure(text="Already in the list.", text_color="#ffc107")
            return
        people.append({"name": name or pid[-4:], "id": pid})
        self.chosen.add(pid)
        self.page._save()
        self.name_e.delete(0, "end"); self.id_e.delete(0, "end")
        self.msg.configure(text=f"Added {name or pid} (ticked).", text_color="#75b798")
        self.fill()

    def remove(self, p):
        people = self.page._people()
        del people[next(i for i, x in enumerate(people) if x is p)]
        self.chosen.discard(p["id"])
        self.page._save()
        self.fill()

    def done(self):
        order = [p["id"] for p in self.page._people() if p["id"] in self.chosen]
        extra = [i for i in self.chosen if i not in order]          # IDs typed in before the list existed
        self.d[self.key] = " ".join(order + extra)
        self.page._save()
        self.on_done()
        self.destroy()


class EventsOnlyLogic(BaseLogic):
    """Logic for the Event Notifier hub card. There's nothing to automate besides the OK popup
    clicker, so it reuses the normal macro window with just the Events + OK Popup pages."""

    def main_loop(self):
        self.app.log("Nothing to start here: use Event alerts on the Events page "
                     "and Always Click OK on the OK Popup page.")
        self.running = False

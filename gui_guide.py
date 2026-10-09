import os
import tkinter as tk
import customtkinter as ctk

W, H = 600, 230
BG = "#16191c"
SLOT = "#2b2f33"
SLOT_EDGE = "#8a7a55"
TXT = "#e9ecef"
DIM = "#adb5bd"
BLUE = "#0d6efd"
GREEN = "#75b798"
YELLOW = "#ffc107"
RED = "#ff3b3b"
CYAN = "#0dcaf0"

MOVES = ["Temporal\nFlick", "Stilled\nVolley", "Chrono\nBurst", "Chrono\nAnast.", "Future\nSight",
         "Mana\nStarfall", "Mana\nLance", "Mana\nVeil"]


# ---------- drawing helpers ----------
def slot(c, x, y, text, size=58, cooldown=False, outline=SLOT_EDGE):
    c.create_rectangle(x, y, x + size, y + size, fill="#141618" if cooldown else SLOT, outline=outline, width=2)
    c.create_text(x + size / 2, y + size / 2, text=text, fill=DIM if cooldown else TXT,
                  font=("Arial", 8 if not cooldown else 10, "bold"), justify="center")


def hotbar(c, x, y, n=8, size=58, gap=8, cooldown=(), labels=True):
    for i in range(n):
        sx = x + i * (size + gap)
        cd = i in cooldown
        slot(c, sx, y, f"[{12.4 + i * 3:.1f}]" if cd else MOVES[i % len(MOVES)], size, cd)
        if labels:
            c.create_text(sx + size / 2, y + size + 10, text=str((i + 1) % 10), fill=DIM, font=("Arial", 9))
    return x + n * (size + gap) - gap


def arrow(c, x1, y1, x2, y2, color=TXT):
    c.create_line(x1, y1, x2, y2, fill=color, width=2, arrow="last", arrowshape=(10, 12, 4))


def tag(c, x, y, text, color=BLUE, anchor="center"):
    t = c.create_text(x, y, text=text, fill="#ffffff", font=("Arial", 10, "bold"), anchor=anchor)
    x1, y1, x2, y2 = c.bbox(t)
    r = c.create_rectangle(x1 - 6, y1 - 3, x2 + 6, y2 + 3, fill=color, outline="")
    c.tag_raise(t, r)


def label(c, x, y, text, color=TXT, size=10, anchor="center", bold=False):
    c.create_text(x, y, text=text, fill=color, font=("Arial", size, "bold" if bold else "normal"),
                  anchor=anchor, justify="center")


def ui_box(c, x, y, w, h, text, fill="#343a40", color=TXT):
    c.create_rectangle(x, y, x + w, y + h, fill=fill, outline="#495057")
    label(c, x + w / 2, y + h / 2, text, color, 10)


# ---------- illustrations ----------
def draw_region(c):
    end = hotbar(c, 30, 55)
    c.create_rectangle(24, 49, end + 6, 119, outline=RED, width=2, dash=(6, 3))
    label(c, W / 2, 25, "Drag ONE box around all your skill icons", YELLOW, 11, bold=True)
    label(c, W / 2, 160, "Tight on the left / right edges  •  include the whole icon  •  skip the numbers underneath", DIM)


def draw_slots(c):
    end = hotbar(c, 30, 55)
    w = (end - 30) / 8
    for i in range(8):
        c.create_rectangle(30 + i * w, 52, 30 + (i + 1) * w - 2, 116, outline=CYAN, width=2)
    label(c, W / 2, 25, "Slots = 8  →  the box is cut into 8 equal parts", YELLOW, 11, bold=True)
    label(c, W / 2, 160, "Press  Show  to flash these cyan boxes. Each one should sit on exactly one icon.", DIM)


def draw_snapshot(c):
    slot(c, 90, 50, MOVES[6], 70)
    label(c, 125, 135, "READY  ✔", GREEN, 11, bold=True)
    label(c, 125, 155, "matches snapshot → can cast", DIM, 9)
    slot(c, 270, 50, "[40.8]", 70, cooldown=True)
    label(c, 305, 135, "COOLDOWN  ✖", YELLOW, 11, bold=True)
    label(c, 305, 155, "dark + timer → macro waits", DIM, 9)
    ui_box(c, 420, 62, 140, 34, "📸 Snapshot All", BLUE, "#ffffff")
    label(c, 490, 120, "Take it while EVERY\nmove is ready", TXT, 10)
    label(c, W / 2, 20, "The snapshot is what “ready” looks like", YELLOW, 11, bold=True)


def rrect(c, x1, y1, x2, y2, r=6, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
           x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


def drop(c, x, y, w, text, blue=False, h=22):
    """Mimics CTkComboBox (grey) / CTkOptionMenu (blue) from the real page."""
    body, btn = ("#1f6aa5", "#144870") if blue else ("#343638", "#565b5e")
    rrect(c, x, y, x + w, y + h, 5, fill=body, outline="" if blue else "#565b5e")
    rrect(c, x + w - 22, y, x + w, y + h, 5, fill=btn, outline="")
    label(c, x + 6, y + h / 2, text, "#dce4ee", 9, "w")
    label(c, x + w - 11, y + h / 2, "⌄", "#dce4ee", 9)


def small(c, x, y, text, anchor="w"):
    label(c, x, y, text, "#dce4ee", 9, anchor)


def marker(c, x, y, n):
    c.create_oval(x - 8, y - 8, x + 8, y + 8, fill=YELLOW, outline="")
    label(c, x, y, str(n), "#000000", 9, bold=True)


def real_card(c, y, rank, name, key, expanded=True, status=("no img", "#ea868f"), summary="default"):
    """One move card drawn like the real Rotation page (scaled to fit)."""
    rrect(c, 8, y, 592, y + (110 if expanded else 34), 8, fill="#212529", outline="#343a40")
    c.create_oval(16, y + 6, 38, y + 28, fill=BLUE, outline="")
    label(c, 27, y + 17, str(rank), "#ffffff", 10, bold=True)
    rrect(c, 42, y + 5, 58, y + 16, 3, fill="#495057", outline=""); label(c, 50, y + 10, "▲", "#adb5bd", 6)
    rrect(c, 42, y + 18, 58, y + 29, 3, fill="#495057", outline=""); label(c, 50, y + 23, "▼", "#adb5bd", 6)
    rrect(c, 64, y + 8, 82, y + 26, 4, fill="#1f6aa5", outline=""); label(c, 73, y + 17, "✓", "#ffffff", 9, bold=True)
    label(c, 88, y + 17, f"Slot {rank}", "#ffffff", 9, "w", True)
    rrect(c, 132, y + 6, 262, y + 28, 5, fill="#343638", outline="#565b5e")
    label(c, 138, y + 17, name or "Move name (optional)", "#dce4ee" if name else DIM, 9, "w")
    small(c, 272, y + 17, "Key")
    drop(c, 296, y + 6, 48, key)
    label(c, 474, y + 17, status[0], status[1], 9, "e")
    rrect(c, 482, y + 6, 508, y + 28, 5, fill="#495057", outline=""); label(c, 495, y + 17, "📸", "#ffffff", 8)
    rrect(c, 514, y + 6, 556, y + 28, 5, fill=BLUE if expanded else "#495057", outline="")
    label(c, 535, y + 17, "⚙ ▴" if expanded else "⚙ ▾", "#ffffff", 9)
    if not expanded:
        label(c, 354, y + 17, summary, "#adb5bd", 9, "w")
        return
    r2 = y + 40
    small(c, 60, r2 + 11, "⏱ Delay before (s)"); drop(c, 166, r2, 54, "0.1")
    small(c, 232, r2 + 11, "⏱ Delay after (s)"); drop(c, 330, r2, 54, "0.5")
    label(c, 400, r2 + 11, "mouse → before → key → M1 → after", "#6c757d", 8, "w")
    r3 = y + 76
    small(c, 60, r3 + 11, "Repeat"); drop(c, 104, r3, 44, "3", blue=True)
    rrect(c, 222, r3 + 3, 238, r3 + 19, 3, fill=BLUE, outline=""); label(c, 230, r3 + 11, "✔", "#ffffff", 8, bold=True)
    small(c, 244, r3 + 11, "then M1")
    small(c, 310, r3 + 11, "Cooldown (s)"); drop(c, 388, r3, 52, "off")


def draw_tune(c):
    label(c, W / 2, 16, "A move that's READY but Test says 'cd'? Auto-tune it", YELLOW, 11, bold=True)
    rrect(c, 330, 34, 430, 60, 6, fill=BLUE, outline=""); label(c, 380, 47, "🪄 Auto-tune", "#ffffff", 10, bold=True)
    rrect(c, 438, 34, 494, 60, 6, fill="#495057", outline=""); label(c, 466, 47, "Test", "#ffffff", 10)
    marker(c, 330, 30, 1); marker(c, 438, 30, 2)
    # before / after
    label(c, 150, 80, "Before", "#adb5bd", 10, bold=True)
    label(c, 450, 80, "After Auto-tune", GREEN, 10, bold=True)
    arrow(c, 262, 120, 338, 120, DIM)
    for i, (name, before, after) in enumerate([("Mana Lance", ("cd 0.78/0.85", YELLOW), ("ready 0.78/0.62", GREEN)),
                                               ("Chrono Burst", ("ready 0.97/0.85", GREEN), ("ready 0.97/0.71", GREEN))]):
        y = 98 + i * 34
        for x, (t, col) in ((40, before), (340, after)):
            rrect(c, x, y, x + 220, y + 26, 6, fill="#212529", outline="#343a40")
            label(c, x + 10, y + 13, name, "#ffffff", 9, "w", True)
            label(c, x + 210, y + 13, t, col, 9, "e", True)
    label(c, W / 2, 178, "score / its line:  READY when the score is at or above the line", TXT, 10)
    label(c, W / 2, 200, "Or set a slot's line yourself: its ⚙ → Ready at  (off = the global one in Settings)", DIM, 9)


def draw_priority(c):
    real_card(c, 12, 1, "Chrono Burst", "3", False, ("cd 0.31", YELLOW))
    real_card(c, 52, 2, "Mana Lance", "7", False, ("ready 0.97", GREEN))
    real_card(c, 92, 3, "Mana Veil", "8", False, ("ready 0.95", GREEN))
    rrect(c, 4, 48, 596, 90, 10, fill="", outline=GREEN, width=2)
    label(c, W / 2, 148, "Casts #2 Mana Lance — the top-most READY move (#1 is on cooldown)", GREEN, 11, bold=True)
    label(c, W / 2, 172, "Use ▲▼ to reorder — top = highest priority.  Test shows the READY / cooldown scores.", DIM)


def draw_card(c):
    real_card(c, 8, 2, "Chrono Burst", "3", False, ("✔", GREEN), "after 0.5s · ×3")
    real_card(c, 52, 1, "Mana Lance", "7")
    for n, (x, y) in enumerate([(64, 60), (132, 58), (296, 58), (166, 92), (330, 92), (104, 128),
                                (242, 128), (388, 128), (514, 14)], start=1):
        marker(c, x, y, n)
    label(c, W / 2, 186, "Folded (top): one line + a recap of its options.  Open (bottom): press ⚙.", TXT, 10, bold=True)
    label(c, W / 2, 208, "Only the move name is typed — everything else is a dropdown.", DIM)


def draw_anim(c):
    label(c, W / 2, 20, "One cast, left to right", YELLOW, 11, bold=True)
    y = 70
    blocks = [(20, 120, "#0dcaf0", "move mouse", "#000000"), (120, 210, "#343a40", "delay before", "#dce4ee"),
              (210, 275, BLUE, "press 7", "#ffffff"), (275, 330, "#6f42c1", "M1", "#ffffff"),
              (330, 490, "#664d03", "delay after  1.5 s", "#ffda6a"), (490, 580, GREEN, "next move", "#000000")]
    for x1, x2, fill, text, col in blocks:
        c.create_rectangle(x1, y, x2, y + 32, fill=fill, outline="#1e2124")
        label(c, (x1 + x2) / 2, y + 16, text, col, 10, bold=True)
    label(c, 70, y + 54, "only if the move\nhas a Mouse aim", DIM, 9)
    label(c, 165, y + 46, "Delay before (s)", YELLOW, 9)
    label(c, 302, y + 54, "only if\n'then M1'", DIM, 9)
    label(c, 410, y + 46, "Delay after (s)", YELLOW, 9)
    arrow(c, 30, 160, 570, 160, DIM); label(c, 570, 174, "time", DIM, 9, "e")
    label(c, W / 2, 200, "Two waits, both in each move's ⚙: one BEFORE the key, one AFTER it.", TXT, 10)


def draw_aim(c):
    label(c, W / 2, 18, "Mouse aim panel: one spot for several slots at once", YELLOW, 11, bold=True)
    rrect(c, 10, 34, 590, 150, 8, fill="#212529", outline="#343a40")
    label(c, 24, 52, "🎯 Mouse aim", "#ffffff", 10, "w", True)
    label(c, 24, 82, "Slots", "#dce4ee", 9, "w")
    for i in range(7):
        x = 70 + i * 34
        sel, aimed = i in (0, 2), i in (0, 2, 4)
        c.create_oval(x, 70, x + 26, 96, fill=BLUE if sel else "#343a40", outline=CYAN if aimed else "#343a40", width=2)
        label(c, x + 13, 83, str(i + 1), "#ffffff", 10, bold=True)
    rrect(c, 406, 70, 496, 96, 6, fill=BLUE, outline=""); label(c, 451, 83, "🎯 Pick spot", "#ffffff", 9, bold=True)
    rrect(c, 502, 70, 576, 96, 6, fill="#495057", outline=""); label(c, 539, 83, "✖ Clear", "#ffffff", 9)
    label(c, 24, 122, "(960, 540) → slot 1, 3, 5", "#adb5bd", 9, "w")
    for n, (x, y) in enumerate([(70, 66), (451, 64), (539, 64), (24, 110)], start=1):
        marker(c, x, y, n)
    label(c, 160, 176, "blue = ticked now", BLUE, 9)
    label(c, 330, 176, "cyan ring = slot already has a spot", CYAN, 9)
    label(c, W / 2, 202, "No spot (Clear) = the move fires wherever the mouse already is.", DIM, 9)


def draw_combo(c):
    label(c, W / 2, 20, "Skill Combo: YOU press the trigger, the steps play by themselves", YELLOW, 11, bold=True)
    c.create_rectangle(40, 70, 100, 130, fill="#343a40", outline=YELLOW, width=2)
    label(c, 70, 100, "2", YELLOW, 22, bold=True); label(c, 70, 145, "you press", DIM, 9)
    arrow(c, 110, 100, 160, 100, TXT)
    for i, (k, n, w) in enumerate([("3", "1 time", "0.2 s"), ("4", "2 times", "0.5 s"), ("5", "1 time", "")]):
        x = 160 + i * 150
        c.create_rectangle(x, 72, x + 92, 128, fill="#212529", outline=BLUE, width=2)
        label(c, x + 46, 86, f"Step {i + 1}", DIM, 9)
        label(c, x + 46, 104, f"press {k}", TXT, 12, bold=True)
        label(c, x + 46, 119, n, DIM, 9)
        if w:
            arrow(c, x + 98, 108, x + 144, 108, DIM)
            label(c, x + 121, 92, f"wait {w}", YELLOW, 9)
    label(c, W / 2, 160, "Every press is followed by its wait — 2 times = press, wait, press, wait.", TXT, 10)
    label(c, W / 2, 182, "☑ Send trigger too = key 2 also casts.   ☐ = 2 is replaced by the combo.", DIM)


def draw_items(c):
    label(c, W / 2, 16, "Drag the scan area over where the pickup messages appear", YELLOW, 11, bold=True)
    rrect(c, 100, 34, 500, 150, 8, fill="#2a3a2a", outline="")
    for i, (t, col) in enumerate([("+ 353.4 EXP (x3.8) obtained", "#5fe08a"),
                                  ("+ 237.8 Magic Mastery (x2.05) obtained", "#b48cff"),
                                  ("+ 173 Gold (x1.05) obtained", "#e9c46a")]):
        label(c, W / 2, 48 + i * 22, t, col, 10)
    label(c, W / 2, 120, "Obtained Copper!", "#ffffff", 12, bold=True)
    c.create_rectangle(170, 38, 430, 136, outline=RED, width=2, dash=(6, 3))
    tag(c, W / 2, 170, "Copper → press 9, then M1      (once per message)", "#495057")
    label(c, W / 2, 200, "The name only has to be part of the message: \"Copper\" matches \"Obtained Copper!\"", DIM, 9)


def draw_skill_extras(c):
    for i, (t, on) in enumerate([("📣  Event alerts: ON   (click to turn off)", True),
                                 ("🔔  Always Click OK: OFF   (click to turn on)", False)]):
        y = 40 + i * 56
        rrect(c, 30, y, 570, y + 36, 8, fill="#198754" if on else "#343a40", outline="#198754" if on else "#495057")
        label(c, W / 2, y + 18, t, "#ffffff", 11, bold=True)
    label(c, W / 2, 170, "Both run next to the rotation; skills pause a moment while /clear is typed.", DIM, 9)


def draw_loadouts(c):
    label(c, W / 2, 18, "One loadout per build — switch in one click", YELLOW, 11, bold=True)
    rrect(c, 20, 36, 580, 72, 8, fill="#212529", outline="#343a40")
    label(c, 32, 54, "🎒 Loadout:", "#ffffff", 10, "w", True)
    drop(c, 120, 43, 150, "Boss Farm", blue=True)
    for x, t in ((280, "New"), (330, "Rename"), (394, "Delete")):
        w = 44 if t == "New" else 58
        rrect(c, x, 43, x + w, 65, 5, fill="#495057", outline=""); label(c, x + w / 2, 54, t, "#dce4ee", 9)
    for i, (name, sub) in enumerate([("Default", "slots 1-8, 2 aims"), ("Boss Farm", "after 1.5s, combo on 2"),
                                     ("Mob Grind", "items: Mana Potion")]):
        x = 40 + i * 185
        rrect(c, x, 96, x + 165, 160, 8, fill="#212529", outline=BLUE if i == 1 else "#343a40", width=2)
        label(c, x + 82, 116, name, "#ffffff" if i == 1 else TXT, 11, bold=True)
        label(c, x + 82, 140, sub, DIM, 9)
    label(c, W / 2, 186, "each keeps its own moves · snapshots · aim · combos · items", TXT, 10)


def draw_start(c):
    c.create_rectangle(60, 60, 230, 110, fill="#198754", outline="")
    label(c, 145, 85, "▶ Start (F6)", "#ffffff", 13, bold=True)
    label(c, 145, 135, "starts every page whose\nEnabled switch is on", DIM, 10)
    for i, (n, on) in enumerate([("Rotation", True), ("Skill Combo", True), ("Items", False)]):
        y = 45 + i * 38
        c.create_oval(330, y, 362, y + 18, fill=BLUE if on else "#495057", outline="")
        c.create_oval(346 if on else 332, y + 2, 360 if on else 346, y + 16, fill="#ffffff", outline="")
        label(c, 375, y + 9, f"{n}  {'ON' if on else 'off'}", TXT if on else DIM, 11, "w")
    label(c, W / 2, 172, "Only acts while Roblox is the focused window (Settings).", DIM)


# section -> pages: (title, drawing, explanation)
PAGES = [
    ("Rotation", "1. Set the hotbar region", draw_region,
     "Rotation page → 🔲 Set Hotbar Region. The screen freezes; drag ONE box over all your skill icons."),
    ("Rotation", "2. Pick how many slots", draw_slots,
     "Choose the Slots dropdown (1–10). Press Show to check each cyan box lands on one icon. "
     "If they drift, redo the region with a tighter box."),
    ("Rotation", "3. Snapshot the ready icons", draw_snapshot,
     "Wait until EVERY move shows its name (no timer), then press 📸 Snapshot All. "
     "Fix a single slot later with its 📸 button. Press Test to see READY / cooldown for each slot."),
    ("Rotation", "4. Slot stuck on cooldown? Auto-tune", draw_tune,
     "1 🪄 Auto-tune (macro stopped): click into the Roblox window within 3 s. It finds the hotbar "
     "by itself (only your FILLED slots), waits for each move to be ready, snapshots it, then casts it once to learn its 'ready' line. 2 Test shows score/line for each slot.\n"
     "Still wrong? Open the move's ⚙ and pick 'Ready at' yourself (lower = counts as ready sooner). "
     "If Auto-tune says nothing changed after the key, the move didn't cast (no target?) - give it a manual Cooldown."),
    ("Rotation", "5. Set the priority order", draw_priority,
     "The macro always casts the highest move in the list that is READY. "
     "Cooldown reductions from other moves are picked up automatically because it reads the screen."),
    ("Rotation", "6. Each move card", draw_card,
     "1 On/off   2 Name (optional)   3 Key   9 ⚙ – open / close the extra options below\n"
     "4 Delay before – wait after the mouse moves, before the key   5 Delay after – wait after the key (lets slow moves finish)\n"
     "6 Repeat – multi-use moves: 4 every 0.25 s = 4 presses, 0.25 s apart (set it just above the move's lockout)\n"
     "7 then M1 – one left click after the key, 'after' = how long to wait first (default 0.3 s)   8 Cooldown – only for slots with no snapshot   Ready at – this slot's own 'ready' line (Auto-tune sets it)"),
    ("Rotation", "7. Mouse aim (optional)", draw_aim,
     "1 Tick the slots that should aim at the same spot   2 Pick spot: click where on screen (the mouse moves "
     "there before the key; tick 'then M1' on the move to also click)   3 Clear: ticked slots go back to 'wherever the mouse is'   "
     "4 The list shows which slots aim where. Pick again with other slots ticked for a different spot."),
    ("Rotation", "8. The order of one cast", draw_anim,
     "Move mouse → Delay before → press → M1 (if ticked) → Delay after → next move. Delay before gives the game "
     "time to turn toward the mouse before the key. Delay after lets slow moves finish before the next cast."),
    ("Skill Combo", "9. Skill Combos", draw_combo,
     "Skill Combo page → + Add Combo, set the trigger key, then + Step. Each step reads like a sentence: "
     "Press [key] [1 time] then wait [0.2 s]; with 2+ times it waits after each press. The step's ⚙ adds 'then M1' (the row then reads 'then M1 after [s]': press → wait → M1) or mouse aim. Works while the macro is running."),
    ("Items", "10. Item auto-use (optional)", draw_items,
     "Items page → Set Scan Area over the pickup messages, then + Add Item: \"When [Copper] shows up, press [9] ☑ then M1\". "
     "It presses the key, then left-clicks to use the item — once per message. Test OCR (while a message is on screen) shows what it reads."),
    ("Settings", "11. Events & OK Popup pages", draw_skill_extras,
     "The Skill Macro also has the 📣 Events and 🔔 OK Popup pages (same as every macro), each with its own ? Help. "
     "Turn on their big bars to post events to Discord or click OK popups while the rotation runs."),
    ("Settings", "12. Loadouts (saved builds)", draw_loadouts,
     "The 🎒 Loadout bar at the top saves a whole build: hotbar region, snapshots, move order and options, mouse aim, "
     "combos and items. New = a fresh empty save (your current one stays as it is); use Auto-tune to set it up. "
     "Switching applies instantly, even while running. The hotkey and focus setting are shared by all loadouts."),
    ("Settings", "13. Start it", draw_start,
     "Press Start or F6 (change it in Settings). Press again to stop."),
]


SKILL_PAGES = PAGES


# ================= Library Macro pages =================
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guide_assets")


def picture(c, name, x, y, max_w=None, max_h=None, anchor="nw"):
    """Draw a screenshot from guide_assets/ on the canvas (keeps a reference so it shows)."""
    try:
        from PIL import Image, ImageTk
        img = Image.open(os.path.join(ASSET_DIR, name)).convert("RGB")
        s = min((max_w or img.width) / img.width, (max_h or img.height) / img.height, 1.0)
        img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        c._pics = getattr(c, "_pics", []) + [photo]
        c.create_image(x, y, image=photo, anchor=anchor)
        return img.width, img.height
    except Exception:
        label(c, x, y, f"[{name} missing]", RED, 9, anchor)
        return 0, 0


def wisp_dialog(c, buttons, x0=20, y0=40, text_lines=2):
    """The wisp's dialogue: dark text panel with option buttons on its right."""
    rrect(c, x0, y0, x0 + 330, y0 + 110, 8, fill="#101214", outline="#3a3f44")
    label(c, x0 + 14, y0 + 16, "Wisp", YELLOW, 10, "w", True)
    for i in range(text_lines):
        c.create_rectangle(x0 + 14, y0 + 36 + i * 16, x0 + 300 - i * 70, y0 + 44 + i * 16, fill="#5c636a", outline="")
    pos = []
    for i, b in enumerate(buttons):
        by = y0 + 6 + i * 34
        rrect(c, x0 + 342, by, x0 + 482, by + 28, 6, fill="#101214", outline="#3a3f44")
        label(c, x0 + 412, by + 14, b, TXT, 9)
        pos.append((x0 + 342, by, x0 + 482, by + 28))
    return pos


def draw_lib_route(c):
    label(c, W / 2, 18, "Record the walk from the desk to the wisp once", YELLOW, 11, bold=True)
    rrect(c, 40, 70, 120, 120, 8, fill="#5c3d1e", outline="")
    label(c, 80, 95, "desk", TXT, 10, bold=True)
    c.create_oval(470, 66, 530, 126, fill="#1f6aa5", outline=CYAN, width=2)
    label(c, 500, 96, "wisp", "#ffffff", 10, bold=True)
    c.create_line(124, 95, 220, 95, 220, 140, 360, 140, 360, 96, 462, 96, fill=TXT, width=2, dash=(6, 4),
                  arrow="last", arrowshape=(10, 12, 4))
    tag(c, 80, 48, "1  Ctrl+P", BLUE)
    tag(c, 290, 160, "2  walk there", "#495057")
    tag(c, 500, 48, "3  tap E   4  Ctrl+P", BLUE)


def draw_lib_moves(c):
    label(c, W / 2, 16, "Settings → Moves to train (up to 9, one per hotbar slot)", YELLOW, 11, bold=True)
    rrect(c, 40, 30, 560, 170, 8, fill="#212529", outline="#343a40")
    rows = [(True, "Mana Wisp", "1"), (True, "Future Sight", "6"), (False, "", "7")]
    for i, (on, name, sl) in enumerate(rows):
        y = 46 + i * 38
        rrect(c, 56, y, 76, y + 20, 4, fill="#1f6aa5" if on else "#343638", outline="" if on else "#565b5e")
        if on:
            label(c, 66, y + 10, "✓", "#ffffff", 9, bold=True)
        label(c, 84, y + 10, f"Move {[1, 6, 7][i]}", "#ffffff", 10, "w", True)
        rrect(c, 160, y - 2, 430, y + 22, 5, fill="#343638", outline="#565b5e")
        label(c, 168, y + 10, name or "name on the wisp's button", TXT if name else DIM, 9, "w")
        label(c, 452, y + 10, "slot", TXT, 9, "w")
        drop(c, 482, y - 1, 56, sl, blue=True)
    label(c, W / 2, 184, "The name finds the button (scrolling the list if needed); slot = its hotbar spot", DIM, 9)
    label(c, W / 2, 206, "The wisp's list: your 9 moves, then Nevermind — always last", DIM, 9)


def draw_lib_dialog(c):
    label(c, W / 2, 16, "Pick how the macro finds the wisp's buttons", YELLOW, 11, bold=True)
    wisp_dialog(c, ["Ask about...", "Clover Training", "Nevermind"], 20, 34)
    for i, (t, on) in enumerate([("Auto", True), ("Image", False), ("Manual", False)]):
        x = 60 + i * 110
        rrect(c, x, 156, x + 104, 180, 6, fill=BLUE if on else "#343a40", outline="")
        label(c, x + 52, 168, t, "#ffffff", 10, bold=True)


def draw_lib_image(c):
    label(c, W / 2, 16, "Image: drag a box around each button once", YELLOW, 11, bold=True)
    pos = wisp_dialog(c, ["Ask about...", "Clover Training", "Nevermind"], 20, 34)
    x1, y1, x2, y2 = pos[1]
    c.create_rectangle(x1 - 4, y1 - 4, x2 + 4, y2 + 4, outline=RED, width=2, dash=(5, 3))
    tag(c, 470, 176, "📸 Capture → drag box", "#495057")
    label(c, 200, 168, "Then open the move menu and capture Move 1 / 2 / 3 the same way", DIM, 9)


def draw_lib_manual(c):
    label(c, W / 2, 16, "Manual: click the exact spot of each button", YELLOW, 11, bold=True)
    pos = wisp_dialog(c, ["Ask about...", "Clover Training", "Nevermind"], 20, 34)
    x1, y1, x2, y2 = pos[1]
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    c.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, outline=RED, width=2)
    c.create_line(cx - 16, cy, cx + 16, cy, fill=RED, width=2)
    c.create_line(cx, cy - 16, cx, cy + 16, fill=RED, width=2)
    tag(c, 470, 176, "🎯 Pick spot → click", "#495057")
    label(c, 200, 168, "Keep the same window size afterwards", DIM, 9)


def draw_gold_spots(c):
    label(c, 8, 12, "The 3rd clover always lands in the same spot — top-right of each icon (arrows):", YELLOW, 10,
          "w", True)
    picture(c, "gold_clover_arrows.png", 8, 24, max_w=W - 16, max_h=92)
    label(c, 8, 128, "Trained — that spot now has a gold clover:", GREEN, 10, "w", True)
    picture(c, "gold_clover_full.png", 8, 140, max_w=W - 16, max_h=86)


def draw_gold_box(c):
    label(c, W / 2, 16, "Automatic: 🪄 Auto finds the hotbar (or drag ONE box over it, clovers included)", YELLOW, 11, bold=True)
    x0, y0, size, gap = 40, 60, 78, 8
    for i in range(6):
        x = x0 + i * (size + gap)
        slot(c, x, y0, MOVES[i], size)
        n = 2 if i in (0, 2) else (0 if i in (1, 4) else 3)
        for j, fx in enumerate((0.2, 0.5, 0.8)[:n]):
            c.create_text(x + fx * size, y0 - 10, text="✿", fill="#f0a020", font=("Arial", 13))
        c.create_rectangle(x + 0.68 * size, y0 - 22, x + 0.92 * size, y0 + 2, outline=YELLOW, width=2)
    c.create_rectangle(x0 - 4, y0 - 26, x0 + 6 * (size + gap) - gap + 4, y0 + size + 4, outline=RED, width=2, dash=(6, 3))
    label(c, W / 2, 168, "red = the hotbar box (top of the clovers → bottom of the icons)   yellow = spots it checks",
          TXT, 9)
    label(c, W / 2, 190, "Then pick which hotbar slot each Move is, and press Test / Show to check.", DIM, 9)


def draw_clicker(c):
    label(c, W / 2, 18, "Clover Clicker tab: pick each clover colour from the screen", YELLOW, 11, bold=True)
    for x, y, col, n in [(120, 90, "#db978b", "bronze"), (300, 120, "#bbc5c5", "silver"), (470, 80, "#fbc66c", "gold")]:
        c.create_text(x, y, text="✿", fill=col, font=("Arial", 34))
        label(c, x, y + 34, n, col, 10, bold=True)
    label(c, W / 2, 200, "Clicks gold first, then silver, then bronze", DIM, 9)


def draw_minigame(c):
    label(c, W / 2, 16, "Snapshot something that ONLY shows during the minigame", YELLOW, 11, bold=True)
    for i, (title, live) in enumerate([("In the minigame", True), ("Walking around", False)]):
        x = 30 + i * 290
        rrect(c, x, 36, x + 250, 176, 8, fill="#1d3b2a" if live else "#1b2a3a", outline="#343a40")
        label(c, x + 125, 52, title, "#ffffff", 10, bold=True)
        if live:
            rrect(c, x + 85, 66, x + 165, 92, 6, fill="#101214", outline="")
            label(c, x + 125, 79, "⏱ 0:24", "#ffffff", 11, bold=True)
            c.create_rectangle(x + 80, 61, x + 170, 97, outline=RED, width=2, dash=(5, 3))
            for cx, cy, col in [(x + 60, 130, "#fbc66c"), (x + 140, 150, "#bbc5c5"), (x + 200, 120, "#db978b")]:
                c.create_text(cx, cy, text="✿", fill=col, font=("Arial", 20))
            label(c, x + 125, 190, "match ✔ → click clovers", GREEN, 10, bold=True)
        else:
            c.create_rectangle(x + 80, 61, x + 170, 97, outline="#6c757d", width=2, dash=(5, 3))
            label(c, x + 125, 79, "(no timer)", DIM, 9)
            label(c, x + 125, 130, "🧍  →  wisp", TXT, 12)
            label(c, x + 125, 190, "no match → walk / talk", "#adb5bd", 10, bold=True)
    label(c, W / 2, 214, "Pick a part that never moves (timer, score, title) — not the clovers.", DIM, 9)


def draw_lib_hidechat(c):
    label(c, W / 2, 16, "Hide the chat during the minigame (its white tabs look like silver clovers)", YELLOW, 11,
          bold=True)
    for i, ic in enumerate(["⌂", "☰", "💬", "🎤", "🛍"]):
        x = 60 + i * 52
        c.create_oval(x - 20, 40, x + 20, 80, fill="#101214", outline="#3a3f44")
        label(c, x, 60, ic, "#ffffff", 12)
    c.create_oval(164 - 26, 34, 164 + 26, 86, outline=RED, width=2, dash=(4, 2))
    tag(c, 164, 104, "🎯 Pick chat button = this one", BLUE)
    rrect(c, 330, 46, 570, 150, 6, fill="#1a1d20", outline="#343a40")
    for j, t in enumerate(["Here", "Global", "Friends"]):
        label(c, 370 + j * 80, 62, t, "#ffffff", 10, bold=True)
    label(c, 450, 104, "closed when a minigame starts,\nopened again after it", DIM, 9)
    label(c, W / 2, 196, "Areas tab → 💬 Hide chat during the minigame → ON. Start the macro with chat OPEN.", TXT, 9)


def draw_lib_start(c):
    rrect(c, 60, 50, 250, 96, 8, fill="#198754", outline="")
    label(c, 155, 73, "Start Macro (F6)", "#ffffff", 13, bold=True)
    rrect(c, 60, 108, 250, 140, 8, fill="#343a40", outline="")
    label(c, 155, 124, "🔔 Always Click OK", "#adb5bd", 10, bold=True)
    for i, t in enumerate(["walk to the wisp", "open the dialogue", "pick the move", "play the clover minigame",
                           "check events (if Event alerts is on)", "repeat until each spot is gold"]):
        label(c, 300, 44 + i * 24, f"{i + 1}.  {t}", TXT, 10, "w")


LIBRARY_PAGES = [
    ("Route", "1. Record the walk to the wisp", draw_lib_route,
     "Settings → Route → New. Stand at the desk (where you end up after a minigame), press Ctrl+P, walk to the wisp, "
     "tap E at it, press Ctrl+P again. Test Path (F3) replays it. No recording = the old D/S/W walk."),
    ("Moves", "2. Tick the moves to train", draw_lib_moves,
     "Tick each move to train and type its name exactly as on the wisp's button. The list only shows ~4 at a "
     "time: the macro scrolls one notch at a time until it sees the name (or its captured picture), and stops at "
     "Nevermind. Pick each move's hotbar slot for the gold clover check."),
    ("Dialogue", "3. Wisp dialogue mode", draw_lib_dialog,
     "Auto (default): finds the buttons by shape — try this first.  Image: you capture a picture of each button.  "
     "Manual: you click the exact spot of each button (only for moves visible without scrolling). "
     "Test Dialogue (F1) shows what each button reads."),
    ("Dialogue", "4. Image mode", draw_lib_image,
     "Talk to the wisp so the menu is on screen, press 📸 Capture next to Clover Training and drag a tight box around "
     "that button. Do the same for each move button in the move menu."),
    ("Dialogue", "5. Manual mode", draw_lib_manual,
     "With the menu on screen, press 🎯 Pick spot and click the middle of the button. "
     "'Wait before each click' gives the dialogue time to appear."),
    ("Gold Clover", "6. Where the 3rd clover appears", draw_gold_spots,
     "Moves are trained in order: Move 1 until its 3rd clover is gold, then Move 2, and so on."),
    ("Gold Clover", "7. Set up Gold Clover detection", draw_gold_box,
     "Areas tab → Automatic → 🪄 Auto (click into Roblox within 3 s: it finds the hotbar and your filled slots by itself) "
     "or 🔲 Set hotbar + Slots by hand. Then choose which hotbar slot each Move is "
     "(Move N = the N-th button in the wisp's menu). Show draws the yellow spots; Test reads them. "
     "Manual is still there if you'd rather drag each spot yourself."),
    ("Clover Clicker", "8. Clover colours", draw_clicker,
     "Clover Clicker tab: pick the bronze, silver and gold clover colours during a minigame. "
     "The Clover Region in Areas is optional — without it the whole minigame view is searched."),
    ("Minigame", "9. Minigame detector", draw_minigame,
     "Areas tab → 🎮 Minigame detector → Snapshot. Start a minigame by hand, press 📸 Capture — the screen freezes — "
     "and drag a box around the timer/score. The macro clicks clovers while it's visible and walks once it's gone. "
     "Press Test in and out of a minigame: it should say IN only during one."),
    ("Minigame", "10. Hide chat during the minigame", draw_lib_hidechat,
     "Areas tab → turn on 💬 Hide chat during the minigame, press 🎯 Pick chat button and click Roblox's chat icon. "
     "It's clicked to close chat when a minigame starts and again after it. Start with chat open."),
    ("Start", "11. Start it", draw_lib_start,
     "Press Start (F6). Turn on Always Click OK if reward popups block the screen. "
     "The macro stops by itself once every ticked move shows its gold clover."),
]


# ================= Event Notifier pages =================
def draw_toggle_bar(c, y, text, on=False):
    rrect(c, 30, y, 570, y + 34, 8, fill="#198754" if on else "#343a40", outline="#198754" if on else "#495057")
    label(c, W / 2, y + 17, text, "#ffffff" if on else "#e9ecef", 11, bold=True)


def draw_ev_webhook(c):
    label(c, W / 2, 16, "Discord: channel ⚙ → Integrations → Webhooks → New → Copy URL", YELLOW, 11, bold=True)
    rrect(c, 20, 36, 580, 120, 8, fill="#212529", outline="#343a40")
    small(c, 34, 58, "Webhook")
    rrect(c, 110, 46, 480, 70, 5, fill="#343638", outline="#565b5e"); label(c, 118, 58, "•" * 40, DIM, 9, "w")
    rrect(c, 490, 46, 566, 70, 5, fill="#495057", outline=""); label(c, 528, 58, "Send test", "#ffffff", 9)
    small(c, 34, 96, "Ping")
    rrect(c, 110, 84, 566, 108, 5, fill="#343638", outline="#565b5e"); label(c, 118, 96, "👥 Vunox, Rushe", TXT, 9, "w")
    for n, (x, y) in enumerate([(110, 44), (490, 44), (110, 82)], start=1):
        marker(c, x, y, n)
    label(c, W / 2, 150, "Send test reads the chat NOW and posts what it finds (marked [TEST]).", TXT, 10)
    label(c, W / 2, 174, "Nothing listed in chat = nothing is posted; the reason shows in the app.", DIM, 9)


def draw_ev_people(c):
    label(c, W / 2, 16, "👥 = tick who gets pinged (saved once, used by every event)", YELLOW, 11, bold=True)
    rrect(c, 140, 34, 460, 196, 8, fill="#1e2124", outline="#343a40")
    label(c, 156, 50, "Ping for: Devil Rift", BLUE, 10, "w", True)
    for i, (n, on) in enumerate([("Vunox", True), ("Rushe", True), ("Alduini", False)]):
        y = 74 + i * 26
        rrect(c, 156, y, 172, y + 16, 3, fill="#1f6aa5" if on else "#343638", outline="")
        if on:
            label(c, 164, y + 8, "✓", "#ffffff", 8, bold=True)
        label(c, 180, y + 8, n, TXT, 10, "w")
    rrect(c, 156, 158, 250, 180, 5, fill="#343638", outline="#565b5e"); label(c, 162, 169, "Name", DIM, 9, "w")
    rrect(c, 256, 158, 380, 180, 5, fill="#343638", outline="#565b5e"); label(c, 262, 169, "Discord user ID", DIM, 9, "w")
    rrect(c, 386, 158, 444, 180, 5, fill=BLUE, outline=""); label(c, 415, 169, "+ Add", "#ffffff", 9)
    label(c, W / 2, 214, "ID = Developer Mode on → right-click the person → Copy User ID (names don't ping)", DIM, 9)


def draw_ev_windows(c):
    label(c, W / 2, 16, "One card per Roblox window (numbered by screen position)", YELLOW, 11, bold=True)
    rrect(c, 20, 34, 580, 120, 8, fill="#1a1d20", outline="#343a40")
    label(c, 34, 52, "Window 1", "#ffffff", 10, "w", True)
    rrect(c, 110, 40, 250, 64, 5, fill="#343638", outline="")
    rrect(c, 110, 40, 190, 64, 5, fill="#1f6aa5", outline=""); label(c, 150, 52, "Clover K.", "#ffffff", 9)
    label(c, 220, 52, "Jungle", TXT, 9)
    rrect(c, 420, 40, 494, 64, 5, fill="#198754", outline=""); label(c, 457, 52, "🔲 Chat ✔", "#ffffff", 9)
    rrect(c, 500, 40, 566, 64, 5, fill="#495057", outline=""); label(c, 533, 52, "👁 Show", "#ffffff", 9)
    small(c, 34, 92, "PS code")
    rrect(c, 110, 80, 566, 104, 5, fill="#343638", outline="#565b5e"); label(c, 118, 92, "e89cc163", TXT, 9, "w")
    for n, (x, y) in enumerate([(110, 38), (420, 38), (500, 38), (110, 78)], start=1):
        marker(c, x, y, n)
    label(c, W / 2, 140, "1 World (goes in the message)   2 drag THIS window's chat box   3 shows WINDOW n + its chat box",
          TXT, 9)
    label(c, W / 2, 160, "4 that window's private server code.   Message: Warlord - Clover Kingdom - e89cc163 @you", TXT, 9)
    label(c, W / 2, 190, "Keep each chat corner uncovered. 👁 Show all labels every window at once.", DIM, 9)


def draw_ev_events(c):
    label(c, W / 2, 16, "Event list: what to watch for", YELLOW, 11, bold=True)
    for i, (on, name, kw, ppl, role) in enumerate([(True, "Devil Rift", "feels off", "👥 2", "1270473…"),
                                                   (True, "Bandit Lord", "whispers rise", "👥", ""),
                                                   (False, "Craftsman", "craftsman", "👥", "")]):
        y = 36 + i * 36
        rrect(c, 20, y, 580, y + 30, 6, fill="#212529", outline="#343a40")
        rrect(c, 30, y + 7, 46, y + 23, 3, fill="#1f6aa5" if on else "#343638", outline="")
        if on:
            label(c, 38, y + 15, "✓", "#ffffff", 8, bold=True)
        for x, w, t in ((56, 120, name), (182, 130, kw), (318, 60, ppl), (384, 110, role or "role ID")):
            rrect(c, x, y + 4, x + w, y + 26, 5, fill="#343638", outline="#565b5e")
            label(c, x + 6, y + 15, t, TXT if t and t != "role ID" else DIM, 9, "w")
    for n, (x, y) in enumerate([(30, 34), (56, 34), (182, 34), (318, 34), (384, 34)], start=1):
        marker(c, x, y, n)
    label(c, W / 2, 160, "1 notify on/off   2 name in the message   3 keyword from the SPAWN message", TXT, 9)
    label(c, W / 2, 178, "4 people for just this event   5 Discord role ID to ping", TXT, 9)
    label(c, W / 2, 204, "Pick a keyword that isn't in the despawn line (\"whispers rise\", not \"bandit lord\").", DIM, 9)


def draw_ev_on(c):
    draw_toggle_bar(c, 30, "📣  Event alerts: ON   (click to turn off)", on=True)
    label(c, W / 2, 86, "Check every 1 min  ·  Same event again after 2 min  ·  /clear chat after an alert", TXT, 10)
    label(c, W / 2, 112, "Each check: hover the chat → read it → post NEW event lines → /clear (optional)", TXT, 10)
    label(c, W / 2, 140, "Old lines already in chat when it starts are skipped; only new ones post.", DIM, 9)
    label(c, W / 2, 162, "Mining checks after each lap, Library after each minigame (no interruptions).", DIM, 9)
    label(c, W / 2, 184, "Skill Macro: skills pause for a moment while /clear is typed.", DIM, 9)


EVENTS_PAGES = [
    ("Discord", "1. Webhook + who to ping", draw_ev_webhook,
     "1 Paste the channel's webhook URL   2 Send test reads the chat now and posts what it finds   "
     "3 Ping = people pinged on every alert (an event's own 👥 replaces it)."),
    ("Discord", "2. The people list", draw_ev_people,
     "Add each person once (name + Discord user ID). Then any 👥 button just ticks who to ping. "
     "Roles go in an event's Role box instead (role needs 'Allow anyone to @mention' on)."),
    ("Windows", "3. Roblox windows", draw_ev_windows,
     "For every Roblox window: pick Clover Kingdom or Jungle, press 🔲 Chat and drag over that window's chat, "
     "and type its PS code. 👁 Show checks the yellow chat box sits on the chat."),
    ("Events", "4. The event list", draw_ev_events,
     "Untick events you don't care about. + Add event for new ones: the keyword only needs to be part of the chat "
     "message, spaces and capitals don't matter."),
    ("Start", "5. Turn it on", draw_ev_on,
     "Click the big Event alerts bar. It keeps running when you switch macros. Test read shows what each window "
     "reads right now."),
]


# ================= OK Popup pages =================
def draw_ok_capture(c):
    label(c, W / 2, 16, "Open any OK popup in Roblox, then 📸 Capture", YELLOW, 11, bold=True)
    rrect(c, 170, 40, 430, 170, 10, fill="#2b2f33", outline="#565b5e")
    label(c, W / 2, 80, "You obtained a reward!", TXT, 11)
    rrect(c, 250, 112, 350, 144, 6, fill="#e9ecef", outline="")
    label(c, 300, 128, "Ok", "#000000", 12)
    c.create_rectangle(244, 106, 356, 150, outline=RED, width=2, dash=(5, 3))
    label(c, W / 2, 190, "Drag a TIGHT box around just the OK button. Scan Area / Click Spot are optional.", DIM, 9)
    label(c, W / 2, 212, "⚠ Be in game + Roblox content maturity = MINIMAL (Settings → Privacy & content restrictions)",
          YELLOW, 9, bold=True)


def draw_ok_on(c):
    draw_toggle_bar(c, 30, "🔔  Always Click OK: ON   (click to turn off)", on=True)
    label(c, W / 2, 90, "Clicks OK popups in the background, even when the macro is stopped.", TXT, 10)
    label(c, W / 2, 116, "▶ Test Now tries once. Match %: lower if it misses, higher if it clicks nothing.", TXT, 10)
    label(c, W / 2, 150, "Set up once — every macro (Library, Mining, Fishing, Skill, Events) shares it.", DIM, 9)


OK_PAGES = [
    ("OK", "1. Capture the OK button", draw_ok_capture,
     "Before you start: be IN GAME, and set Roblox Settings → Privacy & content restrictions → Content maturity to "
     "MINIMAL. Then OK Popup page → 1. Capture: the screen freezes; drag a tight box around the OK button."),
    ("OK", "2. Turn it on", draw_ok_on,
     "Click the Always Click OK bar (it's on the OK Popup page, and on Main in Library/Mining/Fishing). "
     "Test Now to check it finds the button."),
]


# ================= Mining pages =================
def draw_min_route(c):
    label(c, W / 2, 16, "Record a lap once: Ctrl+P → walk → E at each ore → back → Ctrl+P", YELLOW, 11, bold=True)
    pts = [(60, 160), (160, 70), (300, 120), (450, 60), (540, 150)]
    for i, (x, y) in enumerate(pts[1:-1], start=1):
        c.create_oval(x - 16, y - 16, x + 16, y + 16, fill="#6c757d", outline=YELLOW, width=2)
        label(c, x, y, f"E{i}", "#ffffff", 9, bold=True)
    c.create_line(*[v for p in pts for v in p], fill=TXT, width=2, dash=(6, 4), smooth=True)
    c.create_line(540, 150, 300, 200, 60, 160, fill=GREEN, width=2, dash=(6, 4), smooth=True, arrow="last")
    tag(c, 60, 186, "start: Ctrl+P", BLUE)
    label(c, 300, 214, "after the LAST E = the walk back (green)", GREEN, 9, bold=True)


def draw_min_tune(c):
    label(c, W / 2, 16, "Settings → route list: click an ore to see / edit its keys", YELLOW, 11, bold=True)
    rrect(c, 40, 36, 560, 66, 6, fill=BLUE, outline="")
    label(c, 54, 51, "Ore 2   ·   walk 4.0s   ·   0 checkpoints   ▾", "#ffffff", 10, "w", True)
    for i, (k, at, hold) in enumerate([("W", "0.00", "1.50"), ("D", "1.62", "0.40"), ("W", "2.10", "3.25")]):
        y = 76 + i * 30
        rrect(c, 60, y, 540, y + 24, 5, fill="#2b3035", outline="")
        label(c, 80, y + 12, k, "#9ec5fe", 11, bold=True)
        label(c, 130, y + 12, f"at {at}s", DIM, 9, "w")
        rrect(c, 220, y + 2, 290, y + 22, 4, fill="#343638", outline="#565b5e"); label(c, 255, y + 12, hold, TXT, 9)
    label(c, W / 2, 182, "Change how long each key is held (overshoot an ore? lower W a little).", TXT, 10)
    label(c, W / 2, 204, "Mining Secs / Waiting Secs per ore are on the same card.", DIM, 9)


def draw_min_start(c):
    rrect(c, 60, 46, 250, 92, 8, fill=GREEN, outline=""); label(c, 155, 69, "Start Macro (F6)", "#ffffff", 13, bold=True)
    rrect(c, 60, 106, 250, 140, 8, fill="#495057", outline=""); label(c, 155, 123, "Test Path (F2)", "#ffffff", 10)
    for i, t in enumerate(["walk to each ore and mine it", "walk back to the start", "line up on the start spot (if checks on)",
                           "check events (if Event alerts is on)", "repeat"]):
        label(c, 290, 50 + i * 26, f"{i + 1}.  {t}", TXT, 10, "w")


def draw_min_checks(c):
    label(c, W / 2, 16, "Settings → Line-up checks & Prompt area", YELLOW, 11, bold=True)
    rrect(c, 20, 34, 580, 132, 8, fill="#212529", outline="#343a40")
    # Line-up checks switch
    rrect(c, 34, 50, 70, 68, 9, fill=BLUE, outline=""); c.create_oval(52, 51, 68, 67, fill="#ffffff", outline="")
    label(c, 80, 59, "📍 Line-up checks", "#ffffff", 10, "w", True)
    label(c, 230, 59, "ON = line up on start spot / checkpoints / ores + look for [E]", DIM, 9, "w")
    label(c, 230, 77, "OFF = just follow the recorded path and press E", GREEN, 9, "w", True)
    # Prompt area row
    label(c, 34, 108, "Prompt area", "#ffffff", 10, "w", True)
    for x, t in ((130, "🔲 Set"), (196, "Clear"), (256, "👁 Show")):
        rrect(c, x, 96, x + 58, 120, 5, fill="#495057", outline=""); label(c, x + 29, 108, t, "#ffffff", 9)
    label(c, 326, 108, "auto (around your character)", DIM, 9, "w")
    for n, (x, y) in enumerate([(34, 46), (130, 92), (256, 92)], start=1):
        marker(c, x, y, n)
    # where the prompt is looked for
    rrect(c, 200, 146, 400, 206, 6, fill="", outline=CYAN, width=2)
    label(c, 300, 158, "Prompt area", CYAN, 9, bold=True)
    rrect(c, 262, 172, 280, 190, 3, fill="", outline="#ffffff"); label(c, 271, 181, "E", "#ffffff", 9, bold=True)
    label(c, 312, 181, "Interact", "#ffffff", 9)
    label(c, 108, 176, "not the whole screen:\na box around your\ncharacter (or yours)", DIM, 9)


MINING_PAGES = [
    ("Route", "1. Record your mining lap", draw_min_route,
     "Settings → Route → New. Stand at the start, press Ctrl+P, walk the lap and TAP E at every ore (any number), "
     "walk back to the start, press Ctrl+P. Pause briefly at corners."),
    ("Route", "2. Fine-tune the walk", draw_min_tune,
     "Each ore's card lists the recorded keys. Edit how long a key is held to fix over/under-shooting."),
    ("Route", "3. Line-up checks & Prompt area", draw_min_checks,
     "1 Line-up checks: ON lines up on the start spot, checkpoints and each ore, and looks for the [E] Interact prompt "
     "(nudging if it's missing). OFF just plays your recorded path and presses E at each ore.   "
     "2 Prompt area: drag a box where the [E] Interact prompt shows up (Clear = automatic box around your character). "
     "3 Show flashes the box it uses. Test Prompt (F1) checks it."),
    ("Start", "4. Test and start", draw_min_start,
     "Test Path (F2) walks one lap without mining (click into Roblox within 5 s if you used the button). "
     "Then Start (F6)."),
]


# ================= Fishing pages =================
def draw_fish_area(c):
    label(c, W / 2, 16, "Fishing Settings → Set Minigame Bar Area", YELLOW, 11, bold=True)
    rrect(c, 80, 90, 520, 120, 6, fill="#2b2f33", outline="#565b5e")
    rrect(c, 230, 92, 330, 118, 4, fill="#5f9962", outline="")
    c.create_text(300, 105, text="🐟", font=("Arial", 14))
    c.create_rectangle(74, 84, 526, 126, outline=RED, width=2, dash=(5, 3))
    label(c, W / 2, 160, "Drag a box around the whole fishing bar while the minigame is open.", TXT, 10)


def draw_fish_colors(c):
    label(c, W / 2, 16, "Pick the two colours from the screen", YELLOW, 11, bold=True)
    rrect(c, 120, 60, 260, 120, 8, fill="#5f9962", outline=""); label(c, 190, 140, "Bar colour (green)", TXT, 10)
    rrect(c, 340, 60, 480, 120, 8, fill="#bcbb90", outline=""); label(c, 410, 140, "Fish colour", TXT, 10)
    label(c, W / 2, 180, "Tolerance slider: raise it if it loses the bar/fish, lower it if it grabs other things.", DIM, 9)


FISHING_PAGES = [
    ("Setup", "1. The fishing bar", draw_fish_area,
     "Open a fishing minigame, then Fishing Settings → Set Minigame Bar Area and drag over the bar."),
    ("Setup", "2. Colours", draw_fish_colors,
     "Pick Bar Colour (the green bar) and Fish Colour. Use the Test buttons to check, then Start (F6)."),
]


class SetupGuide(ctk.CTkToplevel):
    _open = None

    @classmethod
    def show(cls, master, section=None, pages=None, title="Skill Macro — Setup Guide"):
        pages = pages or SKILL_PAGES
        if cls._open is not None and cls._open.winfo_exists():
            if cls._open.pages is pages:
                cls._open.goto_section(section)
                cls._open.lift(); cls._open.focus_force()
                return
            cls._open.destroy()
        cls._open = cls(master, section, pages, title)

    def __init__(self, master, section=None, pages=None, title="Skill Macro — Setup Guide"):
        super().__init__(master)
        self.pages = pages or SKILL_PAGES
        self.title(title)
        self.geometry("680x510")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color="#1e2124")
        self.i = 0

        tabs = ctk.CTkFrame(self, fg_color="transparent"); tabs.pack(fill="x", padx=16, pady=(12, 0))
        self.sec_btns = {}
        sections = list(dict.fromkeys(p[0] for p in self.pages))
        tab_w = min(96, (W + 20) // len(sections) - 6)      # shrink tabs so they always fit in one row
        for sec in sections:
            b = ctk.CTkButton(tabs, text=sec, width=tab_w, height=26, font=("Arial", 12 if tab_w >= 90 else 11),
                              fg_color="#343a40", hover_color="#495057", command=lambda s=sec: self.goto_section(s))
            b.pack(side="left", padx=3)
            self.sec_btns[sec] = b

        self.title_lbl = ctk.CTkLabel(self, text="", font=("Arial", 18, "bold"), text_color=BLUE)
        self.title_lbl.pack(anchor="w", padx=20, pady=(12, 4))
        self.canvas = tk.Canvas(self, width=W, height=H, bg=BG, highlightthickness=1, highlightbackground="#343a40")
        self.canvas.pack(padx=20)
        self.body = ctk.CTkLabel(self, text="", font=("Arial", 13), text_color=TXT, wraplength=W, justify="left")
        self.body.pack(anchor="w", padx=22, pady=10)

        nav = ctk.CTkFrame(self, fg_color="transparent"); nav.pack(side="bottom", fill="x", padx=16, pady=12)
        self.prev_btn = ctk.CTkButton(nav, text="← Back", width=90, fg_color="#495057", hover_color="#343a40", command=lambda: self.go(-1))
        self.prev_btn.pack(side="left")
        self.dots = ctk.CTkLabel(nav, text="", font=("Arial", 14), text_color=DIM)
        self.dots.pack(side="left", expand=True)
        self.next_btn = ctk.CTkButton(nav, text="Next →", width=90, fg_color=BLUE, hover_color="#0b5ed7", command=lambda: self.go(1))
        self.next_btn.pack(side="right")
        self.bind("<Left>", lambda e: self.go(-1)); self.bind("<Right>", lambda e: self.go(1))
        self.bind("<Escape>", lambda e: self.destroy())
        self.goto_section(section)

    def goto_section(self, section):
        self.i = next((n for n, p in enumerate(self.pages) if p[0] == section), 0) if section else 0
        self.render()

    def go(self, d):
        if self.i + d >= len(self.pages):
            self.destroy(); return
        self.i = max(0, self.i + d)
        self.render()

    def render(self):
        sec, title, draw, text = self.pages[self.i]
        self.title_lbl.configure(text=title)
        self.body.configure(text=text)
        self.canvas.delete("all")
        self.canvas._pics = []
        draw(self.canvas)
        self.dots.configure(text="  ".join("●" if n == self.i else "○" for n in range(len(self.pages))))
        self.prev_btn.configure(state="normal" if self.i else "disabled")
        self.next_btn.configure(text="Done ✓" if self.i == len(self.pages) - 1 else "Next →")
        for s, b in self.sec_btns.items():
            b.configure(fg_color=BLUE if s == sec else "#343a40")

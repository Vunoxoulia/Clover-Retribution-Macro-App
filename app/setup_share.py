import copy
import json
import os
import shutil
import zipfile

FORMAT = 1

LIBRARY_KEYS = ("move_names", "train_moves", "gold_move_slots", "dialog_mode", "dialog_wait",
                "after_training_wait", "manual_moves", "positions", "gold_hotbar", "gold_mode",
                "hide_chat_in_minigame", "minigame_threshold", "clover_colors", "clover_tolerances",
                "color_tolerance", "sound_when_done")
LIBRARY_REGIONS = ("score", "chat_button")


def _write_json(z, data):
    z.writestr("setup.json", json.dumps(data, indent=1))


def _read(path):
    z = zipfile.ZipFile(path)
    try:
        data = json.loads(z.read("setup.json").decode("utf-8"))
    except KeyError:
        z.close()
        raise ValueError("That file isn't a VunVun's Macro setup (no setup.json inside).")
    return z, data


def _extract_folder(z, prefix, dest):
    n = 0
    for info in z.infolist():
        if info.is_dir() or not info.filename.startswith(prefix + "/"):
            continue
        name = os.path.basename(info.filename)
        if not name or name.startswith("."):
            continue
        os.makedirs(dest, exist_ok=True)
        with z.open(info) as src, open(os.path.join(dest, name), "wb") as out:
            shutil.copyfileobj(src, out)
        n += 1
    return n


def export_skill_loadout(logic, path):
    from logic_smart import loadout_dir
    logic._store_active()
    name = logic.active_loadout()
    data = {"type": "skill_loadout", "format": FORMAT, "name": name,
            "sections": copy.deepcopy(logic.loadouts()[name])}
    folder = loadout_dir(name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        _write_json(z, data)
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                if f.lower().endswith(".png"):
                    z.write(os.path.join(folder, f), f"pictures/{f}")
    return name


def import_skill_loadout(logic, path):
    from logic_smart import loadout_dir, LOADOUT_SECTIONS
    z, data = _read(path)
    with z:
        if data.get("type") != "skill_loadout":
            raise ValueError("That file is a " + str(data.get("type", "?")).replace("_", " ")
                             + " setup, not a Skill Macro loadout.")
        base = str(data.get("name") or "Imported").strip()[:40] or "Imported"
        name, k = base, 2
        while name in logic.loadouts():
            name, k = f"{base} ({k})", k + 1
        logic._store_active()
        sections = {s: v for s, v in (data.get("sections") or {}).items() if s in LOADOUT_SECTIONS}
        logic.loadouts()[name] = sections
        dest = loadout_dir(name)
        shutil.rmtree(dest, ignore_errors=True)
        _extract_folder(z, "pictures", dest)
    logic.app.settings.settings["skill_active_loadout"] = None
    for s, v in copy.deepcopy(sections).items():
        logic._fill_section(s, v)
    logic.app.settings.settings["skill_active_loadout"] = name
    logic._templates.clear()
    logic.app.settings.save()
    return name


def export_library(logic, path):
    from logic_library import DIALOG_TEMPLATE_DIR
    st = logic.app.settings.settings
    data = {"type": "library", "format": FORMAT,
            "settings": {k: copy.deepcopy(st[k]) for k in LIBRARY_KEYS if k in st},
            "regions": {k: v for k, v in (st.get("regions") or {}).items() if k in LIBRARY_REGIONS}}
    route = logic.active_route()
    own_route = route and not logic.is_locked(route) and logic.load_route(route)
    data["route"] = route if own_route else None
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        _write_json(z, data)
        if os.path.isdir(DIALOG_TEMPLATE_DIR):
            for f in sorted(os.listdir(DIALOG_TEMPLATE_DIR)):
                if f.lower().endswith(".png"):
                    z.write(os.path.join(DIALOG_TEMPLATE_DIR, f), f"pictures/{f}")
        if own_route:
            d = logic.route_dir(route)
            for f in sorted(os.listdir(d)):
                if os.path.isfile(os.path.join(d, f)):
                    z.write(os.path.join(d, f), f"route/{f}")
    return route if own_route else None


def import_library(logic, path):
    from logic_library import DIALOG_TEMPLATE_DIR
    z, data = _read(path)
    with z:
        if data.get("type") != "library":
            raise ValueError("That file is a " + str(data.get("type", "?")).replace("_", " ")
                             + " setup, not a Library setup.")
        st = logic.app.settings.settings
        for k, v in (data.get("settings") or {}).items():
            if k not in LIBRARY_KEYS:
                continue
            cur = st.get(k)
            if isinstance(cur, list) and isinstance(v, list):
                cur[:] = v
            elif isinstance(cur, dict) and isinstance(v, dict):
                cur.clear(); cur.update(v)
            else:
                st[k] = v
        regions = st.setdefault("regions", {})
        for k, v in (data.get("regions") or {}).items():
            if k in LIBRARY_REGIONS:
                regions[k] = v
        _extract_folder(z, "pictures", DIALOG_TEMPLATE_DIR)
        route = data.get("route")
        if route:
            clean = logic._clean_name(str(route)) or "Imported route"
            name, k = clean, 2
            while name in logic.list_routes():
                name, k = f"{clean} ({k})", k + 1
            os.makedirs(logic.route_dir(name), exist_ok=True)
            _extract_folder(z, "route", logic.route_dir(name))
            logic.set_active_route(name)
            route = name
    logic.app.settings.save()
    return route

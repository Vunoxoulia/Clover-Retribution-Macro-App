import base64
import threading
import time

import cv2
import numpy as np

DEFAULT_CREATURE = {"color1": [243, 99, 152], "tol1": 45, "min1": 3, "color2": [128, 143, 169], "tol2": 16, "min2": 10,
                    "near": 14, "area": [0, 0, 0, 0], "skip_me": True, "looks": []}
MAX_LOOKS = 6
TEACH_DAYLIGHT = 85
TEACH_SATURATION = 100

SELF_TOP, SELF_HALF_W = 0.36, 0.08


VIEW = (0.145, 0.10, 0.90, 0.78)


def view_mask(region, window, skip_me=True):
    l, t, r, b = region
    wl, wt, wr, wb = window
    ww, wh = wr - wl, wb - wt
    m = np.zeros((max(1, b - t), max(1, r - l)), bool)
    vx1, vy1 = int(wl + ww * VIEW[0]) - l, int(wt + wh * VIEW[1]) - t
    vx2, vy2 = int(wl + ww * VIEW[2]) - l, int(wt + wh * VIEW[3]) - t
    m[max(0, vy1):max(0, vy2), max(0, vx1):max(0, vx2)] = True
    if skip_me:
        m &= self_mask(region, window)
    return m


def self_mask(region, window):
    l, t, r, b = region
    wl, wt, wr, wb = window
    m = np.ones((max(1, b - t), max(1, r - l)), bool)
    ww, wh = wr - wl, wb - wt
    x1, x2 = int(wl + ww * (0.5 - SELF_HALF_W)) - l, int(wl + ww * (0.5 + SELF_HALF_W)) - l
    y1 = int(wt + wh * SELF_TOP) - t
    m[max(0, y1):, max(0, x1):max(0, x2)] = False
    return m


def hue_match(img, rgb, tol, scene_v=128.0):
    px = np.uint8([[[rgb[2], rgb[1], rgb[0]]]])
    ph, ps, pv = (int(v) for v in cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0, 0])
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[..., 0].astype(np.int16), hsv[..., 1], hsv[..., 2]
    dh = np.abs(H - ph)
    dh = np.minimum(dh, 180 - dh)
    ok = (dh <= max(2, int(tol) // 4)) & (S >= max(40, ps // 2))
    if pv < scene_v * 0.6:
        ok &= V < scene_v * 0.85
    else:
        ok &= V >= 60
    return ok


def find(img, c, mask=None, full_size=None):
    info = {}
    rgb = tuple(c.get("color1") or ()) or None
    if not rgb or img is None or not img.size:
        info["why"] = "no colour picked" if not rgb else "no picture"
        return False, None, info
    h, w = img.shape[:2]
    m = np.ones((h, w), bool) if mask is None else mask
    scene = float(np.median(cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 2][m])) if m.any() else 128.0
    hit = hue_match(img, rgb, int(c.get("tol1", 40)), scene) & m
    min1, min2 = int(c.get("min1", 5) or 1), int(c.get("min2", 5) or 1)
    info["px"] = int(hit.sum())
    if info["px"] < min1:
        info["why"] = f"too little of colour 1 ({info['px']} px, needs {min1})"
        return False, None, info
    rgb2 = tuple(c.get("color2") or ()) or None
    hit2 = None
    if rgb2:
        hit2 = hue_match(img, rgb2, int(c.get("tol2", 40)), scene) & m
        if int(hit2.sum()) < min2:
            info["why"] = f"too little of colour 2 ({int(hit2.sum())} px, needs {min2})"
            return False, None, info
        near = max(1, int(c.get("near", 20) or 20))
        k = np.ones((2 * near + 1,) * 2, np.uint8)
        close1 = hit & cv2.dilate(hit2.astype(np.uint8), k).astype(bool)
        hit2 = hit2 & cv2.dilate(hit.astype(np.uint8), k).astype(bool)
        hit = close1
        if int(hit.sum()) < min1:
            info["why"] = "both colours are on screen but not together"
            return False, None, info
    fw, fh = full_size or (w, h)
    n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(hit.astype(np.uint8), np.ones((25, 25), np.uint8)))
    best, best_n = None, 0
    for i in range(1, n):
        x, y, bw, bh, _ = (int(v) for v in st[i])
        if bw > fw * 0.12 or bh > fh * 0.3:
            continue
        patch = lab == i
        cnt = int(hit[patch].sum())
        if cnt < min1 or cnt <= best_n or cnt > 0.35 * bw * bh:
            continue
        if hit2 is not None and int(hit2[patch].sum()) < min2:
            continue
        best, best_n = i, cnt
    if best is None:
        info["why"] = "the colour is there, but nothing shaped like it"
        return False, None, info
    x, y, bw, bh, _ = (int(v) for v in st[best])
    info["px"] = best_n
    info["box"] = (x, y, x + bw, y + bh)
    return True, (x + bw // 2, y + bh // 2), info


ODD_W = 640.0
ODD_L, ODD_AB = 16, 32
ODD_BINS = ODD_L * ODD_AB * ODD_AB
ODD_COMMON = .01
ODD_SIZE = (.5, 1.7)
ODD_LIGHT = .55
ODD_CLEAN = np.ones((3, 3), np.uint8)
ODD_JOIN = np.ones((7, 7), np.uint8)


def scene_light(img, mask=None):
    g = cv2.cvtColor(np.ascontiguousarray(img[::4, ::4]), cv2.COLOR_BGR2GRAY)
    m = None if mask is None else mask[::4, ::4][:g.shape[0], :g.shape[1]]
    return float(np.median(g if m is None or not m.any() else g[m]))


def _colour_bins(small):
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
    return ((lab[..., 0] >> 4).astype(np.int32) << 10) | ((lab[..., 1] >> 3).astype(np.int32) << 5) | (lab[..., 2] >> 3)


def _grow(table):
    t = table.reshape(ODD_L, ODD_AB, ODD_AB).copy()
    for axis in range(3):
        v = np.moveaxis(t, axis, 0)
        old = v.copy()
        v[1:] |= old[:-1]
        v[:-1] |= old[1:]
    return t.ravel()


def _pack(table):
    return base64.b64encode(np.packbits(table).tobytes()).decode()


def _unpack(text):
    if not text:
        return np.zeros(ODD_BINS, bool)
    return np.unpackbits(np.frombuffer(base64.b64decode(text), np.uint8))[:ODD_BINS].astype(bool)


def _odd_pixels(bins, ok, taught, common):
    background = _grow(taught | (np.bincount(bins[ok], minlength=ODD_BINS) >= common))
    return ~background[bins] & ok


def _blobs(odd):
    u8 = cv2.morphologyEx(odd.astype(np.uint8), cv2.MORPH_OPEN, ODD_CLEAN)
    return cv2.connectedComponentsWithStats(cv2.morphologyEx(u8, cv2.MORPH_CLOSE, ODD_JOIN), connectivity=8)


def find_odd(img, look, mask=None, full_size=None, whole_view=False):
    if img is None or not img.size:
        return False, None, {"why": "no picture"}
    if scene_light(img, mask) < look["light"] * ODD_LIGHT:
        return False, None, {"why": "too dark for this look"}
    scale = ODD_W / (full_size or (img.shape[1], img.shape[0]))[0]
    bins = _colour_bins(cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA))
    H, W = bins.shape
    ok = np.ones((H, W), bool) if mask is None else cv2.resize(mask.astype(np.uint8), (W, H),
                                                               interpolation=cv2.INTER_NEAREST).astype(bool)
    if not ok.any():
        return False, None, {"why": "nothing to search"}
    tw, th, tp = look["w"] * ODD_W, look["h"] * ODD_W, look["px"] * ODD_W ** 2
    n, lab, st, mid = _blobs(_odd_pixels(bins, ok, _unpack(look["bg"]), max(ODD_COMMON * int(ok.sum()), .6 * tp)))
    top, left, right = np.where(ok.any(1))[0][0], np.where(ok.any(0))[0][0], np.where(ok.any(0))[0][-1]
    lo, hi = ODD_SIZE
    best, best_gap = None, 9.0
    for i in range(1, n):
        x, y, bw, bh, px = (int(v) for v in st[i])
        grow = bw * bh / (tw * th)
        if not (lo * tw <= bw <= hi * tw and lo * th <= bh <= hi * th and .4 * grow * tp <= px <= 2.5 * grow * tp):
            continue
        if whole_view:
            part = lab[y:y + bh, x:x + bw] == i
            if ((y <= top + 1 and part[0].sum() > .5 * bw) or (x <= left + 1 and part[:, 0].sum() > .5 * bh)
                    or (x + bw >= right and part[:, -1].sum() > .5 * bh)):
                continue
        gap = abs(float(np.log(grow)))
        if gap < best_gap:
            best, best_gap = i, gap
    if best is None:
        return False, None, {"why": "nothing of its size stands out"}
    x, y, bw, bh, px = (int(v) for v in st[best])
    return True, (int(mid[best][0] / scale), int(mid[best][1] / scale)), {
        "px": int(px / scale / scale), "how": "it stands out from the background",
        "box": (int(x / scale), int(y / scale), int((x + bw) / scale), int((y + bh) / scale))}


def find_any(img, c, mask=None, full_size=None, whole_view=False):
    looks = c.get("looks") or []
    for look in looks:
        if look.get("odd"):
            r = find_odd(img, look, mask, full_size, whole_view)
            if r[0]:
                return r
    ok, pos, info = find(img, c, mask, full_size)
    if ok:
        return ok, pos, info
    for look in looks:
        if look.get("color1") and (look.get("color1"), look.get("color2")) != (c.get("color1"), c.get("color2")):
            r = find(img, look, mask, full_size)
            if r[0]:
                return r
    if looks:
        n = len(looks)
        info = dict(info, why=f"none of your {n} saved look{'s' if n != 1 else ''} fits ({info.get('why', '?')})")
    return False, None, info


def look_picture(img, box, size=72):
    x1, y1, x2, y2 = (max(0, int(v)) for v in box)
    crop = img[y1:y2, x1:x2]
    if not crop.size:
        return ""
    small = cv2.resize(crop, None, fx=size / max(crop.shape[:2]), fy=size / max(crop.shape[:2]),
                       interpolation=cv2.INTER_AREA)
    ok, data = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return base64.b64encode(data.tobytes()).decode() if ok else ""


def read_look_picture(text):
    try:
        img = cv2.imdecode(np.frombuffer(base64.b64decode(text), np.uint8), cv2.IMREAD_COLOR)
        return None if img is None else img[:, :, ::-1]
    except Exception:
        return None


def forget_looks(c, numbers):
    looks = c.get("looks") or []
    drop = [looks[i] for i in numbers if 0 <= i < len(looks)]
    was_in_use = any(k.get("color1") and (k.get("color1"), k.get("color2")) == (c.get("color1"), c.get("color2"))
                     for k in drop)
    c["looks"] = [k for i, k in enumerate(looks) if i not in numbers]
    if was_in_use:
        left = [k for k in c["looks"] if k.get("color1")]
        if left:
            c.update({k: v for k, v in left[-1].items() if k != "pic"})
        else:
            c.update(color1=None, color2=None)


def _cells(hsv, scene_v):
    h, s, v = hsv[..., 0].astype(np.int32), hsv[..., 1], hsv[..., 2]
    cell = (h // 6) * 2 + (v < scene_v * 0.6)
    return np.where(s >= 40, cell, -1)


def teach(img, box, full_size=None, skip_me_window=None, area=None):
    return teach_many([{"img": img, "box": box, "full_size": full_size, "skip_me_window": skip_me_window}], area)


def _sample(sm, area):
    img, box = sm["img"], sm["box"]
    H, W = img.shape[:2]
    x1, y1, x2, y2 = (int(v) for v in box)
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(W, x2), min(H, y2)
    if x2 - x1 < 6 or y2 - y1 < 6:
        return "The box is too small - drag it around the whole creature."
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    scene_v = float(np.median(hsv[..., 2]))
    inside = np.zeros((H, W), bool)
    inside[y1:y2, x1:x2] = True
    skip = sm.get("skip_me_window")
    if area and area[2] > area[0] and area[3] > area[1]:
        view = np.zeros((H, W), bool)
        view[max(0, int(area[1])):int(area[3]), max(0, int(area[0])):int(area[2])] = True
        if skip:
            view &= self_mask([0, 0, W, H], skip)
    else:
        view = view_mask([0, 0, W, H], skip or [0, 0, W, H], skip_me=bool(skip))
    cells = _cells(hsv, scene_v)
    outside = view & ~inside
    return {"img": img, "hsv": hsv, "scene_v": scene_v, "cells": cells, "inside": inside, "outside": outside,
            "view": view, "box": (x1, y1, x2, y2), "full_size": sm.get("full_size"),
            "ci": np.bincount(cells[inside & (cells >= 0)], minlength=60),
            "co": np.bincount(cells[outside & (cells >= 0)], minlength=60),
            "n_in": max(1, int(inside.sum())), "n_out": max(1, int(outside.sum()))}


def teach_odd(sm, area=None):
    p = _sample(sm, area)
    if isinstance(p, str):
        return None, ""
    img, (x1, y1, x2, y2) = p["img"], p["box"]
    W = img.shape[1]
    scale = ODD_W / W
    bins = _colour_bins(cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA))
    H, Ws = bins.shape
    view = cv2.resize(p["view"].astype(np.uint8), (Ws, H), interpolation=cv2.INTER_NEAREST).astype(bool)
    box = np.zeros((H, Ws), bool)
    box[int(y1 * scale):int(y2 * scale), int(x1 * scale):int(x2 * scale)] = True
    around = view & ~box
    if not box.any() or not around.any():
        return None, ""
    cin = np.bincount(bins[box], minlength=ODD_BINS)
    cout = np.bincount(bins[around], minlength=ODD_BINS)
    mine = cin / cin.sum() > 4 * cout / cout.sum()
    taught = (cout >= 4) & ~mine
    ok = view | box
    n, lab, st, _ = _blobs(_odd_pixels(bins, ok, taught, ODD_COMMON * int(ok.sum())) & box)
    if n < 2:
        return None, ""
    i = 1 + int(np.argmax(st[1:, 4]))
    _, _, bw, bh, px = (int(v) for v in st[i])
    look = {"odd": True, "w": bw / ODD_W, "h": bh / ODD_W, "px": px / ODD_W ** 2, "bg": _pack(taught),
            "light": round(scene_light(img, p["view"]), 1)}
    whole = not (area and area[2] > area[0] and area[3] > area[1])
    px_, py_ = int((x2 - x1) * 0.15), int((y2 - y1) * 0.15)
    found, pos, _ = find_odd(img, look, p["view"] | p["inside"], sm.get("full_size"), whole)
    if not (found and x1 - px_ <= pos[0] <= x2 + px_ and y1 - py_ <= pos[1] <= y2 + py_):
        return None, ""
    away = p["outside"].copy()
    away[max(0, y1 - py_):y2 + py_, max(0, x1 - px_):x2 + px_] = False
    also = find_odd(img, look, away, sm.get("full_size"), whole)[0]
    return look, (" Something else on this screen stands out the same way - press Test to see what it picks, and "
                  "set an Area if that isn't your creature." if also else "")


def strong_colour(rgb):
    return int(cv2.cvtColor(np.uint8([[rgb[::-1]]]), cv2.COLOR_BGR2HSV)[0, 0, 1]) >= TEACH_SATURATION


def teach_look(sm, area=None):
    x1, y1, x2, y2 = (int(v) for v in sm["box"])
    if area and area[2] > area[0] and area[3] > area[1]:
        w = max(0, min(x2, area[2]) - max(x1, area[0]))
        h = max(0, min(y2, area[3]) - max(y1, area[1]))
        if w * h < 0.5 * max(1, (x2 - x1) * (y2 - y1)):
            return [], ("Your box isn't inside your Area, and only the Area is searched - press Clear next to "
                        "Set area, or set a bigger one.")
    p = _sample(sm, area)
    if isinstance(p, str):
        return [], p
    colours, report = teach_many([sm], area)
    strong = colours if colours and strong_colour(colours["color1"]) else None
    odd, warning = teach_odd(sm, area)
    said = "Learned what stands out from the background." + warning
    if scene_light(p["img"], p["view"]) >= TEACH_DAYLIGHT:
        if odd:
            return [odd], said
        return ([strong], report) if strong else ([], "Couldn't learn it on this screen - drag the box tighter around "
                                                      "the creature.")
    if strong:
        return [strong], report
    return ([odd], said) if odd else ([], "Couldn't learn it on this screen - drag the box tighter around the "
                                          "creature.")


def teach_many(samples, area=None):
    ss = []
    for sm in samples:
        r = _sample(sm, area)
        if isinstance(r, str):
            return None, r
        ss.append(r)
    if not ss:
        return None, "Drag a box around the creature first."
    fi = np.mean([x["ci"] / x["n_in"] for x in ss], axis=0)
    fo = np.max([x["co"] / x["n_out"] for x in ss], axis=0)
    present = np.min([x["ci"] for x in ss], axis=0)
    rarity = (fi + 1e-5) / (fo + 1e-5)
    usable = [int(c) for c in range(len(fi)) if present[c] >= 6]
    firsts = sorted([c for c in usable if rarity[c] >= 4], key=lambda c: -rarity[c])[:4]
    seconds = sorted([c for c in usable if rarity[c] >= 1.5], key=lambda c: -fi[c])[:4]
    if not firsts:
        return None, ("Nothing in the box stands out from the background" + (" in every example" if len(ss) > 1
                      else "") + " - drag it tighter around the creature.")

    def colour(c):
        rgbs = np.concatenate([x["img"][x["inside"] & (x["cells"] == c)] for x in ss])
        hues = np.concatenate([x["hsv"][..., 0][x["inside"] & (x["cells"] == c)] for x in ss])
        rgb = [int(np.median(rgbs[:, k])) for k in (2, 1, 0)]
        ph = int(np.median(hues))
        dark = bool(c % 2)
        spreads, counts = [], []
        for x in ss:
            dh = np.abs(x["hsv"][..., 0].astype(np.int32) - ph)
            dh = np.minimum(dh, 180 - dh)
            same = (x["inside"] & (x["hsv"][..., 1] >= 40) & (dh <= 12)
                    & ((x["hsv"][..., 2] < x["scene_v"] * 0.6) == dark))
            if same.any():
                spreads.append(float(np.percentile(dh[same], 90)))
            counts.append(int(same.sum()))
        tol = int(max(16, min(80, max(spreads or [3.0]) * 4 + 8)))
        return rgb, tol, min(counts)

    order = list(dict.fromkeys(firsts + seconds))
    info = {c: colour(c) for c in order}
    big = max(max(x["box"][2] - x["box"][0], x["box"][3] - x["box"][1]) for x in ss)
    near = int(max(10, min(40, 0.12 * big)))

    def settings(c1, c2):
        rgb, tol, n = info[c1]
        d = {"color1": rgb, "tol1": tol, "min1": int(max(3, min(10, n * 0.05))), "near": near,
             "color2": None, "tol2": 40, "min2": 5}
        if c2 is not None:
            rgb2, tol2, n2 = info[c2]
            d.update(color2=rgb2, tol2=tol2, min2=int(max(3, min(10, n2 * 0.05))))
        return d

    def check(d, x):
        x1, y1, x2, y2 = x["box"]
        px, py = int((x2 - x1) * 0.15), int((y2 - y1) * 0.15)
        ok, pos, _ = find(x["img"], d, mask=x["view"] | x["inside"], full_size=x["full_size"])
        in_box = ok and x1 - px <= pos[0] <= x2 + px and y1 - py <= pos[1] <= y2 + py
        away = x["outside"].copy()
        away[max(0, y1 - py):y2 + py, max(0, x1 - px):x2 + px] = False
        elsewhere = find(x["img"], d, mask=away, full_size=x["full_size"])[0]
        return in_box, elsewhere

    tried = []
    for c1 in firsts:
        for c2 in [c for c in seconds if c != c1] + [None]:
            d = settings(c1, c2)
            res = [check(d, x) for x in ss]
            tried.extend(res)
            if all(i and not e for i, e in res):
                text = (f"Learned: colour 1 {tuple(d['color1'])} (tol {d['tol1']}), "
                        + (f"colour 2 {tuple(d['color2'])} (tol {d['tol2']}). " if c2 is not None else "no colour 2. ")
                        + (f"Found it in all {len(ss)} examples and nothing anywhere else in them." if len(ss) > 1
                           else "Found it in your box and nothing anywhere else on this screen."))
                return d, text
    if any(t[0] for t in tried):
        where = "in your search area" if area and area[2] > area[0] else "on screen"
        return None, (f"Its colours also show up elsewhere {where}. Set a search area (Set area) around where it "
                      "usually is - smaller is safer - then Teach again.")
    return None, ("Couldn't find it again with the colours in the box" + (" in every example" if len(ss) > 1 else "")
                  + " - drag the box tighter around the creature.")


class CreatureWatcher:

    def __init__(self, capture, settings, alive, window_region=None, log=lambda m: None):
        self.capture = capture
        self.settings = settings
        self.alive = alive
        self.window_region = window_region
        self.log = log
        self.seen = False
        self.pos = None
        self.info = {}
        self.changed = threading.Event()
        self._hits = 0
        self._last_hit = 0.0
        self._thread = None

    def region(self, c):
        a = list(c.get("area") or [0, 0, 0, 0])
        if a[2] > a[0] and a[3] > a[1]:
            return a
        return list(self.window_region()) if self.window_region else None

    def look(self):
        s = self.settings()
        c = s.get("creature") or {}
        reg = self.region(c)
        if not reg:
            return False, None, {"why": "no Roblox window"}
        img = self.capture(reg)
        win = self.window_region() if self.window_region else None
        full = (win[2] - win[0], win[3] - win[1]) if win else None
        mask = None
        if win and img is not None and img.size:
            a = list(c.get("area") or [0, 0, 0, 0])
            if a[2] > a[0] and a[3] > a[1]:
                if c.get("skip_me", True):
                    mask = self_mask(reg, win)
            else:
                mask = view_mask(reg, win, c.get("skip_me", True))
            if mask is not None:
                mask = mask[:img.shape[0], :img.shape[1]]
        has_area = c.get("area") and c["area"][2] > c["area"][0] and c["area"][3] > c["area"][1]
        ok, pos, info = find_any(img, c, mask=mask, full_size=full, whole_view=not has_area)
        if info.get("box"):
            x1, y1, x2, y2 = info["box"]
            info["box"] = (reg[0] + x1, reg[1] + y1, reg[0] + x2, reg[1] + y2)
        return ok, ((reg[0] + pos[0], reg[1] + pos[1]) if pos else None), info

    def step(self, now=None):
        now = time.time() if now is None else now
        s = self.settings()
        ok, pos, info = self.look()
        self.info = info
        if ok:
            self._hits += 1
            self._last_hit = now
            self.pos = pos
        else:
            self._hits = 0
        before = self.seen
        if not self.seen and self._hits >= max(1, int(s.get("seen_after", 2) or 1)):
            self.seen = True
        elif self.seen and not ok and now - self._last_hit >= max(0.0, float(s.get("lost_after", 1.5) or 0)):
            self.seen = False
            self.pos = None
        if self.seen != before:
            self.changed.set()
            return True
        return False

    def start(self):
        self.seen, self.pos, self._hits, self._last_hit = False, None, 0, 0.0
        self.changed.clear()

        def loop():
            while self.alive():
                t0 = time.time()
                try:
                    self.step()
                except Exception as e:
                    self.log(f"Target check error: {e}")
                wait = max(0.05, float(self.settings().get("poll", 0.25) or 0.25)) - (time.time() - t0)
                end = time.time() + max(0.0, wait)
                while self.alive() and time.time() < end:
                    time.sleep(0.02)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
        return self._thread

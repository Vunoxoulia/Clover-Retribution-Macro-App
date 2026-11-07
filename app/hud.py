import numpy as np
import cv2

SEARCH_AREA = (0.2, 0.55, 0.8, 0.99)


def _runs(row, need):
    if not row.any():
        return []
    d = np.diff(np.concatenate(([0], row.view(np.int8), [0])))
    starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
    keep = (ends - starts) >= need
    return list(zip(starts[keep].tolist(), ends[keep].tolist()))


def find_bar(img, kind, min_frac=0.04, area=SEARCH_AREA, max_thick=0.06, min_ratio=4):
    if img is None or not img.size:
        return None
    H, W = img.shape[:2]
    x1, y1, x2, y2 = int(W * area[0]), int(H * area[1]), int(W * area[2]), int(H * area[3])
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    if kind == "health":
        mask = ((h <= 10) | (h >= 170)) & (s >= 80) & (v >= 60)
    else:
        mask = (h >= 92) & (h <= 115) & (s >= 70) & (v >= 60)
    need = max(20, int(min(W, H * 16 / 9) * min_frac))
    tol = max(4, int(W * 0.01))
    strips, open_ = [], []
    for r in range(mask.shape[0]):
        still = []
        for a, b in _runs(mask[r], need):
            st = next((k for k in open_ if abs(k[2] - a) <= tol and abs(k[3] - b) <= tol), None)
            if st is not None:
                open_.remove(st)
                st[1], st[2], st[3] = r + 1, a, b
                st[4], st[5] = max(st[4], a), min(st[5], b)
            else:
                st = [r, r + 1, a, b, a, b]
                strips.append(st)
            still.append(st)
        open_ = still
    k = max(2, int(H * 0.004))

    def frame(ra, rb, xa, xb):
        ra, rb = max(0, ra), min(v.shape[0], rb)
        return (rb > ra and float(np.median(v[ra:rb, xa:xb])) < 130
                and float(np.median(s[ra:rb, xa:xb])) < 90)
    best = None
    for top, bottom, _, _, xa, xb in strips:
        thick = bottom - top
        if not (3 <= thick <= max(36, int(H * max_thick))) or xb - xa < max(need * 0.8, thick * min_ratio):
            continue
        if frame(top - k - 1, top - 1, xa, xb) and frame(bottom + 1, bottom + k + 1, xa, xb):
            cand = (x1 + xa, y1 + top, x1 + xb, y1 + bottom)
            if best is None or (cand[2] - cand[0]) > (best[2] - best[0]):
                best = cand
    return best


def hud_shown(img):
    return find_bar(img, "health") is not None or find_bar(img, "mana") is not None

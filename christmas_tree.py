"""ASCII Christmas Tree - a full, glowing 3D tree drawn with text characters.

Run:   python christmas_tree.py             window
       python christmas_tree.py --full      fullscreen (big, high-detail tree)
       (needs: python -m pip install pygame-ce numpy)
Keys:  Space pause · R restart · S screenshot · H info · F / F11 fullscreen · G glow on/off · Esc quit

A dense cloud of 3D points (tiered cone of needles, gold garland, lights, ornaments,
star, trunk, presents) turns slowly. Each frame the points are projected onto a text
grid; the nearest point in a cell picks the character (dense = bright) and its colour.
A soft light layer behind the text makes the bulbs, garland and star glow.
"""
import math
import os
import sys
import time

import numpy as np

# ---------------------------------------------------------------- settings
COLS, ROWS = 92, 74              # window grid; fullscreen picks its own (denser) grid
MESSAGE = "MERRY CHRISTMAS"
FPS = 30
SEED = 11

TREE_TOP, FOLIAGE_BOTTOM, BASE_R, TIERS = 10.0, 0.9, 3.7, 6
SPIN = 0.30                      # rad/s
CAM_Y, CAM_D = 5.2, 42.0
LIGHT = np.array([-0.55, 0.55, 0.65]); LIGHT /= np.linalg.norm(LIGHT)
T_GROW, T_GARLAND, T_LIGHTS, T_ORN, T_STAR, T_MSG = 3.6, 3.4, 4.6, 5.6, 6.8, 8.0

SKY = (5, 8, 18)
RAMP = " .,:;~=+*xo%#&@"              # sparse -> dense
CHARS = RAMP + "'`^-|/\\_"
CI = {c: i for i, c in enumerate(CHARS)}
FOLIAGE, GARLAND, ORN, TRUNK, BOX, RIBBON = range(6)
MSG_COLORS = np.array([(236, 64, 64), (250, 204, 92), (90, 210, 120)], float)


def ease(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3 - 2 * u)


def radius_at(y):
    """Tiered silhouette: each layer flares out toward its lower edge."""
    h = np.clip((y - FOLIAGE_BOTTOM) / (TREE_TOP - FOLIAGE_BOTTOM), 0, 1)
    frac = (h * TIERS) % 1.0
    return BASE_R * (1 - h) ** 1.05 * (0.80 + 0.20 * (1 - frac) ** 0.6) + 0.08


class Tree:
    def __init__(self, cols, rows, seed=SEED):
        self.cols, self.rows = cols, rows
        S = self.S = rows / 74.0                 # detail scale (1 = window grid)
        A = S * S                                # point counts follow the number of cells
        rng = self.rng = np.random.default_rng(seed)
        parts = []

        # foliage on the tiered cone surface (density follows area)
        m = int(18000 * A * 0.85)
        y = FOLIAGE_BOTTOM + (TREE_TOP - FOLIAGE_BOTTOM) * (1 - np.sqrt(rng.random(m)))
        y = np.clip(y + rng.normal(0, 0.03, m), FOLIAGE_BOTTOM, TREE_TOP)
        phi = rng.random(m) * 2 * np.pi
        r = radius_at(y) * (0.86 + 0.14 * rng.random(m) ** 0.5)
        N = np.stack([np.cos(phi), np.full(m, 0.42), np.sin(phi)], 1)
        N /= np.linalg.norm(N, axis=1, keepdims=True)
        t0 = 0.15 + T_GROW * ease((y - FOLIAGE_BOTTOM) / (TREE_TOP - FOLIAGE_BOTTOM)) + rng.random(m) * 0.2
        parts.append((np.stack([r * np.cos(phi), y, r * np.sin(phi)], 1), N, FOLIAGE, np.zeros((m, 3)), t0))
        fol_jit = rng.normal(0, 0.09, m)

        # gold garland: a spiral drooping in swags
        m = int(2600 * S)
        u = np.linspace(0, 1, m)
        ang = 2 * np.pi * 4.2 * u + 0.7
        yg = TREE_TOP - 1.0 - u * (TREE_TOP - FOLIAGE_BOTTOM - 1.6) - 0.32 * np.abs(np.sin((2 * np.pi * 4.2 * u + 0.7) * 2.6))
        rg = radius_at(yg) * 1.02 + 0.05
        P = np.stack([rg * np.cos(ang), yg, rg * np.sin(ang)], 1) + rng.normal(0, 0.035, (m, 3))
        N = np.stack([np.cos(ang), np.full(m, 0.3), np.sin(ang)], 1); N /= np.linalg.norm(N, axis=1, keepdims=True)
        parts.append((P, N, GARLAND, np.tile([236, 186, 70], (m, 1)), T_GARLAND + u * 1.6))
        self.gar_idx_range = None

        # ornaments: shaded balls
        palette = np.array([(214, 36, 46), (232, 180, 60), (60, 120, 220), (210, 214, 226), (190, 40, 120)], float)
        n_orn = 30
        oy = FOLIAGE_BOTTOM + 0.6 + (TREE_TOP - FOLIAGE_BOTTOM - 2.2) * rng.random(n_orn) ** 1.2
        oph = rng.random(n_orn) * 2 * np.pi
        self.orn_centres, self.orn_cols = [], []
        for j in range(n_orn):
            m = int(80 * A)
            v = rng.normal(0, 1, (m, 3)); v /= np.linalg.norm(v, axis=1, keepdims=True)
            rr = radius_at(oy[j]) * 0.98
            c = np.array([rr * np.cos(oph[j]), oy[j] - 0.15, rr * np.sin(oph[j])])
            parts.append((c + v * 0.30, v, ORN, np.tile(palette[j % len(palette)], (m, 1)),
                          np.full(m, T_ORN + rng.random() * 1.2)))

        # Short, warm bark trunk, gently flared where it meets the snow.
        m = int(900 * A)
        yt = rng.uniform(0, FOLIAGE_BOTTOM + 0.3, m); ph = rng.random(m) * 2 * np.pi
        rt = 0.43 + 0.12 * np.exp(-yt / 0.22)
        bark = 0.88 + 0.12 * np.cos(ph * 13 + 0.25 * np.sin(yt * 5))
        trunk_color = np.array([164, 109, 62]) * bark[:, None]
        parts.append((np.stack([rt * np.cos(ph), yt, rt * np.sin(ph)], 1),
                      np.stack([np.cos(ph), np.zeros(m), np.sin(ph)], 1), TRUNK, trunk_color,
                      np.full(m, 0.05)))

        # presents
        boxes = [((2.6, 1.6), (1.0, 0.8, 0.9), 0.35, (196, 34, 46), (244, 206, 96)),
                 ((-2.8, 0.8), (0.85, 0.6, 0.8), -0.5, (44, 98, 190), (240, 240, 245)),
                 ((0.3, -2.9), (1.1, 0.65, 0.9), 0.9, (236, 220, 186), (200, 36, 46)),
                 ((-1.7, -2.3), (0.7, 0.95, 0.7), 0.2, (36, 140, 80), (244, 206, 96))]
        g = 0.09 / S
        for j, ((bx, bz), (w, h, d), psi, col, rib) in enumerate(boxes):
            faces = []
            u_, v_ = np.meshgrid(np.arange(-w / 2, w / 2, g), np.arange(-d / 2, d / 2, g))
            faces.append((np.stack([u_.ravel(), np.full(u_.size, h), v_.ravel()], 1), (0, 1, 0)))
            for sx, sz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                half, other = (w / 2, d / 2) if sx else (d / 2, w / 2)
                u_, v_ = np.meshgrid(np.arange(-other, other, g), np.arange(0, h, g))
                q = (np.stack([np.full(u_.size, sx * half), v_.ravel(), u_.ravel()], 1) if sx else
                     np.stack([u_.ravel(), v_.ravel(), np.full(u_.size, sz * half)], 1))
                faces.append((q, (sx, 0, sz)))
            q = np.concatenate([f for f, _ in faces])
            nn = np.concatenate([np.tile(n, (len(f), 1)) for f, n in faces]).astype(float)
            rib_m = (np.abs(q[:, 0]) < 0.09) | (np.abs(q[:, 2]) < 0.09)
            c, s = math.cos(psi), math.sin(psi)
            R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
            q = q @ R.T + [bx, 0, bz]; nn = nn @ R.T
            t0 = np.full(len(q), 2.4 + 0.3 * j)
            parts.append((q[~rib_m], nn[~rib_m], BOX, np.tile(col, ((~rib_m).sum(), 1)), t0[~rib_m]))
            parts.append((q[rib_m], nn[rib_m], RIBBON, np.tile(rib, (rib_m.sum(), 1)), t0[rib_m]))

        self.P = np.concatenate([p[0] for p in parts]).astype(np.float32)
        self.N = np.concatenate([p[1] for p in parts]).astype(np.float32)
        self.K = np.concatenate([np.full(len(p[0]), p[2]) for p in parts]).astype(np.int8)
        self.C = np.concatenate([p[3] for p in parts]).astype(np.float32)
        self.T0 = np.concatenate([p[4] for p in parts]).astype(np.float32)
        self.jit = np.zeros(len(self.P), np.float32); self.jit[:len(fol_jit)] = fol_jit
        self.rnd = rng.random(len(self.P)).astype(np.float32)
        self.t_all = float(self.T0.max())
        kc = {GARLAND: "~=*", ORN: "o%@", TRUNK: ":|#", BOX: ":%#", RIBBON: "-+*"}
        self.kchars = np.zeros((len(self.P), 3), np.int32)
        for k, s in kc.items():
            self.kchars[self.K == k] = [CI[c] for c in s]
        lv = np.linspace(0, 1, 64)
        dark, mid, hi = np.array([10, 52, 24]), np.array([34, 150, 62]), np.array([150, 236, 120])
        self.g_lut = np.where(lv[:, None] < 0.55, dark + (mid - dark) * (lv[:, None] / 0.55),
                              mid + (hi - mid) * ((lv[:, None] - 0.55) / 0.45)).astype(np.float32)
        self.c_lut = np.array([CI[RAMP[min(len(RAMP) - 1, 1 + int(v * (len(RAMP) - 1.01)))]] for v in lv], np.int32)

        # lights
        nl = 170
        ly = FOLIAGE_BOTTOM + 0.3 + (TREE_TOP - FOLIAGE_BOTTOM - 0.9) * (1 - np.sqrt(rng.random(nl)))
        lph = rng.random(nl) * 2 * np.pi
        lr = radius_at(ly) * 1.03
        self.LP = np.stack([lr * np.cos(lph), ly, lr * np.sin(lph)], 1)
        pal = np.array([(255, 70, 70), (255, 200, 80), (90, 150, 255), (255, 236, 210), (255, 110, 200), (120, 255, 160)], float)
        self.LC = pal[rng.integers(len(pal), size=nl)]
        order = np.argsort(ly)
        self.L_t0 = np.empty(nl); self.L_t0[order] = T_LIGHTS + np.linspace(0, 1.8, nl)
        self.L_w = rng.uniform(1.5, 4.0, nl); self.L_p = rng.random(nl) * 2 * np.pi

        # star shape in cells
        self.star = None

        # sky, snow, ground
        ns = int(120 * (cols * rows) / (92 * 74))
        self.stars = np.stack([rng.integers(0, cols, ns), rng.integers(0, int(rows * 0.76), ns), rng.random(ns) * 6.28,
                               rng.uniform(0.6, 2.4, ns)], 1)
        nfl = int(160 * (cols * rows) / (92 * 74))
        self.flakes = np.stack([rng.uniform(0, cols, nfl), rng.uniform(0, rows, nfl), rng.uniform(1.0, 3.6, nfl) * S,
                                rng.random(nfl) * 6.28, rng.random(nfl)], 1)
        self.ground = rng.random((rows, cols))

    def _star_cells(self, aspect):
        cells = []
        R = 3.2 * self.S
        for dr in range(-int(5 * self.S) - 1, int(5 * self.S) + 2):
            for dc in range(-int(10 * self.S) - 1, int(10 * self.S) + 2):
                xx, yy = dc / aspect, dr
                rad = math.hypot(xx, yy)
                ang = math.atan2(xx, -yy)
                sector = (ang % (2 * math.pi / 5)) / (2 * math.pi / 5)
                edge = R * (0.40 + 0.60 * abs(1 - 2 * sector) ** 1.7)
                if rad <= edge:
                    ch = "@" if rad < R * 0.3 else ("#" if rad < edge * 0.65 else "*")
                    cells.append((dr, dc, CI[ch], 1.0 if rad < R * 0.5 else 0.82, rad / R))
        a = np.array(cells, float)
        return a[:, 0].astype(int), a[:, 1].astype(int), a[:, 2].astype(int), a[:, 3], a[:, 4]

    # ------------------------------------------------------------ one frame
    def frame(self, t, kx, ky):
        COLS_, ROWS_, S = self.cols, self.rows, self.S
        size = ROWS_ * COLS_
        ch = np.zeros(size, np.int32)
        col = np.zeros((size, 3), np.float32)
        ground_row = ROWS_ - int(round(12 * S))
        cx = COLS_ / 2
        theta = SPIN * t + 0.4
        c, s = math.cos(theta), math.sin(theta)

        def project(P):
            x = P[:, 0] * c + P[:, 2] * s
            z = -P[:, 0] * s + P[:, 2] * c
            f = CAM_D / (CAM_D - z)
            return cx + x * f * kx, ground_row - ((P[:, 1] - CAM_Y) * f + CAM_Y) * ky, z

        # sky stars
        tw = 0.5 + 0.5 * np.sin(t * self.stars[:, 3] + self.stars[:, 2])
        i = self.stars[:, 1].astype(int) * COLS_ + self.stars[:, 0].astype(int)
        ch[i] = np.where(tw > 0.9, CI["*"], np.where(tw > 0.45, CI["."], CI["`"]))
        col[i] = np.array([140, 150, 190]) * (0.3 + 0.7 * tw[:, None])
        # snowy ground, warm under the tree
        gr = np.arange(ground_row - 1, ROWS_ - int(round(5 * S)))
        G = self.ground[gr]
        depth = ((gr - ground_row + 2) / (len(gr) + 1))[:, None]
        rr, cc = np.nonzero(G < 0.22 + 0.3 * depth)
        i = gr[rr] * COLS_ + cc
        g = G[rr, cc]
        ch[i] = np.where(g < 0.07, CI[","], np.where(g < 0.14, CI["_"], CI["."]))
        warm = np.exp(-((cc - cx) / (24.0 * S)) ** 2 - ((gr[rr] - ground_row) / (5.0 * S)) ** 2)
        col[i] = np.array([66, 76, 100]) * (0.6 + 0.6 * depth[rr]) + np.array([160, 110, 40]) * warm[:, None]
        # snow behind
        fl = self.flakes
        fy = (fl[:, 1] + t * fl[:, 2]) % ROWS_
        fx = (fl[:, 0] + 1.5 * S * np.sin(t * 0.7 + fl[:, 3])) % COLS_
        fi = fy.astype(int) * COLS_ + fx.astype(int)
        back = fl[:, 4] < 0.5
        ch[fi[back]] = CI["."]; col[fi[back]] = (140, 150, 175)

        # tree points
        if t >= self.t_all:
            P, N, K, C, jit, rnd, kch = self.P, self.N, self.K, self.C, self.jit, self.rnd, self.kchars
        else:
            v = self.T0 <= t
            P, N, K, C, jit, rnd, kch = self.P[v], self.N[v], self.K[v], self.C[v], self.jit[v], self.rnd[v], self.kchars[v]
        sx, sy, z = project(P)
        r_ = (sy + 0.5).astype(np.int32); c_ = (sx + 0.5).astype(np.int32)
        ok = (r_ >= 0) & (r_ < ROWS_) & (c_ >= 0) & (c_ < COLS_)
        nx = N[:, 0] * c + N[:, 2] * s; nz = -N[:, 0] * s + N[:, 2] * c
        lam = np.clip(nx * LIGHT[0] + N[:, 1] * LIGHT[1] + nz * LIGHT[2], 0, 1)
        b = np.clip(0.18 + 0.82 * lam + jit + 0.14 * (z / BASE_R), 0, 1)
        li = (b * 63).astype(np.int32)
        cidx = self.c_lut[li]
        colr = self.g_lut[li]
        nf = np.flatnonzero(K != FOLIAGE)
        gar_cells = None
        if len(nf):
            lamn = lam[nf]
            cidx[nf] = kch[nf, np.minimum(2, (lamn * 2.999).astype(int))]
            colr[nf] = C[nf] * (0.35 + 0.65 * lamn)[:, None]
            trunk = nf[K[nf] == TRUNK]
            colr[trunk] = C[trunk] * (0.65 + 0.35 * lam[trunk])[:, None]
            kn = K[nf]
            o = nf[kn == ORN]
            if len(o):
                spec = (lam[o] ** 16)[:, None]
                colr[o] = colr[o] * (1 - spec) + 255 * spec
            g_ = nf[kn == GARLAND]
            if len(g_):
                sparkle = 0.8 + 0.4 * np.sin(t * 3 + rnd[g_] * 20)
                colr[g_] *= sparkle[:, None]
                front = (z[g_] > 0) & ok[g_] & (sparkle > 1.1)          # bright garland glints feed the glow layer
                gar_cells = (sy[g_][front], sx[g_][front], sparkle[front] - 1.0)

        okz = np.flatnonzero(ok)
        zq = ((z[okz] + 8.0) * 2000).astype(np.int16)                 # int keys -> fast radix sort
        order = okz[np.argsort(zq, kind="stable")]
        cell = r_[order] * COLS_ + c_[order]
        ch[cell] = cidx[order]
        col[cell] = colr[order]

        info = {"rotation": math.degrees(theta) % 360, "lights": 0, "letters": 0,
                "light_pts": None, "star": None, "garland": gar_cells, "tree_box": None}
        # tree outline for the soft halo
        top = project(np.array([[0.0, TREE_TOP, 0.0]]))
        info["tree_box"] = (float(top[1][0]), float(ground_row), float(cx), BASE_R * kx)

        # lights
        lv = self.L_t0 <= t
        n_on = int(lv.sum()); info["lights"] = n_on
        if n_on:
            lx, ly, lz = project(self.LP[lv])
            lr, lc = (ly + 0.5).astype(int), (lx + 0.5).astype(int)
            rad = np.hypot(self.LP[lv, 0], self.LP[lv, 2])
            sel = (lr >= 0) & (lr < ROWS_) & (lc >= 0) & (lc < COLS_) & (lz > -0.15 * rad)
            inten = (0.5 + 0.5 * np.sin(t * self.L_w[lv] + self.L_p[lv])) * np.clip((t - self.L_t0[lv]) / 0.3, 0, 1)
            LC = self.LC[lv][sel]; it = inten[sel]
            li_ = lr[sel] * COLS_ + lc[sel]
            ch[li_] = np.where(it > 0.55, CI["@"], np.where(it > 0.25, CI["o"], CI["."]))
            col[li_] = np.minimum(255, LC * (0.55 + 0.7 * it[:, None]))
            info["light_pts"] = (ly[sel], lx[sel], LC, it)

        # star
        if t >= T_STAR:
            if self.star is None:
                self.star = self._star_cells(kx / ky)
            dr, dc, sc, sw, rr_ = self.star
            st = float(ease((t - T_STAR) / 0.6))
            keep = rr_ <= st * 1.06 + 0.01
            x0, y0, _ = project(np.array([[0.0, TREE_TOP + 0.45, 0.0]]))
            y0, x0 = float(y0[0]), float(x0[0])
            r2 = int(round(y0)) + dr[keep]; c2 = int(round(x0)) + dc[keep]
            okk = (r2 >= 0) & (r2 < ROWS_) & (c2 >= 0) & (c2 < COLS_)
            i = r2[okk] * COLS_ + c2[okk]
            pulse = 0.88 + 0.12 * math.sin(t * 2.3)
            ch[i] = sc[keep][okk]; col[i] = np.array([255, 214, 90]) * (sw[keep][okk] * pulse)[:, None]
            info["star"] = (y0, x0, st * pulse)

        # snow in front
        fr = ~back
        ch[fi[fr]] = np.where(fl[fr, 2] > 2.5 * S, CI["*"], CI["."])
        col[fi[fr]] = np.array([215, 225, 240]) * (0.5 + 0.5 * np.clip(fl[fr, 2:3] / (3.6 * S), 0, 1))

        # message (drawn large by the front end)
        if t >= T_MSG:
            text = " ".join(MESSAGE)
            info["letters"] = min(len(text), int((t - T_MSG) / 0.09))
        np.clip(col, 0, 255, out=col)
        return ch, col, info


# ---------------------------------------------------------------- glow layer (numpy, shared by window and preview)
class Glow:
    """Soft light behind the text: blobs splatted on a quarter-size canvas, smoothed when scaled up."""

    def __init__(self, w, h, cw, chh, down=8):
        self.down, self.cw, self.chh = down, cw, chh
        self.gw, self.gh = w // down + 1, h // down + 1
        self.kern = {}

    def _k(self, radius):
        r = max(1, int(radius))
        k = self.kern.get(r)
        if k is None:
            a = np.arange(-3 * r, 3 * r + 1)
            d2 = a[:, None] ** 2 + a[None, :] ** 2
            k = self.kern[r] = np.exp(-d2 / (2.0 * r * r)).astype(np.float32)
        return k

    def _splat(self, buf, x, y, colr, radius):
        k = self._k(radius); r = (k.shape[0] - 1) // 2
        x, y = int(x), int(y)
        x0, x1, y0, y1 = max(0, x - r), min(self.gw, x + r + 1), max(0, y - r), min(self.gh, y + r + 1)
        if x0 >= x1 or y0 >= y1:
            return
        buf[x0:x1, y0:y1] += k[x0 - x + r:x1 - x + r, y0 - y + r:y1 - y + r, None] * colr

    @staticmethod
    def _box(a, r, axis):
        if axis == 1:
            return Glow._box(a.swapaxes(0, 1), r, 0).swapaxes(0, 1)
        n = a.shape[0]
        c = np.empty((n + 2 * r + 1,) + a.shape[1:], np.float32)
        c[0] = 0
        np.cumsum(np.concatenate([np.zeros((r,) + a.shape[1:], np.float32), a, np.zeros((r,) + a.shape[1:], np.float32)]),
                  axis=0, out=c[1:])
        return (c[2 * r + 1:] - c[:n]) * (1.0 / (2 * r + 1))

    def _blur(self, a, sigma):
        r = max(1, int(round(sigma)))
        for _ in range(2):
            a = self._box(self._box(a, r, 0), r, 1)
        return a

    def _points(self, buf, xs, ys, cols):
        xi = xs.astype(int); yi = ys.astype(int)
        m = (xi >= 0) & (xi < self.gw) & (yi >= 0) & (yi < self.gh)
        np.add.at(buf, (xi[m], yi[m]), cols[m])

    def build(self, info, off=(0, 0)):
        d, cw, chh = self.down, self.cw, self.chh
        ox, oy = off
        tb = info.get("tree_box")
        key = tuple(round(v, 1) for v in tb) if tb else None
        if key != getattr(self, "_halo_key", None):          # warm-green halo: only rebuilt when the tree moves
            halo = np.zeros((self.gw, self.gh, 3), np.float32)
            if tb:
                top, gnd, cx, half = tb
                for f in np.linspace(0.15, 0.95, 6):
                    yy = top + (gnd - top) * f
                    self._splat(halo, (ox + cx * cw) / d, (oy + yy * chh) / d, np.array([12, 24, 11]) * (0.6 + 0.4 * f),
                                half * cw / d * (0.30 + 0.35 * f))
            self._halo, self._halo_key = halo, key
        pts = np.zeros((self.gw, self.gh, 3), np.float32)
        sig = 1.2 * chh / d
        lp = info.get("light_pts")
        if lp is not None:
            ys, xs, cs, its = lp
            self._points(pts, (ox + xs * cw) / d, (oy + ys * chh) / d, cs * (0.40 * its)[:, None])
        g = info.get("garland")
        if g is not None:
            ys, xs, a = g
            gc = np.array([255, 190, 70], np.float32)[None] * (0.35 * a)[:, None] * 0.2
            self._points(pts, (ox + xs * cw) / d, (oy + ys * chh) / d, gc)
        buf = self._halo + self._blur(pts, sig) * (2 * math.pi * sig * sig)
        st = info.get("star")
        if st is not None:
            y, x, p = st
            self._splat(buf, (ox + x * cw) / d, (oy + y * chh) / d, np.array([255, 200, 90]) * (0.55 * p), 5 * chh / d)
            self._splat(buf, (ox + x * cw) / d, (oy + y * chh) / d, np.array([255, 230, 160]) * (0.9 * p), 2.5 * chh / d)
        return np.clip(buf, 0, 255)


def message_cells(info, t):
    text = " ".join(MESSAGE)
    out = []
    for j, letter in enumerate(text[:info["letters"]]):
        if letter != " ":
            out.append((j, letter, MSG_COLORS[(j // 2) % 3] * (0.85 + 0.15 * math.sin(t * 2.4 + j * 0.5))))
    cursor = info["letters"] < len(text) and t >= T_MSG and int(t * 3) % 2 == 0
    return text, out, cursor


# ---------------------------------------------------------------- window (pygame / pygame-ce)
def run_window(full=False):
    import pygame
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    pygame.init()
    pygame.display.set_caption("ASCII Christmas Tree")
    names = "consolas,menlo,dejavusansmono,couriernew,monospace"
    W, H = pygame.display.get_desktop_sizes()[0]
    st = {}

    def layout(fullscreen):
        if fullscreen:
            # smaller font, more rows -> big detailed tree (~90 rows on a 1080p screen)
            px = 20
            while px > 8:
                font = pygame.font.SysFont(names, px, bold=True)
                if H / font.get_linesize() >= 88:
                    break
                px -= 1
            cw, chh = font.size("M")[0], font.get_linesize()
            rows, cols = H // chh, W // cw
            screen = pygame.display.set_mode((W, H), pygame.FULLSCREEN)
            off = ((W - cols * cw) // 2, (H - rows * chh) // 2)
            pygame.mouse.set_visible(False)
        else:
            px = 16
            while True:
                font = pygame.font.SysFont(names, px, bold=True)
                cw, chh = font.size("M")[0], font.get_linesize()
                if (ROWS * chh <= H * 0.88 and COLS * cw <= W * 0.95) or px <= 8:
                    break
                px -= 1
            rows, cols = ROWS, COLS
            screen = pygame.display.set_mode((cols * cw, rows * chh))
            off = (0, 0)
            pygame.mouse.set_visible(True)
        sw, sh = screen.get_size()
        ky = 5.0 * rows / 74
        mfont = pygame.font.SysFont(names, max(16, int(chh * 2.6)), bold=True)
        st.update(font=font, cw=cw, chh=chh, screen=screen, off=off, ky=ky, kx=ky * chh / cw, rows=rows, cols=cols,
                  tree=Tree(cols, rows), cache={}, glow=Glow(sw, sh, cw, chh), sw=sw, sh=sh, mfont=mfont,
                  mcw=mfont.size("M")[0], small=pygame.font.SysFont(names, 14), full=fullscreen, glow_big=None)

    def glyph(ci, r, g, b):
        key = (ci, r >> 3, g >> 3, b >> 3)
        sfc = st["cache"].get(key)
        if sfc is None:
            sfc = st["cache"][key] = st["font"].render(CHARS[ci], True, (r, g, b))
        return sfc

    layout(full)
    clock = pygame.time.Clock()
    t, paused, show, glow_on, last, frame_no = 0.0, False, False, True, time.time(), 0
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit(); return
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_SPACE: paused = not paused
                elif e.key == pygame.K_r: t = 0.0
                elif e.key == pygame.K_h: show = not show
                elif e.key == pygame.K_g: glow_on = not glow_on
                elif e.key in (pygame.K_f, pygame.K_F11): layout(not st["full"])
                elif e.key == pygame.K_s:
                    n = time.strftime("tree_%H%M%S.png"); pygame.image.save(st["screen"], n); print("saved", n)
        now = time.time()
        if not paused:
            t += min(now - last, 0.1)
        last = now
        cols = st["cols"]
        ch, col, inf = st["tree"].frame(t, st["kx"], st["ky"])
        screen, cw, chh, (ox, oy) = st["screen"], st["cw"], st["chh"], st["off"]
        screen.fill(SKY)
        if glow_on:
            frame_no += 1
            if frame_no % 2 == 1 or st.get("glow_big") is None:      # the soft light changes slowly: refresh every 2nd frame
                g = st["glow"]
                small = pygame.surfarray.make_surface(g.build(inf, st["off"]).astype(np.uint8))
                st["glow_big"] = pygame.transform.smoothscale(small, (g.gw * g.down, g.gh * g.down))
            screen.blit(st["glow_big"], (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        nz = np.flatnonzero(ch)
        colsv = col[nz].astype(np.int32).tolist()
        screen.blits([(glyph(ci, *rgb), (ox + (i % cols) * cw, oy + (i // cols) * chh))
                      for i, ci, rgb in zip(nz.tolist(), ch[nz].tolist(), colsv)], doreturn=False)
        text, letters, cursor = message_cells(inf, t)
        mf, mcw = st["mfont"], st["mcw"]
        mx0 = (st["sw"] - len(text) * mcw) // 2
        my = oy + (st["rows"] - int(round(4.2 * st["rows"] / 74))) * chh
        for j, letter, c in letters:
            screen.blit(mf.render(letter, True, tuple(int(v) for v in c)), (mx0 + j * mcw, my))
        if cursor:
            screen.blit(mf.render("_", True, (230, 230, 230)), (mx0 + inf["letters"] * mcw, my))
        if show:
            screen.blit(st["small"].render(f"t {t:5.1f}s  rotation {inf['rotation']:5.1f}°  lights {inf['lights']}  "
                                           f"grid {cols}x{st['rows']}  fps {clock.get_fps():4.1f}", True, (120, 130, 150)), (8, 6))
        pygame.display.flip()
        clock.tick(FPS)


# ---------------------------------------------------------------- frames without a window (preview / video)
def render_frames(out_dir, seconds, font_path, step=1, size=None, fps=FPS):
    """size=None -> window grid; size=(W,H) -> fullscreen-style dense grid on a W x H canvas."""
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(out_dir, exist_ok=True)
    if size:
        W, H = size
        px = 20
        while px > 8:
            font = ImageFont.truetype(font_path, px)
            chh = int(px * 1.2)
            if H / chh >= 88:
                break
            px -= 1
        cw = int(round(font.getlength("M")))
        rows, cols = H // chh, W // cw
        off = ((W - cols * cw) // 2, (H - rows * chh) // 2)
    else:
        font = ImageFont.truetype(font_path, 14); cw, chh = int(round(font.getlength("M"))), 17
        rows, cols = ROWS, COLS; W, H = cols * cw, rows * chh; off = (0, 0)
    mfont = ImageFont.truetype(font_path, max(16, int(chh * 2.6))); mcw = int(round(mfont.getlength("M")))
    tree = Tree(cols, rows)
    glow = Glow(W, H, cw, chh)
    ky = 5.0 * rows / 74; kx = ky * chh / cw
    for f in range(0, int(seconds * fps), step):
        t = f / fps
        ch, col, inf = tree.frame(t, kx, ky)
        g = glow.build(inf, off)
        gimg = Image.fromarray(g.transpose(1, 0, 2).astype(np.uint8)).resize((glow.gw * glow.down, glow.gh * glow.down),
                                                                              Image.BILINEAR).crop((0, 0, W, H))
        base = np.array(gimg, np.int32) + np.array(SKY)
        im = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        for i in np.flatnonzero(ch):
            d.text((off[0] + (i % cols) * cw, off[1] + (i // cols) * chh), CHARS[ch[i]],
                   fill=tuple(int(v) for v in col[i]), font=font)
        text, letters, cursor = message_cells(inf, t)
        mx0 = (W - len(text) * mcw) // 2; my = off[1] + (rows - int(round(4.2 * rows / 74))) * chh
        for j, letter, c in letters:
            d.text((mx0 + j * mcw, my), letter, fill=tuple(int(v) for v in c), font=mfont)
        im.save(os.path.join(out_dir, f"f{f:05d}.png"))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--frames":
        sz = tuple(int(v) for v in sys.argv[6].split("x")) if len(sys.argv) > 6 else None
        render_frames(sys.argv[2], float(sys.argv[3]), sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 1, sz)
    else:
        run_window(full="--full" in sys.argv)

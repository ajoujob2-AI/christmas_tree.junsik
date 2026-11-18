"""ASCII Christmas department store scene.

The tree is imported directly from ``christmas_tree.py`` so its geometry,
rotation, lights, ornaments, presents and timing stay exactly the same.  This
file adds a grand, warmly lit department-store facade behind it.

Run:   python christmas_department_store.py
       python christmas_department_store.py --full
       python christmas_department_store.py --still preview.png 10 1920x1080

Keys:  Space pause · R restart · S screenshot · H info · F/F11 fullscreen
       G glow on/off · Esc quit
"""
from __future__ import annotations

import math
import os
import sys
import time

import numpy as np

import christmas_tree as tree_art


TITLE = "CHRISTMAS AT THE DEPARTMENT STORE"
STONE = np.array([126, 112, 100], dtype=float)
STONE_LIT = np.array([188, 161, 124], dtype=float)
STONE_DARK = np.array([62, 61, 70], dtype=float)
GOLD = np.array([244, 191, 78], dtype=float)
WINDOW = np.array([255, 180, 70], dtype=float)
WINDOW_PALE = np.array([255, 225, 154], dtype=float)
EVERGREEN = np.array([44, 128, 69], dtype=float)
RED = np.array([220, 46, 52], dtype=float)


class DepartmentFacade:
    """A scalable ASCII facade cached for one text-grid size."""

    def __init__(self, cols: int, rows: int, seed: int = 27):
        self.cols, self.rows = cols, rows
        self.scale = rows / 74.0
        self.rng = np.random.default_rng(seed)
        self.ch = np.zeros(rows * cols, np.int32)
        self.col = np.zeros((rows * cols, 3), np.float32)
        self.window_cells: list[tuple[int, int, float]] = []
        self.bulb_cells: list[tuple[int, int, float]] = []
        self._build()

    def put(self, r: int, c: int, glyph: str, color, strength: float = 1.0):
        if 0 <= r < self.rows and 0 <= c < self.cols:
            i = r * self.cols + c
            self.ch[i] = tree_art.CI.get(glyph, tree_art.CI["."])
            self.col[i] = np.asarray(color) * strength

    def line(self, r: int, c0: int, c1: int, glyph: str, color, strength: float = 1.0):
        for c in range(max(0, c0), min(self.cols, c1 + 1)):
            self.put(r, c, glyph, color, strength)

    def text(self, r: int, c: int, text: str, color):
        for j, glyph in enumerate(text):
            if glyph != " ":
                self.put(r, c + j, glyph if glyph in tree_art.CI else "#", color)

    def _window(self, top: int, left: int, w: int, h: int, phase: float):
        # Carved stone surround and a warm, cross-divided display window.
        self.line(top - 1, left - 1, left + w, "_", STONE_LIT, 0.78)
        self.line(top + h, left - 1, left + w, "=", STONE_DARK, 0.95)
        for r in range(top, top + h):
            self.put(r, left - 1, "|", STONE_LIT, 0.72)
            self.put(r, left + w, "|", STONE_DARK, 0.9)
            for c in range(left, left + w):
                edge = min(r - top, top + h - 1 - r, c - left, left + w - 1 - c)
                glyph = ":" if edge == 0 else "."
                shade = 0.58 + 0.18 * ((r + c) % 3 == 0)
                self.put(r, c, glyph, WINDOW, shade)
                self.window_cells.append((r, c, phase))
        midc, midr = left + w // 2, top + h // 2
        for r in range(top, top + h):
            self.put(r, midc, "|", GOLD, 0.68)
        self.line(midr, left, left + w - 1, "-", GOLD, 0.65)

        # Small wreath centered in each upper pane.
        if w >= 5 and h >= 5:
            for dr, dc, g in ((-1, 0, "o"), (0, -1, "o"), (0, 1, "o"), (1, 0, "o")):
                self.put(midr + dr - 1, midc + dc, g, EVERGREEN, 0.95)
            self.put(midr, midc, "x", RED, 1.0)

    def _build(self):
        s, cols, rows = self.scale, self.cols, self.rows
        top = max(8, int(round(18 * s)))
        ground = rows - int(round(12 * s))
        left, right = max(1, int(round(2 * s))), cols - max(2, int(round(3 * s)))

        # Roof silhouette, stepped crown and cornices.
        crown_l, crown_r = int(cols * 0.33), int(cols * 0.67)
        self.line(top - 5, crown_l, crown_r, "_", STONE_LIT, 0.58)
        self.line(top - 4, crown_l - 2, crown_r + 2, "=", STONE, 0.76)
        self.line(top - 2, left + 2, right - 2, "_", STONE_LIT, 0.74)
        self.line(top - 1, left, right, "=", STONE_LIT, 0.92)
        self.line(top, left, right, "#", STONE, 0.92)
        self.line(top + 2, left, right, "-", GOLD, 0.82)

        # Main limestone body with a restrained stipple texture.
        for r in range(top + 1, ground + 1):
            for c in range(left, right + 1):
                edge = min(c - left, right - c)
                if edge <= 1:
                    self.put(r, c, "|" if edge == 0 else ":", STONE_LIT if c < cols / 2 else STONE_DARK, 0.78)
                elif self.rng.random() < 0.085:
                    glyph = "." if (r + c) % 3 else ":"
                    light = 0.45 + 0.18 * (1 - (r - top) / max(1, ground - top))
                    self.put(r, c, glyph, STONE, light)

        # Vertical pilasters frame the side wings and central entrance.
        pilasters = [left + 2, int(cols * .27), int(cols * .36), int(cols * .64), int(cols * .73), right - 2]
        for c in pilasters:
            self.line(top + 1, c - 1, c + 1, "_", STONE_LIT, 0.68)
            for r in range(top + 2, ground):
                self.put(r, c - 1, ":", STONE, 0.62)
                self.put(r, c, "|", STONE_LIT, 0.72)
                self.put(r, c + 1, ":", STONE_DARK, 0.82)
            self.line(ground - 1, c - 2, c + 2, "=", STONE_LIT, 0.7)

        # Three levels of windows on both wings. Scale carefully on smaller grids.
        wh = max(4, int(round(5 * s)))
        ww = max(4, int(round(5 * s)))
        row_gap = max(7, int(round(9 * s)))
        first_row = top + max(5, int(round(6 * s)))
        wing_centres = [int(cols * x) for x in (.095, .19, .29, .71, .81, .905)]
        phase = 0.0
        for floor in range(3):
            wr = first_row + floor * row_gap
            if wr + wh >= ground:
                break
            for wc in wing_centres:
                self._window(wr, wc - ww // 2, ww, wh, phase)
                phase += 0.53

        # Central pediment and a tall glass entrance, mostly glimpsed around the tree.
        mid = cols // 2
        ent_w = max(15, int(round(20 * s)))
        ent_l, ent_r = mid - ent_w // 2, mid + ent_w // 2
        ped = top + max(3, int(round(4 * s)))
        for k in range(max(3, int(5 * s))):
            self.line(ped + k, ent_l + k, ent_r - k, "=" if k == 0 else "-", STONE_LIT, 0.68)
        sign = "GRAND STORE"
        self.text(ped + max(2, int(3 * s)), mid - len(sign) // 2, sign, GOLD * 0.82)
        door_top = ground - max(18, int(round(21 * s)))
        for c in (ent_l, mid, ent_r):
            for r in range(door_top, ground):
                self.put(r, c, "|", GOLD, 0.62)
        self.line(door_top, ent_l, ent_r, "_", GOLD, 0.72)
        for r in range(door_top + 1, ground):
            for c in range(ent_l + 1, ent_r):
                if c == mid:
                    continue
                if (r + c) % 3 == 0:
                    self.put(r, c, ".", WINDOW_PALE, 0.48)
                    self.window_cells.append((r, c, 1.7))

        # Evergreen garland and red/gold bulbs along the main cornice.
        gar_r = top + 3
        for c in range(left + 2, right - 1):
            wave = int(round(1.3 * s * abs(math.sin((c - left) * math.pi / max(7, 10 * s)))))
            r = gar_r + wave
            self.put(r, c, "~" if c % 2 else "*", EVERGREEN, 0.9)
            if c % max(4, int(round(5 * s))) == 0:
                self.put(r, c, "o", RED if (c // 5) % 2 else GOLD, 1.0)
                self.bulb_cells.append((r, c, c * 0.21))

        # Stone base and snowy ledges.
        self.line(ground, left, right, "=", STONE_LIT, 0.72)
        self.line(ground + 1, left - 1, right + 1, "_", np.array([184, 197, 218]), 0.72)
        self.top, self.ground, self.left, self.right = top, ground, left, right

    def frame(self, t: float):
        ch = self.ch.copy()
        col = self.col.copy()
        # Quiet breathing window light; stable enough for presentation/video.
        for r, c, phase in self.window_cells:
            i = r * self.cols + c
            pulse = 0.88 + 0.12 * math.sin(t * 0.72 + phase)
            if ch[i]:
                col[i] *= pulse
        glow_rows, glow_cols, glow_colors, glow_intensities = [], [], [], []
        for r, c, phase in self.bulb_cells:
            i = r * self.cols + c
            pulse = 0.72 + 0.28 * math.sin(t * 1.8 + phase)
            col[i] *= pulse
            glow_rows.append(r); glow_cols.append(c)
            glow_colors.append(col[i]); glow_intensities.append(pulse * 0.34)
        return ch, col, (np.asarray(glow_rows), np.asarray(glow_cols),
                         np.asarray(glow_colors), np.asarray(glow_intensities))


class DepartmentChristmasScene:
    def __init__(self, cols: int, rows: int):
        self.cols, self.rows = cols, rows
        self.tree = tree_art.Tree(cols, rows)
        self.facade = DepartmentFacade(cols, rows)

    def frame(self, t: float, kx: float, ky: float):
        tree_ch, tree_col, info = self.tree.frame(t, kx, ky)
        build_ch, build_col, bglow = self.facade.frame(t)
        ch, col = build_ch, build_col

        # The exact original tree is placed in front. Its triangular silhouette
        # also preserves the original snow and sparkle immediately around it.
        tb = info.get("tree_box")
        if tb:
            top, ground, cx, half = tb
            rr, cc = np.indices((self.rows, self.cols))
            f = np.clip((rr - top) / max(1.0, ground - top), 0, 1)
            tree_half = 2.5 + half * (0.16 + 0.92 * f)
            front = (rr >= top - 5 * self.facade.scale) & (rr <= ground + 3 * self.facade.scale) & (np.abs(cc - cx) <= tree_half)
            front = front.ravel() & (tree_ch != 0)
        else:
            front = tree_ch != 0
        # Keep original foreground snow everywhere beneath the building base.
        ground_mask = np.repeat(np.arange(self.rows)[:, None] > self.facade.ground, self.cols, axis=1).ravel()
        front |= ground_mask & (tree_ch != 0)
        ch[front], col[front] = tree_ch[front], tree_col[front]

        # Merge facade bulbs with the original tree lights for one glow layer.
        br, bc, bcols, bits = bglow
        lp = info.get("light_pts")
        if len(br):
            if lp is None:
                info["light_pts"] = (br, bc, bcols, bits)
            else:
                info["light_pts"] = (np.concatenate([lp[0], br]), np.concatenate([lp[1], bc]),
                                     np.concatenate([lp[2], bcols]), np.concatenate([lp[3], bits]))
        return ch, col, info


def _message_cells(info, t):
    # Keep the original MERRY CHRISTMAS typing animation.
    return tree_art.message_cells(info, t)


def run_window(full=False):
    import pygame
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    pygame.init()
    pygame.display.set_caption("ASCII Christmas Department Store")
    names = "consolas,menlo,dejavusansmono,couriernew,monospace"
    desktop_w, desktop_h = pygame.display.get_desktop_sizes()[0]
    state = {}

    def layout(fullscreen):
        if fullscreen:
            px = 20
            while px > 8:
                font = pygame.font.SysFont(names, px, bold=True)
                if desktop_h / font.get_linesize() >= 88:
                    break
                px -= 1
            cw, chh = font.size("M")[0], font.get_linesize()
            rows, cols = desktop_h // chh, desktop_w // cw
            screen = pygame.display.set_mode((desktop_w, desktop_h), pygame.FULLSCREEN)
            off = ((desktop_w - cols * cw) // 2, (desktop_h - rows * chh) // 2)
            pygame.mouse.set_visible(False)
        else:
            rows, cols, px = tree_art.ROWS, 132, 14
            while px > 8:
                font = pygame.font.SysFont(names, px, bold=True)
                cw, chh = font.size("M")[0], font.get_linesize()
                if rows * chh <= desktop_h * .88 and cols * cw <= desktop_w * .95:
                    break
                px -= 1
            screen = pygame.display.set_mode((cols * cw, rows * chh))
            off = (0, 0)
            pygame.mouse.set_visible(True)
        sw, sh = screen.get_size()
        ky = 5.0 * rows / 74
        mfont = pygame.font.SysFont(names, max(16, int(chh * 2.6)), bold=True)
        state.update(font=font, cw=cw, chh=chh, screen=screen, off=off, ky=ky,
                     kx=ky * chh / cw, rows=rows, cols=cols,
                     scene=DepartmentChristmasScene(cols, rows), cache={},
                     glow=tree_art.Glow(sw, sh, cw, chh), sw=sw, sh=sh,
                     mfont=mfont, mcw=mfont.size("M")[0],
                     small=pygame.font.SysFont(names, 14), full=fullscreen, glow_big=None)

    def glyph(ci, r, g, b):
        key = (ci, r >> 3, g >> 3, b >> 3)
        surface = state["cache"].get(key)
        if surface is None:
            surface = state["cache"][key] = state["font"].render(tree_art.CHARS[ci], True, (r, g, b))
        return surface

    layout(full)
    clock = pygame.time.Clock()
    t, paused, show, glow_on, last, frame_no = 0.0, False, False, True, time.time(), 0
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.quit(); return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE: paused = not paused
                elif event.key == pygame.K_r: t = 0.0
                elif event.key == pygame.K_h: show = not show
                elif event.key == pygame.K_g: glow_on = not glow_on
                elif event.key in (pygame.K_f, pygame.K_F11): layout(not state["full"])
                elif event.key == pygame.K_s:
                    name = time.strftime("department_store_%H%M%S.png")
                    pygame.image.save(state["screen"], name); print("saved", name)
        now = time.time()
        if not paused: t += min(now - last, .1)
        last = now
        chars, colors, info = state["scene"].frame(t, state["kx"], state["ky"])
        screen, cw, chh, (ox, oy) = state["screen"], state["cw"], state["chh"], state["off"]
        screen.fill(tree_art.SKY)
        if glow_on:
            frame_no += 1
            if frame_no % 2 == 1 or state.get("glow_big") is None:
                glow = state["glow"]
                small = pygame.surfarray.make_surface(glow.build(info, state["off"]).astype(np.uint8))
                state["glow_big"] = pygame.transform.smoothscale(small, (glow.gw * glow.down, glow.gh * glow.down))
            screen.blit(state["glow_big"], (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        nz = np.flatnonzero(chars)
        rgbs = colors[nz].astype(np.int32).tolist()
        screen.blits([(glyph(ci, *rgb), (ox + (i % state["cols"]) * cw, oy + (i // state["cols"]) * chh))
                      for i, ci, rgb in zip(nz.tolist(), chars[nz].tolist(), rgbs)], doreturn=False)
        text, letters, cursor = _message_cells(info, t)
        mx0 = (state["sw"] - len(text) * state["mcw"]) // 2
        my = oy + (state["rows"] - int(round(4.2 * state["rows"] / 74))) * chh
        for j, letter, color in letters:
            screen.blit(state["mfont"].render(letter, True, tuple(int(v) for v in color)), (mx0 + j * state["mcw"], my))
        if cursor:
            screen.blit(state["mfont"].render("_", True, (230, 230, 230)), (mx0 + info["letters"] * state["mcw"], my))
        if show:
            status = f"t {t:5.1f}s  rotation {info['rotation']:5.1f}°  lights {info['lights']}  grid {state['cols']}x{state['rows']}  fps {clock.get_fps():4.1f}"
            screen.blit(state["small"].render(status, True, (120, 130, 150)), (8, 6))
        pygame.display.flip()
        clock.tick(tree_art.FPS)


def render_still(path: str, t: float = 10.0, size=(1920, 1080), font_path=None):
    from PIL import Image, ImageDraw, ImageFont
    if font_path is None:
        font_path = "C:/Windows/Fonts/consolab.ttf"
    width, height = size
    px = 20
    while px > 8:
        font = ImageFont.truetype(font_path, px)
        chh = int(px * 1.2)
        if height / chh >= 88:
            break
        px -= 1
    cw = int(round(font.getlength("M")))
    rows, cols = height // chh, width // cw
    off = ((width - cols * cw) // 2, (height - rows * chh) // 2)
    mfont = ImageFont.truetype(font_path, max(16, int(chh * 2.6)))
    mcw = int(round(mfont.getlength("M")))
    scene = DepartmentChristmasScene(cols, rows)
    ky = 5.0 * rows / 74; kx = ky * chh / cw
    chars, colors, info = scene.frame(t, kx, ky)
    glow = tree_art.Glow(width, height, cw, chh)
    g = glow.build(info, off)
    gimg = Image.fromarray(g.transpose(1, 0, 2).astype(np.uint8)).resize(
        (glow.gw * glow.down, glow.gh * glow.down), Image.Resampling.BILINEAR).crop((0, 0, width, height))
    base = np.array(gimg, np.int32) + np.array(tree_art.SKY)
    image = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(image)
    for i in np.flatnonzero(chars):
        draw.text((off[0] + (i % cols) * cw, off[1] + (i // cols) * chh), tree_art.CHARS[chars[i]],
                  fill=tuple(int(v) for v in colors[i]), font=font)
    text, letters, cursor = _message_cells(info, t)
    mx0 = (width - len(text) * mcw) // 2
    my = off[1] + (rows - int(round(4.2 * rows / 74))) * chh
    for j, letter, color in letters:
        draw.text((mx0 + j * mcw, my), letter, fill=tuple(int(v) for v in color), font=mfont)
    if cursor:
        draw.text((mx0 + info["letters"] * mcw, my), "_", fill=(230, 230, 230), font=mfont)
    image.save(path)
    print("saved", path)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--still":
        output = sys.argv[2] if len(sys.argv) > 2 else "department_store_preview.png"
        at = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
        size = tuple(int(v) for v in sys.argv[4].lower().split("x")) if len(sys.argv) > 4 else (1920, 1080)
        render_still(output, at, size)
    else:
        run_window(full="--full" in sys.argv)

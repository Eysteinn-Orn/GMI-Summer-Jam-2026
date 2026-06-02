#!/usr/bin/env python3
"""Pixel art editor for the GMI Summer Jam vampire game.

A self-contained tkinter pixel editor that reads and writes PNG sprites in the
project's conventional Godot sprite folder (res://Assets/sprites/). PNGs are the
format Godot imports as Texture2D, so anything saved here is usable directly by
Sprite2D / AnimatedSprite2D / AtlasTexture.

Run with:  python3 tools/pixel_editor.py

Features: pencil / flood-fill / eyedropper / line / rectangle tools, an erase
mode (any tool draws transparent), lasso or box copy/move selections, editable
palette + colour picker, zoom + pixel grid, transparency, undo/redo, animation
frames with onion-skinning, single-frame PNG save and horizontal spritesheet
export.

No third-party dependency is required: Pillow is used when present, otherwise a
small stdlib (zlib) PNG codec is used so every teammate can run it as-is.
"""

import colorsys
import json
import os
import re
import struct
import subprocess
import threading
import zlib
import tkinter as tk
from tkinter import filedialog, messagebox


# ---------------------------------------------------------------------------
# PNG I/O. Pillow when available, otherwise a minimal stdlib RGBA codec.
# ---------------------------------------------------------------------------

def _stdlib_save_png(path, w, h, pixels):
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter type 0 (None)
        row = y * w
        for x in range(w):
            r, g, b, a = pixels[row + x]
            raw += bytes((r, g, b, a))

    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


def _stdlib_load_png(path):
    with open(path, "rb") as f:
        data = f.read()
    sig = b"\x89PNG\r\n\x1a\n"
    if data[:8] != sig:
        raise ValueError("not a PNG file")
    i, idat, plte, trns = 8, bytearray(), None, None
    w = h = depth = color = 0
    while i < len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + ln]
        i += 12 + ln
        if typ == b"IHDR":
            w, h, depth, color = (*struct.unpack(">IIBB", body[:10]),)[:4]
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
    if depth != 8:
        raise ValueError("only 8-bit PNGs are supported by the fallback codec")
    chan = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    raw = zlib.decompress(bytes(idat))
    stride = w * chan
    out = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(h):
        ft = raw[pos]; pos += 1
        line = bytearray(raw[pos:pos + stride]); pos += stride
        for x in range(stride):
            a = line[x - chan] if x >= chan else 0
            b = prev[x]
            c = prev[x - chan] if x >= chan else 0
            if ft == 1:
                line[x] = (line[x] + a) & 0xff
            elif ft == 2:
                line[x] = (line[x] + b) & 0xff
            elif ft == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 0xff
            elif ft == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 0xff
        prev = line
        for x in range(w):
            s = x * chan
            if color == 6:
                out.append([line[s], line[s + 1], line[s + 2], line[s + 3]])
            elif color == 2:
                out.append([line[s], line[s + 1], line[s + 2], 255])
            elif color == 4:
                out.append([line[s], line[s], line[s], line[s + 1]])
            elif color == 0:
                out.append([line[s], line[s], line[s], 255])
            elif color == 3:
                idx = line[s]
                out.append([plte[idx * 3], plte[idx * 3 + 1], plte[idx * 3 + 2],
                            trns[idx] if trns and idx < len(trns) else 255])
    return w, h, out


def save_png(path, w, h, pixels):
    try:
        from PIL import Image
        img = Image.new("RGBA", (w, h))
        img.putdata([tuple(p) for p in pixels])
        img.save(path)
    except ImportError:
        _stdlib_save_png(path, w, h, pixels)


def load_png(path):
    try:
        from PIL import Image
        img = Image.open(path).convert("RGBA")
        w, h = img.size
        return w, h, [list(p) for p in img.getdata()]
    except ImportError:
        return _stdlib_load_png(path)


# ---------------------------------------------------------------------------
# Project layout helpers.
# ---------------------------------------------------------------------------

def find_sprites_dir():
    """Walk up from this file to the Godot project root, return Assets/sprites."""
    here = os.path.dirname(os.path.abspath(__file__))
    root = here
    while root != os.path.dirname(root):
        if os.path.exists(os.path.join(root, "project.godot")):
            break
        root = os.path.dirname(root)
    sprites = os.path.join(root, "Assets", "sprites")
    os.makedirs(sprites, exist_ok=True)
    return sprites


TRANSPARENT = [0, 0, 0, 0]

DEFAULT_PALETTE = [
    "#000000", "#1a1c2c", "#3b3f5c", "#5d5f8c", "#8b8fb5", "#c2c3d6", "#ffffff",
    "#7a2233", "#b13e53", "#ef476f", "#ff7676", "#ffcd75",
    "#ffd700", "#e8a02c", "#6b3e2e",
    "#1b5e57", "#38b764", "#a7f070", "#3b8bd6", "#41a6f6",
    "#6d2f8f", "#a24bc2", "#d77bba",
]

PALETTE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "palette.json")


def load_palette():
    try:
        with open(PALETTE_FILE) as f:
            saved = json.load(f)
        if isinstance(saved, list) and all(isinstance(c, str) for c in saved):
            return saved
    except (OSError, ValueError):
        pass
    return list(DEFAULT_PALETTE)


def save_palette(palette):
    try:
        with open(PALETTE_FILE, "w") as f:
            json.dump(palette, f)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Geometry for the lasso selection.
# ---------------------------------------------------------------------------

def convex_hull(points):
    """Andrew's monotone chain — returns the hull vertices of `points` in order."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def point_in_hull(hull, x, y):
    """True if (x, y) lies inside or on the convex polygon `hull`."""
    sign = 0
    for i in range(len(hull)):
        ax, ay = hull[i]
        bx, by = hull[(i + 1) % len(hull)]
        d = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        if d != 0:
            s = 1 if d > 0 else -1
            if sign and s != sign:
                return False
            sign = s
    return True


# ---------------------------------------------------------------------------
# Pixel-buffer transforms (rotate / flip / scale / perspective warp).
# ---------------------------------------------------------------------------

def rotate_cw(w, h, pixels):
    nw, nh = h, w
    out = [None] * (nw * nh)
    for y in range(h):
        for x in range(w):
            out[x * nw + (h - 1 - y)] = list(pixels[y * w + x])
    return nw, nh, out


def rotate_ccw(w, h, pixels):
    nw, nh = h, w
    out = [None] * (nw * nh)
    for y in range(h):
        for x in range(w):
            out[(w - 1 - x) * nw + y] = list(pixels[y * w + x])
    return nw, nh, out


def flip_h(w, h, pixels):
    out = [None] * (w * h)
    for y in range(h):
        for x in range(w):
            out[y * w + (w - 1 - x)] = list(pixels[y * w + x])
    return w, h, out


def flip_v(w, h, pixels):
    out = [None] * (w * h)
    for y in range(h):
        for x in range(w):
            out[(h - 1 - y) * w + x] = list(pixels[y * w + x])
    return w, h, out


def scale_nn(w, h, pixels, nw, nh):
    out = [None] * (nw * nh)
    for ny in range(nh):
        sy = min(ny * h // nh, h - 1)
        for nx in range(nw):
            sx = min(nx * w // nw, w - 1)
            out[ny * nw + nx] = list(pixels[sy * w + sx])
    return nw, nh, out


def solve_homography(src_pts, dst_pts):
    """8-point DLT: coefficients mapping dst->src for an inverse perspective warp."""
    rows, rhs = [], []
    for (sx, sy), (dx, dy) in zip(src_pts, dst_pts):
        rows.append([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy])
        rhs.append(sx)
        rows.append([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy])
        rhs.append(sy)
    n = 8
    M = [rows[i][:] + [rhs[i]] for i in range(n)]
    for col in range(n):
        best = max(range(col, n), key=lambda r: abs(M[r][col]))
        M[col], M[best] = M[best], M[col]
        if abs(M[col][col]) < 1e-12:
            return None
        for row in range(n):
            if row != col:
                fac = M[row][col] / M[col][col]
                for j in range(n + 1):
                    M[row][j] -= fac * M[col][j]
    return tuple(M[i][n] / M[i][i] for i in range(n))


def perspective_warp(sw, sh, src_pixels, dst_corners):
    """Warp an sw*sh pixel buffer into the quadrilateral dst_corners (TL/TR/BR/BL).
    Corners use inclusive pixel-index coordinates.
    Returns (ow, oh, out_pixels, ox, oy)."""
    src_pts = [(0, 0), (sw - 1, 0), (sw - 1, sh - 1), (0, sh - 1)]
    xs = [p[0] for p in dst_corners]
    ys = [p[1] for p in dst_corners]
    ox, oy = int(min(xs)), int(min(ys))
    ow = int(max(xs)) - ox + 1
    oh = int(max(ys)) - oy + 1
    coeffs = solve_homography(src_pts, dst_corners)
    if not coeffs:
        return sw, sh, [list(p) for p in src_pixels], 0, 0
    a, b, c, d, e, f, g, h = coeffs
    out = [list(TRANSPARENT)] * (ow * oh)
    SS = 3
    for py in range(oh):
        for px in range(ow):
            r_acc, g_acc, b_acc, a_acc, count = 0, 0, 0, 0, 0
            for sj in range(SS):
                for si in range(SS):
                    dx = px + ox + (si + 0.5) / SS - 0.5
                    dy = py + oy + (sj + 0.5) / SS - 0.5
                    den = g * dx + h * dy + 1
                    if abs(den) < 1e-12:
                        continue
                    sx_f = (a * dx + b * dy + c) / den
                    sy_f = (d * dx + e * dy + f) / den
                    ix = max(0, min(sw - 1, int(sx_f + 0.5)))
                    iy = max(0, min(sh - 1, int(sy_f + 0.5)))
                    if -0.5 <= sx_f <= sw - 0.5 and -0.5 <= sy_f <= sh - 0.5:
                        sp = src_pixels[iy * sw + ix]
                        r_acc += sp[0]; g_acc += sp[1]
                        b_acc += sp[2]; a_acc += sp[3]
                        count += 1
            if count > 0:
                out[py * ow + px] = [
                    r_acc // count, g_acc // count,
                    b_acc // count, a_acc // count]
    return ow, oh, out, ox, oy


# Runs in a subprocess so GLib.MainLoop + DBusGMainLoop work without threading
# context issues.  Prints '#rrggbb' on success, nothing on cancel/error.
_PORTAL_PICK_SCRIPT = """\
import dbus, sys
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
loop = GLib.MainLoop()
bus = dbus.SessionBus()
portal = dbus.Interface(
    bus.get_object("org.freedesktop.portal.Desktop",
                   "/org/freedesktop/portal/desktop"),
    "org.freedesktop.portal.Screenshot")
req_path = portal.PickColor("", dbus.Dictionary({}, signature="sv"))
req = dbus.Interface(
    bus.get_object("org.freedesktop.portal.Desktop", req_path),
    "org.freedesktop.portal.Request")
def cb(response, results):
    if response == 0 and "color" in results:
        r, g, b = (round(float(c) * 255) for c in results["color"])
        print(f"#{r:02x}{g:02x}{b:02x}")
    loop.quit()
req.connect_to_signal("Response", cb)
GLib.timeout_add(120_000, loop.quit)
loop.run()
"""

# ---------------------------------------------------------------------------
# Editor.
# ---------------------------------------------------------------------------

class PixelEditor:
    CHECK_LIGHT = "#d4d4d4"
    CHECK_DARK = "#bdbdbd"
    MAX_DIM = 256
    BAR_W = 224
    BAR_H = 18
    PAL_COLS = 8
    SWATCH = BAR_W // PAL_COLS

    def __init__(self, root):
        self.root = root
        self._tk = root.winfo_toplevel()
        self.active = True

        self.sprites_dir = find_sprites_dir()
        self.path = None  # current file path, if saved/opened

        self.w, self.h = 32, 32
        self.zoom = 14
        self.show_grid = True
        self.onion = False

        # Animation frames: each frame is a flat list of [r,g,b,a].
        self.frames = [self.blank_frame()]
        self.frame = 0

        self.color = [177, 62, 83, 255]  # #b13e53
        self.hsv_vals = {"H": 0.0, "S": 0.0, "V": 0.0, "A": 1.0}  # 0..1 each
        self.tool = tk.StringVar(value="pencil")

        self.undo_stack = []
        self.redo_stack = []
        self._img_base = None   # 1:1 PhotoImage (w x h)
        self._img_zoomed = None # zoomed PhotoImage (w*z x h*z)
        self._img_id = None     # canvas item id for the image
        self._grid_ids = []     # canvas item ids for grid lines
        self._rezoom_pending = False
        self.last_px = None    # last painted pixel during a drag
        self.stroke_start = None
        self.stroke_backup = None  # snapshot for live shape preview

        # Floating copy/move selection: {x, y, w, h, buf, mode, hull} or None.
        self.sel = None
        self.cm_grab = None          # cursor offset within a grabbed selection
        self.lasso_select = True     # True: trace a convex-hull region; False: box
        self.rubber = None           # (x0, y0, x1, y1) during a box-marquee drag
        self.lasso_pts = None        # traced points during a lasso drag
        self.sel_outline_id = None
        self.rubber_id = None
        self.resize_visible = False
        self.repeat_id = None  # pending after() for a held-down resize button
        self.panning = False   # dragging in the margin to pan the view
        self._pil_picking = False
        self.warp = None
        self.warp_handle_ids = []
        self.warp_active = None

        self.build_ui()
        self.rebuild_canvas()
        self.bind_keys()

    def blank_frame(self):
        return [list(TRANSPARENT) for _ in range(self.w * self.h)]

    @property
    def pixels(self):
        return self.frames[self.frame]

    # -- UI construction ----------------------------------------------------

    def build_ui(self):
        # tk's defaults give buttons a near-white focus-highlight border and a
        # light-gray pressed/hover background; recolour both to dark grays so
        # nothing flashes bright against the dark UI.
        for cls in ("Button", "Radiobutton"):
            self.root.option_add(f"*{cls}.highlightBackground", "#1a1a1a")
            self.root.option_add(f"*{cls}.highlightColor", "#1a1a1a")
            self.root.option_add(f"*{cls}.activeBackground", "#555555")
            self.root.option_add(f"*{cls}.activeForeground", "white")

        bar = tk.Frame(self.root, bg="#2b2b2b")
        bar.pack(side="top", fill="x")

        def btn(parent, text, cmd, **kw):
            b = tk.Button(parent, text=text, command=cmd, padx=6, pady=2,
                          bg="#3c3c3c", fg="white", relief="flat",
                          activebackground="#555", **kw)
            b.pack(side="left", padx=1, pady=2)
            return b

        btn(bar, "New", self.new_canvas)
        btn(bar, "Export Sheet", self.export_spritesheet)
        tk.Frame(bar, width=12, bg="#2b2b2b").pack(side="left")
        btn(bar, "Undo  U", self.undo)
        btn(bar, "Redo  Y", self.redo)
        tk.Frame(bar, width=12, bg="#2b2b2b").pack(side="left")
        btn(bar, "Zoom -", lambda: self.set_zoom(self.zoom - 2))
        btn(bar, "Zoom +", lambda: self.set_zoom(self.zoom + 2))
        self.grid_btn = btn(bar, "Grid: on", self.toggle_grid)
        self.onion_btn = btn(bar, "Onion: off", self.toggle_onion)
        self.select_btn = btn(bar, "Select: lasso", self.toggle_select_mode)

        self.status = tk.Label(bar, text="", bg="#2b2b2b", fg="#aaa")
        self.status.pack(side="right", padx=8)

        body = tk.Frame(self.root, bg="#1e1e1e")
        body.pack(side="top", fill="both", expand=True)

        # Tool column.
        tools = tk.Frame(body, bg="#2b2b2b")
        tools.pack(side="left", fill="y")
        for name, label in [("pencil", "Pencil  B"),
                            ("fill", "Fill  G"), ("picker", "Picker  Q"),
                            ("line", "Line  L"), ("rect", "Rect  R"),
                            ("rectfill", "Rect Fill  F"), ("copy", "Copy  C"),
                            ("move", "Move  M"), ("warp", "Warp  W")]:
            tk.Radiobutton(tools, text=label, value=name, variable=self.tool,
                           indicatoron=False, width=12, bg="#3c3c3c", fg="white",
                           selectcolor="#7a2233", relief="flat",
                           anchor="w", padx=6, pady=4).pack(fill="x", padx=3, pady=1)
        # Erase isn't a tool — it just makes the active colour transparent, so
        # whichever tool is selected (pencil, fill, line, rect) erases.
        tk.Button(tools, text="Erase  E", command=self.set_transparent, width=12,
                  bg="#3c3c3c", fg="white", relief="flat", anchor="w",
                  padx=6, pady=4).pack(fill="x", padx=3, pady=(6, 1))

        # Canvas resize controls, pinned to the end of the sidebar.
        self.build_resize_controls(tools)
        self.build_transform_controls(tools)

        # Canvas with scrollbars.
        center = tk.Frame(body, bg="#1e1e1e")
        center.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(center, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_hover)
        self.canvas.bind("<Button-3>", self.on_rmb_press)        # right = erase
        self.canvas.bind("<B3-Motion>", self.on_rmb_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_rmb_release)
        self.canvas.bind("<Button-2>", self.on_mmb_press)        # middle = pick
        self.canvas.bind("<B2-Motion>", self.on_mmb_drag)
        self.canvas.bind("<ButtonRelease-2>", lambda e: self.pan_end())
        self.canvas.bind("<MouseWheel>", self.on_wheel)          # wheel = zoom (Win/Mac)
        self.canvas.bind("<Button-4>", lambda e: self.set_zoom(self.zoom + 2, e))  # Linux up
        self.canvas.bind("<Button-5>", lambda e: self.set_zoom(self.zoom - 2, e))  # Linux down

        # Right column: colour + frames.
        right = tk.Frame(body, bg="#2b2b2b", width=self.BAR_W)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="COLOUR", bg="#2b2b2b", fg="#ccc").pack(pady=(8, 2))
        self.swatch = tk.Label(right, height=2, relief="solid", bd=1)
        self.swatch.pack(fill="x")

        # Type or paste a #rrggbb / #rrggbbaa (or shorthand #rgb) hex code.
        self.hex_var = tk.StringVar()
        self.hex_entry = tk.Entry(right, textvariable=self.hex_var, bg="#1e1e1e",
                                  fg="white", insertbackground="white", relief="flat",
                                  justify="center")
        self.hex_entry.pack(fill="x", pady=(2, 0))
        self.hex_entry.bind("<Return>", self.apply_hex_entry)
        self.hex_entry.bind("<FocusOut>", self.apply_hex_entry)

        self.pick_screen_btn = tk.Button(right, text="Pick Screen  P",
                  command=self.enter_screen_pick,
                  bg="#3c3c3c", fg="white", relief="flat",
                  padx=4, pady=2)
        self.pick_screen_btn.pack(fill="x", pady=(2, 0))

        # Hue / saturation / value spectrum bars; click or drag to choose.
        self.bar_canvas = {}
        self.bar_imgs = {}
        for ch in ("H", "S", "V", "A"):
            c = tk.Canvas(right, height=self.BAR_H, bg="#2b2b2b",
                          highlightthickness=0, cursor="sb_h_double_arrow")
            c.pack(fill="x", pady=2)
            c.bind("<Button-1>", lambda e, ch=ch: self.bar_set(ch, e))
            c.bind("<B1-Motion>", lambda e, ch=ch: self.bar_set(ch, e))
            self.bar_canvas[ch] = c

        self.palette_frame = tk.Frame(right, bg="#2b2b2b")
        self.palette_frame.pack(fill="x")
        self.palette = load_palette()
        self.render_palette()

        tk.Label(right, text="FRAMES", bg="#2b2b2b", fg="#ccc").pack(pady=(12, 2))
        self.frame_label = tk.Label(right, text="", bg="#2b2b2b", fg="#aaa")
        self.frame_label.pack()
        fnav = tk.Frame(right, bg="#2b2b2b")
        fnav.pack()
        for text, cmd in [("◀", lambda: self.goto_frame(self.frame - 1)),
                          ("▶", lambda: self.goto_frame(self.frame + 1))]:
            tk.Button(fnav, text=text, command=cmd, width=3, bg="#3c3c3c",
                      fg="white", relief="flat").pack(side="left", padx=1)
        fbtns = tk.Frame(right, bg="#2b2b2b")
        fbtns.pack(fill="x", padx=8, pady=1)
        for text, cmd in [("Add", self.add_frame), ("Dup", self.dup_frame),
                          ("Del", self.del_frame)]:
            tk.Button(fbtns, text=text, command=cmd, bg="#3c3c3c", fg="white",
                      relief="flat", width=4).pack(side="left", expand=True, fill="x", padx=1)

        # FILE: a save-name box sitting right above an always-open file list.
        tk.Label(right, text="FILE", bg="#2b2b2b", fg="#ccc").pack(pady=(12, 2))
        self.name_var = tk.StringVar()
        namerow = tk.Frame(right, bg="#2b2b2b")
        namerow.pack(fill="x")
        self.name_entry = tk.Entry(namerow, textvariable=self.name_var, bg="#1e1e1e",
                                   fg="white", insertbackground="white", relief="flat")
        self.name_entry.pack(side="left", fill="x", expand=True)
        tk.Label(namerow, text=".png", bg="#2b2b2b", fg="#888").pack(side="left")
        saverow = tk.Frame(right, bg="#2b2b2b")
        saverow.pack(fill="x")
        tk.Button(saverow, text="Save", command=self.save_current, bg="#3c3c3c",
                  fg="white", relief="flat", padx=4).pack(fill="x")

        files_wrap = tk.Frame(right, bg="#2b2b2b")
        files_wrap.pack(fill="both", expand=True, padx=6, pady=(4, 8))
        fsb = tk.Scrollbar(files_wrap, orient="vertical")
        self.file_list = tk.Listbox(files_wrap, bg="#1e1e1e", fg="white", relief="flat",
                                    highlightthickness=0, activestyle="none",
                                    selectbackground="#7a2233", yscrollcommand=fsb.set)
        fsb.configure(command=self.file_list.yview)
        fsb.pack(side="right", fill="y")
        self.file_list.pack(side="left", fill="both", expand=True)
        self.file_list.bind("<Double-Button-1>", self.on_file_open)
        self.refresh_file_list()

        self.set_color_hex(self.color_hex())  # sync sliders to the start colour
        self.update_frame_label()

    def build_resize_controls(self, parent):
        wrap = tk.Frame(parent, bg="#2b2b2b")
        wrap.pack(side="bottom", fill="x", pady=(8, 8))
        tk.Label(wrap, text="CANVAS", bg="#2b2b2b", fg="#ccc").pack()

        row = tk.Frame(wrap, bg="#2b2b2b")
        row.pack(pady=2)
        self.w_var = tk.StringVar(value=str(self.w))
        self.h_var = tk.StringVar(value=str(self.h))
        for var in (self.w_var, self.h_var):
            tk.Entry(row, textvariable=var, width=3, bg="#1e1e1e", fg="white",
                     insertbackground="white", relief="flat",
                     justify="center").pack(side="left", padx=1)
            if var is self.w_var:
                tk.Label(row, text="×", bg="#2b2b2b", fg="#ccc").pack(side="left")
        tk.Button(row, text="Set", command=self.apply_resize_entries, bg="#3c3c3c",
                  fg="white", relief="flat", padx=4).pack(side="left", padx=2)

        # Grow (＋) / shrink (−) each edge; the arrow names the edge.
        grid = tk.Frame(wrap, bg="#2b2b2b")
        grid.pack(pady=2)
        for r, (arrow, edge) in enumerate([("↑", "top"), ("↓", "bottom"),
                                           ("←", "left"), ("→", "right")]):
            tk.Label(grid, text=arrow, width=2, bg="#2b2b2b", fg="white").grid(row=r, column=0)
            for col, (sym, sign) in enumerate([("＋", 1), ("−", -1)], start=1):
                b = tk.Button(grid, text=sym, width=2, relief="flat", bg="#3c3c3c", fg="white")
                b.grid(row=r, column=col, padx=1, pady=1)
                self.hold_repeat(b, lambda e=edge, s=sign: self.grow(e, s))

    def hold_repeat(self, widget, action):
        """Fire `action` on press, then keep firing while the button is held."""
        def tick(delay):
            action()
            self.repeat_id = self._tk.after(delay, lambda: tick(70))
        def stop(_e):
            if self.repeat_id is not None:
                self._tk.after_cancel(self.repeat_id)
                self.repeat_id = None
        widget.bind("<ButtonPress-1>", lambda _e: tick(350))  # initial delay, then fast
        widget.bind("<ButtonRelease-1>", stop)

    def build_transform_controls(self, parent):
        wrap = tk.Frame(parent, bg="#2b2b2b")
        wrap.pack(side="bottom", fill="x", pady=(4, 0))
        tk.Label(wrap, text="TRANSFORM", bg="#2b2b2b", fg="#ccc").pack()
        pairs = [
            ("Rot CW", lambda: self.apply_transform(rotate_cw),
             "Rot CCW", lambda: self.apply_transform(rotate_ccw)),
            ("Flip H", lambda: self.apply_transform(flip_h),
             "Flip V", lambda: self.apply_transform(flip_v)),
            ("2×", lambda: self.apply_transform(
                 lambda w, h, p: scale_nn(w, h, p, w * 2, h * 2)),
             "½×", lambda: self.apply_transform(
                 lambda w, h, p: scale_nn(w, h, p, max(1, w // 2), max(1, h // 2)))),
            ("Wide", lambda: self.apply_transform(
                 lambda w, h, p: scale_nn(w, h, p, w * 2, h)),
             "Narrow", lambda: self.apply_transform(
                 lambda w, h, p: scale_nn(w, h, p, max(1, w // 2), h))),
            ("Tall", lambda: self.apply_transform(
                 lambda w, h, p: scale_nn(w, h, p, w, h * 2)),
             "Short", lambda: self.apply_transform(
                 lambda w, h, p: scale_nn(w, h, p, w, max(1, h // 2)))),
        ]
        for left_text, left_cmd, right_text, right_cmd in pairs:
            row = tk.Frame(wrap, bg="#2b2b2b")
            row.pack(fill="x", padx=4, pady=1)
            tk.Button(row, text=left_text, command=left_cmd, width=6,
                      relief="flat", bg="#3c3c3c", fg="white").pack(
                          side="left", expand=True, fill="x", padx=1)
            tk.Button(row, text=right_text, command=right_cmd, width=6,
                      relief="flat", bg="#3c3c3c", fg="white").pack(
                          side="left", expand=True, fill="x", padx=1)

    def apply_transform(self, fn):
        if self.sel:
            nw, nh, npx = fn(self.sel["w"], self.sel["h"], self.sel["buf"])
            if nw > self.MAX_DIM or nh > self.MAX_DIM:
                self.status.configure(text=f"Transform exceeds {self.MAX_DIM}px")
                return
            self.sel["w"], self.sel["h"], self.sel["buf"] = nw, nh, npx
            self.sel["hull"] = None
            self.refresh_all()
            self.draw_sel_outline()
        else:
            nw, nh, npx = fn(self.w, self.h, self.pixels)
            if nw > self.MAX_DIM or nh > self.MAX_DIM:
                self.status.configure(text=f"Transform exceeds {self.MAX_DIM}px")
                return
            self.push_undo()
            resized = nw != self.w or nh != self.h
            self.w, self.h = nw, nh
            self.frames[self.frame] = npx
            if resized:
                self.rebuild_canvas()
            else:
                self.refresh_all()

    def render_palette(self):
        for child in self.palette_frame.winfo_children():
            child.destroy()
        for i, hexc in enumerate(self.palette):
            bg = hexc[:7]
            cell = tk.Frame(self.palette_frame, bg=bg,
                            width=self.SWATCH, height=self.SWATCH,
                            highlightbackground="#1e1e1e", highlightthickness=1)
            cell.grid(row=i // self.PAL_COLS, column=i % self.PAL_COLS)
            cell.bind("<Button-1>", lambda e, c=hexc: self.set_color_hex(c))
            cell.bind("<Button-3>", lambda e, c=hexc: self.remove_from_palette(c))

    def typing(self):
        return isinstance(self._tk.focus_get(), tk.Entry)

    def _key_guard(self, fn):
        def handler(e):
            if self.active and not self.typing():
                fn()
        return handler

    def bind_keys(self):
        binds = {"b": "pencil", "g": "fill", "i": "picker",
                 "q": "picker", "l": "line", "r": "rect", "f": "rectfill",
                 "c": "copy", "m": "move", "w": "warp"}
        for key, name in binds.items():
            self._tk.bind(key, self._key_guard(lambda n=name: self.tool.set(n)), add="+")
        self._tk.bind("e", self._key_guard(self.set_transparent), add="+")
        self._tk.bind("p", self._key_guard(self.enter_screen_pick), add="+")
        self._tk.bind("<Button-1>", self.defocus_name, add="+")
        self.tool.trace_add("write", lambda *a: self.on_tool_change())
        self._tk.bind("u", self._key_guard(self.undo), add="+")
        self._tk.bind("y", self._key_guard(self.redo), add="+")
        self._tk.bind("<Return>", lambda e: self.commit_float() if self.active else None, add="+")
        self._tk.bind("<Escape>", lambda e: self.cancel_selection() if self.active else None, add="+")
        self._tk.bind("<Control-z>", lambda e: self.undo() if self.active else None, add="+")
        self._tk.bind("<Control-y>", lambda e: self.redo() if self.active else None, add="+")
        self._tk.bind("<Control-s>", lambda e: self.save_current() if self.active else None, add="+")
        self._tk.bind("<plus>", lambda e: self.set_zoom(self.zoom + 2) if self.active else None, add="+")
        self._tk.bind("<minus>", lambda e: self.set_zoom(self.zoom - 2) if self.active else None, add="+")

    def on_tool_change(self):
        """Switching tools finalises any floating selection in place."""
        self.cancel_rubber()
        self.commit_float()

    def defocus_name(self, event):
        if not isinstance(event.widget, tk.Entry):
            self._tk.focus_set()

    def on_wheel(self, event):
        self.set_zoom(self.zoom + (2 if event.delta > 0 else -2), event)

    # -- Colour -------------------------------------------------------------

    def color_hex(self):
        r, g, b, a = self.color
        if a == 255:
            return f"#{r:02x}{g:02x}{b:02x}"
        return f"#{r:02x}{g:02x}{b:02x}{a:02x}"

    def set_transparent(self):
        """E / Erase: make the active colour fully transparent so any tool —
        pencil, fill, line, rect — erases by drawing transparent pixels."""
        self.color = list(TRANSPARENT)
        self.hsv_vals["A"] = 0.0
        self.update_swatch()
        self.draw_bars()

    def update_swatch(self):
        r, g, b, a = self.color
        if a == 0:
            self.swatch.configure(bg=self.CHECK_LIGHT, text="erase", fg="#555")
        else:
            self.swatch.configure(bg=f"#{r:02x}{g:02x}{b:02x}", text="")
        if hasattr(self, "hex_var"):
            self.hex_var.set(self.color_hex())

    def gradient_image(self, ch, w):
        cols = []
        for x in range(w):
            t = x / max(w - 1, 1)
            if ch == "A":
                r, g, b = colorsys.hsv_to_rgb(self.hsv_vals["H"], self.hsv_vals["S"], self.hsv_vals["V"])
                cr, cg, cb = round(r * 255), round(g * 255), round(b * 255)
                bg = 0xd4 if (x // 8) % 2 == 0 else 0xbd
                rr = round(bg * (1 - t) + cr * t)
                gg = round(bg * (1 - t) + cg * t)
                bb = round(bg * (1 - t) + cb * t)
                cols.append("#%02x%02x%02x" % (rr, gg, bb))
            else:
                h, s, v = self.hsv_vals["H"], self.hsv_vals["S"], self.hsv_vals["V"]
                r, g, b = colorsys.hsv_to_rgb(t if ch == "H" else h,
                                              t if ch == "S" else s,
                                              t if ch == "V" else v)
                cols.append("#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255)))
        img = tk.PhotoImage(width=w, height=self.BAR_H)
        img.put(" ".join(["{" + " ".join(cols) + "}"] * self.BAR_H))
        return img

    def draw_bars(self):
        for ch, c in self.bar_canvas.items():
            w = c.winfo_width()
            if w < 2:
                w = self.BAR_W
            self.bar_imgs[ch] = self.gradient_image(ch, w)
            c.delete("all")
            c.create_image(0, 0, anchor="nw", image=self.bar_imgs[ch])
            mx = round(self.hsv_vals[ch] * (w - 1))
            c.create_rectangle(mx - 2, 0, mx + 2, self.BAR_H - 1, outline="#fff")
            c.create_line(mx, 0, mx, self.BAR_H, fill="#000")

    def apply_hsv(self):
        r, g, b = colorsys.hsv_to_rgb(*(self.hsv_vals[k] for k in "HSV"))
        self.color = [round(r * 255), round(g * 255), round(b * 255), round(self.hsv_vals["A"] * 255)]
        self.update_swatch()
        self.draw_bars()

    def bar_set(self, ch, event):
        w = event.widget.winfo_width()
        self.hsv_vals[ch] = min(max(event.x / max(w - 1, 1), 0.0), 1.0)
        self.apply_hsv()

    def set_color_hex(self, hexc):
        r, g, b = int(hexc[1:3], 16), int(hexc[3:5], 16), int(hexc[5:7], 16)
        a = int(hexc[7:9], 16) if len(hexc) > 7 else 255
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        self.hsv_vals = {"H": h, "S": s, "V": v, "A": a / 255}
        self.color = [r, g, b, a]
        self.update_swatch()
        self.draw_bars()

    def apply_hex_entry(self, _event=None):
        """Adopt the hex typed/pasted into the field; revert it if it's junk.
        Accepts an optional leading # and 3- (shorthand), 6-, or 8-digit codes."""
        s = self.hex_var.get().strip().lstrip("#")
        if len(s) == 3:
            s = "".join(c * 2 for c in s)
        if len(s) in (6, 8) and all(c in "0123456789abcdefABCDEF" for c in s):
            self.set_color_hex("#" + s.lower())
        else:
            self.hex_var.set(self.color_hex())
        return "break"  # don't also trigger the global <Return> handler

    def add_current_to_palette(self):
        if self.color[3] == 0:
            return  # erasing (transparent) isn't a palette colour
        hexc = self.color_hex()
        if hexc not in self.palette:
            self.palette.append(hexc)
            save_palette(self.palette)
            self.render_palette()

    def enter_screen_pick(self):
        """gcolor3-style screen colour picker.
        Linux: delegates to xcolor/grabc so the pointer is fully free (cross-workspace).
        macOS/Windows (or Linux fallback): PIL ImageGrab + grab_set_global."""
        self.pick_screen_btn.configure(text="Picking…", state="disabled")
        self.status.configure(text="Click anywhere to pick — Esc cancels")
        threading.Thread(target=self._screen_pick_worker, daemon=True).start()

    def _screen_pick_worker(self):
        """Try pickers in order: XDG portal → CLI tools → PIL grab."""
        # 1. XDG Desktop Portal PickColor — compositor-native, cross-workspace,
        #    works on GNOME/KDE/Hyprland; requires python-dbus + python-gobject.
        hexc = self._pick_via_portal()
        if hexc:
            self._tk.after(0, lambda h=hexc: self._screen_pick_done(h))
            return
        # 2. CLI pickers (X11 / XWayland).
        for cmd, parse in [
            (["hyprpicker"],        lambda s: "#" + s.strip().lstrip("#")),
            (["xcolor", "-s", "0"], lambda s: s.strip()),
            (["grabc"],             lambda s: "#" + s.strip().lstrip("#")),
        ]:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if r.returncode == 0:
                    m = re.search(r'#?([0-9a-fA-F]{6})', r.stdout)
                    if m:
                        hexc = "#" + m.group(1).lower()
                        self._tk.after(0, lambda h=hexc: self._screen_pick_done(h))
                        return
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        # 3. PIL grab (macOS / Windows / X11 with scrot).
        self._tk.after(0, self._start_pil_pick)

    def _pick_via_portal(self):
        """Run the portal script in a subprocess — clean GLib context, no
        threading issues.  Returns '#rrggbb' on success, None otherwise."""
        import sys
        try:
            r = subprocess.run(
                [sys.executable, "-c", _PORTAL_PICK_SCRIPT],
                capture_output=True, text=True, timeout=125,
            )
            m = re.search(r'#([0-9a-fA-F]{6})', r.stdout)
            if m:
                return "#" + m.group(1).lower()
        except Exception:
            pass
        return None

    def _start_pil_pick(self):
        """Grab the pointer globally and sample a single pixel with PIL on click."""
        try:
            from PIL import ImageGrab
            self._pil_ig = ImageGrab
        except ImportError:
            self._screen_pick_done(None)
            return
        self._pil_picking = True
        self._tk.configure(cursor="crosshair")
        self._tk.grab_set_global()
        self._pil_btn_id = self._tk.bind("<Button-1>", self._pil_click, add=True)
        self._pil_esc_id = self._tk.bind("<Escape>",   lambda e: self._end_pil_pick(None), add=True)

    def _pil_click(self, _event):
        x, y = self._tk.winfo_pointerx(), self._tk.winfo_pointery()
        # Release the grab before sampling — on Linux the active grab can block
        # scrot / XCB from accessing the display, so we must free it first.
        self._release_pil_grab()
        self._screen_pick_done(self._sample_pixel(x, y))

    def _end_pil_pick(self, hexc):
        self._release_pil_grab()
        self._screen_pick_done(hexc)

    def _release_pil_grab(self):
        self._pil_picking = False
        self._tk.configure(cursor="")
        try:
            self._tk.grab_release()
        except Exception:
            pass
        self._tk.unbind("<Button-1>", self._pil_btn_id)
        self._tk.unbind("<Escape>",   self._pil_esc_id)

    def _sample_pixel(self, x, y):
        """Return '#rrggbb' at screen position (x, y). Tries multiple backends."""
        # 1. PIL ImageGrab — native on macOS/Windows; needs XCB or scrot on Linux.
        try:
            img = self._pil_ig.grab(bbox=(x, y, x + 1, y + 1))
            r, g, b = img.getpixel((0, 0))[:3]
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            pass
        # 2. Python-Xlib — pure-Python X11, no scrot needed (pip install python-xlib).
        try:
            from Xlib import display, X
            d = display.Display()
            raw = d.screen().root.get_image(x, y, 1, 1, X.ZPixmap, 0xffffffff)
            px = raw.data  # bytes; little-endian x86 ZPixmap = [B, G, R, pad]
            if len(px) >= 3:
                return f"#{px[2]:02x}{px[1]:02x}{px[0]:02x}"
        except Exception:
            pass
        # 3. ImageMagick import — common on Linux/macOS developer machines.
        try:
            r = subprocess.run(
                ["import", "-window", "root", "-crop", f"1x1+{x}+{y}",
                 "-depth", "8", "txt:-"],
                capture_output=True, text=True, timeout=5,
            )
            m = re.search(r'#([0-9a-fA-F]{6})', r.stdout)
            if m:
                return "#" + m.group(1).lower()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def _screen_pick_done(self, hexc):
        self.pick_screen_btn.configure(text="Pick Screen  P", state="normal")
        if hexc:
            self.set_color_hex(hexc)
        else:
            self.status.configure(
                text="No picker found — install python-dbus + python-gobject "
                     "(portal), or hyprpicker / xcolor / grabc")

    def remove_from_palette(self, hexc):
        if hexc in self.palette:
            self.palette.remove(hexc)
            save_palette(self.palette)
            self.render_palette()

    # -- Pixel model + rendering -------------------------------------------

    def alpha_over(self, top, bottom):
        ta, ba = top[3] / 255.0, bottom[3] / 255.0
        oa = ta + ba * (1 - ta)
        if oa <= 0:
            return [0, 0, 0, 0]
        return [round((top[i] * ta + bottom[i] * ba * (1 - ta)) / oa)
                for i in range(3)] + [round(oa * 255)]

    def display_hex(self, x, y):
        idx = y * self.w + x
        top = self.pixels[idx]
        if self.sel:
            fx, fy = x - self.sel["x"], y - self.sel["y"]
            if 0 <= fx < self.sel["w"] and 0 <= fy < self.sel["h"]:
                fpix = self.sel["buf"][fy * self.sel["w"] + fx]
                if fpix[3] > 0:
                    top = self.alpha_over(fpix, top)
        r, g, b, a = top
        base = self.CHECK_LIGHT if (x + y) % 2 == 0 else self.CHECK_DARK
        br, bg, bb = int(base[1:3], 16), int(base[3:5], 16), int(base[5:7], 16)
        if a == 0 and self.onion and self.frame > 0:
            pr, pg, pb, pa = self.frames[self.frame - 1][idx]
            if pa > 0:
                t = 0.35 * pa / 255
                br = int(br * (1 - t) + pr * t)
                bg = int(bg * (1 - t) + pg * t)
                bb = int(bb * (1 - t) + pb * t)
        if a > 0:
            t = a / 255
            br = int(br * (1 - t) + r * t)
            bg = int(bg * (1 - t) + g * t)
            bb = int(bb * (1 - t) + b * t)
        return f"#{br:02x}{bg:02x}{bb:02x}"

    def view_margin(self):
        """Padding (screen px) added around the art on every side so the view
        can pan past its edges. Half a viewport lets any edge pixel be scrolled
        to the centre — without it, edge pixels of a large sprite stay pinned
        against the viewport border and are awkward to draw on."""
        return (max(self.canvas.winfo_width() // 2, 200),
                max(self.canvas.winfo_height() // 2, 200))

    def rebuild_canvas(self):
        self.w_var.set(str(self.w))
        self.h_var.set(str(self.h))
        self.canvas.delete("all")
        self.sel_outline_id = self.rubber_id = None
        self.warp_handle_ids = []
        self._grid_ids = []
        self._img_base = tk.PhotoImage(width=self.w, height=self.h)
        self._build_base_image()
        self._img_zoomed = self._img_base.zoom(self.zoom, self.zoom)
        self._img_id = self.canvas.create_image(0, 0, anchor="nw",
                                                 image=self._img_zoomed)
        self._draw_grid()
        mx, my = self.view_margin()
        self.canvas.configure(scrollregion=(-mx, -my, self.w * self.zoom + mx,
                                            self.h * self.zoom + my))
        if self.sel:
            self.draw_sel_outline()
        if self.warp:
            self.draw_warp_handles()

    def _build_base_image(self):
        rows = []
        for y in range(self.h):
            rows.append("{" + " ".join(self.display_hex(x, y)
                                       for x in range(self.w)) + "}")
        self._img_base.put(" ".join(rows))

    def _draw_grid(self):
        for gid in self._grid_ids:
            self.canvas.delete(gid)
        self._grid_ids = []
        if not self.show_grid or self.zoom < 6:
            return
        z = self.zoom
        color = "#3a3a3a"
        for x in range(self.w + 1):
            self._grid_ids.append(
                self.canvas.create_line(x * z, 0, x * z, self.h * z,
                                        fill=color, width=1))
        for y in range(self.h + 1):
            self._grid_ids.append(
                self.canvas.create_line(0, y * z, self.w * z, y * z,
                                        fill=color, width=1))

    def _schedule_rezoom(self):
        if not self._rezoom_pending:
            self._rezoom_pending = True
            self._tk.after_idle(self._do_rezoom)

    def _do_rezoom(self):
        self._rezoom_pending = False
        self._img_zoomed = self._img_base.zoom(self.zoom, self.zoom)
        self.canvas.itemconfigure(self._img_id, image=self._img_zoomed)

    def refresh_cell(self, x, y):
        self._img_base.put(self.display_hex(x, y), to=(x, y))
        self._schedule_rezoom()

    def refresh_all(self):
        self._build_base_image()
        self._img_zoomed = self._img_base.zoom(self.zoom, self.zoom)
        self.canvas.itemconfigure(self._img_id, image=self._img_zoomed)

    def set_zoom(self, z, event=None):
        old_z = self.zoom
        self.zoom = max(2, min(48, z))
        if self.zoom == old_z:
            return
        if event:
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            px, py = cx / old_z, cy / old_z
            self.rebuild_canvas()
            mx, my = self.view_margin()
            self.canvas.xview_moveto((px * self.zoom - event.x + mx) / (self.w * self.zoom + 2 * mx))
            self.canvas.yview_moveto((py * self.zoom - event.y + my) / (self.h * self.zoom + 2 * my))
        else:
            self.rebuild_canvas()

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        self.grid_btn.configure(text=f"Grid: {'on' if self.show_grid else 'off'}")
        self._draw_grid()

    def toggle_onion(self):
        self.onion = not self.onion
        self.onion_btn.configure(text=f"Onion: {'on' if self.onion else 'off'}")
        self.refresh_all()

    def toggle_select_mode(self):
        """Switch copy/move between a convex-hull lasso and a rectangular box."""
        self.cancel_rubber()
        self.rubber = self.lasso_pts = None
        self.lasso_select = not self.lasso_select
        self.select_btn.configure(text=f"Select: {'lasso' if self.lasso_select else 'box'}")

    # -- Mouse / drawing ----------------------------------------------------

    def event_pixel(self, event, clamp=True):
        x = int(self.canvas.canvasx(event.x) // self.zoom)
        y = int(self.canvas.canvasy(event.y) // self.zoom)
        if clamp:
            return (x, y) if 0 <= x < self.w and 0 <= y < self.h else None
        return (x, y)

    def paint(self, x, y, color):
        idx = y * self.w + x
        if self.pixels[idx] != color:
            self.pixels[idx] = list(color)
            self.refresh_cell(x, y)

    def line_points(self, x0, y0, x1, y1):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx - dy
        pts = []
        while True:
            pts.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy; x0 += sx
            if e2 < dx:
                err += dx; y0 += sy
        return pts

    def flood_fill(self, x, y, color):
        idx = y * self.w + x
        target = list(self.pixels[idx])
        if target == list(color):
            return
        stack = [(x, y)]
        seen = set()
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in seen or not (0 <= cx < self.w and 0 <= cy < self.h):
                continue
            seen.add((cx, cy))
            if self.pixels[cy * self.w + cx] == target:
                self.pixels[cy * self.w + cx] = list(color)
                stack += [(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]
        self.refresh_all()

    def outside_grid(self, event):
        x, y = self.event_pixel(event, clamp=False)
        return not (0 <= x < self.w and 0 <= y < self.h)

    def pan_start(self, event):
        self.panning = True
        self.canvas.scan_mark(event.x, event.y)

    def pan_move(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def pan_end(self):
        self.panning = False

    def on_press(self, event):
        if self._pil_picking:
            return
        if self.tool.get() == "warp" and self.warp:
            handle = self.hit_warp_handle(event)
            if handle is not None:
                self.warp_active = handle
                return
        if self.outside_grid(event):
            self.pan_start(event)
            return
        tool = self.tool.get()
        if tool == "warp":
            self.warp_press(event)
            return
        if tool in ("copy", "move"):
            self.cm_press(event)
            return
        px = self.event_pixel(event)
        if px is None:
            return
        x, y = px
        if tool == "picker":
            self.color = list(self.pixels[y * self.w + x])
            if self.color[3] == 0:
                self.color = [0, 0, 0, 255]
            self.update_swatch()
        else:
            self.push_undo()
            self.add_current_to_palette()  # drawing a colour records it
            if tool == "pencil":
                self.last_px = (x, y)
                self.paint(x, y, self.color)
            elif tool == "fill":
                self.flood_fill(x, y, self.color)
            elif tool in ("line", "rect", "rectfill"):
                self.stroke_start = (x, y)
                self.stroke_backup = [list(p) for p in self.pixels]

    def on_drag(self, event):
        if self.panning:
            self.pan_move(event)
            return
        tool = self.tool.get()
        if tool == "warp":
            self.warp_drag(event)
            return
        if tool in ("copy", "move"):
            self.cm_drag(event)
            return
        px = self.event_pixel(event)
        if px is None:
            return
        x, y = px
        if tool == "pencil" and self.last_px:
            for (lx, ly) in self.line_points(*self.last_px, x, y):
                self.paint(lx, ly, self.color)
            self.last_px = (x, y)
        elif tool in ("line", "rect", "rectfill") and self.stroke_start:
            self.frames[self.frame] = [list(p) for p in self.stroke_backup]
            self.draw_shape(tool, self.stroke_start, (x, y))
            self.refresh_all()

    def on_release(self, event):
        if self.panning:
            self.pan_end()
        else:
            tool = self.tool.get()
            if tool == "warp":
                self.warp_release(event)
            elif tool in ("copy", "move"):
                self.cm_release(event)
            self.last_px = None
            self.stroke_start = None
            self.stroke_backup = None

    def on_rmb_press(self, event):
        if self.outside_grid(event):
            self.pan_start(event)
        else:
            self.push_undo()
            self.last_px = self.event_pixel(event)
            self.paint(self.last_px[0], self.last_px[1], TRANSPARENT)

    def on_rmb_drag(self, event):
        if self.panning:
            self.pan_move(event)
        else:
            px = self.event_pixel(event)
            if px and self.last_px:
                for (lx, ly) in self.line_points(self.last_px[0], self.last_px[1], px[0], px[1]):
                    self.paint(lx, ly, TRANSPARENT)
                self.last_px = px

    def on_rmb_release(self, event):
        self.pan_end()
        self.last_px = None

    def eyedrop(self, event):
        px = self.event_pixel(event)
        if px:
            r, g, b, a = self.pixels[px[1] * self.w + px[0]]
            if a > 0:
                self.set_color_hex(f"#{r:02x}{g:02x}{b:02x}")

    def on_mmb_press(self, event):
        self.pan_start(event) if self.outside_grid(event) else self.eyedrop(event)

    def on_mmb_drag(self, event):
        self.pan_move(event) if self.panning else self.eyedrop(event)

    def on_hover(self, event):
        px = self.event_pixel(event)
        f = f"  Frame {self.frame + 1}/{len(self.frames)}"
        self.status.configure(text=(f"{px[0]}, {px[1]}{f}" if px else f.strip()))

    def draw_shape(self, tool, start, end):
        x0, y0 = start
        x1, y1 = end
        if tool == "line":
            for (x, y) in self.line_points(x0, y0, x1, y1):
                self.pixels[y * self.w + x] = list(self.color)
        else:
            lo_x, hi_x = sorted((x0, x1))
            lo_y, hi_y = sorted((y0, y1))
            for y in range(lo_y, hi_y + 1):
                for x in range(lo_x, hi_x + 1):
                    edge = x in (lo_x, hi_x) or y in (lo_y, hi_y)
                    if tool == "rectfill" or edge:
                        self.pixels[y * self.w + x] = list(self.color)

    # -- Copy / move (drag-and-drop floating selection) ---------------------

    def cm_press(self, event):
        if self.sel is None:
            self.start_marquee(event)
        else:
            rx, ry = self.event_pixel(event, clamp=False)
            s = self.sel
            if s["x"] <= rx < s["x"] + s["w"] and s["y"] <= ry < s["y"] + s["h"]:
                self.cm_grab = (rx - s["x"], ry - s["y"])  # picked up the selection
            else:
                self.commit_float()  # clicked away → stamp it, start a new marquee
                self.start_marquee(event)

    def start_marquee(self, event):
        px = self.event_pixel(event)
        if px:
            if self.lasso_select:
                self.lasso_pts = [px]
            else:
                self.rubber = (px[0], px[1], px[0], px[1])
            self.draw_marquee()

    def cm_drag(self, event):
        if self.rubber:
            px = self.event_pixel(event)
            if px:
                self.rubber = (self.rubber[0], self.rubber[1], px[0], px[1])
                self.draw_marquee()
        elif self.lasso_pts is not None:
            px = self.event_pixel(event)
            if px and px != self.lasso_pts[-1]:
                self.lasso_pts.append(px)
                self.draw_marquee()
        elif self.sel and self.cm_grab:
            rx, ry = self.event_pixel(event, clamp=False)
            self.sel["x"] = rx - self.cm_grab[0]
            self.sel["y"] = ry - self.cm_grab[1]
            self.refresh_all()
            self.draw_sel_outline()

    def cm_release(self, event):
        if self.rubber:
            self.lift_box(self.tool.get())
            self.rubber = None
        elif self.lasso_pts is not None:
            self.lift_hull(self.tool.get())
            self.lasso_pts = None
        elif self.sel and self.cm_grab:
            self.commit_float()  # dropping the dragged selection ends the operation
        self.cm_grab = None

    def make_selection(self, sx, sy, w, h, mode, inside, hull):
        """Lift the pixels of a region (`inside[j*w+i]` flags which cells belong)
        into a floating selection, clearing the source when moving."""
        buf = [list(self.pixels[(sy + j) * self.w + (sx + i)]) if inside[j * w + i]
               else list(TRANSPARENT)
               for j in range(h) for i in range(w)]
        if mode == "move":
            self.push_undo()
            for j in range(h):
                for i in range(w):
                    if inside[j * w + i]:
                        self.pixels[(sy + j) * self.w + (sx + i)] = list(TRANSPARENT)
        self.sel = {"x": sx, "y": sy, "ox": sx, "oy": sy,
                    "w": w, "h": h, "buf": buf, "mode": mode, "hull": hull}
        self.refresh_all()
        self.draw_sel_outline()

    def lift_box(self, mode):
        x0, y0, x1, y1 = self.rubber
        sx, sy = min(x0, x1), min(y0, y1)
        w, h = abs(x1 - x0) + 1, abs(y1 - y0) + 1
        self.cancel_rubber()
        self.make_selection(sx, sy, w, h, mode, [True] * (w * h), None)

    def lift_hull(self, mode):
        hull = convex_hull(self.lasso_pts)
        self.cancel_rubber()
        if len(hull) >= 3:
            xs, ys = [p[0] for p in hull], [p[1] for p in hull]
            sx, sy = min(xs), min(ys)
            w, h = max(xs) - sx + 1, max(ys) - sy + 1
            center_hull = [(hx + 0.5, hy + 0.5) for (hx, hy) in hull]
            inside = [point_in_hull(center_hull, sx + i + 0.5, sy + j + 0.5)
                      for j in range(h) for i in range(w)]
            rel = [(hx - sx, hy - sy) for (hx, hy) in hull]
            self.make_selection(sx, sy, w, h, mode, inside, rel)

    def stamp(self, ox, oy):
        s = self.sel
        for j in range(s["h"]):
            for i in range(s["w"]):
                src = s["buf"][j * s["w"] + i]
                dx, dy = ox + i, oy + j
                if src[3] > 0 and 0 <= dx < self.w and 0 <= dy < self.h:
                    idx = dy * self.w + dx
                    self.pixels[idx] = self.alpha_over(src, self.pixels[idx])

    def commit_float(self):
        """Drop the floating selection onto the canvas at its current spot."""
        if self.sel:
            if self.sel["mode"] == "copy":
                self.push_undo()
            self.stamp(self.sel["x"], self.sel["y"])
            self.sel = None
            self.clear_sel_outline()
            self.refresh_all()
        if self.warp:
            self.clear_warp_handles()
            self.warp = None

    def cancel_selection(self):
        """Esc: discard the selection (a moved one snaps back to its origin)."""
        self.cancel_rubber()
        if self.warp:
            self.commit_float()
        elif self.sel:
            if self.sel["mode"] == "move":
                self.stamp(self.sel["ox"], self.sel["oy"])
            self.sel = None
            self.clear_sel_outline()
            self.refresh_all()

    def draw_box(self, x, y, w, h, color):
        z = self.zoom
        return self.canvas.create_rectangle(x * z, y * z, (x + w) * z, (y + h) * z,
                                            outline=color, width=2, dash=(4, 3))

    def draw_hull(self, hull, color):
        """Outline a convex polygon given in pixel coords; None if degenerate."""
        if len(hull) < 3:
            return None
        z = self.zoom
        coords = [c * z for (hx, hy) in hull for c in (hx + 0.5, hy + 0.5)]
        return self.canvas.create_polygon(coords, outline=color, fill="",
                                          width=2, dash=(4, 3))

    def draw_sel_outline(self):
        self.clear_sel_outline()
        if self.sel:
            if self.sel.get("hull"):
                ox, oy = self.sel["x"], self.sel["y"]
                self.sel_outline_id = self.draw_hull(
                    [(ox + hx, oy + hy) for (hx, hy) in self.sel["hull"]], "#ffd700")
            else:
                self.sel_outline_id = self.draw_box(
                    self.sel["x"], self.sel["y"], self.sel["w"], self.sel["h"], "#ffd700")

    def clear_sel_outline(self):
        if self.sel_outline_id:
            self.canvas.delete(self.sel_outline_id)
            self.sel_outline_id = None

    def draw_marquee(self):
        self.cancel_rubber()
        if self.rubber:
            x0, y0, x1, y1 = self.rubber
            self.rubber_id = self.draw_box(
                min(x0, x1), min(y0, y1), abs(x1 - x0) + 1, abs(y1 - y0) + 1, "#41a6f6")
        elif self.lasso_pts:
            self.rubber_id = self.draw_hull(convex_hull(self.lasso_pts), "#41a6f6")

    def cancel_rubber(self):
        if self.rubber_id:
            self.canvas.delete(self.rubber_id)
            self.rubber_id = None

    # -- Warp / perspective tool -----------------------------------------------

    def warp_press(self, event):
        if self.warp:
            self.commit_float()
        px = self.event_pixel(event)
        if px:
            self.rubber = (px[0], px[1], px[0], px[1])
            self.draw_marquee()

    def warp_drag(self, event):
        if self.warp_active is not None:
            px = self.event_pixel(event, clamp=False)
            if px:
                cx, cy = px
                cx = max(-self.w, min(self.w * 2, cx))
                cy = max(-self.h, min(self.h * 2, cy))
                self.warp["corners"][self.warp_active] = (cx, cy)
                self.update_warp_preview()
        elif self.rubber:
            px = self.event_pixel(event)
            if px:
                self.rubber = (self.rubber[0], self.rubber[1], px[0], px[1])
                self.draw_marquee()

    def warp_release(self, event):
        if self.warp_active is not None:
            self.warp_active = None
        elif self.rubber:
            self.start_warp()
            self.rubber = None

    def start_warp(self):
        x0, y0, x1, y1 = self.rubber
        sx, sy = min(x0, x1), min(y0, y1)
        sw = abs(x1 - x0) + 1
        sh = abs(y1 - y0) + 1
        self.cancel_rubber()
        self.push_undo()
        buf = []
        for j in range(sh):
            for i in range(sw):
                px, py = sx + i, sy + j
                if 0 <= px < self.w and 0 <= py < self.h:
                    buf.append(list(self.pixels[py * self.w + px]))
                    self.pixels[py * self.w + px] = list(TRANSPARENT)
                else:
                    buf.append(list(TRANSPARENT))
        self.warp = {
            "src_w": sw, "src_h": sh, "src_buf": buf,
            "corners": [(sx, sy), (sx + sw - 1, sy),
                        (sx + sw - 1, sy + sh - 1), (sx, sy + sh - 1)],
            "origin": (sx, sy),
        }
        self.sel = {
            "x": sx, "y": sy, "ox": sx, "oy": sy,
            "w": sw, "h": sh, "buf": [list(p) for p in buf],
            "mode": "move", "hull": None,
        }
        self.refresh_all()
        self.draw_sel_outline()
        self.draw_warp_handles()

    def update_warp_preview(self):
        corners = self.warp["corners"]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        bw = int(max(xs)) - int(min(xs)) + 1
        bh = int(max(ys)) - int(min(ys)) + 1
        if bw > self.MAX_DIM * 2 or bh > self.MAX_DIM * 2 or bw < 1 or bh < 1:
            return
        ow, oh, out, ox, oy = perspective_warp(
            self.warp["src_w"], self.warp["src_h"],
            self.warp["src_buf"], corners)
        self.sel = {
            "x": ox, "y": oy,
            "ox": self.warp["origin"][0], "oy": self.warp["origin"][1],
            "w": ow, "h": oh, "buf": out,
            "mode": "move", "hull": None,
        }
        self.refresh_all()
        self.draw_sel_outline()
        self.draw_warp_handles()

    def hit_warp_handle(self, event):
        if not self.warp:
            return None
        z = self.zoom
        hz = z // 2
        threshold = max(5, z)
        ex = self.canvas.canvasx(event.x)
        ey = self.canvas.canvasy(event.y)
        for i, (cx, cy) in enumerate(self.warp["corners"]):
            hx, hy = cx * z + hz, cy * z + hz
            if abs(ex - hx) <= threshold and abs(ey - hy) <= threshold:
                return i
        return None

    def draw_warp_handles(self):
        self.clear_warp_handles()
        if not self.warp:
            return
        z = self.zoom
        hz = z // 2
        corners = self.warp["corners"]
        coords = []
        for cx, cy in corners:
            coords.extend([cx * z + hz, cy * z + hz])
        quad_id = self.canvas.create_polygon(
            coords, outline="#ff4444", fill="", width=1, dash=(3, 3))
        self.warp_handle_ids.append(quad_id)
        r = max(3, z // 3)
        for cx, cy in corners:
            hx, hy = cx * z + hz, cy * z + hz
            hid = self.canvas.create_oval(
                hx - r, hy - r, hx + r, hy + r,
                fill="#ff4444", outline="white", width=1)
            self.warp_handle_ids.append(hid)

    def clear_warp_handles(self):
        for hid in self.warp_handle_ids:
            self.canvas.delete(hid)
        self.warp_handle_ids = []

    # -- Undo / redo --------------------------------------------------------

    def snapshot(self):
        return (self.frame, self.w, self.h, [list(p) for p in self.pixels])

    def push_undo(self):
        self.undo_stack.append(self.snapshot())
        del self.undo_stack[:-100]
        self.redo_stack.clear()

    def _restore(self, snap):
        fi, w, h, px = snap
        resized = w != self.w or h != self.h
        self.frame = fi
        self.w, self.h = w, h
        self.frames[fi] = px
        self.update_frame_label()
        if resized:
            self.rebuild_canvas()
        else:
            self.refresh_all()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.snapshot())
            self._restore(self.undo_stack.pop())

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.snapshot())
            self._restore(self.redo_stack.pop())

    # -- Frames -------------------------------------------------------------

    def update_frame_label(self):
        self.frame_label.configure(text=f"{self.frame + 1} / {len(self.frames)}")

    def goto_frame(self, i):
        if 0 <= i < len(self.frames):
            self.frame = i
            self.update_frame_label()
            self.refresh_all()

    def add_frame(self):
        self.frames.insert(self.frame + 1, self.blank_frame())
        self.goto_frame(self.frame + 1)

    def dup_frame(self):
        self.frames.insert(self.frame + 1, [list(p) for p in self.pixels])
        self.goto_frame(self.frame + 1)

    def del_frame(self):
        if len(self.frames) > 1:
            del self.frames[self.frame]
            self.frame = min(self.frame, len(self.frames) - 1)
            self.update_frame_label()
            self.refresh_all()

    # -- File operations ----------------------------------------------------

    def new_canvas(self):
        """Blank canvas at the current dimensions (resize with the sidebar)."""
        self.commit_float()
        self.frames = [self.blank_frame()]
        self.frame = 0
        self.path = None
        self.name_var.set("")
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.update_frame_label()
        self.rebuild_canvas()

    def resize_to(self, nw, nh, ox, oy):
        """Resize every frame, offsetting existing art by (ox, oy)."""
        self.commit_float()
        old_w, old_h = self.w, self.h
        resized = []
        for frame in self.frames:
            grid = [list(TRANSPARENT) for _ in range(nw * nh)]
            for y in range(old_h):
                for x in range(old_w):
                    nx, ny = x + ox, y + oy
                    if 0 <= nx < nw and 0 <= ny < nh:
                        grid[ny * nw + nx] = list(frame[y * old_w + x])
            resized.append(grid)
        self.w, self.h = nw, nh
        self.frames = resized
        self.undo_stack.clear()  # snapshots are sized to the old dimensions
        self.redo_stack.clear()
        self.rebuild_canvas()

    def apply_resize_entries(self):
        try:
            nw, nh = int(self.w_var.get()), int(self.h_var.get())
        except ValueError:
            messagebox.showerror("Resize", "Width and height must be whole numbers.")
        else:
            if 1 <= nw <= self.MAX_DIM and 1 <= nh <= self.MAX_DIM:
                self.resize_to(nw, nh, 0, 0)
            else:
                messagebox.showerror("Resize", f"Each side must be 1..{self.MAX_DIM}.")

    def grow(self, edge, sign):
        """Grow (sign +1) or shrink (sign -1) one edge by a pixel."""
        horizontal = edge in ("left", "right")
        nw = self.w + (sign if horizontal else 0)
        nh = self.h + (0 if horizontal else sign)
        ox = sign if edge == "left" else 0
        oy = sign if edge == "top" else 0
        if 1 <= nw <= self.MAX_DIM and 1 <= nh <= self.MAX_DIM:
            self.resize_to(nw, nh, ox, oy)

    def refresh_file_list(self, select=None):
        """Rescan the sprites folder into the always-open file list."""
        self.file_list.delete(0, tk.END)
        try:
            names = sorted(f for f in os.listdir(self.sprites_dir)
                           if f.lower().endswith(".png"))
        except OSError:
            names = []
        for n in names:
            self.file_list.insert(tk.END, n)
        if select in names:
            i = names.index(select)
            self.file_list.selection_clear(0, tk.END)
            self.file_list.selection_set(i)
            self.file_list.see(i)

    def on_file_open(self, event=None):
        sel = self.file_list.curselection()
        if sel:
            self.load_file(os.path.join(self.sprites_dir, self.file_list.get(sel[0])))

    def load_file(self, path):
        w, h, pixels = load_png(path)
        if w > self.MAX_DIM or h > self.MAX_DIM:
            messagebox.showerror("Open", f"Image exceeds {self.MAX_DIM}px per side.")
        else:
            self.commit_float()
            self.w, self.h = w, h
            self.frames = [pixels]
            self.frame = 0
            self.path = path
            self.name_var.set(os.path.splitext(os.path.basename(path))[0])
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.update_frame_label()
            self.rebuild_canvas()
            self.refresh_file_list(select=os.path.basename(path))

    def open_png(self):
        path = filedialog.askopenfilename(initialdir=self.sprites_dir,
                                          filetypes=[("PNG", "*.png")])
        if path:
            self.load_file(path)

    def save_current(self, force_dialog=False):
        """Save to the FILE-box name (or a dialog). With multiple frames, each is
        written as its own PNG: <base>_0.png, <base>_1.png, …"""
        name = self.name_var.get().strip()
        directory = self.sprites_dir
        if force_dialog or not name:
            path = filedialog.asksaveasfilename(
                initialdir=self.sprites_dir, defaultextension=".png",
                filetypes=[("PNG", "*.png")])
            if not path:
                return
            directory = os.path.dirname(path)
            name = os.path.splitext(os.path.basename(path))[0]
        self.commit_float()
        if len(self.frames) > 1:
            base = name
            if "_" in base and base.rsplit("_", 1)[1].isdigit():
                base = base.rsplit("_", 1)[0]  # vampire_0 → vampire, not vampire_0_0
            for i, frame in enumerate(self.frames):
                save_png(os.path.join(directory, f"{base}_{i}.png"), self.w, self.h, frame)
            self.path = os.path.join(directory, f"{base}_{self.frame}.png")
            self.name_var.set(f"{base}_{self.frame}")
            self.refresh_file_list(select=f"{base}_{self.frame}.png")
            self.status.configure(
                text=f"Saved {len(self.frames)} frames → {base}_0..{len(self.frames) - 1}.png")
        else:
            path = os.path.join(directory, name)
            if not path.lower().endswith(".png"):
                path += ".png"
            save_png(path, self.w, self.h, self.pixels)
            self.path = path
            self.name_var.set(os.path.splitext(os.path.basename(path))[0])
            self.refresh_file_list(select=os.path.basename(path))
            self.status.configure(text=f"Saved {os.path.basename(path)}")

    def export_spritesheet(self):
        if len(self.frames) == 1:
            messagebox.showinfo("Export sheet",
                                "Only one frame — use Save for a single sprite.")
            return
        path = filedialog.asksaveasfilename(
            initialdir=self.sprites_dir, defaultextension=".png",
            initialfile="spritesheet.png", filetypes=[("PNG", "*.png")])
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        n = len(self.frames)
        sheet_w = self.w * n
        sheet = [list(TRANSPARENT) for _ in range(sheet_w * self.h)]
        for fi, frame in enumerate(self.frames):
            ox = fi * self.w
            for y in range(self.h):
                for x in range(self.w):
                    sheet[y * sheet_w + ox + x] = list(frame[y * self.w + x])
        save_png(path, sheet_w, self.h, sheet)
        self.status.configure(
            text=f"Exported {n} frames ({self.w}x{self.h} each) → {os.path.basename(path)}")


# ---------------------------------------------------------------------------
# Ground-tile types and their display colours / materials.
# ---------------------------------------------------------------------------

GROUND_TYPES = [
    {"name": "grass",  "hex": "#7ca164",
     "material_path": "res://Assets/shader/shader-material.tres",
     "material_uid":  "uid://ckch5r1m2f8oo"},
    {"name": "water",  "hex": "#1c7bd6",
     "material_path": "res://Assets/shader/shader-material-water.tres",
     "material_uid":  None},
    {"name": "road",   "hex": "#814c37",
     "material_path": "res://Assets/shader/shader-material-road.tres",
     "material_uid":  None},
    {"name": "road2",  "hex": "#7d7d7d",
     "material_path": "res://Assets/shader/shader-material-road2.tres",
     "material_uid":  None},
]

GHOST_MATERIAL_PATH = "res://addons/TileMapDual/ghost_material.tres"
GHOST_MATERIAL_UID  = "uid://cmbcfxlkxxnwq"
TILESET_PATH        = "res://Assets/tilesets/shader.tres"
TILESET_UID         = "uid://6h55aginnmsp"
TILEMAPD_SCRIPT     = "res://addons/TileMapDual/tile_map_dual.gd"
TILEMAPD_SCRIPT_UID = "uid://cjk8nronimk5r"


def find_maps_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    root = here
    while root != os.path.dirname(root):
        if os.path.exists(os.path.join(root, "project.godot")):
            break
        root = os.path.dirname(root)
    maps = os.path.join(root, "Scenes", "maps")
    os.makedirs(maps, exist_ok=True)
    return maps


def encode_tile_map_data(cells):
    """Encode a list of (x, y) cell coordinates into Godot's
    TileMapLayer PackedByteArray format (format-version 0).
    Every cell uses source=0, atlas=(2,1), alt=0."""
    buf = struct.pack('<H', 0)  # format header
    for x, y in cells:
        buf += struct.pack('<6h', x, y, 0, 2, 1, 0)
    return buf


def decode_tile_map_data(raw):
    """Return a list of (x, y) from a PackedByteArray blob."""
    cells = []
    offset = 2  # skip format header
    while offset + 12 <= len(raw):
        x, y = struct.unpack('<2h', raw[offset:offset+4])
        cells.append((x, y))
        offset += 12
    return cells


def b64_tile_data(cells):
    import base64
    return base64.b64encode(encode_tile_map_data(cells)).decode()


def generate_tscn(scene_name, layers):
    """Build the text of a .tscn file.
    `layers` is a dict mapping ground-type name → set of (x,y) cells."""
    ext_ids = {}
    ext_lines = []
    next_id = [1]

    def ext(rtype, path, uid=None):
        key = (rtype, path)
        if key not in ext_ids:
            tag = f"{next_id[0]}_{path.rsplit('/', 1)[-1].split('.')[0]}"
            ext_ids[key] = tag
            uid_part = f' uid="{uid}"' if uid else ""
            ext_lines.append(
                f'[ext_resource type="{rtype}"{uid_part}'
                f' path="{path}" id="{tag}"]')
            next_id[0] += 1
        return ext_ids[key]

    ghost_id  = ext("Material", GHOST_MATERIAL_PATH, GHOST_MATERIAL_UID)
    tileset_id = ext("TileSet",  TILESET_PATH,       TILESET_UID)
    script_id  = ext("Script",   TILEMAPD_SCRIPT,    TILEMAPD_SCRIPT_UID)

    mat_ids = {}
    for gt in GROUND_TYPES:
        mat_ids[gt["name"]] = ext("Material", gt["material_path"], gt["material_uid"])

    lines = ['[gd_scene format=4]', '']
    lines += ext_lines
    lines += ['', f'[node name="{scene_name}" type="Node2D"]']

    layer_name_map = {
        "grass": "GrassTile", "water": "WaterTile",
        "road": "RoadTile", "road2": "Road2Tile",
    }

    for gt in GROUND_TYPES:
        name = gt["name"]
        cells = layers.get(name, set())
        if not cells:
            continue
        node_name = layer_name_map[name]
        td = b64_tile_data(sorted(cells))
        lines += [
            '',
            f'[node name="{node_name}" type="TileMapLayer" parent="."]',
            f'material = ExtResource("{ghost_id}")',
            f'tile_set = ExtResource("{tileset_id}")',
            f'tile_map_data = PackedByteArray("{td}")',
            f'script = ExtResource("{script_id}")',
            'godot_4_3_compatibility = false',
            f'display_material = ExtResource("{mat_ids[name]}")',
            f'metadata/_custom_type_script = "{TILEMAPD_SCRIPT_UID}"',
        ]

    lines.append('')
    return '\n'.join(lines)


def parse_tscn_layers(path):
    """Read a ground .tscn and return {ground_type_name: set of (x,y)}."""
    import base64
    with open(path) as f:
        text = f.read()

    material_to_type = {}
    for gt in GROUND_TYPES:
        material_to_type[gt["material_path"]] = gt["name"]

    ext_res = {}
    for m in re.finditer(r'\[ext_resource[^\]]*path="([^"]+)"[^\]]*id="([^"]+)"', text):
        ext_res[m.group(2)] = m.group(1)
    for m in re.finditer(r'\[ext_resource[^\]]*id="([^"]+)"[^\]]*path="([^"]+)"', text):
        ext_res[m.group(1)] = m.group(2)

    layers = {}
    node_tile_data = None
    node_type = None
    for line in text.split('\n'):
        if line.startswith('[node'):
            if node_type and node_tile_data:
                layers[node_type] = set(decode_tile_map_data(node_tile_data))
            node_tile_data = None
            node_type = None
            continue
        dm = re.match(r'display_material\s*=\s*ExtResource\("([^"]+)"\)', line.strip())
        if dm:
            mat_path = ext_res.get(dm.group(1), "")
            node_type = material_to_type.get(mat_path)
        td = re.match(r'tile_map_data\s*=\s*PackedByteArray\("([^"]+)"\)', line.strip())
        if td:
            node_tile_data = base64.b64decode(td.group(1))
    if node_type and node_tile_data:
        layers[node_type] = set(decode_tile_map_data(node_tile_data))

    return layers


# ---------------------------------------------------------------------------
# Ground Map Editor.
# ---------------------------------------------------------------------------

class GroundEditor:
    MAX_DIM = 256

    def __init__(self, parent):
        self.parent = parent
        self._tk = parent.winfo_toplevel()
        self.active = False
        self.maps_dir = find_maps_dir()
        self.path = None

        self.w, self.h = 40, 30
        self.zoom = 16
        self.show_grid = True

        self.cells = {}  # (x,y) → ground type name
        self.current_type = "grass"
        self.tool = tk.StringVar(value="pencil")

        self.undo_stack = []
        self.redo_stack = []
        self._img_base = None
        self._img_zoomed = None
        self._img_id = None
        self._grid_ids = []
        self._rezoom_pending = False
        self.last_px = None
        self.panning = False
        self.stroke_start = None
        self.stroke_backup = None

        self.sel = None
        self.cm_grab = None
        self.lasso_select = True
        self.rubber = None
        self.lasso_pts = None
        self.sel_outline_id = None
        self.rubber_id = None

        self.type_colors = {}
        for gt in GROUND_TYPES:
            h = gt["hex"]
            self.type_colors[gt["name"]] = (
                int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))

        self.build_ui()
        self.rebuild_canvas()
        self.bind_keys()

    def build_ui(self):
        for cls in ("Button", "Radiobutton"):
            self.parent.option_add(f"*{cls}.highlightBackground", "#1a1a1a")
            self.parent.option_add(f"*{cls}.highlightColor", "#1a1a1a")
            self.parent.option_add(f"*{cls}.activeBackground", "#555555")
            self.parent.option_add(f"*{cls}.activeForeground", "white")

        bar = tk.Frame(self.parent, bg="#2b2b2b")
        bar.pack(side="top", fill="x")

        def btn(parent, text, cmd, **kw):
            b = tk.Button(parent, text=text, command=cmd, padx=6, pady=2,
                          bg="#3c3c3c", fg="white", relief="flat",
                          activebackground="#555", **kw)
            b.pack(side="left", padx=1, pady=2)
            return b

        btn(bar, "New", self.new_map)
        btn(bar, "Undo  U", self.undo)
        btn(bar, "Redo  Y", self.redo)
        tk.Frame(bar, width=12, bg="#2b2b2b").pack(side="left")
        btn(bar, "Zoom -", lambda: self.set_zoom(self.zoom - 2))
        btn(bar, "Zoom +", lambda: self.set_zoom(self.zoom + 2))
        self.grid_btn = btn(bar, "Grid: on", self.toggle_grid)

        self.status = tk.Label(bar, text="", bg="#2b2b2b", fg="#aaa")
        self.status.pack(side="right", padx=8)

        body = tk.Frame(self.parent, bg="#1e1e1e")
        body.pack(side="top", fill="both", expand=True)

        sidebar = tk.Frame(body, bg="#2b2b2b")
        sidebar.pack(side="left", fill="y")

        tk.Label(sidebar, text="TOOL", bg="#2b2b2b", fg="#ccc").pack(pady=(8, 2))
        for name, label in [("pencil", "Pencil  B"), ("fill", "Fill  G"),
                            ("line", "Line  L"), ("rect", "Rect  R"),
                            ("rectfill", "Rect Fill  F"),
                            ("picker", "Picker  Q"),
                            ("copy", "Copy  C"), ("move", "Move  M")]:
            tk.Radiobutton(sidebar, text=label, value=name, variable=self.tool,
                           indicatoron=False, width=12, bg="#3c3c3c", fg="white",
                           selectcolor="#7a2233", relief="flat",
                           anchor="w", padx=6, pady=4).pack(fill="x", padx=3, pady=1)
        tk.Button(sidebar, text="Erase  E", command=self.set_erase, width=12,
                  bg="#3c3c3c", fg="white", relief="flat", anchor="w",
                  padx=6, pady=4).pack(fill="x", padx=3, pady=(6, 1))
        self.select_btn = tk.Button(sidebar, text="Select: lasso",
                  command=self.toggle_select_mode, width=12,
                  bg="#3c3c3c", fg="white", relief="flat", anchor="w",
                  padx=6, pady=4)
        self.select_btn.pack(fill="x", padx=3, pady=1)

        self.build_resize_controls(sidebar)

        center = tk.Frame(body, bg="#1e1e1e")
        center.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(center, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_hover)
        self.canvas.bind("<Button-3>", self.on_rmb_press)
        self.canvas.bind("<B3-Motion>", self.on_rmb_drag)
        self.canvas.bind("<ButtonRelease-3>", lambda e: self.pan_end())
        self.canvas.bind("<Button-2>", self.on_mmb_press)
        self.canvas.bind("<B2-Motion>", self.on_mmb_drag)
        self.canvas.bind("<ButtonRelease-2>", lambda e: self.pan_end())
        self.canvas.bind("<Button-4>", lambda e: self.set_zoom(self.zoom + 2, e))
        self.canvas.bind("<Button-5>", lambda e: self.set_zoom(self.zoom - 2, e))

        right = tk.Frame(body, bg="#2b2b2b", width=224)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="GROUND TYPE", bg="#2b2b2b", fg="#ccc").pack(pady=(8, 2))
        self.type_var = tk.StringVar(value=self.current_type)
        self.type_btns = {}
        for gt in GROUND_TYPES:
            r, g, b = self.type_colors[gt["name"]]
            fg_lum = (r * 299 + g * 587 + b * 114) / 1000
            fg = "black" if fg_lum > 128 else "white"
            rb = tk.Radiobutton(right, text=gt["name"].upper(), value=gt["name"],
                                variable=self.type_var,
                                command=self.on_type_change,
                                indicatoron=False, width=20,
                                bg=f"#{r:02x}{g:02x}{b:02x}", fg=fg,
                                selectcolor=f"#{max(0,r-30):02x}{max(0,g-30):02x}{max(0,b-30):02x}",
                                relief="flat", anchor="center",
                                padx=6, pady=8, font=("TkDefaultFont", 11, "bold"))
            rb.pack(fill="x", padx=6, pady=2)
            self.type_btns[gt["name"]] = rb
        self.erase_active = False
        self.erase_label = tk.Label(right, text="", bg="#2b2b2b", fg="#ff6666")
        self.erase_label.pack(pady=(2, 0))

        tk.Label(right, text="FILE", bg="#2b2b2b", fg="#ccc").pack(pady=(16, 2))
        self.name_var = tk.StringVar()
        namerow = tk.Frame(right, bg="#2b2b2b")
        namerow.pack(fill="x", padx=6)
        self.name_entry = tk.Entry(namerow, textvariable=self.name_var, bg="#1e1e1e",
                                   fg="white", insertbackground="white", relief="flat")
        self.name_entry.pack(side="left", fill="x", expand=True)
        tk.Label(namerow, text=".tscn", bg="#2b2b2b", fg="#888").pack(side="left")
        saverow = tk.Frame(right, bg="#2b2b2b")
        saverow.pack(fill="x", padx=6)
        tk.Button(saverow, text="Save", command=self.save_current, bg="#3c3c3c",
                  fg="white", relief="flat", padx=4).pack(fill="x")

        files_wrap = tk.Frame(right, bg="#2b2b2b")
        files_wrap.pack(fill="both", expand=True, padx=6, pady=(4, 8))
        fsb = tk.Scrollbar(files_wrap, orient="vertical")
        self.file_list = tk.Listbox(files_wrap, bg="#1e1e1e", fg="white", relief="flat",
                                    highlightthickness=0, activestyle="none",
                                    selectbackground="#7a2233", yscrollcommand=fsb.set)
        fsb.configure(command=self.file_list.yview)
        fsb.pack(side="right", fill="y")
        self.file_list.pack(side="left", fill="both", expand=True)
        self.file_list.bind("<Double-Button-1>", self.on_file_open)
        self.refresh_file_list()

    def build_resize_controls(self, parent):
        wrap = tk.Frame(parent, bg="#2b2b2b")
        wrap.pack(side="bottom", fill="x", pady=(8, 8))
        tk.Label(wrap, text="CANVAS", bg="#2b2b2b", fg="#ccc").pack()

        row = tk.Frame(wrap, bg="#2b2b2b")
        row.pack(pady=2)
        self.w_var = tk.StringVar(value=str(self.w))
        self.h_var = tk.StringVar(value=str(self.h))
        for var in (self.w_var, self.h_var):
            tk.Entry(row, textvariable=var, width=3, bg="#1e1e1e", fg="white",
                     insertbackground="white", relief="flat",
                     justify="center").pack(side="left", padx=1)
            if var is self.w_var:
                tk.Label(row, text="×", bg="#2b2b2b", fg="#ccc").pack(side="left")
        tk.Button(row, text="Set", command=self.apply_resize_entries, bg="#3c3c3c",
                  fg="white", relief="flat", padx=4).pack(side="left", padx=2)

        grid = tk.Frame(wrap, bg="#2b2b2b")
        grid.pack(pady=2)
        self.repeat_id = None
        for r, (arrow, edge) in enumerate([("↑", "top"), ("↓", "bottom"),
                                           ("←", "left"), ("→", "right")]):
            tk.Label(grid, text=arrow, width=2, bg="#2b2b2b", fg="white").grid(row=r, column=0)
            for col, (sym, sign) in enumerate([("＋", 1), ("−", -1)], start=1):
                b = tk.Button(grid, text=sym, width=2, relief="flat", bg="#3c3c3c", fg="white")
                b.grid(row=r, column=col, padx=1, pady=1)
                self._hold_repeat(b, lambda e=edge, s=sign: self.grow(e, s))

    def _hold_repeat(self, widget, action):
        def tick(delay):
            action()
            self.repeat_id = self._tk.after(delay, lambda: tick(70))
        def stop(_e):
            if self.repeat_id is not None:
                self._tk.after_cancel(self.repeat_id)
                self.repeat_id = None
        widget.bind("<ButtonPress-1>", lambda _e: tick(350))
        widget.bind("<ButtonRelease-1>", stop)

    def typing(self):
        return isinstance(self._tk.focus_get(), tk.Entry)

    def _key_guard(self, fn):
        def handler(e):
            if self.active and not self.typing():
                fn()
        return handler

    def bind_keys(self):
        binds = {"b": "pencil", "g": "fill", "q": "picker",
                 "l": "line", "r": "rect", "f": "rectfill",
                 "c": "copy", "m": "move"}
        for key, name in binds.items():
            self._tk.bind(key, self._key_guard(lambda n=name: self.tool.set(n)), add="+")
        self._tk.bind("e", self._key_guard(self.set_erase), add="+")
        self._tk.bind("u", self._key_guard(self.undo), add="+")
        self._tk.bind("y", self._key_guard(self.redo), add="+")
        self._tk.bind("<Return>", lambda e: self.commit_float() if self.active else None, add="+")
        self._tk.bind("<Escape>", lambda e: self.cancel_selection() if self.active else None, add="+")
        self._tk.bind("<Control-z>", lambda e: self.undo() if self.active else None, add="+")
        self._tk.bind("<Control-y>", lambda e: self.redo() if self.active else None, add="+")
        self._tk.bind("<Control-s>", lambda e: self.save_current() if self.active else None, add="+")
        self._tk.bind("<plus>", lambda e: self.set_zoom(self.zoom + 2) if self.active else None, add="+")
        self._tk.bind("<minus>", lambda e: self.set_zoom(self.zoom - 2) if self.active else None, add="+")
        self._tk.bind("<Button-1>", self._defocus, add="+")
        self.tool.trace_add("write", lambda *a: self.on_tool_change())

    def _defocus(self, event):
        if not isinstance(event.widget, tk.Entry):
            self._tk.focus_set()

    def on_type_change(self):
        self.current_type = self.type_var.get()
        self.erase_active = False
        self.erase_label.configure(text="")

    def set_erase(self):
        self.erase_active = True
        self.erase_label.configure(text="ERASING")

    # -- Rendering ----------------------------------------------------------

    def cell_hex(self, x, y):
        t = self.cells.get((x, y))
        if self.sel:
            fx, fy = x - self.sel["x"], y - self.sel["y"]
            if 0 <= fx < self.sel["w"] and 0 <= fy < self.sel["h"]:
                ft = self.sel["buf"].get((fx, fy))
                if ft:
                    t = ft
        if t:
            r, g, b = self.type_colors[t]
            return f"#{r:02x}{g:02x}{b:02x}"
        return "#1e1e1e"

    def view_margin(self):
        return (max(self.canvas.winfo_width() // 2, 200),
                max(self.canvas.winfo_height() // 2, 200))

    def rebuild_canvas(self):
        self.w_var.set(str(self.w))
        self.h_var.set(str(self.h))
        self.canvas.delete("all")
        self._grid_ids = []
        self.sel_outline_id = self.rubber_id = None
        self._img_base = tk.PhotoImage(width=self.w, height=self.h)
        self._build_base_image()
        self._img_zoomed = self._img_base.zoom(self.zoom, self.zoom)
        self._img_id = self.canvas.create_image(0, 0, anchor="nw",
                                                 image=self._img_zoomed)
        self._draw_grid()
        mx, my = self.view_margin()
        self.canvas.configure(scrollregion=(-mx, -my, self.w * self.zoom + mx,
                                            self.h * self.zoom + my))
        if self.sel:
            self.draw_sel_outline()

    def _build_base_image(self):
        rows = []
        for y in range(self.h):
            rows.append("{" + " ".join(self.cell_hex(x, y) for x in range(self.w)) + "}")
        self._img_base.put(" ".join(rows))

    def _draw_grid(self):
        for gid in self._grid_ids:
            self.canvas.delete(gid)
        self._grid_ids = []
        if not self.show_grid or self.zoom < 4:
            return
        z = self.zoom
        color = "#3a3a3a"
        for x in range(self.w + 1):
            self._grid_ids.append(
                self.canvas.create_line(x * z, 0, x * z, self.h * z,
                                        fill=color, width=1))
        for y in range(self.h + 1):
            self._grid_ids.append(
                self.canvas.create_line(0, y * z, self.w * z, y * z,
                                        fill=color, width=1))

    def _schedule_rezoom(self):
        if not self._rezoom_pending:
            self._rezoom_pending = True
            self._tk.after_idle(self._do_rezoom)

    def _do_rezoom(self):
        self._rezoom_pending = False
        self._img_zoomed = self._img_base.zoom(self.zoom, self.zoom)
        self.canvas.itemconfigure(self._img_id, image=self._img_zoomed)

    def refresh_cell(self, x, y):
        self._img_base.put(self.cell_hex(x, y), to=(x, y))
        self._schedule_rezoom()

    def refresh_all(self):
        self._build_base_image()
        self._img_zoomed = self._img_base.zoom(self.zoom, self.zoom)
        self.canvas.itemconfigure(self._img_id, image=self._img_zoomed)

    def set_zoom(self, z, event=None):
        old_z = self.zoom
        self.zoom = max(2, min(48, z))
        if self.zoom == old_z:
            return
        if event:
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            px, py = cx / old_z, cy / old_z
            self.rebuild_canvas()
            mx, my = self.view_margin()
            self.canvas.xview_moveto((px * self.zoom - event.x + mx) / (self.w * self.zoom + 2 * mx))
            self.canvas.yview_moveto((py * self.zoom - event.y + my) / (self.h * self.zoom + 2 * my))
        else:
            self.rebuild_canvas()

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        self.grid_btn.configure(text=f"Grid: {'on' if self.show_grid else 'off'}")
        self._draw_grid()

    # -- Mouse / painting ---------------------------------------------------

    def event_pixel(self, event, clamp=True):
        x = int(self.canvas.canvasx(event.x) // self.zoom)
        y = int(self.canvas.canvasy(event.y) // self.zoom)
        if clamp:
            return (x, y) if 0 <= x < self.w and 0 <= y < self.h else None
        return (x, y)

    def outside_grid(self, event):
        x, y = self.event_pixel(event, clamp=False)
        return not (0 <= x < self.w and 0 <= y < self.h)

    def pan_start(self, event):
        self.panning = True
        self.canvas.scan_mark(event.x, event.y)

    def pan_move(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def pan_end(self):
        self.panning = False

    def paint(self, x, y):
        if self.erase_active:
            if (x, y) in self.cells:
                del self.cells[(x, y)]
                self.refresh_cell(x, y)
        else:
            if self.cells.get((x, y)) != self.current_type:
                self.cells[(x, y)] = self.current_type
                self.refresh_cell(x, y)

    def line_points(self, x0, y0, x1, y1):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx - dy
        pts = []
        while True:
            pts.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy; x0 += sx
            if e2 < dx:
                err += dx; y0 += sy
        return pts

    def flood_fill(self, x, y):
        target = self.cells.get((x, y))
        if self.erase_active:
            if target is None:
                return
        else:
            if target == self.current_type:
                return

        stack = [(x, y)]
        seen = set()
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in seen or not (0 <= cx < self.w and 0 <= cy < self.h):
                continue
            if self.cells.get((cx, cy)) != target:
                continue
            seen.add((cx, cy))
            if self.erase_active:
                self.cells.pop((cx, cy), None)
            else:
                self.cells[(cx, cy)] = self.current_type
            stack += [(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)]
        self.refresh_all()

    def draw_shape(self, tool, start, end):
        x0, y0 = start
        x1, y1 = end
        if tool == "line":
            pts = self.line_points(x0, y0, x1, y1)
        else:
            lo_x, hi_x = sorted((x0, x1))
            lo_y, hi_y = sorted((y0, y1))
            pts = []
            for yy in range(lo_y, hi_y + 1):
                for xx in range(lo_x, hi_x + 1):
                    edge = xx in (lo_x, hi_x) or yy in (lo_y, hi_y)
                    if tool == "rectfill" or edge:
                        pts.append((xx, yy))
        for px, py in pts:
            if 0 <= px < self.w and 0 <= py < self.h:
                if self.erase_active:
                    self.cells.pop((px, py), None)
                else:
                    self.cells[(px, py)] = self.current_type

    def on_press(self, event):
        if self.outside_grid(event):
            self.pan_start(event)
            return
        tool = self.tool.get()
        if tool in ("copy", "move"):
            self.cm_press(event)
            return
        px = self.event_pixel(event)
        if px is None:
            return
        x, y = px
        if tool == "picker":
            t = self.cells.get((x, y))
            if t:
                self.current_type = t
                self.type_var.set(t)
                self.erase_active = False
                self.erase_label.configure(text="")
        elif tool == "fill":
            self.push_undo()
            self.flood_fill(x, y)
        elif tool in ("line", "rect", "rectfill"):
            self.push_undo()
            self.stroke_start = (x, y)
            self.stroke_backup = dict(self.cells)
        else:
            self.push_undo()
            self.last_px = (x, y)
            self.paint(x, y)

    def on_drag(self, event):
        if self.panning:
            self.pan_move(event)
            return
        tool = self.tool.get()
        if tool in ("copy", "move"):
            self.cm_drag(event)
            return
        px = self.event_pixel(event)
        if px is None:
            return
        x, y = px
        if tool == "pencil" and self.last_px:
            for lx, ly in self.line_points(*self.last_px, x, y):
                self.paint(lx, ly)
            self.last_px = (x, y)
        elif tool in ("line", "rect", "rectfill") and self.stroke_start:
            self.cells = dict(self.stroke_backup)
            self.draw_shape(tool, self.stroke_start, (x, y))
            self.refresh_all()

    def on_release(self, event):
        if self.panning:
            self.pan_end()
        elif self.tool.get() in ("copy", "move"):
            self.cm_release(event)
        self.last_px = None
        self.stroke_start = None
        self.stroke_backup = None

    def on_rmb_press(self, event):
        if self.outside_grid(event):
            self.pan_start(event)
        else:
            self.push_undo()
            px = self.event_pixel(event)
            if px:
                self.last_px = px
                was_erase = self.erase_active
                self.erase_active = True
                self.paint(px[0], px[1])
                self.erase_active = was_erase

    def on_rmb_drag(self, event):
        if self.panning:
            self.pan_move(event)
        else:
            px = self.event_pixel(event)
            if px and self.last_px:
                was_erase = self.erase_active
                self.erase_active = True
                for lx, ly in self.line_points(self.last_px[0], self.last_px[1], px[0], px[1]):
                    self.paint(lx, ly)
                self.erase_active = was_erase
                self.last_px = px

    def on_mmb_press(self, event):
        self.pan_start(event)

    def on_mmb_drag(self, event):
        self.pan_move(event) if self.panning else None

    def on_hover(self, event):
        px = self.event_pixel(event)
        info = f"{px[0]}, {px[1]}" if px else ""
        types_here = ""
        if px:
            t = self.cells.get((px[0], px[1]))
            if t:
                types_here = f"  [{t}]"
        self.status.configure(text=f"{info}{types_here}")

    # -- Copy / move selection -----------------------------------------------

    def on_tool_change(self):
        self.cancel_rubber()
        self.commit_float()

    def toggle_select_mode(self):
        self.cancel_rubber()
        self.rubber = self.lasso_pts = None
        self.lasso_select = not self.lasso_select
        self.select_btn.configure(text=f"Select: {'lasso' if self.lasso_select else 'box'}")

    def cm_press(self, event):
        if self.sel is None:
            self.start_marquee(event)
        else:
            rx, ry = self.event_pixel(event, clamp=False)
            s = self.sel
            if s["x"] <= rx < s["x"] + s["w"] and s["y"] <= ry < s["y"] + s["h"]:
                self.cm_grab = (rx - s["x"], ry - s["y"])
            else:
                self.commit_float()
                self.start_marquee(event)

    def start_marquee(self, event):
        px = self.event_pixel(event)
        if px:
            if self.lasso_select:
                self.lasso_pts = [px]
            else:
                self.rubber = (px[0], px[1], px[0], px[1])
            self.draw_marquee()

    def cm_drag(self, event):
        if self.rubber:
            px = self.event_pixel(event)
            if px:
                self.rubber = (self.rubber[0], self.rubber[1], px[0], px[1])
                self.draw_marquee()
        elif self.lasso_pts is not None:
            px = self.event_pixel(event)
            if px and px != self.lasso_pts[-1]:
                self.lasso_pts.append(px)
                self.draw_marquee()
        elif self.sel and self.cm_grab:
            rx, ry = self.event_pixel(event, clamp=False)
            self.sel["x"] = rx - self.cm_grab[0]
            self.sel["y"] = ry - self.cm_grab[1]
            self.refresh_all()
            self.draw_sel_outline()

    def cm_release(self, event):
        if self.rubber:
            self.lift_box(self.tool.get())
            self.rubber = None
        elif self.lasso_pts is not None:
            self.lift_hull(self.tool.get())
            self.lasso_pts = None
        elif self.sel and self.cm_grab:
            self.commit_float()
        self.cm_grab = None

    def make_selection(self, sx, sy, w, h, mode, inside):
        buf = {}
        for j in range(h):
            for i in range(w):
                if inside[j * w + i]:
                    t = self.cells.get((sx + i, sy + j))
                    if t:
                        buf[(i, j)] = t
        if mode == "move":
            self.push_undo()
            for j in range(h):
                for i in range(w):
                    if inside[j * w + i]:
                        self.cells.pop((sx + i, sy + j), None)
        self.sel = {"x": sx, "y": sy, "ox": sx, "oy": sy,
                    "w": w, "h": h, "buf": buf, "mode": mode, "hull": None}
        self.refresh_all()
        self.draw_sel_outline()

    def lift_box(self, mode):
        x0, y0, x1, y1 = self.rubber
        sx, sy = min(x0, x1), min(y0, y1)
        w, h = abs(x1 - x0) + 1, abs(y1 - y0) + 1
        self.cancel_rubber()
        self.make_selection(sx, sy, w, h, mode, [True] * (w * h))

    def lift_hull(self, mode):
        hull = convex_hull(self.lasso_pts)
        self.cancel_rubber()
        if len(hull) >= 3:
            xs, ys = [p[0] for p in hull], [p[1] for p in hull]
            sx, sy = min(xs), min(ys)
            w, h = max(xs) - sx + 1, max(ys) - sy + 1
            center_hull = [(hx + 0.5, hy + 0.5) for (hx, hy) in hull]
            inside = [point_in_hull(center_hull, sx + i + 0.5, sy + j + 0.5)
                      for j in range(h) for i in range(w)]
            self.make_selection(sx, sy, w, h, mode, inside)

    def stamp(self, ox, oy):
        for (fx, fy), t in self.sel["buf"].items():
            self.cells[(ox + fx, oy + fy)] = t

    def commit_float(self):
        if self.sel:
            if self.sel["mode"] == "copy":
                self.push_undo()
            self.stamp(self.sel["x"], self.sel["y"])
            self.sel = None
            self.clear_sel_outline()
            self.refresh_all()

    def cancel_selection(self):
        self.cancel_rubber()
        if self.sel:
            if self.sel["mode"] == "move":
                self.stamp(self.sel["ox"], self.sel["oy"])
            self.sel = None
            self.clear_sel_outline()
            self.refresh_all()

    def draw_box(self, x, y, w, h, color):
        z = self.zoom
        return self.canvas.create_rectangle(x * z, y * z, (x + w) * z, (y + h) * z,
                                            outline=color, width=2, dash=(4, 3))

    def draw_hull_outline(self, hull, color):
        if len(hull) < 3:
            return None
        z = self.zoom
        coords = [c * z for (hx, hy) in hull for c in (hx + 0.5, hy + 0.5)]
        return self.canvas.create_polygon(coords, outline=color, fill="",
                                          width=2, dash=(4, 3))

    def draw_sel_outline(self):
        self.clear_sel_outline()
        if self.sel:
            self.sel_outline_id = self.draw_box(
                self.sel["x"], self.sel["y"], self.sel["w"], self.sel["h"], "#ffd700")

    def clear_sel_outline(self):
        if self.sel_outline_id:
            self.canvas.delete(self.sel_outline_id)
            self.sel_outline_id = None

    def draw_marquee(self):
        self.cancel_rubber()
        if self.rubber:
            x0, y0, x1, y1 = self.rubber
            self.rubber_id = self.draw_box(
                min(x0, x1), min(y0, y1), abs(x1 - x0) + 1, abs(y1 - y0) + 1, "#41a6f6")
        elif self.lasso_pts:
            self.rubber_id = self.draw_hull_outline(convex_hull(self.lasso_pts), "#41a6f6")

    def cancel_rubber(self):
        if self.rubber_id:
            self.canvas.delete(self.rubber_id)
            self.rubber_id = None

    # -- Undo / redo --------------------------------------------------------

    def snapshot(self):
        return dict(self.cells)

    def push_undo(self):
        self.undo_stack.append(self.snapshot())
        del self.undo_stack[:-100]
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.snapshot())
            self.cells = self.undo_stack.pop()
            self.refresh_all()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.snapshot())
            self.cells = self.redo_stack.pop()
            self.refresh_all()

    # -- Resize -------------------------------------------------------------

    def apply_resize_entries(self):
        try:
            nw, nh = int(self.w_var.get()), int(self.h_var.get())
        except ValueError:
            return
        if 1 <= nw <= self.MAX_DIM and 1 <= nh <= self.MAX_DIM:
            self.w, self.h = nw, nh
            self.rebuild_canvas()

    def grow(self, edge, sign):
        horizontal = edge in ("left", "right")
        nw = self.w + (sign if horizontal else 0)
        nh = self.h + (0 if horizontal else sign)
        if 1 <= nw <= self.MAX_DIM and 1 <= nh <= self.MAX_DIM:
            if sign == 1 and edge in ("left", "top"):
                ox = 1 if edge == "left" else 0
                oy = 1 if edge == "top" else 0
                self.cells = {(x + ox, y + oy): t for (x, y), t in self.cells.items()}
            elif sign == -1 and edge in ("left", "top"):
                ox = -1 if edge == "left" else 0
                oy = -1 if edge == "top" else 0
                self.cells = {(x + ox, y + oy): t for (x, y), t in self.cells.items()}
            self.w, self.h = nw, nh
            self.rebuild_canvas()

    def new_map(self):
        self.cells = {}
        self.path = None
        self.name_var.set("")
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.rebuild_canvas()

    # -- File operations ----------------------------------------------------

    def refresh_file_list(self, select=None):
        self.file_list.delete(0, tk.END)
        try:
            names = sorted(f for f in os.listdir(self.maps_dir)
                           if f.lower().endswith(".tscn"))
        except OSError:
            names = []
        for n in names:
            self.file_list.insert(tk.END, n)
        if select in names:
            i = names.index(select)
            self.file_list.selection_clear(0, tk.END)
            self.file_list.selection_set(i)
            self.file_list.see(i)

    def on_file_open(self, event=None):
        sel = self.file_list.curselection()
        if sel:
            self.load_file(os.path.join(self.maps_dir, self.file_list.get(sel[0])))

    def load_file(self, path):
        try:
            loaded = parse_tscn_layers(path)
        except Exception as exc:
            messagebox.showerror("Open", f"Failed to parse scene:\n{exc}")
            return
        self.cells = {}
        for name, coords in loaded.items():
            for xy in coords:
                self.cells[xy] = name
        if self.cells:
            xs = [c[0] for c in self.cells]
            ys = [c[1] for c in self.cells]
            self.w = max(max(xs) + 2, self.w)
            self.h = max(max(ys) + 2, self.h)
        self.path = path
        self.name_var.set(os.path.splitext(os.path.basename(path))[0])
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.rebuild_canvas()
        self.refresh_file_list(select=os.path.basename(path))
        self.status.configure(text=f"Loaded {os.path.basename(path)}")

    def save_current(self):
        name = self.name_var.get().strip()
        if not name:
            path = filedialog.asksaveasfilename(
                initialdir=self.maps_dir, defaultextension=".tscn",
                filetypes=[("Godot Scene", "*.tscn")])
            if not path:
                return
            name = os.path.splitext(os.path.basename(path))[0]
        scene_name = name.replace(" ", "_").title().replace("_", "")
        layers = {}
        for (x, y), t in self.cells.items():
            layers.setdefault(t, set()).add((x, y))
        tscn = generate_tscn(scene_name, layers)
        path = os.path.join(self.maps_dir, name)
        if not path.lower().endswith(".tscn"):
            path += ".tscn"
        with open(path, "w") as f:
            f.write(tscn)
        self.path = path
        self.name_var.set(os.path.splitext(os.path.basename(path))[0])
        self.refresh_file_list(select=os.path.basename(path))
        self.status.configure(text=f"Saved {os.path.basename(path)}")


# ---------------------------------------------------------------------------
# Tabbed main window.
# ---------------------------------------------------------------------------

class TabbedEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("GMI Jam — Editor")

        self.tab_bar = tk.Frame(root, bg="#1a1a1a")
        self.tab_bar.pack(side="top", fill="x")

        self.container = tk.Frame(root, bg="#1e1e1e")
        self.container.pack(side="top", fill="both", expand=True)

        self.tabs = {}
        self.active_tab = None

        pixel_frame = tk.Frame(self.container, bg="#1e1e1e")
        ground_frame = tk.Frame(self.container, bg="#1e1e1e")

        self.pixel_editor = PixelEditor(pixel_frame)
        self.ground_editor = GroundEditor(ground_frame)

        self.tabs["Pixel"] = pixel_frame
        self.tabs["Ground"] = ground_frame

        self.tab_buttons = {}
        for name in ("Pixel", "Ground"):
            b = tk.Button(self.tab_bar, text=name, padx=16, pady=4,
                          bg="#2b2b2b", fg="white", relief="flat",
                          activebackground="#555",
                          command=lambda n=name: self.switch_tab(n))
            b.pack(side="left", padx=1, pady=2)
            self.tab_buttons[name] = b

        self.switch_tab("Pixel")

    def switch_tab(self, name):
        if self.active_tab == name:
            return
        self.pixel_editor.active = (name == "Pixel")
        self.ground_editor.active = (name == "Ground")
        for n, frame in self.tabs.items():
            frame.pack_forget()
        self.tabs[name].pack(in_=self.container, fill="both", expand=True)
        for n, btn in self.tab_buttons.items():
            btn.configure(bg="#7a2233" if n == name else "#2b2b2b")
        self.active_tab = name


def main():
    root = tk.Tk()
    root.geometry("1100x750")
    TabbedEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()

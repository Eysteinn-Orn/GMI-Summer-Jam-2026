#!/usr/bin/env python3
"""Pixel art editor for the GMI Summer Jam vampire game.

A self-contained tkinter pixel editor that reads and writes PNG sprites in the
project's conventional Godot sprite folder (res://Assets/sprites/). PNGs are the
format Godot imports as Texture2D, so anything saved here is usable directly by
Sprite2D / AnimatedSprite2D / AtlasTexture.

Run with:  python3 tools/pixel_editor.py

Features: pencil / eraser / flood-fill / eyedropper / line / rectangle tools,
editable palette + colour picker, zoom + pixel grid, transparency, undo/redo,
animation frames with onion-skinning, single-frame PNG save and horizontal
spritesheet export.

No third-party dependency is required: Pillow is used when present, otherwise a
small stdlib (zlib) PNG codec is used so every teammate can run it as-is.
"""

import colorsys
import json
import os
import struct
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
        self.root.title("GMI Jam — Pixel Editor")

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
        self.rects = {}        # (x, y) -> canvas item id
        self.last_px = None    # last painted pixel during a drag
        self.stroke_start = None
        self.stroke_backup = None  # snapshot for live shape preview

        # Floating copy/move selection: {x, y, w, h, buf, mode} or None.
        self.sel = None
        self.cm_grab = None          # cursor offset within a grabbed selection
        self.rubber = None           # (x0, y0, x1, y1) during marquee drag
        self.sel_outline_id = None
        self.rubber_id = None
        self.resize_visible = False
        self.repeat_id = None  # pending after() for a held-down resize button
        self.panning = False   # dragging in the margin to pan the view

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

        self.status = tk.Label(bar, text="", bg="#2b2b2b", fg="#aaa")
        self.status.pack(side="right", padx=8)

        body = tk.Frame(self.root, bg="#1e1e1e")
        body.pack(side="top", fill="both", expand=True)

        # Tool column.
        tools = tk.Frame(body, bg="#2b2b2b")
        tools.pack(side="left", fill="y")
        for name, label in [("pencil", "Pencil  B"), ("eraser", "Eraser  E"),
                            ("fill", "Fill  G"), ("picker", "Picker  Q"),
                            ("line", "Line  L"), ("rect", "Rect  R"),
                            ("rectfill", "Rect Fill  F"), ("copy", "Copy  C"),
                            ("move", "Move  M")]:
            tk.Radiobutton(tools, text=label, value=name, variable=self.tool,
                           indicatoron=False, width=12, bg="#3c3c3c", fg="white",
                           selectcolor="#7a2233", relief="flat",
                           anchor="w", padx=6, pady=4).pack(fill="x", padx=3, pady=1)

        # Canvas resize controls, pinned to the end of the sidebar.
        self.build_resize_controls(tools)

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
            self.repeat_id = self.root.after(delay, lambda: tick(70))
        def stop(_e):
            if self.repeat_id is not None:
                self.root.after_cancel(self.repeat_id)
                self.repeat_id = None
        widget.bind("<ButtonPress-1>", lambda _e: tick(350))  # initial delay, then fast
        widget.bind("<ButtonRelease-1>", stop)

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
        return isinstance(self.root.focus_get(), tk.Entry)

    def bind_keys(self):
        binds = {"b": "pencil", "e": "eraser", "g": "fill", "i": "picker",
                 "q": "picker", "l": "line", "r": "rect", "f": "rectfill",
                 "c": "copy", "m": "move"}
        for key, name in binds.items():
            self.root.bind(key, lambda e, n=name: self.tool.set(n) if not self.typing() else None)
        # Clicking anywhere that isn't the name box drops its keyboard focus.
        self.root.bind("<Button-1>", self.defocus_name, add="+")
        self.tool.trace_add("write", lambda *a: self.on_tool_change())
        self.root.bind("u", lambda e: self.undo() if not self.typing() else None)
        self.root.bind("y", lambda e: self.redo() if not self.typing() else None)
        self.root.bind("<Return>", lambda e: self.commit_float())
        self.root.bind("<Escape>", lambda e: self.cancel_selection())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Control-s>", lambda e: self.save_current())
        self.root.bind("<plus>", lambda e: self.set_zoom(self.zoom + 2))
        self.root.bind("<minus>", lambda e: self.set_zoom(self.zoom - 2))

    def on_tool_change(self):
        """Switching tools finalises any floating selection in place."""
        self.cancel_rubber()
        self.commit_float()

    def defocus_name(self, event):
        # Clicking off any text field hands focus back to the canvas so the
        # single-key tool shortcuts work again; clicking into one keeps it.
        if not isinstance(event.widget, tk.Entry):
            self.root.focus_set()

    def on_wheel(self, event):
        self.set_zoom(self.zoom + (2 if event.delta > 0 else -2), event)

    # -- Colour -------------------------------------------------------------

    def color_hex(self):
        r, g, b, a = self.color
        if a == 255:
            return f"#{r:02x}{g:02x}{b:02x}"
        return f"#{r:02x}{g:02x}{b:02x}{a:02x}"

    def update_swatch(self):
        r, g, b, _ = self.color
        self.swatch.configure(bg=f"#{r:02x}{g:02x}{b:02x}")
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
        hexc = self.color_hex()
        if hexc not in self.palette:
            self.palette.append(hexc)
            save_palette(self.palette)
            self.render_palette()

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
        self.rects.clear()
        self.sel_outline_id = self.rubber_id = None
        z, outline = self.zoom, ("#3a3a3a" if self.show_grid and self.zoom >= 6 else "")
        for y in range(self.h):
            for x in range(self.w):
                rid = self.canvas.create_rectangle(
                    x * z, y * z, (x + 1) * z, (y + 1) * z,
                    fill=self.display_hex(x, y), outline=outline, width=1)
                self.rects[(x, y)] = rid
        mx, my = self.view_margin()
        self.canvas.configure(scrollregion=(-mx, -my, self.w * z + mx, self.h * z + my))
        if self.sel:
            self.draw_sel_outline()

    def refresh_cell(self, x, y):
        self.canvas.itemconfigure(self.rects[(x, y)], fill=self.display_hex(x, y))

    def refresh_all(self):
        for y in range(self.h):
            for x in range(self.w):
                self.refresh_cell(x, y)

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
        self.rebuild_canvas()

    def toggle_onion(self):
        self.onion = not self.onion
        self.onion_btn.configure(text=f"Onion: {'on' if self.onion else 'off'}")
        self.refresh_all()

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
            self.color = list(self.pixels[y * self.w + x])
            if self.color[3] == 0:
                self.color = [0, 0, 0, 255]
            self.update_swatch()
        else:
            self.push_undo()
            if tool != "eraser":
                self.add_current_to_palette()  # drawing a colour records it
            if tool in ("pencil", "eraser"):
                self.last_px = (x, y)
                self.paint(x, y, TRANSPARENT if tool == "eraser" else self.color)
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
        if tool in ("copy", "move"):
            self.cm_drag(event)
            return
        px = self.event_pixel(event)
        if px is None:
            return
        x, y = px
        if tool in ("pencil", "eraser") and self.last_px:
            color = TRANSPARENT if tool == "eraser" else self.color
            for (lx, ly) in self.line_points(*self.last_px, x, y):
                self.paint(lx, ly, color)
            self.last_px = (x, y)
        elif tool in ("line", "rect", "rectfill") and self.stroke_start:
            self.frames[self.frame] = [list(p) for p in self.stroke_backup]
            self.draw_shape(tool, self.stroke_start, (x, y))
            self.refresh_all()

    def on_release(self, event):
        if self.panning:
            self.pan_end()
        else:
            if self.tool.get() in ("copy", "move"):
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
            px = self.event_pixel(event)
            if px:
                self.rubber = (px[0], px[1], px[0], px[1])
                self.draw_rubber()
        else:
            rx, ry = self.event_pixel(event, clamp=False)
            s = self.sel
            if s["x"] <= rx < s["x"] + s["w"] and s["y"] <= ry < s["y"] + s["h"]:
                self.cm_grab = (rx - s["x"], ry - s["y"])  # picked up the selection
            else:
                self.commit_float()  # clicked away → stamp it, start a new marquee
                px = self.event_pixel(event)
                if px:
                    self.rubber = (px[0], px[1], px[0], px[1])
                    self.draw_rubber()

    def cm_drag(self, event):
        if self.rubber:
            px = self.event_pixel(event)
            if px:
                self.rubber = (self.rubber[0], self.rubber[1], px[0], px[1])
                self.draw_rubber()
        elif self.sel and self.cm_grab:
            rx, ry = self.event_pixel(event, clamp=False)
            self.sel["x"] = rx - self.cm_grab[0]
            self.sel["y"] = ry - self.cm_grab[1]
            self.refresh_all()
            self.draw_sel_outline()

    def cm_release(self, event):
        if self.rubber:
            self.lift_selection(self.tool.get())
            self.rubber = None
        elif self.sel and self.cm_grab:
            self.commit_float()  # dropping the dragged selection ends the operation
        self.cm_grab = None

    def lift_selection(self, mode):
        x0, y0, x1, y1 = self.rubber
        sx, sy = min(x0, x1), min(y0, y1)
        w, h = abs(x1 - x0) + 1, abs(y1 - y0) + 1
        self.cancel_rubber()
        buf = [list(self.pixels[(sy + j) * self.w + (sx + i)])
               for j in range(h) for i in range(w)]
        if mode == "move":
            self.push_undo()
            for j in range(h):
                for i in range(w):
                    self.pixels[(sy + j) * self.w + (sx + i)] = list(TRANSPARENT)
        self.sel = {"x": sx, "y": sy, "ox": sx, "oy": sy,
                    "w": w, "h": h, "buf": buf, "mode": mode}
        self.refresh_all()
        self.draw_sel_outline()

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

    def cancel_selection(self):
        """Esc: discard the selection (a moved one snaps back to its origin)."""
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

    def draw_sel_outline(self):
        self.clear_sel_outline()
        if self.sel:
            self.sel_outline_id = self.draw_box(
                self.sel["x"], self.sel["y"], self.sel["w"], self.sel["h"], "#ffd700")

    def clear_sel_outline(self):
        if self.sel_outline_id:
            self.canvas.delete(self.sel_outline_id)
            self.sel_outline_id = None

    def draw_rubber(self):
        self.cancel_rubber()
        if self.rubber:
            x0, y0, x1, y1 = self.rubber
            self.rubber_id = self.draw_box(
                min(x0, x1), min(y0, y1), abs(x1 - x0) + 1, abs(y1 - y0) + 1, "#41a6f6")

    def cancel_rubber(self):
        if self.rubber_id:
            self.canvas.delete(self.rubber_id)
            self.rubber_id = None

    # -- Undo / redo --------------------------------------------------------

    def snapshot(self):
        return (self.frame, [list(p) for p in self.pixels])

    def push_undo(self):
        self.undo_stack.append(self.snapshot())
        del self.undo_stack[:-100]
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.snapshot())
            fi, px = self.undo_stack.pop()
            self.frame = fi
            self.frames[fi] = px
            self.update_frame_label()
            self.refresh_all()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.snapshot())
            fi, px = self.redo_stack.pop()
            self.frame = fi
            self.frames[fi] = px
            self.update_frame_label()
            self.refresh_all()

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


def main():
    root = tk.Tk()
    root.geometry("1000x700")
    PixelEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()

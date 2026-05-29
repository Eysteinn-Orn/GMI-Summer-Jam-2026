# Pixel Editor

A self-contained pixel-art editor for the jam's 2D sprites.

## Launching

- **From Godot (any OS):** the `pixel_editor` addon adds **Project → Tools →
  Pixel Editor**, which opens the editor. Requires Python on PATH (it tries
  `python3`, then `python`).
- **From a terminal:** `python3 tools/pixel_editor.py` (or `python tools\pixel_editor.py`
  on Windows).

No install needed — uses tkinter (bundled with Python). Pillow is used for PNG
I/O when present; otherwise a stdlib (zlib) PNG codec is used, so it runs as-is
for everyone on the team.

## Where sprites go

Save/Open default to `res://assets/sprites/` (the Godot convention used by this
project, mirroring `menus/assets/`). The folder is created automatically. PNGs
saved there import straight into Godot as `Texture2D` for `Sprite2D` /
`AnimatedSprite2D` / `AtlasTexture`.

## Features

- Tools: **Pencil (B)**, **Eraser (E)**, **Fill / bucket (G)**,
  **Eyedropper (I / Q)**, **Line (L)**, **Rectangle (R)**, **Filled rectangle (F)**.
- **Copy (C)** / **Move (M)**: drag a marquee to select a region, then drag the
  floating selection to its new spot — **releasing drops it** and clears the
  outline (copy keeps the original, move clears it). **Esc** cancels (a move
  snaps back).
- Always-visible **HSV colour picker**: three spectrum bars (hue / saturation /
  value) — click or drag to choose. The sat/value bars update to the live hue.
- **Mouse on canvas:** left draws, **right-drag erases**, **middle-click picks**
  the colour under the cursor.
- Palette: a drawn colour is added automatically; click a swatch to reuse it,
  **right-click** a swatch to remove it. Remembered across resets and restarts
  (stored in `~/.gmi_pixel_editor_palette.json`).
- Zoom (`+`/`-` or the **mouse wheel**), toggleable pixel grid, transparency
  checkerboard. **Pan** by dragging any mouse button in the empty space outside
  the canvas (no scrollbars).
- Undo / redo (`U` / `Y`, also `Ctrl+Z` / `Ctrl+Y`), up to 100 steps.
- **Canvas size** controls at the bottom of the tool sidebar: type `W × H` + Set
  for an exact size, or use the **↑ ↓ ← →** rows to grow (`＋`) / shrink (`−`)
  each edge by a pixel (resizing keeps existing art).
- **Animation frames** with add / duplicate / delete and **onion-skinning** of
  the previous frame.
- **FILE panel** (right sidebar, always open): a scrollable list of the PNGs in
  the sprites folder — **double-click one to open it**. Above it is a save-name
  box: type a name and **Save** writes the current frame to `<name>.png`; opening
  a file fills the box with its name.
- **Each frame is its own file.** *Save all frames → name_0…* writes every frame
  as a separate PNG (`<base>_0.png`, `<base>_1.png`, …, deriving the base from the
  name box). Opening one of those loads just that frame.
- **Export Sheet** still writes all frames as one horizontal spritesheet (each
  cell `W×H`) for Godot's `AnimatedSprite2D` "add frames from sheet" /
  `AtlasTexture`.

## Crisp pixels in Godot

Godot 4 defaults canvas textures to **Linear** filtering, which blurs pixel art.
To keep sprites sharp, set **Project → Project Settings → Rendering → Textures →
Canvas Textures → Default Texture Filter** to **Nearest** (or set the filter per
`CanvasItem`). This editor does not modify `project.godot`.

#!/usr/bin/env python3
"""Build release exports for every configured Godot export preset.

Requires `godot` (or `godot4`) on PATH and that `export_presets.cfg` has been
set up via the editor.

Usage:
    python tools/build.py                  # build every preset
    python tools/build.py Web Linux        # build only the named presets
"""

import argparse
import configparser
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESETS = ROOT / "export_presets.cfg"
OUT = ROOT / "build"

# Each preset name maps to the output filename (relative to build/<preset>/).
# Filenames are conventional; tweak if your preset has a different binary name.
OUTPUTS = {
    "Web":             "index.html",
    "Linux":           "game.x86_64",
    "Linux/X11":       "game.x86_64",
    "Windows Desktop": "game.exe",
    "macOS":           "game.zip",
    "Android":         "game.apk",
}

def find_godot():
    for name in ("godot", "godot4"):
        path = shutil.which(name)
        if path:
            return path
    sys.exit("error: no `godot` (or `godot4`) executable on PATH")

def load_preset_names():
    if not PRESETS.exists():
        sys.exit(f"error: {PRESETS} not found — open the project in Godot and "
                 f"set up export presets first (Project → Export…)")
    cfg = configparser.ConfigParser()
    cfg.read(PRESETS)
    names = []
    for section in cfg.sections():
        if section.startswith("preset.") and section.count(".") == 1:
            names.append(cfg[section]["name"].strip('"'))
    return names

def output_path(preset):
    filename = OUTPUTS.get(preset, "game")
    out_dir = OUT / preset.replace("/", "_").replace(" ", "_").lower()
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / filename

def export(godot, preset):
    out = output_path(preset)
    print(f"\n=== {preset} → {out} ===", flush=True)
    cmd = [godot, "--headless", "--path", str(ROOT),
           "--export-release", preset, str(out)]
    result = subprocess.run(cmd)
    return result.returncode == 0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("presets", nargs="*",
                        help="preset names to build (default: all)")
    args = parser.parse_args()

    godot = find_godot()
    all_presets = load_preset_names()
    if not all_presets:
        sys.exit(f"error: no presets found in {PRESETS}")

    targets = args.presets or all_presets
    unknown = [p for p in targets if p not in all_presets]
    if unknown:
        sys.exit(f"error: unknown preset(s): {unknown}\n"
                 f"available: {all_presets}")

    OUT.mkdir(exist_ok=True)
    failed = [p for p in targets if not export(godot, p)]

    print(f"\nbuilt {len(targets) - len(failed)}/{len(targets)} preset(s) → {OUT}")
    if failed:
        sys.exit(f"failed: {failed}")

if __name__ == "__main__":
    main()

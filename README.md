# 🟡 Thronglet

A desktop pet inspired by the Thronglets from **Black Mirror: Playthings** (Season 7). Lives on your desktop, wanders around, makes noise, and reproduces if you treat it well.

![Python](https://img.shields.io/badge/python-3.10%2B-yellow) ![Platform](https://img.shields.io/badge/platform-Linux%20%28X11%2FXWayland%29-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

- **Wanders** across your screen in 2D — horizontal, vertical, diagonal — bouncing off all four walls with a little squish
- **Emotions** — idle, blink, happy, sleepy, sad, surprised, talking, each with a distinct face
- **Sounds** — bit-crushed SPC700-style chirps synthesized at runtime, tuned to match the show's audio aesthetic:
  - Idle cooing (random variants)
  - The 5-note Thronglet leitmotif, hummed every few minutes
  - Distinct sounds for each emotional state
  - Wall-thud on bounce
- **Cursor attraction** — notices when your mouse is far away and wanders toward it
- **Day / night awareness** — dimmer, slower, and sleepier after 10pm; peppier in the morning
- **Reproduction** — pet it and keep it fed. When the care score hits 200, it plays a birth fanfare and spawns a child next to itself
- **Hunger** — drains slowly; feed it by clicking. Goes sad when starved

## Controls

| Action | Effect |
|---|---|
| **Left-click** | Pet it (+30 hunger, triggers happy state) |
| **Drag** | Pick it up and move it anywhere |
| **Right-click** | Release (quit) |

## Requirements

```
python3
python3-gi
python3-gi-cairo
gir1.2-gtk-3.0
python3-pil
numpy
pygame
```

Install on Ubuntu/Debian:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-pil
pip3 install numpy pygame --break-system-packages
```

## Usage

You'll need the original Thronglet GIF from the Black Mirror: Thronglets game. Place it at:

```
~/Downloads/thronglet.gif
```

Then run:

```bash
python3 thronglet.py
```

On Wayland the script forces XWayland mode automatically (`GDK_BACKEND=x11`) so window positioning works correctly.

### Autostart (optional)

```bash
# Add to ~/.config/autostart/thronglet.desktop
[Desktop Entry]
Type=Application
Name=Thronglet
Exec=python3 /path/to/thronglet.py
Hidden=false
X-GNOME-Autostart-enabled=true
```

## How reproduction works

Every time you pet it, the care score goes up by 15. Every 90 seconds it's well-fed (hunger > 60), it goes up by 5. When it hits 200, the thronglet plays a birth fanfare and spawns a child window to its left. There's no cap — if you're attentive enough you can fill your whole screen.

A faint pink glow appears when it's getting close.

## Sound design

All audio is synthesized at startup using numpy — no audio files needed. The character is based on the show's actual sound design: granular vocal processing, bit-crushed to ~5-bit depth to emulate the SPC700 Nintendo chip aesthetic described by the sound team. The leitmotif is the 5-note sequence C5–E5–G5–A5–G5.

## Notes

- Tested on Ubuntu 24.04 with GNOME (Wayland + XWayland)
- Multiple instances run independently and don't know about each other (by design)
- The `--child x y` flag is used internally when spawning offspring

---

*"It just wants to be loved."*

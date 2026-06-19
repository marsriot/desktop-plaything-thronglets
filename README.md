# 🟡 desktop-plaything-thronglets

> *"It just wants to be loved."*

A desktop creature inspired by the Thronglets from **Black Mirror: Playthings** (S7). It lives on your screen, wanders in 2D, makes noise, tracks time of day, and — if you treat it well — reproduces.

![Python](https://img.shields.io/badge/python-3.10%2B-yellow) ![Platform](https://img.shields.io/badge/platform-Linux%20%28X11%2FXWayland%29-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

Your Thronglet lives on your desktop as a transparent, always-on-top window. It has no agenda beyond existing, wandering, and craving attention.

| Behavior | Detail |
|---|---|
| **Wanders** | Moves in 8 directions, bounces off all four walls with a squish animation |
| **Emotions** | idle · blink · happy · sleepy · sad · surprised · talking |
| **Sound** | Bit-crushed SPC700-style chirps synthesized at runtime — no audio files |
| **Leitmotif** | Hums its 5-note theme (C5–E5–G5–A5–G5) every few minutes |
| **Cursor attraction** | Notices when you're far away and starts walking toward you |
| **Day / night** | After 10pm it slows down, dims, and gets sleepy. Peppier in the morning |
| **Hunger** | Drains every 90 seconds. Neglect it long enough and it goes sad |
| **Reproduction** | Hit care score 200 and it plays a birth fanfare and spawns a child |

A faint pink glow appears when reproduction is near. Fill your whole screen if you're dedicated enough.

---

## Controls

| Input | Effect |
|---|---|
| **Left-click** | Pet it — +30 hunger, triggers happy state, raises care score |
| **Drag** | Pick it up and carry it anywhere |
| **Right-click** | Release thronglet (quit) |

---

## Sound design

All audio is generated at startup with numpy — no files, no samples. The aesthetic is intentional: granular chirps bit-crushed to ~5–6 bit depth to emulate the SPC700 sound chip from the SNES, matching the lo-fi vocal character heard in the show. Every emotional state has its own sound. Wall bounces thud. The leitmotif plays unprompted.

---

## Requirements

```
python3-gi
python3-gi-cairo
gir1.2-gtk-3.0
python3-pil
numpy
pygame
```

Install on Ubuntu / Debian:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-pil
pip3 install numpy pygame --break-system-packages
```

---

## Setup

You'll need the original Thronglet GIF from the Black Mirror: Thronglets web game. Save it to:

```
~/Pictures/thronglet.gif
```

Then run:

```bash
python3 thronglet.py
```

Wayland is handled automatically — the script forces XWayland (`GDK_BACKEND=x11`) so window positioning works correctly.

---

## Autostart

To have it waiting for you every time you log in:

```ini
# ~/.config/autostart/thronglet.desktop
[Desktop Entry]
Type=Application
Name=Thronglet
Exec=python3 /path/to/thronglet.py
Hidden=false
X-GNOME-Autostart-enabled=true
```

---

## Notes

- Tested on Ubuntu 24.04, GNOME, Wayland + XWayland
- Multiple instances run independently — they don't know about each other, by design
- `--child x y` is used internally when spawning offspring; don't call it directly

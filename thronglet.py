#!/usr/bin/env python3
"""
Thronglet desktop pet — GIF sprite + emotion state machine.
Features: walking, sounds, cursor attraction, melody humming,
          day/night mood, reproduction.
Click to pet, drag to move, right-click to quit.
"""

import os, sys, subprocess, datetime, random, math
os.environ['GDK_BACKEND'] = 'x11'   # Wayland ignores window.move()

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('cairo', '1.0')
from gi.repository import Gtk, Gdk, GLib
import cairo
from PIL import Image, ImageDraw
import numpy as np
import pygame.mixer

GIF_PATH   = '/home/titan/Downloads/thronglet.gif'
SCALE      = 0.22
BG         = (86, 86, 86)
TOL        = 28
WIN_W      = 110
WIN_H      = 120
WALK_SPEED = 1.3    # px/tick daytime
WALK_NIGHT = 0.65   # px/tick nighttime
REPRODUCE_AT = 200  # care points needed to spawn a child


def is_night():
    h = datetime.datetime.now().hour
    return h < 7 or h >= 22


# ── sound engine ──────────────────────────────────────────────────────────
SR = 22050


def _tone(freq, dur, amp=0.35, bits=6, vib=0.0):
    """Stable bit-crushed tone with optional vibrato."""
    t   = np.linspace(0, dur, int(SR * dur), endpoint=False)
    mod = np.sin(2 * np.pi * 6 * t) * vib * freq if vib else 0
    ph  = 2 * np.pi * (freq + mod) * t
    w   = np.sin(ph)*0.60 + np.sin(ph*2)*0.25 + np.sin(ph*3)*0.10
    lvl = 2**bits
    w   = np.round(w * lvl) / lvl
    fade = max(1, int(0.04 * SR))
    env  = np.ones(len(t))
    env[:fade]  = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    return (w * env * amp * 32767).astype(np.int16)


def _chirp(f0, f1, dur, amp=0.38, bits=5, vib=0.0):
    """Frequency-sweep chirp, SPC700 bit-crushed."""
    t    = np.linspace(0, dur, int(SR * dur), endpoint=False)
    vm   = np.sin(2*np.pi*8*t) * vib * f0 if vib else 0
    ph   = 2*np.pi*(f0*t + (f1-f0)*t**2/(2*dur))
    w    = np.sin(ph)*0.65 + np.sin(ph*2+vm)*0.25 + np.sin(ph*3)*0.10
    lvl  = 2**bits
    w    = np.round(w * lvl) / lvl
    fade = max(1, int(0.05 * SR))
    env  = np.ones(len(t))
    env[:fade]  = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    pcm  = (w * env * amp * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.ascontiguousarray(np.column_stack([pcm, pcm])))


def _seq(notes, gap=0.04):
    """Chain (f0,f1,dur) chirps into one playable buffer."""
    bufs = []
    sil  = np.zeros(int(SR * gap), dtype=np.int16)
    for f0, f1, dur in notes:
        t   = np.linspace(0, dur, int(SR * dur), endpoint=False)
        ph  = 2*np.pi*(f0*t + (f1-f0)*t**2/(2*dur))
        w   = np.sin(ph)*0.65 + np.sin(ph*2)*0.25
        lvl = 32
        w   = np.round(w * lvl) / lvl
        fade = max(1, int(0.04 * SR))
        env  = np.ones(len(t))
        env[:fade]  = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        bufs.append((w * env * 0.38 * 32767).astype(np.int16))
        bufs.append(sil)
    pcm = np.concatenate(bufs)
    return pygame.sndarray.make_sound(np.ascontiguousarray(np.column_stack([pcm, pcm])))


def _make_melody():
    """Thronglet leitmotif: C5–E5–G5–A5–G5, SPC700 bit-crushed."""
    notes = [(523, 0.22), (659, 0.20), (784, 0.22), (880, 0.26), (784, 0.38)]
    gap   = np.zeros(int(SR * 0.07), dtype=np.int16)
    bufs  = []
    for freq, dur in notes:
        bufs.append(_tone(freq, dur, amp=0.28, bits=6, vib=0.010))
        bufs.append(gap)
    pcm = np.concatenate(bufs)
    return pygame.sndarray.make_sound(np.ascontiguousarray(np.column_stack([pcm, pcm])))


def _make_birth_sound():
    """Ascending scale + excited baby chirp finale."""
    notes = [(523, 0.11), (659, 0.10), (784, 0.10), (880, 0.10), (1047, 0.28)]
    gap   = np.zeros(int(SR * 0.04), dtype=np.int16)
    bufs  = []
    for freq, dur in notes:
        bufs.append(_tone(freq, dur, amp=0.38, bits=5))
        bufs.append(gap)
    # baby chirp
    t   = np.linspace(0, 0.16, int(SR * 0.16))
    ph  = 2*np.pi*(1047*t + (1318-1047)*t**2/(2*0.16))
    w   = np.sin(ph)*0.60 + np.sin(ph*2)*0.25
    w   = np.round(w * 32) / 32
    fade = int(0.025 * SR)
    env  = np.ones(len(t))
    env[:fade]  = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    bufs.append((w * env * 0.45 * 32767).astype(np.int16))
    pcm = np.concatenate(bufs)
    return pygame.sndarray.make_sound(np.ascontiguousarray(np.column_stack([pcm, pcm])))


class SoundEngine:
    def __init__(self):
        pygame.mixer.pre_init(SR, -16, 2, 512)
        pygame.mixer.init()

        self.idle = [
            _chirp(440, 494, 0.20, amp=0.28, bits=6),
            _chirp(494, 523, 0.18, amp=0.26, bits=6),
            _chirp(440, 415, 0.22, amp=0.24, bits=6),
            _chirp(523, 494, 0.16, amp=0.27, bits=6, vib=0.005),
        ]
        self.happy     = _seq([(523,784,0.14),(784,1047,0.11)], gap=0.03)
        self.pet       = _chirp(659, 880, 0.12, amp=0.42, bits=5)
        self.sad       = _chirp(440, 330, 0.32, amp=0.30, bits=6)
        self.sleepy    = _chirp(392, 330, 0.40, amp=0.22, bits=7, vib=0.006)
        self.surprised = _chirp(880, 1318, 0.10, amp=0.50, bits=4)
        self.talking   = [
            _seq([(523,587,0.09),(587,523,0.09)], gap=0.02),
            _seq([(494,659,0.08),(659,440,0.10)], gap=0.02),
            _seq([(587,784,0.07),(523,440,0.09)], gap=0.02),
        ]
        self.melody = _make_melody()
        self.birth  = _make_birth_sound()
        self.bump   = _chirp(300, 200, 0.07, amp=0.22, bits=5)   # wall thud

        self._idle_cd   = random.randint(12*25, 22*25)
        self._talk_cd   = 0
        self._melody_cd = random.randint(90*25, 180*25)   # 1.5–3 min between hums

    def tick(self, state):
        self._idle_cd   -= 1
        self._melody_cd -= 1

        if state == 'idle':
            if self._idle_cd <= 0:
                random.choice(self.idle).play()
                self._idle_cd = random.randint(12*25, 24*25)
            if self._melody_cd <= 0:
                self.melody.play()
                self._melody_cd = random.randint(90*25, 180*25)

        if state == 'talking':
            self._talk_cd -= 1
            if self._talk_cd <= 0:
                random.choice(self.talking).play()
                self._talk_cd = random.randint(6, 12)

    def on_enter(self, state):
        if state == 'happy':     self.happy.play()
        elif state == 'sad':     self.sad.play()
        elif state == 'sleepy':  self.sleepy.play()
        elif state == 'surprised': self.surprised.play()
        elif state == 'talking': self._talk_cd = 0

    def play_pet(self):   self.pet.play()
    def play_birth(self): self.birth.play()
    def play_bump(self):  self.bump.play()


# ── pixel coords in the 440×440 original ──────────────────────────────────
L_EYE = (190, 190, 229, 249)
R_EYE = (260, 190, 299, 249)
FACE  = (228, 181, 66)
DARK  = (14, 11, 8)
BRW_Y = 178
L_BRW = (193, 229)
R_BRW = (263, 299)


# ── frame utilities ────────────────────────────────────────────────────────

def remove_bg(pil_img):
    img  = pil_img.convert('RGBA')
    data = img.load()
    br, bg2, bb = BG
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = data[x, y]
            if abs(r-br) < TOL and abs(g-bg2) < TOL and abs(b-bb) < TOL:
                data[x, y] = (0, 0, 0, 0)
    return img


def to_cairo(pil_rgba):
    scaled = pil_rgba.resize(
        (int(pil_rgba.width * SCALE), int(pil_rgba.height * SCALE)),
        Image.NEAREST)
    raw  = scaled.tobytes('raw', 'BGRa')
    surf = cairo.ImageSurface.create_for_data(
        bytearray(raw), cairo.FORMAT_ARGB32,
        scaled.width, scaled.height, scaled.width * 4)
    return surf


def fill_eyes(draw, colour):
    draw.rectangle(L_EYE, fill=colour)
    draw.rectangle(R_EYE, fill=colour)


def draw_brows(draw, style='flat'):
    lx1, lx2 = L_BRW
    rx1, rx2 = R_BRW
    if style == 'flat':
        draw.line([(lx1, BRW_Y),    (lx2, BRW_Y)],    fill=DARK, width=5)
        draw.line([(rx1, BRW_Y),    (rx2, BRW_Y)],    fill=DARK, width=5)
    elif style == 'raised':
        draw.line([(lx1, BRW_Y-8),  (lx2, BRW_Y-10)], fill=DARK, width=5)
        draw.line([(rx1, BRW_Y-10), (rx2, BRW_Y-8)],  fill=DARK, width=5)
    elif style == 'sad':
        draw.line([(lx1, BRW_Y-4),  (lx2, BRW_Y-12)], fill=DARK, width=5)
        draw.line([(rx1, BRW_Y-12), (rx2, BRW_Y-4)],  fill=DARK, width=5)
    elif style == 'angry':
        draw.line([(lx1, BRW_Y-12), (lx2, BRW_Y-4)],  fill=DARK, width=5)
        draw.line([(rx1, BRW_Y-4),  (rx2, BRW_Y-12)], fill=DARK, width=5)


def make_blink(base):
    img = base.copy(); draw = ImageDraw.Draw(img)
    fill_eyes(draw, FACE)
    midy = (L_EYE[1] + L_EYE[3]) // 2
    draw.line([(L_EYE[0]+4, midy), (L_EYE[2]-4, midy)], fill=DARK, width=5)
    draw.line([(R_EYE[0]+4, midy), (R_EYE[2]-4, midy)], fill=DARK, width=5)
    return img


def make_happy(base):
    img = base.copy(); draw = ImageDraw.Draw(img)
    fill_eyes(draw, FACE)
    pad = 4
    draw.arc([L_EYE[0]+pad, L_EYE[1]+pad, L_EYE[2]-pad, L_EYE[3]-pad], 180, 360, fill=DARK, width=6)
    draw.arc([R_EYE[0]+pad, R_EYE[1]+pad, R_EYE[2]-pad, R_EYE[3]-pad], 180, 360, fill=DARK, width=6)
    draw_brows(draw, 'raised')
    return img


def make_sleepy(base):
    img = base.copy(); draw = ImageDraw.Draw(img)
    lid_bottom = L_EYE[1] + int((L_EYE[3] - L_EYE[1]) * 0.55)
    draw.rectangle([L_EYE[0], L_EYE[1], L_EYE[2], lid_bottom], fill=FACE)
    draw.rectangle([R_EYE[0], R_EYE[1], R_EYE[2], lid_bottom], fill=FACE)
    draw.line([(L_EYE[0]+2, lid_bottom), (L_EYE[2]-2, lid_bottom)], fill=DARK, width=5)
    draw.line([(R_EYE[0]+2, lid_bottom), (R_EYE[2]-2, lid_bottom)], fill=DARK, width=5)
    draw_brows(draw, 'sad')
    return img


def make_sad(base):
    img = base.copy(); draw = ImageDraw.Draw(img)
    pad = 4
    draw.rectangle([L_EYE[0]+pad, L_EYE[1]+pad, L_EYE[2]-pad, L_EYE[3]-pad], fill=(255,255,255))
    draw.rectangle([R_EYE[0]+pad, R_EYE[1]+pad, R_EYE[2]-pad, R_EYE[3]-pad], fill=(255,255,255))
    pw = (L_EYE[2]-L_EYE[0])//2; ph = (L_EYE[3]-L_EYE[1])//2
    draw.rectangle([L_EYE[0]+4, L_EYE[1]+ph, L_EYE[0]+4+pw, L_EYE[3]-2], fill=DARK)
    draw.rectangle([R_EYE[0]+4, R_EYE[1]+ph, R_EYE[0]+4+pw, R_EYE[3]-2], fill=DARK)
    draw_brows(draw, 'sad')
    return img


def make_surprised(base):
    img = base.copy(); draw = ImageDraw.Draw(img)
    pad = 6
    draw.rectangle([L_EYE[0]-pad, L_EYE[1]-pad, L_EYE[2]+pad, L_EYE[3]+pad], fill=(255,255,255))
    draw.rectangle([R_EYE[0]-pad, R_EYE[1]-pad, R_EYE[2]+pad, R_EYE[3]+pad], fill=(255,255,255))
    cly = (L_EYE[1]+L_EYE[3])//2
    clx = (L_EYE[0]+L_EYE[2])//2; crx = (R_EYE[0]+R_EYE[2])//2; r = 12
    draw.ellipse([clx-r, cly-r, clx+r, cly+r], fill=DARK)
    draw.ellipse([crx-r, cly-r, crx+r, cly+r], fill=DARK)
    draw.ellipse([clx+4, cly-10, clx+10, cly-4], fill=(255,255,255))
    draw.ellipse([crx+4, cly-10, crx+10, cly-4], fill=(255,255,255))
    draw_brows(draw, 'raised')
    return img


def load_sprites():
    gif = Image.open(GIF_PATH)
    frames = []
    for i in range(gif.n_frames):
        gif.seek(i)
        frames.append(remove_bg(gif.convert('RGBA')))
    base_closed = frames[0]
    base_open   = frames[5]
    sprites = {
        'idle':      [to_cairo(base_closed)],
        'walk':      [to_cairo(base_closed)],
        'blink':     [to_cairo(make_blink(base_closed))],
        'happy':     [to_cairo(make_happy(base_closed))],
        'sleepy':    [to_cairo(make_sleepy(base_closed))],
        'sad':       [to_cairo(make_sad(base_closed))],
        'surprised': [to_cairo(make_surprised(base_open))],
        'talking':   [to_cairo(f) for f in frames],
    }
    fw = sprites['idle'][0].get_width()
    fh = sprites['idle'][0].get_height()
    return sprites, fw, fh


# ── state machine ──────────────────────────────────────────────────────────

TRANSITIONS = {
    # (next_state, min_ticks, max_ticks, weight)
    'idle':  [('idle', 6*25,14*25,55), ('blink',0,0,22),
              ('walk', 5*25,12*25,16), ('sleepy',4*25,8*25,5),
              ('sad',  3*25, 6*25,  1), ('talking',3*25,6*25,1)],
    'walk':  [('idle', 1,1,44), ('walk',4*25,10*25,38),
              ('blink',0,0,14), ('surprised',0,0,3), ('talking',3*25,5*25,1)],
    'blink':     [('idle',2,2,1)],
    'happy':     [('idle',3*25,4*25,1)],
    'sleepy':    [('idle',1,1,1)],
    'sad':       [('idle',1,1,1)],
    'surprised': [('idle',2*25,3*25,1)],
    'talking':   [('idle',1,1,1)],
}

TRANSITIONS_NIGHT = {
    'idle':  [('idle',10*25,22*25,28), ('blink',0,0,22),
              ('walk', 2*25, 6*25,  8), ('sleepy',6*25,14*25,38),
              ('sad',  3*25, 6*25,  1), ('talking',3*25,5*25, 1)],
    'walk':  [('idle', 1,1,55), ('walk',2*25,5*25,20),
              ('blink',0,0,18), ('surprised',0,0,1), ('talking',3*25,5*25,1)],
    'blink':     [('idle',2,2,1)],
    'happy':     [('idle',3*25,4*25,1)],
    'sleepy':    [('idle',1,1,1)],
    'sad':       [('idle',1,1,1)],
    'surprised': [('idle',2*25,3*25,1)],
    'talking':   [('idle',1,1,1)],
}


# Preset 2-D walk directions (unit-ish vectors): pure H, pure V, and diagonals
_WALK_DIRS = [
    ( 1.000,  0.000), (-1.000,  0.000),   # pure horizontal
    ( 0.000,  1.000), ( 0.000, -1.000),   # pure vertical
    ( 0.707,  0.707), (-0.707,  0.707),   # 45° diagonals
    ( 0.707, -0.707), (-0.707, -0.707),
    ( 0.894,  0.447), (-0.894,  0.447),   # shallow diagonals
    ( 0.894, -0.447), (-0.894, -0.447),
    ( 0.447,  0.894), (-0.447,  0.894),   # steep diagonals
    ( 0.447, -0.894), (-0.447, -0.894),
]


class StateMachine:
    def __init__(self, snd=None):
        self.state      = 'idle'
        self.timer      = random.randint(8*25, 14*25)
        self.frame_i    = 0
        self.frame_cd   = 6
        self.walk_vx    = 1.0   # horizontal unit component
        self.walk_vy    = 0.0   # vertical unit component
        self.walk_dir   = 1     # sign of walk_vx (for sprite mirror flip)
        self.snd        = snd
        self.idle_ticks = 0

    def tick(self, sprites):
        self.frame_cd -= 1
        if self.frame_cd <= 0:
            frames        = sprites[self.state]
            self.frame_i  = (self.frame_i + 1) % len(frames)
            self.frame_cd = 3 if self.state == 'talking' else 8

        self.idle_ticks = (self.idle_ticks + 1) if self.state == 'idle' else 0

        self.timer -= 1
        if self.timer <= 0:
            self._transition(self.snd)

    def _transition(self, snd=None):
        table = TRANSITIONS_NIGHT if is_night() else TRANSITIONS
        opts  = table[self.state]
        total = sum(o[3] for o in opts)
        r, acc = random.random() * total, 0
        for nxt, mn, mx, w in opts:
            acc += w
            if r <= acc:
                if nxt == 'walk':
                    vx, vy = random.choice(_WALK_DIRS)
                    self.walk_vx  = vx
                    self.walk_vy  = vy
                    self.walk_dir = 1 if vx >= 0 else -1
                self.state   = nxt
                self.timer   = random.randint(max(1, mn), max(1, mx))
                self.frame_i = 0
                if snd: snd.on_enter(nxt)
                return

    def pet(self, snd=None):
        self.state, self.timer, self.frame_i = 'happy', random.randint(3*25, 4*25), 0
        if snd: snd.play_pet()

    def surprise(self, snd=None):
        self.state, self.timer, self.frame_i = 'surprised', random.randint(2*25, 3*25), 0
        if snd: snd.on_enter('surprised')

    def walk_toward(self, direction):
        # pick from directions whose horizontal component matches the hint
        candidates = [d for d in _WALK_DIRS if (d[0] > 0) == (direction > 0) and d[0] != 0]
        vx, vy = random.choice(candidates)
        self.walk_vx  = vx
        self.walk_vy  = vy
        self.walk_dir = direction
        self.state    = 'walk'
        self.timer    = random.randint(4*25, 9*25)
        self.frame_i  = 0

    def current_surface(self, sprites):
        frames = sprites[self.state]
        return frames[self.frame_i % len(frames)]


# ── GTK window ────────────────────────────────────────────────────────────

class Thronglet(Gtk.Window):
    def __init__(self, start_x=None, start_y=None):
        super().__init__()
        print("Loading sprites…")
        self.sprites, self.fw, self.fh = load_sprites()
        print("Initialising sounds…")
        self.snd        = SoundEngine()
        self.sm         = StateMachine(snd=self.snd)
        self.tick_n     = 0
        self.squish     = 0.0
        self.hunger     = 100
        self.care_score = 0
        self.walk_x     = 0.0
        self.walk_y     = 0.0
        self._drag      = False
        self._press_x   = self._press_y = self._press_t = 0
        self._start_x   = start_x
        self._start_y   = start_y
        self._attract_cd = 0    # ticks until next cursor-attraction check

        self._setup()
        GLib.timeout_add(40,    self._tick)
        GLib.timeout_add(90000, self._get_hungry)

    def _setup(self):
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_default_size(WIN_W, WIN_H)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        vis = self.get_screen().get_rgba_visual()
        if vis: self.set_visual(vis)

        self.da = Gtk.DrawingArea()
        self.da.connect('draw', self._draw)
        self.add(self.da)

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect('button-press-event',   self._on_press)
        self.connect('button-release-event', self._on_release)
        self.connect('motion-notify-event',  self._on_motion)
        self.show_all()
        GLib.idle_add(self._reposition)

    def _reposition(self):
        if self._start_x is not None:
            self.move(self._start_x, self._start_y)
            self.walk_x = float(self._start_x)
            self.walk_y = float(self._start_y)
        else:
            sc = self.get_screen()
            sx = sc.get_width()  - WIN_W - 80
            sy = sc.get_height() - WIN_H - 60
            self.move(sx, sy)
            self.walk_x = float(sx)
            self.walk_y = float(sy)
        return False

    # ── events ────────────────────────────────────────────────────────────

    def _on_press(self, w, e):
        if e.button == 3:
            self._show_menu(e); return
        self._drag = False
        self._press_x, self._press_y, self._press_t = e.x_root, e.y_root, e.time

    def _on_release(self, w, e):
        if e.button == 1 and not self._drag:
            self.sm.pet(self.snd)
            self.squish     = 1.0
            self.hunger     = min(100, self.hunger + 30)
            self.care_score = min(REPRODUCE_AT, self.care_score + 15)
            self._check_reproduce()
        else:
            # sync float position after WM drag so walking resumes from correct spot
            wx, wy = self.get_position()
            self.walk_x = float(wx)
            self.walk_y = float(wy)
        self._drag = False

    def _on_motion(self, w, e):
        if e.state & Gdk.ModifierType.BUTTON1_MASK and not self._drag:
            if abs(e.x_root - self._press_x) > 4 or abs(e.y_root - self._press_y) > 4:
                self._drag = True
                self.begin_move_drag(1, int(self._press_x), int(self._press_y), self._press_t)

    def _show_menu(self, e):
        m = Gtk.Menu()
        for label, fn in [('Release thronglet', Gtk.main_quit)]:
            i = Gtk.MenuItem(label=label)
            i.connect('activate', lambda *_, f=fn: f())
            m.append(i)
        m.show_all()
        m.popup_at_pointer(e)

    # ── timers ────────────────────────────────────────────────────────────

    def _tick(self):
        self.tick_n += 1
        self.sm.tick(self.sprites)
        self.snd.tick(self.sm.state)

        if self.squish > 0:
            self.squish = max(0.0, self.squish - 0.07)
        if random.random() < 0.0003:
            self.sm.surprise(self.snd)

        # cursor attraction — check every 5–12s when idle for >5s
        if self.sm.state == 'idle':
            self._attract_cd -= 1
        if self.sm.idle_ticks > 125 and self._attract_cd <= 0:
            self._try_attract_cursor()
            self._attract_cd = random.randint(5*25, 12*25)

        # walking — 2-D movement with wall bouncing
        if self.sm.state == 'walk' and not self._drag:
            sc    = self.get_screen()
            sw    = sc.get_width()
            sh    = sc.get_height()
            speed = WALK_NIGHT if is_night() else WALK_SPEED
            self.walk_x += speed * self.sm.walk_vx
            self.walk_y += speed * self.sm.walk_vy

            bounced = False
            if self.walk_x < 0:
                self.walk_x  = 0
                self.sm.walk_vx  = abs(self.sm.walk_vx)
                self.sm.walk_dir = 1
                bounced = True
            elif self.walk_x > sw - WIN_W:
                self.walk_x  = sw - WIN_W
                self.sm.walk_vx  = -abs(self.sm.walk_vx)
                self.sm.walk_dir = -1
                bounced = True

            if self.walk_y < 0:
                self.walk_y      = 0
                self.sm.walk_vy  = abs(self.sm.walk_vy)
                bounced = True
            elif self.walk_y > sh - WIN_H:
                self.walk_y      = sh - WIN_H
                self.sm.walk_vy  = -abs(self.sm.walk_vy)
                bounced = True

            if bounced:
                self.squish = 0.55
                self.snd.play_bump()

            self.move(int(self.walk_x), int(self.walk_y))

        self.da.queue_draw()
        return True

    def _try_attract_cursor(self):
        try:
            display = Gdk.Display.get_default()
            seat    = display.get_default_seat()
            pointer = seat.get_pointer()
            _, mx, _my = pointer.get_position()
            wx, _wy = self.get_position()
            cx   = wx + WIN_W // 2
            dist = abs(mx - cx)
            if dist > 180:
                self.sm.walk_toward(1 if mx > cx else -1)
        except Exception:
            pass

    def _get_hungry(self):
        self.hunger = max(0, self.hunger - 10)
        if self.hunger > 60:
            self.care_score = min(REPRODUCE_AT, self.care_score + 5)
            self._check_reproduce()
        if self.hunger < 30 and random.random() < 0.4:
            self.sm.state = 'sad'
            self.sm.timer = 4*25
        return True

    def _check_reproduce(self):
        if self.care_score >= REPRODUCE_AT:
            self.care_score = 0
            self._spawn_child()

    def _spawn_child(self):
        wx, wy = self.get_position()
        child_x = max(0, wx - WIN_W - 15)
        subprocess.Popen(
            [sys.executable, __file__, '--child', str(child_x), str(wy)],
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        self.snd.play_birth()
        self.sm.state, self.sm.timer, self.sm.frame_i = 'happy', 5*25, 0

    # ── drawing ───────────────────────────────────────────────────────────

    def _draw(self, widget, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        t       = self.tick_n
        night   = is_night()
        walking = self.sm.state == 'walk'

        bob_freq = 0.28 if walking else 0.13
        bob_amp  = 5.0  if walking else 3.0
        bob  = math.sin(t * bob_freq) * bob_amp
        sqx  = 1.0 + self.squish * 0.10
        sqy  = 1.0 - self.squish * 0.14
        cx   = WIN_W / 2
        cy   = WIN_H / 2

        surf  = self.sm.current_surface(self.sprites)
        alpha = 0.72 if night else 1.0

        # sprite
        cr.save()
        cr.translate(cx, cy + bob)
        cr.scale(sqx, sqy)
        if walking and self.sm.walk_dir == -1:
            cr.scale(-1, 1)
        cr.translate(-self.fw / 2, -self.fh / 2)
        cr.set_source_surface(surf, 0, 0)
        cr.paint_with_alpha(alpha)
        cr.restore()

        # night tint — cool blue wash
        if night:
            cr.save()
            cr.translate(cx, cy + bob)
            cr.scale(self.fw / 2 + 4, self.fh / 2 + 4)
            cr.arc(0, 0, 1, 0, 2 * math.pi)
            cr.restore()
            cr.set_source_rgba(0.30, 0.40, 0.80, 0.13)
            cr.fill()

        # shadow
        sy  = cy + self.fh / 2 + bob + 2
        sh_a = 0.16 if night else 0.25
        pat = cairo.RadialGradient(cx, sy, 2, cx, sy, 26)
        pat.add_color_stop_rgba(0, 0, 0, 0, sh_a)
        pat.add_color_stop_rgba(1, 0, 0, 0, 0)
        cr.set_source(pat)
        cr.save()
        cr.translate(cx, sy); cr.scale(1.0, 0.20)
        cr.arc(0, 0, 26, 0, 2 * math.pi)
        cr.restore(); cr.fill()

        # hunger indicator
        if self.hunger < 30:
            pulse = 0.5 + 0.5 * abs(math.sin(t * 0.20))
            cr.set_source_rgba(0.95, 0.12, 0.12, pulse)
            cr.select_font_face('sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(14)
            cr.move_to(cx - 3, cy - self.fh / 2 + bob - 4)
            cr.show_text('!')

        # pink glow as care_score approaches reproduction threshold
        if self.care_score > 140:
            glow  = (self.care_score - 140) / float(REPRODUCE_AT - 140)
            pulse = 0.5 + 0.5 * math.sin(t * 0.15)
            cr.save()
            cr.translate(cx, cy + bob)
            cr.scale(self.fw / 2 + 10, self.fh / 2 + 10)
            cr.arc(0, 0, 1, 0, 2 * math.pi)
            cr.restore()
            cr.set_source_rgba(1.0, 0.70, 0.85, glow * 0.38 * pulse)
            cr.fill()


def main():
    start_x = start_y = None
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] == '--child':
        try:
            start_x, start_y = int(args[1]), int(args[2])
        except ValueError:
            pass

    Gtk.init([])
    win = Thronglet(start_x=start_x, start_y=start_y)
    win.connect('destroy', Gtk.main_quit)
    Gtk.main()


if __name__ == '__main__':
    main()

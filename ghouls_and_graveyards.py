import os, sys, math, random, threading, tempfile, wave, struct, time
import importlib, subprocess
from array import array
VERSION = "1.5"
debug_mode = False 

def _ensure(module, pip_name=None):
    try:
        return importlib.import_module(module)
    except ImportError:
        pass
    if getattr(sys, "frozen", False): return None
    base = [sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", pip_name or module]
    for extra in ([], ["--user"], ["--break-system-packages"], ["--user", "--break-system-packages"]):
        try:
            r = subprocess.run(base + extra, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            return None
        if r.returncode == 0:
            importlib.invalidate_caches()
            try: return importlib.import_module(module)
            except ImportError: pass
    return None


_ensure("PIL", "pillow")
_ensure("miniaudio")
import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageTk, ImageOps

def _resource_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR  = _resource_dir()
SOUND_DIR = os.path.join(BASE_DIR, "data", "sounds")
IMG_DIR   = os.path.join(BASE_DIR, "data", "shapes")

ROWS, COLS   = 8, 8
GAP          = 10
TILE         = 50
CELL         = TILE + GAP
WALL_T       = GAP
PAD          = 36
TITLE_H      = 60
GRID_BOTTOM  = TITLE_H + PAD + ROWS*CELL - GAP
BOARD_W      = PAD*2 + COLS*CELL - GAP
BOARD_H      = GRID_BOTTOM + PAD + 20
PANEL_W      = 340
TRAY_W       = PANEL_W - 26
STEP_W       = 288

MAP_BG       = "#2a2a2e"

MAX_WALLS        = 50
EXTRA_PASSAGES   = 12
MIN_TREAS_DIST   = 3
MIN_GHOST_TREAS  = 3
DRAGON_WAKE_DIST = 3
DRAGON_WAKE_RADIUS = 3
STEPS_BY_LIVES   = {3: 8, 2: 6, 1: 4, 0: 0}
TREASURE_STEPS   = 4
DOOR_COUNT       = 8
DOOR_TURNS       = (3, 9)
START_STRENGTH   = 50
STRENGTH_LOSS    = (1, 3)
RENEW_MOVES      = (12, 30)
ATTACK_DELAY_MS  = 600
DOOR_OUCH_PITCH  = 0.88

DELTA = {"n": (-1,0), "s": (1,0), "e": (0,1), "w": (0,-1)}
OPP   = {"n":"s", "s":"n", "e":"w", "w":"e"}
DIRS  = list(DELTA.keys())
CELLS = [(r, c) for r in range(ROWS) for c in range(COLS)]

def in_grid(r, c): return 0 <= r < ROWS and 0 <= c < COLS
def step(r, c, d): return r + DELTA[d][0], c + DELTA[d][1]
def manhattan(r1, c1, r2, c2): return abs(r1-r2) + abs(c1-c2)

def dragon_distance(r1, c1, r2, c2):
    return max(abs(r1-r2), abs(c1-c2))

def neighbors(r, c):
    for d in DIRS:
        nr, nc = step(r, c, d)
        if in_grid(nr, nc): yield d, nr, nc

def far_cells(rules):
    return [(r, c) for r, c in CELLS if all(dragon_distance(r, c, *a) >= dist for a, dist in rules)]

C = dict(
    bg           = "#160c08",
    map_bg       = MAP_BG,
    wall_col     = "#fe6429",
    hot          = "#ff8454",
    door_col     = "#c87820",
    treasure_col = "#ffd700",
    ghost_col    = "#ccccff",
    base_p1      = "#00aa00",
    base_p2      = "#2266dd",
    panel_bg     = "#100c08",
    card_bg      = "#1a100a",
    panel_border = "#5a1400",
    panel_sep    = "#3a1800",
    text_col     = "#ddd0b0",
    label_col    = "#7a6040",
    highlight    = "#ffcc44",
    dim_col      = "#4a3820",
    btn_bg       = "#1e1008",
    btn_fg       = "#c09060",
    btn_hover    = "#3a1a06",
    heart_on     = "#cc2222",
    heart_off    = "#2e1010",
    end_box      = "#0d0608",
    active_border= "#ffcc44",
    bad          = "#ff7766",
)

SND_FILES = {
    "tik":           ["2_sayit-tik.wav.mp3",           "11_nat-tik.wav.mp3"],
    "no":            ["3_sayit-no.wav.mp3",             "12_nat-no.wav.mp3"],
    "hitawall":      ["4_sayit-hitawall.wav.mp3",       "13_nat-hitawall.wav.mp3"],
    "ghostmoves":    ["5_sayit-ghostmoves.wav.mp3",     "14_nat-ghostmoves.wav.mp3"],
    "ghostawakes":   ["6_sayit-ghostawakes.wav.mp3",    "15_nat-ghostawakes.wav.mp3"],
    "ghostattacks":  ["7_sayit-ghostattacks.wav.mp3",   "16_nat-ghostattacks.wav.mp3"],
    "gameover":      ["8_sayit-gameover.wav.mp3",       "17_nat-gameover.wav.mp3"],
    "foundtreasure": ["9_sayit-foundtreasure.wav.mp3",  "18_nat-foundtreasure.wav.mp3"],
    "youwin":        ["1_sayit-youwin.wav.mp3",         "10_nat-youwin.wav.mp3"],
}
TIPS = {
    "r0": "Player 1's Secret Room. Drag it onto the map; you can keep moving it until the game starts. "
          "The ghost can't find you inside your own room, but you are not safe in your opponent's.",
    "r1": "Player 2's Secret Room. It lights up once Player 1's room is on the map; then drag it on too. "
          "You can keep moving it until the game starts. "
          "The ghost can't find you inside your own room, but you are not safe in your opponent's.",
    "g":  "Ghost marker (active once the game has started). Drag it onto the map to mark where you think "
          "the ghost is. It can't be removed, "
          "only moved. It also lands by itself on the tile where the ghost attacks.",
    "start": "Start the game. One Secret Room on the map = 1-player game; two rooms = 2-player game. "
             "The dungeon and the treasure room are generated when you press it.",
    "end":   "End your turn now (Space, or right-click on the map).",
    "l1":    "New Level 1 game: a new random dungeon every game, built like the original (ROM) one.",
    "walls": "Wall mode. Auto: bumped walls are drawn for you. Manual: nothing is drawn; click the gap between two tiles "
             "to place a wall marker yourself (click again: a door marker on Level 2; once more to remove it). Can only be changed between games.",
    "l2":    "New Level 2 game: magic doors close and reopen at random as the turns go by. "
             "You only find one by bumping into it.",
    "voice": "Switch the announcer between the synthesised and the natural voice.",
    "locked": " Locked: Secret Rooms can't be moved once the game has started.",
}
CAPTIONS = {
    "tik":           "",
    "no":            "Not there: you can only move to a neighbouring tile.",
    "hitawall":      "Ouch! A wall. Your turn ends.",
    "ghostmoves":    "The ghost moves.",
    "ghostawakes":   "The ghost awakes!",
    "ghostattacks":  "The ghost attacks!",
    "gameover":      "Game over.",
    "foundtreasure": "You found the treasure!",
    "youwin":        "You win!",
    "endturn":       "Turn ended.",
    "doorvanish":    "A passage seals…",
    "doorappear":    "A passage opens!",
}

WARRIOR_TUNES = {
    0: [(523, .13), (659, .13), (784, .13), (1047, .42)],
    1: [(392, .13), (494, .13), (587, .13), (784, .13), (988, .42)],
}


def _warrior_tune_path(idx):
    try:
        d = os.path.join(tempfile.gettempdir(), "ghouls_tunes")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"warrior{idx+1}.wav")
        if not os.path.exists(path):
            rate = 22050; frames = bytearray()
            for freq, dur in WARRIOR_TUNES[idx]:
                n = int(rate * dur)
                for k in range(n):
                    env = min(1.0, k / (rate * 0.01)) * math.exp(-3.0 * k / n)
                    v = 0.5*math.sin(2*math.pi*freq*k/rate) + 0.2*math.sin(4*math.pi*freq*k/rate)
                    frames += struct.pack("<h", int(32767 * 0.6 * env * v))
            with wave.open(path, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
                w.writeframes(bytes(frames))
        return path
    except Exception:
        return None


def _sword_clash_path():
    try:
        d = os.path.join(tempfile.gettempdir(), "ghouls_tunes")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "swordfight.wav")
        if not os.path.exists(path):
            rate = 22050
            hits = [(0.00, 1650, 0.8, 0.22), (0.17, 1900, 0.9, 0.22), (0.31, 1500, 0.8, 0.22),
                    (0.50, 2100, 1.0, 0.45)]
            partials = [(1.00, 1.0), (1.58, 0.7), (2.76, 0.55), (4.07, 0.35), (5.43, 0.2)]
            total = int(rate * 1.05)
            buf = [0.0] * total
            rnd = random.Random(7)
            for t0, f0, amp, ring in hits:
                start = int(t0 * rate); n = int(ring * rate)
                prev = 0.0
                for k in range(n):
                    if start + k >= total: break
                    t = k / rate
                    tone = sum(a * math.sin(2*math.pi*f0*r*t) for r, a in partials)
                    tone *= math.exp(-t * 7.0 / ring) * min(1.0, k / (rate * 0.0008))
                    x = rnd.uniform(-1, 1)
                    noise = (x - prev) * math.exp(-t * 400.0)
                    prev = x
                    buf[start + k] += amp * (0.22 * tone + 0.5 * noise)
            peak = max(abs(v) for v in buf) or 1.0
            frames = b"".join(struct.pack("<h", int(32767 * 0.7 * v / peak)) for v in buf)
            with wave.open(path, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
                w.writeframes(frames)
        return path
    except Exception:
        return None


def _build_audio_backend():
    miniaudio = _ensure("miniaudio")
    if miniaudio is None:
        print("[audio] miniaudio not available", file=sys.stderr)
        return (lambda paths, priority=False, append=False, pitch=1.0: None), (lambda: False), (lambda: False)

    import traceback
    RATE, CH = 44100, 2
    lock = threading.Lock()
    state = {"q": [], "pos": 0, "prio": False}
    cache = {}
    ready = threading.Event(); ok = {"v": False}
    gap = array("h", [0]) * int(RATE * CH * 0.12)

    def load(path, pitch=1.0):
        decode_rate = RATE if pitch == 1.0 else max(RATE, int(round(RATE / pitch)))
        key = (path, decode_rate)
        s = cache.get(key)
        if s is None:
            try:
                dec = miniaudio.decode_file(path, output_format=miniaudio.SampleFormat.SIGNED16, nchannels=CH, sample_rate=decode_rate)
                s = array("h"); s.frombytes(bytes(dec.samples) if not isinstance(dec.samples, array) else dec.samples.tobytes())
                cache[key] = s
            except Exception:
                print("[audio] cannot decode", path, file=sys.stderr); traceback.print_exc()
                return array("h")
        return s

    def stream():
        required = yield b""
        while True:
            n = required * CH
            out = array("h")
            try:
                with lock:
                    q = state["q"]
                    while len(out) < n and q:
                        cur = q[0]; pos = state["pos"]
                        chunk = cur[pos:pos + n - len(out)]
                        out.extend(chunk); pos += len(chunk)
                        if pos >= len(cur): q.pop(0); state["pos"] = 0
                        else: state["pos"] = pos
                    if not q:
                        state["prio"] = False
            except Exception:
                traceback.print_exc()
            if len(out) < n: out.extend(array("h", [0]) * (n - len(out)))
            required = yield out

    def engine():
        try:
            dev = miniaudio.PlaybackDevice(output_format=miniaudio.SampleFormat.SIGNED16, nchannels=CH, sample_rate=RATE, buffersize_msec=40)
            gen = stream(); next(gen); dev.start(gen)
            ok["v"] = True; ready.set()
            for files in SND_FILES.values():
                for f in files: load(os.path.join(SOUND_DIR, f))
            while True: time.sleep(3600)
        except Exception:
            print("[audio] audio device failed", file=sys.stderr); traceback.print_exc()
            ready.set()

    threading.Thread(target=engine, daemon=True).start()
    ready.wait(3)

    if not ok["v"]:
        return (lambda paths, priority=False, append=False, pitch=1.0: None), (lambda: False), (lambda: False)

    def play(paths, priority=False, append=False, pitch=1.0):
        if isinstance(paths, str): paths = [paths]
        paths = [p for p in paths if p and os.path.exists(p)]
        parts = []
        for i, p in enumerate(paths):
            if i: parts.append(gap)
            parts.append(load(p, pitch=pitch))
        with lock:
            if append and parts and state["q"]:
                state["q"].extend([gap] + parts); state["prio"] = True; return
            if paths and not priority and state["prio"] and state["q"]: return
            state["q"] = parts; state["pos"] = 0; state["prio"] = bool(priority and parts)

    def busy():
        with lock: return bool(state["q"])

    def prio_busy():
        with lock: return bool(state["q"]) and state["prio"]

    return play, busy, prio_busy

_audio_play, _audio_busy, _audio_prio_busy = _build_audio_backend()


class SoundQueue:
    def __init__(self, root, voice="Robo"):
        self.root = root; self.voice = voice
        self.on_caption = lambda s: None
        self.GHOST_KEYS = ("ghostawakes", "ghostattacks", "ghostmoves")

    def _path(self, key):
        files = SND_FILES.get(key, [])
        if not files: return None
        idx = 0 if self.voice == "Robo" else 1
        return os.path.join(SOUND_DIR, files[idx] if idx < len(files) else files[0])

    def push(self, key, pitch=1.0):
        cap = CAPTIONS.get(key, "")
        if cap: self.on_caption(cap)
        if key == "gameover":
            _audio_play([self._path(key)], priority=True, append=True, pitch=pitch); return
        _audio_play([self._path(key)], priority=key in self.GHOST_KEYS, pitch=pitch)

    def push_duel(self, winner_idx, caption):
        self.on_caption(caption)
        _audio_play([_sword_clash_path(), self._path("foundtreasure")])

    def clear(self): _audio_play([], priority=True)
    def busy(self): return _audio_busy()
    def prio_busy(self): return _audio_prio_busy()


class SpriteCache:
    def __init__(self):
        self._raw = {}; self._cache = {}

    def _load(self, num):
        if num not in self._raw:
            path = os.path.join(IMG_DIR, f"{num}.png")
            try:
                self._raw[num] = Image.open(path).convert("RGBA") if os.path.exists(path) else None
            except Exception:
                self._raw[num] = None
        return self._raw[num]

    def get_fit(self, num, max_w, max_h, rot=0, flip=False):
        img = self._load(num)
        if img is None: return None
        key = (num, max_w, max_h, rot, flip)
        if key not in self._cache:
            im = img
            if rot: im = im.rotate(rot, expand=True)
            if flip: im = ImageOps.flip(im)
            iw, ih = im.size
            s = min(max_w / iw, max_h / ih)
            size = (max(1, int(iw*s)), max(1, int(ih*s)))
            self._cache[key] = ImageTk.PhotoImage(im.resize(size, Image.LANCZOS))
        return self._cache[key]

    def get_dim(self, num, max_w, max_h, rot=0, flip=False):
        img = self._load(num)
        if img is None: return None
        key = (num, max_w, max_h, rot, flip, "dim")
        if key not in self._cache:
            im = img
            if rot: im = im.rotate(rot, expand=True)
            if flip: im = ImageOps.flip(im)
            iw, ih = im.size; sc = min(max_w / iw, max_h / ih)
            im = im.convert("RGBA").resize((max(1, int(iw*sc)), max(1, int(ih*sc))), Image.LANCZOS)
            a = im.getchannel("A").point(lambda v: int(v * 0.55))
            g = ImageOps.grayscale(im.convert("RGB")).point(lambda v: int(v * 0.7))
            out = Image.merge("RGBA", (g, g, g, a))
            self._cache[key] = ImageTk.PhotoImage(out)
        return self._cache[key]

    def get_stretch(self, num, w, h):
        img = self._load(num)
        if img is None: return None
        key = (num, w, h, "stretch")
        if key not in self._cache:
            self._cache[key] = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))
        return self._cache[key]

    def get_fit_rot90(self, num, max_w, max_h):
        return self.get_fit(num, max_w, max_h, rot=90)

    def get_fit_rotcw(self, num, max_w, max_h, flip=False):
        return self.get_fit(num, max_w, max_h, rot=-90, flip=flip)

SPRITES = SpriteCache()

SP_FLOOR   = 20
SP_TREAS   = 21
SP_BASE_P1 = 24
SP_BASE_P2 = 25
SP_GHOST   = 26
SP_WALL    = 34
SP_DOOR    = 35
SP_P1      = 36
SP_P2      = 37
SP_TITLE   = 47
SP_STEP_AV = 51
SP_STEP_US = 52
SP_BASE    = (SP_BASE_P1, SP_BASE_P2)
SP_HERO    = (SP_P1, SP_P2)
P_COL      = (C["base_p1"], C["base_p2"])


class Tip:
    def __init__(self, root, font):
        self.root = root; self.font = font; self._win = None; self._job = None; self._key = None

    def schedule(self, key, text, x, y):
        if key == self._key: return
        self.hide(); self._key = key
        if text: self._job = self.root.after(450, lambda: self._show(text, x, y))

    def _show(self, text, x, y):
        self._job = None
        try:
            w = tk.Toplevel(self.root); w.overrideredirect(True)
            tk.Label(w, text=text, font=self.font, bg=C["card_bg"], fg=C["text_col"], justify="left",
                     wraplength=280, padx=10, pady=6, highlightthickness=1,
                     highlightbackground=C["highlight"]).pack()
            w.update_idletasks()
            wd, ht = w.winfo_reqwidth(), w.winfo_reqheight()
            px = x + 16 if x + wd + 24 < self.root.winfo_screenwidth() else x - wd - 16
            py = y + 18 if y + ht + 30 < self.root.winfo_screenheight() else y - ht - 12
            w.geometry(f"+{max(0, px)}+{max(0, py)}")
            self._win = w
        except Exception:
            self._win = None

    def hide(self):
        if self._job: self.root.after_cancel(self._job); self._job = None
        if self._win is not None:
            try: self._win.destroy()
            except Exception: pass
            self._win = None
        self._key = None


class FlatButton(tk.Frame):
    def __init__(self, parent, text, command, font, hint="", hint_font=None, primary=False,
                 tip=None, tip_text="", center=False, chars=0):
        super().__init__(parent, bg=C["panel_border"], padx=1, pady=1, cursor="hand2")
        self._cmd = command; self._primary = primary; self._on = True; self._hover = False
        self._active = False; self._tip = tip; self._tip_text = tip_text
        self._in = tk.Frame(self); self._in.pack(fill="x")
        self._lbl = tk.Label(self._in, text=text, font=font, anchor="center" if center else "w", padx=12, pady=7, width=chars)
        if center: self._lbl.pack(side="left", expand=True, fill="x")
        else:      self._lbl.pack(side="left")
        self._hint = tk.Label(self._in, text=hint, font=hint_font or font, padx=10)
        if hint: self._hint.pack(side="right")
        for w in (self, self._in, self._lbl, self._hint):
            w.bind("<Enter>", self._enter); w.bind("<Leave>", self._leave)
            w.bind("<Button-1>", self._click)
        self._paint()

    def _enter(self, e=None):
        self._hover = True; self._paint()
        if self._tip and self._tip_text and e is not None:
            self._tip.schedule(("btn", id(self)), self._tip_text, e.x_root, e.y_root)
    def _leave(self, e=None):
        self._hover = False; self._paint()
        if self._tip: self._tip.hide()
    def _click(self, e=None):
        if self._tip: self._tip.hide()
        if self._on and self._cmd: self._cmd()
    def set_text(self, t): self._lbl.config(text=t)
    def set_tip(self, t): self._tip_text = t
    def set_active(self, on): self._active = on; self._paint()
    def set_enabled(self, on):
        self._on = on; self.config(cursor="hand2" if on else ""); self._paint()

    def _paint(self):
        if not self._on:
            bg, fg, hf, bd = C["panel_sep"], C["dim_col"], C["dim_col"], C["panel_sep"]
        elif self._primary:
            bg = C["hot"] if self._hover else C["wall_col"]
            fg, hf, bd = C["bg"], C["panel_border"], bg
        else:
            bg = C["btn_hover"] if self._hover else C["btn_bg"]
            fg = C["highlight"] if (self._hover or self._active) else C["btn_fg"]
            hf = C["label_col"]
            bd = C["highlight"] if self._active else C["panel_border"]
        self.config(bg=bd); self._in.config(bg=bg)
        self._lbl.config(bg=bg, fg=fg); self._hint.config(bg=bg, fg=hf)


class Cell:
    __slots__ = ("row","col","walls","wall_shown","seen","is_door","door_closed","door_shown")
    def __init__(self, r, c):
        self.row, self.col = r, c
        self.walls       = {d: True  for d in DIRS}
        self.wall_shown  = {d: False for d in DIRS}
        self.seen        = False
        self.is_door     = {d: False for d in DIRS}
        self.door_closed = {d: False for d in DIRS}
        self.door_shown  = {d: False for d in DIRS}

    def passable(self, d): return not self.walls[d] and not self.door_closed[d]
    def open_count(self):  return sum(1 for d in DIRS if not self.walls[d])

def _carve(grid, r, c, d, opened=True):
    nr, nc = step(r, c, d)
    grid[r][c].walls[d] = not opened
    grid[nr][nc].walls[OPP[d]] = not opened

def _walls(grid):
    return [(r, c, d) for r, c in CELLS for d in ("s", "e")
            if in_grid(*step(r, c, d)) and grid[r][c].walls[d]]

def disjoint_paths(grid, src, dst, limit=2):
    cap, adj = {}, {}
    def link(a, b):
        cap[(a, b)] = cap.get((a, b), 0) + 1; cap.setdefault((b, a), 0)
        adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    for r, c in CELLS:
        link(("in", r, c), ("out", r, c))
        for d, nr, nc in neighbors(r, c):
            if grid[r][c].passable(d): link(("out", r, c), ("in", nr, nc))
    s, t = ("out",) + tuple(src), ("in",) + tuple(dst)
    flow = 0
    while flow < limit:
        prev = {s: None}; queue = [s]
        for u in queue:
            for v in adj.get(u, ()):
                if v not in prev and cap[(u, v)] > 0: prev[v] = u; queue.append(v)
        if t not in prev: break
        v = t
        while prev[v] is not None:
            u = prev[v]; cap[(u, v)] -= 1; cap[(v, u)] += 1; v = u
        flow += 1
    return flow

def treasure_ok(grid, treasure, rooms):
    return all(disjoint_paths(grid, rm, treasure) >= 2 for rm in rooms)

def generate_maze(treasure, rooms):
    grid = [[Cell(r, c) for c in range(COLS)] for r in range(ROWS)]
    sr, sc = random.choice(CELLS)
    grid[sr][sc].seen = True
    frontier = [(sr, sc)]
    while frontier:
        i = random.randrange(len(frontier)); r, c = frontier[i]
        nbrs = [(d, nr, nc) for d, nr, nc in neighbors(r, c) if not grid[nr][nc].seen]
        if not nbrs: frontier.pop(i); continue
        d, nr, nc = random.choice(nbrs)
        _carve(grid, r, c, d); grid[nr][nc].seen = True; frontier.append((nr, nc))

    added = attempts = 0
    while added < EXTRA_PASSAGES and len(_walls(grid)) > MAX_WALLS and attempts < 2000:
        attempts += 1
        r, c = random.choice(CELLS); d = random.choice(DIRS); nr, nc = step(r, c, d)
        if in_grid(nr, nc) and grid[r][c].walls[d]: _carve(grid, r, c, d); added += 1

    def score(): return sum(disjoint_paths(grid, rm, treasure) for rm in rooms)
    best = score()
    while best < 2 * len(rooms):
        walls = _walls(grid); random.shuffle(walls)
        if not walls: break
        for r, c, d in walls:
            _carve(grid, r, c, d); s = score()
            if s > best: best = s; break
            _carve(grid, r, c, d, False)
        else:
            _carve(grid, *walls[0]); best = score()

    for r, c in CELLS: grid[r][c].seen = False
    return grid


ROM_TEMPLATES = ["C949409C", "62DC1629", "64C8425E", "0A68A11B", "C4A94629", "52DA0529", "9139C09C",
                 "66A8111B", "C199494C", "C4C9484C", "C49C464C", "191D9919", "9ACC1629", "43DC0948"]
ROM_STRIP_BASES = (0x00, 0x08, 0x40, 0x48)

def rom_maze_ram():
    ram = [0] * 128
    for base in ROM_STRIP_BASES:
        for i, ch in enumerate(random.choice(ROM_TEMPLATES)): ram[base + i] = int(ch, 16)
    ram[random.choice([b + i for b in ROM_STRIP_BASES for i in range(8)])] = 0
    return ram

def grid_from_rom_ram(ram):
    grid = [[Cell(r, c) for c in range(COLS)] for r in range(ROWS)]
    for r, c in CELLS:
        v = ram[(0x40 if c >= 4 else 0) + 4 * (c & 3) + (r >> 1)]; k = (r & 1) * 2
        if c < COLS - 1 and not (v >> k) & 1:       _carve(grid, r, c, "e")
        if r < ROWS - 1 and not (v >> (k + 1)) & 1: _carve(grid, r, c, "s")
    return grid

def _connected(grid):
    seen = {(0, 0)}; stack = [(0, 0)]
    while stack:
        r, c = stack.pop()
        for d, nr, nc in neighbors(r, c):
            if grid[r][c].passable(d) and (nr, nc) not in seen: seen.add((nr, nc)); stack.append((nr, nc))
    return len(seen) == ROWS * COLS

def pick_treasure(cands, rooms):
    by = {}
    for r, c in cands:
        by.setdefault(min(dragon_distance(r, c, *rm) for rm in rooms), []).append((r, c))
    return random.choice(by[random.choice(list(by))])

def generate_rom_level(rooms, tries=400):
    for _ in range(tries):
        grid = grid_from_rom_ram(rom_maze_ram())
        if not _connected(grid): continue
        cands = [(r, c) for r, c in far_cells([(rm, MIN_TREAS_DIST) for rm in rooms])
                 if grid[r][c].open_count() >= 2 and treasure_ok(grid, (r, c), rooms)]
        if cands: return grid, pick_treasure(cands, rooms)
    treasure = pick_treasure(far_cells([(rm, MIN_TREAS_DIST) for rm in rooms]), rooms)
    return generate_maze(treasure, rooms), treasure


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Ghouls & Graveyards {VERSION} by Theruler76")
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, False)
        self._fonts()
        self.tip = Tip(root, self.F["small"])
        self.phase = "title"
        self.num_players = 0; self.difficulty = 1; self.voice = "Robo"
        self.grid = None; self.players = [None, None]; self.cur_p = 0
        self.rooms = [None, None]
        self.dr = self.dc = -1
        self.dragon_awake = False
        self.ghost_fresh = False
        self.tr = self.tc = -1
        self.game_over = False; self.winner = None
        self.reveal_all = False; self.doors = []
        self.manual_walls = False; self.user_walls = {}
        self._attack_job = None
        self._locked = False
        self._ghost_panel_cell = None
        self._ghost_hold = None
        self._press = None; self._drag = None
        self._duel_cell = None
        self._flash_wall_edge = None
        self._tray_slots = []
        self._img_refs = []
        self._panel_img_refs = []
        self._build_ui()
        self.snd = SoundQueue(root, self.voice)
        self.snd.on_caption = lambda t: self._say(t)
        self._show_title()
        self._bind_keys()

    def _fonts(self):
        fams = set(tkfont.families())
        def pick(*cands):
            for f in cands:
                if f in fams: return f
            return cands[-1]
        sans  = pick("Segoe UI", "SF Pro Text", "Helvetica Neue", "Ubuntu", "Noto Sans", "DejaVu Sans", "Arial")
        serif = pick("Palatino Linotype", "Palatino", "Georgia", "Noto Serif", "DejaVu Serif", "Times New Roman")
        self.F = {}
        for name, fam, sz, wt in [
            ("title",  serif, 20, "bold"), ("turn",  serif, 14, "bold"), ("end", serif, 14, "bold"),
            ("h2",     sans,  12, "bold"), ("h3",    sans,  10, "bold"), ("btn", sans,  11, "bold"),
            ("body",   sans,  10, "normal"), ("caption", sans, 11, "normal"),
            ("small",  sans,   9, "normal"), ("hint",  sans,  9, "normal"), ("tiny", sans, 8, "normal"),
        ]:
            self.F[name] = tkfont.Font(family=fam, size=sz, weight=wt)
        self.F["italic"] = tkfont.Font(family=serif, size=11, slant="italic")

    def _build_ui(self):
        outer = tk.Frame(self.root, bg=C["bg"])
        outer.pack(padx=8, pady=8)
        self.cv = tk.Canvas(outer, width=BOARD_W, height=BOARD_H, bg=MAP_BG, highlightthickness=2, highlightbackground=C["panel_border"])
        self.cv.pack(side="left")
        self.cv.bind("<ButtonPress-1>",   self._map_press)
        self.cv.bind("<B1-Motion>",       self._drag_motion)
        self.cv.bind("<ButtonRelease-1>", self._drag_release)
        self.cv.bind("<Motion>",          self._on_hover)
        self.cv.bind("<Leave>", lambda e: (self.cv.delete("hover"), self.cv.config(cursor=""), self.tip.hide()))

        self.panel = tk.Frame(outer, bg=C["panel_bg"], width=PANEL_W, highlightthickness=2, highlightbackground=C["panel_border"])
        self.panel.pack(side="right", fill="y", padx=(10, 0))
        self.panel.pack_propagate(False)
        self._build_panel(self.panel)

    def _build_panel(self, p):
        cb = C["card_bg"]
        tk.Label(p, text="Move by using the arrows, WASD or by clicking an adjacent tile.", font=self.F["tiny"], bg=C["panel_bg"], fg=C["text_col"]).pack(side="bottom", pady=(0, 6))
        self._turn_var = tk.StringVar(value="")
        self._turn_lbl = tk.Label(p, textvariable=self._turn_var, font=self.F["turn"], bg=cb, fg=C["highlight"], pady=9)
        self._turn_lbl.pack(fill="x", padx=10, pady=(10, 6))

        self._pui = []
        for i in range(2):
            pc = P_COL[i]
            border = tk.Frame(p, bg=C["panel_sep"])
            border.pack(fill="x", padx=10, pady=3)
            card = tk.Frame(border, bg=cb, padx=10, pady=7)
            card.pack(fill="x", padx=2, pady=2)
            hdr = tk.Frame(card, bg=cb); hdr.pack(fill="x")
            tk.Frame(hdr, bg=pc, width=5, height=20).pack(side="left", padx=(0, 8))
            tk.Label(hdr, text=f"Player {i+1}", font=self.F["h2"], bg=cb, fg=pc).pack(side="left")
            treas_cv = tk.Canvas(hdr, width=28, height=28, bg=cb, highlightthickness=0)
            treas_cv.pack(side="right")
            lives_cv = tk.Canvas(hdr, width=72, height=26, bg=cb, highlightthickness=0)
            lives_cv.pack(side="right", padx=(0, 6))
            steps_cv = tk.Canvas(card, width=STEP_W, height=34, bg=cb, highlightthickness=0)
            steps_cv.pack(anchor="w", pady=(6, 0))
            sv = tk.StringVar(value="")
            tk.Label(card, textvariable=sv, font=self.F["small"], bg=cb, fg=C["label_col"], anchor="w").pack(fill="x")
            self._pui.append(dict(border=border, lives=lives_cv, steps=steps_cv, treas=treas_cv, sv=sv))

        self._cap_frame = tk.Frame(p, bg=cb)
        self._cap_frame.pack(fill="x", padx=10, pady=(8, 4))
        self._cap_var = tk.StringVar(value="")
        self._cap_lbl = tk.Label(self._cap_frame, textvariable=self._cap_var, font=self.F["caption"],
                                 bg=cb, fg=C["text_col"], wraplength=PANEL_W-60, justify="left",
                                 anchor="w", height=2, padx=10, pady=6)
        self._cap_lbl.pack(fill="x")

        tray = tk.Frame(p, bg=C["panel_sep"]); tray.pack(fill="x", padx=10, pady=4)
        self.ghost_cv = tk.Canvas(tray, width=TRAY_W, height=82, bg=cb, highlightthickness=0)
        self.ghost_cv.pack(padx=1, pady=1)
        self.ghost_cv.bind("<ButtonPress-1>",   self._tray_press)
        self.ghost_cv.bind("<B1-Motion>",       self._drag_motion)
        self.ghost_cv.bind("<ButtonRelease-1>", self._drag_release)
        self.ghost_cv.bind("<Motion>",          self._tray_hover)
        self.ghost_cv.bind("<Leave>", lambda e: (self.tip.hide(), self.ghost_cv.config(cursor="")))
        self._draw_tray()

        self._btn_end = FlatButton(p, "▷  Start game", self._end_turn, self.F["btn"], "Space", self.F["hint"], primary=True, tip=self.tip, tip_text=TIPS["start"])
        self._btn_end.pack(fill="x", padx=10, pady=(8, 3))
        row = tk.Frame(p, bg=C["panel_bg"]); row.pack(fill="x", padx=10, pady=3)
        self._btn_l1 = FlatButton(row, "Level 1 game", lambda: self._start_setup(1), self.F["btn"], tip=self.tip, tip_text=TIPS["l1"], center=True)
        self._btn_l1.pack(side="left", expand=True, fill="x", padx=(0, 3))
        self._btn_l2 = FlatButton(row, "Level 2 game", lambda: self._start_setup(2), self.F["btn"], tip=self.tip, tip_text=TIPS["l2"], center=True)
        self._btn_l2.pack(side="left", expand=True, fill="x", padx=(3, 0))
        row2 = tk.Frame(p, bg=C["panel_bg"]); row2.pack(fill="x", padx=10, pady=3)
        row2.grid_columnconfigure(0, weight=1, uniform="vw"); row2.grid_columnconfigure(1, weight=1, uniform="vw")
        self._btn_voice = FlatButton(row2, "Voice: Robo", self._toggle_voice, self.F["btn"], tip=self.tip, tip_text=TIPS["voice"], center=True, chars=15)
        self._btn_voice.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self._btn_walls = FlatButton(row2, "Walls: Auto", self._toggle_walls, self.F["btn"], tip=self.tip, tip_text=TIPS["walls"], center=True, chars=15)
        self._btn_walls.grid(row=0, column=1, sticky="ew", padx=(3, 0))

    def _set_cards(self, n):
        for i, ui in enumerate(self._pui):
            if i < n: ui["border"].pack(fill="x", padx=10, pady=3, before=self._cap_frame)
            else:     ui["border"].pack_forget()

    def _say(self, text, kind="info"):
        col = {"info": C["text_col"], "bad": C["bad"], "good": C["treasure_col"]}[kind]
        self._cap_var.set(text); self._cap_lbl.config(fg=col)

    def _draw_tray(self):
        cv = self.ghost_cv; cv.delete("all"); self._tray_slots = []
        cw, ch = TRAY_W, 82
        cv.create_text(cw//2, 13, text="Drag to map", font=self.F["h3"], fill=C["text_col"])
        slot_w = cw // 3
        for k, (tok, col, sp) in enumerate((("r0", C["base_p1"], SP_BASE_P1), ("r1", C["base_p2"], SP_BASE_P2), ("g",  C["ghost_col"], SP_GHOST))):
            x0, x1, y0, y1 = k*slot_w + 6, (k+1)*slot_w - 6, 26, ch - 6
            on = self._token_enabled(tok); placed = self._token_cell(tok) is not None
            cv.create_rectangle(x0, y0, x1, y1, fill=C["bg"], width=2 if (on and not placed) else 1, outline=col if on else C["dim_col"])
            cx, cy = (x0+x1)//2, (y0+y1)//2
            if not self._blit(sp, cx, cy, 38, cv=cv):
                if tok == "g":
                    cv.create_oval(cx-17, cy-17, cx+17, cy+17, fill="#8888cc", outline="")
                else:
                    cv.create_rectangle(cx-17, cy-17, cx+17, cy+17, outline=col, width=3)
                    cv.create_text(cx, cy, text="⌂", fill=col, font=("Georgia", 16, "bold"))
            if not on:
                cv.create_rectangle(x0, y0, x1, y1, fill=C["bg"], stipple="gray50", outline="")
            elif placed:
                cv.create_text(x1-9, y0+9, text="✓", fill=C["highlight"], font=self.F["h3"])
            self._tray_slots.append((tok, x0, y0, x1, y1))

    def _token_cell(self, tok):
        return self._ghost_panel_cell if tok == "g" else self.rooms[int(tok[1])]

    def _set_token(self, tok, cell):
        if tok == "g": self._ghost_panel_cell = cell
        else:          self.rooms[int(tok[1])] = cell

    def _token_enabled(self, tok):
        if tok == "g": return self.phase == "play" and not self.game_over
        return self.phase == "setup" and (tok == "r0" or self.rooms[0] is not None)

    def _token_at_cell(self, cell):
        if cell is None: return None
        if cell == self._ghost_panel_cell: return "g"
        for i in (0, 1):
            if self.rooms[i] == cell: return f"r{i}"
        return None

    def _tray_token_at(self, x, y):
        for tok, x0, y0, x1, y1 in self._tray_slots:
            if x0 <= x <= x1 and y0 <= y <= y1: return tok
        return None

    def _cell_ok(self, tok, cell):
        if cell is None: return False
        if tok == "g": return True
        return self.rooms[1 - int(tok[1])] != cell

    def _tip_text(self, tok):
        t = TIPS[tok]
        if tok in ("r0", "r1") and self.phase == "play": t += TIPS["locked"]
        return t

    def _pointer_cell(self, ev):
        return self._cell_from_canvas(ev.x_root - self.cv.winfo_rootx(), ev.y_root - self.cv.winfo_rooty())

    def _tray_hover(self, e):
        tok = self._tray_token_at(e.x, e.y)
        if tok:
            self.tip.schedule(("tray", tok), self._tip_text(tok), e.x_root, e.y_root)
            self.ghost_cv.config(cursor="hand2" if self._token_enabled(tok) else "")
        else:
            self.tip.hide(); self.ghost_cv.config(cursor="")

    def _map_press(self, e):
        self.tip.hide()
        cell = self._cell_from_canvas(e.x, e.y)
        edge = self._edge_from_canvas(e.x, e.y) if (self.manual_walls and self.phase == "play" and not self.game_over) else None
        if edge: cell = None
        tok = self._token_at_cell(cell)
        if tok and not self._token_enabled(tok): tok = None
        self._press = dict(src="map", tok=tok, cell=cell, edge=edge, cy=e.y, xy=(e.x_root, e.y_root))
        self._drag = None

    def _tray_press(self, e):
        self.tip.hide()
        tok = self._tray_token_at(e.x, e.y)
        if tok is None or not self._token_enabled(tok):
            self._press = None
            if self.phase == "setup" and tok == "r1":
                self._say("Place Player 1's Secret Room first: then this one lights up.")
            elif self.phase == "setup" and tok == "g":
                self._say("The ghost marker unlocks once the game has started.")
            return
        self._press = dict(src="tray", tok=tok, cell=None, cy=0, xy=(e.x_root, e.y_root))
        self._drag = None

    def _drag_motion(self, e):
        pr = self._press
        if not pr or not pr["tok"]: return
        tok = pr["tok"]
        if self._drag is None:
            if abs(e.x_root - pr["xy"][0]) + abs(e.y_root - pr["xy"][1]) < 5: return
            self._drag = dict(tok=tok, orig=self._token_cell(tok), cell="?")
        self.cv.config(cursor="fleur")
        cell = self._pointer_cell(e)
        if cell != self._drag["cell"]:
            self._drag["cell"] = cell
            target = cell if self._cell_ok(tok, cell) else self._drag["orig"]
            if target != self._token_cell(tok):
                self._set_token(tok, target)
                self._full_redraw()
            self._draw_tray()

    def _drag_release(self, e):
        pr, dr = self._press, self._drag
        self._press = None; self._drag = None
        self.cv.config(cursor="")
        if dr is not None:
            cell = self._pointer_cell(e)
            tok = dr["tok"]
            self._set_token(tok, cell if self._cell_ok(tok, cell) else dr["orig"])
            self._full_redraw(); self._draw_tray(); self._update_panel()
            return
        if pr and pr["src"] == "map":
            if self.phase == "play":
                if self.game_over:
                    if pr["cy"] > GRID_BOTTOM: self._start_setup(self.difficulty)
                elif pr.get("edge"):
                    if not self._locked: self._toggle_user_wall(*pr["edge"])
                elif pr["cell"]:
                    self._take_turn(*pr["cell"])
            elif self.phase == "setup":
                self._say("Drag a Secret Room from the panel onto the map.")

    def _board_y0(self): return TITLE_H

    def _xy(self, r, c):
        return PAD + c*CELL, self._board_y0() + PAD + r*CELL

    def _cx_cy(self, r, c):
        x0, y0 = self._xy(r, c)
        return x0 + TILE//2, y0 + TILE//2

    def _cell_from_canvas(self, x, y):
        yy = y - self._board_y0() - PAD
        xx = x - PAD
        if xx < 0 or yy < 0: return None
        c = xx // CELL; r = yy // CELL
        if 0 <= r < ROWS and 0 <= c < COLS:
            return r, c
        return None

    def _on_hover(self, event):
        if self._press: return
        self.cv.delete("hover")
        if self.manual_walls and self.phase == "play" and not self.game_over:
            edge = self._edge_from_canvas(event.x, event.y)
            if edge:
                x0, y0, x1, y1, _h = self._edge_rect(*edge)
                self.cv.create_rectangle(x0, y0, x1, y1, outline=C["highlight"], width=2, tags="hover")
                self.cv.config(cursor="hand2"); self.tip.hide(); return
        cell = self._cell_from_canvas(event.x, event.y)
        tok = self._token_at_cell(cell)
        ok = False
        if tok:
            self.tip.schedule(("map", tok), self._tip_text(tok), event.x_root, event.y_root)
            ok = self._token_enabled(tok)
        else:
            self.tip.hide()
            p = self._active_player()
            if cell:
                if p and manhattan(cell[0], cell[1], p["row"], p["col"]) == 1:
                    ok = True
                    x0, y0 = self._xy(*cell)
                    self.cv.create_rectangle(x0-2, y0-2, x0+TILE+2, y0+TILE+2, outline=C["highlight"], width=2, tags="hover")
        if self.game_over and event.y > GRID_BOTTOM: ok = True
        self.cv.config(cursor="hand2" if ok else "")

    def _draw_banner(self, bg):
        self._img_refs.clear(); self.cv.delete("all")
        self.cv.create_rectangle(4, 4, BOARD_W, BOARD_H, fill=bg, outline="")
        ph = SPRITES.get_stretch(SP_TITLE, BOARD_W, TITLE_H)
        if ph:
            self._img_refs.append(ph)
            self.cv.create_image(2, 5, anchor="nw", image=ph)
        else:
            self.cv.create_rectangle(0, 0, BOARD_W, TITLE_H, fill="#0a0a0a", outline=C["panel_border"], width=2)
            self.cv.create_text(BOARD_W//2, TITLE_H//2, text="GHOULS & GRAVEYARDS", font=(self.F["title"].actual("family"), 20, "bold"), fill="#ff0000")

    def _set_end_button(self, text, tip):
        self._btn_end.set_text(text); self._btn_end.set_tip(tip)

    def _show_title(self):
        self.phase = "title"
        self._draw_banner("#1a0a06")
        cx = BOARD_W//2; cy = TITLE_H + (BOARD_H-TITLE_H)//2
        if not self._blit(SP_GHOST, cx, cy-50, 90):
            self.cv.create_oval(cx-40, cy-90, cx+40, cy-10, fill="#8888cc", outline="")
        self.cv.create_text(cx, cy+20, text="Find the treasure, dodge the ghost,\nand bring it back to your Secret Room.", font=self.F["italic"], fill=C["text_col"], justify="center")
        self.cv.create_text(cx, cy+80, text="Press  Level 1 game  or  Level 2 game  to begin", font=self.F["h3"], fill=C["highlight"])
        self.cv.create_text(cx, cy+112, text="Python/Tkinter  ·  based on Mattel Electronics 1980", font=self.F["small"], fill=C["label_col"])
        self._set_cards(2); self._say("")
        self._turn_var.set("Welcome, brave warrior"); self._turn_lbl.config(fg=C["highlight"])
        self._set_end_button("▷  Start game", TIPS["start"]); self._btn_end.set_enabled(False)
        self._draw_tray()
        for i in range(2): self._blank_card(i, 0, "Waiting to start")

    def _start_setup(self, level):
        self.tip.hide(); self.snd.clear(); self.snd.voice = self.voice
        self._btn_voice.set_text(f"Voice: {self.voice}")
        if self._attack_job: self.root.after_cancel(self._attack_job)
        self._attack_job = None
        self.difficulty = level; self.phase = "setup"
        self.game_over = False; self.winner = None; self.reveal_all = False
        self.doors = []; self._locked = False; self._ghost_hold = None
        self.user_walls = {}
        self.dragon_awake = False; self.ghost_fresh = False
        self.grid = None; self.players = [None, None]; self.num_players = 0; self.cur_p = 0
        self.tr = self.tc = self.dr = self.dc = -1
        self.rooms = [None, None]; self._ghost_panel_cell = None
        self._duel_cell = None; self._flash_wall_edge = None; self._press = None; self._drag = None
        self._panel_img_refs = []
        self._btn_l1.set_active(level == 1); self._btn_l2.set_active(level == 2)
        self._set_end_button("▷  Start game", TIPS["start"]); self._btn_end.set_enabled(True)
        self._set_cards(2)
        self._say("Drag Player 1's Secret Room onto the map. Optionally second Player 2's, then press Start game.")
        self._update_panel(); self._full_redraw(); self._draw_tray()

    @staticmethod
    def _new_player(room):
        return dict(base_r=room[0], base_c=room[1], row=room[0], col=room[1], lives=3, used_steps=0,
                    max_steps=8, carrying=False, alive=True,
                    strength=START_STRENGTH, renew_in=random.randint(*RENEW_MOVES))

    @staticmethod
    def _pick_ghost_spot(rooms, treasure):
        for dist in range(DRAGON_WAKE_DIST + 1, 0, -1):
            cands = far_cells([(rm, dist) for rm in rooms] + [(treasure, MIN_GHOST_TREAS)])
            if cands: return random.choice(cands)
        return treasure

    def _start_game(self):
        placed = [c for c in self.rooms if c]
        if not placed:
            self._say("Drag at least one Secret Room onto the map first.", "bad"); return
        n = len(placed)
        self.grid, treasure = generate_rom_level(placed)
        self.tr, self.tc = treasure
        self.dr, self.dc = treasure
        self.dragon_awake = False; self.ghost_fresh = False
        self.num_players = n
        self._place_doors()
        self.players = [self._new_player(rm) for rm in placed] + [None] * (2 - n)
        for p in self.players[:n]: self._reveal_adjacent(p["row"], p["col"])
        self.cur_p = 0; self.phase = "play"
        self._set_cards(n)
        self._set_end_button("▷  End turn", TIPS["end"])
        self._say("Player 1 starts. Move with the arrow keys or click a neighbouring tile." if n == 2
                  else "Move with the arrow keys or click a neighbouring tile. Find the treasure!")
        self._update_panel(); self._full_redraw(); self._draw_tray()

    def _toggle_walls(self):
        if self.phase == "play" and not self.game_over:
            self._say("Wall mode can only be changed between games.", "bad"); return
        self.manual_walls = not self.manual_walls
        self._btn_walls.set_text("Walls: Manual" if self.manual_walls else "Walls: Auto")
        self.user_walls = {}
        self._say("Manual walls: bumped walls/doors are not placed. Click the gap between two tiles to place a marker or remove it."
                  if self.manual_walls else "Auto walls: bumped walls/doors are automatically placed.")
        if self.grid is not None: self._full_redraw()

    def _edge_from_canvas(self, x, y):
        m = 3
        xx, yy = x - PAD, y - self._board_y0() - PAD
        if xx < 0 or yy < 0: return None
        c, fx = divmod(xx, CELL); r, fy = divmod(yy, CELL)
        if not (0 <= r < ROWS and 0 <= c < COLS): return None
        vx = fx >= TILE - m or (fx < m and c > 0)
        vy = fy >= TILE - m or (fy < m and r > 0)
        if vx == vy: return None
        if vx:
            cc = c if fx >= TILE - m else c - 1
            return (r, cc, "e") if 0 <= cc < COLS - 1 else None
        rr = r if fy >= TILE - m else r - 1
        return (rr, c, "s") if 0 <= rr < ROWS - 1 else None

    def _toggle_user_wall(self, r, c, d):
        key = (r, c, d)
        cur = self.user_walls.get(key)
        if cur is None: self.user_walls[key] = "wall"
        elif cur == "wall" and self.difficulty == 2: self.user_walls[key] = "door"
        else: del self.user_walls[key]
        self._full_redraw()

    def _draw_user_walls(self):
        for (r, c, d), kind in self.user_walls.items():
            rect = self._edge_rect(r, c, d)
            if kind == "door":
                if self.reveal_all and not self.grid[r][c].is_door[d]:
                    self.cv.create_rectangle(*rect[:4], fill="#CCAA00", outline="")
                else:
                    self._seg(SP_DOOR, rect, C["door_col"])
            elif self.reveal_all and self.grid[r][c].walls[d] is False:
                self.cv.create_rectangle(*rect[:4], fill="#CCFF00", outline="")
            else:
                self._seg(SP_WALL, rect, C["wall_col"])

    def _treasure_ok(self):
        return treasure_ok(self.grid, (self.tr, self.tc), [rm for rm in self.rooms if rm])

    def _place_doors(self):
        self.doors = []
        if self.difficulty != 2 or self.grid is None: return
        cands = [(r, c, d) for r, c in CELLS for d in ("n", "e")
                 if in_grid(*step(r, c, d)) and not self.grid[r][c].walls[d]]
        random.shuffle(cands)
        for r, c, d in cands:
            if len(self.doors) >= DOOR_COUNT: break
            if not self._try_close(r, c, d): continue
            self._set_closed(r, c, d, False)
            nr, nc = step(r, c, d)
            self.grid[r][c].is_door[d] = True; self.grid[nr][nc].is_door[OPP[d]] = True
            self.doors.append([r, c, d, random.randint(*DOOR_TURNS)])
        for r, c, d, _t in self.doors:
            if random.random() < 0.5: self._try_close(r, c, d)

    def _set_closed(self, r, c, d, closed):
        nr, nc = step(r, c, d)
        self.grid[r][c].door_closed[d] = closed
        self.grid[nr][nc].door_closed[OPP[d]] = closed

    def _try_close(self, r, c, d):
        self._set_closed(r, c, d, True)
        if self._treasure_ok(): return True
        self._set_closed(r, c, d, False); return False

    def _mark_edge(self, r, c, d, door):
        if self.manual_walls:
            return
        attr = "door_shown" if door else "wall_shown"
        nr, nc = step(r, c, d)
        self.grid[r][c].seen = True
        getattr(self.grid[r][c], attr)[d] = True
        if in_grid(nr, nc): getattr(self.grid[nr][nc], attr)[OPP[d]] = True

    def _update_doors(self):
        if self.difficulty != 2 or self.grid is None: return
        for dr in self.doors:
            dr[3] -= 1
            if dr[3] > 0: continue
            r, c, d = dr[0], dr[1], dr[2]
            if self.grid[r][c].door_closed[d]: self._set_closed(r, c, d, False)
            else: self._try_close(r, c, d)
            dr[3] = random.randint(*DOOR_TURNS)

    def _reveal_adjacent(self, r, c):
        self.grid[r][c].seen = True

    def _blit(self, sp, x, y, w, h=None, cv=None, anchor="center", dim=False, **kw):
        cv = self.cv if cv is None else cv
        ph = (SPRITES.get_dim if dim else SPRITES.get_fit)(sp, w, h or w)
        if ph is None: return False
        (self._img_refs if cv is self.cv else self._panel_img_refs).append(ph)
        cv.create_image(x, y, anchor=anchor, image=ph, **kw)
        return True

    def _full_redraw(self):
        self._draw_banner(MAP_BG)
        for r, c in CELLS:
            x0, y0 = self._xy(r, c)
            if not self._blit(SP_FLOOR, x0, y0, TILE, anchor="nw"):
                self.cv.create_rectangle(x0, y0, x0+TILE, y0+TILE, fill="#2b1a10", outline="")
        self._draw_bases()
        if self.grid is not None:
            self._draw_edges("walls", "wall_shown", SP_WALL, C["wall_col"])
            self._draw_edges("is_door", "door_shown", SP_DOOR, C["door_col"])
            if self.manual_walls: self._draw_user_walls()
        self._draw_treasure(); self._draw_hints(); self._draw_warriors()
        self._draw_map_ghost(); self._draw_real_ghost(); self._draw_flashes()
        if self.game_over: self._redraw_end_overlay()

    def _edge_rect(self, r, c, d):
        x0, y0 = self._xy(r, c); x1, y1 = x0+TILE, y0+TILE
        if d == "n": return (x0, y0-GAP, x1, y0, True)
        if d == "s": return (x0, y1, x1, y1+GAP, True)
        if d == "w": return (x0-GAP, y0, x0, y1, False)
        return (x1, y0, x1+GAP, y1, False)

    @staticmethod
    def _edge_key(r, c, d):
        return tuple(sorted([(r, c), step(r, c, d)]))

    def _seg(self, sp, rect, col, dim=False):
        x0, y0, x1, y1, horiz = rect
        w, h = x1-x0, y1-y0
        if dim:
            ph = SPRITES.get_dim(sp, w, h) if horiz else SPRITES.get_dim(sp, w, h, rot=90)
        else:
            ph = SPRITES.get_fit(sp, w, h) if horiz else SPRITES.get_fit_rot90(sp, w, h)
        if ph:
            self._img_refs.append(ph)
            self.cv.create_image(x0, y0, anchor="nw", image=ph)
        else:
            self.cv.create_rectangle(x0, y0, x1, y1, fill=col if not dim else C["dim_col"], outline="")

    def _draw_edges(self, active, shown, sp, col, reveal=True):
        drawn = set()
        for r, c in CELLS:
            cell = self.grid[r][c]
            for d in DIRS:
                if not getattr(cell, active)[d]: continue
                is_shown = getattr(cell, shown)[d] or (reveal and self.reveal_all)
                if not is_shown and not debug_mode: continue
                key = self._edge_key(r, c, d)
                if key in drawn: continue
                drawn.add(key)
                self._seg(sp, self._edge_rect(r, c, d), col, dim=(not is_shown and debug_mode))

    def _draw_bases(self):
        sz = int(TILE * 0.8)
        for i, cell in enumerate(self.rooms):
            if cell is None: continue
            cx, cy = self._cx_cy(*cell)
            if not self._blit(SP_BASE[i], cx, cy, sz):
                h = sz//2
                self.cv.create_rectangle(cx-h, cy-h, cx+h, cy+h, fill="", outline=P_COL[i], width=3)
                self.cv.create_text(cx, cy, text="⌂", fill=P_COL[i], font=("Georgia", 16, "bold"))

    def _chest_fallback(self, cv, cx, cy, s):
        w = s; h = int(s*0.7)
        cv.create_rectangle(cx-w//2, cy-h//2, cx+w//2, cy+h//2, fill="#8a5a1c", outline=C["treasure_col"], width=2)
        cv.create_rectangle(cx-w//2, cy-h//2, cx+w//2, cy-h//6, fill=C["treasure_col"], outline="")
        cv.create_rectangle(cx-2, cy-h//6, cx+2, cy+h//10, fill=C["bg"], outline="")

    def _draw_chest(self, cx, cy, s, cv=None, dim=False):
        cv = self.cv if cv is None else cv
        if self._blit(SP_TREAS, cx, cy, s, cv=cv, dim=dim): return
        if dim:
            w, h = s, int(s*0.7)
            cv.create_rectangle(cx-w//2, cy-h//2, cx+w//2, cy+h//2, fill="#3a3a3a", outline="#777777", width=2, stipple="gray50")
        else: self._chest_fallback(cv, cx, cy, s)

    def _draw_treasure(self):
        if self.tr < 0: return
        if self._carrier():
            if self.game_over and self.winner is not None:
                self._draw_chest(*self._cx_cy(self.tr, self.tc), int(TILE * 0.8), dim=True)
            return
        is_visible = self.reveal_all or any((q["row"], q["col"]) == (self.tr, self.tc) for q in self._live())
        if is_visible:
            self._draw_chest(*self._cx_cy(self.tr, self.tc), int(TILE * 0.8))
        elif debug_mode:
            self._draw_chest(*self._cx_cy(self.tr, self.tc), int(TILE * 0.8), dim=True)

    def _draw_hints(self):
        if self.game_over or self.manual_walls:
            return
        p = self._cur_player()
        if p is None: return
        r, c = p["row"], p["col"]
        for _, nr, nc in neighbors(r, c):
            x0, y0 = self._xy(nr, nc)
            self.cv.create_rectangle(x0+4, y0+4, x0+TILE-5, y0+TILE-5, outline=C["text_col"], dash=(3, 4))
        x0, y0 = self._xy(r, c)
        self.cv.create_rectangle(x0-1, y0-1, x0+TILE+1, y0+TILE+1, outline=P_COL[self.cur_p], width=2)

    def _draw_mini_treasure(self, bx, by):
        bs = int(TILE * 0.4); rad = bs//2 + 3
        self.cv.create_oval(bx-rad, by-rad, bx+rad, by+rad, fill=C["bg"], outline=C["treasure_col"], width=2)
        self._draw_chest(bx, by, bs)

    def _draw_warriors(self):
        live = [(i, p) for i, p in enumerate(self.players) if p and p["alive"]]
        badges = []
        for i, p in live:
            cx, cy = self._cx_cy(p["row"], p["col"])
            sharing = [j for j, q in live if (q["row"], q["col"]) == (p["row"], p["col"])]
            if len(sharing) > 1:
                cx += (-1 if i == sharing[0] else 1) * int(TILE*0.2)
            sz = int(TILE * (0.68 if len(sharing) > 1 else 0.85))
            if not self._blit(SP_HERO[i], cx, cy, sz):
                h = sz//2 - 2
                self.cv.create_oval(cx-h, cy-h, cx+h, cy+h, fill=P_COL[i], outline=C["text_col"], width=2)
                self.cv.create_text(cx, cy, text=str(i+1), fill="white", font=("Georgia", 13, "bold"))
            if p["carrying"]:
                badges.append((cx + sz//2 - 5, cy - sz//2 + 5))
        for bx, by in badges:
            self._draw_mini_treasure(bx, by)

    def _draw_map_ghost(self):
        if self._ghost_panel_cell is None: return
        cx, cy = self._cx_cy(*self._ghost_panel_cell); sz = int(TILE * 0.75)
        self._blit(SP_GHOST, cx, cy, sz, tags="map_ghost")
        half = sz//2
        self.cv.create_oval(cx-half, cy-half, cx+half, cy+half, outline=C["highlight"], width=1, dash=(4, 3), tags="map_ghost")

    def _draw_real_ghost(self):
        if self.dr < 0: return
        if self.reveal_all:
            cx, cy = self._cx_cy(self.dr, self.dc); sz = int(TILE*0.8); half = sz//2 + 2
            m = self._ghost_panel_cell
            if m is not None and m != (self.dr, self.dc):
                mx, my = self._cx_cy(*m)
                self.cv.create_line(mx, my, cx, cy, fill=C["bad"], width=2, dash=(5, 3), arrow="last")
            self.cv.create_oval(cx-half, cy-half, cx+half, cy+half, fill="#1a0a0a", outline="#ff3333", width=3)
            if not self._blit(SP_GHOST, cx, cy, sz):
                self.cv.create_oval(cx-half+6, cy-half+6, cx+half-6, cy+half-6, fill="#8888cc", outline="")
            self.cv.create_text(cx, cy+half+7, text="Ghost", fill="#ff6655", font=self.F["tiny"])
        elif debug_mode and self.phase == "play":
            cx, cy = self._cx_cy(self.dr, self.dc); sz = int(TILE*0.8)
            self._blit(SP_GHOST, cx, cy, sz, dim=True)

    def _draw_flashes(self):
        if self._flash_wall_edge:
            r, c, d, is_door = self._flash_wall_edge
            self._seg(SP_DOOR if is_door else SP_WALL, self._edge_rect(r, c, d), C["door_col"] if is_door else C["wall_col"])
            x0, y0 = self._xy(r, c)
            self.cv.create_rectangle(x0, y0, x0+TILE, y0+TILE, fill="#ffffff", outline="", stipple="gray25")
        if self._duel_cell:
            cx, cy = self._cx_cy(*self._duel_cell)
            self.cv.create_oval(cx-24, cy-24, cx+24, cy+24, fill=C["bg"], outline=C["treasure_col"], width=3)
            self.cv.create_text(cx, cy, text="⚔", font=("Georgia", 24, "bold"), fill=C["treasure_col"])

    def _flash_wall(self, r, c, d, is_door=False):
        self._flash_wall_edge = (r, c, d, is_door)
        def clear():
            self._flash_wall_edge = None
            if self.grid is not None: self._full_redraw()
        self.root.after(450, clear)

    def _clear_duel(self):
        self._duel_cell = None
        if self.grid is not None: self._full_redraw()

    def _draw_lives(self, cv, lives, max_l, dead=False):
        cv.delete("all")
        if dead:
            cv.create_text(4, 13, text="💀", font=("Georgia", 14), fill="#cc3333", anchor="w"); return
        for i in range(max_l):
            col = C["heart_on"] if i < lives else C["heart_off"]
            cv.create_text(4+i*22, 13, text="♥", font=("Georgia", 15), fill=col, anchor="w")

    def _footprint(self, cv, cx, cy, s, col, mirror):
        m = -1 if mirror else 1
        cv.create_oval(cx-0.47*s, cy-0.13*s, cx-0.13*s, cy+0.13*s, fill=col, outline="")
        cv.create_oval(cx-0.20*s, cy-0.25*s, cx+0.22*s, cy+0.25*s, fill=col, outline="")
        for tx, ty, tr in ((0.34, -0.19, 0.075), (0.40, -0.07, 0.062), (0.40, 0.04, 0.056), (0.36, 0.14, 0.05)):
            x = cx + tx*s; y = cy + m*ty*s; r = tr*s
            cv.create_oval(x-r, y-r, x+r, y+r, fill=col, outline="")

    def _draw_steps(self, cv, used, max_s):
        cv.delete("all")
        if max_s == 0: return
        slot_w = min(36, (STEP_W-4)//8)
        for i in range(max_s):
            cx = 4 + i*slot_w + slot_w//2
            cy = 17 + (-6 if i % 2 == 0 else 6)
            spent = i < used
            sp = SP_STEP_US if spent else SP_STEP_AV
            ph = SPRITES.get_fit_rotcw(sp, slot_w+2, 15, flip=(i % 2 == 1))
            if ph:
                self._panel_img_refs.append(ph)
                cv.create_image(cx, cy, anchor="center", image=ph)
            else:
                self._footprint(cv, cx, cy, slot_w, "#6a2a1a" if spent else "#ff6644", i % 2 == 1)

    def _draw_treas_icon(self, cv, show):
        cv.delete("all")
        if show: self._draw_chest(14, 14, 24, cv=cv)

    def _blank_card(self, i, lives, text, dead=False, steps=8):
        ui = self._pui[i]
        ui["border"].config(bg=C["panel_sep"])
        self._draw_lives(ui["lives"], lives, 3, dead)
        self._draw_steps(ui["steps"], 0, steps)
        self._draw_treas_icon(ui["treas"], False)
        ui["sv"].set(text)

    def _update_panel(self):
        if self.phase != "play":
            if self.phase == "setup":
                for i in range(2):
                    if self.rooms[i]:                  txt = "Secret Room is on the map"
                    elif i == 1 and not self.rooms[0]: txt = "Waits for Player 1's Secret Room"
                    else:                              txt = "Drag its Secret Room onto the map"
                    self._blank_card(i, 3, txt)
                self._turn_var.set("Place your Secret Rooms"); self._turn_lbl.config(fg=C["highlight"])
            else:
                for i in range(2): self._blank_card(i, 0, "Waiting to start")
            return
        for i in range(2):
            ui = self._pui[i]; p = self.players[i]
            if p is None:        self._blank_card(i, 0, "—", steps=0); continue
            if not p["alive"]:   self._blank_card(i, 0, "Eliminated", dead=True, steps=0); continue
            active = (i == self.cur_p) and not self.game_over
            ui["border"].config(bg=C["active_border"] if active else C["panel_sep"])
            self._draw_lives(ui["lives"], p["lives"], 3)
            self._draw_steps(ui["steps"], p["used_steps"], p["max_steps"])
            self._draw_treas_icon(ui["treas"], p["carrying"])
            left = max(0, p["max_steps"] - p["used_steps"])
            if p["carrying"]: ui["sv"].set(f"★ Carrying the treasure · {left} moves left")
            else:             ui["sv"].set(f"{left} of {p['max_steps']} moves left")
        if self.game_over:
            if self.winner is not None:
                self._turn_var.set(f"🏆  Player {self.winner+1} wins!")
                self._turn_lbl.config(fg=C["treasure_col"])
            else:
                self._turn_var.set("💀  Game over"); self._turn_lbl.config(fg="#ff3333")
        else:
            self._turn_var.set(f"Player {self.cur_p+1}'s turn"); self._turn_lbl.config(fg=P_COL[self.cur_p])

    def _redraw_end_overlay(self):
        y0 = GRID_BOTTOM + GAP + 10; y1 = y0 + 28
        if self.winner is not None:
            msg = f"🏆  Player {self.winner+1} wins!"; col = C["treasure_col"]
        else:
            msg = "💀  Game over"; col = "#ff3333"
        self.cv.create_rectangle(PAD, y0, BOARD_W-PAD, y1, fill=C["end_box"], outline=col, width=2)
        self.cv.create_text(PAD+14, (y0+y1)//2, text=msg, anchor="w", font=self.F["end"], fill=col)
        self.cv.create_text(BOARD_W-PAD-12, (y0+y1)//2, anchor="e", font=self.F["small"], fill=C["label_col"], text="Red ring = real ghost  ·  click to play again")

    def _bind_keys(self):
        for key, (dr, dc) in {"Left": (0, -1), "Right": (0, 1), "Up": (-1, 0), "Down": (1, 0), "a": (0, -1), "d": (0, 1), "w": (-1, 0), "s": (1, 0)}.items():
            self.root.bind(f"<{key}>", lambda e, dr=dr, dc=dc: self._move(dr, dc))
        self.root.bind("<space>", lambda e: self._end_turn())
        for k in ("v", "V"): self.root.bind(k, lambda e: self._toggle_voice())
        for k in ("m", "M"): self.root.bind(k, lambda e: self._toggle_walls())
        self.cv.bind("<Button-3>", lambda e: self._end_turn())

    def _active_player(self):
        if self.phase != "play" or self.game_over or self._locked or self.grid is None: return None
        if self.snd.prio_busy(): return None
        return self._cur_player()

    def _move(self, dr, dc):
        p = self._active_player()
        if p and in_grid(p["row"]+dr, p["col"]+dc): self._take_turn(p["row"]+dr, p["col"]+dc)

    def _end_turn(self):
        if self.phase == "setup": self._start_game(); return
        p = self._active_player()
        if p: self._say(CAPTIONS["endturn"]); self._finish_turn(p)

    def _toggle_voice(self):
        self.voice = "Natural" if self.voice == "Robo" else "Robo"
        self.snd.voice = self.voice
        self._btn_voice.set_text(f"Voice: {self.voice}")

    def _cur_player(self):
        p = self.players[self.cur_p]
        return p if (p and p["alive"]) else None

    def _live(self): return [q for q in self.players if q and q["alive"]]
    def _carrier(self): return next((q for q in self._live() if q["carrying"]), None)
    def _in_own_base(self, p): return p["row"] == p["base_r"] and p["col"] == p["base_c"]
    def _idx(self, p): return next(i for i, q in enumerate(self.players) if q is p)

    def _warriors_at(self, row, col):
        return [q for q in self._live() if (q["row"], q["col"]) == (row, col) and not self._in_own_base(q)]

    def _spend_strength(self, p):
        p["strength"] = max(1, p["strength"] - random.randint(*STRENGTH_LOSS))
        p["renew_in"] -= 1
        if p["renew_in"] <= 0:
            p["strength"] = START_STRENGTH
            p["renew_in"] = random.randint(*RENEW_MOVES)

    def _pick_victim(self, victims):
        if len(victims) == 1: return victims[0]
        a, b = victims
        if a["strength"] == b["strength"]: return random.choice(victims)
        return a if a["strength"] < b["strength"] else b

    def _try_wake_ghost(self, p=None):
        if self.dragon_awake or self.game_over or self.grid is None:
            return

        tr, tc = self.tr, self.tc
        if tr < 0:
            return

        for q in self._live():
            if self._in_own_base(q):
                continue
            d = dragon_distance(q["row"], q["col"], tr, tc)
            if d <= DRAGON_WAKE_RADIUS:
                self.dragon_awake = True
                self.ghost_fresh = False
                self.snd.push("ghostawakes")
                return

    def _take_turn(self, row, col):
        p = self._active_player()
        if p is None: return
        dr = row - p["row"]; dc = col - p["col"]
        if abs(dr) + abs(dc) != 1:
            self.snd.push("no"); return
        d = "n" if dr == -1 else "s" if dr == 1 else "w" if dc == -1 else "e"
        cell = self.grid[p["row"]][p["col"]]

        if not cell.passable(d):
            is_door = cell.door_closed[d]
            self._mark_edge(p["row"], p["col"], d, is_door)
            if not self.manual_walls:
                self._flash_wall(p["row"], p["col"], d, is_door)
            self.snd.push("hitawall", pitch=DOOR_OUCH_PITCH if is_door else 1.0)
            if is_door:
                self._say("A closed door! You stay where you are and your turn is over. "
                          "Try again later: every door opens sooner or later.", "bad")
            p["used_steps"] = p["max_steps"]
            self._update_doors()
            self._finish_turn(p); return

        p["row"] = row; p["col"] = col; p["used_steps"] += 1
        self._spend_strength(p)
        self._update_doors()
        self.grid[row][col].seen = True; self._reveal_adjacent(row, col)
        self.snd.push("tik")

        if self.dragon_awake and (row, col) == (self.dr, self.dc):
            here = self._warriors_at(row, col)
            if here:
                v = self._pick_victim(here)
                others = [q for q in here if q is not v]
                if others:
                    self._ghost_hold = [others[0], 1 if self._idx(others[0]) <= self._idx(p) else 0]
                after = (lambda: self._finish_turn(p)) if v is p else (lambda: self._resume_turn(p))
                self._update_panel(); self._full_redraw()
                self._dragon_attacks(v, after); return

        if (row, col) == (self.tr, self.tc) and not self._carrier():
            p["carrying"] = True; p["max_steps"] = TREASURE_STEPS
            p["used_steps"] = max(p["used_steps"], p["max_steps"])
            self.snd.push("foundtreasure")
            self._say(f"Treasure found! It is heavy: your turn ends, then {TREASURE_STEPS} moves per turn.", "good")

        self._check_combat(p)
        if self._check_win(): return

        if p["used_steps"] >= p["max_steps"]:
            self._finish_turn(p); return
        self._update_panel(); self._full_redraw()

    def _check_combat(self, p):
        here = [q for q in self._live() if (q["row"], q["col"]) == (p["row"], p["col"]) and not self._in_own_base(q)]
        if len(here) < 2: return
        self._duel_cell = (p["row"], p["col"])
        a, b = here[0], here[1]
        w = a if a["strength"] >= b["strength"] else b
        l = b if w is a else a
        w_idx = self._idx(w); l_idx = self._idx(l)

        if l["carrying"]:
            l["carrying"] = False
            l["max_steps"] = STEPS_BY_LIVES.get(l["lives"], 8)
            w["carrying"] = True
            w["max_steps"] = TREASURE_STEPS

        l["used_steps"] = l["max_steps"]
        self.snd.push_duel(w_idx, f"Player {w_idx+1} defeats Player {l_idx+1} in a duel!")
        self.root.after(800, self._clear_duel)

    def _check_win(self):
        c = self._carrier()
        if c and self._in_own_base(c):
            self.game_over = True
            self.winner = self._idx(c)
            self.reveal_all = True
            self.snd.push("youwin")
            self._say(f"Player {self.winner+1} returned to the Secret Room with the treasure and wins!", "good")
            self._update_panel(); self._full_redraw()
            return True
        return False

    def _resume_turn(self, p):
        if self.game_over: return
        if p["used_steps"] >= p["max_steps"]: self._finish_turn(p)
        else: self._update_panel(); self._full_redraw()

    def _finish_turn(self, p):
        if self.game_over: return
        self._try_wake_ghost(p)
        self._update_panel(); self._full_redraw()
        if self.dragon_awake and self._round_end(p) and self.snd.busy():
            self._locked = True
            self._attack_job = self.root.after(20, lambda: self._wait_sound(p, 0))
            return
        self._finish_turn_now(p)

    def _wait_sound(self, p, n):
        if self.game_over: return
        if self.snd.busy() and n < 75:
            self._attack_job = self.root.after(20, lambda: self._wait_sound(p, n + 1)); return
        self._finish_turn_now(p)

    def _finish_turn_now(self, p):
        self._locked = False; self._attack_job = None
        if self.game_over: return
        if self._round_end(p) and self._do_dragon_turn(p): return
        self._advance_turn(p)

    def _round_end(self, p):
        i = self._idx(p)
        return not any(q and q["alive"] for q in self.players[i + 1:])

    def _advance_turn(self, p):
        if self.game_over: return
        p["used_steps"] = 0
        self._next_player()
        self._update_panel(); self._full_redraw()

    def _next_player(self):
        live = [i for i, q in enumerate(self.players) if q and q["alive"]]
        if not live: return
        if self.cur_p in live:
            idx = live.index(self.cur_p)
            self.cur_p = live[(idx + 1) % len(live)]
        else:
            self.cur_p = live[0]

    def _do_dragon_turn(self, p):
        if not self.dragon_awake or self.game_over: return False
        if self._ghost_hold is not None:
            hw, skips = self._ghost_hold
            if hw["alive"] and skips > 0:
                self._ghost_hold[1] -= 1; return False
            self._ghost_hold = None
        out = [q for q in self._live() if not self._in_own_base(q)]
        goal = self._carrier() or min(
            out, key=lambda q: dragon_distance(self.dr, self.dc, q["row"], q["col"]), default=None)
        tr, tc = (goal["row"], goal["col"]) if goal else (self.tr, self.tc)

        if (self.dr, self.dc) != (tr, tc):
            self.dr += (tr > self.dr) - (tr < self.dr)
            self.dc += (tc > self.dc) - (tc < self.dc)
            self.snd.push("ghostmoves")

        victims = self._warriors_at(self.dr, self.dc)
        if not victims: return False
        v = self._pick_victim(victims)
        others = [q for q in victims if q is not v]
        if others: self._ghost_hold = [others[0], 0]
        self._dragon_attacks(v, lambda: self._advance_turn(p))
        return True

    def _fatal_catch(self, v):
        return bool(v["carrying"]) or ((v["row"], v["col"]) == (self.tr, self.tc) and not self._carrier())

    def _dragon_attacks(self, v, after):
        self._locked = True
        self.dr, self.dc = v["row"], v["col"]
        lethal = self._fatal_catch(v) or v["lives"] <= 1
        last = lethal and not any(q is not v for q in self._live())
        if not last:
            self._ghost_panel_cell = (v["row"], v["col"])
        self.snd.push("ghostattacks")
        self._say("The ghost attacks!", "bad")
        self._draw_tray(); self._full_redraw()
        self._attack_job = self.root.after(ATTACK_DELAY_MS, lambda: self._apply_attack(v, after))

    def _apply_attack(self, v, after):
        self._locked = False; self._attack_job = None
        if self.game_over: return
        n = self._idx(v) + 1
        if self._fatal_catch(v):
            v["carrying"] = False; v["lives"] = 0
        else:
            v["lives"] -= 1
            v["max_steps"] = STEPS_BY_LIVES.get(v["lives"], 8)
        v["row"], v["col"] = v["base_r"], v["base_c"]
        v["used_steps"] = 0

        if v["lives"] <= 0:
            v["alive"] = False
            self._say(f"Player {n} was eliminated!", "bad")

        live = self._live()
        if not live:
            self.game_over = True; self.reveal_all = True
            self.snd.push("gameover")
            self._say("Game over! All warriors have been eliminated.", "bad")
            self._update_panel(); self._full_redraw(); return

        if len(live) == 1 and self.num_players == 2:
            s = live[0]; sn = self._idx(s) + 1
            self._say(f"Player {n} was eliminated. Player {sn} continues alone!", "info")

        self._update_panel(); self._full_redraw()
        after()


def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main()

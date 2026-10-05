import os, sys, math, random, threading, tempfile, wave, struct, time
import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageTk, ImageOps

def _resource_dir():
    """Folder that contains ./data: next to this script, or inside the PyInstaller bundle."""
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
BOARD_H      = GRID_BOTTOM + PAD + 10          # extra room for the end-of-game banner
PANEL_W      = 340
TRAY_W       = PANEL_W - 26
STEP_W       = 288

MAP_BG       = "#2a2a2e"

MAX_WALLS        = 50
EXTRA_PASSAGES   = 12
MIN_TREAS_DIST   = 3          # the treasure is always >= 3 squares from every Secret Room
MIN_GHOST_TREAS  = 3          # ... and the sleeping ghost is always >= 3 squares from the treasure
DRAGON_WAKE_DIST = 3          # a hero can wake the ghost from this distance
WAKE_CHANCE      = {3: 0.25, 2: 0.50, 1: 1.0}   # chance to wake per hero step, by distance from the ghost
STEPS_BY_LIVES   = {3: 8, 2: 6, 1: 4, 0: 0}
TREASURE_STEPS   = 4          # moves per turn while carrying the treasure
PHANTOM_DOORS    = 4          # max closed doors at the same time
DOOR_TURNS       = (3, 9)     # a door stays closed for a random number of turns
START_STRENGTH   = 50         # both warriors start equally strong
STRENGTH_LOSS    = (1, 3)     # lost at every move
RENEW_MOVES      = (12, 30)   # strength is renewed after a random number of moves
ATTACK_DELAY_MS  = 600

DELTA = {"n": (-1,0), "s": (1,0), "e": (0,1), "w": (0,-1)}
OPP   = {"n":"s", "s":"n", "e":"w", "w":"e"}
DIRS  = list(DELTA.keys())
CELLS = [(r, c) for r in range(ROWS) for c in range(COLS)]

def in_grid(r, c): return 0 <= r < ROWS and 0 <= c < COLS
def step(r, c, d): return r + DELTA[d][0], c + DELTA[d][1]
def manhattan(r1, c1, r2, c2): return abs(r1-r2) + abs(c1-c2)

def neighbors(r, c):
    """(direction, row, col) of every neighbouring tile inside the grid."""
    for d in DIRS:
        nr, nc = step(r, c, d)
        if in_grid(nr, nc): yield d, nr, nc

def far_cells(rules):
    """Every tile at least `dist` squares away from each (cell, dist) in rules."""
    return [(r, c) for r, c in CELLS if all(manhattan(r, c, *a) >= dist for a, dist in rules)]

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
    "l1":    "New Level 1 game: the labyrinth never changes.",
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

# Short jingles for the "warrior tune" played after a duel (synthesised at runtime,
# no audio assets needed).  (frequency Hz, seconds)
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


def _build_audio_backend():
    """play(list_of_paths) plays the files one after the other; a new call interrupts the old one."""
    try:
        import miniaudio
    except Exception:
        return (lambda paths: None), (lambda: False)
    state = {"gen": 0, "thread": None}

    def play(paths):
        if isinstance(paths, str): paths = [paths]
        paths = [p for p in paths if p and os.path.exists(p)]
        state["gen"] += 1
        gen = state["gen"]
        if not paths: return

        def run():
            for path in paths:
                if state["gen"] != gen: return
                try:
                    stream = miniaudio.stream_file(path)
                    with miniaudio.PlaybackDevice() as dev:
                        dev.start(stream)
                        while dev.callback_generator is not None:
                            if state["gen"] != gen: return
                            time.sleep(0.02)
                        time.sleep(0.12)
                except Exception:
                    pass
        t = threading.Thread(target=run, daemon=True)
        state["thread"] = t
        t.start()

    def busy():
        t = state["thread"]
        return bool(t and t.is_alive())
    return play, busy

_audio_play, _audio_busy = _build_audio_backend()


class SoundQueue:
    """Plays immediately and interrupts the previous sound."""
    def __init__(self, root, voice="Robo"):
        self.root = root; self.voice = voice
        self.on_caption = lambda s: None

    def _path(self, key):
        files = SND_FILES.get(key, [])
        if not files: return None
        idx = 0 if self.voice == "Robo" else 1
        return os.path.join(SOUND_DIR, files[idx] if idx < len(files) else files[0])

    def push(self, key):
        cap = CAPTIONS.get(key, "")
        if cap: self.on_caption(cap)
        _audio_play([self._path(key)])

    def push_duel(self, winner_idx, caption):
        """Winner's tune followed by the treasure tune."""
        self.on_caption(caption)
        _audio_play([_warrior_tune_path(winner_idx), self._path("foundtreasure")])

    def clear(self): _audio_play([])
    def busy(self): return _audio_busy()


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
        """Fit inside max_w x max_h keeping the aspect ratio. rot is counter-clockwise degrees."""
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
        """Rotated 90 degrees CLOCKWISE (optionally mirrored top-bottom)."""
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
    """One tooltip shared by the whole app: shown after a short hover, hidden on leave / click."""
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
    """Flat button with hover state, optional key hint, tooltip, enabled and 'active' (selected) flags."""
    def __init__(self, parent, text, command, font, hint="", hint_font=None, primary=False,
                 tip=None, tip_text="", center=False):
        super().__init__(parent, bg=C["panel_border"], padx=1, pady=1, cursor="hand2")
        self._cmd = command; self._primary = primary; self._on = True; self._hover = False
        self._active = False; self._tip = tip; self._tip_text = tip_text
        self._in = tk.Frame(self); self._in.pack(fill="x")
        self._lbl = tk.Label(self._in, text=text, font=font, anchor="center" if center else "w", padx=12, pady=7)
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
        self.door_shown  = {d: False for d in DIRS}   # a door is only visible once you bumped into it

    def passable(self, d): return not self.walls[d] and not self.door_closed[d]
    def open_count(self):  return sum(1 for d in DIRS if not self.walls[d])

def _carve(grid, r, c, d, opened=True):
    nr, nc = step(r, c, d)
    grid[r][c].walls[d] = not opened
    grid[nr][nc].walls[OPP[d]] = not opened

def _walls(grid):
    """Every interior wall exactly once, as (r, c, d) with d in ('s', 'e')."""
    return [(r, c, d) for r, c in CELLS for d in ("s", "e")
            if in_grid(*step(r, c, d)) and grid[r][c].walls[d]]

def disjoint_paths(grid, src, dst, limit=2):
    """How many routes (up to `limit`) lead from src to dst without sharing any intermediate tile.
    Max-flow with unit capacities on a split-node graph; closed doors count as walls."""
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
    """The treasure is never a dead end: from every Secret Room a hero can reach it by 2 different routes."""
    return all(disjoint_paths(grid, rm, treasure) >= 2 for rm in rooms)

def generate_maze(treasure, rooms):
    grid = [[Cell(r, c) for c in range(COLS)] for r in range(ROWS)]
    sr, sc = random.choice(CELLS)
    grid[sr][sc].seen = True
    frontier = [(sr, sc)]
    while frontier:                                   # randomised Prim: a perfect maze
        i = random.randrange(len(frontier)); r, c = frontier[i]
        nbrs = [(d, nr, nc) for d, nr, nc in neighbors(r, c) if not grid[nr][nc].seen]
        if not nbrs: frontier.pop(i); continue
        d, nr, nc = random.choice(nbrs)
        _carve(grid, r, c, d); grid[nr][nc].seen = True; frontier.append((nr, nc))

    added = attempts = 0                              # a few extra passages: loops and shortcuts
    while added < EXTRA_PASSAGES and len(_walls(grid)) > MAX_WALLS and attempts < 2000:
        attempts += 1
        r, c = random.choice(CELLS); d = random.choice(DIRS); nr, nc = step(r, c, d)
        if in_grid(nr, nc) and grid[r][c].walls[d]: _carve(grid, r, c, d); added += 1

    def score(): return sum(disjoint_paths(grid, rm, treasure) for rm in rooms)
    best = score()
    while best < 2 * len(rooms):                      # open the fewest walls that give every room 2 routes
        walls = _walls(grid); random.shuffle(walls)
        if not walls: break
        for r, c, d in walls:
            _carve(grid, r, c, d); s = score()
            if s > best: best = s; break
            _carve(grid, r, c, d, False)
        else:                                         # no single wall helps: open one at random and go on
            _carve(grid, *walls[0]); best = score()

    for r, c in CELLS: grid[r][c].seen = False
    return grid


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Ghouls & Graveyards")
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, False)
        self._fonts()
        self.tip = Tip(root, self.F["small"])
        self.phase = "title"                    # title -> setup (place the Secret Rooms) -> play
        self.num_players = 0; self.difficulty = 1; self.voice = "Robo"
        self.grid = None; self.players = [None, None]; self.cur_p = 0
        self.rooms = [None, None]               # Secret Room tokens on the map (cells)
        self.dr = self.dc = -1                  # REAL ghost position (hidden until the game ends)
        self.dragon_awake = False
        self.ghost_fresh = False                # just woke up: it only starts moving on its next turn
        self.tr = self.tc = -1
        self.game_over = False; self.winner = None
        self.reveal_all = False; self.doors = []
        self._attack_job = None
        self._locked = False                    # input locked while the ghost attacks
        self._ghost_panel_cell = None           # the player's own ghost MARKER
        self._ghost_hold = None                 # [warrior, turns_to_skip]
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

    # ── fonts ────────────────────────────────────────────────────────
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

    # ── UI ───────────────────────────────────────────────────────────
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
        # whose turn
        self._turn_var = tk.StringVar(value="")
        self._turn_lbl = tk.Label(p, textvariable=self._turn_var, font=self.F["turn"], bg=cb, fg=C["highlight"], pady=9)
        self._turn_lbl.pack(fill="x", padx=10, pady=(10, 6))

        # player cards
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

        # message area
        self._cap_frame = tk.Frame(p, bg=cb)
        self._cap_frame.pack(fill="x", padx=10, pady=(8, 4))
        self._cap_var = tk.StringVar(value="")
        self._cap_lbl = tk.Label(self._cap_frame, textvariable=self._cap_var, font=self.F["caption"],
                                 bg=cb, fg=C["text_col"], wraplength=PANEL_W-60, justify="left",
                                 anchor="w", height=2, padx=10, pady=6)
        self._cap_lbl.pack(fill="x")

        # tokens tray: both Secret Rooms and the ghost marker
        tray = tk.Frame(p, bg=C["panel_sep"]); tray.pack(fill="x", padx=10, pady=4)
        self.ghost_cv = tk.Canvas(tray, width=TRAY_W, height=82, bg=cb, highlightthickness=0)
        self.ghost_cv.pack(padx=1, pady=1)
        self.ghost_cv.bind("<ButtonPress-1>",   self._tray_press)
        self.ghost_cv.bind("<B1-Motion>",       self._drag_motion)
        self.ghost_cv.bind("<ButtonRelease-1>", self._drag_release)
        self.ghost_cv.bind("<Motion>",          self._tray_hover)
        self.ghost_cv.bind("<Leave>", lambda e: (self.tip.hide(), self.ghost_cv.config(cursor="")))
        self._draw_tray()

        # buttons
        self._btn_end = FlatButton(p, "▷  Start game", self._end_turn, self.F["btn"], "Space", self.F["hint"], primary=True, tip=self.tip, tip_text=TIPS["start"])
        self._btn_end.pack(fill="x", padx=10, pady=(8, 3))
        row = tk.Frame(p, bg=C["panel_bg"]); row.pack(fill="x", padx=10, pady=3)
        self._btn_l1 = FlatButton(row, "Level 1 game", lambda: self._start_setup(1), self.F["btn"], tip=self.tip, tip_text=TIPS["l1"], center=True)
        self._btn_l1.pack(side="left", expand=True, fill="x", padx=(0, 3))
        self._btn_l2 = FlatButton(row, "Level 2 game", lambda: self._start_setup(2), self.F["btn"], tip=self.tip, tip_text=TIPS["l2"], center=True)
        self._btn_l2.pack(side="left", expand=True, fill="x", padx=(3, 0))
        self._btn_voice = FlatButton(p, "♪  Voice: Robo", self._toggle_voice, self.F["btn"], "V", self.F["hint"], tip=self.tip, tip_text=TIPS["voice"])
        self._btn_voice.pack(fill="x", padx=10, pady=3)

        # footer
        tk.Label(p, text="Arrows / WASD or click a neighbouring tile", font=self.F["tiny"], bg=C["panel_bg"], fg=C["dim_col"]).pack()

    def _set_cards(self, n):
        for i, ui in enumerate(self._pui):
            if i < n: ui["border"].pack(fill="x", padx=10, pady=3, before=self._cap_frame)
            else:     ui["border"].pack_forget()

    def _say(self, text, kind="info"):
        col = {"info": C["text_col"], "bad": C["bad"], "good": C["treasure_col"]}[kind]
        self._cap_var.set(text); self._cap_lbl.config(fg=col)

    def _draw_tray(self):
        """Three draggable tokens: Secret Room 1, Secret Room 2 and the ghost marker."""
        cv = self.ghost_cv; cv.delete("all"); self._tray_slots = []
        cw, ch = TRAY_W, 82
        cv.create_text(cw//2, 13, text="Drag to map", font=self.F["h3"], fill=C["text_col"])
        slot_w = cw // 3
        for k, (tok, col, sp) in enumerate((("r0", C["base_p1"], SP_BASE_P1),
                                            ("r1", C["base_p2"], SP_BASE_P2),
                                            ("g",  C["ghost_col"], SP_GHOST))):
            x0, x1, y0, y1 = k*slot_w + 6, (k+1)*slot_w - 6, 26, ch - 6
            on = self._token_enabled(tok); placed = self._token_cell(tok) is not None
            cv.create_rectangle(x0, y0, x1, y1, fill=C["bg"], width=2 if (on and not placed) else 1,
                                outline=col if on else C["dim_col"])
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

    # ── tokens: Secret Rooms and ghost marker ────────────────────────
    def _token_cell(self, tok):
        return self._ghost_panel_cell if tok == "g" else self.rooms[int(tok[1])]

    def _set_token(self, tok, cell):
        if tok == "g": self._ghost_panel_cell = cell
        else:          self.rooms[int(tok[1])] = cell

    def _token_enabled(self, tok):
        if tok == "g": return self.phase == "play" and not self.game_over      # unlocked by Start
        # Secret Rooms move only before the game starts; Player 2's lights up after Player 1's is placed
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
        tok = self._token_at_cell(cell)
        if tok and not self._token_enabled(tok): tok = None
        self._press = dict(src="map", tok=tok, cell=cell, cy=e.y, xy=(e.x_root, e.y_root))
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
            target = cell if self._cell_ok(tok, cell) else self._drag["orig"]   # invalid drop: back to origin
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
        if pr and pr["src"] == "map":                   # plain click on the board
            if self.phase == "play":
                if self.game_over:
                    if pr["cy"] > GRID_BOTTOM: self._start_setup(self.difficulty)
                elif pr["cell"]:
                    self._take_turn(*pr["cell"])
            elif self.phase == "setup":
                self._say("Drag a Secret Room from the panel onto the map.")

    # ── geometry ─────────────────────────────────────────────────────
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
                    self.cv.create_rectangle(x0-2, y0-2, x0+TILE+2, y0+TILE+2,
                                             outline=C["highlight"], width=2, tags="hover")
        if self.game_over and event.y > GRID_BOTTOM: ok = True
        self.cv.config(cursor="hand2" if ok else "")

    # ── screens ──────────────────────────────────────────────────────
    def _draw_banner(self, bg):
        """Clear the board and draw the title strip."""
        self._img_refs.clear(); self.cv.delete("all")
        self.cv.create_rectangle(4, 4, BOARD_W, BOARD_H, fill=bg, outline="")
        ph = SPRITES.get_stretch(SP_TITLE, BOARD_W, TITLE_H)
        if ph:
            self._img_refs.append(ph)
            self.cv.create_image(2, 5, anchor="nw", image=ph)
        else:
            self.cv.create_rectangle(0, 0, BOARD_W, TITLE_H, fill="#0a0a0a", outline=C["panel_border"], width=2)
            self.cv.create_text(BOARD_W//2, TITLE_H//2, text="GHOULS & GRAVEYARDS",
                                font=(self.F["title"].actual("family"), 20, "bold"), fill="#ff0000")

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
        """New game at `level`: the players first drag their Secret Rooms onto the (still empty) map."""
        self.tip.hide(); self.snd.clear(); self.snd.voice = self.voice
        self._btn_voice.set_text(f"♪  Voice: {self.voice}")
        if self._attack_job: self.root.after_cancel(self._attack_job)
        self._attack_job = None
        self.difficulty = level; self.phase = "setup"
        self.game_over = False; self.winner = None; self.reveal_all = False
        self.doors = []; self._locked = False; self._ghost_hold = None
        self.dragon_awake = False; self.ghost_fresh = False
        self.grid = None; self.players = [None, None]; self.num_players = 0; self.cur_p = 0
        self.tr = self.tc = self.dr = self.dc = -1
        self.rooms = [None, None]; self._ghost_panel_cell = None
        self._duel_cell = None; self._flash_wall_edge = None; self._press = None; self._drag = None
        self._panel_img_refs = []
        self._btn_l1.set_active(level == 1); self._btn_l2.set_active(level == 2)
        self._set_end_button("▷  Start game", TIPS["start"]); self._btn_end.set_enabled(True)
        self._set_cards(2)
        self._say("Drag Player 1's Secret Room onto the map. Once it is placed, Player 2's room lights up "
                  "(optional: 2-player game). Then press Start game.")
        self._update_panel(); self._full_redraw(); self._draw_tray()

    @staticmethod
    def _new_player(room):
        return dict(base_r=room[0], base_c=room[1], row=room[0], col=room[1], lives=3, used_steps=0,
                    max_steps=8, carrying=False, alive=True,
                    strength=START_STRENGTH, renew_in=random.randint(*RENEW_MOVES))

    @staticmethod
    def _pick_ghost_spot(rooms, treasure):
        """Sleeping ghost: >= MIN_GHOST_TREAS from the treasure and, when possible, out of the wake-up
        zone of every hero's starting tile."""
        for dist in range(DRAGON_WAKE_DIST + 1, 0, -1):
            cands = far_cells([(rm, dist) for rm in rooms] + [(treasure, MIN_GHOST_TREAS)])
            if cands: return random.choice(cands)
        return treasure

    def _start_game(self):
        """Rooms are placed: now (and only now) the treasure, the ghost and the dungeon are generated."""
        placed = [c for c in self.rooms if c]            # Player 2's room can't exist without Player 1's
        if not placed:
            self._say("Drag at least one Secret Room onto the map first.", "bad"); return
        n = len(placed)
        treasure = random.choice(far_cells([(rm, MIN_TREAS_DIST) for rm in placed]))
        self.tr, self.tc = treasure
        self.dr, self.dc = self._pick_ghost_spot(placed, treasure)
        self.grid = generate_maze(treasure, placed)      # every room has 2 different routes to the treasure
        self.dragon_awake = False; self.ghost_fresh = False
        self.num_players = n
        self.players = [self._new_player(rm) for rm in placed] + [None] * (2 - n)
        for p in self.players[:n]: self._reveal_adjacent(p["row"], p["col"])
        self.cur_p = 0; self.phase = "play"
        self._set_cards(n)
        self._set_end_button("▷  End turn", TIPS["end"])
        self._say("Player 1 starts. Move with the arrow keys or click a neighbouring tile." if n == 2
                  else "Move with the arrow keys or click a neighbouring tile. Find the treasure!")
        self._update_panel(); self._full_redraw(); self._draw_tray()

    # ── magic doors (level 2) ────────────────────────────────────────
    def _treasure_ok(self):
        return treasure_ok(self.grid, (self.tr, self.tc), [rm for rm in self.rooms if rm])

    def _pick_door(self):
        """A random open edge that can close without leaving a Secret Room with fewer than 2 routes."""
        cands = [(r, c, d) for r, c in CELLS for d in ("n", "e")
                 if in_grid(*step(r, c, d)) and not self.grid[r][c].walls[d] and not self.grid[r][c].is_door[d]]
        random.shuffle(cands)
        for spot in cands:
            self._set_door(*spot, True)
            if self._treasure_ok(): return spot
            self._set_door(*spot, False)
        return None

    def _set_door(self, r, c, d, on):
        nr, nc = step(r, c, d)
        for a, b, dd in ((r, c, d), (nr, nc, OPP[d])):
            cell = self.grid[a][b]
            cell.is_door[dd] = on; cell.door_closed[dd] = on
            if not on: cell.door_shown[dd] = False      # an open door is invisible again

    def _mark_edge(self, r, c, d, door):
        """Remember a wall (or door) the warrior bumped into, on both sides of the edge."""
        attr = "door_shown" if door else "wall_shown"
        nr, nc = step(r, c, d)
        self.grid[r][c].seen = True
        getattr(self.grid[r][c], attr)[d] = True
        if in_grid(nr, nc): getattr(self.grid[nr][nc], attr)[OPP[d]] = True

    def _update_doors(self):
        """Once per turn the computer decides which doors reopen and which new ones close, silently."""
        if self.difficulty != 2 or self.grid is None: return
        for dr in list(self.doors):
            dr[3] -= 1
            if dr[3] <= 0:
                self._set_door(dr[0], dr[1], dr[2], False); self.doors.remove(dr)
        for _ in range(2):
            if len(self.doors) < PHANTOM_DOORS and random.random() < 0.5:
                spot = self._pick_door()
                if spot:
                    self._set_door(*spot, True)
                    self.doors.append([spot[0], spot[1], spot[2], random.randint(*DOOR_TURNS)])

    # ═══ DRAWING ═══
    def _blit(self, sp, x, y, w, h=None, cv=None, anchor="center", **kw):
        """Draw sprite `sp` fitted into w x h. Returns False when the sprite file is missing."""
        cv = self.cv if cv is None else cv
        ph = SPRITES.get_fit(sp, w, h or w)
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
            self._draw_edges("door_closed", "door_shown", SP_DOOR, C["door_col"])
        self._draw_treasure(); self._draw_hints(); self._draw_warriors()
        self._draw_map_ghost(); self._draw_real_ghost(); self._draw_flashes()
        if self.game_over: self._redraw_end_overlay()

    def _edge_rect(self, r, c, d):
        """Rectangle of the gap between a tile and its neighbour in direction d."""
        x0, y0 = self._xy(r, c); x1, y1 = x0+TILE, y0+TILE
        if d == "n": return (x0, y0-GAP, x1, y0, True)
        if d == "s": return (x0, y1, x1, y1+GAP, True)
        if d == "w": return (x0-GAP, y0, x0, y1, False)
        return (x1, y0, x1+GAP, y1, False)

    @staticmethod
    def _edge_key(r, c, d):
        """Same key for both sides of an edge, so a wall / door is drawn only once."""
        return tuple(sorted([(r, c), step(r, c, d)]))

    def _seg(self, sp, rect, col):
        x0, y0, x1, y1, horiz = rect
        w, h = x1-x0, y1-y0
        ph = SPRITES.get_fit(sp, w, h) if horiz else SPRITES.get_fit_rot90(sp, w, h)
        if ph:
            self._img_refs.append(ph)
            self.cv.create_image(x0, y0, anchor="nw", image=ph)
        else:
            self.cv.create_rectangle(x0, y0, x1, y1, fill=col, outline="")

    def _draw_edges(self, active, shown, sp, col):
        """Walls / closed doors (Cell attributes `active` / `shown`): drawn only once discovered
        (or when the map is revealed), one sprite per edge."""
        drawn = set()
        for r, c in CELLS:
            cell = self.grid[r][c]
            for d in DIRS:
                if not getattr(cell, active)[d]: continue
                if not (getattr(cell, shown)[d] or self.reveal_all): continue
                key = self._edge_key(r, c, d)
                if key in drawn: continue
                drawn.add(key)
                self._seg(sp, self._edge_rect(r, c, d), col)

    def _draw_bases(self):
        """Secret Room tokens (placed by the players before the game, fixed afterwards)."""
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

    def _draw_chest(self, cx, cy, s, cv=None):
        """Treasure sprite (or a vector chest) on the board or on a panel canvas."""
        cv = self.cv if cv is None else cv
        if not self._blit(SP_TREAS, cx, cy, s, cv=cv): self._chest_fallback(cv, cx, cy, s)

    def _draw_treasure(self):
        if self.tr < 0 or self._carrier(): return
        if not self.reveal_all and not any((q["row"], q["col"]) == (self.tr, self.tc) for q in self._live()): return
        self._draw_chest(*self._cx_cy(self.tr, self.tc), int(TILE * 0.8))

    def _draw_hints(self):
        """Ring on the active hero and faint outlines on the tiles it can step to."""
        if self.game_over: return
        p = self._cur_player()
        if p is None: return
        r, c = p["row"], p["col"]
        for _, nr, nc in neighbors(r, c):
            x0, y0 = self._xy(nr, nc)
            self.cv.create_rectangle(x0+3, y0+3, x0+TILE-3, y0+TILE-3, outline=C["label_col"], dash=(3, 4))
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
            if p["carrying"]:      # reduced treasure at the top-right of the warrior
                badges.append((cx + sz//2 - 5, cy - sz//2 + 5))
        for bx, by in badges:      # drawn last so a warrior sharing the tile never hides it
            self._draw_mini_treasure(bx, by)

    def _draw_map_ghost(self):
        """The player's own ghost marker."""
        if self._ghost_panel_cell is None: return
        cx, cy = self._cx_cy(*self._ghost_panel_cell); sz = int(TILE * 0.75)
        self._blit(SP_GHOST, cx, cy, sz, tags="map_ghost")
        half = sz//2
        self.cv.create_oval(cx-half, cy-half, cx+half, cy+half,
                            outline=C["highlight"], width=1, dash=(4, 3), tags="map_ghost")

    def _draw_real_ghost(self):
        """When the game is over, show where the ghost REALLY is."""
        if not self.reveal_all or self.dr < 0: return
        cx, cy = self._cx_cy(self.dr, self.dc); sz = int(TILE*0.8); half = sz//2 + 2
        m = self._ghost_panel_cell
        if m is not None and m != (self.dr, self.dc):          # arrow: where you thought → where it was
            mx, my = self._cx_cy(*m)
            self.cv.create_line(mx, my, cx, cy, fill=C["bad"], width=2, dash=(5, 3), arrow="last")
        self.cv.create_oval(cx-half, cy-half, cx+half, cy+half, fill="#1a0a0a", outline="#ff3333", width=3)
        if not self._blit(SP_GHOST, cx, cy, sz):
            self.cv.create_oval(cx-half+6, cy-half+6, cx+half-6, cy+half-6, fill="#8888cc", outline="")
        self.cv.create_text(cx, cy+half+7, text="Ghost", fill="#ff6655", font=self.F["tiny"])

    def _draw_flashes(self):
        if self._flash_wall_edge:
            r, c, d, is_door = self._flash_wall_edge
            self._seg(SP_DOOR if is_door else SP_WALL, self._edge_rect(r, c, d),
                      C["door_col"] if is_door else C["wall_col"])
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

    # ── panel drawing ────────────────────────────────────────────────
    def _draw_lives(self, cv, lives, max_l, dead=False):
        cv.delete("all")
        if dead:
            cv.create_text(4, 13, text="💀", font=("Georgia", 14), fill="#cc3333", anchor="w"); return
        for i in range(max_l):
            col = C["heart_on"] if i < lives else C["heart_off"]
            cv.create_text(4+i*22, 13, text="♥", font=("Georgia", 15), fill=col, anchor="w")

    def _footprint(self, cv, cx, cy, s, col, mirror):
        """Vector footprint pointing RIGHT (used when the sprite file is missing)."""
        m = -1 if mirror else 1
        cv.create_oval(cx-0.47*s, cy-0.13*s, cx-0.13*s, cy+0.13*s, fill=col, outline="")      # heel
        cv.create_oval(cx-0.20*s, cy-0.25*s, cx+0.22*s, cy+0.25*s, fill=col, outline="")      # sole
        for tx, ty, tr in ((0.34, -0.19, 0.075), (0.40, -0.07, 0.062), (0.40, 0.04, 0.056), (0.36, 0.14, 0.05)):
            x = cx + tx*s; y = cy + m*ty*s; r = tr*s
            cv.create_oval(x-r, y-r, x+r, y+r, fill=col, outline="")                          # toes

    def _draw_steps(self, cv, used, max_s):
        """Footprints: drawn horizontally (sprite rotated 90° clockwise) and staggered, left/right foot."""
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
        """Player card with no spent steps and no treasure."""
        ui = self._pui[i]
        ui["border"].config(bg=C["panel_sep"])
        self._draw_lives(ui["lives"], lives, 3, dead)
        self._draw_steps(ui["steps"], 0, steps)
        self._draw_treas_icon(ui["treas"], False)
        ui["sv"].set(text)

    def _update_panel(self):
        if self.phase != "play":                       # title / setup: nobody is playing yet
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
        """Banner under the board, so the revealed map and the real ghost stay visible."""
        y0 = GRID_BOTTOM + GAP + 3; y1 = y0 + 28
        if self.winner is not None:
            msg = f"🏆  Player {self.winner+1} wins!"; col = C["treasure_col"]
        else:
            msg = "💀  Game over"; col = "#ff3333"
        self.cv.create_rectangle(PAD, y0, BOARD_W-PAD, y1, fill=C["end_box"], outline=col, width=2)
        self.cv.create_text(PAD+14, (y0+y1)//2, text=msg, anchor="w", font=self.F["end"], fill=col)
        self.cv.create_text(BOARD_W-PAD-12, (y0+y1)//2, anchor="e", font=self.F["small"], fill=C["label_col"], text="Red ring = real ghost  ·  click to play again")

    # ═══ INPUT ═══
    def _bind_keys(self):
        for key, (dr, dc) in {"Left": (0, -1), "Right": (0, 1), "Up": (-1, 0), "Down": (1, 0), "a": (0, -1), "d": (0, 1), "w": (-1, 0), "s": (1, 0)}.items():
            self.root.bind(f"<{key}>", lambda e, dr=dr, dc=dc: self._move(dr, dc))
        self.root.bind("<space>", lambda e: self._end_turn())
        for k in ("v", "V"): self.root.bind(k, lambda e: self._toggle_voice())
        self.cv.bind("<Button-3>", lambda e: self._end_turn())

    def _active_player(self):
        """The current hero, but only while the game runs and the board accepts input."""
        if self.phase != "play" or self.game_over or self._locked or self.grid is None: return None
        return self._cur_player()

    def _move(self, dr, dc):
        p = self._active_player()
        if p and in_grid(p["row"]+dr, p["col"]+dc): self._take_turn(p["row"]+dr, p["col"]+dc)

    def _end_turn(self):
        """During setup this button is 'Start game'; during play it ends the turn."""
        if self.phase == "setup": self._start_game(); return
        p = self._active_player()
        if p: self._say(CAPTIONS["endturn"]); self._finish_turn(p)

    def _toggle_voice(self):
        self.voice = "Natural" if self.voice == "Robo" else "Robo"
        self.snd.voice = self.voice
        self._btn_voice.set_text(f"♪  Voice: {self.voice}")

    # ═══ GAME LOGIC ═══
    def _cur_player(self):
        p = self.players[self.cur_p]
        return p if (p and p["alive"]) else None

    def _live(self): return [q for q in self.players if q and q["alive"]]
    def _carrier(self): return next((q for q in self._live() if q["carrying"]), None)
    def _in_own_base(self, p): return p["row"] == p["base_r"] and p["col"] == p["base_c"]
    def _idx(self, p): return next(i for i, q in enumerate(self.players) if q is p)

    def _warriors_at(self, row, col):
        """Warriors standing on (row, col) outside their own Secret Room (the ghost can reach them)."""
        return [q for q in self._live() if (q["row"], q["col"]) == (row, col) and not self._in_own_base(q)]

    def _spend_strength(self, p):
        """Every move costs a little strength; now and then the computer renews it. Never shown."""
        p["strength"] = max(1, p["strength"] - random.randint(*STRENGTH_LOSS))
        p["renew_in"] -= 1
        if p["renew_in"] <= 0:
            p["strength"] = START_STRENGTH
            p["renew_in"] = random.randint(*RENEW_MOVES)

    def _pick_victim(self, victims):
        """If the ghost jumps two warriors together it attacks the WEAKER one."""
        if len(victims) == 1: return victims[0]
        a, b = victims
        if a["strength"] == b["strength"]: return random.choice(victims)
        return a if a["strength"] < b["strength"] else b

    def _try_wake_ghost(self, p):
        """Every step inside the wake zone is a roll: 25% at distance 3, 50% at 2, 100% at 1.
        A hero inside his own Secret Room can't be sensed."""
        if self.dragon_awake or self._in_own_base(p): return
        d = manhattan(p["row"], p["col"], self.dr, self.dc)
        if d <= DRAGON_WAKE_DIST and random.random() < WAKE_CHANCE[max(d, 1)]:
            self.dragon_awake = True
            self.ghost_fresh = True            # it stirs now, but only moves from its next turn
            self.snd.push("ghostawakes")

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
            self._flash_wall(p["row"], p["col"], d, is_door)
            self.snd.push("hitawall")                     # same "ouch" for walls and doors
            if is_door:
                self._say("A closed door! You stay where you are and your turn is over. "
                          "Try again later: every door opens sooner or later.", "bad")
            p["used_steps"] = p["max_steps"]
            self._finish_turn(p); return

        p["row"] = row; p["col"] = col; p["used_steps"] += 1
        self._spend_strength(p)
        self.grid[row][col].seen = True; self._reveal_adjacent(row, col)
        self.snd.push("tik")
        self._try_wake_ghost(p)

        # stepping on the awake ghost: it attacks (the weaker one, if both warriors are here)
        if self.dragon_awake and (row, col) == (self.dr, self.dc):
            here = self._warriors_at(row, col)
            if here:
                v = self._pick_victim(here)
                others = [q for q in here if q is not v]
                if others:                                # the survivor shares the square with the ghost
                    self._ghost_hold = [others[0], 1 if others[0] is p else 0]
                after = (lambda: self._finish_turn(p)) if v is p else (lambda: self._resume_turn(p))
                self._update_panel(); self._full_redraw()
                self._dragon_attacks(v, after); return

        # treasure: it is heavy, picking it up STOPS the warrior; afterwards 4 moves per turn
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

    def _resume_turn(self, p):
        if self.game_over: return
        if p["used_steps"] >= p["max_steps"]: self._finish_turn(p)
        else: self._update_panel(); self._full_redraw()

    # ── turn flow ────────────────────────────────────────────────────
    def _finish_turn(self, p):
        """End of a warrior's turn: the ghost moves (and may attack), then the next player starts."""
        if self.game_over: return
        self._update_panel(); self._full_redraw()
        if self.dragon_awake and self.snd.busy():   # let the "ouch" / door sound finish before the ghost flies
            self._locked = True
            self._attack_job = self.root.after(900, lambda: self._finish_turn_now(p))
            return
        self._finish_turn_now(p)

    def _finish_turn_now(self, p):
        self._locked = False; self._attack_job = None
        if self.game_over: return
        if self._do_dragon_turn(p): return          # an attack is in progress; it resumes the flow
        self._advance_turn(p)

    def _advance_turn(self, p):
        if self.game_over: return
        p["used_steps"] = 0
        self._update_doors()
        self._next_player()
        self._update_panel(); self._full_redraw()

    # ── ghost ────────────────────────────────────────────────────────
    def _do_dragon_turn(self, p):
        """Move the ghost one step. Returns True if it attacked somebody."""
        if not self.dragon_awake or self.game_over: return False
        if self.ghost_fresh:                        # it has just woken up: it moves from its next turn
            self.ghost_fresh = False; return False
        if self._ghost_hold is not None:            # the ghost waits beside the warrior it did not wound
            hw, skips = self._ghost_hold
            if hw is not p or not hw["alive"]:
                if not hw["alive"]: self._ghost_hold = None
                return False
            if skips > 0:
                self._ghost_hold[1] -= 1; return False
            self._ghost_hold = None
        out = [q for q in self._live() if not self._in_own_base(q)]
        goal = self._carrier() or min(out, key=lambda q: manhattan(self.dr, self.dc, q["row"], q["col"]), default=None)
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

    def _dragon_attacks(self, v, after):
        """The ghost lands on the victim's tile and the marker settles there; the marker stays put
        afterwards (the player can drag it), while the real ghost goes on moving."""
        self._locked = True
        self.dr, self.dc = v["row"], v["col"]
        lethal = v["carrying"] or v["lives"] <= 1
        last = lethal and not any(q is not v for q in self._live())
        if not last:        # on the LAST hero's death the marker is not placed: the player's guess stays his own
            self._ghost_panel_cell = (v["row"], v["col"])
        self.snd.push("ghostattacks")
        self._say("The ghost attacks!", "bad")
        self._draw_tray(); self._full_redraw()
        self._attack_job = self.root.after(ATTACK_DELAY_MS, lambda: self._apply_attack(v, after))

    def _apply_attack(self, v, after):
        self._locked = False; self._attack_job = None
        if self.game_over: return
        n = self._idx(v) + 1
        if v["carrying"]:                       # attacked while carrying the treasure: out of the game
            v["carrying"] = False; v["lives"] = 0
        else:                                   # lose a life, fewer moves, back to the Secret Room
            v["lives"] -= 1
            v["max_steps"] = STEPS_BY_LIVES.get(max(0, v["lives"]), 0)
            v["used_steps"] = 0
            v["row"] = v["base_r"]; v["col"] = v["base_c"]
        if v["lives"] <= 0:
            v["alive"] = False
            survivors = [i for i, q in enumerate(self.players) if q and q["alive"]]
            self.snd.push("gameover")
            if survivors:                       # the other warrior carries on
                self._say(f"Player {n} is out of the game. Player {survivors[0]+1} carries on.", "bad")
                self._update_panel(); self._full_redraw(); after(); return
            self.game_over = True; self.reveal_all = True; self.winner = None
            self._say("The ghost got you. Here is the map, and where it really was.", "bad")
            self._btn_end.set_enabled(False)
            self._update_panel(); self._full_redraw(); return
        self._say(f"Player {n} is sent back to the Secret Room. {v['lives']} "
                  f"{'life' if v['lives'] == 1 else 'lives'} left.", "bad")
        self._update_panel(); self._full_redraw()
        after()

    # ── warrior vs warrior ───────────────────────────────────────────
    def _check_combat(self, p):
        """Called after `p` has landed on a tile. Duel if the other warrior is here and one of them
        holds the treasure. The computer decides using each warrior's hidden strength."""
        if self.num_players < 2: return
        o = self.players[1 - self._idx(p)]
        if not o or not o["alive"] or (o["row"], o["col"]) != (p["row"], p["col"]): return
        if not (p["carrying"] or o["carrying"]): return

        sp, so = p["strength"], o["strength"]       # hidden strength, unrelated to moves per turn
        winner, loser = (p, o) if random.random() < sp/(sp+so) else (o, p)
        widx = self._idx(winner)
        took = loser["carrying"]
        if took:                                # the treasure changes hands
            loser["carrying"] = False
            loser["max_steps"] = STEPS_BY_LIVES[loser["lives"]]     # back to 6 / 8 (or 4)
            winner["carrying"] = True
        winner["max_steps"] = TREASURE_STEPS                        # the winner holds the treasure: 4 moves
        txt = f"Duel! Player {widx+1} wins and {'takes' if took else 'keeps'} the treasure."
        self._say(txt, "good")
        self.snd.push_duel(widx, txt)
        self._duel_cell = (p["row"], p["col"])
        self.root.after(1400, self._clear_duel)
        # the turn continues or ends by the usual rule: used_steps >= max_steps ends it

    def _check_win(self):
        for i, q in enumerate(self.players):
            if q and q["alive"] and q["carrying"] and self._in_own_base(q):
                self._win(i); return True
        return False

    def _win(self, idx):
        self.winner = idx; self.game_over = True; self.reveal_all = True
        self.snd.push("youwin")
        self._say(f"Player {idx+1} brought the treasure home!", "good")
        self._btn_end.set_enabled(False)
        self._update_panel(); self._full_redraw()

    def _reveal_adjacent(self, r, c):
        self.grid[r][c].seen = True
        for d, nr, nc in neighbors(r, c):
            if not self.grid[r][c].walls[d]: self.grid[nr][nc].seen = True

    def _next_player(self):
        if self.num_players == 1: return
        for _ in range(self.num_players):
            self.cur_p = (self.cur_p + 1) % self.num_players
            p = self.players[self.cur_p]
            if p and p["alive"]: break


def main():
    root = tk.Tk()
    root.geometry("+80+40")
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()

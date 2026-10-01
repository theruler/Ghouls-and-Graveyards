import os, math, random, threading, ctypes, ctypes.util
import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageTk

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
SOUND_DIR = os.path.join(BASE_DIR, "data", "sounds")
IMG_DIR   = os.path.join(BASE_DIR, "data", "shapes")

ROWS, COLS   = 8, 8
CELL         = 58
WALL_W       = 6
PAD          = 46
TITLE_H      = 52       # altezza banner titolo in cima al canvas
BOARD_W = PAD*2 + COLS*CELL
BOARD_H = PAD*2 + ROWS*CELL + TITLE_H
PANEL_W = 252
WIN_W   = BOARD_W + PANEL_W + 28
WIN_H   = BOARD_H + 20

MAX_WALLS        = 50
EXTRA_PASSAGES   = 12
MIN_BASE_DIST    = 4
MIN_TREAS_DIST   = 3
DRAGON_WAKE_DIST = 3
STEPS_BY_LIVES   = {3: 8, 2: 6, 1: 4, 0: 0}
PHANTOM_DOORS    = 4
DOOR_INTERVAL_MS = 7000

DELTA = {"n": (-1,0), "s": (1,0), "e": (0,1), "w": (0,-1)}
OPP   = {"n":"s", "s":"n", "e":"w", "w":"e"}
DIRS  = list(DELTA.keys())

C = dict(
    bg           = "#160c08",
    fog          = "#0c0608",
    wall_col     = "#fe6429",
    wall_hi      = "#ff5757",
    wall_lo      = "#ff0000",
    wall_flash   = "#ffffff",
    door_col     = "#7a4400",
    treasure_col = "#ffd700",
    ghost_col    = "#ffffff",
    base_p1      = "#009900",
    base_p2      = "#0055cc",
    panel_bg     = "#0e0a06",
    panel_border = "#6b1800",
    text_col     = "#e0d0b8",
    label_col    = "#806040",
    highlight    = "#ffcc44",
    btn_bg       = "#1c0e06",
    btn_fg       = "#c09060",
    btn_hover    = "#3a1a06",
    heart_on     = "#cc2222",
    heart_off    = "#3a1010",
    end_box      = "#0d0608",
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
CAPTIONS = {
    "tik":           "",
    "no":            "No.",
    "hitawall":      "Ouch!",
    "ghostmoves":    "Ghost moves.",
    "ghostawakes":   "Ghost awakes!",
    "ghostattacks":  "Ghost attacks!",
    "gameover":      "Game over.",
    "foundtreasure": "Found the treasure!",
    "youwin":        "You win!",
    "endturn":       "End of turn.",
    "doorvanish":    "A passage seals…",
    "doorappear":    "A passage opens!",
}

# ---------------------------------------------------------------------------
# Audio backend – miniaudio
# ---------------------------------------------------------------------------
def _build_audio_backend():
    try:
        import miniaudio
        _busy = [False]
        def play(path):
            if not os.path.exists(path): return
            def _t():
                _busy[0] = True
                try:
                    stream = miniaudio.stream_file(path)
                    with miniaudio.PlaybackDevice() as dev:
                        dev.start(stream)
                        import time
                        while dev.callback_generator is not None:
                            time.sleep(0.05)
                except Exception:
                    pass
                _busy[0] = False
            threading.Thread(target=_t, daemon=True).start()
        def busy(): return _busy[0]
        return play, busy
    except Exception:
        pass
    # fallback silenzioso
    return lambda p: None, lambda: False

_audio_play, _audio_busy = _build_audio_backend()


class SoundQueue:
    def __init__(self, root, voice="sayit"):
        self.root       = root
        self.voice      = voice
        self._q         = []
        self._active    = False
        self.on_caption = lambda s: None

    def push(self, key):
        self._q.append(key)
        if not self._active:
            self._fire()

    def clear(self):
        self._q.clear()
        self._active = False

    def busy(self):
        return self._active

    def _fire(self):
        if not self._q:
            self._active = False; return
        self._active = True
        key = self._q.pop(0)
        cap = CAPTIONS.get(key, "")
        if cap:
            self.on_caption(cap)
        idx   = 0 if self.voice == "sayit" else 1
        files = SND_FILES.get(key, [])
        if files:
            fname = files[idx] if idx < len(files) else files[0]
            _audio_play(os.path.join(SOUND_DIR, fname))
            self._wait()
        else:
            self.root.after(900 if cap else 0, self._fire)

    def _wait(self):
        if _audio_busy():
            self.root.after(60, self._wait)
        else:
            self.root.after(20, self._fire)


# ---------------------------------------------------------------------------
# Sprite loader
# ---------------------------------------------------------------------------
class SpriteCache:
    """Carica e ridimensiona i PNG da data/shapes/."""
    def __init__(self):
        self._raw   = {}   # {num: PIL.Image}
        self._cache = {}   # {(num, w, h): ImageTk.PhotoImage}

    def _load(self, num):
        if num not in self._raw:
            path = os.path.join(IMG_DIR, f"{num}.png")
            if os.path.exists(path):
                self._raw[num] = Image.open(path).convert("RGBA")
            else:
                self._raw[num] = None
        return self._raw[num]

    def get(self, num, size):
        """Restituisce un PhotoImage quadrato di lato `size`."""
        key = (num, size, size)
        if key not in self._cache:
            img = self._load(num)
            if img is None:
                self._cache[key] = None
            else:
                resized = img.resize((size, size), Image.LANCZOS)
                self._cache[key] = ImageTk.PhotoImage(resized)
        return self._cache[key]

    def get_wh(self, num, w, h):
        key = (num, w, h)
        if key not in self._cache:
            img = self._load(num)
            if img is None:
                self._cache[key] = None
            else:
                resized = img.resize((w, h), Image.LANCZOS)
                self._cache[key] = ImageTk.PhotoImage(resized)
        return self._cache[key]

SPRITES = SpriteCache()

# Sprite id
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

# ---------------------------------------------------------------------------
# Maze
# ---------------------------------------------------------------------------
class Cell:
    __slots__ = ("row","col","walls","wall_shown","seen","is_door","door_closed")
    def __init__(self, r, c):
        self.row, self.col = r, c
        self.walls      = {d: True  for d in DIRS}
        self.wall_shown = {d: False for d in DIRS}
        self.seen       = False
        self.is_door    = {d: False for d in DIRS}
        self.door_closed= {d: False for d in DIRS}

    def passable(self, d):
        return not self.walls[d] and not self.door_closed[d]

    def open_count(self):
        return sum(1 for d in DIRS if not self.walls[d])


def _carve(grid, r, c, d):
    grid[r][c].walls[d] = False
    nr, nc = r+DELTA[d][0], c+DELTA[d][1]
    grid[nr][nc].walls[OPP[d]] = False


def generate_maze(tr, tc):
    grid = [[Cell(r,c) for c in range(COLS)] for r in range(ROWS)]
    sr, sc = random.randrange(ROWS), random.randrange(COLS)
    grid[sr][sc].seen = True
    frontier = [(sr, sc)]

    while frontier:
        i = random.randrange(len(frontier))
        r, c = frontier[i]
        nbrs = [(d,r+DELTA[d][0],c+DELTA[d][1])
                for d in DIRS
                if 0<=r+DELTA[d][0]<ROWS and 0<=c+DELTA[d][1]<COLS
                and not grid[r+DELTA[d][0]][c+DELTA[d][1]].seen]
        if not nbrs:
            frontier.pop(i); continue
        d, nr, nc = random.choice(nbrs)
        _carve(grid, r, c, d)
        grid[nr][nc].seen = True
        frontier.append((nr, nc))

    def count_walls():
        return sum(1 for r in range(ROWS) for c in range(COLS)
                   for d in ["s","e"]
                   if (0<=r+DELTA[d][0]<ROWS and 0<=c+DELTA[d][1]<COLS
                       and grid[r][c].walls[d]))

    added, attempts = 0, 0
    while added < EXTRA_PASSAGES and count_walls() > MAX_WALLS and attempts < 2000:
        attempts += 1
        r,c = random.randrange(ROWS), random.randrange(COLS)
        d   = random.choice(DIRS)
        nr,nc = r+DELTA[d][0], c+DELTA[d][1]
        if 0<=nr<ROWS and 0<=nc<COLS and grid[r][c].walls[d]:
            _carve(grid, r, c, d); added += 1

    while grid[tr][tc].open_count() < 2:
        cands = [d for d in DIRS
                 if (0<=tr+DELTA[d][0]<ROWS and 0<=tc+DELTA[d][1]<COLS
                     and grid[tr][tc].walls[d])]
        if not cands: break
        _carve(grid, tr, tc, random.choice(cands))

    for row in grid:
        for cell in row: cell.seen = False
    return grid


def manhattan(r1,c1,r2,c2): return abs(r1-r2)+abs(c1-c2)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class App:

    def __init__(self, root):
        self.root = root
        self.root.title("Ghouls & Graveyards")
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, False)

        self._fonts()
        self._build_ui()

        self.num_players = 1
        self.difficulty  = 1
        self.voice       = "sayit"

        self.grid          = None
        self.players       = [None, None]
        self.cur_p         = 0
        self.dr = self.dc  = -1
        self.dragon_awake  = False
        self.dragon_exact  = False
        self.tr = self.tc  = -1
        self.game_over     = False
        self.winner        = None
        self.reveal_all    = False
        self.doors         = []
        self._door_job     = None
        self.end_turn_flag = False

        # fantasma draggable (segnaposto utente)
        self._drag_ghost_id   = None   # canvas item id
        self._drag_ghost_pos  = None   # (col, row) snap corrente
        self._drag_active     = False
        self._drag_offset     = (0, 0)

        # immagini references (evita GC)
        self._img_refs = []

        self.snd = SoundQueue(root, self.voice)
        self.snd.on_caption = lambda t: self._cap_var.set(t)

        self._show_title()
        self._bind_keys()

    def _fonts(self):
        self.F = {}
        for name, fam, sz, wt in [
            ("title",  "Georgia", 18, "bold"),
            ("h2",     "Georgia", 12, "bold"),
            ("body",   "Georgia", 10, "normal"),
            ("small",  "Georgia",  9, "normal"),
            ("caption","Georgia", 10, "normal"),
            ("mono",   "Courier", 10, "bold"),
            ("tiny",   "Courier",  8, "normal"),
            ("btn",    "Georgia", 10, "bold"),
        ]:
            self.F[name] = tkfont.Font(family=fam, size=sz, weight=wt)

    def _build_ui(self):
        outer = tk.Frame(self.root, bg=C["bg"])
        outer.pack(padx=6, pady=6)

        self.cv = tk.Canvas(
            outer, width=BOARD_W, height=BOARD_H,
            bg=C["bg"], highlightthickness=2,
            highlightbackground=C["panel_border"],
        )
        self.cv.pack(side="left")
        self.cv.bind("<Button-1>",        self._on_click)
        self.cv.bind("<ButtonPress-3>",   self._drag_start)
        self.cv.bind("<B3-Motion>",       self._drag_motion)
        self.cv.bind("<ButtonRelease-3>", self._drag_end)

        panel = tk.Frame(outer, bg=C["panel_bg"], width=PANEL_W)
        panel.pack(side="right", fill="y", padx=(8,0))
        panel.pack_propagate(False)
        self._build_panel(panel)

    def _build_panel(self, p):
        self._hsep(p)
        self._pui = []
        pc = [C["base_p1"], C["base_p2"]]
        for i in range(2):
            fr = tk.LabelFrame(p, text=f"  Player {i+1}  ",
                font=self.F["h2"], bg=C["panel_bg"],
                fg=pc[i], bd=1, relief="ridge", padx=6, pady=4)
            fr.pack(fill="x", padx=8, pady=3)
            lives_cv = tk.Canvas(fr, width=72, height=18,
                bg=C["panel_bg"], highlightthickness=0)
            lives_cv.pack(anchor="w")
            steps_cv = tk.Canvas(fr, width=220, height=18,
                bg=C["panel_bg"], highlightthickness=0)
            steps_cv.pack(anchor="w", pady=(2,0))

            sv = tk.StringVar(value="")
            tk.Label(fr, textvariable=sv, font=self.F["small"],
                bg=C["panel_bg"], fg=C["text_col"],
                wraplength=210, justify="left").pack(anchor="w")
            self._pui.append((fr, lives_cv, steps_cv, sv))

        self._hsep(p)

        self._cap_var = tk.StringVar(value="")
        tk.Label(p, textvariable=self._cap_var,
            font=self.F["caption"], bg=C["panel_bg"],
            fg=C["highlight"], wraplength=236,
            justify="center", height=2).pack(fill="x", padx=6)

        self._turn_var = tk.StringVar(value="")
        tk.Label(p, textvariable=self._turn_var,
            font=self.F["mono"], bg=C["panel_bg"],
            fg=C["highlight"]).pack(pady=(2,4))

        self._hsep(p)

        bkw = dict(font=self.F["btn"], bg=C["btn_bg"], fg=C["btn_fg"],
                   activebackground=C["btn_hover"],
                   activeforeground=C["highlight"],
                   relief="raised", bd=2, padx=4, pady=5,
                   anchor="w", cursor="hand2")
        self._btn_end = tk.Button(p, text="▷  End Turn  [Space]",
            command=self._end_turn, **bkw)
        self._btn_end.pack(fill="x", padx=8, pady=2)

        tk.Button(p, text="⟳  New Game  [R]",
            command=self._dialog_new_game, **bkw).pack(fill="x", padx=8, pady=2)

        self._btn_voice = tk.Button(p, text="♪  Voice: sayit",
            command=self._toggle_voice, **bkw)
        self._btn_voice.pack(fill="x", padx=8, pady=2)

        self._hsep(p)

        tk.Label(p, text="LEGEND", font=self.F["tiny"],
            bg=C["panel_bg"], fg=C["label_col"]).pack(anchor="w", padx=10, pady=(4,2))
        leg = [
            (C["base_p1"],     "P1 Secret Room"),
            (C["base_p2"],     "P2 Secret Room"),
            (C["treasure_col"],"Treasure Room"),
            (C["ghost_col"],   "Ghost draggable (guess!)"),
            (C["wall_col"],    "Discovered wall"),
            (C["door_col"],    "Phantom door (Lvl 2)"),
        ]
        for col, txt in leg:
            row = tk.Frame(p, bg=C["panel_bg"]); row.pack(anchor="w", padx=12, pady=1)
            tk.Label(row, text="  ", bg=col, width=2,
                relief="solid", bd=1).pack(side="left")
            tk.Label(row, text="  "+txt, font=self.F["tiny"],
                fg=C["label_col"], bg=C["panel_bg"]).pack(side="left")

        self._hsep(p)

        self._diff_var = tk.StringVar(value="")
        tk.Label(p, textvariable=self._diff_var, font=self.F["tiny"],
            bg=C["panel_bg"], fg=C["label_col"], justify="center").pack(pady=(2,0))
        tk.Label(p, text="Arrows / click to move\nSpace = End turn   R = New game\nTasto destro = trascina fantasma",
            font=self.F["tiny"], bg=C["panel_bg"],
            fg=C["label_col"], justify="center").pack(pady=(2,8))

    def _hsep(self, parent):
        tk.Frame(parent, bg=C["panel_border"], height=2).pack(fill="x", padx=8, pady=4)

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------
    def _board_y0(self):
        """Offset Y del labirinto sotto il titolo."""
        return TITLE_H

    def _xy(self, r, c):
        return PAD + c*CELL, self._board_y0() + PAD + r*CELL

    def _cx_cy(self, r, c):
        x0, y0 = self._xy(r, c)
        return x0+CELL//2, y0+CELL//2

    def _cell_from_xy(self, x, y):
        """Restituisce (row, col) dalla posizione canvas, o None."""
        y -= self._board_y0()
        col = (x  - PAD) // CELL
        row = (y  - PAD) // CELL
        if 0 <= row < ROWS and 0 <= col < COLS:
            return row, col
        return None

    # ------------------------------------------------------------------
    # Show title screen
    # ------------------------------------------------------------------
    def _show_title(self):
        self.cv.delete("all")
        self.cv.create_rectangle(0, 0, BOARD_W, BOARD_H, fill="#1a0a06")

        # titolo con PNG 47
        ph = SPRITES.get_wh(SP_TITLE, BOARD_W, TITLE_H)
        if ph:
            self._img_refs.append(ph)
            self.cv.create_image(0, 0, anchor="nw", image=ph)
        else:
            self.cv.create_rectangle(0, 0, BOARD_W, TITLE_H, fill="#0a0a0a", outline=C["wall_lo"], width=2)
            self.cv.create_text(BOARD_W//2, TITLE_H//2,
                text="GHOULS & GRAVEYARDS",
                font=("Georgia", max(10, TITLE_H//5), "bold"), fill="#ff0000")

        cx, cy = BOARD_W//2, TITLE_H + (BOARD_H-TITLE_H)//2

        # fantasma centrato
        ph_ghost = SPRITES.get(SP_GHOST, 80)
        if ph_ghost:
            self._img_refs.append(ph_ghost)
            self.cv.create_image(cx, cy-20, anchor="center", image=ph_ghost)

        self.cv.create_text(cx, cy+60,
            text="Python/Tkinter  ·  based on Mattel Electronics 1980",
            font=self.F["small"], fill=C["label_col"])
        self.cv.create_text(cx, cy+100,
            text="Press  New Game [R]  to begin",
            font=("Georgia",12,"italic"), fill=C["highlight"])

        self._cap_var.set(""); self._turn_var.set("")
        self._btn_end.config(state="disabled")
        for i in range(2):
            _,lc,sc,sv = self._pui[i]
            self._draw_lives(lc, 0, 3)
            self._draw_steps(sc, 0, 8)
            sv.set("")

    # ------------------------------------------------------------------
    # Dialog
    # ------------------------------------------------------------------
    def _dialog_new_game(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("New Game"); dlg.configure(bg=C["bg"])
        dlg.resizable(False,False); dlg.grab_set()

        tk.Label(dlg, text="NEW GAME", font=("Georgia",16,"bold"),
            bg=C["bg"], fg=C["treasure_col"]).pack(pady=(16,6))

        tk.Label(dlg, text="Players:", font=self.F["body"],
            bg=C["bg"], fg=C["text_col"]).pack()
        np_var = tk.IntVar(value=self.num_players)
        f = tk.Frame(dlg, bg=C["bg"]); f.pack()
        for n,lbl in [(1,"1 Player"),(2,"2 Players")]:
            tk.Radiobutton(f, text=lbl, variable=np_var, value=n,
                bg=C["bg"], fg=C["text_col"], selectcolor=C["panel_bg"],
                font=self.F["body"]).pack(side="left", padx=14)

        tk.Label(dlg, text="Difficulty:", font=self.F["body"],
            bg=C["bg"], fg=C["text_col"]).pack(pady=(10,0))
        dv = tk.IntVar(value=self.difficulty)
        f2 = tk.Frame(dlg, bg=C["bg"]); f2.pack()
        tk.Radiobutton(f2, text="Level 1 — Classic",
            variable=dv, value=1, bg=C["bg"], fg=C["text_col"],
            selectcolor=C["panel_bg"], font=self.F["body"]).pack(side="left", padx=14)
        tk.Radiobutton(f2, text="Level 2 — Phantom Doors",
            variable=dv, value=2, bg=C["bg"], fg=C["text_col"],
            selectcolor=C["panel_bg"], font=self.F["body"]).pack(side="left", padx=14)

        tk.Label(dlg, text="Voice:", font=self.F["body"],
            bg=C["bg"], fg=C["text_col"]).pack(pady=(10,0))
        vv = tk.StringVar(value=self.voice)
        f3 = tk.Frame(dlg, bg=C["bg"]); f3.pack()
        for v,lbl in [("sayit","TTS (sayit)"),("nat","Natural voice")]:
            tk.Radiobutton(f3, text=lbl, variable=vv, value=v,
                bg=C["bg"], fg=C["text_col"], selectcolor=C["panel_bg"],
                font=self.F["body"]).pack(side="left", padx=14)

        def start():
            self.num_players = np_var.get()
            self.difficulty  = dv.get()
            self.voice       = vv.get()
            dlg.destroy()
            self._new_game()

        tk.Button(dlg, text="▷  Start Game", command=start,
            font=("Georgia",11,"bold"), bg=C["btn_bg"], fg=C["btn_fg"],
            activebackground=C["btn_hover"], relief="raised", bd=2,
            padx=10, pady=8, cursor="hand2").pack(pady=(4,18))

        dlg.update_idletasks()
        x = self.root.winfo_x()+(self.root.winfo_width() -dlg.winfo_width())//2
        y = self.root.winfo_y()+(self.root.winfo_height()-dlg.winfo_height())//2
        dlg.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # New game
    # ------------------------------------------------------------------
    def _new_game(self):
        self.snd.clear()
        self.snd.voice = self.voice
        if self._door_job:
            self.root.after_cancel(self._door_job)
            self._door_job = None

        self.game_over     = False
        self.winner        = None
        self.reveal_all    = False
        self.end_turn_flag = False
        self.doors         = []
        self.dragon_awake  = False
        self.dragon_exact  = False
        self.dr = self.dc  = -1
        self._drag_ghost_id  = None
        self._drag_ghost_pos = None
        self._img_refs.clear()

        base_pos = []
        for i in range(self.num_players):
            for _ in range(5000):
                br = random.randrange(ROWS); bc = random.randrange(COLS)
                if all(manhattan(br,bc,pr,pc)>=MIN_BASE_DIST for pr,pc in base_pos):
                    base_pos.append((br,bc)); break
            else:
                base_pos.append((random.randrange(ROWS), random.randrange(COLS)))

        for _ in range(5000):
            tr = random.randrange(ROWS); tc = random.randrange(COLS)
            if all(manhattan(tr,tc,br,bc)>=MIN_TREAS_DIST for br,bc in base_pos):
                break
        self.tr, self.tc = tr, tc
        self.grid = generate_maze(tr, tc)

        self.players = [None, None]
        for i in range(self.num_players):
            br, bc = base_pos[i]
            self.players[i] = dict(
                base_r=br, base_c=bc, row=br, col=bc,
                lives=3, used_steps=0, max_steps=8,
                carrying=False, placed=False, alive=True,
            )

        self.cur_p = 0
        self._diff_var.set(
            f"{'1' if self.num_players==1 else '2'}-player  ·  "
            f"{'Level 1' if self.difficulty==1 else 'Level 2 — Phantom Doors'}"
        )
        self._btn_end.config(state="normal")
        self.snd.on_caption = lambda t: self._cap_var.set(t)
        self._update_panel()
        self._full_redraw()

        if self.difficulty == 2:
            self._door_job = self.root.after(DOOR_INTERVAL_MS, self._toggle_doors)

    # ------------------------------------------------------------------
    # Phantom doors
    # ------------------------------------------------------------------
    def _toggle_doors(self):
        if self.game_over: return
        had = bool(self.doors)
        for r,c,d in self.doors:
            self.grid[r][c].door_closed[d] = False
            self.grid[r][c].is_door[d]     = False
            nr,nc = r+DELTA[d][0], c+DELTA[d][1]
            self.grid[nr][nc].door_closed[OPP[d]] = False
            self.grid[nr][nc].is_door[OPP[d]]     = False
        self.doors.clear()

        cands = []
        for r in range(ROWS):
            for c in range(COLS):
                for d in ["n","e"]:
                    nr,nc = r+DELTA[d][0], c+DELTA[d][1]
                    if not (0<=nr<ROWS and 0<=nc<COLS): continue
                    if self.grid[r][c].walls[d]: continue
                    if (r==self.tr and c==self.tc
                            and self.grid[r][c].open_count()<=2): continue
                    if (nr==self.tr and nc==self.tc
                            and self.grid[nr][nc].open_count()<=2): continue
                    cands.append((r,c,d))

        random.shuffle(cands)
        new_doors = cands[:PHANTOM_DOORS]
        for r,c,d in new_doors:
            self.grid[r][c].door_closed[d] = True
            self.grid[r][c].is_door[d]     = True
            nr,nc = r+DELTA[d][0], c+DELTA[d][1]
            self.grid[nr][nc].door_closed[OPP[d]] = True
            self.grid[nr][nc].is_door[OPP[d]]     = True
        self.doors = new_doors

        if had and new_doors: self._cap_var.set(CAPTIONS["doorappear"]+"  "+CAPTIONS["doorvanish"])
        elif had:             self._cap_var.set(CAPTIONS["doorappear"])
        elif new_doors:       self._cap_var.set(CAPTIONS["doorvanish"])

        self._full_redraw()
        self._door_job = self.root.after(DOOR_INTERVAL_MS, self._toggle_doors)

    # ------------------------------------------------------------------
    # Full redraw
    # ------------------------------------------------------------------
    def _full_redraw(self):
        self._img_refs.clear()
        self.cv.delete("all")
        self.cv.create_rectangle(0, 0, BOARD_W, BOARD_H, fill=C["bg"])

        # --- Titolo in cima ---
        ph_title = SPRITES.get_wh(SP_TITLE, BOARD_W, TITLE_H)
        if ph_title:
            self._img_refs.append(ph_title)
            self.cv.create_image(0, 0, anchor="nw", image=ph_title)
        else:
            self.cv.create_rectangle(0, 0, BOARD_W, TITLE_H, fill="#0a0a0a", outline=C["wall_lo"], width=2)
            self.cv.create_text(BOARD_W//2, TITLE_H//2,
                text="GHOULS & GRAVEYARDS",
                font=("Georgia", max(10, TITLE_H//5), "bold"), fill="#ff0000")

        # --- Floor tiles: SEMPRE tutte visibili ---
        for r in range(ROWS):
            for c in range(COLS):
                x0, y0 = self._xy(r, c)
                ph = SPRITES.get(SP_FLOOR, CELL)
                if ph:
                    self._img_refs.append(ph)
                    self.cv.create_image(x0, y0, anchor="nw", image=ph)
                else:
                    self.cv.create_rectangle(x0, y0, x0+CELL, y0+CELL, fill="#2b1a10", outline="")

        # --- Basi: sempre visibili ---
        self._draw_bases()

        # --- Fog of war SOLO per muri/porte, tesoro, fantasma ---
        # (gestita nelle singole funzioni di draw)

        self._draw_walls()
        self._draw_doors()
        self._draw_treasure()
        self._draw_dragon()
        self._draw_warriors()

        # --- Fantasma draggable (segnaposto utente) ---
        self._draw_drag_ghost()

        # --- Tesoro in miniatura in alto a destra se raccolto ---
        self._draw_carried_treasure_icon()

        if self.game_over:
            self._redraw_end_overlay()

    # ------------------------------------------------------------------
    # Draw helpers
    # ------------------------------------------------------------------
    def _draw_walls(self):
        drawn = set()
        ph_wall = SPRITES.get(SP_WALL, WALL_W*4)  # sprite piccolo per muri
        for r in range(ROWS):
            for c in range(COLS):
                cell = self.grid[r][c]
                for d in DIRS:
                    if not (cell.wall_shown[d] or self.reveal_all):
                        continue
                    if not cell.walls[d]:
                        continue
                    nr, nc = r+DELTA[d][0], c+DELTA[d][1]
                    key = (min(r,nr), min(c,nc), max(r,nr), max(c,nc))
                    if key in drawn:
                        continue
                    drawn.add(key)

                    x0, y0 = self._xy(r, c)
                    x1, y1 = x0+CELL, y0+CELL
                    # Disegna muro con rettangolo colorato + sprite opzionale
                    if d == "n":
                        self._draw_wall_segment(x0+2, y0-3, x1-2, y0+3, horizontal=True)
                    elif d == "s":
                        self._draw_wall_segment(x0+2, y1-3, x1-2, y1+3, horizontal=True)
                    elif d == "w":
                        self._draw_wall_segment(x0-3, y0+2, x0+3, y1-2, horizontal=False)
                    elif d == "e":
                        self._draw_wall_segment(x1-3, y0+2, x1+3, y1-2, horizontal=False)

    def _draw_wall_segment(self, x0, y0, x1, y1, horizontal):
        w = x1-x0
        h = y1-y0
        if w <= 0 or h <= 0:
            return
        ph = SPRITES.get_wh(SP_WALL, max(1,w), max(1,h))
        if ph:
            self._img_refs.append(ph)
            self.cv.create_image(x0, y0, anchor="nw", image=ph)
        else:
            self.cv.create_rectangle(x0, y0, x1, y1, fill=C["wall_col"], outline="")

    def _draw_doors(self):
        for r in range(ROWS):
            for c in range(COLS):
                cell = self.grid[r][c]
                if not (cell.seen or self.reveal_all):
                    continue
                x0, y0 = self._xy(r, c)
                x1, y1 = x0+CELL, y0+CELL
                for d in DIRS:
                    if not cell.is_door[d]:
                        continue
                    if d in ("n","s"):
                        yy = y0 if d=="n" else y1
                        mc = (x0+x1)//2
                        ph = SPRITES.get_wh(SP_DOOR, 16, 6)
                        if ph:
                            self._img_refs.append(ph)
                            self.cv.create_image(mc-8, yy-3, anchor="nw", image=ph)
                        else:
                            self.cv.create_rectangle(mc-8, yy-2, mc+8, yy+2, fill=C["door_col"], outline="")
                    else:
                        xx = x0 if d=="w" else x1
                        mr = (y0+y1)//2
                        ph = SPRITES.get_wh(SP_DOOR, 6, 16)
                        if ph:
                            self._img_refs.append(ph)
                            self.cv.create_image(xx-3, mr-8, anchor="nw", image=ph)
                        else:
                            self.cv.create_rectangle(xx-2, mr-8, xx+2, mr+8, fill=C["door_col"], outline="")

    def _draw_treasure(self):
        if self.tr < 0: return
        # fog of war per il tesoro
        if not self.reveal_all and not self.grid[self.tr][self.tc].seen: return
        # Se qualcuno porta il tesoro, non mostrarlo sulla mappa
        for p in self.players:
            if p and p["carrying"]:
                return
        x0, y0 = self._xy(self.tr, self.tc)
        ph = SPRITES.get(SP_TREAS, CELL-4)
        if ph:
            self._img_refs.append(ph)
            cx, cy = self._cx_cy(self.tr, self.tc)
            self.cv.create_image(cx, cy, anchor="center", image=ph)

    def _draw_carried_treasure_icon(self):
        """Mostra miniatura del tesoro in alto a destra se un giocatore lo porta."""
        carrying = any(p and p["carrying"] for p in self.players)
        if not carrying: return
        size = 24
        margin = 4
        x = BOARD_W - size - margin
        y = TITLE_H + margin   # appena sotto il titolo
        ph = SPRITES.get(SP_TREAS, size)
        if ph:
            self._img_refs.append(ph)
            self.cv.create_image(x, y, anchor="nw", image=ph)

    def _draw_bases(self):
        base_size = int(CELL * 1.15)  # leggermente più grande della floor tile
        for i in range(self.num_players):
            p = self.players[i]
            if p is None: continue
            sp = SP_BASE_P1 if i == 0 else SP_BASE_P2
            x0, y0 = self._xy(p["base_r"], p["base_c"])
            cx = x0 + CELL//2
            cy = y0 + CELL//2
            half = base_size // 2
            ph = SPRITES.get(sp, base_size)
            if ph:
                self._img_refs.append(ph)
                self.cv.create_image(cx, cy, anchor="center", image=ph)
            else:
                col = C["base_p1"] if i == 0 else C["base_p2"]
                self.cv.create_rectangle(cx-half, cy-half, cx+half, cy+half, fill=col, outline="")

    def _draw_dragon(self):
        # Il fantasma reale è SEMPRE nascosto → non lo disegniamo mai
        pass

    def _draw_drag_ghost(self):
        """Disegna il segnaposto draggable del fantasma."""
        if self._drag_ghost_pos is None or self.grid is None:
            return
        gc, gr = self._drag_ghost_pos  # col, row
        if not (0 <= gr < ROWS and 0 <= gc < COLS):
            return
        cx, cy = self._cx_cy(gr, gc)
        size = CELL - 8
        ph = SPRITES.get(SP_GHOST, size)
        if ph:
            self._img_refs.append(ph)
            tag = "drag_ghost"
            self.cv.create_image(cx, cy, anchor="center", image=ph, tags=tag)
            # bordo tratteggiato per indicare che è il segnaposto utente
            self.cv.create_oval(cx-size//2, cy-size//2, cx+size//2, cy+size//2,
                outline=C["highlight"], width=1, dash=(4,3), tags=tag)

    def _draw_warriors(self):
        for i in range(self.num_players):
            p = self.players[i]
            if p is None or not p["alive"] or not p["placed"]: continue
            cx, cy = self._cx_cy(p["row"], p["col"])
            sp = SP_P1 if i == 0 else SP_P2
            size = CELL - 6

            active = (i == self.cur_p) and not self.game_over
            if active:
                col = C["base_p1"] if i==0 else C["base_p2"]
                self.cv.create_oval(cx-24, cy-24, cx+24, cy+24,
                    fill=col, outline="", stipple="gray12")

            ph = SPRITES.get(sp, size)
            if ph:
                self._img_refs.append(ph)
                self.cv.create_image(cx, cy, anchor="center", image=ph)
            else:
                col = C["base_p1"] if i==0 else C["base_p2"]
                self.cv.create_rectangle(cx-size//3, cy-size//3,
                    cx+size//3, cy+size//3, fill=col, outline="")

            if p["carrying"]:
                # stella piccola invece del testo
                self.cv.create_text(cx+16, cy-16, text="★",
                    font=("Georgia",11), fill=C["treasure_col"])

    def _draw_lives(self, cv, lives, max_l):
        cv.delete("all")
        for i in range(max_l):
            col = C["heart_on"] if i < lives else C["heart_off"]
            cv.create_text(6+i*22, 9, text="♥",
                font=("Georgia",13), fill=col, anchor="w")

    def _draw_steps(self, cv, used, max_s):
        cv.delete("all")
        if max_s == 0: return
        slot_w = min(22, (220-4)//max_s)
        for i in range(max_s):
            cx = 4 + i*slot_w + slot_w//2
            cy = 9
            is_used = (i < used)
            sp = SP_STEP_US if is_used else SP_STEP_AV
            size = min(10, slot_w-2)
            ph = SPRITES.get(sp, size)
            if ph:
                # keep reference
                cv.create_image(cx, cy, anchor="center", image=ph)
                # nota: le ref per i canvas panel non vanno in self._img_refs
                # usiamo un attributo temporaneo per evitare GC
                if not hasattr(self, "_panel_img_refs"):
                    self._panel_img_refs = []
                self._panel_img_refs.append(ph)
            else:
                col = C["step_used"] if is_used else "#ff0000"
                cv.create_oval(cx-size//2, cy-size//2, cx+size//2, cy+size//2,
                    fill=col, outline="")

    # ------------------------------------------------------------------
    # Panel update
    # ------------------------------------------------------------------
    def _update_panel(self):
        if hasattr(self, "_panel_img_refs"):
            self._panel_img_refs.clear()
        pc = [C["base_p1"], C["base_p2"]]
        for i in range(2):
            fr, lc, sc, sv = self._pui[i]
            p = self.players[i]
            if p is None:
                fr.config(fg=C["label_col"])
                self._draw_lives(lc, 0, 3)
                self._draw_steps(sc, 0, 8)
                sv.set("—"); continue
            if not p["alive"]:
                fr.config(fg=C["label_col"])
                self._draw_lives(lc, 0, 3)
                self._draw_steps(sc, 0, 8)
                sv.set("Eliminated"); continue
            active = (i == self.cur_p) and not self.game_over
            fr.config(fg=pc[i], relief="ridge" if active else "flat",
                      bd=2 if active else 1)
            self._draw_lives(lc, p["lives"], 3)
            self._draw_steps(sc, p["used_steps"], p["max_steps"])
            if not p["placed"]:
                sv.set("Click to choose\nyour Secret Room")
            elif p["carrying"]:
                sv.set("★ Carrying treasure!")
            else:
                sv.set("")

        if self.game_over:
            self._turn_var.set(
                f"🏆  Player {self.winner+1} wins!" if self.winner is not None
                else "💀  Game over")
        else:
            self._turn_var.set(f"Player {self.cur_p+1}'s turn")

    # ------------------------------------------------------------------
    # End overlay (trasparente)
    # ------------------------------------------------------------------
    def _end_overlay(self, *, won):
        self._redraw_end_overlay(won=won)
        self._btn_end.config(state="disabled")

    def _redraw_end_overlay(self, *, won=None):
        if won is None:
            won = (self.winner is not None)
        cx, cy = BOARD_W//2, BOARD_H//2
        # sfondo semi-trasparente (stipple) invece di nero pieno
        self.cv.create_rectangle(cx-168, cy-60, cx+168, cy+76,
            fill=C["end_box"], outline=C["treasure_col"], width=3,
            stipple="gray50", tags="end")
        if won and self.winner is not None:
            msg = f"🏆  Player {self.winner+1} Wins!"
            col = C["treasure_col"]
        else:
            msg = "💀  Game Over"
            col = "#ff3333"
        self.cv.create_text(cx, cy-20, text=msg,
            font=("Georgia",22,"bold"), fill=col, tags="end")
        self.cv.create_text(cx, cy+28,
            text="Full map revealed\nPress  New Game [R]  to play again",
            font=self.F["body"], fill=C["text_col"],
            justify="center", tags="end")

    # ------------------------------------------------------------------
    # Wall flash
    # ------------------------------------------------------------------
    def _flash_wall(self, r, c, d):
        x0, y0 = self._xy(r, c)
        x1, y1 = x0+CELL, y0+CELL
        tag = f"wf_{r}_{c}_{d}"
        if d == "n":
            self._draw_wall_segment(x0+2, y0-3, x1-2, y0+3, horizontal=True)
        elif d == "s":
            self._draw_wall_segment(x0+2, y1-3, x1-2, y1+3, horizontal=True)
        elif d == "w":
            self._draw_wall_segment(x0-3, y0+2, x0+3, y1-2, horizontal=False)
        elif d == "e":
            self._draw_wall_segment(x1-3, y0+2, x1+3, y1-2, horizontal=False)
        self.cv.create_rectangle(x0, y0, x1, y1,
            fill=C["wall_flash"], outline="", stipple="gray25", tags=tag)
        self.root.after(400, lambda: self.cv.delete(tag))

    # ------------------------------------------------------------------
    # Drag & drop fantasma (tasto destro)
    # ------------------------------------------------------------------
    def _drag_start(self, event):
        if self.grid is None: return
        self._drag_active = True
        # posizione di partenza
        cell = self._cell_from_xy(event.x, event.y)
        if cell:
            r, c = cell
            self._drag_ghost_pos = (c, r)
        self._drag_offset = (event.x, event.y)

    def _drag_motion(self, event):
        if not self._drag_active or self.grid is None: return
        cell = self._cell_from_xy(event.x, event.y)
        if cell:
            r, c = cell
            if self._drag_ghost_pos != (c, r):
                self._drag_ghost_pos = (c, r)
                self._full_redraw()

    def _drag_end(self, event):
        if not self._drag_active: return
        self._drag_active = False
        cell = self._cell_from_xy(event.x, event.y)
        if cell:
            r, c = cell
            self._drag_ghost_pos = (c, r)
        self._full_redraw()

    # ------------------------------------------------------------------
    # Key / click input
    # ------------------------------------------------------------------
    def _bind_keys(self):
        self.root.bind("<Left>",  lambda e: self._move(0,-1))
        self.root.bind("<Right>", lambda e: self._move(0, 1))
        self.root.bind("<Up>",    lambda e: self._move(-1,0))
        self.root.bind("<Down>",  lambda e: self._move(1, 0))
        self.root.bind("<space>", lambda e: self._end_turn())
        self.root.bind("r",       lambda e: self._dialog_new_game())
        self.root.bind("R",       lambda e: self._dialog_new_game())

    def _on_click(self, event):
        if self.grid is None or self.game_over: return
        cell = self._cell_from_xy(event.x, event.y)
        if cell:
            row, col = cell
            self._take_turn(row, col)

    def _move(self, dr, dc):
        if self.grid is None or self.game_over: return
        p = self._cur_player()
        if p is None: return
        nr, nc = p["row"]+dr, p["col"]+dc
        if 0<=nr<ROWS and 0<=nc<COLS:
            self._take_turn(nr, nc)

    def _end_turn(self):
        if self.grid is None or self.game_over: return
        p = self._cur_player()
        if p is None or not p["placed"]: return
        self.end_turn_flag = True
        self._take_turn(p["row"], p["col"])

    def _toggle_voice(self):
        self.voice = "nat" if self.voice=="sayit" else "sayit"
        self.snd.voice = self.voice
        self._btn_voice.config(text=f"♪  Voice: {self.voice}")

    # ------------------------------------------------------------------
    # Game logic
    # ------------------------------------------------------------------
    def _cur_player(self):
        p = self.players[self.cur_p]
        return p if (p and p["alive"]) else None

    def _in_own_base(self, p):
        return p["row"]==p["base_r"] and p["col"]==p["base_c"]

    def _take_turn(self, row, col):
        p = self._cur_player()
        if p is None: return
        if not p["placed"]:
            if row==self.tr and col==self.tc:
                self._cap_var.set("That's the treasure room!"); return
            for j in range(self.num_players):
                other = self.players[j]
                if other and j!=self.cur_p and other["placed"]:
                    if other["base_r"]==row and other["base_c"]==col:
                        self._cap_var.set("That room is taken!"); return
            p["base_r"]=row; p["base_c"]=col
            p["row"]=row;    p["col"]=col
            p["placed"]=True
            self.grid[row][col].seen = True
            self._reveal_adjacent(row, col)
            self.snd.push("tik")
            self._update_panel(); self._full_redraw()
            if self.num_players==2:
                other = self.players[1-self.cur_p]
                if other and not other["placed"]:
                    self.cur_p = 1-self.cur_p
                    self._cap_var.set(f"Player {self.cur_p+1}: click your Secret Room")
                    self._update_panel()
            return

        dr = row-p["row"]; dc = col-p["col"]
        if self.end_turn_flag:
            self.end_turn_flag = False
            self._cap_var.set(CAPTIONS["endturn"])
            self._do_dragon_turn(p)
            if not self.game_over:
                p["used_steps"] = 0
                self._next_player()
            self._update_panel(); self._full_redraw()
            return

        if abs(dr)+abs(dc) != 1:
            self.snd.push("no"); return

        d = None
        if   dr==-1: d="n"
        elif dr== 1: d="s"
        elif dc==-1: d="w"
        elif dc== 1: d="e"

        cell = self.grid[p["row"]][p["col"]]

        if not cell.passable(d):
            if cell.door_closed[d]:
                self._mark_wall(p["row"], p["col"], d, is_door=True)
                self._flash_wall(p["row"], p["col"], d)
                self.snd.push("hitawall")
                p["used_steps"] = p["max_steps"]
            else:
                self._mark_wall(p["row"], p["col"], d, is_door=False)
                self._flash_wall(p["row"], p["col"], d)
                self.snd.push("hitawall")
                p["used_steps"] = p["max_steps"]
            self._update_panel(); self._full_redraw()
            self._do_dragon_turn(p)
            if not self.game_over:
                p["used_steps"] = 0; self._next_player()
            self._update_panel(); self._full_redraw()
            return

        p["row"] = row; p["col"] = col
        p["used_steps"] += 1
        self.grid[row][col].seen = True
        self._reveal_adjacent(row, col)
        self.snd.push("tik")

        if (not self.dragon_awake and
                manhattan(p["row"],p["col"],self.tr,self.tc)<=DRAGON_WAKE_DIST):
            self.dr = self.tr; self.dc = self.tc
            self.dragon_awake = True
            self.snd.push("ghostawakes")

        if (self.dragon_awake and
                p["row"]==self.dr and p["col"]==self.dc and
                not self._in_own_base(p)):
            self._dragon_attacks(p)
            self._update_panel(); self._full_redraw()
            if self.game_over: return
            self._do_dragon_turn(p)
            if not self.game_over:
                p["used_steps"] = 0; self._next_player()
            self._update_panel(); self._full_redraw()
            return

        if p["row"]==self.tr and p["col"]==self.tc and not p["carrying"]:
            p["carrying"]   = True
            p["max_steps"]  = 4
            p["used_steps"] = p["max_steps"]
            self.snd.push("foundtreasure")

        if p["carrying"] and self._in_own_base(p):
            self._win(); return

        if p["used_steps"] >= p["max_steps"]:
            self._do_dragon_turn(p)
            if not self.game_over:
                p["used_steps"] = 0; self._next_player()

        self._update_panel(); self._full_redraw()

    def _do_dragon_turn(self, p):
        """Il fantasma insegue l'eroe con il tesoro, o il più vicino."""
        if not self.dragon_awake or self.game_over: return

        # Determina target
        carrier = next((pl for pl in self.players if pl and pl.get("carrying")), None)
        if carrier:
            tr, tc = carrier["row"], carrier["col"]
        else:
            # Più vicino al fantasma
            active = [pl for pl in self.players if pl and pl.get("alive") and pl.get("placed")]
            if not active:
                return
            active.sort(key=lambda pl: manhattan(self.dr, self.dc, pl["row"], pl["col"]))
            tr, tc = active[0]["row"], active[0]["col"]

        if self.dr==tr and self.dc==tc:
            if p["row"]==self.dr and p["col"]==self.dc and not self._in_own_base(p):
                self._dragon_attacks(p)
            return

        new_r = self.dr + (1 if self.dr<tr else (-1 if self.dr>tr else 0))
        new_c = self.dc + (1 if self.dc<tc else (-1 if self.dc>tc else 0))
        self.dr = max(0, min(ROWS-1, new_r))
        self.dc = max(0, min(COLS-1, new_c))
        self.snd.push("ghostmoves")

        if (self.dr==p["row"] and self.dc==p["col"] and not self._in_own_base(p)):
            self._dragon_attacks(p)

    def _dragon_attacks(self, p):
        self.dr = p["row"]
        self.dc = p["col"]
        self.dragon_exact = True
        self.snd.push("ghostattacks")
        self.root.after(600, lambda: self._apply_attack(p))

    def _apply_attack(self, p):
        if self.game_over: return

        carrying_at_attack = p["carrying"]

        p["carrying"]   = False
        p["max_steps"]  = STEPS_BY_LIVES.get(max(0, p["lives"]-1), 0)
        if carrying_at_attack:
            p["lives"]  = 0
            p["alive"]  = False
        else:
            p["lives"] -= 1
            p["used_steps"] = 0
            p["row"] = p["base_r"]
            p["col"] = p["base_c"]

        if p["lives"] <= 0 or not p["alive"]:
            p["alive"] = False
            self.snd.push("gameover")
            alive = [i for i in range(self.num_players)
                     if self.players[i] and self.players[i]["alive"]]
            if not alive or self.num_players==1:
                self.game_over  = True
                self.reveal_all = True
                self._update_panel(); self._full_redraw()
                self._end_overlay(won=False); return
            else:
                self.winner    = alive[0]
                self.game_over = True
                self.reveal_all= True
                self._update_panel(); self._full_redraw()
                self._end_overlay(won=True); return

        self._update_panel(); self._full_redraw()

    def _win(self):
        self.winner     = self.cur_p
        self.game_over  = True
        self.reveal_all = True
        self.snd.push("youwin")
        self._update_panel(); self._full_redraw()
        self._end_overlay(won=True)

    def _reveal_adjacent(self, r, c):
        self.grid[r][c].seen = True
        for d,(dr,dc) in DELTA.items():
            nr,nc = r+dr, c+dc
            if 0<=nr<ROWS and 0<=nc<COLS and not self.grid[r][c].walls[d]:
                self.grid[nr][nc].seen = True

    def _mark_wall(self, r, c, d, *, is_door=False):
        self.grid[r][c].wall_shown[d] = True
        self.grid[r][c].seen          = True
        nr,nc = r+DELTA[d][0], c+DELTA[d][1]
        if 0<=nr<ROWS and 0<=nc<COLS:
            self.grid[nr][nc].wall_shown[OPP[d]] = True

    def _next_player(self):
        if self.num_players == 1: return
        for _ in range(self.num_players):
            self.cur_p = (self.cur_p+1) % self.num_players
            p = self.players[self.cur_p]
            if p and p["alive"]: break


def main():
    root = tk.Tk()
    root.geometry(f"{WIN_W}x{WIN_H}+80+60")
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()

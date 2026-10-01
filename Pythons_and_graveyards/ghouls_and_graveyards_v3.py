import os, math, random, threading
import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageTk

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
SOUND_DIR = os.path.join(BASE_DIR, "data", "sounds")
IMG_DIR   = os.path.join(BASE_DIR, "data", "shapes")

ROWS, COLS   = 8, 8
GAP          = 10   
TILE         = 50  
CELL         = TILE + GAP 
WALL_T       = GAP
PAD          = 36   
TITLE_H      = 60  
BOARD_W      = PAD*2 + COLS*CELL - GAP
BOARD_H      = TITLE_H + PAD*2 + ROWS*CELL - GAP
PANEL_W      = 300
WIN_W        = BOARD_W + PANEL_W + 20
WIN_H        = BOARD_H + 20

MAP_BG       = "#2a2a2e"  

MAX_WALLS        = 50
EXTRA_PASSAGES   = 12
MIN_BASE_DIST    = 4
MIN_TREAS_DIST   = 4
DRAGON_WAKE_DIST = 3
STEPS_BY_LIVES   = {3: 8, 2: 6, 1: 4, 0: 0}
PHANTOM_DOORS    = 4
DOOR_INTERVAL_MS = 7000

DELTA = {"n": (-1,0), "s": (1,0), "e": (0,1), "w": (0,-1)}
OPP   = {"n":"s", "s":"n", "e":"w", "w":"e"}
DIRS  = list(DELTA.keys())

C = dict(
    bg           = "#160c08",
    map_bg       = MAP_BG,
    wall_col     = "#fe6429",
    door_col     = "#c87820",
    treasure_col = "#ffd700",
    ghost_col    = "#ccccff",
    base_p1      = "#00aa00",
    base_p2      = "#2266dd",
    panel_bg     = "#100c08",
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


def _build_audio_backend():
    try:
        import miniaudio
        # Use a single stop flag + device reference so we can interrupt playback
        _state = {"stop": False, "thread": None}

        def play(path):
            if not os.path.exists(path): return
            # Signal any ongoing playback to stop
            _state["stop"] = True
            def _t():
                import time
                _state["stop"] = False
                try:
                    stream = miniaudio.stream_file(path)
                    with miniaudio.PlaybackDevice() as dev:
                        dev.start(stream)
                        while dev.callback_generator is not None:
                            if _state["stop"]:
                                break
                            time.sleep(0.02)
                except Exception:
                    pass
            t = threading.Thread(target=_t, daemon=True)
            _state["thread"] = t
            t.start()

        def busy():
            t = _state.get("thread")
            return (t is not None and t.is_alive() and not _state["stop"])

        return play, busy
    except Exception:
        return lambda p: None, lambda: False

_audio_play, _audio_busy = _build_audio_backend()

class SoundQueue:
    """Instant sound: plays immediately, interrupts previous sound."""
    def __init__(self, root, voice="sayit"):
        self.root = root; self.voice = voice
        self.on_caption = lambda s: None

    def push(self, key):
        cap = CAPTIONS.get(key, "")
        if cap: self.on_caption(cap)
        idx = 0 if self.voice == "sayit" else 1
        files = SND_FILES.get(key, [])
        if files:
            fname = files[idx] if idx < len(files) else files[0]
            _audio_play(os.path.join(SOUND_DIR, fname))

    def clear(self): _audio_play.__func__ if hasattr(_audio_play,"__func__") else None
    def busy(self): return _audio_busy()


class SpriteCache:
    def __init__(self):
        self._raw   = {}
        self._cache = {}

    def _load(self, num):
        if num not in self._raw:
            path = os.path.join(IMG_DIR, f"{num}.png")
            self._raw[num] = Image.open(path).convert("RGBA") if os.path.exists(path) else None
        return self._raw[num]

    def _fit(self, img, max_w, max_h):
        iw, ih = img.size
        scale = min(max_w / iw, max_h / ih)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        return img.resize((nw, nh), Image.LANCZOS)

    def get_fit(self, num, max_w, max_h):
        img = self._load(num)
        if img is None: return None
        iw, ih = img.size
        scale = min(max_w / iw, max_h / ih)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        key = (num, nw, nh)
        if key not in self._cache:
            self._cache[key] = ImageTk.PhotoImage(img.resize((nw, nh), Image.LANCZOS))
        return self._cache[key]

    def get_stretch(self, num, w, h):
        img = self._load(num)
        if img is None: return None
        key = (num, w, h, "stretch")
        if key not in self._cache:
            self._cache[key] = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))
        return self._cache[key]

    def get_fit_rot90(self, num, max_w, max_h):
        """Load image rotated 90°, then fit within max_w×max_h preserving A/R."""
        img = self._load(num)
        if img is None: return None
        img_rot = img.rotate(90, expand=True)
        iw, ih = img_rot.size
        scale = min(max_w / iw, max_h / ih)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        key = (num, nw, nh, "rot90")
        if key not in self._cache:
            self._cache[key] = ImageTk.PhotoImage(img_rot.resize((nw, nh), Image.LANCZOS))
        return self._cache[key]

    def get_stretch_rot90(self, num, w, h):
        """Load image rotated 90° then stretched to exact w×h."""
        img = self._load(num)
        if img is None: return None
        img_rot = img.rotate(90, expand=True)
        key = (num, w, h, "stretch_rot90")
        if key not in self._cache:
            self._cache[key] = ImageTk.PhotoImage(img_rot.resize((w, h), Image.LANCZOS))
        return self._cache[key]

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


class Cell:
    __slots__ = ("row","col","walls","wall_shown","seen","is_door","door_closed")
    def __init__(self, r, c):
        self.row, self.col = r, c
        self.walls       = {d: True  for d in DIRS}
        self.wall_shown  = {d: False for d in DIRS}
        self.seen        = False
        self.is_door     = {d: False for d in DIRS}
        self.door_closed = {d: False for d in DIRS}

    def passable(self, d): return not self.walls[d] and not self.door_closed[d]
    def open_count(self):  return sum(1 for d in DIRS if not self.walls[d])

def _carve(grid, r, c, d):
    grid[r][c].walls[d] = False
    nr,nc = r+DELTA[d][0], c+DELTA[d][1]
    grid[nr][nc].walls[OPP[d]] = False

def generate_maze(tr, tc):
    grid = [[Cell(r,c) for c in range(COLS)] for r in range(ROWS)]
    sr,sc = random.randrange(ROWS), random.randrange(COLS)
    grid[sr][sc].seen = True
    frontier = [(sr,sc)]
    while frontier:
        i = random.randrange(len(frontier)); r,c = frontier[i]
        nbrs = [(d,r+DELTA[d][0],c+DELTA[d][1]) for d in DIRS
                if 0<=r+DELTA[d][0]<ROWS and 0<=c+DELTA[d][1]<COLS
                and not grid[r+DELTA[d][0]][c+DELTA[d][1]].seen]
        if not nbrs: frontier.pop(i); continue
        d,nr,nc = random.choice(nbrs)
        _carve(grid,r,c,d); grid[nr][nc].seen=True; frontier.append((nr,nc))

    def count_walls():
        return sum(1 for r in range(ROWS) for c in range(COLS) for d in ["s","e"]
                   if 0<=r+DELTA[d][0]<ROWS and 0<=c+DELTA[d][1]<COLS and grid[r][c].walls[d])

    added,attempts = 0,0
    while added<EXTRA_PASSAGES and count_walls()>MAX_WALLS and attempts<2000:
        attempts+=1; r,c=random.randrange(ROWS),random.randrange(COLS)
        d=random.choice(DIRS); nr,nc=r+DELTA[d][0],c+DELTA[d][1]
        if 0<=nr<ROWS and 0<=nc<COLS and grid[r][c].walls[d]:
            _carve(grid,r,c,d); added+=1

    while grid[tr][tc].open_count()<2:
        cands=[d for d in DIRS if 0<=tr+DELTA[d][0]<ROWS and 0<=tc+DELTA[d][1]<COLS and grid[tr][tc].walls[d]]
        if not cands: break
        _carve(grid,tr,tc,random.choice(cands))

    for row in grid:
        for cell in row: cell.seen=False
    return grid

def manhattan(r1,c1,r2,c2): return abs(r1-r2)+abs(c1-c2)



class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Ghouls & Graveyards")
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, False)
        self._fonts()
        self.num_players = 1; self.difficulty = 1; self.voice = "sayit"
        self.grid = None; self.players = [None,None]; self.cur_p = 0
        self.dr = self.dc = -1
        self.dragon_awake = False; self.dragon_exact = False
        self.tr = self.tc = -1
        self.game_over = False; self.winner = None
        self.reveal_all = False; self.doors = []
        self._door_job = None; self.end_turn_flag = False
        self._ghost_panel_pos = None 
        self._ghost_panel_cell = None 
        self._drag_active = False
        self._drag_pending = False
        self._drag_source = "panel"
        self._drag_ox = self._drag_oy = 0
        self._drag_base_preview = None
        self._drag_base_cell = None
        self._img_refs = []
        self._panel_img_refs = []
        self._build_ui()
        self.snd = SoundQueue(root, self.voice)
        self.snd.on_caption = lambda t: self._cap_var.set(t)

        self._show_title()
        self._bind_keys()

    def _fonts(self):
        self.F = {}
        serif = "Palatino Linotype"
        mono  = "Courier New"
        for name,fam,sz,wt,sl in [
            ("brand",  serif,  15, "bold",   False),
            ("h2",     serif,  11, "bold",   False),
            ("h3",     serif,  10, "bold",   False),
            ("body",   serif,  10, "normal", False),
            ("italic", serif,  10, "normal", True),
            ("small",  serif,   9, "normal", False),
            ("caption",serif,  10, "normal", False),
            ("mono",   mono,   10, "bold",   False),
            ("tiny",   serif,   8, "normal", False),
            ("btn",    serif,  10, "bold",   False),
        ]:
            slant = "italic" if sl else "roman"
            self.F[name] = tkfont.Font(family=fam, size=sz, weight=wt, slant=slant)

    def _build_ui(self):
        outer = tk.Frame(self.root, bg=C["bg"])
        outer.pack(padx=6, pady=6)

        self.cv = tk.Canvas(outer, width=BOARD_W, height=BOARD_H,
            bg=MAP_BG, highlightthickness=2, highlightbackground=C["panel_border"])
        self.cv.pack(side="left")
        self.cv.bind("<ButtonPress-1>",   self._map_ghost_press)
        self.cv.bind("<B1-Motion>",       self._map_ghost_motion)
        self.cv.bind("<ButtonRelease-1>", self._map_click_or_release)

        # pannello destra
        self.panel = tk.Frame(outer, bg=C["panel_bg"], width=PANEL_W)
        self.panel.pack(side="right", fill="y", padx=(10,0))
        self.panel.pack_propagate(False)
        self._build_panel(self.panel)

    def _build_panel(self, p):
        self._hsep(p, color=C["panel_border"], thick=2)
        self._pui = []
        for i in range(2):
            pc = C["base_p1"] if i==0 else C["base_p2"]
            outer_fr = tk.Frame(p, bg=C["panel_sep"], bd=0)
            outer_fr.pack(fill="x", padx=6, pady=(4,2))
            fr = tk.Frame(outer_fr, bg=C["panel_bg"], padx=6, pady=4)
            fr.pack(fill="x", padx=1, pady=1)
            hdr = tk.Frame(fr, bg=C["panel_bg"])
            hdr.pack(fill="x")
            name_lbl = tk.Label(hdr, text=f"PLAYER  {i+1}",font=self.F["h2"], bg=C["panel_bg"], fg=pc)
            name_lbl.pack(side="left")
            # Hearts right next to player name
            lives_cv = tk.Canvas(hdr, width=72, height=20, bg=C["panel_bg"], highlightthickness=0)
            lives_cv.pack(side="left", padx=(4,0))
            treas_cv = tk.Canvas(hdr, width=22, height=22,bg=C["panel_bg"], highlightthickness=0)
            treas_cv.pack(side="right", padx=(0,2))
            # Steps (footprints) on own row, larger
            steps_cv = tk.Canvas(fr, width=230, height=22,bg=C["panel_bg"], highlightthickness=0)
            steps_cv.pack(anchor="w", pady=(2,0))
            sv = tk.StringVar(value="")
            st_lbl = tk.Label(fr, textvariable=sv, font=self.F["small"],bg=C["panel_bg"], fg=C["label_col"], wraplength=220, justify="left")
            st_lbl.pack(anchor="w")
            self._pui.append((outer_fr, fr, lives_cv, steps_cv, treas_cv, sv))
        self._hsep(p)
        self._turn_var = tk.StringVar(value="")
        tk.Label(p, textvariable=self._turn_var,font=self.F["mono"], bg=C["panel_bg"], fg=C["highlight"]).pack(pady=(2,0))
        self._cap_var = tk.StringVar(value="")
        tk.Label(p, textvariable=self._cap_var,font=self.F["caption"], bg=C["panel_bg"], fg=C["text_col"],wraplength=240, justify="center", height=2).pack(fill="x", padx=6)
        self._hsep(p)
        self._ghost_frame = tk.Frame(p, bg=C["panel_bg"])
        self._ghost_frame.pack(fill="x", padx=6, pady=2)
        self.ghost_cv = tk.Canvas(self._ghost_frame, width=PANEL_W-20, height=52,
            bg=C["panel_bg"], highlightthickness=0)
        self.ghost_cv.pack(pady=(2,4))
        self._draw_panel_ghost_idle()
        self.ghost_cv.bind("<ButtonPress-1>",   self._panel_ghost_press)
        self.ghost_cv.bind("<B1-Motion>",       self._panel_ghost_motion)
        self.ghost_cv.bind("<ButtonRelease-1>", self._panel_ghost_release)
        self._hsep(p)
        bkw = dict(font=self.F["btn"], bg=C["btn_bg"], fg=C["btn_fg"],
                   activebackground=C["btn_hover"], activeforeground=C["highlight"],
                   relief="groove", bd=2, padx=4, pady=4,
                   anchor="w", cursor="hand2")
        self._btn_end = tk.Button(p, text="▷  End Turn   [Space / RClick]",command=self._end_turn, **bkw)
        self._btn_end.pack(fill="x", padx=8, pady=2)
        tk.Button(p, text="⟳  New Game   [R]",command=self._dialog_new_game, **bkw).pack(fill="x", padx=8, pady=2)
        self._btn_voice = tk.Button(p, text="♪  Voice: sayit",command=self._toggle_voice, **bkw)
        self._btn_voice.pack(fill="x", padx=8, pady=2)
        self._hsep(p)
        self._diff_var = tk.StringVar(value="")
        tk.Label(p, textvariable=self._diff_var, font=self.F["tiny"],bg=C["panel_bg"], fg=C["label_col"], justify="center").pack(pady=(2,0))
        tk.Label(p, text="Arrow keys / click to move",font=self.F["tiny"], bg=C["panel_bg"], fg=C["dim_col"],justify="center").pack(pady=(0,6))

    def _draw_panel_ghost_idle(self):
        self.ghost_cv.delete("all")
        # Hide panel ghost when it's placed on the map
        if self._ghost_panel_cell is not None:
            self.ghost_cv.config(height=1)
            return
        self.ghost_cv.config(height=52)
        cw = PANEL_W - 20; ch = 52
        # Ghost image on left, drag text on right
        ph = SPRITES.get_fit(SP_GHOST, 40, 40)
        if ph:
            self._panel_img_refs.append(ph)
            self.ghost_cv.create_image(28, ch//2, anchor="center", image=ph, tags="idle_ghost")
        else:
            self.ghost_cv.create_oval(8, ch//2-16, 44, ch//2+16, fill="#8888cc", outline="")
        self.ghost_cv.create_text(56, ch//2, text="drag to map →",
            font=self.F["small"], fill=C["label_col"], anchor="w")

    def _hsep(self, parent, color=None, thick=1):
        col = color or C["panel_sep"]
        tk.Frame(parent, bg=col, height=thick).pack(fill="x", padx=6, pady=3)

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

    # ── Panel ghost drag ─────────────────────────────────────────────
    def _panel_ghost_press(self, event):
        if self.grid is None: return
        self._drag_pending = True
        self._drag_source = "panel"
        self._drag_active = False

    def _panel_ghost_motion(self, event):
        if not self._drag_pending or self.grid is None: return
        self._drag_active = True
        gx = self.ghost_cv.winfo_rootx() + event.x
        gy = self.ghost_cv.winfo_rooty() + event.y
        cx_abs = gx - self.cv.winfo_rootx()
        cy_abs = gy - self.cv.winfo_rooty()
        cell = self._cell_from_canvas(cx_abs, cy_abs)
        if cell != self._ghost_panel_cell:
            self._ghost_panel_cell = cell
            self._draw_panel_ghost_idle()
            self._full_redraw()
        self.ghost_cv.delete("all")
        self.ghost_cv.create_text((PANEL_W-20)//2, 26,
            text="dragging…", font=self.F["tiny"], fill=C["highlight"])

    def _panel_ghost_release(self, event):
        self._drag_pending = False
        was_dragging = self._drag_active
        self._drag_active = False
        if not was_dragging: return
        gx = self.ghost_cv.winfo_rootx() + event.x
        gy = self.ghost_cv.winfo_rooty() + event.y
        cx_abs = gx - self.cv.winfo_rootx()
        cy_abs = gy - self.cv.winfo_rooty()
        cell = self._cell_from_canvas(cx_abs, cy_abs)
        if cell is not None:
            self._ghost_panel_cell = cell
        self._draw_panel_ghost_idle()
        self._full_redraw()

    # ── Map ghost drag (drag ghost token from the map itself) ─────────
    def _map_ghost_press(self, event):
        if self.grid is None: return
        cell = self._cell_from_canvas(event.x, event.y)
        # Check if pressing on ghost marker
        if self._ghost_panel_cell is not None and cell == self._ghost_panel_cell:
            self._drag_pending = True
            self._drag_source = "map"
            self._drag_active = False
            return
        # Check if pressing on player base during placement phase
        p = self._cur_player()
        if p is not None and not p["placed"] and cell is not None:
            self._drag_pending = True
            self._drag_source = "base"
            self._drag_active = False
            self._drag_base_cell = cell
            return
        # Also allow dragging an already-placed base (reposition before first move)
        if p is not None and p["placed"] and p["used_steps"] == 0 and cell is not None:
            if cell == (p["base_r"], p["base_c"]):
                self._drag_pending = True
                self._drag_source = "base_reposition"
                self._drag_active = False
                return

    def _map_ghost_motion(self, event):
        if not self._drag_pending: return
        self._drag_active = True
        cell = self._cell_from_canvas(event.x, event.y)
        if self._drag_source == "map":
            if cell != self._ghost_panel_cell:
                self._ghost_panel_cell = cell
                self._draw_panel_ghost_idle()
                self._full_redraw()
            self.cv.config(cursor="fleur")
        elif self._drag_source in ("base", "base_reposition"):
            self.cv.config(cursor="fleur")
            if cell is not None:
                self._drag_base_preview = cell
                self._full_redraw()

    def _map_ghost_release(self, event):
        if not self._drag_pending: return
        self._drag_pending = False
        was_dragging = self._drag_active
        self._drag_active = False
        self.cv.config(cursor="")
        cell = self._cell_from_canvas(event.x, event.y)

        if self._drag_source == "map":
            if was_dragging:
                if cell is not None:
                    self._ghost_panel_cell = cell
                elif event.x < 0 or event.x > BOARD_W or event.y < 0 or event.y > BOARD_H:
                    self._ghost_panel_cell = None
                self._draw_panel_ghost_idle()
                self._full_redraw()
            # If not dragging (just a click on the ghost), do nothing special

        elif self._drag_source == "base" and was_dragging and cell is not None:
            self._drag_base_preview = None
            self._take_turn(*cell)

        elif self._drag_source == "base_reposition" and was_dragging and cell is not None:
            # Allow repositioning base before first move
            p = self._cur_player()
            if p and p["placed"] and p["used_steps"] == 0:
                self._drag_base_preview = None
                self._take_turn_reposition(p, cell)

        self._drag_base_preview = None

    def _map_click_or_release(self, event):
        """Single ButtonRelease-1 handler: runs drag logic, then click if no drag occurred."""
        was_drag = self._drag_pending and self._drag_active
        self._map_ghost_release(event)
        # Plain click (no motion occurred during press→release)
        if not was_drag and self.grid is not None and not self.game_over:
            cell = self._cell_from_canvas(event.x, event.y)
            if cell:
                self._take_turn(*cell)

    def _show_title(self):
        self._img_refs.clear()
        self.cv.delete("all")
        self.cv.create_rectangle(0,0,BOARD_W,BOARD_H, fill="#1a0a06")
        ph = SPRITES.get_stretch(SP_TITLE, BOARD_W, TITLE_H)
        if ph:
            self._img_refs.append(ph)
            self.cv.create_image(0, 0, anchor="nw", image=ph)
        else:
            self.cv.create_rectangle(0,0,BOARD_W,TITLE_H,fill="#0a0a0a",outline=C["panel_border"],width=2)
            self.cv.create_text(BOARD_W//2,TITLE_H//2,text="GHOULS & GRAVEYARDS",
                font=("Georgia",14,"bold"),fill="#ff0000")
        cx = BOARD_W//2; cy = TITLE_H + (BOARD_H-TITLE_H)//2
        ph2 = SPRITES.get_fit(SP_GHOST, 90, 90)
        if ph2:
            self._img_refs.append(ph2)
            self.cv.create_image(cx, cy-20, anchor="center", image=ph2)
        self.cv.create_text(cx,cy+60,text="Python/Tkinter  ·  based on Mattel Electronics 1980",
            font=self.F["small"],fill=C["label_col"])
        self.cv.create_text(cx,cy+100,text="Press  New Game [R]  to begin",
            font=self.F["italic"],fill=C["highlight"])
        self._cap_var.set(""); self._turn_var.set("")
        self._btn_end.config(state="disabled")
        for _,_,lc,sc,tc,sv in self._pui:
            self._draw_lives(lc,0,3); self._draw_steps(sc,0,8)
            tc.delete("all"); sv.set("")

    def _dialog_new_game(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("New Game"); dlg.configure(bg=C["bg"])
        dlg.resizable(False,False); dlg.grab_set()
        tk.Label(dlg,text="NEW GAME",font=("Palatino Linotype",16,"bold"),bg=C["bg"],fg=C["treasure_col"]).pack(pady=(16,6))
        tk.Label(dlg,text="Players:",font=self.F["body"],bg=C["bg"],fg=C["text_col"]).pack()
        np_var=tk.IntVar(value=self.num_players)
        f=tk.Frame(dlg,bg=C["bg"]); f.pack()
        for n,lbl in [(1,"1 Player"),(2,"2 Players")]:
            tk.Radiobutton(f,text=lbl,variable=np_var,value=n,bg=C["bg"],
                fg=C["text_col"],selectcolor=C["panel_bg"],font=self.F["body"]).pack(side="left",padx=14)
        tk.Label(dlg,text="Difficulty:",font=self.F["body"],bg=C["bg"],fg=C["text_col"]).pack(pady=(10,0))
        dv=tk.IntVar(value=self.difficulty)
        f2=tk.Frame(dlg,bg=C["bg"]); f2.pack()
        tk.Radiobutton(f2,text="Level 1 — Classic",variable=dv,value=1,bg=C["bg"],fg=C["text_col"],selectcolor=C["panel_bg"],font=self.F["body"]).pack(side="left",padx=14)
        tk.Radiobutton(f2,text="Level 2 — Phantom Doors",variable=dv,value=2,bg=C["bg"],fg=C["text_col"],selectcolor=C["panel_bg"],font=self.F["body"]).pack(side="left",padx=14)
        tk.Label(dlg,text="Voice:",font=self.F["body"],bg=C["bg"],fg=C["text_col"]).pack(pady=(10,0))
        vv=tk.StringVar(value=self.voice)
        f3=tk.Frame(dlg,bg=C["bg"]); f3.pack()
        for v,lbl in [("sayit","TTS (sayit)"),("nat","Natural voice")]:
            tk.Radiobutton(f3,text=lbl,variable=vv,value=v,bg=C["bg"],
                fg=C["text_col"],selectcolor=C["panel_bg"],font=self.F["body"]).pack(side="left",padx=14)
        def start():
            self.num_players=np_var.get(); self.difficulty=dv.get(); self.voice=vv.get()
            dlg.destroy(); self._new_game()
        tk.Button(dlg,text="▷  Start Game",command=start,
            font=("Palatino Linotype",11,"bold"),bg=C["btn_bg"],fg=C["btn_fg"],
            activebackground=C["btn_hover"],relief="raised",bd=2,padx=10,pady=8,cursor="hand2").pack(pady=(4,18))
        dlg.update_idletasks()
        x=self.root.winfo_x()+(self.root.winfo_width()-dlg.winfo_width())//2
        y=self.root.winfo_y()+(self.root.winfo_height()-dlg.winfo_height())//2
        dlg.geometry(f"+{x}+{y}")

    def _new_game(self):
        self.snd.clear(); self.snd.voice=self.voice
        if self._door_job: self.root.after_cancel(self._door_job); self._door_job=None
        self.game_over=False; self.winner=None; self.reveal_all=False
        self.end_turn_flag=False; self.doors=[]
        self.dragon_awake=False; self.dragon_exact=False; self.dr=self.dc=-1
        self._ghost_panel_cell=None
        self._img_refs.clear(); self._panel_img_refs=[]

        base_pos=[]
        for i in range(self.num_players):
            for _ in range(5000):
                br=random.randrange(ROWS); bc=random.randrange(COLS)
                if all(manhattan(br,bc,pr,pc)>=MIN_BASE_DIST for pr,pc in base_pos):
                    base_pos.append((br,bc)); break
            else:
                base_pos.append((random.randrange(ROWS),random.randrange(COLS)))

        for _ in range(5000):
            tr=random.randrange(ROWS); tc=random.randrange(COLS)
            if all(manhattan(tr,tc,br,bc)>=MIN_TREAS_DIST for br,bc in base_pos): break
        self.tr,self.tc=tr,tc
        self.grid=generate_maze(tr,tc)

        self.players=[None,None]
        for i in range(self.num_players):
            br,bc=base_pos[i]
            self.players[i]=dict(base_r=br,base_c=bc,row=br,col=bc,
                lives=3,used_steps=0,max_steps=8,carrying=False,placed=False,alive=True)

        self.cur_p=0
        self._diff_var.set(f"{'1' if self.num_players==1 else '2'}-player  ·  "
            f"{'Level 1' if self.difficulty==1 else 'Level 2 — Phantom Doors'}")
        self._btn_end.config(state="normal")
        self.snd.on_caption=lambda t: self._cap_var.set(t)
        self._update_panel(); self._full_redraw()
        self._draw_panel_ghost_idle()
        if self.difficulty==2:
            self._door_job=self.root.after(DOOR_INTERVAL_MS,self._toggle_doors)

    def _toggle_doors(self):
        if self.game_over: return
        had=bool(self.doors)
        for r,c,d in self.doors:
            self.grid[r][c].door_closed[d]=False; self.grid[r][c].is_door[d]=False
            nr,nc=r+DELTA[d][0],c+DELTA[d][1]
            self.grid[nr][nc].door_closed[OPP[d]]=False; self.grid[nr][nc].is_door[OPP[d]]=False
        self.doors.clear()
        cands=[]
        for r in range(ROWS):
            for c in range(COLS):
                for d in ["n","e"]:
                    nr,nc=r+DELTA[d][0],c+DELTA[d][1]
                    if not(0<=nr<ROWS and 0<=nc<COLS): continue
                    if self.grid[r][c].walls[d]: continue
                    if r==self.tr and c==self.tc and self.grid[r][c].open_count()<=2: continue
                    if nr==self.tr and nc==self.tc and self.grid[nr][nc].open_count()<=2: continue
                    cands.append((r,c,d))
        random.shuffle(cands); new_doors=cands[:PHANTOM_DOORS]
        for r,c,d in new_doors:
            self.grid[r][c].door_closed[d]=True; self.grid[r][c].is_door[d]=True
            nr,nc=r+DELTA[d][0],c+DELTA[d][1]
            self.grid[nr][nc].door_closed[OPP[d]]=True; self.grid[nr][nc].is_door[OPP[d]]=True
        self.doors=new_doors
        if had and new_doors: self._cap_var.set(CAPTIONS["doorappear"]+"  "+CAPTIONS["doorvanish"])
        elif had: self._cap_var.set(CAPTIONS["doorappear"])
        elif new_doors: self._cap_var.set(CAPTIONS["doorvanish"])
        self._full_redraw()
        self._door_job=self.root.after(DOOR_INTERVAL_MS,self._toggle_doors)

    def _full_redraw(self):
        self._img_refs.clear()
        self.cv.delete("all")
        self.cv.create_rectangle(0,0,BOARD_W,BOARD_H, fill=MAP_BG, outline="")
        ph = SPRITES.get_stretch(SP_TITLE, BOARD_W, TITLE_H)
        if ph:
            self._img_refs.append(ph)
            self.cv.create_image(0,0,anchor="nw",image=ph)
        else:
            self.cv.create_rectangle(0,0,BOARD_W,TITLE_H,fill="#0a0a0a",outline=C["panel_border"],width=2)
            self.cv.create_text(BOARD_W//2,TITLE_H//2,text="GHOULS & GRAVEYARDS",
                font=("Georgia",14,"bold"),fill="#ff0000")
        for r in range(ROWS):
            for c in range(COLS):
                x0,y0=self._xy(r,c)
                ph=SPRITES.get_fit(SP_FLOOR,TILE,TILE)
                if ph:
                    self._img_refs.append(ph)
                    self.cv.create_image(x0,y0,anchor="nw",image=ph)
                else:
                    self.cv.create_rectangle(x0,y0,x0+TILE,y0+TILE,fill="#2b1a10",outline="")
        self._draw_bases()
        self._draw_walls()
        self._draw_doors()
        self._draw_treasure()
        self._draw_warriors()
        self._draw_map_ghost()
        if self.game_over:
            self._redraw_end_overlay()

    def _draw_bases(self):
        base_sz = int(TILE * 0.8)
        for i in range(self.num_players):
            p=self.players[i]
            if p is None: continue
            sp=SP_BASE_P1 if i==0 else SP_BASE_P2
            cx,cy=self._cx_cy(p["base_r"],p["base_c"])
            ph=SPRITES.get_fit(sp,base_sz,base_sz)
            if ph:
                self._img_refs.append(ph)
                self.cv.create_image(cx,cy,anchor="center",image=ph)
            else:
                col=C["base_p1"] if i==0 else C["base_p2"]
                h=base_sz//2
                self.cv.create_rectangle(cx-h,cy-h,cx+h,cy+h,fill=col,outline="")
        # Draw base drag preview (semi-transparent highlight on hovered cell)
        if self._drag_base_preview is not None and self._drag_source in ("base","base_reposition"):
            pr, pc = self._drag_base_preview
            px, py = self._cx_cy(pr, pc)
            half = base_sz//2
            self.cv.create_rectangle(px-half, py-half, px+half, py+half,
                outline=C["highlight"], width=2, dash=(4,3))

    def _draw_walls(self):
        drawn=set()
        for r in range(ROWS):
            for c in range(COLS):
                cell=self.grid[r][c]
                for d in DIRS:
                    if not(cell.wall_shown[d] or self.reveal_all): continue
                    if not cell.walls[d]: continue
                    nr,nc=r+DELTA[d][0],c+DELTA[d][1]
                    key=(min(r,nr),min(c,nc),max(r,nr),max(c,nc),d if d in("n","s") else OPP[d])
                    if key in drawn: continue
                    drawn.add(key)
                    x0,y0=self._xy(r,c); x1,y1=x0+TILE,y0+TILE
                    # Walls span full TILE width, GAP thick
                    if d=="n":
                        self._wall_seg(x0, y0-GAP, x0+TILE, y0, True)
                    elif d=="s":
                        self._wall_seg(x0, y1, x0+TILE, y1+GAP, True)
                    elif d=="w":
                        self._wall_seg(x0-GAP, y0, x0, y0+TILE, False)
                    elif d=="e":
                        self._wall_seg(x1, y0, x1+GAP, y0+TILE, False)

    def _wall_seg(self,x0,y0,x1,y1,horiz):
        w=x1-x0; h=y1-y0
        if w<=0 or h<=0: return
        if horiz:
            # Horizontal wall: keep A/R, fit in TILE×GAP
            ph = SPRITES.get_fit(SP_WALL, w, h)
        else:
            # Vertical wall: rotate 90° to keep A/R, fit in GAP×TILE
            ph = SPRITES.get_fit_rot90(SP_WALL, w, h)
        if ph:
            self._img_refs.append(ph)
            self.cv.create_image(x0,y0,anchor="nw",image=ph)
        else:
            self.cv.create_rectangle(x0,y0,x1,y1,fill=C["wall_col"],outline="")

    def _draw_doors(self):
        for r in range(ROWS):
            for c in range(COLS):
                cell=self.grid[r][c]
                if not(cell.seen or self.reveal_all): continue
                x0,y0=self._xy(r,c); x1,y1=x0+TILE,y0+TILE
                for d in DIRS:
                    if not cell.is_door[d]: continue
                    if d in("n","s"):
                        # Horizontal door: full TILE wide, GAP thick — keep A/R
                        yy=y0 if d=="n" else y1
                        ph=SPRITES.get_fit(SP_DOOR,TILE,GAP)
                        if ph:
                            self._img_refs.append(ph)
                            self.cv.create_image(x0, yy-GAP//2, anchor="nw", image=ph)
                        else:
                            self.cv.create_rectangle(x0,yy-GAP//2,x1,yy+GAP//2,fill=C["door_col"],outline="")
                    else:
                        # Vertical door: GAP wide, full TILE tall — rotate 90°
                        xx=x0 if d=="w" else x1
                        ph=SPRITES.get_fit_rot90(SP_DOOR,GAP,TILE)
                        if ph:
                            self._img_refs.append(ph)
                            self.cv.create_image(xx-GAP//2, y0, anchor="nw", image=ph)
                        else:
                            self.cv.create_rectangle(xx-GAP//2,y0,xx+GAP//2,y1,fill=C["door_col"],outline="")

    def _draw_treasure(self):
        if self.tr<0: return
        # Treasure only shown when a hero steps exactly on it, or reveal_all
        if not self.reveal_all:
            hero_on_treasure = any(
                p and p.get("placed") and p.get("alive") and p["row"]==self.tr and p["col"]==self.tc
                for p in self.players
            )
            if not hero_on_treasure: return
        for p in self.players:
            if p and p["carrying"]: return
        sz=int(TILE*0.8)
        cx,cy=self._cx_cy(self.tr,self.tc)
        ph=SPRITES.get_fit(SP_TREAS,sz,sz)
        if ph:
            self._img_refs.append(ph)
            self.cv.create_image(cx,cy,anchor="center",image=ph)

    def _draw_warriors(self):
        for i in range(self.num_players):
            p=self.players[i]
            if p is None or not p["alive"] or not p["placed"]: continue
            cx,cy=self._cx_cy(p["row"],p["col"])
            sp=SP_P1 if i==0 else SP_P2
            sz=int(TILE*0.85)
            ph=SPRITES.get_fit(sp,sz,sz)
            if ph:
                self._img_refs.append(ph)
                self.cv.create_image(cx,cy,anchor="center",image=ph)
            else:
                col=C["base_p1"] if i==0 else C["base_p2"]
                h=sz//3
                self.cv.create_rectangle(cx-h,cy-h,cx+h,cy+h,fill=col,outline="")

    def _draw_map_ghost(self):
        if self._ghost_panel_cell is None or self.grid is None: return
        r,c=self._ghost_panel_cell
        if not(0<=r<ROWS and 0<=c<COLS): return
        cx,cy=self._cx_cy(r,c)
        sz=int(TILE*0.75)
        ph=SPRITES.get_fit(SP_GHOST,sz,sz)
        if ph:
            self._img_refs.append(ph)
            self.cv.create_image(cx,cy,anchor="center",image=ph,tags="map_ghost")
        half=sz//2
        self.cv.create_oval(cx-half,cy-half,cx+half,cy+half,
            outline=C["highlight"],width=1,dash=(4,3),tags="map_ghost")

    def _draw_lives(self, cv, lives, max_l, dead=False):
        cv.delete("all")
        if dead:
            # Show skull symbol when player is dead
            cv.create_text(4, 10, text="💀", font=("Georgia", 14), fill="#cc3333", anchor="w")
            return
        for i in range(max_l):
            col=C["heart_on"] if i<lives else C["heart_off"]
            cv.create_text(4+i*22, 10, text="♥", font=("Georgia", 14), fill=col, anchor="w")

    def _draw_steps(self, cv, used, max_s):
        cv.delete("all")
        if max_s==0: return
        # Footprints: larger, horizontal layout
        slot_w = min(22, (226-4)//max_s)
        sz = min(16, slot_w-2)  # larger footprint size
        for i in range(max_s):
            cx = 4 + i*slot_w + slot_w//2; cy = 11
            sp = SP_STEP_US if i<used else SP_STEP_AV
            # Horizontal: rotate by swapping w/h (wider than tall)
            ph = SPRITES.get_fit(sp, sz, sz//2+2) if sz>8 else SPRITES.get_fit(sp, sz, sz)
            if ph:
                self._panel_img_refs.append(ph)
                cv.create_image(cx, cy, anchor="center", image=ph)
            else:
                col = "#550000" if i<used else "#ff6644"
                cv.create_rectangle(cx-sz//2, cy-sz//4, cx+sz//2, cy+sz//4, fill=col, outline="")

    def _draw_treas_icon(self, cv, show):
        cv.delete("all")
        if not show: return
        ph=SPRITES.get_fit(SP_TREAS,18,18)
        if ph:
            self._panel_img_refs.append(ph)
            cv.create_image(11,11,anchor="center",image=ph)

    def _update_panel(self):
        pc=[C["base_p1"],C["base_p2"]]
        for i in range(2):
            outer_fr,fr,lc,sc,tc,sv=self._pui[i]
            p=self.players[i]
            if p is None:
                outer_fr.config(bg=C["panel_sep"])
                self._draw_lives(lc,0,3); self._draw_steps(sc,0,8)
                self._draw_treas_icon(tc,False); sv.set("—"); continue
            if not p["alive"]:
                outer_fr.config(bg=C["panel_sep"])
                self._draw_lives(lc,0,3,dead=True); self._draw_steps(sc,0,8)
                self._draw_treas_icon(tc,False); sv.set("Eliminated"); continue
            active=(i==self.cur_p) and not self.game_over
            outer_fr.config(bg=C["active_border"] if active else C["panel_sep"])
            self._draw_lives(lc,p["lives"],3)
            self._draw_steps(sc,p["used_steps"],p["max_steps"])
            self._draw_treas_icon(tc,p["carrying"])
            if not p["placed"]: sv.set("Choose your Secret Room")
            elif p["carrying"]: sv.set("★ Has the treasure!")
            else: sv.set("")

        if self.game_over:
            self._turn_var.set(f"🏆  Player {self.winner+1} wins!" if self.winner is not None else "💀  Game over")
        else:
            self._turn_var.set(f"— Player {self.cur_p+1}'s turn —")

    def _end_overlay(self, *, won):
        self._redraw_end_overlay(won=won)
        self._btn_end.config(state="disabled")

    def _redraw_end_overlay(self, *, won=None):
        if won is None: won=(self.winner is not None)
        cx,cy=BOARD_W//2,BOARD_H//2
        self.cv.create_rectangle(cx-150,cy-65,cx+150,cy+40,
            fill=C["end_box"],outline=C["treasure_col"],width=3,stipple="gray50",tags="end")
        if won and self.winner is not None:
            msg=f"🏆  Player {self.winner+1} Wins!"; col=C["treasure_col"]
        else:
            msg="💀  Game Over"; col="#ff3333"
        self.cv.create_text(cx,cy-20,text=msg,
            font=("Palatino Linotype",22,"bold"),fill=col,tags="end")

    def _flash_wall(self,r,c,d):
        x0,y0=self._xy(r,c); x1,y1=x0+TILE,y0+TILE
        tag=f"wf_{r}_{c}_{d}"
        if d=="n": self._wall_seg(x0,y0-GAP,x1,y0,True)
        elif d=="s": self._wall_seg(x0,y1,x1,y1+GAP,True)
        elif d=="w": self._wall_seg(x0-GAP,y0,x0,y1,False)
        elif d=="e": self._wall_seg(x1,y0,x1+GAP,y1,False)
        self.cv.create_rectangle(x0,y0,x1,y1,fill="#ffffff",outline="",stipple="gray25",tags=tag)
        self.root.after(400,lambda:self.cv.delete(tag))

    def _bind_keys(self):
        self.root.bind("<Left>",  lambda e: self._move(0,-1))
        self.root.bind("<Right>", lambda e: self._move(0, 1))
        self.root.bind("<Up>",    lambda e: self._move(-1,0))
        self.root.bind("<Down>",  lambda e: self._move(1, 0))
        self.root.bind("<space>", lambda e: self._end_turn())
        self.root.bind("r",       lambda e: self._dialog_new_game())
        self.root.bind("R",       lambda e: self._dialog_new_game())
        self.cv.bind("<Button-3>", lambda e: self._end_turn())

    def _on_click(self, event):
        if self.grid is None or self.game_over: return
        # Skip if a drag just completed (drag_active was True during motion)
        if self._drag_active: return
        cell=self._cell_from_canvas(event.x,event.y)
        if cell: self._take_turn(*cell)

    def _move(self,dr,dc):
        if self.grid is None or self.game_over: return
        p=self._cur_player()
        if p is None: return
        nr,nc=p["row"]+dr,p["col"]+dc
        if 0<=nr<ROWS and 0<=nc<COLS: self._take_turn(nr,nc)

    def _end_turn(self):
        if self.grid is None or self.game_over: return
        p=self._cur_player()
        if p is None or not p["placed"]: return
        self.end_turn_flag=True
        self._take_turn(p["row"],p["col"])

    def _toggle_voice(self):
        self.voice="nat" if self.voice=="sayit" else "sayit"
        self.snd.voice=self.voice
        self._btn_voice.config(text=f"♪  Voice: {self.voice}")

    def _cur_player(self):
        p=self.players[self.cur_p]
        return p if(p and p["alive"]) else None

    def _in_own_base(self,p): return p["row"]==p["base_r"] and p["col"]==p["base_c"]

    def _take_turn(self,row,col):
        p=self._cur_player()
        if p is None: return
        if not p["placed"]:
            if row==self.tr and col==self.tc:
                self._cap_var.set("That's the treasure room!"); return
            for j in range(self.num_players):
                other=self.players[j]
                if other and j!=self.cur_p and other["placed"]:
                    if other["base_r"]==row and other["base_c"]==col:
                        self._cap_var.set("That room is taken!"); return
            p["base_r"]=row;p["base_c"]=col;p["row"]=row;p["col"]=col;p["placed"]=True
            self.grid[row][col].seen=True; self._reveal_adjacent(row,col)
            self.snd.push("tik")
            self._update_panel(); self._full_redraw()
            if self.num_players==2:
                other=self.players[1-self.cur_p]
                if other and not other["placed"]:
                    self.cur_p=1-self.cur_p
                    self._cap_var.set(f"Player {self.cur_p+1}: choose your Secret Room")
                    self._update_panel()
            return

        if self.end_turn_flag:
            self.end_turn_flag=False
            self._cap_var.set(CAPTIONS["endturn"])
            self._do_dragon_turn(p)
            if not self.game_over:
                p["used_steps"]=0; self._next_player()
            self._update_panel(); self._full_redraw(); return

        dr=row-p["row"]; dc=col-p["col"]
        if abs(dr)+abs(dc)!=1: self.snd.push("no"); return

        d=("n" if dr==-1 else "s" if dr==1 else "w" if dc==-1 else "e")
        cell=self.grid[p["row"]][p["col"]]

        if not cell.passable(d):
            self._mark_wall(p["row"],p["col"],d,is_door=cell.door_closed[d])
            self._flash_wall(p["row"],p["col"],d)
            self.snd.push("hitawall"); p["used_steps"]=p["max_steps"]
            self._update_panel(); self._full_redraw()
            self._do_dragon_turn(p)
            if not self.game_over: p["used_steps"]=0; self._next_player()
            self._update_panel(); self._full_redraw(); return

        p["row"]=row;p["col"]=col;p["used_steps"]+=1
        self.grid[row][col].seen=True; self._reveal_adjacent(row,col)
        self.snd.push("tik")

        if not self.dragon_awake and manhattan(p["row"],p["col"],self.tr,self.tc)<=DRAGON_WAKE_DIST:
            self.dr=self.tr;self.dc=self.tc;self.dragon_awake=True
            self.snd.push("ghostawakes")

        if (self.dragon_awake and p["row"]==self.dr and p["col"]==self.dc and not self._in_own_base(p)):
            self._dragon_attacks(p)
            self._update_panel();self._full_redraw()
            if self.game_over: return
            self._do_dragon_turn(p)
            if not self.game_over: p["used_steps"]=0;self._next_player()
            self._update_panel();self._full_redraw(); return

        if p["row"]==self.tr and p["col"]==self.tc and not p["carrying"]:
            p["carrying"]=True;p["max_steps"]=4;p["used_steps"]=p["max_steps"]
            self.snd.push("foundtreasure")

        if p["carrying"] and self._in_own_base(p):
            self._win(); return

        if p["used_steps"]>=p["max_steps"]:
            self._do_dragon_turn(p)
            if not self.game_over: p["used_steps"]=0;self._next_player()

        self._update_panel();self._full_redraw()

    def _do_dragon_turn(self,p):
        if not self.dragon_awake or self.game_over: return
        carrier=next((pl for pl in self.players if pl and pl.get("carrying")),None)
        if carrier:
            tr,tc=carrier["row"],carrier["col"]
        else:
            active=[pl for pl in self.players if pl and pl.get("alive") and pl.get("placed")]
            all_home=all(self._in_own_base(pl) for pl in active) if active else True
            if all_home:
                tr,tc=self.tr,self.tc
            else:
                out=[pl for pl in active if not self._in_own_base(pl)]
                if not out: tr,tc=self.tr,self.tc
                else:
                    out.sort(key=lambda pl:manhattan(self.dr,self.dc,pl["row"],pl["col"]))
                    tr,tc=out[0]["row"],out[0]["col"]

        if self.dr==tr and self.dc==tc:
            if p["row"]==self.dr and p["col"]==self.dc and not self._in_own_base(p):
                self._dragon_attacks(p)
            return

        new_r=self.dr+(1 if self.dr<tr else(-1 if self.dr>tr else 0))
        new_c=self.dc+(1 if self.dc<tc else(-1 if self.dc>tc else 0))
        self.dr=max(0,min(ROWS-1,new_r)); self.dc=max(0,min(COLS-1,new_c))
        self.snd.push("ghostmoves")
        if self.dr==p["row"] and self.dc==p["col"] and not self._in_own_base(p):
            self._dragon_attacks(p)

    def _dragon_attacks(self,p):
        self.dr=p["row"]; self.dc=p["col"]; self.dragon_exact=True
        self.snd.push("ghostattacks")
        self.root.after(600,lambda:self._apply_attack(p))

    def _apply_attack(self,p):
        if self.game_over: return
        carrying_at_attack=p["carrying"]
        if carrying_at_attack:
            # Attacked while carrying treasure: instant death
            p["carrying"]=False
            p["lives"]=0; p["alive"]=False
        else:
            # Attacked without treasure: lose a life, reduce max steps, teleport home
            p["lives"]-=1
            # Steps decrease with lives: 3→8, 2→6, 1→4, 0→0
            p["max_steps"]=STEPS_BY_LIVES.get(max(0,p["lives"]),0)
            p["used_steps"]=0
            p["row"]=p["base_r"]; p["col"]=p["base_c"]
        if p["lives"]<=0 or not p["alive"]:
            p["alive"]=False; self.snd.push("gameover")
            alive=[i for i in range(self.num_players) if self.players[i] and self.players[i]["alive"]]
            if not alive or self.num_players==1:
                self.game_over=True;self.reveal_all=True
                self._update_panel();self._full_redraw();self._end_overlay(won=False); return
            else:
                self.winner=alive[0];self.game_over=True;self.reveal_all=True
                self._update_panel();self._full_redraw();self._end_overlay(won=True); return
        self._update_panel();self._full_redraw()

    def _take_turn_reposition(self, p, cell):
        """Allow player to drag their base to a new cell before making any move."""
        row, col = cell
        if row == self.tr and col == self.tc:
            self._cap_var.set("That's the treasure room!"); return
        for j in range(self.num_players):
            other = self.players[j]
            if other and j != self.cur_p and other["placed"]:
                if other["base_r"] == row and other["base_c"] == col:
                    self._cap_var.set("That room is taken!"); return
        # Unmark old base cell visibility
        self.grid[p["base_r"]][p["base_c"]].seen = False
        p["base_r"] = row; p["base_c"] = col; p["row"] = row; p["col"] = col
        self.grid[row][col].seen = True; self._reveal_adjacent(row, col)
        self.snd.push("tik")
        self._update_panel(); self._full_redraw()

    def _win(self):
        self.winner=self.cur_p;self.game_over=True;self.reveal_all=True
        self.snd.push("youwin")
        self._update_panel();self._full_redraw();self._end_overlay(won=True)

    def _reveal_adjacent(self,r,c):
        self.grid[r][c].seen=True
        for d,(dr,dc) in DELTA.items():
            nr,nc=r+dr,c+dc
            if 0<=nr<ROWS and 0<=nc<COLS and not self.grid[r][c].walls[d]:
                self.grid[nr][nc].seen=True

    def _mark_wall(self,r,c,d,*,is_door=False):
        self.grid[r][c].wall_shown[d]=True; self.grid[r][c].seen=True
        nr,nc=r+DELTA[d][0],c+DELTA[d][1]
        if 0<=nr<ROWS and 0<=nc<COLS: self.grid[nr][nc].wall_shown[OPP[d]]=True

    def _next_player(self):
        if self.num_players==1: return
        for _ in range(self.num_players):
            self.cur_p=(self.cur_p+1)%self.num_players
            p=self.players[self.cur_p]
            if p and p["alive"]: break


def main():
    root=tk.Tk()
    root.geometry(f"{WIN_W}x{WIN_H}+80+60")
    App(root)
    root.mainloop()

if __name__=="__main__":
    main()

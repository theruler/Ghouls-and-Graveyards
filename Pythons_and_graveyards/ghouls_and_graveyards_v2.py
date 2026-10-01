import os, math, random, threading
import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageTk

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
SOUND_DIR = os.path.join(BASE_DIR, "data", "sounds")
IMG_DIR   = os.path.join(BASE_DIR, "data", "shapes")

ROWS, COLS   = 8, 8
GAP          = 6   
TILE         = 52  
CELL         = TILE + GAP 
WALL_T       = GAP
PAD          = 36   
TITLE_H      = 52   
BOARD_W      = PAD*2 + COLS*CELL - GAP
BOARD_H      = TITLE_H + PAD*2 + ROWS*CELL - GAP
PANEL_W      = 260
WIN_W        = BOARD_W + PANEL_W + 20
WIN_H        = BOARD_H + 20

MAP_BG       = "#2a2a2e"  

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
                except Exception: pass
                _busy[0] = False
            threading.Thread(target=_t, daemon=True).start()
        return play, lambda: _busy[0]
    except Exception:
        return lambda p: None, lambda: False

_audio_play, _audio_busy = _build_audio_backend()

class SoundQueue:
    def __init__(self, root, voice="sayit"):
        self.root = root; self.voice = voice
        self._q = []; self._active = False
        self.on_caption = lambda s: None

    def push(self, key):
        self._q.append(key)
        if not self._active: self._fire()

    def clear(self): self._q.clear(); self._active = False
    def busy(self): return self._active

    def _fire(self):
        if not self._q: self._active = False; return
        self._active = True
        key = self._q.pop(0)
        cap = CAPTIONS.get(key, "")
        if cap: self.on_caption(cap)
        idx = 0 if self.voice == "sayit" else 1
        files = SND_FILES.get(key, [])
        if files:
            fname = files[idx] if idx < len(files) else files[0]
            _audio_play(os.path.join(SOUND_DIR, fname))
            self._wait()
        else:
            self.root.after(900 if cap else 0, self._fire)

    def _wait(self):
        if _audio_busy(): self.root.after(60, self._wait)
        else: self.root.after(20, self._fire)


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
        self._drag_ox = self._drag_oy = 0 
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
        self.cv.bind("<Button-1>",        self._on_click)

        # pannello destra
        self.panel = tk.Frame(outer, bg=C["panel_bg"], width=PANEL_W)
        self.panel.pack(side="right", fill="y", padx=(10,0))
        self.panel.pack_propagate(False)
        self._build_panel(self.panel)

    def _build_panel(self, p):
        tk.Label(p, text="GHOULS & GRAVEYARDS",
            font=self.F["brand"], bg=C["panel_bg"], fg=C["highlight"],pady=6).pack(fill="x")
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
            treas_cv = tk.Canvas(hdr, width=22, height=22,bg=C["panel_bg"], highlightthickness=0)
            treas_cv.pack(side="right", padx=(0,2))
            lives_cv = tk.Canvas(fr, width=80, height=18,bg=C["panel_bg"], highlightthickness=0)
            lives_cv.pack(anchor="w", pady=(2,0))
            steps_cv = tk.Canvas(fr, width=230, height=16,bg=C["panel_bg"], highlightthickness=0)
            steps_cv.pack(anchor="w", pady=(1,0))
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
        ghost_frame = tk.Frame(p, bg=C["panel_bg"])
        ghost_frame.pack(fill="x", padx=6, pady=2)
        tk.Label(ghost_frame, text="GHOST TRACKER",font=self.F["h3"], bg=C["panel_bg"], fg=C["ghost_col"]).pack(anchor="w")
        tk.Label(ghost_frame, text="Drag onto map to guess ghost's position",font=self.F["tiny"], bg=C["panel_bg"], fg=C["label_col"]).pack(anchor="w")
        self.ghost_cv = tk.Canvas(ghost_frame, width=PANEL_W-20, height=48,bg=C["panel_bg"], highlightthickness=1,highlightbackground=C["panel_sep"])
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
        self._panel_img_refs = [r for r in self._panel_img_refs]
        cw = PANEL_W - 20; ch = 48
        cx, cy = cw//2, ch//2
        ph = SPRITES.get_fit(SP_GHOST, 36, 36)
        if ph:
            self._panel_img_refs.append(ph)
            self.ghost_cv.create_image(cx, cy, anchor="center", image=ph, tags="idle_ghost")
        else:
            self.ghost_cv.create_oval(cx-14,cy-14,cx+14,cy+14, fill="#8888cc", outline="")
        self.ghost_cv.create_text(cx+24, cy, text="← drag to map",
            font=self.F["tiny"], fill=C["label_col"], anchor="w")

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

    def _panel_ghost_press(self, event):
        if self.grid is None: return
        self._drag_active = True
        cw = PANEL_W-20; ch=48
        self._drag_ox = event.x - cw//2
        self._drag_oy = event.y - ch//2

    def _panel_ghost_motion(self, event):
        if not self._drag_active or self.grid is None: return
        gx = self.ghost_cv.winfo_rootx() + event.x
        gy = self.ghost_cv.winfo_rooty() + event.y
        cx_abs = gx - self.cv.winfo_rootx()
        cy_abs = gy - self.cv.winfo_rooty()
        cell = self._cell_from_canvas(cx_abs, cy_abs)
        if cell != self._ghost_panel_cell:
            self._ghost_panel_cell = cell
            self._full_redraw()
        self.ghost_cv.delete("all")
        self.ghost_cv.create_text(PANEL_W//2-10, 24,
            text="↑ dragging…", font=self.F["tiny"], fill=C["highlight"])

    def _panel_ghost_release(self, event):
        if not self._drag_active: return
        self._drag_active = False
        gx = self.ghost_cv.winfo_rootx() + event.x
        gy = self.ghost_cv.winfo_rooty() + event.y
        cx_abs = gx - self.cv.winfo_rootx()
        cy_abs = gy - self.cv.winfo_rooty()
        cell = self._cell_from_canvas(cx_abs, cy_abs)
        if cell is not None:
            self._ghost_panel_cell = cell
        self._draw_panel_ghost_idle()
        self._full_redraw()

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
        base_sz = int(TILE * 0.8)   # 20% ridotto rispetto a TILE
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
                    if d=="n":
                        self._wall_seg(x0,y0-GAP,x1,y0,True)
                    elif d=="s":
                        self._wall_seg(x0,y1,x1,y1+GAP,True)
                    elif d=="w":
                        self._wall_seg(x0-GAP,y0,x0,y1,False)
                    elif d=="e":
                        self._wall_seg(x1,y0,x1+GAP,y1,False)

    def _wall_seg(self,x0,y0,x1,y1,horiz):
        w=x1-x0; h=y1-y0
        if w<=0 or h<=0: return
        ph=SPRITES.get_fit(SP_WALL,w,h) if not horiz else SPRITES.get_fit(SP_WALL,w,h)
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
                        yy=y0 if d=="n" else y1; mc=(x0+x1)//2
                        ph=SPRITES.get_fit(SP_DOOR,GAP*3,GAP)
                        if ph:
                            self._img_refs.append(ph)
                            self.cv.create_image(mc-GAP*3//2,yy-GAP//2,anchor="nw",image=ph)
                        else:
                            self.cv.create_rectangle(mc-10,yy-GAP//2,mc+10,yy+GAP//2,fill=C["door_col"],outline="")
                    else:
                        xx=x0 if d=="w" else x1; mr=(y0+y1)//2
                        ph=SPRITES.get_fit(SP_DOOR,GAP,GAP*3)
                        if ph:
                            self._img_refs.append(ph)
                            self.cv.create_image(xx-GAP//2,mr-GAP*3//2,anchor="nw",image=ph)
                        else:
                            self.cv.create_rectangle(xx-GAP//2,mr-10,xx+GAP//2,mr+10,fill=C["door_col"],outline="")

    def _draw_treasure(self):
        if self.tr<0: return
        if not self.reveal_all and not self.grid[self.tr][self.tc].seen: return
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

    def _draw_lives(self, cv, lives, max_l):
        cv.delete("all")
        for i in range(max_l):
            col=C["heart_on"] if i<lives else C["heart_off"]
            cv.create_text(6+i*22,9,text="♥",font=("Georgia",13),fill=col,anchor="w")

    def _draw_steps(self, cv, used, max_s):
        cv.delete("all")
        if max_s==0: return
        slot_w=min(18,(226-4)//max_s)
        for i in range(max_s):
            cx=4+i*slot_w+slot_w//2; cy=8
            sp=SP_STEP_US if i<used else SP_STEP_AV
            sz=min(10,slot_w-2)
            ph=SPRITES.get_fit(sp,sz,sz)
            if ph:
                self._panel_img_refs.append(ph)
                cv.create_image(cx,cy,anchor="center",image=ph)
            else:
                col="#550000" if i<used else "#ff0000"
                cv.create_oval(cx-sz//2,cy-sz//2,cx+sz//2,cy+sz//2,fill=col,outline="")

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
                self._draw_lives(lc,0,3); self._draw_steps(sc,0,8)
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
        self.cv.create_rectangle(cx-170,cy-65,cx+170,cy+80,
            fill=C["end_box"],outline=C["treasure_col"],width=3,stipple="gray50",tags="end")
        if won and self.winner is not None:
            msg=f"🏆  Player {self.winner+1} Wins!"; col=C["treasure_col"]
        else:
            msg="💀  Game Over"; col="#ff3333"
        self.cv.create_text(cx,cy-20,text=msg,
            font=("Palatino Linotype",22,"bold"),fill=col,tags="end")
        self.cv.create_text(cx,cy+28,
            text="Full map revealed\nPress  New Game [R]  to play again",
            font=self.F["body"],fill=C["text_col"],justify="center",tags="end")

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
        p["carrying"]=False
        p["max_steps"]=STEPS_BY_LIVES.get(max(0,p["lives"]-1),0)
        if carrying_at_attack:
            p["lives"]=0; p["alive"]=False
        else:
            p["lives"]-=1; p["used_steps"]=0
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

DATA FOLDER STRUCTURE
=====================
Place a folder named "data/" beside ghouls_and_graveyards.py:

data/
  shapes/
    19.svg   — Dragon/Ghost sprite
    21.svg   — Warrior sprite
    24.svg   — Secret Room / Base marker
    29.svg   — Wall tile (dark red square)
    32.svg   — Floor tile (grey bevelled square)
    34.svg   — Speech bubble shape
    51.svg   — Treasure chest sprite
    (other SVGs are ignored)

  sounds/
    0.wav
    1_sayit-youwin.wav.mp3
    2_sayit-tik.wav.mp3
    3_sayit-no.wav.mp3
    4_sayit-hitawall.wav.mp3
    5_sayit-ghostmoves.wav.mp3
    6_sayit-ghostawakes.wav.mp3
    7_sayit-ghostattacks.wav.mp3
    8_sayit-gameover.wav.mp3
    9_sayit-foundtreasure.wav.mp3
    10_nat-youwin.wav.mp3
    11_nat-tik.wav.mp3
    12_nat-no.wav.mp3
    13_nat-hitawall.wav.mp3
    14_nat-ghostmoves.wav.mp3
    15_nat-ghostawakes.wav.mp3
    16_nat-ghostattacks.wav.mp3
    17_nat-gameover.wav.mp3
    18_nat-foundtreasure.wav.mp3

  frames/
    1.png    — Title screen backdrop (641×401)

PYTHON DEPENDENCIES
===================
Required:
  python3  (≥3.9)
  tkinter  (usually bundled; on Ubuntu: sudo apt install python3-tk)

Optional (for SVG sprites):
  pip install cairosvg Pillow

Optional (for sound):
  pip install pygame           ← best cross-platform audio
  pip install playsound        ← fallback

RUN
===
  python ghouls_and_graveyards.py

# Ghouls & Graveyards 🏰👻

A Python/Tkinter retro dungeon crawler inspired by the iconic **1980 Mattel Electronics Computer Labyrinth Game**. 

Explore a hidden 8x8 labyrinth, track down the legendary treasure chest, outsmart or battle rival warriors, and escape before the restless ghost awakens to hunt you down!

---

## 📜 Overview

In **Ghouls & Graveyards**, you step into an unexplored underground dungeon. The maze walls are invisible until you bump into them. Deep within the maze lies a secret treasure room guarding a golden chest, but a sleeping ghost watches over it.

You can play **Solo** against the AI-controlled ghost or **Head-to-Head (Local 2-Player Hotseat)** against a rival warrior.

<img width="910" height="631" alt="Screenshot 2026-10-05 103826" src="https://github.com/user-attachments/assets/518c79e7-3293-458f-92cf-0e9e6c6475f8" />


---

## ✨ Features

- **Retro Labyrinth Exploration:** Procedurally generated 8x8 maze with invisible walls that are revealed as you explore or bump into them.
- **1-Player & 2-Player Modes:** Play solo to beat the ghost or play hotseat against a friend.
- **Two Game Levels:**
  - **Level 1 (Classic):** A static labyrinth generated at the start of the game.
  - **Level 2 (Phantom Doors):** Magic doors dynamically close and open across the dungeon as turns pass.
- **Dynamic Ghost Mechanics:** 
  - The ghost remains asleep in the treasure room until a player ventures near.
  - Once awake, the ghost actively tracks and hunts down warriors.
  - Includes a draggable **Ghost Marker** so you can mark where you suspect the ghost is lurking.
- **Warrior Combat & Duels:** If both players meet on the same tile while carrying the treasure, a duel ensues based on hidden warrior strength!
- **Rich Audio & Visual Experience:**
  - Dual announcer voices (Synthesised vs. Natural voice toggle).
  - Runtime synthesised procedural audio jingles for warrior victories.
  - Custom UI elements: step footprints, live counters, custom sprites, and interactive drag-and-drop elements.


<img width="907" height="633" alt="Screenshot 2026-10-05 103930" src="https://github.com/user-attachments/assets/326fd95f-a66a-4f39-ae61-2867e43caa0c" />


---

## 🎮 How to Play

### 1. Game Setup Phase
1. Select **Level 1** or **Level 2**.
2. **Drag your Secret Room** from the right panel onto the map grid:
   - **1 Secret Room:** Starts a 1-Player game against the AI Ghost.
   - **2 Secret Rooms:** Starts a 2-Player competitive game.
3. Click **Start game** (or press `Space`). The hidden dungeon and treasure room are generated.

### 2. Exploration & Movement
- Move using the **Arrow Keys**, **WASD**, or by **clicking** adjacent tiles on the map.
- Bumping into a wall ends your turn immediately and highlights the wall edge.
- You have a limited number of movement steps per turn based on your current health/lives.

### 3. The Treasure & The Ghost
- **Finding the Treasure:** Stepping into the Treasure Room awards you the treasure. The chest is heavy, dropping your movement speed to **4 steps per turn**.
- **Awakening the Ghost:** The ghost wakes up when any warrior comes within 3 tiles of the treasure room.
- **Ghost Attacks:** If the ghost catches you outside your Secret Room, you lose a life (or drop the treasure) and are sent back to your base.
- **Safe Zone:** The ghost **cannot** enter your own Secret Room! However, you are not safe inside your opponent's room.

### 4. Winning the Game
- Successfully carry the treasure all the way back to **your own Secret Room** to claim victory!


<img width="908" height="629" alt="Screenshot 2026-10-05 103953" src="https://github.com/user-attachments/assets/58741e7d-c17e-43b2-9511-bb1eecca53ec" />


---

## 🕹️ Controls & Shortcuts

| Action | Control |
| :--- | :--- |
| **Move Warrior** | `Arrow Keys` / `WASD` / `Left-Click` adjacent tile |
| **End Turn** | `Spacebar` / `Right-Click` anywhere on the map / `▷ End Turn` button |
| **Toggle Announcer Voice** | `V` key / `♪ Voice` button |
| **Drag & Drop Tokens** | `Left-Click + Drag` Secret Rooms or Ghost Marker |

---

## 💻 Installation & Running

### Prerequisites
Make sure you have **Python 3.8+** installed along with the required dependencies.

```bash
# Clone the repository
git clone https://github.com/your-username/ghouls-and-graveyards.git
cd ghouls-and-graveyards

# Install dependencies
pip install pillow miniaudio
```

### Running the Game

Execute the main script:

```bash
python ghouls_and_graveyards.py
```

---

## 📁 Project Structure

```text
ghouls-and-graveyards/
├── ghouls_and_graveyards.py  # Main game loop, UI engine, sound queue, and logic
├── data/
│   ├── shapes/               # Game sprites & icons (floor, walls, chest, heroes, ghost)
│   └── sounds/               # Audio clips for announcer and game events
└── README.md                 # Project documentation
```

---

## 🛡️ License & Acknowledgments

- Inspired by the classic **Mattel Electronics Computer Labyrinth Game (1980)**.
- Built using **Python**, **Tkinter**, **Pillow**, and **Miniaudio**.

*Enjoy the dungeon crawl, warrior!* 🗡️✨

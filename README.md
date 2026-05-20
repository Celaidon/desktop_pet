# Leon Desktop Pet 🐾

An interactive Shimeji-style desktop companion built with Python and PySide6.

Leon is a transparent always-on-top desktop pet that reacts to user interactions with animations, moods, dialogue, and autonomous behaviors.

---

## Preview

<img width="252" height="302" alt="image" src="https://github.com/user-attachments/assets/186c6f28-65ac-44d4-840c-b5a12b84c0ec" />

HANDMADE frame by frame animations for tickle, angry, sleepy, eating and waking up .

---

## Features

### Interactive Actions
- 🖱️ Left click to pet Leon
- 😂 Double-click to tickle Leon
- 🍖 Feed Leon from right-click menu
- 😴 Put Leon to sleep / wake him up
- 🐭 Optional cursor-follow mode

### Mood & Behavior System
- Angry reaction after excessive tickling
- Sleep mode after inactivity
- Wake-up interaction handling
- Friendship / affection logic
- Anti-spam animation locking

### Animation System
Custom handmade PNG frame animations for:
- Angry
- Sleep
- Wake-up
- Feed
- Tickle

### UI Features
- Transparent frameless desktop overlay
- Always-on-top pet window
- Drag-and-drop movement
- Right-click context menu
- Speech bubbles with random dialogue

---

## Tech Stack

**Programming Language**
- Python

**Framework / Libraries**
- PySide6 (Qt for Python)

**Animation / Asset Creation**
- OpenToonz

**Architecture Concepts**
- Modular Python design
- Event-driven UI
- QTimer animation engine
- State-based interaction system

---

## Project Structure

```bash
desktop_pet/
│
├── assets/
│   ├── sprites/
│   │   └── leon.png
│   │
│   └── animations/
│       ├── angry/
│       ├── sleepy/
│       ├── wakeup/
│       ├── feed/
│       └── tickle/
│
├── main.py
├── pet_window.py
├── dialogue.py
├── speech_bubble.py
├── .gitignore
└── README.md
```

---

## Installation

Clone repository:

```bash
git clone https://github.com/Celaidon/desktop_pet.git
cd desktop_pet
```

Install dependencies:

```bash
pip install PySide6
```

Run:

```bash
python main.py
```

---

## How It Works

Leon uses a modular event-driven architecture:

- `main.py` launches the application
- `pet_window.py` handles UI, dragging, interactions, animations
- `dialogue.py` stores contextual dialogue
- `speech_bubble.py` renders dialogue popups
- QTimer drives frame-by-frame animations

---

## Challenges Solved

This project involved solving:

- transparent desktop overlay rendering
- animation frame playback
- interaction state locking
- anti-spam input handling
- idle timers
- mood/state transitions
- context menu integration
- wake/sleep logic
- animation synchronization

---

## Future Improvements

Planned ideas:

- Idle breathing animation
- Blink loop
- Persistent save system
- Sound effects
- Wandering AI movement
- Reminder / productivity mode
- Outfit / skin switching
- Optional AI conversation mode

---

## Author

Built by **Vani Mishra** ✨

Engineering student exploring software development through creative projects.

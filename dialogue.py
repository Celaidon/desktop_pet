"""
dialogue.py — All of Leon's canned dialogue lines
---------------------------------------------------
This file is pure data + one helper function.
No Qt, no UI, no game logic — just text.

Adding new lines? Just append strings to any list below.
The pick() function will randomly select from them.

Interaction types:
  - PET     : single left-click (friendly tap)
  - TICKLE  : double left-click (playful poke)
  - ANGRY   : tickle overload — shown when tickle counter hits threshold
  - IDLE    : unprompted lines while Leon is awake and uninteracted with
  - FEED    : shown when Leon is fed from the right-click menu
"""

import random


# ── Dialogue lines ────────────────────────────────────────────────────────────

# Shown when the user single-clicks (pets) Leon
PET_LINES = [
    "Hey, watch the hair.",
    "...You good?",
    "I've survived worse than this.",
    "Professional, remember?",
    "What do you need?",
    "Feels kinda nice actually.",
    "Don't get used to it.",
    "I'm on duty, you know.",
    "Ashley would do the same thing.",
    "Heh. Okay.",
]

# Shown when the user double-clicks (tickles) Leon
TICKLE_LINES = [
    "H-hey! Stop that!",
    "I am a government agent!!",
    "Absolutely not.",
    "...Did you just—",
    "I went through STARS training for THIS?",
    "VANIIIIIII",
    "Sto— haha— STOP.",
    "I will report this.",
    "This is not in my mission briefing.",
    "Ada would never.",
]

# Shown when tickle count hits the threshold (tickle overload)
ANGRY_LINES = [
    "THAT'S IT. >:(",
    "I SAID STOP!!",
    "You just made a critical error.",
    "LEON S. KENNEDY IS DONE.",
    "Do you want to be a zombie? Keep it up.",
    "I survived Raccoon City for THIS?!",
    "HEY!! >:(",
    "You have 3 seconds to run.",
    "Umbrella was less annoying than you.",
    "Professional courtesy — OVER.",
]

# Shown randomly while Leon is idle and awake (unprompted, every 20–60s)
IDLE_LINES = [
    "you studying?",
    "im bored...",
    "pet me >:(",
    "what are we doing?",
    "dont ignore me",
    "snacks??",
    "...hello?",
    "this is fine. totally fine.",
    "i cleared Raccoon City for THIS?",
    "someone could at least say hi.",
    "do you hear that? me neither. nothing.",
    "my spidey sense is tingling. or hunger.",
    "just gonna stand here i guess.",
    "you good out there?",
    "tap me. i dare you.",
]

# Shown when Leon is fed from the right-click menu
FEED_LINES = [
    "YUM!!",
    "MORE",
    "nom nom",
    "best human",
    "you spoil me",
    "...okay you're forgiven.",
    "don't stop.",
    "this is why i put up with you.",
    "10/10. no notes.",
    "finally some appreciation.",
]


# ── Picker function ───────────────────────────────────────────────────────────

def pick(lines: list[str]) -> str:
    """
    Return a random line from the given list.
    Simple wrapper around random.choice for clarity.

    Usage:
        from dialogue import pick, PET_LINES
        text = pick(PET_LINES)
    """
    return random.choice(lines)
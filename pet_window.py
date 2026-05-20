"""
pet_window.py — The main desktop pet window
---------------------------------------------
This module creates a transparent, frameless, always-on-top window
that displays the Leon sprite. It handles:

  Mouse interactions:
    Left click      → pet interaction + speech bubble
    Double click    → tickle; overloads into angry animation at threshold
    Right click     → context menu (Pet / Tickle / Feed / Sleep / Follow / Exit)

  Autonomous behaviour:
    7s inactivity   → sleepy animation plays once; Leon holds final frame
    20–60s idle     → Leon says a random idle line (only while awake)
    Follow cursor   → Leon smoothly drifts toward the mouse (toggleable)

  State:
    Friendship counter — rises on pet/feed, drops slightly on tickle overload
    Angry lock         — blocks new inputs while tantrum animation plays
    Sleeping flag      — blocks follow-cursor and idle dialogue

  Architecture:
    One reusable _play_animation() drives all frame sequences.
    All interaction paths call shared helpers (_wake_up, _reset_inactivity_timer)
    to avoid duplicate logic.
"""

import os
import random
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QMenu
from PySide6.QtCore import Qt, QPoint, Signal, QTimer
from PySide6.QtGui import QPixmap, QCursor, QAction

# Local modules
from speech_bubble import SpeechBubble
import dialogue


# ── Asset path helper ────────────────────────────────────────────────────────

# Build an absolute path to assets/ relative to THIS file's location.
# This way the app works regardless of where you run it from.
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
SPRITE_DIR = os.path.join(BASE_DIR, "assets", "sprites")

def get_sprite_path(filename: str) -> str:
    """Return the full path to a sprite file inside assets/sprites/."""
    return os.path.join(SPRITE_DIR, filename)


# Path to the folder that holds animation sub-folders (e.g. angry/, happy/)
ANIM_DIR = os.path.join(BASE_DIR, "assets", "animations")


def load_animation_frames(anim_name: str, width: int = 200) -> list[QPixmap]:
    """
    Load all PNG frames from assets/animations/<anim_name>/ in sorted order.

    Frames are sorted alphabetically, so name your files consistently:
        angry_01.png, angry_02.png, ... OR frame_001.png, frame_002.png ...

    Returns a list of scaled QPixmap objects, ready to display.
    Raises FileNotFoundError if the folder is missing or contains no PNGs.
    """
    folder = os.path.join(ANIM_DIR, anim_name)

    if not os.path.isdir(folder):
        raise FileNotFoundError(
            f"Animation folder not found: {folder}\n"
            f"Expected PNG frames inside assets/animations/{anim_name}/"
        )

    # Collect every .png in the folder, sorted so frames play in order
    filenames = sorted(
        f for f in os.listdir(folder) if f.lower().endswith(".png")
    )

    if not filenames:
        raise FileNotFoundError(
            f"No PNG files found in: {folder}"
        )

    frames = []
    for filename in filenames:
        path = os.path.join(folder, filename)
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            frames.append(pixmap.scaledToWidth(width, Qt.SmoothTransformation))

    return frames


# ── Sprite loader (centralised) ───────────────────────────────────────────────

def load_sprite(filename: str, width: int = 200) -> QPixmap:
    """
    Load a sprite PNG and scale it to `width` pixels (keeps aspect ratio).
    All sprite loading in the whole app should go through this one function
    so there's a single place to change paths, scaling, or caching later.
    """
    path = get_sprite_path(filename)
    pixmap = QPixmap(path)

    if pixmap.isNull():
        # Helpful error instead of a silent blank window
        raise FileNotFoundError(
            f"Could not load sprite: {path}\n"
            f"Make sure '{filename}' is inside assets/sprites/"
        )

    # Scale width, let height follow automatically (smooth = anti-aliased)
    return pixmap.scaledToWidth(width, Qt.SmoothTransformation)


# ── Pet Window ────────────────────────────────────────────────────────────────

class PetWindow(QWidget):
    """
    The main desktop pet window.

    Signals:
        petted   — emitted on a single left-click
        tickled  — emitted on a double left-click
    """

    # Qt signals: other objects can connect() to these to react to interactions
    petted  = Signal()
    tickled = Signal()

    def __init__(self):
        super().__init__()

        # ── Window flags ──────────────────────────────────────────────────────
        self.setWindowFlags(
            Qt.FramelessWindowHint      # No title bar or border
            | Qt.WindowStaysOnTopHint   # Always above other windows
            | Qt.Tool                   # Keeps it off the taskbar (Windows/Linux)
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # ── Load sprites ──────────────────────────────────────────────────────
        # The normal idle sprite — restored after any animation ends
        self._sprite_pixmap = load_sprite("leon.png", width=200)

        # ── Build UI ──────────────────────────────────────────────────────────
        self._build_ui()

        # ── Drag state ────────────────────────────────────────────────────────
        # Tracks mouse offset so the window follows the cursor while dragging
        self._drag_start_pos: QPoint | None = None

        # ── Double-click guard ────────────────────────────────────────────────
        # Qt fires mousePressEvent BEFORE mouseDoubleClickEvent.
        # This 250ms timer lets us distinguish a single-click from a double.
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(250)
        self._click_timer.timeout.connect(self._on_single_click_confirmed)

        # ── Active bubble tracker ─────────────────────────────────────────────
        self._active_bubble: SpeechBubble | None = None

        # ── Tickle overload state ─────────────────────────────────────────────
        self._tickle_count: int     = 0
        self._tickle_threshold: int = 5
        self._angry_locked: bool    = False  # True while angry animation plays

        # ── Sleepy / inactivity state ─────────────────────────────────────────
        # True once sleepy animation finishes and Leon is holding the last frame
        self._is_sleeping: bool = False

        # Inactivity timer — fires once after 7s of no interaction
        self._inactivity_timer = QTimer(self)
        self._inactivity_timer.setSingleShot(True)
        self._inactivity_timer.setInterval(7_000)           # 7 seconds
        self._inactivity_timer.timeout.connect(self._trigger_sleepy)
        self._inactivity_timer.start()                      # Begin counting immediately

        # ── Follow cursor state ───────────────────────────────────────────────
        # When True, Leon drifts toward the mouse cursor every timer tick.
        self._follow_cursor: bool = False

        # Fires every 50ms while follow mode is on — drives smooth movement.
        self._follow_timer = QTimer(self)
        self._follow_timer.setInterval(50)                  # 20 updates per second
        self._follow_timer.timeout.connect(self._follow_step)
        # Note: _follow_timer only starts when follow mode is enabled.

        # How many pixels Leon moves toward the cursor each tick.
        # Lower = floatier, higher = snappier.
        self._follow_speed: int = 8

        # ── Drag-override flag ────────────────────────────────────────────────
        # True while the user is actively dragging. Pauses follow-cursor so
        # the window doesn't fight the drag movement.
        self._is_dragging: bool = False

        # ── Idle dialogue state ───────────────────────────────────────────────
        # Leon occasionally says something unprompted while awake.
        # Timer is restarted with a fresh random interval after each line.
        self._idle_dialogue_timer = QTimer(self)
        self._idle_dialogue_timer.setSingleShot(True)       # One-shot, we restart manually
        self._idle_dialogue_timer.timeout.connect(self._say_idle_line)
        self._schedule_idle_dialogue()                      # Kick off first interval

        # ── Friendship counter ────────────────────────────────────────────────
        # Rises on pet (+1) and feed (+3). Falls on tickle overload (-2).
        # No upper cap — just a running score for future features.
        self._friendship: int = 0

        # ── Pre-load all animation frames at startup ──────────────────────────
        # Both frame lists are loaded once here so there's zero disk I/O
        # when an animation actually triggers.
        self._angry_frames:  list[QPixmap] = load_animation_frames("angry",  width=200)
        self._sleepy_frames: list[QPixmap] = load_animation_frames("sleepy", width=200)
        self._tickle_frames: list[QPixmap] = load_animation_frames("tickle", width=200)
        self._wakeup_frames: list[QPixmap] = load_animation_frames("wakeup", width=200)
        self._feed_frames:   list[QPixmap] = load_animation_frames("feed",   width=200)

        # ── General animation lock ─────────────────────────────────────────────
        # True while ANY one-shot animation (tickle, angry) is mid-playback.
        # Prevents double-clicks from stacking or restarting animations.
        # Distinct from _angry_locked, which also carries side-effects like
        # stopping the inactivity timer and blocking the context menu.
        self._is_animating: bool = False

        # Callback stored by _wake_up() so _finish_wakeup_animation can
        # chain into a second animation (e.g. wakeup → feed).
        # Initialised here so it's never undefined if the finish fires early.
        self._wakeup_callback: callable = None

        # ── Generic animation engine state ────────────────────────────────────
        # _play_animation() writes to these before starting _anim_timer.
        # All animations share this one timer — only one can play at a time.
        self._anim_frames:    list[QPixmap] = []   # Frames currently playing
        self._anim_index:     int           = 0    # Which frame is next
        self._anim_on_finish: callable      = None  # Called when last frame ends

        # Single shared QTimer — interval is set per animation call
        self._anim_timer = QTimer(self)
        self._anim_timer.setSingleShot(False)           # Repeats each tick
        self._anim_timer.timeout.connect(self._anim_tick)

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Create and arrange the sprite label inside the window."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # No padding — tight fit

        # QLabel is the simplest way to display a QPixmap
        self._sprite_label = QLabel(self)
        self._sprite_label.setPixmap(self._sprite_pixmap)
        self._sprite_label.setFixedSize(self._sprite_pixmap.size())

        layout.addWidget(self._sprite_label)

        # Size the window exactly to the sprite — no extra blank area
        self.setFixedSize(self._sprite_pixmap.size())

    # ── Mouse: Drag ───────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        """Record where the drag started (left button only)."""
        if event.button() == Qt.LeftButton:
            # Any press wakes Leon if sleeping and resets the idle clock.
            # on_finish=None — plain click wake, no chained animation.
            self._wake_up(on_finish=None)
            self._reset_inactivity_timer()
            self._schedule_idle_dialogue()      # Reset idle chatter countdown

            self._is_dragging = True            # Pause follow-cursor during drag
            self._drag_start_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            # Start the single-click timer — may be cancelled by double-click
            self._click_timer.start()

        event.accept()

    def mouseMoveEvent(self, event):
        """Move the window to follow the mouse while dragging."""
        if event.buttons() & Qt.LeftButton and self._drag_start_pos:
            new_pos = event.globalPosition().toPoint() - self._drag_start_pos
            self.move(new_pos)

            # Dragging counts as activity — cancel the click and reset idle clock
            self._click_timer.stop()
            self._reset_inactivity_timer()

        event.accept()

    def mouseReleaseEvent(self, event):
        """Reset drag state when the button is released."""
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = None
            self._is_dragging = False   # Follow-cursor may resume after drag ends
        event.accept()

    def contextMenuEvent(self, event):
        """
        Right-click opens a styled context menu.
        Each action delegates to the same shared methods used by mouse clicks,
        so there's zero logic duplication.
        """
        menu = QMenu(self)

        # ── Styling — simple, readable, matches a cute desktop app ───────────
        menu.setStyleSheet("""
            QMenu {
                background-color: #fff8f8;
                border: 2px solid #c0a0c0;
                border-radius: 10px;
                padding: 4px;
                font-family: 'Segoe UI';
                font-size: 10pt;
                color: #3a2a3a;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #e8c8e8;
            }
            QMenu::separator {
                height: 1px;
                background: #d0b0d0;
                margin: 4px 8px;
            }
        """)

        # ── Actions ───────────────────────────────────────────────────────────
        act_pet    = QAction("🖐  Pet",       self)
        act_tickle = QAction("🫶  Tickle",    self)
        act_feed   = QAction("🍖  Feed",      self)
        act_sleep  = QAction("😴  Sleep",     self)
        act_wake   = QAction("👋  Wake Up",   self)

        # Follow cursor toggle — label shows current state
        follow_label = "🐾  Follow Cursor  ✓" if self._follow_cursor else "🐾  Follow Cursor"
        act_follow = QAction(follow_label, self)

        act_exit   = QAction("🚪  Exit",      self)

        menu.addAction(act_pet)
        menu.addAction(act_tickle)
        menu.addAction(act_feed)
        menu.addSeparator()
        menu.addAction(act_sleep)
        menu.addAction(act_wake)
        menu.addSeparator()
        menu.addAction(act_follow)
        menu.addSeparator()
        menu.addAction(act_exit)

        # ── Connect actions — reuse existing methods everywhere possible ───────
        act_pet.triggered.connect(self._do_pet)
        act_tickle.triggered.connect(self._do_tickle)
        act_feed.triggered.connect(self._do_feed)
        act_sleep.triggered.connect(self._trigger_sleepy)
        act_wake.triggered.connect(self._wake_up_from_menu)
        act_follow.triggered.connect(self._toggle_follow_cursor)
        act_exit.triggered.connect(self._exit_app)

        menu.exec(event.globalPos())



    def _show_bubble(self, text: str):
        """
        Close any existing bubble, then show a new one with `text`.
        Centralises bubble creation so click handlers stay short.
        """
        # Close the old bubble immediately if it's still visible
        if self._active_bubble is not None:
            self._active_bubble.close()

        bubble = SpeechBubble(parent_window=self, text=text)
        bubble.show_bubble()
        self._active_bubble = bubble

    # ── Context menu actions ──────────────────────────────────────────────────

    def _do_pet(self):
        """
        Menu 'Pet' — same result as a left-click.
        Wakes Leon (playing wakeup animation if sleeping), shows dialogue,
        bumps friendship slightly. on_finish=None — no chained animation.
        """
        if self._is_animating:
            return
        self._wake_up(on_finish=None)
        self._reset_inactivity_timer()
        self._schedule_idle_dialogue()
        self._friendship += 1
        self.petted.emit()
        self._show_bubble(dialogue.pick(dialogue.PET_LINES))

    def _do_tickle(self):
        """
        Menu 'Tickle' — identical overload logic as double-click path.
        Guarded by both _angry_locked and _is_animating.
        Wake-up plays before tickle if Leon is sleeping (on_finish=None
        here — tickle doesn't chain; it runs after _wake_up returns).
        """
        if self._angry_locked or self._is_animating:
            return
        self._wake_up(on_finish=None)
        self._reset_inactivity_timer()
        self._schedule_idle_dialogue()
        self._tickle_count += 1
        if self._tickle_count >= self._tickle_threshold:
            self.tickled.emit()
            self._trigger_angry()
        else:
            self.tickled.emit()
            self._show_bubble(dialogue.pick(dialogue.TICKLE_LINES))
            self._trigger_tickle_anim()

    def _do_feed(self):
        """
        Menu 'Feed' — plays the feed animation, shows dialogue, boosts friendship.

        If Leon is sleeping:
            _wake_up(on_finish=_trigger_feed_anim) plays wakeup animation first,
            then _trigger_feed_anim fires automatically when wakeup finishes.

        If Leon is already awake:
            _wake_up() calls on_finish immediately, so feed starts right away.

        Animation lock guards against triggering while another anim is playing.
        State changes (friendship, tickle calm) happen in _finish_feed_animation
        so they only apply after the animation actually completes.
        """
        # Ignore if any animation is already playing (angry, tickle, etc.)
        if self._is_animating:
            return

        # Show the dialogue immediately — feels responsive
        self._show_bubble(dialogue.pick(dialogue.FEED_LINES))

        # _wake_up handles sleeping/awake branching; feed fires via on_finish
        self._wake_up(on_finish=self._trigger_feed_anim)

    def _wake_up_from_menu(self):
        """
        Menu 'Wake Up' — plays the wakeup animation if Leon is sleeping,
        then restores idle state. Safe to call when already awake (no-op).
        Passes on_finish=None — plain wake, no chained animation afterward.
        """
        if self._is_animating:
            return                          # Don't interrupt another animation
        self._wake_up(on_finish=None)
        self._reset_inactivity_timer()
        self._schedule_idle_dialogue()

    def _exit_app(self):
        """Quit the app cleanly through Qt's application instance."""
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()

    # ── Follow cursor ─────────────────────────────────────────────────────────

    def _toggle_follow_cursor(self):
        """
        Toggle follow-cursor mode on / off.
        The follow timer only runs while the mode is active.
        """
        self._follow_cursor = not self._follow_cursor
        if self._follow_cursor:
            self._follow_timer.start()
        else:
            self._follow_timer.stop()

    def _follow_step(self):
        """
        Called every 50ms while follow mode is active.
        Moves Leon one step toward the cursor — smooth drift, not a teleport.

        Skipped when:
          - User is actively dragging (drag has physical control of the window)
          - Leon is sleeping (he doesn't move in his sleep)
          - Angry animation is playing (tantrum takes focus)
        """
        if self._is_dragging or self._is_sleeping or self._angry_locked:
            return

        pet_center = self.frameGeometry().center()
        cursor_pos = QCursor.pos()

        dx = cursor_pos.x() - pet_center.x()
        dy = cursor_pos.y() - pet_center.y()
        distance = (dx ** 2 + dy ** 2) ** 0.5

        # Dead-zone: don't jitter when already close enough
        if distance < self._follow_speed:
            return

        # Normalise the direction vector and scale by step size
        step_x = int(dx / distance * self._follow_speed)
        step_y = int(dy / distance * self._follow_speed)
        self.move(self.x() + step_x, self.y() + step_y)

    # ── Idle dialogue ─────────────────────────────────────────────────────────

    def _schedule_idle_dialogue(self):
        """
        (Re)start the idle dialogue timer with a fresh random interval.
        Calling this after every interaction ensures the countdown always
        begins from now, preventing lines from firing right after interaction.
        """
        interval_ms = random.randint(20_000, 60_000)    # 20–60 second window
        self._idle_dialogue_timer.start(interval_ms)

    def _say_idle_line(self):
        """
        Fires when the idle dialogue timer expires.
        Speaks only while Leon is awake and not mid-animation.
        Always reschedules itself with a new random interval afterward.
        """
        if self._is_sleeping or self._angry_locked:
            # Can't speak right now — try again after a fresh delay
            self._schedule_idle_dialogue()
            return

        self._show_bubble(dialogue.pick(dialogue.IDLE_LINES))
        self._schedule_idle_dialogue()     # Restart for the next unprompted line

    # ── Generic animation engine ──────────────────────────────────────────────

    def _play_animation(
        self,
        frames: list[QPixmap],
        interval_ms: int,
        on_finish: callable,
    ):
        """
        Reusable frame-sequence player. Called by _trigger_angry and
        _trigger_sleepy with their own frames, speed, and finish callback.

        Args:
            frames      : pre-loaded list of QPixmap frames to display
            interval_ms : milliseconds between frames
            on_finish   : function to call after the last frame is shown
        """
        # Stop any animation that might already be running
        self._anim_timer.stop()

        # Store the animation's parameters in shared engine state
        self._anim_frames    = frames
        self._anim_index     = 0
        self._anim_on_finish = on_finish

        # Set this animation's speed and start ticking
        self._anim_timer.setInterval(interval_ms)
        self._anim_timer.start()

    def _anim_tick(self):
        """
        Called by _anim_timer on every tick (shared by all animations).
        Shows the next frame, or calls on_finish when the sequence ends.
        """
        if self._anim_index >= len(self._anim_frames):
            # All frames shown — stop timer and hand off to the finish callback
            self._anim_timer.stop()
            if self._anim_on_finish:
                self._anim_on_finish()
            return

        # Display current frame and advance the index for next tick
        self._sprite_label.setPixmap(self._anim_frames[self._anim_index])
        self._anim_index += 1

    # ── Inactivity / wake-up ──────────────────────────────────────────────────

    def _reset_inactivity_timer(self):
        """
        Restart the 7-second idle countdown from zero.
        Call this on every user interaction so the clock only fires after
        a full 7 seconds of silence.
        """
        # Don't restart if Leon is mid-angry — angry takes priority
        if not self._angry_locked:
            self._inactivity_timer.start()     # start() on a running timer restarts it

    def _wake_up(self, on_finish: callable = None):
        """
        Wake Leon from sleep.

        If Leon IS sleeping:
            Plays the wakeup animation once.
            When the animation ends, calls on_finish (if provided).
            Restores idle sprite and resets timers inside _finish_wakeup_animation.

        If Leon is NOT sleeping:
            Calls on_finish immediately (if provided) so callers that chain
            into a second animation still work correctly.

        Always safe to call — does the right thing in either state.

        Args:
            on_finish : optional callable to invoke after wakeup completes.
                        Pass None for a plain wake (click, drag, menu Wake Up).
                        Pass _trigger_feed_anim to chain wakeup → feed.
        """
        if self._is_sleeping:
            # Store the callback so _finish_wakeup_animation can forward it
            self._wakeup_callback = on_finish
            self._is_sleeping     = False       # Mark awake before anim starts
            self._is_animating    = True        # Lock against other triggers
            self._inactivity_timer.stop()
            self._play_animation(
                frames      = self._wakeup_frames,
                interval_ms = 120,              # snappy wake-up pace
                on_finish   = self._finish_wakeup_animation,
            )
        else:
            # Already awake — forward to callback immediately if given
            if on_finish:
                on_finish()

    # ── Angry animation ───────────────────────────────────────────────────────

    def _trigger_angry(self):
        """
        Called when tickle count hits the threshold.
        Pauses inactivity tracking, shows angry dialogue, plays angry frames.
        """
        self._angry_locked = True
        self._inactivity_timer.stop()       # Don't fall asleep mid-tantrum
        self._show_bubble(dialogue.pick(dialogue.ANGRY_LINES))
        self._play_animation(
            frames      = self._angry_frames,
            interval_ms = 400,              # 400 ms per frame
            on_finish   = self._finish_angry_animation,
        )

    def _finish_angry_animation(self):
        """
        Called after all angry frames have played once.
        Restores idle sprite, resets angry state, restarts both timers.
        Applies a friendship penalty — tickle overload has consequences.
        """
        self._sprite_label.setPixmap(self._sprite_pixmap)
        self._tickle_count  = 0
        self._angry_locked  = False
        self._is_animating  = False                         # Release general lock too
        self._friendship    = max(0, self._friendship - 2)  # Overload costs friendship
        self._reset_inactivity_timer()
        self._schedule_idle_dialogue()  # Fresh idle countdown after tantrum ends

    # ── Tickle animation ──────────────────────────────────────────────────────

    def _trigger_tickle_anim(self):
        """
        Play the tickle PNG frame sequence once, then return to idle sprite.

        Called by mouseDoubleClickEvent and _do_tickle() ONLY when:
          - _is_animating is False (no animation already running)
          - _angry_locked is False (no tantrum in progress)
          - Sleepy animation is not mid-play (guarded at call sites)

        Sets _is_animating = True for the duration so spam double-clicks
        are silently ignored until _finish_tickle_animation() clears the lock.
        """
        self._is_animating = True           # Engage anti-spam lock
        self._inactivity_timer.stop()       # Don't doze off mid-tickle
        self._play_animation(
            frames      = self._tickle_frames,
            interval_ms = 120,              # ~8 fps — snappy, playful
            on_finish   = self._finish_tickle_animation,
        )

    def _finish_tickle_animation(self):
        """
        Called by the animation engine after the last tickle frame is shown.
        Restores the idle sprite and releases the anti-spam lock so the next
        tickle can be accepted.
        """
        self._sprite_label.setPixmap(self._sprite_pixmap)  # Back to idle Leon
        self._is_animating = False                          # Accept tickles again
        self._reset_inactivity_timer()                      # Resume idle countdown

    # ── Wakeup animation ──────────────────────────────────────────────────────

    def _finish_wakeup_animation(self):
        """
        Called after all wakeup frames have played once.
        Restores idle sprite, releases the animation lock, restarts timers.
        Then forwards to _wakeup_callback if one was set — this is how
        _do_feed chains wakeup → feed without any duplicate logic.
        """
        self._sprite_label.setPixmap(self._sprite_pixmap)
        self._is_animating = False
        self._reset_inactivity_timer()
        self._schedule_idle_dialogue()

        # Forward to the chained callback (e.g. _trigger_feed_anim), if any
        callback = self._wakeup_callback
        self._wakeup_callback = None            # Clear before calling — no double-fire
        if callback:
            callback()

    # ── Feed animation ────────────────────────────────────────────────────────

    def _trigger_feed_anim(self):
        """
        Play the feed animation once, then restore idle sprite.
        Called directly when already awake, or as _wakeup_callback when
        Leon was sleeping (wakeup → feed chain via _do_feed).
        """
        self._is_animating = True
        self._inactivity_timer.stop()
        self._play_animation(
            frames      = self._feed_frames,
            interval_ms = 150,              # brisk nom-nom pace
            on_finish   = self._finish_feed_animation,
        )

    def _finish_feed_animation(self):
        """
        Called after all feed frames have played once.
        Restores idle sprite, releases lock, applies friendship reward,
        and partially calms tickle count (fed Leon is harder to anger).
        State changes live here — not in _do_feed — so they only apply
        when the animation actually completes.
        """
        self._sprite_label.setPixmap(self._sprite_pixmap)
        self._is_animating  = False
        # Feeding reward — more than petting (+1)
        self._friendship   += 3
        # Partial calm: feeding reduces recent tickle grievances
        self._tickle_count  = max(0, self._tickle_count - 2)
        self._reset_inactivity_timer()
        self._schedule_idle_dialogue()

    # ── Sleepy animation ──────────────────────────────────────────────────────

    def _trigger_sleepy(self):
        """
        Called by _inactivity_timer after 7 seconds of no interaction.
        Plays the sleepy frame sequence once, then holds the final frame.
        Blocked if angry animation or any other one-shot animation is playing.
        """
        # Don't go to sleep during any animation — both locks checked
        if self._angry_locked or self._is_animating:
            return

        self._play_animation(
            frames      = self._sleepy_frames,
            interval_ms = 1_000,            # 1 second per frame (slow, drowsy)
            on_finish   = self._finish_sleepy_animation,
        )

    def _finish_sleepy_animation(self):
        """
        Called after all sleepy frames have played once.
        Holds the LAST frame visible — Leon stays asleep until interaction.
        """
        self._is_sleeping = True

        # Show the final frame permanently (no timer running)
        if self._sleepy_frames:
            self._sprite_label.setPixmap(self._sleepy_frames[-1])

    # ── Mouse: Click interactions ─────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event):
        """
        Double-click detected — cancel pending single-click, handle tickle logic.

        Guard priority (checked top to bottom — first match wins):
          1. _angry_locked    → ignore entirely (tantrum in progress)
          2. _is_animating    → ignore entirely (tickle animation mid-play)
          3. threshold hit    → wake + trigger angry overload
          4. normal tickle    → wake if sleeping, play tickle animation + bubble
        """
        if event.button() == Qt.LeftButton:
            self._click_timer.stop()

            # Guard 1 — angry animation playing: ignore all tickle input
            if self._angry_locked:
                event.accept()
                return

            # Guard 2 — tickle animation already playing: anti-spam lock
            if self._is_animating:
                event.accept()
                return

            self._schedule_idle_dialogue()
            self._tickle_count += 1

            if self._tickle_count >= self._tickle_threshold:
                # Overload path — wake first (no chained anim), then go angry
                self._wake_up(on_finish=None)
                self._reset_inactivity_timer()
                self.tickled.emit()
                self._trigger_angry()
            else:
                # Normal tickle — wake if sleeping, play tickle animation + dialogue
                self._wake_up(on_finish=None)
                self._reset_inactivity_timer()
                self.tickled.emit()
                self._show_bubble(dialogue.pick(dialogue.TICKLE_LINES))
                self._trigger_tickle_anim()

        event.accept()

    def _on_single_click_confirmed(self):
        """
        Called by the timer after 250 ms if no double-click interrupted.
        This means it really was a single click — emit 'petted'.
        Bumps friendship slightly and resets the idle dialogue countdown.
        """
        self._friendship += 1
        self._schedule_idle_dialogue()
        self.petted.emit()
        self._show_bubble(dialogue.pick(dialogue.PET_LINES))
"""
speech_bubble.py — Leon's speech bubble popup
-----------------------------------------------
A small frameless Qt window that:
  - Appears just above Leon's head
  - Shows a short text message
  - Has a rounded, cute style (white bubble, soft border)
  - Auto-disappears after a set duration (default 2.5 seconds)
  - Fades out smoothly when dismissing

Usage (from pet_window.py):
    bubble = SpeechBubble(parent_window=self, text="Hey!")
    bubble.show_bubble()
"""

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont


# ── Styling constants ─────────────────────────────────────────────────────────

BUBBLE_STYLE = """
    QWidget#SpeechBubble {
        background-color: white;
        border: 2px solid #c0a0c0;
        border-radius: 16px;
    }
"""

TEXT_STYLE = """
    QLabel {
        color: #3a2a3a;
        background: transparent;
        padding: 4px 2px;
    }
"""

BUBBLE_FONT  = QFont("Segoe UI", 10)   # Clean, readable on Windows
MAX_WIDTH    = 220                      # Pixels — keeps lines short and cute
DISPLAY_MS   = 2500                     # How long the bubble stays (ms)
FADE_MS      = 400                      # Fade-out animation duration (ms)


# ── SpeechBubble widget ───────────────────────────────────────────────────────

class SpeechBubble(QWidget):
    """
    A frameless, transparent-background popup that appears above the pet.

    Args:
        parent_window : the PetWindow instance (used to find screen position)
        text          : the dialogue line to display
        duration_ms   : how many ms before auto-dismiss (default DISPLAY_MS)
    """

    def __init__(self, parent_window: QWidget, text: str, duration_ms: int = DISPLAY_MS):
        # No Qt parent — free-floating window so it can overlap anything
        super().__init__(parent=None)

        self._parent_window = parent_window
        self._text          = text
        self._duration_ms   = duration_ms

        self._setup_window()
        self._build_ui()
        self._setup_timers()

    # ── Window setup ──────────────────────────────────────────────────────────

    def _setup_window(self):
        """Configure window flags for a transparent, always-on-top popup."""
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool                   # Off taskbar
            | Qt.WindowTransparentForInput  # Clicks pass through the bubble
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # Don't steal focus
        self.setObjectName("SpeechBubble")              # For stylesheet targeting

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Create the rounded bubble container and text label."""
        # Outer layout (transparent — just positions the bubble widget)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 0, 8, 12)  # Bottom gap = tail space

        # Inner bubble container (this gets the white + border styling)
        self._bubble_widget = QWidget(self)
        self._bubble_widget.setObjectName("SpeechBubble")
        self._bubble_widget.setStyleSheet(BUBBLE_STYLE)

        inner_layout = QVBoxLayout(self._bubble_widget)
        inner_layout.setContentsMargins(14, 10, 14, 10)

        # Text label
        self._label = QLabel(self._text, self._bubble_widget)
        self._label.setFont(BUBBLE_FONT)
        self._label.setStyleSheet(TEXT_STYLE)
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(MAX_WIDTH)
        self._label.setAlignment(Qt.AlignCenter)

        inner_layout.addWidget(self._label)
        outer_layout.addWidget(self._bubble_widget)

        # Size to fit text, then fix so it doesn't resize later
        self.adjustSize()
        self.setFixedSize(self.sizeHint())

    # ── Timers ────────────────────────────────────────────────────────────────

    def _setup_timers(self):
        """Set up the auto-dismiss timer and fade animation."""
        # Timer fires once after DISPLAY_MS → triggers fade out
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.setInterval(self._duration_ms)
        self._dismiss_timer.timeout.connect(self._start_fade_out)

        # Fade-out animation on the window opacity (1.0 → 0.0)
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(FADE_MS)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.finished.connect(self.close)   # Close after fade

    # ── Positioning ───────────────────────────────────────────────────────────

    def _position_above_pet(self):
        """
        Move the bubble so it sits just above Leon's head.
        Uses the parent PetWindow's screen position as reference.
        """
        pet_geo  = self._parent_window.frameGeometry()
        pet_center_x = pet_geo.left() + pet_geo.width() // 2

        bubble_w = self.width()
        bubble_h = self.height()

        # Center the bubble horizontally over the pet
        x = pet_center_x - bubble_w // 2
        # Place it just above the pet window (with a small gap)
        y = pet_geo.top() - bubble_h - 6

        self.move(x, y)

    # ── Public API ────────────────────────────────────────────────────────────

    def show_bubble(self):
        """
        Position and show the bubble, then start the auto-dismiss timer.
        Call this instead of show() directly.
        """
        self._position_above_pet()
        self.setWindowOpacity(1.0)  # Reset in case bubble is reused
        self.show()
        self._dismiss_timer.start()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _start_fade_out(self):
        """Begin the fade-out animation (called automatically by timer)."""
        self._fade_anim.start()

"""
PyQt6 overlay window — frameless, always-on-top, non-focus-stealing.
Plain QWidget subclass (no nativeEvent override).

Click-through: WS_EX_TRANSPARENT makes the whole window pass clicks to whatever
is underneath. A 50ms timer polls the cursor position; when it's over the close
button the flag is temporarily removed so the button can be clicked.
"""

import ctypes
import ctypes.wintypes

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import config

GWL_EXSTYLE      = -20
WS_EX_NOACTIVATE  = 0x08000000
WS_EX_TOOLWINDOW  = 0x00000080
WS_EX_TRANSPARENT = 0x00000020


def _get_screen():
    app = QApplication.instance()
    if config.MONITOR == "primary":
        return app.primaryScreen()
    screens = app.screens()
    try:
        idx = int(config.MONITOR)
    except (ValueError, TypeError):
        return app.primaryScreen()
    return screens[idx] if idx < len(screens) else app.primaryScreen()


class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._lines: list[str] = []
        self._click_through = False   # tracks current WS_EX_TRANSPARENT state
        self._setup_window()
        self._build_ui()
        self._setup_hover_timer()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

    def _build_ui(self):
        container = QWidget(self)
        container.setObjectName("container")
        container.setStyleSheet(
            "#container { background: rgba(20, 20, 20, 180); border-radius: 6px; }"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(4)

        bar = QHBoxLayout()
        title = QLabel("STT Overlay")
        title.setStyleSheet("font-weight: bold; font-size: 11px; color: #888;")
        bar.addWidget(title)
        bar.addStretch()

        self._close_btn = QPushButton("X")
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent; font-size: 12px; color: #666; }"
            "QPushButton:hover { color: #ff4444; }"
        )
        self._close_btn.clicked.connect(self._on_close)
        bar.addWidget(self._close_btn)
        root.addLayout(bar)

        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._label.setMinimumWidth(300)
        self._label.setMaximumWidth(500)
        self._label.setStyleSheet("font-size: 13px; color: #e8e8e8; padding: 2px;")
        root.addWidget(self._label)

        self._status = QLabel("")
        self._status.setStyleSheet("font-size: 11px; color: #e05050; font-style: italic;")
        root.addWidget(self._status)

    def _setup_hover_timer(self):
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(50)   # 20 Hz — cheap, imperceptible latency
        self._hover_timer.timeout.connect(self._update_click_through)
        self._hover_timer.start()

    # ── Public API ────────────────────────────────────────────────────────────
    def show_recording(self):
        self._status.setText("Recording...")
        self._ensure_visible()

    def show_transcribing(self):
        self._status.setText("Transcribing...")

    def append_text(self, text: str):
        if not text:
            return
        self._lines.append(text)
        if len(self._lines) > config.MAX_LINES:
            self._lines = self._lines[-config.MAX_LINES:]
        self._label.setText("\n".join(self._lines))
        self._status.setText("")
        self.adjustSize()
        self._ensure_visible()
        self._reposition()

    def keyPressEvent(self, event: QKeyEvent):
        event.accept()

    # ── Click-through logic ───────────────────────────────────────────────────
    def _update_click_through(self):
        """Enable click-through unless the cursor is over the close button."""
        if not self.isVisible():
            return

        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))

        btn = self._close_btn
        tl = btn.mapToGlobal(btn.rect().topLeft())
        over_btn = (tl.x() <= pt.x <= tl.x() + btn.width() and
                    tl.y() <= pt.y <= tl.y() + btn.height())

        # Only call SetWindowLongW when the state actually changes
        want_through = not over_btn
        if want_through != self._click_through:
            self._set_click_through(want_through)

    def _set_click_through(self, enabled: bool):
        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enabled:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        self._click_through = enabled

    # ── Internal helpers ──────────────────────────────────────────────────────
    def _ensure_visible(self):
        if not self.isVisible():
            self.show()
            self._apply_no_activate()
        self._reposition()

    def _on_close(self):
        self._lines.clear()
        self._label.setText("")
        self._status.setText("")
        self.hide()

    def _apply_no_activate(self):
        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        )

    def _reposition(self):
        screen = _get_screen()
        geo = screen.geometry()
        w, h = self.width(), self.height()
        m = config.MARGIN
        positions = {
            "top_left":      (geo.x() + m,                         geo.y() + m),
            "top_center":    (geo.x() + geo.width() // 2 - w // 2, geo.y() + m),
            "top_right":     (geo.x() + geo.width() - w - m,       geo.y() + m),
            "middle_left":   (geo.x() + m,                         geo.y() + geo.height() // 2 - h // 2),
            "center":        (geo.x() + geo.width() // 2 - w // 2, geo.y() + geo.height() // 2 - h // 2),
            "middle_right":  (geo.x() + geo.width() - w - m,       geo.y() + geo.height() // 2 - h // 2),
            "bottom_left":   (geo.x() + m,                         geo.y() + geo.height() - h - m),
            "bottom_center": (geo.x() + geo.width() // 2 - w // 2, geo.y() + geo.height() - h - m),
            "bottom_right":  (geo.x() + geo.width() - w - m,       geo.y() + geo.height() - h - m),
        }
        x, y = positions.get(config.ANCHOR, positions["middle_right"])
        self.move(x, y)

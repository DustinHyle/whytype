"""On-screen recording indicator, styled after the iPhone Dynamic Island.

A frameless, always-on-top, click-through pill near the top of the screen. It
shows a live microphone level while recording so the user can *see* that their
voice is registering — the reported failure mode was talking to an app that was
in the recording state but hearing nothing.
"""

from __future__ import annotations

import math
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

# Pill geometry.
_WIDTH = 190
_HEIGHT = 44
_TOP_MARGIN = 12

# Level meter.
_BAR_COUNT = 5
_BAR_WIDTH = 4
_BAR_GAP = 4
_BAR_MAX = 22
_BAR_MIN = 4

# Peak amplitude that drives the bars to full height. Normal speech peaks well
# below 1.0, so scaling against 1.0 would leave the meter looking dead.
_FULL_SCALE = 0.35

_UPDATE_MS = 50
_FADE_MS = 400


class RecordingIndicator(QWidget):
    """Floating status pill shown during recording, transcription and typing."""

    def __init__(self, level_provider: Callable[[], float]) -> None:
        super().__init__(None)
        self._level_provider = level_provider
        self._state = "recording"
        # One smoothed height ratio (0.0-1.0) per bar. Bars lag the raw level
        # so the meter decays smoothly instead of strobing.
        self._bars = [0.0] * _BAR_COUNT
        self._phase = 0.0
        self._opacity = 1.0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # keeps it out of the taskbar and unfocusable
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.resize(_WIDTH, _HEIGHT)

        self._timer = QTimer(self)
        self._timer.setInterval(_UPDATE_MS)
        self._timer.timeout.connect(self._tick)

        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(_UPDATE_MS)
        self._fade_timer.timeout.connect(self._fade_step)

    # --- Public API -------------------------------------------------------

    def show_state(self, state: str) -> None:
        """Show the pill in `state` ("recording", "transcribing", "typing")."""
        self._fade_timer.stop()
        self._opacity = 1.0
        self._state = state
        if state == "recording":
            self._bars = [0.0] * _BAR_COUNT
        if not self.isVisible():
            self._move_to_active_screen()
            self.show()
            self.raise_()
        self._timer.start()
        self.update()

    def dismiss(self) -> None:
        """Fade the pill out and hide it."""
        if not self.isVisible():
            return
        self._timer.stop()
        self._fade_timer.start()

    # --- Internals --------------------------------------------------------

    def _move_to_active_screen(self) -> None:
        """Centre the pill at the top of the screen holding the cursor."""
        from PySide6.QtGui import QCursor, QGuiApplication

        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.x() + (geo.width() - _WIDTH) // 2,
            geo.y() + _TOP_MARGIN,
        )

    def _tick(self) -> None:
        self._phase += _UPDATE_MS / 1000.0
        if self._state == "recording":
            try:
                level = min(1.0, max(0.0, self._level_provider() / _FULL_SCALE))
            except Exception:
                level = 0.0
            # Give each bar its own target so the meter reads as a waveform
            # rather than five identical blocks, then ease toward it.
            for i in range(_BAR_COUNT):
                shape = 0.55 + 0.45 * math.sin(self._phase * 7.0 + i * 1.3)
                target = level * shape
                current = self._bars[i]
                # Attack fast, release slow — the same asymmetry a VU meter uses.
                rate = 0.6 if target > current else 0.25
                self._bars[i] = current + (target - current) * rate
        self.update()

    def _fade_step(self) -> None:
        self._opacity -= _UPDATE_MS / _FADE_MS
        if self._opacity <= 0:
            self._opacity = 1.0
            self._fade_timer.stop()
            self.hide()
            return
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)

        rect = QRectF(0, 0, self.width(), self.height())
        path = QPainterPath()
        path.addRoundedRect(rect, self.height() / 2, self.height() / 2)
        painter.fillPath(path, QBrush(QColor(0, 0, 0, 235)))
        painter.setPen(QPen(QColor(255, 255, 255, 28), 1))
        painter.drawPath(path)

        if self._state == "recording":
            self._paint_recording(painter, rect)
        else:
            label = "Transcribing…" if self._state == "transcribing" else "Typing…"
            self._paint_busy(painter, rect, label)

    def _paint_recording(self, painter: QPainter, rect: QRectF) -> None:
        meter_width = _BAR_COUNT * _BAR_WIDTH + (_BAR_COUNT - 1) * _BAR_GAP
        dot_radius = 5.0
        gap = 10.0
        content = dot_radius * 2 + gap + meter_width
        x = rect.center().x() - content / 2
        cy = rect.center().y()

        # Pulsing red dot.
        pulse = 0.65 + 0.35 * math.sin(self._phase * 4.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 69, 58, int(255 * pulse)))
        painter.drawEllipse(QPointF(x + dot_radius, cy), dot_radius, dot_radius)

        x += dot_radius * 2 + gap
        painter.setBrush(QColor(255, 255, 255, 235))
        for ratio in self._bars:
            height = _BAR_MIN + (_BAR_MAX - _BAR_MIN) * ratio
            bar = QRectF(x, cy - height / 2, _BAR_WIDTH, height)
            painter.drawRoundedRect(bar, _BAR_WIDTH / 2, _BAR_WIDTH / 2)
            x += _BAR_WIDTH + _BAR_GAP

    def _paint_busy(self, painter: QPainter, rect: QRectF, label: str) -> None:
        font = QFont(painter.font())
        font.setPointSizeF(10.5)
        painter.setFont(font)
        text_width = painter.fontMetrics().horizontalAdvance(label)

        spinner_radius = 7.0
        gap = 9.0
        content = spinner_radius * 2 + gap + text_width
        x = rect.center().x() - content / 2
        cy = rect.center().y()

        # Spinner: a 270° arc rotating at a steady rate.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor(255, 255, 255, 220), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        arc = QRectF(x, cy - spinner_radius, spinner_radius * 2, spinner_radius * 2)
        start = int(-self._phase * 300 * 16) % (360 * 16)
        painter.drawArc(arc, start, 270 * 16)

        painter.setPen(QColor(255, 255, 255, 235))
        painter.drawText(
            QRectF(x + spinner_radius * 2 + gap, rect.top(), text_width, rect.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            label,
        )

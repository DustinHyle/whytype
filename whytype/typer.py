"""Keyboard text simulation using pynput."""

from pynput.keyboard import Controller


class TextTyper:
    """Types text into the focused input field character-by-character."""

    def __init__(self) -> None:
        self._controller = Controller()

    def type_text(self, text: str) -> None:
        if not text:
            return
        try:
            self._controller.type(text)
        except Exception:
            # pynput may fail for some Unicode characters or missing permissions.
            # Swallow the error to avoid crashing the app.
            pass

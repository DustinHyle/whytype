"""Configuration management for WhyType."""

import json
import os
import sys
from platformdirs import user_config_dir

APP_NAME = "WhyType"


def default_shortcut() -> str:
    """Platform-appropriate default global shortcut.

    Windows/Linux use Ctrl+Win (Super); macOS uses Ctrl+Cmd. The Fn key is
    intentionally avoided on macOS because it is not deliverable to the
    keyboard listener.
    """
    if sys.platform == "darwin":
        return "ctrl+cmd"
    return "ctrl+win"


_DEFAULT_SHORTCUT = default_shortcut()

DEFAULT_CONFIG = {
    "shortcut": _DEFAULT_SHORTCUT,
    "model": "",
    "custom_model_path": "",
    "recording_mode": "hold",
    "device": "auto",  # auto | gpu | cpu
    "input_device": "",  # "" = OS default microphone; else device name
}


class Config:
    """Persistent JSON-backed configuration store."""

    def __init__(self) -> None:
        self._config_dir = user_config_dir(APP_NAME)
        self._config_path = os.path.join(self._config_dir, "settings.json")
        self._data = DEFAULT_CONFIG.copy()
        self.load()

    def load(self) -> None:
        """Load configuration from disk, or keep defaults if missing/corrupt."""
        if not os.path.exists(self._config_path):
            return
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    self._data.update(loaded)
        except (json.JSONDecodeError, OSError, TypeError):
            # If the config file is corrupt, start with defaults.
            self._data = DEFAULT_CONFIG.copy()

    def save(self) -> None:
        """Persist current configuration to disk."""
        os.makedirs(self._config_dir, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str):
        return self._data.get(key)

    def set(self, key: str, value) -> None:
        self._data[key] = value

    @property
    def shortcut(self) -> str:
        return self._data.get("shortcut", DEFAULT_CONFIG["shortcut"])

    @shortcut.setter
    def shortcut(self, value: str) -> None:
        self._data["shortcut"] = value

    @property
    def model(self) -> str:
        return self._data.get("model", DEFAULT_CONFIG["model"])

    @model.setter
    def model(self, value: str) -> None:
        self._data["model"] = value

    @property
    def custom_model_path(self) -> str:
        return self._data.get("custom_model_path", DEFAULT_CONFIG["custom_model_path"])

    @custom_model_path.setter
    def custom_model_path(self, value: str) -> None:
        self._data["custom_model_path"] = value

    @property
    def recording_mode(self) -> str:
        return self._data.get("recording_mode", DEFAULT_CONFIG["recording_mode"])

    @recording_mode.setter
    def recording_mode(self, value: str) -> None:
        self._data["recording_mode"] = value

    @property
    def device(self) -> str:
        return self._data.get("device", DEFAULT_CONFIG["device"])

    @device.setter
    def device(self, value: str) -> None:
        self._data["device"] = value

    @property
    def input_device(self) -> str:
        """Microphone device name, or "" to use the OS default."""
        return self._data.get("input_device", DEFAULT_CONFIG["input_device"])

    @input_device.setter
    def input_device(self, value: str) -> None:
        self._data["input_device"] = value

    def effective_model(self) -> str:
        """Return the active model identifier: custom path if valid, otherwise built-in name."""
        custom = self.custom_model_path.strip()
        if custom and os.path.exists(custom):
            return custom
        return self.model

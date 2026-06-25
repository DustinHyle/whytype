"""Settings dialog for WhyType."""

from __future__ import annotations

import logging
import sys
import threading
from typing import Optional

logger = logging.getLogger("whytype.settings")

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QWidget,
)
from PySide6.QtCore import Qt, Signal

from whytype.config import Config
from whytype.recorder import list_input_devices
from whytype.models import MODEL_REGISTRY, is_model_downloaded, download_model


class ShortcutButton(QPushButton):
    """A button that captures the next key combination pressed while active."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Click to set shortcut...", parent)
        self.setCheckable(True)
        self.toggled.connect(self._on_toggled)
        self._captured: list[str] = []
        self._pending_mods: list[str] = []
        if sys.platform == "win32":
            meta_name = "win"
        elif sys.platform == "darwin":
            meta_name = "cmd"
        else:
            meta_name = "win"
        self._meta_name = meta_name
        self._modifier_map = {
            Qt.Key_Control: "ctrl",
            Qt.Key_Shift: "shift",
            Qt.Key_Alt: "alt",
            Qt.Key_Meta: meta_name,
        }
        self._special_map = {
            Qt.Key_Space: "space",
            Qt.Key_Tab: "tab",
            Qt.Key_Return: "enter",
            Qt.Key_Enter: "enter",
            Qt.Key_Escape: "esc",
            Qt.Key_Backspace: "backspace",
            Qt.Key_Delete: "delete",
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
            Qt.Key_Home: "home",
            Qt.Key_End: "end",
            Qt.Key_PageUp: "pageup",
            Qt.Key_PageDown: "pagedown",
            Qt.Key_F1: "f1",
            Qt.Key_F2: "f2",
            Qt.Key_F3: "f3",
            Qt.Key_F4: "f4",
            Qt.Key_F5: "f5",
            Qt.Key_F6: "f6",
            Qt.Key_F7: "f7",
            Qt.Key_F8: "f8",
            Qt.Key_F9: "f9",
            Qt.Key_F10: "f10",
            Qt.Key_F11: "f11",
            Qt.Key_F12: "f12",
        }

    def _on_toggled(self, checked: bool) -> None:
        if checked:
            self._pending_mods = []
            self.setText("Press keys...")

    def _event_modifiers(self, event) -> list:
        """Modifier tokens currently held, in a stable canonical order."""
        mods = []
        m = event.modifiers()
        if m & Qt.ControlModifier:
            mods.append("ctrl")
        if m & Qt.ShiftModifier:
            mods.append("shift")
        if m & Qt.AltModifier:
            mods.append("alt")
        if m & Qt.MetaModifier:
            mods.append(self._meta_name)
        return mods

    def keyPressEvent(self, event) -> None:
        if not self.isChecked():
            super().keyPressEvent(event)
            return

        key = event.key()
        if key in (Qt.Key_unknown, 0):
            return

        if key in self._modifier_map:
            # Track the largest modifier-only combo held so far. If no normal
            # key follows, it is finalized on release (e.g. Ctrl+Win).
            mods = self._event_modifiers(event)
            this_mod = self._modifier_map[key]
            if this_mod not in mods:
                mods.append(this_mod)
            if len(mods) >= len(self._pending_mods):
                self._pending_mods = mods
            self.setText(" + ".join(mods) + " + …")
            event.accept()
            return

        modifiers = self._event_modifiers(event)

        if key in self._special_map:
            key_name = self._special_map[key]
        else:
            key_name = event.text().lower()
            if not key_name or not key_name.isprintable():
                key_name = None

        if key_name:
            parts = modifiers + [key_name]
            self._captured = parts
            self._pending_mods = []
            self.setText(" + ".join(parts))
            self.setChecked(False)
        event.accept()

    def keyReleaseEvent(self, event) -> None:
        if not self.isChecked() or event.isAutoRepeat():
            super().keyReleaseEvent(event)
            return
        # Only modifiers were pressed: finalize a modifier-only shortcut as the
        # user begins releasing them.
        if self._pending_mods:
            self._captured = list(self._pending_mods)
            self._pending_mods = []
            self.setText(" + ".join(self._captured))
            self.setChecked(False)
        event.accept()

    def get_shortcut(self) -> str:
        return "+".join(self._captured)

    def set_shortcut(self, shortcut_str: str) -> None:
        self._captured = [p.strip() for p in shortcut_str.split("+")]
        self.setText(" + ".join(self._captured))


class SettingsDialog(QDialog):
    """Dialog for configuring WhyType settings and managing models."""

    download_finished = Signal(str, bool, str)
    download_progress = Signal(str, int)

    def __init__(
        self,
        config: Config,
        parent: Optional[QWidget] = None,
        accel_status: str = "",
    ) -> None:
        super().__init__(parent)
        self.config = config
        self._accel_status = accel_status
        self.setWindowTitle("Why Type - Settings")
        self.setMinimumWidth(480)
        self._installed_radios: dict[str, QRadioButton] = {}
        self._no_models_label: Optional[QLabel] = None
        # Queued so the slots always run on the GUI thread, even though the
        # signals are emitted from the download worker thread.
        self.download_finished.connect(self._on_download_finished, Qt.ConnectionType.QueuedConnection)
        self.download_progress.connect(self._on_download_progress, Qt.ConnectionType.QueuedConnection)
        self._build_ui()
        self._load_config()
        logger.info(
            "Settings opened; %d models available to download",
            self.available_combo.count(),
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Shortcut
        shortcut_layout = QFormLayout()
        self.shortcut_btn = ShortcutButton()
        shortcut_layout.addRow("Shortcut:", self.shortcut_btn)
        layout.addLayout(shortcut_layout)

        # Recording mode
        mode_layout = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.hold_radio = QRadioButton("Hold")
        self.toggle_radio = QRadioButton("Toggle")
        self.mode_group.addButton(self.hold_radio)
        self.mode_group.addButton(self.toggle_radio)
        mode_layout.addWidget(self.hold_radio)
        mode_layout.addWidget(self.toggle_radio)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Microphone
        mic_group = QGroupBox("Microphone")
        mic_layout = QVBoxLayout(mic_group)
        self.default_mic_check = QCheckBox("Use default microphone")
        self.default_mic_check.setChecked(True)
        self.default_mic_check.toggled.connect(self._on_default_mic_toggled)
        mic_layout.addWidget(self.default_mic_check)
        self.mic_combo = QComboBox()
        for name in list_input_devices():
            self.mic_combo.addItem(name, name)
        mic_layout.addWidget(self.mic_combo)
        layout.addWidget(mic_group)

        # Acceleration (CPU / GPU)
        accel_group = QGroupBox("Acceleration")
        accel_layout = QVBoxLayout(accel_group)
        accel_radios = QHBoxLayout()
        self.device_group = QButtonGroup(self)
        self.device_auto_radio = QRadioButton("Automatic")
        self.device_gpu_radio = QRadioButton("GPU")
        self.device_cpu_radio = QRadioButton("CPU")
        for r in (self.device_auto_radio, self.device_gpu_radio, self.device_cpu_radio):
            self.device_group.addButton(r)
            accel_radios.addWidget(r)
        accel_radios.addStretch()
        accel_layout.addLayout(accel_radios)
        if self._accel_status:
            status = QLabel(f"Currently using: {self._accel_status}")
            status.setStyleSheet("color: gray;")
            accel_layout.addWidget(status)
        hint = QLabel(
            "Automatic uses your GPU when available and falls back to CPU. "
            "GPU works across NVIDIA, AMD, Intel (incl. integrated) and Apple Silicon."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        accel_layout.addWidget(hint)
        layout.addWidget(accel_group)

        layout.addSpacing(10)

        # Installed Models
        installed_group = QGroupBox("Installed Models")
        installed_layout = QVBoxLayout(installed_group)
        self.installed_group_box = installed_group

        self.model_radio_group = QButtonGroup(self)

        downloaded = [name for name in MODEL_REGISTRY if is_model_downloaded(name)]
        if downloaded:
            for name in downloaded:
                meta = MODEL_REGISTRY[name]
                radio = QRadioButton(
                    f"{meta['display']}  ({meta['size']} - {meta['speed']}, {meta['accuracy']} accuracy)"
                )
                radio.setProperty("model_name", name)
                self.model_radio_group.addButton(radio)
                self._installed_radios[name] = radio
                installed_layout.addWidget(radio)
        else:
            self._no_models_label = QLabel(
                "No models installed. Download one below or use a custom model."
            )
            self._no_models_label.setWordWrap(True)
            self._no_models_label.setStyleSheet("color: gray; font-style: italic;")
            installed_layout.addWidget(self._no_models_label)

        # Custom model
        self.custom_radio = QRadioButton("Custom model")
        self.model_radio_group.addButton(self.custom_radio)
        custom_hbox = QHBoxLayout()
        self.custom_path_edit = QLineEdit()
        self.custom_path_edit.setPlaceholderText("Path to GGML .bin model file")
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_model)
        custom_hbox.addWidget(self.custom_path_edit)
        custom_hbox.addWidget(self.browse_btn)
        installed_layout.addWidget(self.custom_radio)
        installed_layout.addLayout(custom_hbox)

        layout.addWidget(installed_group)

        # Available Models — a dropdown + one top-level Download button.
        # (Per-row buttons inside a scroll area did not receive mouse events on
        # Windows; this mirrors the Save button, which works reliably.)
        available_group = QGroupBox("Available Models")
        available_layout = QVBoxLayout(available_group)

        combo_row = QHBoxLayout()
        self.available_combo = QComboBox()
        self._populate_available_combo()
        self.download_btn = QPushButton("Download")
        self.download_btn.setMinimumHeight(28)
        self.download_btn.clicked.connect(self._on_download_clicked)
        combo_row.addWidget(self.available_combo, stretch=1)
        combo_row.addWidget(self.download_btn)
        available_layout.addLayout(combo_row)

        self.download_status = QLabel("")
        self.download_status.setWordWrap(True)
        self.download_status.setStyleSheet("color: gray;")
        available_layout.addWidget(self.download_status)

        layout.addWidget(available_group)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _browse_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Custom Model",
            "",
            "GGML model files (*.bin);;All files (*)",
        )
        if path:
            self.custom_path_edit.setText(path)
            self.custom_radio.setChecked(True)

    def _on_default_mic_toggled(self, checked: bool) -> None:
        # Gray out the device dropdown when "use default" is checked.
        self.mic_combo.setEnabled(not checked)

    def _populate_available_combo(self) -> None:
        """Fill the dropdown with models that are not yet downloaded."""
        self.available_combo.clear()
        for name, meta in MODEL_REGISTRY.items():
            if not is_model_downloaded(name):
                label = (
                    f"{meta['display']} — {meta['size']}, "
                    f"{meta['speed']}, {meta['accuracy']} accuracy"
                )
                self.available_combo.addItem(label, name)

    def _on_download_clicked(self) -> None:
        name = self.available_combo.currentData()
        logger.info("Download button clicked; selected model=%r", name)
        if name:
            self._download_model(str(name))
        else:
            self.download_status.setText("No model selected to download.")

    def _download_model(self, name: str) -> None:
        logger.info("Downloading model: %s", name)
        self.download_btn.setEnabled(False)
        self.available_combo.setEnabled(False)
        self.download_status.setText(f"Starting download of {MODEL_REGISTRY[name]['display']}…")

        def do_download() -> None:
            last_pct = [-1]

            def on_progress(done: int, total: int) -> None:
                if total > 0:
                    pct = int(done * 100 / total)
                    if pct != last_pct[0]:
                        last_pct[0] = pct
                        self.download_progress.emit(name, pct)

            try:
                path = download_model(name, progress=on_progress)
                logger.info("Download complete for %s -> %s", name, path)
                self.download_finished.emit(name, True, "")
            except Exception as e:
                logger.exception("Download failed for %s", name)
                self.download_finished.emit(name, False, str(e))

        threading.Thread(target=do_download, daemon=True).start()

    def _on_download_progress(self, name: str, pct: int) -> None:
        self.download_status.setText(
            f"Downloading {MODEL_REGISTRY[name]['display']}… {pct}%"
        )

    def _on_download_finished(self, name: str, success: bool, error: str) -> None:
        logger.info("Download finished for %s: success=%s error=%s", name, success, error)
        self.download_btn.setEnabled(True)
        self.available_combo.setEnabled(True)
        if success:
            self.download_status.setText(f"{MODEL_REGISTRY[name]['display']} downloaded ✓")

            # Add to Installed list and select it.
            meta = MODEL_REGISTRY[name]
            radio = QRadioButton(
                f"{meta['display']}  ({meta['size']} - {meta['speed']}, {meta['accuracy']} accuracy)"
            )
            radio.setProperty("model_name", name)
            self.model_radio_group.addButton(radio)
            self._installed_radios[name] = radio

            if self._no_models_label:
                self._no_models_label.deleteLater()
                self._no_models_label = None

            installed_layout = self.installed_group_box.layout()
            custom_idx = -1
            for i in range(installed_layout.count()):
                if installed_layout.itemAt(i).widget() == self.custom_radio:
                    custom_idx = i
                    break
            if custom_idx >= 0:
                installed_layout.insertWidget(custom_idx, radio)
            else:
                installed_layout.addWidget(radio)
            radio.setChecked(True)

            # Remove the just-downloaded model from the dropdown deterministically.
            idx = self.available_combo.findData(name)
            if idx >= 0:
                self.available_combo.removeItem(idx)
        else:
            self.download_status.setText("")
            QMessageBox.critical(
                self, "Download Failed", f"Failed to download {name}:\n{error}"
            )

    def _load_config(self) -> None:
        self.shortcut_btn.set_shortcut(self.config.shortcut)
        if self.config.recording_mode == "toggle":
            self.toggle_radio.setChecked(True)
        else:
            self.hold_radio.setChecked(True)

        device = self.config.device
        if device == "gpu":
            self.device_gpu_radio.setChecked(True)
        elif device == "cpu":
            self.device_cpu_radio.setChecked(True)
        else:
            self.device_auto_radio.setChecked(True)

        # Microphone: "" means use the OS default.
        configured_mic = self.config.input_device
        if configured_mic:
            idx = self.mic_combo.findData(configured_mic)
            if idx < 0:
                # Saved device isn't currently present — add it so it's visible.
                self.mic_combo.addItem(f"{configured_mic} (not connected)", configured_mic)
                idx = self.mic_combo.findData(configured_mic)
            self.mic_combo.setCurrentIndex(idx)
            self.default_mic_check.setChecked(False)
        else:
            self.default_mic_check.setChecked(True)
        self.mic_combo.setEnabled(not self.default_mic_check.isChecked())

        current_model = self.config.model
        current_custom = self.config.custom_model_path

        if current_custom:
            self.custom_path_edit.setText(current_custom)
            self.custom_radio.setChecked(True)
        elif current_model in self._installed_radios:
            self._installed_radios[current_model].setChecked(True)
        elif self._installed_radios:
            list(self._installed_radios.values())[0].setChecked(True)
        else:
            self.custom_radio.setChecked(True)

    def _save(self) -> None:
        shortcut = self.shortcut_btn.get_shortcut()
        if not shortcut:
            QMessageBox.warning(
                self, "Invalid Shortcut", "Please set a keyboard shortcut."
            )
            return

        self.config.shortcut = shortcut
        self.config.recording_mode = "toggle" if self.toggle_radio.isChecked() else "hold"
        if self.device_gpu_radio.isChecked():
            self.config.device = "gpu"
        elif self.device_cpu_radio.isChecked():
            self.config.device = "cpu"
        else:
            self.config.device = "auto"

        if self.default_mic_check.isChecked():
            self.config.input_device = ""
        else:
            self.config.input_device = self.mic_combo.currentData() or ""

        selected_model = ""
        custom_path = self.custom_path_edit.text().strip()

        if self.custom_radio.isChecked():
            if not custom_path:
                QMessageBox.warning(
                    self,
                    "No Model Selected",
                    "Please enter a custom model path or select a downloaded model.",
                )
                return
            self.config.model = ""
            self.config.custom_model_path = custom_path
        else:
            for name, radio in self._installed_radios.items():
                if radio.isChecked():
                    selected_model = name
                    break
            if not selected_model:
                QMessageBox.warning(
                    self,
                    "No Model Selected",
                    "Please download and select a model, or specify a custom model path.",
                )
                return
            self.config.model = selected_model
            self.config.custom_model_path = ""

        self.config.save()
        self.accept()

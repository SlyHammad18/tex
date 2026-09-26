from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tex import config
from tex.constants import PROVIDERS
from tex.ocr import engine_items, make_engine
from tex.ui import theme


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.cfg = config.load_config()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)

        # --- API Keys section ---
        api_frame = QFrame()
        api_frame.setObjectName("settingsSection")
        api_lay = QVBoxLayout(api_frame)
        api_lay.setContentsMargins(12, 12, 12, 12)
        api_lay.setSpacing(4)

        api_title = QLabel("API Keys")
        api_title.setObjectName("settingsSectionTitle")
        api_lay.addWidget(api_title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setContentsMargins(0, 8, 0, 0)

        self.key_edits: dict[str, QLineEdit] = {}
        for pid, meta in PROVIDERS.items():
            row = QHBoxLayout()
            edit = QLineEdit()
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.setPlaceholderText(f"paste {meta['label']} API key")
            edit.setText(config.get_key(pid) or "")
            toggle = QCheckBox("show")
            toggle.toggled.connect(
                lambda on, e=edit: e.setEchoMode(
                    QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
                )
            )
            row.addWidget(edit, 1)
            row.addWidget(toggle)
            wrap = QWidget()
            wrap.setLayout(row)
            form.addRow(meta["label"], wrap)
            self.key_edits[pid] = edit

        api_lay.addLayout(form)
        lay.addWidget(api_frame)

        # --- Defaults section ---
        def_frame = QFrame()
        def_frame.setObjectName("settingsSection")
        def_lay = QVBoxLayout(def_frame)
        def_lay.setContentsMargins(12, 12, 12, 12)
        def_lay.setSpacing(4)

        def_title = QLabel("Defaults")
        def_title.setObjectName("settingsSectionTitle")
        def_lay.addWidget(def_title)

        def_form = QFormLayout()
        def_form.setSpacing(10)
        def_form.setContentsMargins(0, 8, 0, 0)

        self.engine_combo = QComboBox()
        for eid, elabel in engine_items():
            self.engine_combo.addItem(elabel, eid)
        self.engine_combo.setCurrentIndex(
            max(0, self.engine_combo.findData(self.cfg["general"].get("engine", "tesseract")))
        )
        def_form.addRow("Default engine", self.engine_combo)

        self.lang_combo = QComboBox()
        try:
            for m in make_engine("tesseract").list_models():
                self.lang_combo.addItem(m.label, m.id)
        except Exception:
            pass
        cur = self.cfg["tesseract"].get("language", "eng")
        idx = self.lang_combo.findData(f"tesseract:{cur}")
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        def_form.addRow("Tesseract language", self.lang_combo)

        def_lay.addLayout(def_form)
        lay.addWidget(def_frame)

        lay.addStretch()

        self._orig_keys = {pid: e.text() for pid, e in self.key_edits.items()}

        row = QHBoxLayout()
        row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setProperty("variant", "primary")
        save_btn.clicked.connect(self._save)
        row.addWidget(cancel_btn)
        row.addWidget(save_btn)
        lay.addLayout(row)

    def _save(self) -> None:
        for pid, edit in self.key_edits.items():
            if edit.text() != self._orig_keys[pid]:
                config.set_key(pid, edit.text())
        self.cfg["general"]["engine"] = self.engine_combo.currentData()
        if self.lang_combo.currentData():
            self.cfg["tesseract"]["language"] = self.lang_combo.currentData().split(":", 1)[1]
        config.save_config(self.cfg)
        self.accept()

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
        self.setMinimumWidth(460)
        self.cfg = config.load_config()

        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

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
            link = QLabel(f"<a href='{meta['key_url']}'>get key</a>")
            link.setOpenExternalLinks(True)
            link.setStyleSheet(f"color: {theme.MUTED}; background: transparent;")
            row.addWidget(edit, 1)
            row.addWidget(toggle)
            row.addWidget(link)
            wrap = QWidget()
            wrap.setLayout(row)
            form.addRow(meta["label"], wrap)
            self.key_edits[pid] = edit

        self.engine_combo = QComboBox()
        for eid, elabel in engine_items():
            self.engine_combo.addItem(elabel, eid)
        self.engine_combo.setCurrentIndex(
            max(0, self.engine_combo.findData(self.cfg["general"].get("engine", "tesseract")))
        )
        form.addRow("Default engine", self.engine_combo)

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
        form.addRow("Tesseract language", self.lang_combo)

        lay.addLayout(form)
        self._orig_keys = {pid: e.text() for pid, e in self.key_edits.items()}

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _save(self) -> None:
        for pid, edit in self.key_edits.items():
            if edit.text() != self._orig_keys[pid]:
                config.set_key(pid, edit.text())
        self.cfg["general"]["engine"] = self.engine_combo.currentData()
        if self.lang_combo.currentData():
            self.cfg["tesseract"]["language"] = self.lang_combo.currentData().split(":", 1)[1]
        config.save_config(self.cfg)
        self.accept()

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tex.ocr.models import ModelInfo, OcrResult, short_model
from tex.ui import theme
from tex.ui.toasts import show_toast


def _mono() -> QFont:
    f = QFont()
    f.setFamilies(["JetBrains Mono", "DejaVu Sans Mono", "Liberation Mono", "monospace"])
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f


class _ModelPage(QWidget):
    def __init__(self, model: ModelInfo, on_copy, parent=None):
        super().__init__(parent)
        self.model = model
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        top = QHBoxLayout()
        self.status = QLabel("Waiting…")
        self.status.setStyleSheet(f"color: {theme.MUTED}; font-size: 9pt;")
        top.addWidget(self.status)
        top.addStretch()
        btn = QPushButton("Copy")
        btn.clicked.connect(lambda: on_copy(self.model.id))
        top.addWidget(btn)
        lay.addLayout(top)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setFont(_mono())
        self.text.setPlaceholderText("Waiting…")
        lay.addWidget(self.text)

    def set_result(self, result: OcrResult) -> None:
        if result.error:
            self.status.setText(f"✗ {result.error[:140]}")
            self.status.setStyleSheet(f"color: {theme.ERR}; font-size: 9pt;")
            self.text.setPlainText(result.error)
        else:
            secs = result.latency_ms / 1000
            tokens = result.usage.get("total_tokens") or result.usage.get("completion_tokens") or ""
            extra = f" · {tokens} tok" if tokens != "" else ""
            self.status.setText(f"✓ {secs:.1f}s{extra}")
            self.status.setStyleSheet(f"color: {theme.OK}; font-size: 9pt;")
            self.text.setPlainText(result.text)


class CompareView(QWidget):
    def __init__(self, models: list[ModelInfo], parent=None):
        super().__init__(parent)
        self.models = models
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        lay.addWidget(self.tabs)

        self.pages: dict[str, _ModelPage] = {}
        seen: dict[str, int] = {}
        for m in models:
            base = short_model(m.id)
            n = seen.get(base, 0)
            seen[base] = n + 1
            title = base if n == 0 else f"{base} ·{n + 1}"
            page = _ModelPage(m, self._copy_one)
            self.pages[m.id] = page
            self.tabs.addTab(page, title)
        self.all_text = QPlainTextEdit()
        self.all_text.setReadOnly(True)
        self.all_text.setFont(_mono())
        self.all_text.setPlaceholderText("Results will appear here as they finish…")
        self.tabs.addTab(self.all_text, "All")

    def _copy_one(self, model_id: str) -> None:
        page = self.pages.get(model_id)
        if page is None:
            return
        QApplication.clipboard().setText(page.text.toPlainText())
        show_toast(self.window(), "Copied", "success")

    def set_result(self, result: OcrResult) -> None:
        page = self.pages.get(result.model)
        if page is None:
            return
        page.set_result(result)
        idx = self.tabs.indexOf(page)
        name = short_model(result.model)
        if result.error:
            self.tabs.setTabText(idx, f"✗ {name}")
        else:
            self.tabs.setTabText(idx, f"✓ {name} · {result.latency_ms / 1000:.1f}s")
        self._rebuild_all()

    def _rebuild_all(self) -> None:
        chunks = []
        for m in self.models:
            page = self.pages[m.id]
            body = page.text.toPlainText().strip() or "(pending…)"
            chunks.append(f"===== {short_model(m.id)} =====\n{body}")
        self.all_text.setPlainText("\n\n".join(chunks))

    def combined_text(self) -> str:
        good = []
        for m in self.models:
            page = self.pages[m.id]
            body = page.text.toPlainText().strip()
            if body and body != page.text.placeholderText():
                good.append(body)
        return "\n\n".join(good)

from __future__ import annotations

import datetime as _dt

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from tex import config
from tex.capture.base import CaptureMode, CaptureResult
from tex.constants import DEFAULT_PROMPT
from tex.ocr import engine_items, make_engine
from tex.ocr.base import OcrError
from tex.ocr.models import ModelInfo, OcrResult
from tex.ui.compare_view import CompareView, _mono
from tex.ui.icons import pil_to_pixmap
from tex.ui.toasts import show_toast


class ResultPanel(QWidget):
    backRequested = Signal()
    recropRequested = Signal()
    extractionFinished = Signal(str)
    extractionFailed = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._image = None
        self._base_pix = None
        self._capture: CaptureResult | None = None
        self._history_id: str | None = None
        self._model_cache: dict[str, list[ModelInfo]] = {}
        self._pending = 0
        self._running_compare = False
        self._auto_pick = False
        self._auto_spec: dict | None = None
        self._cancelled = False
        self._filling_models = False
        self.last_engine = ""
        self.last_model_label = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        bar = QHBoxLayout()
        self.engine_combo = QComboBox()
        for eid, elabel in engine_items():
            if eid == "tesseract" and not make_engine("tesseract").available():
                continue
            self.engine_combo.addItem(elabel, eid)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(230)
        self.compare_check = QCheckBox("Compare")
        self.custom_check = QCheckBox("Custom prompt")
        self.extract_btn = QPushButton("Extract")
        self.extract_btn.setProperty("variant", "primary")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setVisible(False)
        bar.addWidget(QLabel("Engine"))
        bar.addWidget(self.engine_combo)
        bar.addWidget(QLabel("Model"))
        bar.addWidget(self.model_combo, 1)
        bar.addWidget(self.compare_check)
        bar.addWidget(self.custom_check)
        bar.addWidget(self.extract_btn)
        bar.addWidget(self.cancel_btn)
        lay.addLayout(bar)

        list_row = QHBoxLayout()
        list_row.addWidget(QLabel("Models"))
        self.model_list = QListWidget()
        self.model_list.setFixedHeight(110)
        self.model_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        list_row.addWidget(self.model_list, 1)
        self.model_list_host = QWidget()
        self.model_list_host.setLayout(list_row)
        self.model_list_host.setVisible(False)
        lay.addWidget(self.model_list_host)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText(DEFAULT_PROMPT)
        self.prompt_edit.setMaximumHeight(84)
        self.prompt_edit.setVisible(False)
        lay.addWidget(self.prompt_edit)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.preview = QLabel()
        self.preview.setObjectName("imagePreview")
        self.preview.setMinimumSize(240, 200)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        split.addWidget(self.preview)

        self.right_stack = QStackedWidget()
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(_mono())
        self.text_edit.setPlaceholderText("Extracted text will appear here…")
        self.right_stack.addWidget(self.text_edit)
        self._compare_view = None
        split.addWidget(self.right_stack)
        split.setSizes([380, 460])
        lay.addWidget(split, 1)

        tools = QHBoxLayout()
        copy_btn = QPushButton("Copy")
        save_btn = QPushButton("Save .txt")
        recrop_btn = QPushButton("Re-crop")
        back_btn = QPushButton("Back")
        copy_btn.clicked.connect(self.copy_text)
        save_btn.clicked.connect(self.save_txt)
        recrop_btn.clicked.connect(self.recropRequested.emit)
        back_btn.clicked.connect(self.backRequested.emit)
        tools.addWidget(copy_btn)
        tools.addWidget(save_btn)
        tools.addWidget(recrop_btn)
        tools.addStretch()
        tools.addWidget(back_btn)
        lay.addLayout(tools)

        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        self.engine_combo.activated.connect(self._persist_engine)
        self.model_combo.activated.connect(self._persist_model)
        self.model_list.itemChanged.connect(self._persist_compare_models)
        self.compare_check.toggled.connect(self._on_compare_toggled)
        self.custom_check.toggled.connect(self.prompt_edit.setVisible)
        self.extract_btn.clicked.connect(self._on_extract_clicked)
        self.cancel_btn.clicked.connect(self.cancel_extraction)
        self.controller.models_ready.connect(self._on_models_ready)
        self.controller.models_failed.connect(self._on_models_failed)
        self.controller.result_ready.connect(self._on_result)
        self.controller.all_done.connect(self._on_all_done)
        self._apply_default_engine()

    def _apply_default_engine(self) -> None:
        name = config.load_config()["general"].get("engine", "tesseract")
        idx = self.engine_combo.findData(name)
        self.engine_combo.blockSignals(True)
        if idx >= 0:
            self.engine_combo.setCurrentIndex(idx)
        self.engine_combo.blockSignals(False)
        self._on_engine_changed()

    def _persist_engine(self, *_):
        name = self.engine_combo.currentData()
        if not name:
            return
        cfg = config.load_config()
        cfg["general"]["engine"] = name
        config.save_config(cfg)

    def _persist_model(self, *_):
        mid = self.model_combo.currentData()
        engine = self.engine_combo.currentData()
        if not mid or not engine:
            return
        cfg = config.load_config()
        cfg["providers"].setdefault(engine, {})["model"] = mid
        config.save_config(cfg)

    def _persist_compare_models(self, *_):
        if self._filling_models:
            return
        engine = self.engine_combo.currentData()
        if not engine:
            return
        cfg = config.load_config()
        cfg["providers"].setdefault(engine, {})["models"] = self._checked_model_ids()
        config.save_config(cfg)

    # ---------- capture / history ----------

    def set_capture(self, capture: CaptureResult, history_id: str | None = None) -> None:
        self._capture = capture
        self._image = capture.image
        self._history_id = history_id
        self._set_preview()
        QTimer.singleShot(0, self._rescale_preview)
        self.text_edit.clear()
        self.last_engine = ""
        self.last_model_label = ""
        self._set_compare_view(None)
        self._set_running(False)

    def show_history(self, entry: dict, image) -> None:
        mode = entry.get("mode") or "select"
        try:
            mode = CaptureMode(mode)
        except ValueError:
            mode = CaptureMode.SELECT
        self.set_capture(CaptureResult(image=image, mode=mode), entry.get("id"))
        if entry.get("text"):
            self.text_edit.setPlainText(entry["text"])
        if entry.get("engine"):
            idx = self.engine_combo.findData(entry["engine"])
            if idx >= 0:
                self.engine_combo.setCurrentIndex(idx)

    def _set_preview(self) -> None:
        if self._image is None:
            self.preview.clear()
            self._base_pix = None
            return
        self._base_pix = pil_to_pixmap(self._image)
        self._rescale_preview()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._rescale_preview()

    def _rescale_preview(self) -> None:
        if self._base_pix is None or self._base_pix.isNull():
            return
        size = self.preview.size()
        if size.width() <= 1 or size.height() <= 1:
            return
        scaled = self._base_pix.scaled(
            int(size.width() * 0.96),
            int(size.height() * 0.96),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(scaled)

    # ---------- models ----------

    def _on_engine_changed(self, *_):
        name = self.engine_combo.currentData()
        if not name:
            return
        self.model_combo.clear()
        self.model_list.clear()
        cached = self._model_cache.get(name)
        if cached is not None:
            self._fill_models(name, cached)
            return
        self.model_combo.addItem("Loading models…", "")
        self.controller.list_models(make_engine(name))

    def _fill_models(self, engine_name: str, models: list[ModelInfo]) -> None:
        self._filling_models = True
        try:
            self.model_combo.clear()
            self.model_list.clear()
            cfg = config.load_config()["providers"].get(engine_name, {})
            preferred = cfg.get("model", "")
            saved_models = cfg.get("models", [])
            checked: set[str] = set(saved_models) if saved_models else (
                {preferred} if preferred else set()
            )
            for m in models:
                self.model_combo.addItem(m.label or m.id, m.id)
                item = QListWidgetItem(m.label or m.id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if m.id in checked else Qt.CheckState.Unchecked
                )
                item.setData(Qt.ItemDataRole.UserRole, m.id)
                self.model_list.addItem(item)
            if not models:
                self.model_combo.addItem("(no vision models found)", "")
            else:
                sel = self.model_combo.findData(preferred)
                self.model_combo.setCurrentIndex(sel if sel >= 0 else 0)
            if self._auto_pick:
                self._auto_pick = False
                spec = self._auto_spec
                self._auto_spec = None
                if models and spec:
                    self.start_extraction(
                        engine_name=spec.get("engine"),
                        model_ids=[self.model_combo.currentData() or models[0].id],
                        prompt=spec.get("prompt"),
                        compare=bool(spec.get("compare")),
                    )
        finally:
            self._filling_models = False

    def _on_models_ready(self, engine_name: str, models: list) -> None:
        if engine_name != self.engine_combo.currentData():
            return
        self._model_cache[engine_name] = models
        self._fill_models(engine_name, models)

    def _on_models_failed(self, engine_name: str, error: str) -> None:
        if engine_name != self.engine_combo.currentData():
            return
        self.model_combo.clear()
        self.model_combo.addItem("No models", "")
        show_toast(self.window(), error, "error")

    # ---------- extraction ----------

    def _checked_model_ids(self) -> list[str]:
        return [
            self.model_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.model_list.count())
            if self.model_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _on_extract_clicked(self) -> None:
        compare = self.compare_check.isChecked()
        self.start_extraction(
            model_ids=self._checked_model_ids() if compare else None,
            compare=compare,
        )

    def start_extraction(
        self,
        engine_name: str | None = None,
        model_ids: list[str] | None = None,
        prompt: str | None = None,
        compare: bool = False,
    ) -> None:
        if self._image is None:
            return
        name = engine_name or self.engine_combo.currentData()
        engine = make_engine(name)
        prompt = (
            prompt
            or (self.prompt_edit.toPlainText().strip() if self.custom_check.isChecked() else "")
            or DEFAULT_PROMPT
        )
        if model_ids is None:
            if compare:
                model_ids = self._checked_model_ids()
                if not model_ids:
                    show_toast(self.window(), "Select at least one model to compare", "error")
                    return
            else:
                model_ids = [self.model_combo.currentData()]
                if not model_ids or not model_ids[0]:
                    show_toast(self.window(), "No model selected", "error")
                    return
        if name != "tesseract" and not engine.available():
            show_toast(
                self.window(),
                f"No API key set for {engine.label} (Settings > API keys)",
                "error",
            )
            self.extractionFailed.emit()
            return

        self.last_engine = name
        self.last_model_label = ", ".join(model_ids)
        self._cancelled = False
        self._running_compare = compare and len(model_ids) > 1
        self._pending = len(model_ids)
        if self._running_compare:
            infos = [m for m in self._model_cache.get(name, []) if m.id in model_ids]
            if not infos:
                infos = [ModelInfo(mid, name, mid) for mid in model_ids]
            self._set_compare_view(infos)
        else:
            self._set_compare_view(None)
            self.text_edit.clear()
        self._set_running(True)
        self.controller.extract(engine, self._image, model_ids, prompt)

    def run_auto(self, spec: dict) -> None:
        name = spec.get("engine")
        if name:
            idx = self.engine_combo.findData(name)
            if idx < 0:
                show_toast(self.window(), f"Unknown engine: {name}", "error")
                return
            self.engine_combo.setCurrentIndex(idx)
        self.compare_check.setChecked(bool(spec.get("compare")))
        if spec.get("prompt"):
            self.custom_check.setChecked(True)
            self.prompt_edit.setPlainText(spec["prompt"])
        if spec.get("models"):
            self.start_extraction(
                engine_name=spec.get("engine") or name,
                model_ids=list(spec["models"]),
                prompt=spec.get("prompt"),
                compare=bool(spec.get("compare")),
            )
        else:
            self._auto_pick = True
            self._auto_spec = spec
            self._on_engine_changed()

    def cancel_extraction(self) -> None:
        self.controller.cancel()
        self._cancelled = True
        self._pending = 0
        self._set_running(False)
        show_toast(self.window(), "Extraction canceled")

    def _on_result(self, result: OcrResult) -> None:
        if self._running_compare and self._compare_view is not None:
            self._compare_view.set_result(result)
        elif result.error:
            self.text_edit.setPlainText(result.error)
        else:
            self.text_edit.setPlainText(result.text)

    def _on_all_done(self) -> None:
        self._set_running(False)
        if self._cancelled:
            self._cancelled = False
            return
        if self._running_compare and self._compare_view is not None:
            text = self._compare_view.combined_text()
        else:
            text = self.text_edit.toPlainText().strip()
        if text:
            self.extractionFinished.emit(text)
            if self._history_id:
                from tex.ui.history import get_store

                get_store().update(
                    self._history_id,
                    self.last_engine,
                    self.last_model_label,
                    self.text_edit.toPlainText().strip() or text,
                )
        else:
            show_toast(self.window(), "No text extracted", "error")
            self.extractionFailed.emit()

    def _set_running(self, running: bool) -> None:
        self.extract_btn.setEnabled(not running)
        self.cancel_btn.setVisible(running)
        self.engine_combo.setEnabled(not running)

    def _set_compare_view(self, models: list[ModelInfo] | None) -> None:
        if self.right_stack.count() > 1:
            old = self.right_stack.widget(1)
            self.right_stack.removeWidget(old)
            old.deleteLater()
        self._compare_view = None
        if models is not None:
            self._compare_view = CompareView(models)
            self.right_stack.addWidget(self._compare_view)
            self.right_stack.setCurrentIndex(1)
        else:
            self.right_stack.setCurrentIndex(0)

    def _on_compare_toggled(self, on: bool) -> None:
        self.model_combo.setVisible(not on)
        self.model_list_host.setVisible(on)

    # ---------- actions ----------

    def _current_text(self) -> str:
        if self._compare_view is not None:
            return self._compare_view.all_text.toPlainText()
        return self.text_edit.toPlainText()

    def copy_text(self) -> None:
        text = self._current_text()
        if not text.strip():
            show_toast(self.window(), "Nothing to copy")
            return
        QApplication.clipboard().setText(text)
        show_toast(self.window(), "Copied to clipboard", "success")

    def save_txt(self) -> None:
        text = self._current_text()
        if not text.strip():
            show_toast(self.window(), "Nothing to save")
            return
        default = _dt.datetime.now().strftime("tex-%Y%m%d-%H%M%S.txt")
        path, _ = QFileDialog.getSaveFileName(self, "Save text", default, "Text files (*.txt)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        show_toast(self.window(), f"Saved {path}", "success")

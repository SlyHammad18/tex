from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from tex.capture import grab_raw, interactive_select, is_wayland
from tex.capture.base import CaptureCanceled, CaptureMode, CaptureResult, crop_image
from tex.ui import theme
from tex.ui.capture_overlay import CaptureOverlay
from tex.ui.history import get_store
from tex.ui.icons import render_icon
from tex.ui.result_panel import ResultPanel
from tex.ui.settings_dialog import SettingsDialog
from tex.ui.toasts import show_toast
from tex.workers import ExtractionController


class CaptureController(QObject):
    captured = Signal(object)
    failed = Signal(str)
    canceled = Signal()

    def start(self, mode: CaptureMode, dpr: float) -> None:
        threading.Thread(target=self._work, args=(mode, dpr), daemon=True).start()

    def _work(self, mode: CaptureMode, dpr: float) -> None:
        try:
            if is_wayland() and mode == CaptureMode.SELECT:
                try:
                    img = interactive_select()
                    self.captured.emit(
                        CaptureResult(image=img, mode=mode, dpr=dpr, preselected=True)
                    )
                    return
                except CaptureCanceled:
                    self.canceled.emit()
                    return
                except Exception as e:
                    self.failed.emit(str(e))
                    return
            img, windows, origin = grab_raw()
            self.captured.emit(
                CaptureResult(image=img, mode=mode, windows=windows, origin=origin, dpr=dpr)
            )
        except CaptureCanceled:
            self.canceled.emit()
        except Exception as e:
            self.failed.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self, cfg: dict, args):
        super().__init__()
        self.setWindowTitle("Tex")
        self.resize(880, 580)
        self.setMinimumSize(720, 480)

        self._pending_auto: dict | None = self._spec_from_args(args)
        self._quit_after = bool(self._pending_auto and (self._pending_auto["clipboard"] or self._pending_auto["save"]))
        self._current_history_id: str | None = None
        self._overlay: CaptureOverlay | None = None

        self.extract_controller = ExtractionController(self)
        self.capture_controller = CaptureController(self)
        self.capture_controller.captured.connect(self._on_captured)
        self.capture_controller.canceled.connect(self._on_capture_canceled)
        self.capture_controller.failed.connect(self._on_capture_failed)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.stack.addWidget(self._build_home())
        self.result_panel = ResultPanel(self.extract_controller)
        self.result_panel.backRequested.connect(self._go_home)
        self.result_panel.recropRequested.connect(self._recrop)
        self.result_panel.extractionFinished.connect(self._on_extracted)
        self.stack.addWidget(self.result_panel)
        self.stack.setCurrentIndex(0)

        self._reload_history()

        if getattr(args, "mode", None):
            mode = CaptureMode(args.mode)
            QTimer.singleShot(0, lambda: self._start_capture(mode))

    # ---------- home page ----------

    def _build_home(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)

        header = QHBoxLayout()
        logo = QLabel("Tex")
        logo.setObjectName("logo")
        header.addWidget(logo)
        header.addStretch()
        shot_btn = QPushButton("Take screenshot")
        shot_btn.setIcon(render_icon("select", 16, theme.ACCENT))
        shot_btn.setToolTip("Capture a screen region (tex --select)")
        shot_btn.clicked.connect(lambda: self._start_capture(CaptureMode.SELECT))
        header.addWidget(shot_btn)
        header.addSpacing(8)
        gear = QToolButton()
        gear.setObjectName("iconBtn")
        gear.setIcon(render_icon("gear", 24))
        gear.setToolTip("Settings")
        gear.clicked.connect(self._open_settings)
        header.addWidget(gear)
        lay.addLayout(header)

        recent_row = QHBoxLayout()
        recent_label = QLabel("Recent")
        recent_label.setObjectName("muted")
        recent_row.addWidget(recent_label)
        recent_row.addStretch()
        clear_btn = QPushButton("Clear history")
        clear_btn.clicked.connect(self._clear_history)
        recent_row.addWidget(clear_btn)
        lay.addLayout(recent_row)

        self.history_list = QListWidget()
        self.history_list.itemActivated.connect(self._open_history)
        self.history_list.itemClicked.connect(self._open_history)
        lay.addWidget(self.history_list, 1)

        self.empty_state = QWidget()
        es_lay = QVBoxLayout(self.empty_state)
        es_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        es_title = QLabel("No captures yet")
        es_title.setObjectName("emptyTitle")
        es_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        es_sub = QLabel("Take a screenshot to get started")
        es_sub.setObjectName("emptySub")
        es_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        es_btn = QPushButton("Take screenshot")
        es_btn.setProperty("variant", "primary")
        es_btn.clicked.connect(lambda: self._start_capture(CaptureMode.SELECT))
        es_btn.setFixedHeight(36)
        es_lay.addWidget(es_title)
        es_lay.addWidget(es_sub)
        es_lay.addSpacing(8)
        es_lay.addWidget(es_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.empty_state, 1)

        return page

    def _clear_history(self) -> None:
        ret = QMessageBox.question(
            self,
            "Clear history",
            "Delete all captures and their results?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            get_store().clear()
            self._reload_history()

    def _reload_history(self) -> None:
        self.history_list.clear()
        store = get_store()
        entries = store.entries()
        for e in entries:
            item = QListWidgetItem()
            try:
                pix = QPixmap(e["image"])
                if not pix.isNull():
                    item.setIcon(
                        QIcon(
                            pix.scaled(
                                96,
                                54,
                                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        )
                    )
            except Exception:
                pass
            t = (e.get("ts") or "")[11:16] or "--:--"
            parts = [t, (e.get("mode") or "select").capitalize()]
            if e.get("model"):
                parts.append(e["model"])
            elif e.get("engine"):
                parts.append(e["engine"])
            item.setText("  ·  ".join(parts))
            item.setData(Qt.ItemDataRole.UserRole, e)
            self.history_list.addItem(item)

        has_items = len(entries) > 0
        self.history_list.setVisible(has_items)
        self.empty_state.setVisible(not has_items)

    def _open_history(self, item: QListWidgetItem) -> None:
        entry = item.data(Qt.ItemDataRole.UserRole)
        try:
            from PIL import Image

            image = Image.open(entry["image"]).convert("RGB")
        except Exception as e:
            show_toast(self, f"Could not open capture: {e}", "error")
            return
        self._current_history_id = entry.get("id")
        self.result_panel.show_history(entry, image)
        self.stack.setCurrentIndex(1)

    # ---------- capture flow ----------

    def _start_capture(self, mode: CaptureMode) -> None:
        dpr = QGuiApplication.primaryScreen().devicePixelRatio()
        self.hide()
        QTimer.singleShot(180, lambda: self.capture_controller.start(mode, dpr))

    def _on_captured(self, res: CaptureResult) -> None:
        if res.preselected or res.mode == CaptureMode.SCREEN:
            self._finish_capture(res.image, res.mode)
            return
        virtual = QGuiApplication.primaryScreen().virtualGeometry()
        if is_wayland():
            dpr = res.dpr or 1.0

            def origin_fn(g: QPoint, v=virtual, d=dpr) -> QPoint:
                return QPoint(int((g.x() - v.x()) * d), int((g.y() - v.y()) * d))

        else:
            ox, oy = res.origin

            def origin_fn(g: QPoint, ox=ox, oy=oy) -> QPoint:
                return QPoint(g.x() - ox, g.y() - oy)

        windows = []
        if res.mode == CaptureMode.WINDOW:
            windows = CaptureOverlay.window_rects(res.windows, res.origin)

        self._overlay = CaptureOverlay(
            res.image,
            windows,
            res.mode,
            origin_fn,
            parent=None,
        )
        self._overlay.accepted.connect(lambda rect, r=res: self._on_region_selected(r, rect))
        self._overlay.canceled.connect(self._on_capture_canceled)
        if is_wayland():
            screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
            self._overlay.setScreen(screen)
            self._overlay.setGeometry(screen.geometry())
            self._overlay.showFullScreen()
        else:
            self._overlay.setGeometry(virtual)
            self._overlay.showNormal()
            self._overlay.raise_()
            self._overlay.activateWindow()

    def _on_region_selected(self, res: CaptureResult, rect) -> None:
        try:
            image = crop_image(res.image, rect)
        except Exception as e:
            show_toast(self, f"Invalid selection: {e}", "error")
            self._go_home()
            return
        self._finish_capture(image, res.mode)

    def _finish_capture(self, image, mode: CaptureMode) -> None:
        self._current_history_id = get_store().add(image, mode)
        self.result_panel.set_capture(
            CaptureResult(image=image, mode=mode), self._current_history_id
        )
        self.stack.setCurrentIndex(1)
        self.show()
        self.raise_()
        self.activateWindow()
        if self._pending_auto:
            self.result_panel.run_auto(self._pending_auto)

    def _on_capture_canceled(self) -> None:
        self._go_home()

    def _on_capture_failed(self, msg: str) -> None:
        self.show()
        show_toast(self, msg, "error")

    def _go_home(self) -> None:
        self._reload_history()
        self.stack.setCurrentIndex(0)
        self.show()
        self.raise_()

    def _recrop(self) -> None:
        image = self.result_panel._image
        if image is None:
            return

        def on_selected(rect) -> None:
            try:
                cropped = crop_image(image, rect)
            except Exception as e:
                show_toast(self, f"Invalid selection: {e}", "error")
                return
            self.result_panel.set_capture(
                CaptureResult(image=cropped, mode=CaptureMode.SELECT),
                self._current_history_id,
            )
            self.stack.setCurrentIndex(1)
            self.show()

        virtual = QGuiApplication.primaryScreen().virtualGeometry()
        if is_wayland():
            dpr = QGuiApplication.primaryScreen().devicePixelRatio()

            def origin_fn(g: QPoint, v=virtual, d=dpr) -> QPoint:
                return QPoint(int((g.x() - v.x()) * d), int((g.y() - v.y()) * d))
        else:
            def origin_fn(g: QPoint) -> QPoint:
                return QPoint(g.x(), g.y())

        self._overlay = CaptureOverlay(image, [], CaptureMode.SELECT, origin_fn)
        self._overlay.accepted.connect(on_selected)
        self._overlay.canceled.connect(lambda: (self.show(), self.raise_()))
        if is_wayland():
            screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
            self._overlay.setScreen(screen)
            self._overlay.setGeometry(screen.geometry())
            self._overlay.showFullScreen()
        else:
            self._overlay.setGeometry(virtual)
            self._overlay.showNormal()
            self._overlay.raise_()
            self._overlay.activateWindow()
        self.hide()

    # ---------- extraction results / auto actions ----------

    def _on_extracted(self, text: str) -> None:
        spec = self._pending_auto
        if not spec:
            return
        self._pending_auto = None
        if spec.get("clipboard"):
            QGuiApplication.clipboard().setText(text)
            show_toast(self, "Copied to clipboard", "success")
        if spec.get("save"):
            try:
                with open(spec["save"], "w", encoding="utf-8") as f:
                    f.write(text)
                show_toast(self, f"Saved {spec['save']}", "success")
            except Exception as e:
                show_toast(self, f"Save failed: {e}", "error")
                return
        if self._quit_after:
            self.close()

    # ---------- misc ----------

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._reload_history()

    def handle_remote(self, payload: dict) -> None:
        mode = payload.get("mode")
        self._pending_auto = {
            "engine": payload.get("engine"),
            "models": [payload["model"]] if payload.get("model") else None,
            "prompt": payload.get("prompt"),
            "clipboard": bool(payload.get("clipboard")),
            "save": payload.get("save"),
        }
        self._quit_after = bool(
            self._pending_auto["clipboard"] or self._pending_auto["save"]
        )
        self.show()
        self.raise_()
        self.activateWindow()
        if mode:
            self._start_capture(CaptureMode(mode))

    @staticmethod
    def _spec_from_args(args) -> dict | None:
        if args is None:
            return None
        return {
            "engine": getattr(args, "engine", None),
            "models": [args.model] if getattr(args, "model", None) else None,
            "prompt": getattr(args, "prompt", None),
            "clipboard": bool(getattr(args, "clipboard", False)),
            "save": getattr(args, "save", None),
        }

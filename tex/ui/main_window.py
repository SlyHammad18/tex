from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
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
                except Exception:
                    pass
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

        self.statusBar().showMessage("Ready")
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
        subtitle = QLabel("Screenshot + text extraction")
        subtitle.setObjectName("muted")
        header.addSpacing(6)
        header.addWidget(subtitle)
        header.addStretch()
        gear = QToolButton()
        gear.setObjectName("iconBtn")
        gear.setIcon(render_icon("gear", 24))
        gear.setToolTip("Settings")
        gear.clicked.connect(self._open_settings)
        header.addWidget(gear)
        lay.addLayout(header)

        cards = QHBoxLayout()
        cards.addStretch()
        for mode, icon in (
            (CaptureMode.SELECT, "select"),
            (CaptureMode.WINDOW, "window"),
            (CaptureMode.SCREEN, "screen"),
        ):
            btn = QToolButton()
            btn.setObjectName("modeCard")
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setIcon(render_icon(icon, 64, theme.ACCENT))
            btn.setIconSize(QSize(40, 40))
            btn.setText(mode.label)
            btn.clicked.connect(lambda _, m=mode: self._start_capture(m))
            cards.addWidget(btn)
        cards.addStretch()
        lay.addLayout(cards)

        recent_label = QLabel("Recent")
        recent_label.setObjectName("muted")
        lay.addWidget(recent_label)
        self.history_list = QListWidget()
        self.history_list.itemActivated.connect(self._open_history)
        self.history_list.itemClicked.connect(self._open_history)
        lay.addWidget(self.history_list, 1)
        return page

    def _reload_history(self) -> None:
        self.history_list.clear()
        store = get_store()
        for e in store.entries():
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
        self.statusBar().showMessage("Capturing…")
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
        self.statusBar().showMessage(f"{mode.label} captured — choose engine and Extract")
        if self._pending_auto:
            self.result_panel.run_auto(self._pending_auto)

    def _on_capture_canceled(self) -> None:
        self._go_home()

    def _on_capture_failed(self, msg: str) -> None:
        self.show()
        self.statusBar().showMessage("Capture failed")
        show_toast(self, msg, "error")

    def _go_home(self) -> None:
        self._reload_history()
        self.stack.setCurrentIndex(0)
        self.show()
        self.raise_()
        self.statusBar().showMessage("Ready")

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
            self.statusBar().showMessage("Settings saved")
            self._reload_history()

    def handle_remote(self, payload: dict) -> None:
        mode = payload.get("mode")
        self._pending_auto = {
            "engine": payload.get("engine"),
            "models": (
                [m.strip() for m in payload["compare"].split(",") if m.strip()]
                if payload.get("compare")
                else ([payload["model"]] if payload.get("model") else None)
            ),
            "prompt": payload.get("prompt"),
            "compare": bool(payload.get("compare") and "," in payload["compare"]),
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
        compare_models = None
        if getattr(args, "compare", None):
            compare_models = [m.strip() for m in args.compare.split(",") if m.strip()]
        models = compare_models or ([args.model] if getattr(args, "model", None) else None)
        return {
            "engine": getattr(args, "engine", None),
            "models": models,
            "prompt": getattr(args, "prompt", None),
            "compare": bool(compare_models and len(compare_models) > 1),
            "clipboard": bool(getattr(args, "clipboard", False)),
            "save": getattr(args, "save", None),
        }

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from tex.ocr.base import OcrEngine, parse_number_groups, parse_translation
from tex.ocr.models import OcrResult


class _Signals(QObject):
    done = Signal(object)
    models = Signal(list)
    fail = Signal(str)


class ExtractJob(QRunnable):
    def __init__(self, engine: OcrEngine, image, model_id: str, prompt: str):
        super().__init__()
        self.engine = engine
        self.image = image
        self.model_id = model_id
        self.prompt = prompt
        self.signals = _Signals()

    def run(self):
        try:
            result = self.engine.extract(self.image, self.model_id, self.prompt)
        except Exception as e:
            result = OcrResult(model=self.model_id, provider=self.engine.name, error=str(e))
        try:
            self.signals.done.emit(result)
        except RuntimeError:
            pass


class ModelsJob(QRunnable):
    def __init__(self, engine: OcrEngine):
        super().__init__()
        self.engine = engine
        self.signals = _Signals()

    def run(self):
        try:
            models = self.engine.list_models()
        except Exception as e:
            self._emit("fail", str(e))
        else:
            self._emit("models", models)

    def _emit(self, name, value):
        try:
            getattr(self.signals, name).emit(value)
        except RuntimeError:
            pass


class GroupJob(QRunnable):
    def __init__(self, engine: OcrEngine, text: str, model_id: str):
        super().__init__()
        self.engine = engine
        self.text = text
        self.model_id = model_id
        self.signals = _Signals()

    def run(self):
        try:
            groups = parse_number_groups(self.engine.group_text(self.text, self.model_id))
        except Exception as e:
            self._emit("fail", str(e))
        else:
            self._emit("done", groups)

    def _emit(self, name, value):
        try:
            getattr(self.signals, name).emit(value)
        except RuntimeError:
            pass


class TranslateJob(QRunnable):
    def __init__(self, engine: OcrEngine, text: str, model_id: str):
        super().__init__()
        self.engine = engine
        self.text = text
        self.model_id = model_id
        self.signals = _Signals()

    def run(self):
        try:
            lang, translated = parse_translation(self.engine.translate_text(self.text, self.model_id))
        except Exception as e:
            self._emit("fail", str(e))
        else:
            self._emit("done", (lang, translated))

    def _emit(self, name, value):
        try:
            getattr(self.signals, name).emit(value)
        except RuntimeError:
            pass


class ExtractionController(QObject):
    result_ready = Signal(object)
    models_ready = Signal(str, list)
    models_failed = Signal(str, str)
    all_done = Signal()
    groups_ready = Signal(str, list)
    groups_failed = Signal(str, str)
    translation_ready = Signal(str, object)
    translation_failed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._cancelled = False
        self._pending = 0
        self._jobs = set()

    def _track(self, job: QRunnable, *done_signals) -> None:
        job.setAutoDelete(False)
        self._jobs.add(job)
        for sig in done_signals:
            sig.connect(lambda *_, j=job: self._jobs.discard(j))

    def list_models(self, engine: OcrEngine):
        job = ModelsJob(engine)
        name = engine.name
        self._track(job, job.signals.models, job.signals.fail)
        job.signals.models.connect(lambda models, n=name: self.models_ready.emit(n, models))
        job.signals.fail.connect(lambda err, n=name: self.models_failed.emit(n, err))
        self._pool.start(job)

    def extract(self, engine: OcrEngine, image, model_ids: list[str], prompt: str):
        self._cancelled = False
        self._pending = len(model_ids)
        for mid in model_ids:
            job = ExtractJob(engine, image, mid, prompt)
            self._track(job, job.signals.done)
            job.signals.done.connect(self._on_done)
            self._pool.start(job)

    def _on_done(self, result: OcrResult):
        if self._cancelled:
            return
        self._pending = max(0, self._pending - 1)
        self.result_ready.emit(result)
        if self._pending == 0:
            self.all_done.emit()

    def group_numbers(self, engine: OcrEngine, text: str, model_id: str) -> None:
        job = GroupJob(engine, text, model_id)
        name = engine.name
        self._track(job, job.signals.done, job.signals.fail)
        job.signals.done.connect(lambda groups, n=name: self.groups_ready.emit(n, groups))
        job.signals.fail.connect(lambda err, n=name: self.groups_failed.emit(n, err))
        self._pool.start(job)

    def translate_text(self, engine: OcrEngine, text: str, model_id: str) -> None:
        job = TranslateJob(engine, text, model_id)
        name = engine.name
        self._track(job, job.signals.done, job.signals.fail)
        job.signals.done.connect(lambda res, n=name: self.translation_ready.emit(n, res))
        job.signals.fail.connect(lambda err, n=name: self.translation_failed.emit(n, err))
        self._pool.start(job)

    def cancel(self):
        self._cancelled = True
        self._pending = 0
        self.all_done.emit()

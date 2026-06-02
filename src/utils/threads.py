from PyQt6.QtCore import QRunnable, pyqtSignal, QObject
import logging

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(Exception)
    result = pyqtSignal(object)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        fname = getattr(self.fn, "__name__", str(self.fn))
        logger.debug("Worker %s started with args=%s kwargs=%s", fname, self.args, self.kwargs)
        try:
            result = self.fn(*self.args, **self.kwargs)
            logger.debug("Worker %s produced result: %s", fname, result)
            self.signals.result.emit(result)
        except Exception as e:
            logger.exception("Worker %s raised exception", fname)
            self.signals.error.emit(e)
        finally:
            logger.debug("Worker %s finished", fname)
            self.signals.finished.emit()

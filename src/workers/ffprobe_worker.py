import subprocess
import traceback
import logging
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject


logger = logging.getLogger(__name__)


class FfprobeWorkerSignals(QObject):
	result = pyqtSignal(str, str, str)
	error = pyqtSignal(str, str)


class FfprobeWorker(QRunnable):
	def __init__(self, filepath, mode, cmd, timeout=120):
		super().__init__()
		self.filepath = filepath
		self.mode = mode
		self.cmd = cmd
		self.timeout = timeout
		self.signals = FfprobeWorkerSignals()

	def run(self):
		try:
			r = subprocess.run(
				self.cmd,
				capture_output=True, text=True, timeout=self.timeout
			)
			self.signals.result.emit(self.mode, r.stdout, r.stderr)
		except Exception as e:
			self.signals.error.emit(self.mode, str(e))
			logger.exception("FfprobeWorker error for mode %s", self.mode)
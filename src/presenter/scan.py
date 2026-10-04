import os
import logging
from ..worker import AnalysisWorker, ScanWorker


logger = logging.getLogger(__name__)


class ScanMixin:
	def handle_scan(self):
		folder = self.folder_evidence
		if not folder or not os.path.exists(folder):
			logger.error("Folder not found: %s", folder)
			return

		logger.info("Scan started")
		
		worker = ScanWorker(folder)
		worker.signals.result.connect(self._on_scan_finished)
		worker.signals.error.connect(self.on_analysis_error)
		self.threadpool.start(worker)

	def _on_scan_finished(self, files):
		logger.info("Scan completed: %d files found", len(files))
		for f in files:
			path = os.path.join(self.folder_evidence, f)
			worker = AnalysisWorker(self.model, path, case_id=self.model.current_case_id)
			worker.signals.result.connect(self.on_analysis_finished)
			worker.signals.error.connect(self.on_analysis_error)
			self.threadpool.start(worker)

	def on_analysis_finished(self, data):
		logger.info("Analysis completed: %s", data['file_name'])
		self.refresh_ui_list()

	def on_analysis_error(self, error_msg):
		logger.error("Thread error: %s", error_msg)
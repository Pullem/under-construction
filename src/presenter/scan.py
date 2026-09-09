import os
from ..worker import AnalysisWorker, ScanWorker


class ScanMixin:
	def handle_scan(self):
		folder = self.folder_evidence
		if not folder or not os.path.exists(folder):
			print(f"FEHLER: Ordner {folder} nicht gefunden.")
			return

		print(f"Scan gestartet...")
		
		worker = ScanWorker(folder)
		worker.signals.result.connect(self._on_scan_finished)
		worker.signals.error.connect(self.on_analysis_error)
		self.threadpool.start(worker)

	def _on_scan_finished(self, files):
		print(f"Scan abgeschlossen: {len(files)} Dateien gefunden.")
		for f in files:
			path = os.path.join(self.folder_evidence, f)
			worker = AnalysisWorker(self.model, path)
			worker.signals.result.connect(self.on_analysis_finished)
			worker.signals.error.connect(self.on_analysis_error)
			self.threadpool.start(worker)

	def on_analysis_finished(self, data):
		print(f"Analyse abgeschlossen: {data['file_name']}")
		self.refresh_ui_list()

	def on_analysis_error(self, error_msg):
		print(f"THREAD-FEHLER: {error_msg}")

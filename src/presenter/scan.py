import os
from ..worker import AnalysisWorker


class ScanMixin:
	def handle_scan(self):
		folder = self.folder_evidence
		if not os.path.exists(folder):
			print(f"FEHLER: Ordner {folder} nicht gefunden.")
			return

		files = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.jpg', '.png'))]
		print(f"Scan gestartet... {len(files)} Dateien gefunden.")

		for f in files:
			path = os.path.join(folder, f)
			worker = AnalysisWorker(self.model, path)
			worker.signals.result.connect(self.on_analysis_finished)
			worker.signals.error.connect(self.on_analysis_error)
			self.threadpool.start(worker)

	def on_analysis_finished(self, data):
		print(f"Analyse abgeschlossen: {data['file_name']}")
		self.refresh_ui_list()

	def on_analysis_error(self, error_msg):
		print(f"THREAD-FEHLER: {error_msg}")

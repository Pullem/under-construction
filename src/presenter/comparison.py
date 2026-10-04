import json
import logging
from PyQt6.QtWidgets import QMenu
from ..worker import DbWorker
from ..compare_window import ComparisonWindow


logger = logging.getLogger(__name__)


class ComparisonMixin:
	def show_context_menu(self, position):
		item = self.view.file_list.itemAt(position)
		if not item:
			return

		menu = QMenu()
		add_action = menu.addAction(f"'{item.text()}' zum Vergleich hinzufügen")
		open_action = menu.addAction("Vergleichs-Fenster öffnen")
		clear_action = menu.addAction("Vergleichs-Liste leeren")

		action = menu.exec(self.view.file_list.mapToGlobal(position))

		if action == add_action:
			self.add_to_comparison(item.text())
		elif action == open_action:
			self.open_comparison_view()
		elif action == clear_action:
			self.comparison_data.clear()
			logger.info("Comparison list cleared")

	def add_to_comparison(self, file_name):
		def _query(model):
			conn = model.get_connection()
			if not conn:
				return None
			try:
				cur = conn.cursor(dictionary=True)
				cur.execute("SELECT metadata, exif_metadata FROM media_files WHERE file_name = ?", (file_name,))
				return cur.fetchone()
			finally:
				conn.close()

		def _on_result(row):
			if row:
				data = json.loads(row['metadata'])
				if row['exif_metadata']:
					data["EXIF"] = json.loads(row['exif_metadata'])

				self.comparison_data[file_name] = data
				logger.info("Added '%s' to comparison (%d files in list)", file_name, len(self.comparison_data))

		worker = DbWorker(self.model, _query)
		worker.signals.result.connect(_on_result)
		worker.signals.error.connect(lambda e: logger.error("Failed to add to comparison: %s", e))
		self.threadpool.start(worker)

	def open_comparison_view(self):
		if not self.comparison_data:
			logger.warning("No files selected for comparison!")
			return

		self.comparison_window = ComparisonWindow(self.comparison_data)
		self.comparison_window.show()
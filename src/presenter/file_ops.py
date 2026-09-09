import json
from ..worker import DbWorker


class FileOpsMixin:
	def refresh_ui_list(self):
		def _query(model):
			conn = model.get_connection()
			if not conn:
				return []
			try:
				cur = conn.cursor()
				case_id = model.current_case_id
				if case_id:
					cur.execute("SELECT file_name FROM media_files WHERE case_id = ? ORDER BY created_at DESC", (case_id,))
				else:
					cur.execute("SELECT file_name FROM media_files ORDER BY created_at DESC")
				files = [r[0] for r in cur.fetchall()]
				return files
			finally:
				conn.close()
		
		worker = DbWorker(self.model, _query)
		worker.signals.result.connect(self.view.update_file_list)
		worker.signals.error.connect(lambda e: print(f"UI-Refresh fehlgeschlagen: {e}"))
		self.threadpool.start(worker)

	def load_file_details(self, file_name):
		if not file_name:
			return

		self._last_selected_file = file_name

		# ffmpeg-Tab: Datei vorbefüllen
		if hasattr(self.view, 'set_ffmpeg_file') and self._last_selected_file:
			self._load_file_path_for_ffmpeg(file_name)

		target_tab = self.last_tab_focus

		def _query(model):
			conn = model.get_connection()
			if not conn:
				return None
			try:
				cur = conn.cursor(dictionary=True)
				cur.execute("SELECT metadata, exif_metadata, file_path FROM media_files WHERE file_name = ?", (file_name,))
				return cur.fetchone()
			finally:
				conn.close()

		def _on_result(row):
			if not row:
				return
			mi_data = self._parse_json_column(row.get('metadata'))
			exif_data = self._parse_json_column(row.get('exif_metadata'))
			if exif_data:
				mi_data["EXIF Deep Dive"] = exif_data

			self.view.tabs.blockSignals(True)
			self.view.display_metadata(mi_data)
			self.view.set_active_tab_by_name(target_tab)
			self.view.tabs.blockSignals(False)

			self.view.set_thumbnail(row['file_path'])

		worker = DbWorker(self.model, _query)
		worker.signals.result.connect(_on_result)
		worker.signals.error.connect(lambda e: print(f"Fehler beim Laden der Dateidetails: {e}"))
		self.threadpool.start(worker)

	def _load_file_path_for_ffmpeg(self, file_name):
		def _query(model):
			conn = model.get_connection()
			if not conn:
				return None
			try:
				cur = conn.cursor(dictionary=True)
				cur.execute("SELECT file_path FROM media_files WHERE file_name = ?", (file_name,))
				return cur.fetchone()
			finally:
				conn.close()

		def _on_result(row):
			if row and row.get('file_path'):
				self.view.set_ffmpeg_file(row['file_path'])

		worker = DbWorker(self.model, _query)
		worker.signals.result.connect(_on_result)
		self.threadpool.start(worker)

	def handle_search(self, query):
		self.view.apply_row_filter(query)

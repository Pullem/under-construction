import json


class FileOpsMixin:
	def refresh_ui_list(self):
		conn = self.model.get_connection()
		if not conn:
			return

		try:
			cur = conn.cursor()
			case_id = self.model.current_case_id
			if case_id:
				cur.execute("SELECT file_name FROM media_files WHERE case_id = ? ORDER BY created_at DESC", (case_id,))
			else:
				cur.execute("SELECT file_name FROM media_files ORDER BY created_at DESC")
			files = [r[0] for r in cur.fetchall()]
			conn.close()
			self.view.update_file_list(files)
		except Exception as e:
			print(f"UI-Refresh fehlgeschlagen: {e}")

	def load_file_details(self, file_name):
		if not file_name:
			return

		self._last_selected_file = file_name

		# ffmpeg-Tab: Datei vorbefüllen
		if hasattr(self.view, 'set_ffmpeg_file') and self._last_selected_file:
			conn = self.model.get_connection()
			if conn:
				try:
					cur = conn.cursor(dictionary=True)
					cur.execute("SELECT file_path FROM media_files WHERE file_name = ?", (file_name,))
					row = cur.fetchone()
					conn.close()
					if row:
						self.view.set_ffmpeg_file(row['file_path'])
				except Exception as e:
					print(f"Fehler in set_ffmpeg_file: {e}")
					conn.close()

		target_tab = self.last_tab_focus

		try:
			conn = self.model.get_connection()
			cur = conn.cursor(dictionary=True)
			cur.execute("SELECT metadata, exif_metadata, file_path FROM media_files WHERE file_name = ?", (file_name,))
			row = cur.fetchone()
			conn.close()

			if row:
				mi_data = self._parse_json_column(row.get('metadata'))
				exif_data = self._parse_json_column(row.get('exif_metadata'))
				if exif_data:
					mi_data["EXIF Deep Dive"] = exif_data

				self.view.tabs.blockSignals(True)
				self.view.display_metadata(mi_data)
				self.view.set_active_tab_by_name(target_tab)
				self.view.tabs.blockSignals(False)

				self.view.set_thumbnail(row['file_path'])
		except Exception as e:
			print(f"Fehler beim Laden der Dateidetails: {e}")
			if hasattr(self.view, 'tabs'):
				self.view.tabs.blockSignals(False)

	def handle_search(self, query):
		self.view.apply_row_filter(query)

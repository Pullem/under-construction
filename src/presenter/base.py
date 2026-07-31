import json
import os
import time
from PyQt6.QtCore import QThreadPool, Qt


def _guess_is_video(filename):
	name = filename.lower()
	return name.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm", ".mts"))

def _guess_is_foto(filename):
	name = filename.lower()
	return name.endswith((".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"))

def _guess_media_type(filename):
	if _guess_is_foto(filename):
		return "Foto"
	if _guess_is_video(filename):
		return "Video"
	return "Sonstige"


class PresenterBase:
	def __init__(self, model, view, **kwargs):
		super().__init__(**kwargs)
		self.model = model
		self.view = view
		self.threadpool = QThreadPool()

		self.view.scan_requested.connect(self.handle_scan)
		self.view.search_changed.connect(self.handle_search)
		self.view.file_selected.connect(self.load_file_details)
		self.view.tabs.currentChanged.connect(self.track_tab_change)
		self.view.nav_bar.currentChanged.connect(self.handle_nav_tab_change)

		self.view.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
		self.view.file_list.customContextMenuRequested.connect(self.show_context_menu)

		if hasattr(self.view, "import_media_requested"):
			self.view.import_media_requested.connect(self.open_import_dialog)

		if hasattr(self.view, "case_selected"):
			self.view.case_selected.connect(self.handle_case_selected)

		if hasattr(self.view, "create_case_requested"):
			self.view.create_case_requested.connect(self.handle_create_case)

		if hasattr(self.view, "save_settings_requested"):
			self.view.save_settings_requested.connect(self.handle_save_settings)

		if hasattr(self.view, "update_db_password_requested"):
			self.view.update_db_password_requested.connect(self.handle_update_db_password)

		if hasattr(self.view, "open_timeline_requested"):
			self.view.open_timeline_requested.connect(self.handle_open_timeline)

		if hasattr(self.view, "ffmpeg_run_requested"):
			self.view.ffmpeg_run_requested.connect(self.handle_ffmpeg_run)
		if hasattr(self.view, "ffmpeg_abort_requested"):
			self.view.ffmpeg_abort_requested.connect(self.handle_ffmpeg_abort)

		if hasattr(self.view, "ffmpeg_lossless_trim_requested"):
			self.view.ffmpeg_lossless_trim_requested.connect(self.handle_lossless_trim)

		if hasattr(self.view, "ffprobe_analyse_requested"):
			self.view.ffprobe_analyse_requested.connect(self.handle_ffprobe_analyse)

		if hasattr(self.view, "sensitivity_requested"):
			self.view.sensitivity_requested.connect(self.handle_sensitivity_changed)

		self._refresh_settings()

		self._last_selected_file = None
		self._thumbnail_generation = 0
		self._thumb_worker_running = False
		self._thumb_worker_case_id = None
		self._last_timeline_offset = 0
		self._last_timeline_zoom = 100
		self._last_chunk_refresh = 0.0
		self.case_path = model.current_case_path
		if self.case_path:
			self._init_case_paths()
			self.view.set_case_path(str(self.case_path))
			case_name = self.model.current_case.get("project_name", "Unbekannter Fall")
			self.view.setWindowTitle(f"Forensic Analyzer – {case_name}")
			self.view.set_case_name(case_name)
		else:
			_none = None
			self.folder_evidence = _none
			self.folder_analyze = _none
			self.folder_exports = _none
			self.folder_reports = _none
			self.folder_thumbnails = _none
			self.folder_recovered = _none
			self.folder_logs = _none
			self.view.setWindowTitle("Video Forensic Lab - Analyzer")

		self.last_tab_focus = "General"
		self.comparison_data = {}
		self.comparison_window = None

		print(f"System bereit. {self.threadpool.maxThreadCount()} Threads verfügbar.")
		self.refresh_ui_list()
		self.refresh_case_list()

	@staticmethod
	def _parse_json_column(value):
		if not value:
			return {}
		if isinstance(value, dict):
			return value
		return json.loads(value)

	def handle_nav_tab_change(self, index):
		if not self.case_path and index not in (0, 7):
			from PyQt6.QtWidgets import QMessageBox
			QMessageBox.warning(
				self.view,
				"Kein Fall aktiv",
				"Bitte wählen Sie zuerst einen Fall aus oder legen Sie einen neuen Fall an (Tab „Fallübersicht“)."
			)
			self.view.nav_bar.blockSignals(True)
			self.view.nav_bar.setCurrentIndex(0)
			self.view.nav_bar.blockSignals(False)
			self.view.content_stack.setCurrentIndex(0)

	def track_tab_change(self, index):
		name = self.view.get_active_tab_name()
		if name:
			self.last_tab_focus = name

	def _init_case_paths(self):
		self.case_path = self.model.current_case_path
		if self.case_path:
			self.model.ensure_case_folders(self.case_path)
			self.folder_evidence = self.case_path / "evidence_input"
			self.folder_analyze = self.case_path / "analyze_media"
			self.folder_exports = self.case_path / "exports"
			self.folder_reports = self.case_path / "reports"
			self.folder_thumbnails = self.case_path / "thumbnails"
			self.folder_recovered = self.case_path / "recovered"
			self.folder_logs = self.case_path / "logs"

	def handle_case_selected(self, case_id):
		case = self.model.load_case(case_id)
		if case:
			self._init_case_paths()
			self.view.set_case_path(str(self.case_path))
			case_name = case.get("project_name", "Unbekannter Fall")
			self.view.setWindowTitle(f"Forensic Analyzer – {case_name}")
			self.view.set_case_name(case_name)
			self.view.clear_metadata_display()
			self.refresh_ui_list()
			self.handle_open_timeline()

	def handle_create_case(self, name, desc, incident_at, incident_until=None):
		try:
			existing = self.model.load_cases()
			if any(c["project_name"] == name for c in existing):
				from PyQt6.QtWidgets import QMessageBox
				QMessageBox.warning(self.view, "Fehler", f"Ein Fall mit dem Namen „{name}“ existiert bereits.")
				return
			case_id = self.model.create_case(name, desc, incident_at, incident_until)
			self._init_case_paths()
			self.view.set_case_path(str(self.case_path))
			self.view.set_case_name(name)
			self.view.setWindowTitle(f"Forensic Analyzer – {name}")
			self.refresh_ui_list()
			self.refresh_case_list()
			self.handle_open_timeline()
		except Exception as e:
			print(f"Fehler beim Erstellen des Falls: {e}")

	def _refresh_settings(self):
		db_user = self.model.db_config.get("user", "—")
		db_password = self.model.db_config.get("password", "")
		case_root = self.model.proj_config.get("settings", "case_root", fallback="")
		root_password = getattr(self.model, "root_password", "")
		if hasattr(self.view, "_refresh_settings_display"):
			self.view._refresh_settings_display(db_user, db_password, case_root, root_password)

	def handle_update_db_password(self, new_password):
		self.model.db_config["password"] = new_password
		self.model.save_db_config()
		self._refresh_settings()

	def handle_save_settings(self, case_root):
		from pathlib import Path
		self.model.proj_config["settings"]["case_root"] = str(Path(case_root).resolve())
		self.model.save_project_config()
		self._refresh_settings()
		from PyQt6.QtWidgets import QMessageBox
		QMessageBox.information(self.view, "Gespeichert", "Einstellungen wurden gespeichert.")

	def handle_open_timeline(self):
		if not self.model.current_case:
			from PyQt6.QtWidgets import QMessageBox
			QMessageBox.warning(self.view, "Kein Fall aktiv",
							   "Bitte wählen Sie zuerst einen Fall aus.")
			return
		media_files = []
		conn = self.model.get_connection()
		if conn:
			try:
				cur = conn.cursor(dictionary=True)
				cur.execute(
					"SELECT file_name, file_path, metadata, exif_metadata FROM media_files WHERE case_id = ?",
					(self.model.current_case_id,)
				)
				media_files = cur.fetchall() or []
			finally:
				conn.close()
		for f in media_files:
			for col in ("metadata", "exif_metadata"):
				if isinstance(f.get(col), str):
					try:
						f[col] = json.loads(f[col])
					except (json.JSONDecodeError, TypeError):
						f[col] = {}
		if hasattr(self.view, 'timeline_widget'):
			offset = 0
			if hasattr(self.view, 'cbo_offset'):
				offset = self.view.cbo_offset.currentData() or 0
			zoom = 100
			if hasattr(self.view, 'slider_zoom'):
				zoom = self.view.slider_zoom.value()

			# Zuerst Timeline ohne Thumbnails anzeigen (schnell)
			for f in media_files:
				f["_thumbnails"] = []
				f["_duration_sec"] = 0
			self.view.timeline_widget.refresh(media_files, self.model.current_case,
											 offset_hours=offset, zoom_pct=zoom)

			self._last_timeline_offset = offset
			self._last_timeline_zoom = zoom

			# Thumbnails asynchron im Worker-Thread extrahieren
			thumb_dir = self.model.current_case_path / "thumbnails" if self.model.current_case_path else None
			if thumb_dir and media_files:
				case_id = self.model.current_case_id
				if self._thumb_worker_running and self._thumb_worker_case_id == case_id:
					print("[Timeline] ThumbnailWorker läuft bereits – überspringe Start.")
				else:
					from ..worker import ThumbnailWorker
					self._thumbnail_generation += 1
					gen = self._thumbnail_generation
					self._thumb_worker_running = True
					self._thumb_worker_case_id = case_id
					worker = ThumbnailWorker(self.model, media_files, thumb_dir)
					worker.signals.chunk.connect(
						lambda result, g=gen: self._on_thumbnails_chunk(result, g))
					worker.signals.result.connect(
						lambda result, g=gen, o=offset, z=zoom: self._on_thumbnails_done(result, g, o, z))
					worker.signals.error.connect(
						lambda err, g=gen: self._on_thumbnail_error(err, g))
					QThreadPool.globalInstance().start(worker)

	def refresh_case_list(self):
		cases = self.model.load_cases()
		self.view.update_case_list(cases)

	def _on_thumbnails_chunk(self, media_files, gen):
		if gen != self._thumbnail_generation:
			return
		now = time.monotonic()
		if now - self._last_chunk_refresh < 0.5:
			return
		self._last_chunk_refresh = now
		if hasattr(self.view, 'timeline_widget'):
			self.view.timeline_widget.refresh(
				media_files, self.model.current_case,
				offset_hours=self._last_timeline_offset, zoom_pct=self._last_timeline_zoom)

	def _on_thumbnails_done(self, media_files, gen, offset, zoom):
		if gen != self._thumbnail_generation:
			return
		if self._thumb_worker_case_id != self.model.current_case_id:
			return
		self._thumb_worker_running = False
		if hasattr(self.view, 'timeline_widget'):
			self.view.timeline_widget.refresh(media_files, self.model.current_case,
											 offset_hours=offset, zoom_pct=zoom)

	def _on_thumbnail_error(self, err, gen):
		if gen != self._thumbnail_generation:
			return
		if self._thumb_worker_case_id != self.model.current_case_id:
			return
		self._thumb_worker_running = False
		print(f"[Timeline] Thumbnail-Fehler: {err}")

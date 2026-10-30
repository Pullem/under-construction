"""FFmpeg-/Analyse-Steuerung: Buttons, Signale, Dateiauswahl, Ergebnisse."""

import os
import json
import subprocess
import logging
from datetime import datetime, timedelta

from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QTime

from ..image_enhance_widget import ImageEnhanceWindow
from ..tabs import active_media_prefix


logger = logging.getLogger(__name__)
class FFmpegControlsMixin:
	"""Steuerung der FFmpeg-/Analyse-Buttons und Ergebnisanzeige."""

	def _on_plugin_btn_clicked(self, mode):
		if mode == "histogramm":
			self._open_enhance_window()
		else:
			prefix = active_media_prefix(self)
			result = getattr(self, f"{prefix}_result", None)
			if result:
				btn = getattr(self, f"{prefix}_pbtn_{mode}", None)
				name = btn.text() if btn else mode
				result.setPlainText(f"{name} – noch nicht implementiert")

	def _open_enhance_window(self):
		if not hasattr(self, "_enhance_window") or self._enhance_window is None:
			self._enhance_window = ImageEnhanceWindow()
		self._enhance_window.show_image(self.ffmpeg_input_path)

	def _on_ffmpeg_run(self):
		inp = self.ffmpeg_input_path
		if not inp:
			QMessageBox.warning(self, "Keine Datei", "Bitte zuerst eine Datei auswählen.")
			return

		prefix = active_media_prefix(self)
		w = lambda n: getattr(self, f"{prefix}_{n}")

		# Lossless Trim via TrimWidget (nur Videos)
		if prefix == "video":
			tw = getattr(self, "video_trim_widget", None)
			if tw and tw.isVisible():
				start_f = tw.get_start_frame()
				end_f = tw.get_end_frame()
				mode = tw.get_trim_mode()
				if end_f <= start_f:
					QMessageBox.warning(self, "Ungültiger Bereich",
										"Der Endframe muss größer als der Startframe sein.")
					return
				self.ffmpeg_lossless_trim_requested.emit(inp, start_f, end_f, mode)
				return

		if prefix == "video":
			start = w("start").time().toString("HH:mm:ss")
			end = w("end").time().toString("HH:mm:ss") if w("end").time() != QTime(0, 0) else ""
		else:
			start = "00:00:00"
			end = ""
		filter_str = w("filter").text().strip()
		fmt = w("format").currentData()

		# __REALTIME__ durch encoded_date + UTC-Offset ersetzen (nur Videos)
		if prefix == "video" and "__REALTIME__" in filter_str:
			encoded = w("encoded_label").text()
			utc_offset = w("utc_combo").currentData()
			realtime_plain = "00:00:00:00"
			if encoded != "–" and "T" in encoded:
				try:
					dt = datetime.fromisoformat(encoded.replace("Z", "+00:00"))
					dt += timedelta(hours=utc_offset)
					realtime_plain = dt.strftime("%H:%M:%S") + ":00"
				except Exception:
					pass
			realtime_val = realtime_plain.replace(":", "\\:")
			filter_str = filter_str.replace("__REALTIME__", realtime_val)

		if prefix == "video" and "__POSITION__" in filter_str:
			filter_str = filter_str.replace("__POSITION__", w("tc_pos").currentData())

		self.ffmpeg_run_requested.emit(inp, start + "|" + end + "|" + filter_str, fmt, prefix)

	def _on_ffmpeg_abort(self):
		self.ffmpeg_abort_requested.emit()

	def _on_ffmpeg_browse(self):
		from PyQt6.QtWidgets import QFileDialog
		prefix = active_media_prefix(self)
		if prefix == "video":
			filter_str = "Video (*.mp4 *.mov *.avi *.mkv *.webm *.mts)"
		else:
			filter_str = "Bild (*.jpg *.jpeg *.png *.tif *.tiff *.bmp)"
		path, _ = QFileDialog.getOpenFileName(
			self, "Mediendatei auswählen", self._case_path, filter_str
		)
		if path:
			self.set_ffmpeg_file(path)
			if prefix == "video":
				from ..trim_widget import TrimWidget
				if hasattr(self, "video_trim_widget"):
					self.video_trim_widget.load_file(path)

	def set_ffmpeg_file(self, path):
		self.ffmpeg_input_path = path
		for p in ("video", "bild"):
			fl = getattr(self, f"{p}_file_label", None)
			if fl:
				fl.setText(os.path.basename(path))
				fl.setToolTip(path)
			lg = getattr(self, f"{p}_log", None)
			if lg:
				lg.clear()
			pr = getattr(self, f"{p}_progress", None)
			if pr:
				pr.setValue(0)
		self._update_ffmpeg_encoded_date(path)
		try:
			self.set_hex_file(path)
		except Exception as e:
			logger.warning("set_hex_file failed: %s", e)
		try:
			if hasattr(self, "video_trim_widget"):
				self.video_trim_widget.load_file(path)
		except Exception as e:
			logger.warning("trim_widget.load_file failed: %s", e)
		try:
			if hasattr(self, "_enhance_window") and self._enhance_window.isVisible():
				self._enhance_window.load_image(path)
		except Exception as e:
			logger.warning("_enhance_window.load_image failed: %s", e)

	def _update_ffmpeg_encoded_date(self, path):
		label = None
		if hasattr(self, "video_encoded_label"):
			label = self.video_encoded_label
		if label is None:
			return
		try:
			from ...model.base import BASE_DIR
			r = subprocess.run(
				[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
				 "-show_entries", "format_tags=creation_time",
				 "-of", "csv=p=0", path],
				capture_output=True, text=True, timeout=15
			)
			out = r.stdout.strip()
			if out:
				label.setText(out)
				return
		except Exception as e:
			logger.warning("_update_ffmpeg_encoded_date ffprobe: %s", e)

		try:
			conn = self._get_db_connection()
			if conn:
				cur = conn.cursor(dictionary=True)
				cur.execute(
					"SELECT metadata FROM media_files WHERE file_path = ?",
					(path,)
				)
				row = cur.fetchone()
				conn.close()
				if row:
					md = json.loads(row['metadata'])
					gen = md.get("General", {})
					ct = gen.get("encoded_date") or gen.get("creation_date") or gen.get("file_creation_date_local", "")
					if ct:
						label.setText(ct)
						return
		except Exception as e:
			logger.warning("_update_ffmpeg_encoded_date db: %s", e)

		label.setText("–")

	def _get_db_connection(self):
		for cls in type(self).__mro__:
			if hasattr(cls, 'get_connection'):
				return cls.get_connection(self)
		return None

	def _on_ffprobe_analyse(self, mode):
		prefix = active_media_prefix(self)
		for attr_name in dir(self):
			if attr_name.startswith(f"{prefix}_btn_"):
				btn = getattr(self, attr_name)
				btn_m = attr_name[len(f"{prefix}_btn_"):]
				if btn_m == mode:
					btn.setStyleSheet(
						"QPushButton { background-color: #2e7d32; color: #ffffff; "
						"border: 1px solid #43a047; font-weight: bold; }"
					)
				else:
					btn.setStyleSheet("")
		path = self.ffmpeg_input_path
		if not path:
			QMessageBox.warning(self, "Keine Datei", "Bitte zuerst eine Datei auswählen.")
			return
		getattr(self, f"{prefix}_result").clear()
		self.ffprobe_analyse_requested.emit(path, mode, prefix)

	def _on_sensitivity_changed(self):
		prefix = active_media_prefix(self)
		path = self.ffmpeg_input_path
		if not path:
			return
		self.sensitivity_requested.emit(path, prefix)

	def show_analysis_result(self, prefix, mode, data):
		widget = getattr(self, f"{prefix}_tab_{mode}", None)
		if widget is None or data is None:
			return
		widget.show_result(data)

	def export_analysis_figures(self, prefix, mode, stem, exports_dir):
		widget = getattr(self, f"{prefix}_tab_{mode}", None)
		if widget is None:
			return "", ""
		return widget.export_analysis(stem, exports_dir)

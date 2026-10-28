import os
import json
import subprocess
import logging
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
							 QListWidget, QListWidgetItem, QLabel, QLineEdit,
							 QPushButton, QTabWidget, QTabBar, QTextEdit,
							 QStackedWidget, QMessageBox, QStyle, QStyleOptionTab,
							 QDateEdit, QTimeEdit, QCheckBox, QComboBox, QSlider,
						 QPlainTextEdit, QProgressBar, QGridLayout, QFileDialog,
						 QSpinBox)
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QRect, QDate, QTime, QDateTime
from PyQt6.QtGui import QPixmap, QPainter, QColor

from .hex_view import HexViewWidget
from .trim_widget import TrimWidget
from .image_enhance_widget import ImageEnhanceWindow
from .tab_builder import (build_case_tab, build_import_tab, build_metadata_tab,
	build_videos_tab, build_bilder_tab, build_settings_tab,
	build_hex_tab, build_analysis_tab, build_placeholder_tab,
	active_media_prefix)
from ..utils.gpu_config import get_gpu_config, check_cuda_available

# ---------------------------------------------------------
# CUSTOM TAB BAR (flaches Design, horizontale Schrift)
# ---------------------------------------------------------
class FlatTabBar(QTabBar):
	# Farbtokens der Navigation (dunkles Design)
	_BG = QColor("#1a1a1a")
	_BG_HOVER = QColor("#242424")
	_BG_SELECTED = QColor("#252526")
	_TEXT = QColor("#9a9a9a")
	_TEXT_HOVER = QColor("#dcdcdc")
	_TEXT_SELECTED = QColor("#ffffff")
	_ACCENT = QColor("#2d7dd2")
	_SEPARATOR = QColor("#2a2a2a")

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setDrawBase(False)
		self.setExpanding(True)
		self.setMouseTracking(True)
		self._hover_index = -1

	def tabSizeHint(self, index):
		s = super().tabSizeHint(index)
		return QSize(max(s.width() + 30, 180), 40)

	# Hover-Zustand nur visuell verfolgen (keine Funktionsänderung)
	def mouseMoveEvent(self, event):
		super().mouseMoveEvent(event)
		idx = self.tabAt(event.position().toPoint())
		if idx != self._hover_index:
			self._hover_index = idx
			self.update()

	def leaveEvent(self, event):
		self._hover_index = -1
		super().leaveEvent(event)

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)

		for idx in range(self.count()):
			opt = QStyleOptionTab()
			self.initStyleOption(opt, idx)
			rect = opt.rect
			selected = bool(opt.state & QStyle.StateFlag.State_Selected)
			hovered = (idx == self._hover_index and not selected)

			# Hintergrund je nach Zustand
			if selected:
				bg = self._BG_SELECTED
			elif hovered:
				bg = self._BG_HOVER
			else:
				bg = self._BG
			painter.save()
			painter.setPen(Qt.PenStyle.NoPen)
			painter.setBrush(bg)
			painter.drawRect(rect)

			# Feine Trennlinie zwischen den Einträgen
			painter.setPen(self._SEPARATOR)
			painter.drawLine(rect.bottomLeft(), rect.bottomRight())

			# Akzent-Balken links für den aktiven Eintrag
			if selected:
				painter.setPen(Qt.PenStyle.NoPen)
				painter.setBrush(self._ACCENT)
				painter.drawRoundedRect(
					QRect(rect.left() + 1, rect.top() + 8, 3, max(rect.height() - 16, 4)),
					1.5, 1.5)
			painter.restore()

			# Typografie: aktiver Eintrag fett und hell
			font = painter.font()
			font.setBold(selected)
			painter.setFont(font)
			if selected:
				painter.setPen(self._TEXT_SELECTED)
			elif hovered:
				painter.setPen(self._TEXT_HOVER)
			else:
				painter.setPen(self._TEXT)
			painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.tabText(idx))
			font.setBold(False)
			painter.setFont(font)


# ---------------------------------------------------------
# MAIN WINDOW MIXIN
# ---------------------------------------------------------
class MainWindowMixin(QMainWindow):
	scan_requested = pyqtSignal()
	search_changed = pyqtSignal(str)
	file_selected = pyqtSignal(str)
	import_media_requested = pyqtSignal()
	case_selected = pyqtSignal(object)
	create_case_requested = pyqtSignal(str, str, object, object)
	save_settings_requested = pyqtSignal(str)
	update_db_password_requested = pyqtSignal(str)
	open_timeline_requested = pyqtSignal()
	ffmpeg_run_requested = pyqtSignal(str, str, str, str)
	ffmpeg_abort_requested = pyqtSignal()
	ffprobe_analyse_requested = pyqtSignal(str, str, str)
	sensitivity_requested = pyqtSignal(str, str)
	ffmpeg_lossless_trim_requested = pyqtSignal(str, int, int, str)

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.setWindowTitle("Video Forensic Lab - Analyzer")
		self.resize(1920, 1080)
		self._raw_db_password = ""
		self._pw_visible = False
		self._raw_root_password = ""
		self._root_pw_visible = False
		self._is_analysis_built = False
		self._case_path = ""
		self.ffmpeg_input_path = ""

	def setup_ui(self):
		central = QWidget()
		self.setCentralWidget(central)
		main_layout = QHBoxLayout(central)
		main_layout.setContentsMargins(0, 0, 0, 0)
		main_layout.setSpacing(0)

		# --- LINKS: Navigations-Tabbar ---
		self.nav_bar = FlatTabBar()
		self.nav_bar.setShape(QTabBar.Shape.RoundedWest)
		self.nav_bar.setFixedWidth(200)

		# --- MITTE: Inhaltsbereich ---
		self.content_stack = QStackedWidget()

		# Tabs + Inhalt bauen
		build_case_tab(self)
		build_import_tab(self)
		build_metadata_tab(self)
		build_videos_tab(self)
		build_bilder_tab(self)
		build_hex_tab(self)
		build_analysis_tab(self)
		build_placeholder_tab(self, "Export")
		build_settings_tab(self)

		# Navigation verknüpfen
		self.nav_bar.currentChanged.connect(self.content_stack.setCurrentIndex)

		self._refresh_timezone()
		self._update_gpu_status()

		main_layout.addWidget(self.nav_bar)
		main_layout.addWidget(self.content_stack, 1)

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
				from .trim_widget import TrimWidget
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
			from ..model.base import BASE_DIR
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

	def _on_meta_search(self, query):
		if hasattr(self, "search_metadata_tables"):
			self.search_metadata_tables(query)

	def _refresh_settings_display(self, db_user, db_password, case_root, root_password=""):
		self.lbl_db_user.setText(db_user or "—")
		self._raw_db_password = db_password or ""
		self._pw_visible = False
		self._update_password_display()
		self._raw_root_password = root_password or ""
		self._root_pw_visible = False
		self._update_root_password_display()
		self.txt_case_root.setText(case_root or "")
		self.txt_new_db_password.clear()
		self._refresh_timezone()

	def _update_password_display(self):
		if self._raw_db_password:
			self.lbl_db_password.setText(self._raw_db_password if self._pw_visible else "••••••••")
		else:
			self.lbl_db_password.setText("—")
		self.btn_toggle_pw.setVisible(bool(self._raw_db_password))

	def _update_root_password_display(self):
		if self._raw_root_password:
			self.lbl_root_password.setText(self._raw_root_password if self._root_pw_visible else "••••••••")
		else:
			self.lbl_root_password.setText("—")

	def _toggle_root_pw_visible(self, checked):
		self._root_pw_visible = checked
		self._update_root_password_display()

	def _toggle_password_visible(self, checked):
		self._pw_visible = checked
		self._update_password_display()

	def _toggle_new_pw_visible(self, checked):
		self.txt_new_db_password.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)

	def _on_browse_case_root(self):
		from PyQt6.QtWidgets import QFileDialog
		folder = QFileDialog.getExistingDirectory(self, "Basisordner für Fälle auswählen")
		if folder:
			self.txt_case_root.setText(folder)

	def _on_save_settings(self):
		case_root = self.txt_case_root.text().strip()
		if not case_root:
			QMessageBox.warning(self, "Fehler", "Basisordner darf nicht leer sein.")
			return
		new_pw = self.txt_new_db_password.text().strip()
		if new_pw:
			self.update_db_password_requested.emit(new_pw)
		self.save_settings_requested.emit(case_root)

	def _on_hex_open(self):
		path, _ = QFileDialog.getOpenFileName(
			self, "Datei öffnen", "",
			"Alle Dateien (*.*)"
		)
		if path:
			self.set_hex_file(path)

	def _on_hex_goto(self):
		self.hex_viewer.goto_offset(self.hex_goto_input.text())

	def _on_hex_font_size(self, size):
		self.hex_viewer.set_font_size(size)

	def _on_hex_search(self):
		text = self.hex_search_input.text().strip()
		mode = self.hex_search_mode.currentData()
		self.hex_viewer.search(text, mode)

	def _on_hex_search_next(self):
		self.hex_viewer.search_next()

	def _on_hex_search_prev(self):
		self.hex_viewer.search_prev()

	def _on_hex_search_moved(self, index, total):
		if total > 0:
			self.hex_search_status.setText(f"{index}/{total}")
		else:
			self.hex_search_status.setText("")

	def set_hex_file(self, path):
		self.hex_viewer.set_file(path)
		self.hex_file_label.setText(path)
		self.hex_file_label.setToolTip(path)
		size = self.hex_viewer._file_size
		if size > 0:
			self.hex_status.setText(f"Datei: {path}  |  Größe: {size:,} Bytes  |  Zeilen: {self.hex_viewer._total_lines:,}")
		else:
			self.hex_status.setText("–")

	@staticmethod
	def _get_current_utc_offset():
		from datetime import datetime, timedelta
		now = datetime.now()
		mar = datetime(now.year, 3, 31)
		last_sun_mar = mar - timedelta(days=(mar.weekday() + 1) % 7)
		oct_ = datetime(now.year, 10, 31)
		last_sun_oct = oct_ - timedelta(days=(oct_.weekday() + 1) % 7)
		return 2 if last_sun_mar <= now < last_sun_oct else 1

	def _refresh_timezone(self):
		offset = self._get_current_utc_offset()
		name = "Sommerzeit UTC+2 (MESZ)" if offset == 2 else "Winterzeit UTC+1 (MEZ)"
		if hasattr(self, 'lbl_tz_info'):
			self.lbl_tz_info.setText(name)
		for combo_name in ('video_utc_combo', 'cbo_offset'):
			combo = getattr(self, combo_name, None)
			if combo:
				idx = combo.findData(offset)
				if idx >= 0:
					combo.setCurrentIndex(idx)

	def _update_gpu_status(self):
		"""Update GPU status label in settings tab."""
		if not hasattr(self, 'lbl_gpu_status'):
			return
		try:
			cuda_available, gpu_name = check_cuda_available()
			config = get_gpu_config()
			if cuda_available and config.enabled:
				vram_gb = config.max_vram_mb / 1024
				self.lbl_gpu_status.setText(
					f"✅ GPU aktiv: {gpu_name}\n"
					f"   Gerät: {config.device_index} | VRAM-Limit: {vram_gb:.1f} GB\n"
					f"   Decode: {config.decode_hwaccel.upper()} | Thumbnail HW: {'Ja' if config.thumbnail_hwaccel else 'Nein'}"
				)
				self.lbl_gpu_status.setStyleSheet(
					"background-color: #14311c; color: #7ddc7d; padding: 8px 10px; "
					"border: 1px solid #2e6b3f; border-radius: 4px;"
				)
			elif config.enabled and not cuda_available:
				self.lbl_gpu_status.setText(
					"⚠️ GPU konfiguriert, aber CUDA nicht verfügbar\n"
					"Fallback auf CPU-Berechnung"
				)
				self.lbl_gpu_status.setStyleSheet(
					"background-color: #3a3115; color: #ffd666; padding: 8px 10px; "
					"border: 1px solid #7a6a2a; border-radius: 4px;"
				)
			else:
				self.lbl_gpu_status.setText(
					"❌ GPU deaktiviert (config/gpu.ini: enabled=false)"
				)
				self.lbl_gpu_status.setStyleSheet(
					"background-color: #3a1c1c; color: #ff9a9a; padding: 8px 10px; "
					"border: 1px solid #7a3a3a; border-radius: 4px;"
				)
		except Exception as e:
			self.lbl_gpu_status.setText(f"❌ GPU-Status Fehler: {e}")
			self.lbl_gpu_status.setStyleSheet(
				"background-color: #3a1c1c; color: #ff9a9a; padding: 8px 10px; "
				"border: 1px solid #7a3a3a; border-radius: 4px;"
			)

	def _on_bis_toggled(self, checked):
		self.d_incident_until.setVisible(checked)
		self.t_incident_until.setVisible(checked)

	def _on_create_case(self):
		name = self.txt_case_name.text().strip()
		desc = self.txt_case_desc.toPlainText().strip()
		if not name:
			QMessageBox.warning(self, "Fehler", "Fallname darf nicht leer sein.")
			return
		incident_at = QDateTime(self.d_incident.date(), self.t_incident.time()).toPyDateTime()
		incident_until = QDateTime(self.d_incident_until.date(), self.t_incident_until.time()).toPyDateTime() if self.chk_bis.isChecked() else None
		if incident_until and incident_until < incident_at:
			QMessageBox.warning(self, "Fehler", "„Bis“-Tatzeit liegt vor der „Von“-Tatzeit.")
			return
		self.create_case_requested.emit(name, desc, incident_at, incident_until)

	def _on_case_selected(self):
		item = self.case_list.currentItem()
		if not item:
			return
		self.case_selected.emit(item.data(Qt.ItemDataRole.UserRole))

	def set_case_name(self, name):
		self.lbl_case_name.setText(f"Aktueller Fall: {name}")

	def set_case_path(self, path):
		self._case_path = path

	def apply_dark_style(self):
		"""Einheitliches dunkles Farbschema (rein grafisch, keine Logikänderung)."""
		from pathlib import Path
		assets = (Path(__file__).resolve().parent / "assets").as_posix().replace("\\", "/")

		style = """
			/* ===== Grundflächen ===== */
			QMainWindow { background-color: #1a1a1a; }
			QDialog { background-color: #1a1a1a; color: #e6e6e6; }
			QStackedWidget { background-color: #1e1e1e; border: none; }
			QTabWidget::pane { border: 1px solid #333333; background-color: #1e1e1e; }
			QScrollArea { border: none; background-color: transparent; }

			/* ===== Beschriftungen ===== */
			QLabel { color: #cccccc; font-family: 'Segoe UI', sans-serif; }

			/* ===== Innere Registerkarten ===== */
			QTabBar::tab {
				background-color: #2d2d2d;
				color: #8f8f8f;
				padding: 7px 14px;
				border: 1px solid #333333;
				border-bottom: 2px solid #444444;
				border-top-left-radius: 4px;
				border-top-right-radius: 4px;
			}
			QTabBar::tab:selected {
				background-color: #1e1e1e;
				color: #ffffff;
				border-bottom: 2px solid #2d7dd2;
			}
			QTabBar::tab:hover:!selected { background-color: #383838; color: #d0d0d0; }
			QTabBar::tab:disabled { color: #666666; }

			/* ===== Schaltflächen ===== */
			QPushButton {
				background-color: #2f2f2f;
				color: #e6e6e6;
				border: 1px solid #4a4a4a;
				border-radius: 4px;
				padding: 6px 10px;
			}
			QPushButton:hover { background-color: #3a3a3a; border-color: #5c5c5c; }
			QPushButton:pressed { background-color: #262626; border-color: #444444; }
			QPushButton:disabled { background-color: #242424; color: #6a6a6a; border-color: #333333; }
			QPushButton:checked { background-color: #094771; border-color: #1177bb; color: #ffffff; }
			QPushButton:focus { border-color: #2d7dd2; }
			QPushButton#btnPrimary {
				background-color: #0e639c;
				border-color: #0e639c;
				color: #ffffff;
				font-weight: bold;
			}
			QPushButton#btnPrimary:hover { background-color: #1177bb; border-color: #1177bb; }
			QPushButton#btnPrimary:pressed { background-color: #0a4f7f; border-color: #0a4f7f; }
			QPushButton#btnPrimary:disabled {
				background-color: #243a4a; color: #6a8296; border-color: #2d4a5e;
			}
			/* Kompakte Analyse-Buttons (verhindert beschnittene Beschriftungen) */
			QPushButton#btnAnalysis { padding: 5px 6px; }

			/* ===== Eingabefelder ===== */
			QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox,
			QDoubleSpinBox, QDateEdit, QTimeEdit {
				background-color: #2d2d2d;
				color: #ffffff;
				border: 1px solid #454545;
				border-radius: 4px;
				padding: 5px 8px;
				selection-background-color: #264f78;
				selection-color: #ffffff;
			}
			QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover,
			QSpinBox:hover, QDoubleSpinBox:hover, QDateEdit:hover, QTimeEdit:hover {
				border-color: #5c5c5c;
			}
			QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
			QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus {
				border-color: #2d7dd2;
				background-color: #313131;
			}
			QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
			QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
			QDateEdit:disabled, QTimeEdit:disabled {
				background-color: #242424; color: #6f6f6f; border-color: #333333;
			}
			/* Innerer Editor von SpinBox/Datum (kein doppelter Rahmen) */
			QLineEdit#qt_spinbox_lineedit {
				padding: 0;
				border: none;
				background-color: transparent;
			}

			/* ===== Auswahllisten (Combobox) ===== */
			QComboBox { padding: 5px 28px 5px 8px; }
			QComboBox::drop-down {
				subcontrol-origin: padding;
				subcontrol-position: center right;
				width: 24px;
				border-left: 1px solid #454545;
				background-color: transparent;
			}
			QComboBox::down-arrow {
				image: url("%(assets)s/arrow_down.png");
				width: 9px;
				height: 6px;
			}
			QComboBox QAbstractItemView {
				background-color: #252526;
				color: #e6e6e6;
				border: 1px solid #4a4a4a;
				selection-background-color: #094771;
				selection-color: #ffffff;
				outline: 0;
			}

			/* ===== Datum / Uhrzeit / Spinner ===== */
			QDateTimeEdit { padding: 5px 26px 5px 8px; }
			QDateTimeEdit::up-button, QSpinBox::up-button, QDoubleSpinBox::up-button {
				subcontrol-origin: border;
				subcontrol-position: top right;
				width: 18px;
				border-left: 1px solid #454545;
				border-bottom: none;
				background-color: transparent;
			}
			QDateTimeEdit::down-button, QSpinBox::down-button, QDoubleSpinBox::down-button {
				subcontrol-origin: border;
				subcontrol-position: bottom right;
				width: 18px;
				border-left: 1px solid #454545;
				border-top: none;
				background-color: transparent;
			}
			QDateTimeEdit::up-arrow, QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
				image: url("%(assets)s/arrow_up.png");
				width: 9px;
				height: 6px;
			}
			QDateTimeEdit::down-arrow, QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
				image: url("%(assets)s/arrow_down.png");
				width: 9px;
				height: 6px;
			}
			QDateTimeEdit::calendar-button {
				subcontrol-origin: padding;
				subcontrol-position: center right;
				width: 24px;
				border-left: 1px solid #454545;
				background-color: transparent;
				image: url("%(assets)s/calendar.png");
			}

			/* ===== Kalender-Popup ===== */
			QCalendarWidget { background-color: #252526; }
			QCalendarWidget QToolButton {
				background-color: #2f2f2f;
				color: #e6e6e6;
				border: 1px solid #454545;
				border-radius: 3px;
				padding: 3px 6px;
				margin: 1px;
			}
			QCalendarWidget QToolButton:hover { background-color: #3a3a3a; }
			QCalendarWidget QAbstractItemView {
				background-color: #252526;
				color: #e6e6e6;
				selection-background-color: #094771;
				selection-color: #ffffff;
				outline: 0;
			}
			QCalendarWidget QSpinBox, QCalendarWidget QComboBox {
				background-color: #2d2d2d;
				color: #ffffff;
				border: 1px solid #454545;
				border-radius: 3px;
			}

			/* ===== Kontrollkästchen ===== */
			QCheckBox { spacing: 7px; color: #e0e0e0; }
			QCheckBox::indicator {
				width: 15px;
				height: 15px;
				border: 1px solid #5a5a5a;
				border-radius: 3px;
				background-color: #2d2d2d;
			}
			QCheckBox::indicator:hover { border-color: #2d7dd2; }
			QCheckBox::indicator:checked {
				background-color: #0e639c;
				border-color: #1177bb;
				image: url("%(assets)s/check.png");
			}
			QCheckBox::indicator:disabled {
				background-color: #242424;
				border-color: #444444;
			}
			QCheckBox:disabled { color: #6f6f6f; }

			/* ===== Listen ===== */
			QListWidget {
				background-color: #252526;
				color: #eeeeee;
				border: 1px solid #333333;
				border-radius: 4px;
				padding: 2px;
				outline: none;
			}
			QListWidget::item {
				padding: 7px 8px;
				border-left: 2px solid transparent;
				border-bottom: 1px solid #2a2a2a;
			}
			QListWidget::item:selected {
				background-color: #094771;
				color: #ffffff;
				border-left: 2px solid #2d7dd2;
			}
			QListWidget::item:hover:!selected { background-color: #2e3134; }

			/* ===== Tabellen ===== */
			QHeaderView::section {
				background-color: #252526;
				color: #b0b0b0;
				padding: 6px 8px;
				border: none;
				border-right: 1px solid #333333;
				border-bottom: 1px solid #333333;
			}
			QTableWidget {
				background-color: #1e1e1e;
				color: #dddddd;
				gridline-color: #2d2d2d;
				border: 1px solid #333333;
				selection-background-color: #094771;
				selection-color: #ffffff;
			}

			/* ===== Schieberegler ===== */
			QSlider::groove:horizontal {
				height: 4px;
				background-color: #3c3c3c;
				border-radius: 2px;
			}
			QSlider::sub-page:horizontal {
				background-color: #0e639c;
				border-radius: 2px;
			}
			QSlider::handle:horizontal {
				width: 14px;
				margin: -5px 0;
				border-radius: 7px;
				background-color: #e8e8e8;
				border: 1px solid #0e639c;
			}
			QSlider::handle:horizontal:hover { background-color: #ffffff; }

			/* ===== Fortschritt ===== */
			QProgressBar {
				background-color: #2d2d2d;
				border: 1px solid #454545;
				border-radius: 4px;
				text-align: center;
				color: #e6e6e6;
				min-height: 16px;
			}
			QProgressBar::chunk {
				background-color: #0e639c;
				border-radius: 3px;
			}

			/* ===== Bildlaufleisten ===== */
			QScrollBar:vertical {
				background-color: #1a1a1a;
				width: 12px;
				margin: 0;
				border: none;
			}
			QScrollBar::handle:vertical {
				background-color: #4d4d4d;
				min-height: 30px;
				width: 8px;
				margin: 2px;
				border-radius: 4px;
			}
			QScrollBar::handle:vertical:hover { background-color: #606060; }
			QScrollBar:horizontal {
				background-color: #1a1a1a;
				height: 12px;
				margin: 0;
				border: none;
			}
			QScrollBar::handle:horizontal {
				background-color: #4d4d4d;
				min-width: 30px;
				height: 8px;
				margin: 2px;
				border-radius: 4px;
			}
			QScrollBar::handle:horizontal:hover { background-color: #606060; }
			QScrollBar::add-line, QScrollBar::sub-line {
				width: 0;
				height: 0;
				border: none;
				background-color: transparent;
			}
			QScrollBar::add-page, QScrollBar::sub-page {
				background-color: transparent;
			}
			QScrollBar::corner { background-color: transparent; }

			/* ===== Teiler ===== */
			QSplitter::handle { background-color: #333333; }
			QSplitter::handle:horizontal { width: 2px; }
			QSplitter::handle:vertical { height: 2px; }
			QSplitter::handle:hover { background-color: #2d7dd2; }
			QSplitter::handle:pressed { background-color: #1177bb; }

			/* ===== Kontextmenüs und Hinweise ===== */
			QMenu {
				background-color: #252526;
				color: #e0e0e0;
				border: 1px solid #4a4a4a;
				padding: 4px;
			}
			QMenu::item {
				padding: 6px 26px 6px 14px;
				border-radius: 3px;
			}
			QMenu::item:selected { background-color: #094771; color: #ffffff; }
			QMenu::item:disabled { color: #6f6f6f; }
			QMenu::separator { height: 1px; background-color: #3c3c3c; margin: 4px 8px; }
			QToolTip {
				background-color: #2d2d2d;
				color: #e6e6e6;
				border: 1px solid #5a5a5a;
				padding: 4px 8px;
			}
			QMessageBox { background-color: #1e1e1e; }

			/* ===== Statusleiste ===== */
			QStatusBar { background-color: #1f1f1f; color: #b0b0b0; }
			QStatusBar::item { border: none; }
		""" % {"assets": assets}
		self.setStyleSheet(style)

	def update_file_list(self, files):
		self.file_list.clear()
		self.file_list.addItems(files)

	def apply_row_filter(self, query):
		for i in range(self.file_list.count()):
			item = self.file_list.item(i)
			item.setHidden(query.lower() not in item.text().lower())

	def clear_metadata_display(self):
		self.tabs.clear()
		self._metadata_tables = []
		self.thumb_label.setText("Vorschau")
		self.thumb_label.setPixmap(QPixmap())

	def set_thumbnail(self, path):
		if path and os.path.exists(path):
			try:
				from PIL import Image, ImageOps
				from io import BytesIO
				img = Image.open(path)
				img = ImageOps.exif_transpose(img) or img
				img.thumbnail((320, 180))
				buf = BytesIO()
				img.save(buf, format="PNG")
				buf.seek(0)
				pix = QPixmap()
				pix.loadFromData(buf.read())
				self.thumb_label.setPixmap(pix)
				return
			except Exception:
				pix = QPixmap(path)
				if not pix.isNull():
					self.thumb_label.setPixmap(
						pix.scaled(320, 180, Qt.AspectRatioMode.KeepAspectRatio))
		else:
			self.thumb_label.setText("Vorschau")

	def update_case_list(self, cases):
		self.case_list.clear()
		for c in cases:
			text = f"{c['project_name']} — {c['description']} — {c['created_at']}"
			item = QListWidgetItem(text)
			item.setData(Qt.ItemDataRole.UserRole, c['id'])
			self.case_list.addItem(item)

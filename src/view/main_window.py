import os
import json
import subprocess
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
							 QListWidget, QListWidgetItem, QLabel, QLineEdit,
							 QPushButton, QTabWidget, QTabBar, QTextEdit,
							 QStackedWidget, QMessageBox, QStyle, QStyleOptionTab,
							 QDateEdit, QTimeEdit, QCheckBox, QComboBox, QSlider,
							 QPlainTextEdit, QProgressBar, QGridLayout, QFileDialog,
							 QSpinBox, QSplitter)
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QDate, QTime, QDateTime
from PyQt6.QtGui import QPixmap, QPainter, QColor

from .hex_view import HexViewWidget
from .trim_widget import TrimWidget
from .image_enhance_widget import ImageEnhanceWidget
from .tab_builder import (build_case_tab, build_import_tab, build_metadata_tab,
	build_videos_tab, build_bilder_tab, build_settings_tab,
	build_hex_tab, build_analysis_tab, build_placeholder_tab,
	build_plugin_content, toggle_plugin_panel, update_plugin_tab_labels,
	active_media_prefix)

# ---------------------------------------------------------
# CUSTOM TAB BAR (flaches Design, horizontale Schrift)
# ---------------------------------------------------------
class FlatTabBar(QTabBar):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setDrawBase(False)
		self.setExpanding(True)

	def tabSizeHint(self, index):
		s = super().tabSizeHint(index)
		return QSize(max(s.width() + 30, 180), 40)

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)

		for idx in range(self.count()):
			opt = QStyleOptionTab()
			self.initStyleOption(opt, idx)
			rect = opt.rect
			selected = bool(opt.state & QStyle.StateFlag.State_Selected)

			painter.save()
			painter.setPen(Qt.PenStyle.NoPen)
			painter.setBrush(QColor("#094771" if selected else "#2d2d2d"))
			painter.drawRect(rect)
			if selected:
				painter.setPen(QColor("#0e639c"))
				painter.drawLine(rect.topLeft(), rect.bottomLeft())
			painter.restore()

			text = self.tabText(idx)
			painter.setPen(QColor("#ffffff" if selected else "#888888"))
			painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


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

		# --- RECHTS: Plugin-Tabbar ---
		self.plugin_bar = FlatTabBar()
		self.plugin_bar.setShape(QTabBar.Shape.RoundedEast)
		self.plugin_bar.setFixedWidth(160)

		# Plugin-Inhaltsbereich (rechts neben content_stack)
		self.plugin_stack = QStackedWidget()
		self.plugin_stack.setVisible(False)

		# Splitter: links content_stack, rechts plugin_stack
		self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
		self._main_splitter.addWidget(self.content_stack)
		self._main_splitter.addWidget(self.plugin_stack)
		self._main_splitter.setStretchFactor(0, 3)
		self._main_splitter.setStretchFactor(1, 2)

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

		# Plugin-Tabs rechts
		for i in range(1, 7):
			self.plugin_bar.addTab(f"Plugin {i}")
		build_plugin_content(self)

		# Navigation verknüpfen
		self.nav_bar.currentChanged.connect(self.content_stack.setCurrentIndex)
		self.content_stack.currentChanged.connect(lambda i: update_plugin_tab_labels(self, i))
		self.content_stack.currentChanged.connect(lambda i: toggle_plugin_panel(self, i))
		self.plugin_bar.currentChanged.connect(self.plugin_stack.setCurrentIndex)

		self._refresh_timezone()

		main_layout.addWidget(self.nav_bar)
		main_layout.addWidget(self._main_splitter, 1)
		main_layout.addWidget(self.plugin_bar)

		# Initialen Status setzen
		update_plugin_tab_labels(self, 0)
		toggle_plugin_panel(self, 0)

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
		path, _ = QFileDialog.getOpenFileName(
			self, "Mediendatei auswählen", "",
			"Media Files (*.mp4 *.mov *.avi *.mkv *.webm *.mts *.jpg *.png)"
		)
		if path:
			self.set_ffmpeg_file(path)
			# load into video trim widget as well (safe to call even if hidden)
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
			print(f"set_hex_file fehlgeschlagen: {e}")
		try:
			if hasattr(self, "video_trim_widget"):
				self.video_trim_widget.load_file(path)
		except Exception as e:
			print(f"trim_widget.load_file fehlgeschlagen: {e}")
		try:
			if hasattr(self, "_plugin_enhance"):
				self._plugin_enhance.load_image(path)
		except Exception as e:
			print(f"plugin_enhance.load_image fehlgeschlagen: {e}")

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
			print(f"_update_ffmpeg_encoded_date ffprobe: {e}")

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
			print(f"_update_ffmpeg_encoded_date db: {e}")

		label.setText("–")

	def _get_db_connection(self):
		for cls in type(self).__mro__:
			if hasattr(cls, 'get_connection'):
				return cls.get_connection(self)
		return None

	def _on_ffprobe_analyse(self, mode):
		path = self.ffmpeg_input_path
		if not path:
			QMessageBox.warning(self, "Keine Datei", "Bitte zuerst eine Datei auswählen.")
			return
		prefix = active_media_prefix(self)
		getattr(self, f"{prefix}_result").clear()
		self.ffprobe_analyse_requested.emit(path, mode, prefix)

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

	def apply_dark_style(self):
		style = """
			QMainWindow { background-color: #1a1a1a; }
			QLabel { color: #ccc; font-family: 'Segoe UI', sans-serif; }

			QListWidget { background-color: #252526; color: #eee; border: 1px solid #333; outline: none; }
			QListWidget::item { padding: 8px; border-bottom: 1px solid #2d2d2d; }
			QListWidget::item:selected { background-color: #094771; color: white; border-left: 4px solid #0e639c; }

			QPushButton { background-color: #333; color: white; border: 1px solid #555; padding: 10px; font-weight: bold; }
			QPushButton:hover { background-color: #444; border-color: #666; }
			QLineEdit { background-color: #2d2d2d; color: white; border: 1px solid #444; padding: 6px; }
			QTextEdit { background-color: #2d2d2d; color: white; border: 1px solid #444; padding: 6px; }

			QStackedWidget { background-color: #1e1e1e; border: none; }
			QTabWidget::pane { border: 1px solid #333; background-color: #1e1e1e; }
			QTabBar::tab { background-color: #2d2d2d; color: #888; padding: 8px 12px; border: 1px solid #333; border-bottom: 2px solid #444; }
			QTabBar::tab:selected { background-color: #1e1e1e; color: #fff; border-bottom: 2px solid #0e639c; }
			QTabBar::tab:hover { background-color: #333; }

			QHeaderView::section { background-color: #2d2d2d; color: #aaa; padding: 5px; border: 1px solid #111; }
			QTableWidget { background-color: #1e1e1e; color: #ddd; gridline-color: #2d2d2d; border: none; }
		"""
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
			pix = QPixmap(path)
			self.thumb_label.setPixmap(pix.scaled(320, 180, Qt.AspectRatioMode.KeepAspectRatio))
		else:
			self.thumb_label.setText("Vorschau")

	def update_case_list(self, cases):
		self.case_list.clear()
		for c in cases:
			text = f"{c['project_name']} — {c['description']} — {c['created_at']}"
			item = QListWidgetItem(text)
			item.setData(Qt.ItemDataRole.UserRole, c['id'])
			self.case_list.addItem(item)

import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
							 QListWidget, QListWidgetItem, QLabel, QLineEdit,
							 QPushButton, QTabWidget, QTabBar, QTextEdit,
							 QStackedWidget, QMessageBox, QStyle, QStyleOptionTab,
							 QDateEdit, QTimeEdit, QCheckBox, QComboBox, QSlider,
							 QPlainTextEdit, QProgressBar, QGridLayout)
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QDate, QTime, QDateTime, QProcess
from PyQt6.QtGui import QPixmap, QPainter, QColor


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
	ffmpeg_run_requested = pyqtSignal(str, str, str)
	ffmpeg_abort_requested = pyqtSignal()

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

		# Tabs + Inhalt bauen
		self._build_case_tab()
		self._build_import_tab()
		self._build_metadata_tab()
		self._build_ffprobe_tab()
		self._build_ffmpeg_tab()
		self._build_analysis_tab()
		self._build_placeholder_tab("Export")
		self._build_settings_tab()

		# Plugin-Tabs rechts
		for i in range(1, 7):
			self.plugin_bar.addTab(f"Plugin {i}")

		# Navigation verknüpfen
		self.nav_bar.currentChanged.connect(self.content_stack.setCurrentIndex)

		main_layout.addWidget(self.nav_bar)
		main_layout.addWidget(self.content_stack, 1)
		main_layout.addWidget(self.plugin_bar)

	def _build_case_tab(self):
		widget = QWidget()
		layout = QVBoxLayout(widget)

		title = QLabel("<b>Fallübersicht</b>")
		layout.addWidget(title)

		self.lbl_case_name = QLabel("Aktueller Fall: —")
		layout.addWidget(self.lbl_case_name)

		layout.addSpacing(20)
		layout.addWidget(QLabel("<b>Fallneuanlage</b>"))

		self.txt_case_name = QLineEdit()
		self.txt_case_name.setPlaceholderText("Fallname")
		layout.addWidget(self.txt_case_name)

		self.txt_case_desc = QTextEdit()
		self.txt_case_desc.setPlaceholderText("Beschreibung")
		self.txt_case_desc.setMaximumHeight(80)
		layout.addWidget(self.txt_case_desc)

		# ---- Tatzeit ----
		tatzeit_layout = QHBoxLayout()
		tatzeit_layout.addWidget(QLabel("Tatzeit:"))
		first_of_month = QDate.currentDate().addDays(-QDate.currentDate().day() + 1)
		self.d_incident = QDateEdit(first_of_month)
		self.d_incident.setCalendarPopup(True)
		self.d_incident.setDisplayFormat("dd.MM.yyyy")
		tatzeit_layout.addWidget(self.d_incident)
		self.t_incident = QTimeEdit(QTime(0, 0))
		self.t_incident.setDisplayFormat("HH:mm")
		tatzeit_layout.addWidget(self.t_incident)
		self.chk_bis = QCheckBox("Bis:")
		self.chk_bis.toggled.connect(self._on_bis_toggled)
		tatzeit_layout.addWidget(self.chk_bis)
		self.d_incident_until = QDateEdit(first_of_month)
		self.d_incident_until.setCalendarPopup(True)
		self.d_incident_until.setDisplayFormat("dd.MM.yyyy")
		self.d_incident_until.setVisible(False)
		tatzeit_layout.addWidget(self.d_incident_until)
		self.t_incident_until = QTimeEdit(QTime(0, 0))
		self.t_incident_until.setDisplayFormat("HH:mm")
		self.t_incident_until.setVisible(False)
		tatzeit_layout.addWidget(self.t_incident_until)
		tatzeit_layout.addStretch()
		layout.addLayout(tatzeit_layout)

		btn_create = QPushButton("Fall erstellen")
		btn_create.clicked.connect(self._on_create_case)
		layout.addWidget(btn_create)

		layout.addSpacing(20)
		layout.addWidget(QLabel("<b>Fallexplorer</b>"))

		self.case_list = QListWidget()
		self.case_list.itemDoubleClicked.connect(self._on_case_selected)
		layout.addWidget(self.case_list, 1)

		btn_open = QPushButton("Ausgewählten Fall öffnen")
		btn_open.clicked.connect(self._on_case_selected)
		layout.addWidget(btn_open)

		self.nav_bar.addTab("Fallübersicht")
		self.content_stack.addWidget(widget)

	def _build_import_tab(self):
		widget = QWidget()
		layout = QVBoxLayout(widget)

		layout.addWidget(QLabel("<b>Medien Import</b>"))
		layout.addSpacing(10)
		layout.addWidget(QLabel("Importieren Sie Videodateien und Fotos\nmit Lieferantenangaben in den aktuellen Fall."))
		layout.addSpacing(10)

		btn_import = QPushButton("Import-Dialog öffnen")
		btn_import.setMinimumHeight(80)
		btn_import.clicked.connect(self.import_media_requested.emit)
		layout.addWidget(btn_import)

		layout.addStretch()

		self.nav_bar.addTab("Import")
		self.content_stack.addWidget(widget)

	def _build_metadata_tab(self):
		widget = QWidget()
		layout = QHBoxLayout(widget)

		left = QVBoxLayout()
		self.search_bar = QLineEdit()
		self.search_bar.setPlaceholderText("Dateiliste filtern...")
		self.search_bar.setClearButtonEnabled(True)
		self.file_list = QListWidget()
		self.btn_scan = QPushButton("Watchfolder scannen")
		self.btn_scan.setToolTip("Scannt den Eingabeordner nach Mediendateien")

		left.addWidget(QLabel("Mediendateien"))
		left.addWidget(self.search_bar)
		left.addWidget(self.file_list, 1)
		left.addWidget(self.btn_scan)

		right = QVBoxLayout()
		self.thumb_label = QLabel("Vorschau")
		self.thumb_label.setFixedSize(320, 180)
		self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.thumb_label.setStyleSheet("border: 2px solid #333; background: black;")

		self.tabs = QTabWidget()
		self.tabs.setDocumentMode(True)

		right.addWidget(self.thumb_label, alignment=Qt.AlignmentFlag.AlignCenter)
		self.meta_search_bar = QLineEdit()
		self.meta_search_bar.setPlaceholderText("In Metadaten suchen...")
		self.meta_search_bar.setClearButtonEnabled(True)
		right.addWidget(self.meta_search_bar)
		right.addWidget(self.tabs, 1)

		layout.addLayout(left, 1)
		layout.addLayout(right, 3)

		self.btn_scan.clicked.connect(self.scan_requested.emit)
		self.search_bar.textChanged.connect(self.search_changed.emit)
		self.meta_search_bar.textChanged.connect(self._on_meta_search)
		self.file_list.itemClicked.connect(
			lambda item: self.file_selected.emit(item.text())
		)

		self.nav_bar.addTab("Metadaten")
		self.content_stack.addWidget(widget)

	def _build_ffprobe_tab(self):
		widget = QWidget()
		layout = QVBoxLayout(widget)
		label = QLabel("ffprobe\n\nNoch nicht implementiert")
		label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		layout.addWidget(label)
		self.nav_bar.addTab("ffprobe")
		self.content_stack.addWidget(widget)

	def _build_ffmpeg_tab(self):
		widget = QWidget()
		layout = QVBoxLayout(widget)

		layout.addWidget(QLabel("<b>ffmpeg</b>"))
		layout.addSpacing(8)

		# Dateiauswahl
		file_layout = QHBoxLayout()
		file_layout.addWidget(QLabel("Datei:"))
		self.ffmpeg_file_label = QLabel("–")
		self.ffmpeg_file_label.setStyleSheet("color: #aaa;")
		file_layout.addWidget(self.ffmpeg_file_label, 1)
		self.ffmpeg_input_path = ""  # wird vom Presenter gesetzt
		self.ffmpeg_btn_browse = QPushButton("Durchsuchen")
		file_layout.addWidget(self.ffmpeg_btn_browse)
		layout.addLayout(file_layout)

		# Preset-Buttons
		layout.addWidget(QLabel("Presets:"))
		preset_grid = QGridLayout()
		presets = [
			(0, 0, "Trim", self._ffmpeg_preset_trim),
			(0, 1, "Frames", self._ffmpeg_preset_frames),
			(0, 2, "Audio", self._ffmpeg_preset_audio),
			(0, 3, "Timecode", self._ffmpeg_preset_timecode),
			(1, 0, "Container", self._ffmpeg_preset_container),
			(1, 1, "Hash", self._ffmpeg_preset_hash),
			(1, 2, "Custom", self._ffmpeg_preset_custom),
		]
		for row, col, title, cb in presets:
			btn = QPushButton(title)
			btn.clicked.connect(cb)
			preset_grid.addWidget(btn, row, col)
		layout.addLayout(preset_grid)

		# Parameter
		param_group = QWidget()
		param_group.setStyleSheet("QWidget#ffmpeg_params { border: 1px solid #444; padding: 6px; }")
		param_group.setObjectName("ffmpeg_params")
		param_layout = QHBoxLayout(param_group)

		param_layout.addWidget(QLabel("Start:"))
		self.ffmpeg_start = QTimeEdit(QTime(0, 0))
		self.ffmpeg_start.setDisplayFormat("HH:mm:ss")
		param_layout.addWidget(self.ffmpeg_start)

		param_layout.addWidget(QLabel("Ende:"))
		self.ffmpeg_end = QTimeEdit(QTime(0, 0))
		self.ffmpeg_end.setDisplayFormat("HH:mm:ss")
		self.ffmpeg_end.setSpecialValueText("–")
		self.ffmpeg_end.clear()
		param_layout.addWidget(self.ffmpeg_end)

		param_layout.addWidget(QLabel("Format:"))
		self.ffmpeg_format = QComboBox()
		self.ffmpeg_format.addItem("FFV1 (lossless)", "ffv1")
		self.ffmpeg_format.addItem("H.264 CRF 18", "h264_crf18")
		self.ffmpeg_format.addItem("H.264 CRF 10", "h264_crf10")
		param_layout.addWidget(self.ffmpeg_format)

		param_layout.addWidget(QLabel("Filter:"))
		self.ffmpeg_filter = QLineEdit()
		self.ffmpeg_filter.setPlaceholderText("z.B. scale=1280:720,eq=brightness=0.2")
		param_layout.addWidget(self.ffmpeg_filter, 1)

		layout.addWidget(param_group)

		# Ausführen / Abbrechen
		run_layout = QHBoxLayout()
		self.ffmpeg_btn_run = QPushButton("▶ Ausführen")
		self.ffmpeg_btn_run.setMinimumHeight(36)
		self.ffmpeg_btn_run.clicked.connect(self._on_ffmpeg_run)
		run_layout.addWidget(self.ffmpeg_btn_run)

		self.ffmpeg_btn_abort = QPushButton("✕ Abbrechen")
		self.ffmpeg_btn_abort.setMinimumHeight(36)
		self.ffmpeg_btn_abort.setEnabled(False)
		self.ffmpeg_btn_abort.clicked.connect(self._on_ffmpeg_abort)
		run_layout.addWidget(self.ffmpeg_btn_abort)

		self.ffmpeg_btn_abort.setStyleSheet("color: #ff6666;")
		run_layout.addStretch()
		self.ffmpeg_out_label = QLabel("")
		run_layout.addWidget(self.ffmpeg_out_label)
		layout.addLayout(run_layout)

		# Log
		self.ffmpeg_log = QPlainTextEdit()
		self.ffmpeg_log.setReadOnly(True)
		self.ffmpeg_log.setMaximumBlockCount(1000)
		self.ffmpeg_log.setStyleSheet("background: #111; color: #0f0; font-family: Consolas; font-size: 9pt;")
		layout.addWidget(self.ffmpeg_log, 1)

		# Progress
		self.ffmpeg_progress = QProgressBar()
		self.ffmpeg_progress.setTextVisible(True)
		layout.addWidget(self.ffmpeg_progress)

		self.nav_bar.addTab("ffmpeg")
		self.content_stack.addWidget(widget)

	def _ffmpeg_preset_trim(self):
		self.ffmpeg_filter.clear()
		self.ffmpeg_format.setCurrentIndex(0)

	def _ffmpeg_preset_frames(self):
		self.ffmpeg_filter.setText("fps=1/10")
		self.ffmpeg_format.setCurrentIndex(0)
		self.ffmpeg_end.clear()

	def _ffmpeg_preset_audio(self):
		self.ffmpeg_filter.clear()
		self.ffmpeg_format.setCurrentIndex(0)
		self.ffmpeg_start.setTime(QTime(0, 0))
		self.ffmpeg_end.clear()

	def _ffmpeg_preset_timecode(self):
		self.ffmpeg_filter.setText("__TIMECODE__")
		self.ffmpeg_format.setCurrentIndex(0)
		self.ffmpeg_start.setTime(QTime(0, 0))
		self.ffmpeg_end.clear()

	def _ffmpeg_preset_container(self):
		self.ffmpeg_filter.clear()
		self.ffmpeg_format.setCurrentIndex(0)
		self.ffmpeg_start.setTime(QTime(0, 0))
		self.ffmpeg_end.clear()

	def _ffmpeg_preset_hash(self):
		self.ffmpeg_filter.setText("-f framehash -")
		self.ffmpeg_format.setCurrentIndex(0)
		self.ffmpeg_start.setTime(QTime(0, 0))
		self.ffmpeg_end.clear()

	def _ffmpeg_preset_custom(self):
		pass

	def _on_ffmpeg_run(self):
		inp = self.ffmpeg_input_path
		if not inp:
			QMessageBox.warning(self, "Keine Datei", "Bitte zuerst eine Datei auswählen.")
			return
		start = self.ffmpeg_start.time().toString("HH:mm:ss")
		end = self.ffmpeg_end.time().toString("HH:mm:ss") if self.ffmpeg_end.time() != QTime(0, 0) else ""
		filter_str = self.ffmpeg_filter.text().strip()
		fmt = self.ffmpeg_format.currentData()
		self.ffmpeg_run_requested.emit(inp, start + "|" + end + "|" + filter_str, fmt)

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

	def set_ffmpeg_file(self, path):
		self.ffmpeg_input_path = path
		self.ffmpeg_file_label.setText(os.path.basename(path))
		self.ffmpeg_file_label.setToolTip(path)
		self.ffmpeg_log.clear()
		self.ffmpeg_progress.setValue(0)

	def _on_meta_search(self, query):
		if hasattr(self, "search_metadata_tables"):
			self.search_metadata_tables(query)

	def _build_settings_tab(self):
		widget = QWidget()
		layout = QVBoxLayout(widget)

		layout.addWidget(QLabel("<b>Einstellungen</b>"))
		layout.addSpacing(20)

		layout.addWidget(QLabel("Datenbank-Benutzer:"))
		self.lbl_db_user = QLabel("—")
		self.lbl_db_user.setStyleSheet("background-color: #2d2d2d; color: #ccc; padding: 6px; border: 1px solid #444;")
		layout.addWidget(self.lbl_db_user)

		layout.addWidget(QLabel("Datenbank-Passwort:"))
		pw_layout = QHBoxLayout()
		self.lbl_db_password = QLabel("—")
		self.lbl_db_password.setStyleSheet("background-color: #2d2d2d; color: #ccc; padding: 6px; border: 1px solid #444;")
		self.lbl_db_password.setMinimumWidth(200)
		self.lbl_db_password.setWordWrap(True)
		pw_layout.addWidget(self.lbl_db_password, 1)
		self._pw_visible = False
		self.btn_toggle_pw = QPushButton("\U0001F441")
		self.btn_toggle_pw.setFixedWidth(36)
		self.btn_toggle_pw.setCheckable(True)
		self.btn_toggle_pw.toggled.connect(self._toggle_password_visible)
		pw_layout.addWidget(self.btn_toggle_pw)
		layout.addLayout(pw_layout)

		layout.addWidget(QLabel("MariaDB-Root-Passwort:"))
		root_pw_layout = QHBoxLayout()
		self.lbl_root_password = QLabel("—")
		self.lbl_root_password.setStyleSheet("background-color: #2d2d2d; color: #ccc; padding: 6px; border: 1px solid #444;")
		self.lbl_root_password.setMinimumWidth(200)
		self.lbl_root_password.setWordWrap(True)
		root_pw_layout.addWidget(self.lbl_root_password, 1)
		self._root_pw_visible = False
		self.btn_toggle_root_pw = QPushButton("\U0001F441")
		self.btn_toggle_root_pw.setFixedWidth(36)
		self.btn_toggle_root_pw.setCheckable(True)
		self.btn_toggle_root_pw.toggled.connect(self._toggle_root_pw_visible)
		root_pw_layout.addWidget(self.btn_toggle_root_pw)
		layout.addLayout(root_pw_layout)

		layout.addSpacing(10)
		layout.addWidget(QLabel("Neues Datenbank-Passwort festlegen (optional):"))
		new_pw_layout = QHBoxLayout()
		self.txt_new_db_password = QLineEdit()
		self.txt_new_db_password.setEchoMode(QLineEdit.EchoMode.Password)
		self.txt_new_db_password.setPlaceholderText("leer lassen = kein Update")
		new_pw_layout.addWidget(self.txt_new_db_password)
		self.btn_toggle_new_pw = QPushButton("\U0001F441")
		self.btn_toggle_new_pw.setFixedWidth(36)
		self.btn_toggle_new_pw.setCheckable(True)
		self.btn_toggle_new_pw.toggled.connect(self._toggle_new_pw_visible)
		new_pw_layout.addWidget(self.btn_toggle_new_pw)
		layout.addLayout(new_pw_layout)

		layout.addSpacing(20)
		layout.addWidget(QLabel("Basisordner für neue Fälle:"))
		folder_layout = QHBoxLayout()
		self.txt_case_root = QLineEdit()
		folder_layout.addWidget(self.txt_case_root)
		btn_browse = QPushButton("…")
		btn_browse.setFixedWidth(40)
		btn_browse.clicked.connect(self._on_browse_case_root)
		folder_layout.addWidget(btn_browse)
		layout.addLayout(folder_layout)

		layout.addSpacing(10)
		btn_save = QPushButton("Einstellungen speichern")
		btn_save.clicked.connect(self._on_save_settings)
		layout.addWidget(btn_save)

		layout.addStretch()

		self.nav_bar.addTab("Einstellungen")
		self.content_stack.addWidget(widget)

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

	def _build_analysis_tab(self):
		widget = QWidget()
		layout = QVBoxLayout(widget)

		layout.addWidget(QLabel("<b>Auswertung</b>"))
		layout.addSpacing(10)

		toolbar = QHBoxLayout()
		btn_timeline = QPushButton("Zeitachsen-Analyse")
		btn_timeline.clicked.connect(self.open_timeline_requested.emit)
		toolbar.addWidget(btn_timeline)

		toolbar.addStretch()

		toolbar.addWidget(QLabel("Zoom:"))
		self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
		self.slider_zoom.setRange(25, 400)
		self.slider_zoom.setValue(100)
		self.slider_zoom.setFixedWidth(120)
		self.slider_zoom.setTickPosition(QSlider.TickPosition.TicksBelow)
		self.slider_zoom.setTickInterval(75)
		self.slider_zoom.valueChanged.connect(self.open_timeline_requested.emit)
		toolbar.addWidget(self.slider_zoom)
		self.lbl_zoom = QLabel("100%")
		self.slider_zoom.valueChanged.connect(lambda v: self.lbl_zoom.setText(f"{v}%"))
		toolbar.addWidget(self.lbl_zoom)

		toolbar.addStretch()

		toolbar.addWidget(QLabel("Offset:"))
		self.cbo_offset = QComboBox()
		self.cbo_offset.addItem("Winter UTC+1", 1)
		self.cbo_offset.addItem("Sommer UTC+2", 2)
		self.cbo_offset.currentIndexChanged.connect(self.open_timeline_requested.emit)
		toolbar.addWidget(self.cbo_offset)

		layout.addLayout(toolbar)

		from ..timeline_window import TimelineWidget
		self.timeline_widget = TimelineWidget()
		layout.addWidget(self.timeline_widget, 1)

		self.nav_bar.addTab("Auswertung")
		self.content_stack.addWidget(widget)

		self._is_analysis_built = True

	def _build_placeholder_tab(self, title):
		widget = QWidget()
		layout = QVBoxLayout(widget)
		label = QLabel(f"{title}\n\nNoch nicht implementiert")
		label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		layout.addWidget(label)
		self.nav_bar.addTab(title)
		self.content_stack.addWidget(widget)

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

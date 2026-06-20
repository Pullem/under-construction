import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
							 QListWidget, QListWidgetItem, QLabel, QLineEdit,
							 QPushButton, QTabWidget, QTabBar, QTextEdit,
							 QStackedWidget, QMessageBox, QStyle, QStyleOptionTab,
							 QDateTimeEdit, QCheckBox)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
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

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.setWindowTitle("Video Forensic Lab - Analyzer")
		self.resize(1280, 720)

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
		self._build_placeholder_tab("Auswertung")
		self._build_placeholder_tab("Export")
		self._build_placeholder_tab("Einstellungen")

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
		self.dt_incident = QDateTimeEdit()
		self.dt_incident.setCalendarPopup(True)
		self.dt_incident.setDisplayFormat("dd.MM.yyyy HH:mm")
		tatzeit_layout.addWidget(self.dt_incident)
		self.chk_bis = QCheckBox("Bis:")
		self.chk_bis.toggled.connect(self._on_bis_toggled)
		tatzeit_layout.addWidget(self.chk_bis)
		self.dt_incident_until = QDateTimeEdit()
		self.dt_incident_until.setCalendarPopup(True)
		self.dt_incident_until.setDisplayFormat("dd.MM.yyyy HH:mm")
		self.dt_incident_until.setVisible(False)
		tatzeit_layout.addWidget(self.dt_incident_until)
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
		self.search_bar.setPlaceholderText("Suche in Metadaten...")
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
		right.addWidget(self.tabs, 1)

		layout.addLayout(left, 1)
		layout.addLayout(right, 3)

		self.btn_scan.clicked.connect(self.scan_requested.emit)
		self.search_bar.textChanged.connect(self.search_changed.emit)
		self.file_list.itemClicked.connect(
			lambda item: self.file_selected.emit(item.text())
		)

		self.nav_bar.addTab("Metadaten")
		self.content_stack.addWidget(widget)

	def _build_placeholder_tab(self, title):
		widget = QWidget()
		layout = QVBoxLayout(widget)
		label = QLabel(f"{title}\n\nNoch nicht implementiert")
		label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		layout.addWidget(label)
		self.nav_bar.addTab(title)
		self.content_stack.addWidget(widget)

	def _on_bis_toggled(self, checked):
		self.dt_incident_until.setVisible(checked)

	def _on_create_case(self):
		name = self.txt_case_name.text().strip()
		desc = self.txt_case_desc.toPlainText().strip()
		if not name:
			QMessageBox.warning(self, "Fehler", "Fallname darf nicht leer sein.")
			return
		incident_at = self.dt_incident.dateTime().toPyDateTime()
		incident_until = self.dt_incident_until.dateTime().toPyDateTime() if self.chk_bis.isChecked() else None
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

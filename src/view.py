import os # Für check in set_thumbnail

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
							 QPushButton, QLineEdit, QTabWidget, QTableWidget, 
							 QTableWidgetItem, QHeaderView, QLabel, QTabBar,
							 QListWidget, QSplitter)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QPixmap

class ForensicView(QMainWindow):
	start_requested = pyqtSignal()
	config_requested = pyqtSignal()
	search_changed = pyqtSignal(str)
	file_selected = pyqtSignal(str)

	def __init__(self):
		super().__init__()
		self.setWindowTitle("Video Forensics Analyzer PRO")
		self.resize(1300, 850)

		central_widget = QWidget()
		self.setCentralWidget(central_widget)
		main_layout = QVBoxLayout(central_widget)

		# Toolbar
		top_bar = QHBoxLayout()
		self.btn_config = QPushButton("⚙ Konfiguration")
		self.btn_start = QPushButton("🚀 Watchfolder Scan")
		self.search_input = QLineEdit()
		self.search_input.setPlaceholderText("Metadaten-Filter...")
		self.search_input.setClearButtonEnabled(True)
		
		top_bar.addWidget(self.btn_config)
		top_bar.addWidget(self.btn_start)
		top_bar.addStretch()
		top_bar.addWidget(QLabel("Filter:"))
		top_bar.addWidget(self.search_input)
		main_layout.addLayout(top_bar)

		# Main Splitter
		self.splitter = QSplitter(Qt.Orientation.Horizontal)
		
		# Links: Sidebar mit Thumbnail und Liste
		sidebar = QWidget()
		sidebar_layout = QVBoxLayout(sidebar)
		
		self.thumb_label = QLabel("Keine Vorschau")
		self.thumb_label.setFixedSize(320, 180)
		self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.thumb_label.setStyleSheet("border: 2px solid #333; background: #000; color: #555;")
		sidebar_layout.addWidget(self.thumb_label)
		
		sidebar_layout.addWidget(QLabel("Dateiliste:"))
		self.file_list = QListWidget()
		sidebar_layout.addWidget(self.file_list)
		self.splitter.addWidget(sidebar)

		# Rechts: Metadaten
		self.tabs = QTabWidget()
		self.tabs.setDocumentMode(True)
		self.splitter.addWidget(self.tabs)
		
		self.splitter.setStretchFactor(1, 4)
		main_layout.addWidget(self.splitter)

		# Signals
		self.btn_start.clicked.connect(self.start_requested.emit)
		self.btn_config.clicked.connect(self.config_requested.emit)
		self.search_input.textChanged.connect(self.search_changed.emit)
		self.file_list.currentTextChanged.connect(self.file_selected.emit)

	def set_thumbnail(self, path):
		if path and os.path.exists(path):
			pixmap = QPixmap(path)
			self.thumb_label.setPixmap(pixmap.scaled(self.thumb_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
		else:
			self.thumb_label.clear()
			self.thumb_label.setText("Keine Vorschau")

	def update_file_list(self, files):
		self.file_list.clear()
		if files: self.file_list.addItems(files)

	def display_metadata(self, metadata_dict):
		self.tabs.clear()
		colors = {"General": "#2c3e50", "Video": "#c0392b", "Audio": "#27ae60", "Image": "#d35400", "Other": "#7f8c8d"}

		for cat, params in metadata_dict.items():
			table = QTableWidget(len(params), 2)
			table.setHorizontalHeaderLabels(["Parameter", "Wert"])
			table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
			table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
			
			for row, (k, v) in enumerate(params.items()):
				ik, iv = QTableWidgetItem(str(k)), QTableWidgetItem(str(v))
				ik.setFlags(ik.flags() & ~Qt.ItemFlag.ItemIsEditable)
				iv.setFlags(iv.flags() & ~Qt.ItemFlag.ItemIsEditable)
				table.setItem(row, 0, ik)
				table.setItem(row, 1, iv)

			idx = self.tabs.addTab(table, cat)
			col = colors.get(cat, colors["Other"])
			self.tabs.tabBar().setTabTextColor(idx, QColor("white"))
			self.tabs.setStyleSheet(f"QTabBar::tab:selected {{ background: {col}; color: white; font-weight: bold; }}")
			self.tabs.tabBar().setTabButton(idx, QTabBar.ButtonPosition.LeftSide, None)

		self.apply_row_filter(self.search_input.text())

	def apply_row_filter(self, query):
		query = query.lower()
		for i in range(self.tabs.count()):
			table = self.tabs.widget(i)
			if isinstance(table, QTableWidget):
				hits = 0
				for r in range(table.rowCount()):
					match = query in table.item(r, 0).text().lower() or query in table.item(r, 1).text().lower()
					table.setRowHidden(r, not match)
					if match: hits += 1
				orig = self.tabs.tabText(i).split(" (")[0]
				self.tabs.setTabText(i, f"{orig} ({hits})" if query else orig)


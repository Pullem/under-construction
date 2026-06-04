from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
							 QPushButton, QLineEdit, QTabWidget, QTableWidget, 
							 QTableWidgetItem, QHeaderView, QLabel, QTabBar,
							 QListWidget, QSplitter)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor

class ForensicView(QMainWindow):
	# Signale für die Kommunikation mit dem Presenter
	start_requested = pyqtSignal()
	config_requested = pyqtSignal()
	search_changed = pyqtSignal(str)
	file_selected = pyqtSignal(str)

	def __init__(self):
		super().__init__()
		self.setWindowTitle("Video Forensics Analyzer PRO")
		self.resize(1200, 800)

		# Zentrales Widget und Haupt-Layout
		central_widget = QWidget()
		self.setCentralWidget(central_widget)
		main_layout = QVBoxLayout(central_widget)

		# --- TOP TOOLBAR ---
		top_bar = QHBoxLayout()
		self.btn_config = QPushButton("⚙ Konfiguration")
		self.btn_start = QPushButton("🚀 Watchfolder Scan")
		self.search_input = QLineEdit()
		self.search_input.setPlaceholderText("Globaler Metadaten-Filter...")
		
		top_bar.addWidget(self.btn_config)
		top_bar.addWidget(self.btn_start)
		top_bar.addStretch()
		top_bar.addWidget(QLabel("Suche:"))
		top_bar.addWidget(self.search_input)
		main_layout.addLayout(top_bar)

		# --- HAUPTBEREICH (Splitter) ---
		# Ein Splitter erlaubt es dem Nutzer, die Breite der Liste manuell zu ändern
		self.splitter = QSplitter(Qt.Orientation.Horizontal)
		
		# Links: Die Dateiliste
		list_container = QWidget()
		list_layout = QVBoxLayout(list_container)
		list_layout.addWidget(QLabel("Gefundene Medien:"))
		self.file_list = QListWidget()
		list_layout.addWidget(self.file_list)
		self.splitter.addWidget(list_container)

		# Rechts: Die Tabs für Metadaten
		self.tabs = QTabWidget()
		self.tabs.setDocumentMode(True)
		self.tabs.setMovable(True)
		self.splitter.addWidget(self.tabs)
		
		# Initiales Verhältnis: 20% Liste, 80% Tabs
		self.splitter.setStretchFactor(0, 1)
		self.splitter.setStretchFactor(1, 4)
		
		main_layout.addWidget(self.splitter)

		# --- EVENT-BINDING ---
		self.btn_start.clicked.connect(self.start_requested.emit)
		self.btn_config.clicked.connect(self.config_requested.emit)
		self.search_input.textChanged.connect(self.search_changed.emit)
		
		# Wenn ein Item in der Liste angeklickt wird
		self.file_list.currentTextChanged.connect(self.file_selected.emit)

	def update_file_list(self, files):
		"""Aktualisiert die Dateiliste auf der linken Seite."""
		self.file_list.clear()
		if files:
			self.file_list.addItems(files)

	def display_metadata(self, metadata_dict):
		"""Erstellt dynamisch Tabs basierend auf den JSON-Kategorien."""
		self.tabs.clear()
		
		# Farbschema für Forensik-Kategorien
		category_colors = {
			"General": "#2c3e50", # Dunkelblau
			"Video": "#c0392b",   # Dunkelrot
			"Audio": "#27ae60",   # Grün
			"Image": "#d35400",   # Orange
			"Menu": "#8e44ad",    # Lila
			"Other": "#7f8c8d"    # Grau
		}

		for category, parameters in metadata_dict.items():
			# Erstelle Tabelle für diesen Tab
			table = QTableWidget(len(parameters), 2)
			table.setHorizontalHeaderLabels(["Parameter", "Wert"])
			table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
			table.setAlternatingRowColors(True)
			
			# Daten einfüllen
			for row, (key, value) in enumerate(parameters.items()):
				table.setItem(row, 0, QTableWidgetItem(str(key)))
				table.setItem(row, 1, QTableWidgetItem(str(value)))

			# Tab hinzufügen
			idx = self.tabs.addTab(table, category)
			
			# Farbe zuweisen
			bg_color = category_colors.get(category, category_colors["Other"])
			self.tabs.tabBar().setTabTextColor(idx, QColor("white"))
			
			# Stylesheet für den Tab-Header
			self.tabs.setStyleSheet(f"""
				QTabBar::tab:selected {{ background: {bg_color}; color: white; font-weight: bold; }}
				QTabBar::tab {{ padding: 8px 15px; }}
			""")
			
			# Button-Enum Fix (PyQt6 kompatibel)
			self.tabs.tabBar().setTabButton(idx, QTabBar.ButtonPosition.LeftSide, None)
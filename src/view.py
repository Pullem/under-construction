import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
							 QListWidget, QTableWidget, QTableWidgetItem, 
							 QTabWidget, QTabBar, QLabel, QLineEdit, 
							 QPushButton, QHeaderView)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QColor, QIcon, QPainter

class ForensicView(QMainWindow):
	start_requested = pyqtSignal()
	config_requested = pyqtSignal()
	search_changed = pyqtSignal(str)
	file_selected = pyqtSignal(str)

	def __init__(self):
		super().__init__()
		self.setWindowTitle("Video Forensic Lab - Analyzer")
		self.resize(1200, 800)
		self.setup_ui()
		self.apply_dark_style()

	def setup_ui(self):
		main_layout = QHBoxLayout()
		central_widget = QWidget()
		central_widget.setLayout(main_layout)
		self.setCentralWidget(central_widget)

		# --- LINKS ---
		left_panel = QVBoxLayout()
		self.search_bar = QLineEdit()
		self.search_bar.setPlaceholderText("Suche...")
		self.file_list = QListWidget()
		self.btn_scan = QPushButton("Watchfolder Scan")
		
		left_panel.addWidget(QLabel("📂 Beweisstücke"))
		left_panel.addWidget(self.search_bar)
		left_panel.addWidget(self.file_list)
		left_panel.addWidget(self.btn_scan)

		# --- RECHTS ---
		right_panel = QVBoxLayout()
		self.thumb_label = QLabel("Vorschau")
		self.thumb_label.setFixedSize(320, 180)
		self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.thumb_label.setStyleSheet("border: 2px solid #333; background: black;")
		
		self.tabs = QTabWidget()
		self.tabs.setDocumentMode(True)
		
		right_panel.addWidget(self.thumb_label, alignment=Qt.AlignmentFlag.AlignCenter)
		right_panel.addWidget(self.tabs)

		main_layout.addLayout(left_panel, 1)
		main_layout.addLayout(right_panel, 3)

		# Signale
		self.btn_scan.clicked.connect(self.start_requested.emit)
		self.search_bar.textChanged.connect(self.search_changed.emit)
		self.file_list.itemClicked.connect(lambda item: self.file_selected.emit(item.text()))

	def apply_dark_style(self):
		style = """
			QMainWindow { background-color: #1a1a1a; }
			QLabel { color: #ccc; }
			QListWidget { background-color: #252526; color: #eee; border: none; }
			QListWidget::item:selected { background-color: #0e639c; }
			QPushButton { background-color: #333; color: white; border: 1px solid #555; padding: 8px; }
			QPushButton:hover { background-color: #444; }
			QLineEdit { background-color: #2d2d2d; color: white; border: 1px solid #444; }
			QHeaderView::section { background-color: #333; color: white; border: 1px solid #111; }
			QTableWidget { background-color: #1e1e1e; color: #ddd; gridline-color: #333; }
		"""
		self.setStyleSheet(style)

	def create_color_icon(self, hex_color):
		"""Erstellt ein kleines quadratisches Icon in der gewünschten Farbe."""
		pixmap = QPixmap(12, 12)
		pixmap.fill(QColor(hex_color))
		return QIcon(pixmap)

	def display_metadata(self, metadata_dict):
		self.tabs.clear()
		
		# Farbschema Definition
		colors = {
			"General": "#4FC3F7",       # Hellblau
			"Video": "#29B6F6",         # Blau
			"Audio": "#66BB6A",         # Grün
			"EXIF Deep Dive": "#FF7043", # Forensik-Orange
			"Other": "#9E9E9E"          # Grau
		}

		for i, (category, params) in enumerate(metadata_dict.items()):
			if not isinstance(params, dict): continue
			
			table = QTableWidget(len(params), 2)
			table.setHorizontalHeaderLabels(["Parameter", "Wert"])
			table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
			
			for row, (key, value) in enumerate(params.items()):
				table.setItem(row, 0, QTableWidgetItem(str(key)))
				table.setItem(row, 1, QTableWidgetItem(str(value)))

			# Tab mit Icon und Text hinzufügen
			color_hex = colors.get(category, colors["Other"])
			self.tabs.addTab(table, category)
			
			# --- DIE FARB-MAGIE ---
			# 1. Kleines farbiges Quadrat links neben den Text
			self.tabs.setTabIcon(i, self.create_color_icon(color_hex))
			
			# 2. Den Text selbst in der Farbe einfärben
			self.tabs.tabBar().setTabTextColor(i, QColor(color_hex))

	def set_thumbnail(self, path):
		if path and os.path.exists(path):
			pix = QPixmap(path)
			self.thumb_label.setPixmap(pix.scaled(320, 180, Qt.AspectRatioMode.KeepAspectRatio))
		else:
			self.thumb_label.setText("Vorschau")

	def update_file_list(self, files):
		self.file_list.clear()
		self.file_list.addItems(files)

	def apply_row_filter(self, query):
		for i in range(self.file_list.count()):
			item = self.file_list.item(i)
			item.setHidden(query.lower() not in item.text().lower())
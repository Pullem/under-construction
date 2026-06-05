import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, 
							 QTableWidgetItem, QHeaderView, QLabel, QAbstractItemView)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

class ComparisonWindow(QWidget):
	def __init__(self, comparison_data):
		super().__init__()
		self.setWindowTitle("Forensic Comparison View")
		self.resize(1000, 600)
		self.setStyleSheet("background-color: #1a1a1a; color: white;")
		
		layout = QVBoxLayout()
		self.setLayout(layout)
		
		if not comparison_data:
			layout.addWidget(QLabel("Keine Daten zum Vergleich vorhanden."))
			return

		# Wir sammeln alle einzigartigen Keys über alle Dateien hinweg
		all_keys = set()
		for file_data in comparison_data.values():
			for category in file_data.values():
				if isinstance(category, dict):
					all_keys.update(category.keys())
		
		sorted_keys = sorted(list(all_keys))
		filenames = list(comparison_data.keys())

		# Tabelle aufbauen
		self.table = QTableWidget(len(sorted_keys), len(filenames))
		self.table.setVerticalHeaderLabels(sorted_keys)
		self.table.setHorizontalHeaderLabels(filenames)
		self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
		
		# --- FORENSIC LOCK: Editieren verbieten ---
		self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
		self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
		
		self.table.setStyleSheet("""
			QTableWidget { 
				gridline-color: #333; 
				background-color: #1e1e1e; 
				color: #ddd;
				border: none;
			}
			QHeaderView::section { 
				background-color: #2d2d2d; 
				color: #aaa; 
				padding: 5px; 
			}
		""")

		for col, fname in enumerate(filenames):
			file_meta = comparison_data[fname]
			for row, key in enumerate(sorted_keys):
				# Wert suchen
				value = "N/A"
				for cat_data in file_meta.values():
					if isinstance(cat_data, dict) and key in cat_data:
						value = cat_data[key]
						break
				
				item = QTableWidgetItem(str(value))
				
				# Markierung von Unterschieden
				if col > 0:
					prev_val = self.table.item(row, col-1).text()
					if str(value) != prev_val:
						# Ein dezentes Orange für Abweichungen (bessere Lesbarkeit als Gelb)
						item.setForeground(QColor("#FF7043")) 
				
				self.table.setItem(row, col, item)

		layout.addWidget(self.table)
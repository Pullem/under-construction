from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
							 QLabel, QLineEdit, QListWidget)

class FileExplorerPanel(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setup_ui()

	def setup_ui(self):
		layout = QVBoxLayout(self)
		# Ränder auf 0 setzen, damit es sich nahtlos ins Hauptfenster einfügt
		layout.setContentsMargins(0, 0, 0, 0) 

		# Obere Leiste (Fall laden & Einstellungen)
		top_bar = QHBoxLayout()
		self.btn_change_case = QPushButton("📁 Fall laden")
		self.btn_settings = QPushButton("⚙")
		self.btn_settings.setFixedWidth(35)
		top_bar.addWidget(self.btn_change_case, 1)
		top_bar.addWidget(self.btn_settings)
		layout.addLayout(top_bar)

		# Status & Import
		self.file_count_label = QLabel("Kein Fall geladen")
		self.file_count_label.setStyleSheet("color: #888; font-style: italic;")
		layout.addWidget(self.file_count_label)

		self.btn_import = QPushButton("📥 Beweismittel importieren")
		self.btn_import.setStyleSheet("background-color: #0e639c; color: white;")
		layout.addWidget(self.btn_import)
		
		# Dateiliste & Suche
		self.search_bar = QLineEdit()
		self.search_bar.setPlaceholderText("Dateien suchen...")
		layout.addWidget(self.search_bar)

		self.file_list = QListWidget()
		self.file_list.setStyleSheet("background-color: #252526; border: 1px solid #333;")
		layout.addWidget(self.file_list)

		# Bottom Action
		self.btn_scan = QPushButton("🔍 Analyse & Hash-Scan starten")
		layout.addWidget(self.btn_scan)
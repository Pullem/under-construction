from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, 
							 QPushButton, QLabel, QFileDialog)

class SettingsDialog(QDialog):
	"""
	Das Fenster für die Einstellungen (wird über das Zahnrad aufgerufen).
	Hier kann der User den Basis-Pfad für alle Fälle ändern.
	"""
	def __init__(self, current_config, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Einstellungen")
		self.setFixedSize(500, 200)
		self.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: 'Segoe UI';")
		
		layout = QVBoxLayout(self)
		
		layout.addWidget(QLabel("Basis-Ordner für alle Fälle (case_root):"))
		
		# Zeile für den Pfad + Durchsuchen-Button
		path_layout = QHBoxLayout()
		self.path_input = QLineEdit(current_config.get("case_root", ""))
		self.path_input.setStyleSheet("background-color: #252526; border: 1px solid #333; padding: 5px;")
		
		self.btn_browse = QPushButton("...")
		self.btn_browse.setFixedWidth(40)
		self.btn_browse.setStyleSheet("background-color: #333; color: white;")
		
		path_layout.addWidget(self.path_input)
		path_layout.addWidget(self.btn_browse)
		layout.addLayout(path_layout)
		
		layout.addStretch()
		
		# Speichern Button
		self.btn_save = QPushButton("Änderungen speichern")
		self.btn_save.setStyleSheet("""
			QPushButton { background-color: #0e639c; color: white; font-weight: bold; padding: 10px; border: none; }
			QPushButton:hover { background-color: #1177bb; }
		""")
		layout.addWidget(self.btn_save)
		
		# Signale verbinden
		self.btn_browse.clicked.connect(self.browse_path)
		self.btn_save.clicked.connect(self.accept)

	def browse_path(self):
		"""Öffnet den Windows-Ordner-Dialog."""
		path = QFileDialog.getExistingDirectory(self, "Wähle den Basis-Ordner")
		if path:
			self.path_input.setText(path)

	def get_settings(self):
		"""Gibt die eingegebenen Daten als Dictionary zurück."""
		return {"case_root": self.path_input.text()}
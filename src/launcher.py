import os
from PyQt6.QtWidgets import (
	QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
	QPushButton, QLineEdit, QLabel, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt
from src.model import ForensicModel


class CaseLauncher(QDialog):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("Forensic Lab – Fallverwaltung")
		self.setFixedSize(550, 550)

		self.model = ForensicModel()
		self.selected_case_id = None

		self.setup_ui()
		self.load_cases()
		self.apply_style()

	def setup_ui(self):
		layout = QVBoxLayout()

		# --- Neuer Fall ---
		layout.addWidget(QLabel("<b>Neuen Fall anlegen</b>"))
		new_layout = QVBoxLayout()

		self.txt_name = QLineEdit()
		self.txt_name.setPlaceholderText("Fallname…")

		self.txt_desc = QTextEdit()
		self.txt_desc.setPlaceholderText("Beschreibung…")

		btn_create = QPushButton("Fall erstellen")
		btn_create.clicked.connect(self.create_case)

		new_layout.addWidget(self.txt_name)
		new_layout.addWidget(self.txt_desc)
		new_layout.addWidget(btn_create)
		layout.addLayout(new_layout)

		layout.addSpacing(20)

		# --- Fälle anzeigen ---
		layout.addWidget(QLabel("<b>Bestehende Fälle</b>"))
		self.list_cases = QListWidget()
		self.list_cases.itemDoubleClicked.connect(self.open_case)
		layout.addWidget(self.list_cases)

		btn_open = QPushButton("Ausgewählten Fall öffnen")
		btn_open.clicked.connect(self.open_case)
		layout.addWidget(btn_open)

		self.setLayout(layout)

	def apply_style(self):
		self.setStyleSheet("""
			QDialog { background-color: #1a1a1a; color: white; }
			QLabel { color: #aaa; }
			QLineEdit, QTextEdit { background-color: #2d2d2d; color: white; border: 1px solid #444; padding: 5px; }
			QPushButton { background-color: #0e639c; color: white; border: none; padding: 8px; font-weight: bold; }
			QPushButton:hover { background-color: #1177bb; }
			QListWidget { background-color: #252526; color: #eee; border: 1px solid #333; }
		""")

	def load_cases(self):
		self.list_cases.clear()
		cases = self.model.load_cases()

		for c in cases:
			text = f"{c['project_name']} — {c['description']} — {c['created_at']}"
			item = QListWidgetItem(text)
			item.setData(Qt.ItemDataRole.UserRole, c['id'])
			self.list_cases.addItem(item)

	def create_case(self):
		name = self.txt_name.text().strip()
		desc = self.txt_desc.toPlainText().strip()

		if not name:
			QMessageBox.warning(self, "Fehler", "Fallname darf nicht leer sein.")
			return

		case_id = self.model.create_case(name, desc)
		self.load_cases()
		QMessageBox.information(self, "Erfolg", "Fall wurde angelegt.")

	def open_case(self):
		item = self.list_cases.currentItem()
		if not item:
			return

		self.selected_case_id = item.data(Qt.ItemDataRole.UserRole)
		self.accept()

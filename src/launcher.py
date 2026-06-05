import os
import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
							 QPushButton, QLineEdit, QLabel, QFileDialog)
from PyQt6.QtCore import Qt

class ProjectLauncher(QDialog):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("Forensic Lab - Projekt Manager")
		self.setFixedSize(450, 400)
		self.selected_project_path = None
		self.recent_projects_file = "recent_projects.json"
		
		self.setup_ui()
		self.load_recent_projects()
		self.apply_style()

	def setup_ui(self):
		layout = QVBoxLayout()
		
		# --- SEKTION: NEUES PROJEKT ---
		layout.addWidget(QLabel("<b>Neues Projekt erstellen</b>"))
		new_proj_layout = QHBoxLayout()
		self.txt_new_name = QLineEdit()
		self.txt_new_name.setPlaceholderText("Projektname eingeben...")
		btn_create = QPushButton("Erstellen")
		btn_create.clicked.connect(self.create_new_project)
		new_proj_layout.addWidget(self.txt_new_name)
		new_proj_layout.addWidget(btn_create)
		layout.addLayout(new_proj_layout)

		layout.addSpacing(20)

		# --- SEKTION: ZULETZT GEÖFFNET ---
		layout.addWidget(QLabel("<b>Zuletzt geöffnete Projekte</b>"))
		self.list_recent = QListWidget()
		self.list_recent.itemDoubleClicked.connect(self.open_selected_recent)
		layout.addWidget(self.list_recent)
		
		btn_open_recent = QPushButton("Ausgewähltes Projekt öffnen")
		btn_open_recent.clicked.connect(self.open_selected_recent)
		layout.addWidget(btn_open_recent)

		layout.addSpacing(10)

		# --- SEKTION: BESTEHENDES ÖFFNEN ---
		btn_browse = QPushButton("Anderes Projekt öffnen (.db)")
		btn_browse.clicked.connect(self.browse_project)
		layout.addWidget(btn_browse)

		self.setLayout(layout)

	def apply_style(self):
		self.setStyleSheet("""
			QDialog { background-color: #1a1a1a; color: white; }
			QLabel { color: #aaa; }
			QLineEdit { background-color: #2d2d2d; color: white; border: 1px solid #444; padding: 5px; }
			QPushButton { background-color: #0e639c; color: white; border: none; padding: 8px; font-weight: bold; }
			QPushButton:hover { background-color: #1177bb; }
			QListWidget { background-color: #252526; color: #eee; border: 1px solid #333; }
		""")

	def load_recent_projects(self):
		if os.path.exists(self.recent_projects_file):
			with open(self.recent_projects_file, "r") as f:
				projects = json.load(f)
				self.list_recent.addItems(projects)

	def save_to_recent(self, path):
		projects = []
		if os.path.exists(self.recent_projects_file):
			with open(self.recent_projects_file, "r") as f:
				projects = json.load(f)
		
		if path in projects: projects.remove(path)
		projects.insert(0, path)
		
		with open(self.recent_projects_file, "w") as f:
			json.dump(projects[:10], f) # Max 10 Einträge

	def create_new_project(self):
		name = self.txt_new_name.text().strip()
		if name:
			path, _ = QFileDialog.getSaveFileName(self, "Projekt speichern unter", f"{name}.db", "SQLite DB (*.db)")
			if path:
				self.selected_project_path = path
				self.save_to_recent(path)
				self.accept()

	def open_selected_recent(self):
		item = self.list_recent.currentItem()
		if item:
			self.selected_project_path = item.text()
			self.save_to_recent(self.selected_project_path)
			self.accept()

	def browse_project(self):
		path, _ = QFileDialog.getOpenFileName(self, "Projekt öffnen", "", "SQLite DB (*.db)")
		if path:
			self.selected_project_path = path
			self.save_to_recent(path)
			self.accept()
import os
import shutil # Für den physischen Import
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTreeView, 
							 QPushButton, QLabel, QSplitter, QMessageBox, 
							 QWidget, QFileSystemModel)
from PyQt6.QtCore import Qt, QDir

class ImportDialog(QDialog):
	def __init__(self, case_path, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Medien Import - Quelle wählen")
		self.resize(1200, 700)
		self.case_path = case_path
		self.selected_files = []
		self.target_folder = ""
		
		self.setup_ui()

	def setup_ui(self):
		layout = QVBoxLayout(self)
		self.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: 'Segoe UI';")

		header = QLabel("Links: Dateien/Ordner wählen | Rechts: Zielordner im Fall markieren")
		header.setStyleSheet("color: #0e639c; font-weight: bold; margin-bottom: 5px;")
		layout.addWidget(header)

		splitter = QSplitter(Qt.Orientation.Horizontal)

		# QUELLE (Links)
		self.source_model = QFileSystemModel()
		self.source_model.setRootPath("") 
		
		self.source_tree = QTreeView()
		self.source_tree.setModel(self.source_model)
		self.source_tree.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
		self.source_tree.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
		self.source_tree.setStyleSheet("""
			QTreeView { background-color: #252526; border: 1px solid #333; }
			QTreeView::item:selected:active { background-color: #e67e22; }
			QTreeView::item:selected:!active { background-color: #d35400; }
		""")
		splitter.addWidget(self.source_tree)

		# ZIEL (Rechts)
		self.target_model = QFileSystemModel()
		self.target_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot)
		self.target_model.setRootPath(self.case_path)
		
		self.target_tree = QTreeView()
		self.target_tree.setModel(self.target_model)
		self.target_tree.setRootIndex(self.target_model.index(self.case_path))
		for i in range(1, 4): self.target_tree.hideColumn(i)
		
		self.target_tree.setStyleSheet("""
			QTreeView { background-color: #252526; border: 1px solid #333; }
			QTreeView::item:selected { background-color: #0e639c; }
		""")
		splitter.addWidget(self.target_tree)

		layout.addWidget(splitter)

		btn_layout = QHBoxLayout()
		self.btn_import = QPushButton("Auswahl importieren")
		self.btn_import.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold; padding: 12px;")
		btn_layout.addStretch()
		btn_layout.addWidget(self.btn_import)
		layout.addLayout(btn_layout)

		self.btn_import.clicked.connect(self.handle_import)

	def handle_import(self):
		# Gewählte Quelldateien sammeln
		indices = self.source_tree.selectionModel().selectedRows()
		self.selected_files = [self.source_model.filePath(i) for i in indices if not self.source_model.isDir(i)]
		
		# Zielordner ermitteln
		target_index = self.target_tree.currentIndex()
		self.target_folder = self.target_model.filePath(target_index)

		# Validierung
		if not self.selected_files:
			QMessageBox.warning(self, "Hinweis", "Bitte wählen Sie links Dateien aus (keine Ordner).")
			return
		if not self.target_folder or not os.path.isdir(self.target_folder):
			QMessageBox.warning(self, "Hinweis", "Bitte wählen Sie rechts einen Zielordner aus.")
			return

		self.accept() # Schließt den Dialog und gibt QDialog.DialogCode.Accepted zurück

	def get_data(self):
		return self.selected_files, self.target_folder
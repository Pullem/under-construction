import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
	QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
	QPushButton, QLineEdit, QLabel, QTextEdit, QMessageBox, QProgressDialog
)
from PyQt6.QtCore import Qt
from src.model import ForensicModel
from src.utils.logging_config import setup_logging, set_log_context
from src.utils.config_validator import ConfigValidator
from src.utils.errors import ErrorSeverity


class CaseLauncher(QDialog):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("Forensic Lab – Fallverwaltung")
		self.setFixedSize(550, 550)

		setup_logging(console_level=logging.INFO)
		self.logger = logging.getLogger(__name__)

		self.model = ForensicModel()
		self.selected_case_id = None

		# Validate config before showing UI
		if not self._validate_and_fix_config():
			self.reject()
			return

		self.finished.connect(self._on_finished)

		self.setup_ui()
		self.load_cases()
		self.apply_style()

	def _validate_and_fix_config(self) -> bool:
		"""Validate config, run setup dialogs if needed. Returns True if ready."""
		validator = ConfigValidator(Path(__file__).resolve().parent.parent.parent)
		result = validator.validate_all(self.model)

		if result.warnings:
			for w in result.warnings:
				self.logger.warning("Config validation warning: %s", w)

		if result.has_errors:
			# Try to fix common issues via setup dialogs
			if self._run_required_setups():
				# Re-validate after setup
				result = validator.validate_all(self.model)
				if result.has_errors:
					msgs = "\n\n".join(str(e) for e in result.errors)
					QMessageBox.critical(self, "Konfigurationsfehler",
						f"Konfiguration unvollständig:\n\n{msgs}\n\nProgramm wird beendet.")
					return False
			else:
				return False

		return True

	def _run_required_setups(self) -> bool:
		"""Run DB and/or case_root setup dialogs. Returns True if all completed."""
		# DB setup
		if not self.model.db_config.get('password'):
			if not self._run_db_setup():
				return False

		# Project root setup
		PROJECT_INI = Path(__file__).resolve().parent.parent.parent / "config" / "project.ini"
		if not PROJECT_INI.exists():
			if not self._run_case_root_setup():
				return False

		return True

	def _run_db_setup(self) -> bool:
		from PyQt6.QtWidgets import QInputDialog, QLineEdit, QMessageBox

		root_pw, ok_root = QInputDialog.getText(
			self, "Initiales Setup",
			"MariaDB 'root' Passwort eingeben:",
			echo=QLineEdit.EchoMode.Password
		)
		if not (ok_root and root_pw):
			return False

		user_pw, ok_user = QInputDialog.getText(
			self, "Initiales Setup",
			"Neues Passwort für den Analyzer-User (va_user) festlegen:",
			echo=QLineEdit.EchoMode.Password
		)
		if not (ok_user and user_pw):
			return False

		try:
			self.model.initial_root_setup(root_pw, user_pw)
			QMessageBox.information(self, "Setup Erfolg",
				"Datenbank wurde erfolgreich konfiguriert und mariadb.ini erstellt.")
			return True
		except Exception as e:
			QMessageBox.critical(self, "Setup Fehler", f"Fehler beim Erstellen der Datenbank:\n{e}")
			return False

	def _run_case_root_setup(self) -> bool:
		from PyQt6.QtWidgets import QFileDialog, QMessageBox
		from configparser import ConfigParser

		PROJECT_INI = Path(__file__).resolve().parent.parent.parent / "config" / "project.ini"

		QMessageBox.information(self, "Projekt-Speicherort",
			"Bitte wählen Sie den Standard-Speicherort für alle Fälle aus.")

		folder = QFileDialog.getExistingDirectory(self, "Speicherort für Fälle auswählen")
		if not folder:
			QMessageBox.critical(self, "Abbruch", "Es wurde kein Speicherort gewählt.")
			return False

		parser = ConfigParser()
		parser.add_section("settings")
		parser.set("settings", "case_root", str(Path(folder).resolve()))

		PROJECT_INI.parent.mkdir(parents=True, exist_ok=True)
		with open(PROJECT_INI, "w") as f:
			parser.write(f)

		self.model.load_project_config()
		QMessageBox.information(self, "Gespeichert", f"Standard-Speicherort wurde gesetzt:\n{folder}")
		return True

	def _on_finished(self, result):
		self.model.close_pool()

	def setup_ui(self):
		layout = QVBoxLayout()

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
		self.logger.info("Loading case list")
		self.list_cases.clear()
		cases = self.model.load_cases()

		for c in cases:
			text = f"{c['project_name']} — {c['description']} — {c['created_at']}"
			item = QListWidgetItem(text)
			item.setData(Qt.ItemDataRole.UserRole, c['id'])
			self.list_cases.addItem(item)

		self.logger.info("Loaded %d cases", len(cases))

	def create_case(self):
		name = self.txt_name.text().strip()
		desc = self.txt_desc.toPlainText().strip()

		if not name:
			QMessageBox.warning(self, "Fehler", "Fallname darf nicht leer sein.")
			return

		self.logger.info("Creating case: %s", name)
		case_id = self.model.create_case(name, desc)
		self.load_cases()
		self.logger.info("Case created with ID: %s", case_id)
		QMessageBox.information(self, "Erfolg", "Fall wurde angelegt.")

	def open_case(self):
		item = self.list_cases.currentItem()
		if not item:
			return

		self.selected_case_id = item.data(Qt.ItemDataRole.UserRole)
		self.logger.info("Opening case ID: %s", self.selected_case_id)
		self.accept()
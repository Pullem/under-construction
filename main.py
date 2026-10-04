import sys
import os
import faulthandler
import argparse
import logging
from pathlib import Path

faulthandler.enable()

from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox, QLineEdit, QProgressDialog

from configparser import ConfigParser
from src.model import ForensicModel, BASE_DIR
from src.view import ForensicView
from src.presenter import ForensicPresenter
from src.utils.logging_config import setup_logging, set_log_context
from src.utils.config_validator import ConfigValidator
from src.utils.errors import AppError, ErrorSeverity

PROJECT_INI = BASE_DIR / "config" / "project.ini"


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Video Forensic Analyzer")
	parser.add_argument("--verbose", "-v", action="store_true", help="Enable console INFO logging")
	parser.add_argument("--debug", action="store_true", help="Enable console DEBUG logging")
	parser.add_argument("--skip-validation", action="store_true", help="Skip startup config validation (not recommended)")
	return parser.parse_args()


def run_initial_db_setup(model: ForensicModel) -> bool:
	"""Run initial DB setup dialog. Returns True on success."""
	root_pw, ok_root = QInputDialog.getText(
		None, "Initiales Setup",
		"MariaDB 'root' Passwort eingeben:",
		echo=QLineEdit.EchoMode.Password
	)

	if not (ok_root and root_pw):
		return False

	user_pw, ok_user = QInputDialog.getText(
		None, "Initiales Setup",
		"Neues Passwort für den Analyzer-User (va_user) festlegen:",
		echo=QLineEdit.EchoMode.Password
	)

	if not (ok_user and user_pw):
		return False

	try:
		model.initial_root_setup(root_pw, user_pw)
		QMessageBox.information(
			None, "Setup Erfolg",
			"Datenbank wurde erfolgreich konfiguriert und mariadb.ini erstellt."
		)
		return True
	except Exception as e:
		QMessageBox.critical(
			None, "Setup Fehler",
			f"Fehler beim Erstellen der Datenbank:\n{e}"
		)
		return False


def run_case_root_setup(model: ForensicModel) -> bool:
	"""Run case root selection dialog. Returns True on success."""
	from PyQt6.QtWidgets import QFileDialog

	QMessageBox.information(
		None,
		"Projekt-Speicherort",
		"Bitte wählen Sie den Standard-Speicherort für alle Fälle aus."
	)

	folder = QFileDialog.getExistingDirectory(
		None,
		"Speicherort für Fälle auswählen"
	)

	if not folder:
		QMessageBox.critical(
			None,
			"Abbruch",
			"Es wurde kein Speicherort gewählt. Programm wird beendet."
		)
		return False

	parser = ConfigParser()
	parser.add_section("settings")
	parser.set("settings", "case_root", str(Path(folder).resolve()))

	PROJECT_INI.parent.mkdir(parents=True, exist_ok=True)
	with open(PROJECT_INI, "w") as f:
		parser.write(f)

	model.load_project_config()

	QMessageBox.information(
		None,
		"Gespeichert",
		f"Standard-Speicherort wurde gesetzt:\n{folder}"
	)
	return True


def validate_startup_config(model: ForensicModel, skip_validation: bool = False) -> bool:
	"""Validate all startup configuration. Shows dialogs for errors. Returns True if valid."""
	if skip_validation:
		logging.warning("Startup validation skipped via --skip-validation")
		return True

	validator = ConfigValidator(BASE_DIR)
	result = validator.validate_all(model)

	if result.warnings:
		for w in result.warnings:
			logging.warning("Startup validation warning: %s", w)

	if result.has_errors:
		# Build error message
		error_msgs = []
		for err in result.errors:
			error_msgs.append(str(err))

		# Show detailed error dialog
		msg = (
			"Konfigurationsfehler beim Start:\n\n" +
			"\n\n".join(error_msgs) +
			"\n\nDas Programm kann nicht gestartet werden. "
			"Bitte beheben Sie die oben genannten Probleme."
		)
		logging.critical("Startup validation failed: %s", "; ".join(error_msgs))
		QMessageBox.critical(None, "Konfigurationsfehler", msg)
		return False

	logging.info("Startup validation passed")
	return True


def main() -> None:
	args = parse_args()

	console_level = logging.WARNING
	if args.debug:
		console_level = logging.DEBUG
	elif args.verbose:
		console_level = logging.INFO

	setup_logging(console_level=console_level)

	app = QApplication(sys.argv)

	def excepthook(typ, val, tb):
		import traceback
		msg = "".join(traceback.format_exception(typ, val, tb))
		logging.critical("UNHANDLED EXCEPTION:\n%s", msg)
	sys.excepthook = excepthook

	# 0) MODEL LADEN
	model = ForensicModel()

	# 1) DB-SETUP (wenn mariadb.ini fehlt oder unvollständig)
	if not model.db_config.get('password'):
		if not run_initial_db_setup(model):
			return

	# 1b) PROJECT-SPEICHERORT (wenn project.ini fehlt)
	if not PROJECT_INI.exists():
		if not run_case_root_setup(model):
			return

	# 2) VALIDIERUNG (nach Setup, vor GUI)
	if not validate_startup_config(model, skip_validation=args.skip_validation):
		return

	# 3) LOGGING für aktiven Fall konfigurieren
	if model.current_case_path:
		setup_logging(case_path=model.current_case_path, console_level=console_level)
		set_log_context(case_id=model.current_case_id)

	# 4) GUI STARTEN
	try:
		view = ForensicView()
		presenter = ForensicPresenter(model, view)

		app.aboutToQuit.connect(lambda: model.close_pool())

		view.show()
		sys.exit(app.exec())
	except Exception as e:
		logging.critical("Start Fehler: %s", e, exc_info=True)
		QMessageBox.critical(
			None, "Start Fehler",
			f"Anwendung konnte nicht gestartet werden:\n{e}"
		)


if __name__ == "__main__":
	main()
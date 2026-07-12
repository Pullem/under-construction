import sys, os, faulthandler
faulthandler.enable()
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox, QLineEdit

from configparser import ConfigParser
from src.model import ForensicModel, BASE_DIR
from src.view import ForensicView
from src.presenter import ForensicPresenter

 
PROJECT_INI = BASE_DIR / "config" / "project.ini"


def main():
	app = QApplication(sys.argv)

	def excepthook(typ, val, tb):
		import traceback
		msg = "".join(traceback.format_exception(typ, val, tb))
		print(f"UNHANDLED EXCEPTION:\n{msg}", file=sys.stderr)
	sys.excepthook = excepthook

	# ---------------------------------------------------------
	# 0) MODEL LADEN (für DB-Setup)
	# ---------------------------------------------------------
	model = ForensicModel()

	# ---------------------------------------------------------
	# 1) DB-SETUP (wenn mariadb.ini fehlt)
	# ---------------------------------------------------------
	if not model.db_config.get('password'):
		root_pw, ok_root = QInputDialog.getText(
			None, "Initiales Setup",
			"MariaDB 'root' Passwort eingeben:",
			echo=QLineEdit.EchoMode.Password
		)

		if ok_root and root_pw:
			user_pw, ok_user = QInputDialog.getText(
				None, "Initiales Setup",
				"Neues Passwort für den Analyzer-User (va_user) festlegen:",
				echo=QLineEdit.EchoMode.Password
			)

			if ok_user and user_pw:
				try:
					model.initial_root_setup(root_pw, user_pw)
					QMessageBox.information(
						None, "Setup Erfolg",
						"Datenbank wurde erfolgreich konfiguriert und mariadb.ini erstellt."
					)
				except Exception as e:
					QMessageBox.critical(
						None, "Setup Fehler",
						f"Fehler beim Erstellen der Datenbank:\n{e}"
					)
					return
			else:
				return
		else:
			return

	# ---------------------------------------------------------
	# 1b) Projekt-Speicherort abfragen, wenn projekt.ini fehlt
	# ---------------------------------------------------------
	if not PROJECT_INI.exists():
		from PyQt6.QtWidgets import QFileDialog
		from configparser import ConfigParser

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
			return

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



	# ---------------------------------------------------------
	# 2) GUI STARTEN (ohne Fall-Vorauswahl – über Tab 1 steuerbar)
	# ---------------------------------------------------------
	try:
		view = ForensicView()
		presenter = ForensicPresenter(model, view)

		view.show()
		sys.exit(app.exec())
	except Exception as e:
		QMessageBox.critical(
			None, "Start Fehler",
			f"Anwendung konnte nicht gestartet werden:\n{e}"
		)


if __name__ == "__main__":
	main()

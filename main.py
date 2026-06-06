import sys, os

from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox, QLineEdit

from configparser import ConfigParser
from src.launcher import CaseLauncher
from src.model import ForensicModel
from src.view import ForensicView
from src.presenter import ForensicPresenter


def main():
	app = QApplication(sys.argv)

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
	if not os.path.exists("config/project.ini"):
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
		parser.set("settings", "case_root", folder)

		with open("config/project.ini", "w") as f:
			parser.write(f)

		QMessageBox.information(
			None,
			"Gespeichert",
			f"Standard-Speicherort wurde gesetzt:\n{folder}"
		)



	# ---------------------------------------------------------
	# 2) LAUNCHER STARTEN (DB ist jetzt garantiert vorhanden)
	# ---------------------------------------------------------
	launcher = CaseLauncher()
	if launcher.exec() != launcher.DialogCode.Accepted:
		return

	case_id = launcher.selected_case_id
	if not case_id:
		return

	# ---------------------------------------------------------
	# 3) FALL LADEN
	# ---------------------------------------------------------
	model.load_case(case_id)

	# ---------------------------------------------------------
	# 4) GUI STARTEN
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

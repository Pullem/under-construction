import sys
from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox, QLineEdit

from src.launcher import CaseLauncher
from src.model import ForensicModel
from src.view import ForensicView
from src.presenter import ForensicPresenter


def main():
	# QApplication starten
	app = QApplication(sys.argv)

	# ---------------------------------------------------------
	# 1) LAUNCHER STARTEN
	# ---------------------------------------------------------
	launcher = CaseLauncher()
	if launcher.exec() != launcher.DialogCode.Accepted:
		return  # User hat abgebrochen

	case_id = launcher.selected_case_id
	if not case_id:
		return

	# ---------------------------------------------------------
	# 2) MODEL LADEN (Fallbasiert)
	# ---------------------------------------------------------
	model = ForensicModel()
	model.load_case(case_id)

	# ---------------------------------------------------------
	# 3) DB-SETUP (nur wenn mariadb.ini fehlt)
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
	# 4) PRESENTER STARTEN
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

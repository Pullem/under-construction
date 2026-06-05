import sys
import os
from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox, QLineEdit
from src.model import ForensicModel
from src.view import ForensicView
from src.presenter import ForensicPresenter

def main():
	# 1. App-Instanz erstellen
	app = QApplication(sys.argv)
	
	# 2. Model und View initialisieren
	# Das Model lädt beim Start vorhandene Configs aus /config
	model = ForensicModel()
	view = ForensicView()
	
	# 3. SETUP LOGIK: Prüfen, ob Datenbank-Zugang existiert
	if not model.db_config.get('password'):
		# Schritt A: Root Passwort abfragen (um User/DB anzulegen)
		root_pw, ok_root = QInputDialog.getText(
			None, "Initiales Setup", 
			"MariaDB 'root' Passwort eingeben:", 
			echo=QLineEdit.EchoMode.Password
		)
		
		if ok_root and root_pw:
			# Schritt B: Gewünschtes Passwort für den neuen 'va_user' abfragen
			user_pw, ok_user = QInputDialog.getText(
				None, "Initiales Setup", 
				"Neues Passwort für den Analyzer-User (va_user) festlegen:", 
				echo=QLineEdit.EchoMode.Password
			)
			
			if ok_user and user_pw:
				try:
					# Datenbank, User und Berechtigungen über das Model anlegen
					model.initial_root_setup(root_pw, user_pw)
					QMessageBox.information(None, "Setup Erfolg", 
										  "Datenbank wurde erfolgreich konfiguriert und mariadb.ini erstellt.")
				except Exception as e:
					QMessageBox.critical(None, "Setup Fehler", 
									   f"Fehler beim Erstellen der Datenbank:\n{str(e)}")
					return
			else:
				return # Abbruch durch User
		else:
			return # Abbruch durch User

	# 4. START DER ANWENDUNG
	# Der Presenter wird erst erstellt, wenn die DB-Verbindung (Config) sicher steht
	try:
		presenter = ForensicPresenter(model, view)
		
		# Hauptfenster anzeigen
		view.show()
		
		# Event Loop starten
		sys.exit(app.exec())
		
	except Exception as e:
		print(f"Kritischer Fehler beim Starten des Presenters: {e}")
		QMessageBox.critical(None, "Start Fehler", f"Anwendung konnte nicht gestartet werden:\n{e}")

if __name__ == "__main__":
	main()
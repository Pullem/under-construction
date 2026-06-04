import sys
import os
import mariadb
from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog, QLineEdit
from src.model import ForensicModel
from src.view import ForensicView
from src.presenter import ForensicPresenter

def bootstrap():
	for d in ['config', 'evidence_input']:
		if not os.path.exists(d): os.makedirs(d)

def run_db_setup(model):
	pw, ok = QInputDialog.getText(None, "Setup", "MariaDB Root Passwort erforderlich:", QLineEdit.EchoMode.Password)
	if ok:
		try:
			model.initial_root_setup(pw)
			return True
		except Exception as e:
			QMessageBox.critical(None, "Fehler", str(e))
	return False

def main():
	bootstrap()
	app = QApplication(sys.argv)
	app.setStyle("Fusion")
	
	model = ForensicModel()
	
	# Connection Check
	while True:
		try:
			conn = model.get_connection()
			conn.close()
			break
		except Exception as e:
			if not run_db_setup(model): sys.exit()

	view = ForensicView()
	presenter = ForensicPresenter(model, view)
	view.show()
	sys.exit(app.exec())

if __name__ == "__main__":
	main()
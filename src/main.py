import sys
from PyQt6.QtWidgets import QApplication
from models.core_model import ForensicModel
from views.main_window import ForensicView
from presenters.main_presenter import ForensicPresenter

def main():
	app = QApplication(sys.argv)
	
	# 1. Model (Daten)
	model = ForensicModel()
	
	# 2. View (Optik)
	view = ForensicView()
	
	# 3. Presenter (Verbindung)
	presenter = ForensicPresenter(model, view)
	
	view.show()
	sys.exit(app.exec())

if __name__ == "__main__":
	main()
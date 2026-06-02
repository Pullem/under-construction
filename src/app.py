import sys
from PyQt6.QtWidgets import QApplication
from main_window import MainWindow
from utils.config import Config

def main():
    app = QApplication(sys.argv)
    cfg = Config("config/project.ini")
    window = MainWindow(cfg)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel
from PyQt6.QtCore import pyqtSignal
from views.file_list_view import FileListView
from views.media_info_view import MediaInfoDetailView

class MainView(QWidget):
    start_import_requested = pyqtSignal()
    open_config_requested = pyqtSignal()
    scan_requested = pyqtSignal()
    search_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.btn_start = QPushButton("Start Import")
        self.btn_start.clicked.connect(lambda: self.start_import_requested.emit())
        top.addWidget(self.btn_start)

        self.btn_config = QPushButton("Konfiguration")
        self.btn_config.clicked.connect(lambda: self.open_config_requested.emit())
        top.addWidget(self.btn_config)

        self.btn_scan = QPushButton("Scan Watchfolder")
        self.btn_scan.clicked.connect(lambda: self.scan_requested.emit())
        top.addWidget(self.btn_scan)

        top.addStretch()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Suche (Parameter oder Wert)...")
        self.search.textChanged.connect(lambda t: self.search_changed.emit(t))
        top.addWidget(QLabel("Suche:"))
        top.addWidget(self.search)

        layout.addLayout(top)

        self.file_list = FileListView()
        layout.addWidget(self.file_list)

        self.media_info = MediaInfoDetailView()
        layout.addWidget(self.media_info)

    def show_message(self, text):
        # einfache Anzeige, Presenter kann erweitern
        print(text)

    def refresh_file_list(self):
        self.file_list.reload()

    def open_file_in_editor(self, path):
        import subprocess, sys
        if sys.platform.startswith("win"):
            subprocess.Popen(["notepad.exe", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def apply_search(self, text):
        self.media_info.apply_search(text)

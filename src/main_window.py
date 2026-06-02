from PyQt6.QtWidgets import QMainWindow, QToolBar, QStatusBar
from PyQt6.QtGui import QAction
import logging
from presenters.main_presenter import MainPresenter
from views.main_view import MainView
from utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        setup_logging()
        self.setWindowTitle("video-forensik - analyzer")
        self.view = MainView()
        self.setCentralWidget(self.view)
        self.presenter = MainPresenter(self.view, config)
        self._init_ui()

    def _init_ui(self):
        tb = QToolBar("Main")
        self.addToolBar(tb)

        start_action = QAction("Start Import", self)
        start_action.triggered.connect(self.presenter.on_start_import)
        tb.addAction(start_action)

        cfg_action = QAction("Konfiguration", self)
        cfg_action.triggered.connect(self.presenter.on_open_config)
        tb.addAction(cfg_action)

        scan_action = QAction("Scan Watchfolder", self)
        scan_action.triggered.connect(self.presenter.on_scan_watchfolder)
        tb.addAction(scan_action)

        self.setStatusBar(QStatusBar(self))

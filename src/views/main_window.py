from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter
from PyQt6.QtCore import Qt

# Wir importieren unsere neuen Lego-Steine
from .panels.file_explorer import FileExplorerPanel
from .panels.media_preview import MediaPreviewPanel
from .panels.metadata_tabs import MetadataPanel

class ForensicView(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("Forensic Lab Pro")
		self.resize(1400, 900)
		self.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
		
		# Bausteine instanziieren
		self.explorer_panel = FileExplorerPanel()
		self.preview_panel = MediaPreviewPanel()
		self.metadata_panel = MetadataPanel()
		
		self.setup_ui()

	def setup_ui(self):
		# Der Haupt-Splitter (Links <-> Rechts)
		main_splitter = QSplitter(Qt.Orientation.Horizontal)
		
		# Linke Seite hinzufügen
		main_splitter.addWidget(self.explorer_panel)
		
		# Der rechte Splitter (Oben <-> Unten)
		right_splitter = QSplitter(Qt.Orientation.Vertical)
		right_splitter.addWidget(self.preview_panel)
		right_splitter.addWidget(self.metadata_panel)
		
		# Rechte Seite dem Haupt-Splitter hinzufügen
		main_splitter.addWidget(right_splitter)
		
		# Größenverhältnisse setzen (z.B. Links 1/4, Rechts 3/4 Platz)
		main_splitter.setSizes([350, 1050])
		
		# Das Ganze in die Mitte des Fensters setzen
		self.setCentralWidget(main_splitter)
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTextEdit

class MetadataPanel(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setup_ui()

	def setup_ui(self):
		layout = QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)
		
		self.tabs = QTabWidget()
		self.tabs.setStyleSheet("QTabWidget::pane { border: 1px solid #333; }")
		
		# Tab 1: Basis-Info
		self.info_text = QTextEdit()
		self.info_text.setReadOnly(True)
		self.tabs.addTab(self.info_text, "Datei-Info")
		
		# Tab 2: Hashes
		self.hash_text = QTextEdit()
		self.hash_text.setReadOnly(True)
		self.tabs.addTab(self.hash_text, "Hashes (MD5/SHA256)")
		
		# Tab 3: EXIF / Metadaten
		self.exif_text = QTextEdit()
		self.exif_text.setReadOnly(True)
		self.tabs.addTab(self.exif_text, "Media Info / EXIF")
		
		layout.addWidget(self.tabs)
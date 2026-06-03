from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

class MediaPreviewPanel(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setup_ui()

	def setup_ui(self):
		layout = QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)
		
		self.preview_label = QLabel("Kein Medium zur Vorschau ausgewählt")
		self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.preview_label.setStyleSheet("""
			background-color: #000000; 
			color: #555555; 
			border: 1px solid #333;
			font-size: 16px;
		""")
		
		layout.addWidget(self.preview_label)
		
		# Später kommen hier Player-Controls (Play, Pause, Slider) hinzu
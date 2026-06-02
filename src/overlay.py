from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt

class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowFlags(self.windowFlags())
        self.label = QLabel("Loading...", self)
        self.label.setStyleSheet("color: white; background: rgba(0,0,0,0.6); padding: 8px; border-radius: 6px;")
        layout = QVBoxLayout(self)
        layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.hide()

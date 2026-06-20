import os
from PyQt6.QtGui import QPixmap

from .main_window import MainWindowMixin
from .metadata_tabs import MetadataTabMixin


class ForensicView(MainWindowMixin, MetadataTabMixin):
	def __init__(self):
		super().__init__()
		self.setup_ui()
		self.apply_dark_style()

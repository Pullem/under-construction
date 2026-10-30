"""Hauptfenster: Signale, Konstruktor und Tab-Setup."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout,
							 QStackedWidget, QTabBar)
from PyQt6.QtCore import pyqtSignal

from .flat_tab_bar import FlatTabBar
from .tabs import (build_case_tab, build_import_tab, build_metadata_tab,
	build_videos_tab, build_bilder_tab, build_settings_tab,
	build_hex_tab, build_analysis_tab, build_placeholder_tab)
from .mixins import (DarkStyleMixin, FFmpegControlsMixin, SettingsMixin,
	HexControlsMixin, CaseControlsMixin, MediaListMixin)


class MainWindowMixin(DarkStyleMixin, FFmpegControlsMixin, SettingsMixin,
		HexControlsMixin, CaseControlsMixin, MediaListMixin, QMainWindow):
	scan_requested = pyqtSignal()
	search_changed = pyqtSignal(str)
	file_selected = pyqtSignal(str)
	import_media_requested = pyqtSignal()
	case_selected = pyqtSignal(object)
	create_case_requested = pyqtSignal(str, str, object, object)
	save_settings_requested = pyqtSignal(str)
	update_db_password_requested = pyqtSignal(str)
	open_timeline_requested = pyqtSignal()
	ffmpeg_run_requested = pyqtSignal(str, str, str, str)
	ffmpeg_abort_requested = pyqtSignal()
	ffprobe_analyse_requested = pyqtSignal(str, str, str)
	sensitivity_requested = pyqtSignal(str, str)
	ffmpeg_lossless_trim_requested = pyqtSignal(str, int, int, str)

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.setWindowTitle("Video Forensic Lab - Analyzer")
		self.resize(1920, 1080)
		self._raw_db_password = ""
		self._pw_visible = False
		self._raw_root_password = ""
		self._root_pw_visible = False
		self._is_analysis_built = False
		self._case_path = ""
		self.ffmpeg_input_path = ""

	def setup_ui(self):
		central = QWidget()
		self.setCentralWidget(central)
		main_layout = QHBoxLayout(central)
		main_layout.setContentsMargins(0, 0, 0, 0)
		main_layout.setSpacing(0)

		# --- LINKS: Navigations-Tabbar ---
		self.nav_bar = FlatTabBar()
		self.nav_bar.setShape(QTabBar.Shape.RoundedWest)
		self.nav_bar.setFixedWidth(200)

		# --- MITTE: Inhaltsbereich ---
		self.content_stack = QStackedWidget()

		# Tabs + Inhalt bauen
		build_case_tab(self)
		build_import_tab(self)
		build_metadata_tab(self)
		build_videos_tab(self)
		build_bilder_tab(self)
		build_hex_tab(self)
		build_analysis_tab(self)
		build_placeholder_tab(self, "Export")
		build_settings_tab(self)

		# Navigation verknüpfen
		self.nav_bar.currentChanged.connect(self.content_stack.setCurrentIndex)

		self._refresh_timezone()
		self._update_gpu_status()

		main_layout.addWidget(self.nav_bar)
		main_layout.addWidget(self.content_stack, 1)

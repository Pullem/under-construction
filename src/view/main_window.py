"""Hauptfenster: Signale, Konstruktor und Baum-Navigation."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout,
							 QStackedWidget, QTreeWidget, QTreeWidgetItem)
from PyQt6.QtCore import pyqtSignal, Qt

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

		# --- LINKS: Navigations-Baum (ersetzt FlatTabBar) ---
		self.nav_tree = QTreeWidget()
		self.nav_tree.setHeaderHidden(True)
		self.nav_tree.setFixedWidth(200)
		self.nav_tree.setStyleSheet(
			"QTreeWidget { background-color: #1a1a1a; border: none; }"
			"QTreeWidget::item { color: #9a9a9a; padding: 8px; height: 32px; }"
			"QTreeWidget::item:selected { color: #ffffff; background-color: #252526; }"
			"QTreeWidget::item:hover { background-color: #242424; }"
			"QTreeWidget::branch { background: transparent; }"
		)

		# --- MITTE: Inhaltsbereich ---
		self.content_stack = QStackedWidget()

		# Tabs + Inhalt bauen (reihenfolge bestimmt Stack-Index)
		build_case_tab(self)          # 0
		build_import_tab(self)        # 1
		build_metadata_tab(self)      # 2
		build_videos_tab(self)        # 3
		build_bilder_tab(self)        # 4 (Analysen), 5 (Processing)
		build_hex_tab(self)           # 6
		build_analysis_tab(self)      # 7
		build_placeholder_tab(self, "Export")  # 8
		build_settings_tab(self)      # 9

		# Baum-Navigation aufbauen
		self._build_nav_tree()

		# Klick im Baum wechselt Stack-Seite
		self.nav_tree.itemClicked.connect(self._on_tree_item_clicked)

		self._refresh_timezone()
		self._update_gpu_status()

		main_layout.addWidget(self.nav_tree)
		main_layout.addWidget(self.content_stack, 1)

	def _build_nav_tree(self):
		"""Baut die Baum-Navigation mit expandierbarer 'Bilder'-Kategorie."""
		# Jeder Eintrag ist entweder:
		#   (name, stack_idx) – einfacher Eintrag
		#   {"name": ..., "expanded": bool, "children": [(name, stack_idx), ...]} – Kategorie
		nav_items = [
			("Fallübersicht", 0),
			("Import", 1),
			("Metadaten", 2),
			{"name": "Bilder", "expanded": True,
			 "children": [("Analysen", 4), ("Processing", 5)]},
			("Videos", 3),
			("Hex-Viewer", 6),
			("Auswertung", 7),
			("Export", 8),
			("Einstellungen", 9),
		]

		for entry in nav_items:
			if isinstance(entry, tuple):
				name, stack_idx = entry
				item = QTreeWidgetItem([name])
				item.setData(0, Qt.ItemDataRole.UserRole, stack_idx)
				self.nav_tree.addTopLevelItem(item)
			elif isinstance(entry, dict):
				cat_item = QTreeWidgetItem([entry["name"]])
				cat_item.setData(0, Qt.ItemDataRole.UserRole, -1)
				cat_item.setExpanded(entry.get("expanded", True))
				self.nav_tree.addTopLevelItem(cat_item)
				for child_name, child_idx in entry.get("children", []):
					child = QTreeWidgetItem([child_name])
					child.setData(0, Qt.ItemDataRole.UserRole, child_idx)
					cat_item.addChild(child)

		# Ersten Eintrag auswählen (Fallübersicht)
		self.nav_tree.setCurrentItem(
			self.nav_tree.topLevelItem(0))
		self.content_stack.setCurrentIndex(0)

	def _on_tree_item_clicked(self, item, column):
		"""Wechselt zur Stack-Seite des geklickten Tree-Items."""
		stack_idx = item.data(0, Qt.ItemDataRole.UserRole)
		if stack_idx is not None and stack_idx >= 0:
			self.content_stack.setCurrentIndex(stack_idx)
			# Merke welchen Bilder-Subtab wir haben (für active_media_prefix)
			if stack_idx in (4, 5):
				self._current_bilder_subtab = stack_idx - 4

	def set_active_bilder_subtab(self, subtab_index):
		"""Wird von Presenter aufgerufen, um den aktiven Bilder-Subtab zu markieren."""
		self._current_bilder_subtab = subtab_index
		# Baum-Selektion aktualisieren
		bilder_item = self.nav_tree.topLevelItem(3)  # "Bilder" ist 4. Top-Level (zwischen Metadaten und Videos)
		if bilder_item:
			child = bilder_item.child(subtab_index)
			if child:
				self.nav_tree.setCurrentItem(child)

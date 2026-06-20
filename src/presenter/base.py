import json
from PyQt6.QtCore import QThreadPool, Qt


class PresenterBase:
	def __init__(self, model, view, **kwargs):
		super().__init__(**kwargs)
		self.model = model
		self.view = view
		self.threadpool = QThreadPool()

		self.view.scan_requested.connect(self.handle_scan)
		self.view.search_changed.connect(self.handle_search)
		self.view.file_selected.connect(self.load_file_details)
		self.view.tabs.currentChanged.connect(self.track_tab_change)
		self.view.nav_bar.currentChanged.connect(self.handle_nav_tab_change)

		self.view.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
		self.view.file_list.customContextMenuRequested.connect(self.show_context_menu)

		if hasattr(self.view, "import_media_requested"):
			self.view.import_media_requested.connect(self.open_import_dialog)

		if hasattr(self.view, "case_selected"):
			self.view.case_selected.connect(self.handle_case_selected)

		if hasattr(self.view, "create_case_requested"):
			self.view.create_case_requested.connect(self.handle_create_case)

		self.case_path = model.current_case_path
		if self.case_path:
			self._init_case_paths()
			case_name = self.model.current_case.get("project_name", "Unbekannter Fall")
			self.view.setWindowTitle(f"Forensic Analyzer – {case_name}")
			self.view.set_case_name(case_name)
		else:
			_none = None
			self.folder_evidence = _none
			self.folder_analyze = _none
			self.folder_exports = _none
			self.folder_reports = _none
			self.folder_thumbnails = _none
			self.folder_recovered = _none
			self.folder_logs = _none
			self.view.setWindowTitle("Video Forensic Lab - Analyzer")

		self.last_tab_focus = "General"
		self.comparison_data = {}
		self.comparison_window = None

		print(f"System bereit. {self.threadpool.maxThreadCount()} Threads verfügbar.")
		self.refresh_ui_list()
		self.refresh_case_list()

	@staticmethod
	def _parse_json_column(value):
		if not value:
			return {}
		if isinstance(value, dict):
			return value
		return json.loads(value)

	def handle_nav_tab_change(self, index):
		if not self.case_path and index not in (0, 5):
			from PyQt6.QtWidgets import QMessageBox
			QMessageBox.warning(
				self.view,
				"Kein Fall aktiv",
				"Bitte wählen Sie zuerst einen Fall aus oder legen Sie einen neuen Fall an (Tab „Fallübersicht“)."
			)
			self.view.nav_bar.blockSignals(True)
			self.view.nav_bar.setCurrentIndex(0)
			self.view.nav_bar.blockSignals(False)
			self.view.content_stack.setCurrentIndex(0)

	def track_tab_change(self, index):
		name = self.view.get_active_tab_name()
		if name:
			self.last_tab_focus = name

	def _init_case_paths(self):
		self.case_path = self.model.current_case_path
		if self.case_path:
			self.model.ensure_case_folders(self.case_path)
			self.folder_evidence = self.case_path / "evidence_input"
			self.folder_analyze = self.case_path / "analyze_media"
			self.folder_exports = self.case_path / "exports"
			self.folder_reports = self.case_path / "reports"
			self.folder_thumbnails = self.case_path / "thumbnails"
			self.folder_recovered = self.case_path / "recovered"
			self.folder_logs = self.case_path / "logs"

	def handle_case_selected(self, case_id):
		case = self.model.load_case(case_id)
		if case:
			self._init_case_paths()
			case_name = case.get("project_name", "Unbekannter Fall")
			self.view.setWindowTitle(f"Forensic Analyzer – {case_name}")
			self.view.set_case_name(case_name)
			self.refresh_ui_list()

	def handle_create_case(self, name, desc):
		try:
			case_id = self.model.create_case(name, desc)
			self._init_case_paths()
			self.view.set_case_name(name)
			self.view.setWindowTitle(f"Forensic Analyzer – {name}")
			self.refresh_ui_list()
			self.refresh_case_list()
		except Exception as e:
			print(f"Fehler beim Erstellen des Falls: {e}")

	def refresh_case_list(self):
		cases = self.model.load_cases()
		self.view.update_case_list(cases)

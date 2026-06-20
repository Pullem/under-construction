import json
from PyQt6.QtCore import QThreadPool, Qt


class PresenterBase:
	def __init__(self, model, view, **kwargs):
		super().__init__(**kwargs)
		self.model = model
		self.view = view
		self.threadpool = QThreadPool()

		self.view.start_requested.connect(self.handle_scan)
		self.view.search_changed.connect(self.handle_search)
		self.view.file_selected.connect(self.load_file_details)
		self.view.tabs.currentChanged.connect(self.track_tab_change)

		self.view.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
		self.view.file_list.customContextMenuRequested.connect(self.show_context_menu)

		if hasattr(self.view, "import_media_requested"):
			self.view.import_media_requested.connect(self.open_import_dialog)

		if not model.current_case_path:
			raise Exception("Kein Fall geladen – Ordnerstruktur kann nicht ermittelt werden.")
		model.ensure_case_folders(model.current_case_path)

		self.case_path = model.current_case_path
		self.folder_evidence = self.case_path / "evidence_input"
		self.folder_analyze = self.case_path / "analyze_media"
		self.folder_exports = self.case_path / "exports"
		self.folder_reports = self.case_path / "reports"
		self.folder_thumbnails = self.case_path / "thumbnails"
		self.folder_recovered = self.case_path / "recovered"
		self.folder_logs = self.case_path / "logs"

		if self.model.current_case:
			case_name = self.model.current_case.get("project_name", "Unbekannter Fall")
			self.view.setWindowTitle(f"Forensic Analyzer – {case_name}")

		self.last_tab_focus = "General"
		self.comparison_data = {}
		self.comparison_window = None

		print(f"System bereit. {self.threadpool.maxThreadCount()} Threads verfügbar.")
		self.refresh_ui_list()

	@staticmethod
	def _parse_json_column(value):
		if not value:
			return {}
		if isinstance(value, dict):
			return value
		return json.loads(value)

	def track_tab_change(self, index):
		name = self.view.get_active_tab_name()
		if name:
			self.last_tab_focus = name

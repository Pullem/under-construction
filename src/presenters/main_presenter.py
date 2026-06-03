import os
from PyQt6.QtCore import Qt
from .import_logic import ImportManager

class ForensicPresenter:
	def __init__(self, model, view):
		self.model = model
		self.view = view
		
		# Hilfs-Manager für den Import
		self.import_manager = ImportManager(self.model, self.view)
		
		self.connect_signals()
		self.update_ui_state()

	def connect_signals(self):
		exp = self.view.explorer_panel
		
		# Buttons
		exp.btn_change_case.clicked.connect(self.handle_change_case)
		exp.btn_settings.clicked.connect(self.open_settings)
		exp.btn_import.clicked.connect(self.handle_import_action)
		exp.btn_scan.clicked.connect(self.handle_scan)
		
		# Liste & Suche
		exp.file_list.itemSelectionChanged.connect(self.handle_file_selection)
		exp.search_bar.textChanged.connect(self.handle_search)

	# --- Handler Methoden ---

	def handle_scan(self):
		"""Scannt den aktuellen Fall-Ordner nach Dateien."""
		if not self.model.current_case_folder:
			return

		# Hier rufen wir die Logik im Model auf (muss im CaseModel existieren)
		# Für den Moment: Wir listen einfach die Dateien auf
		self.refresh_file_list()
		print(f"Scan durchgeführt in: {self.model.current_case_folder}")

	def handle_search(self, text):
		"""Filtert die Dateiliste basierend auf der Sucheingabe."""
		for i in range(self.view.explorer_panel.file_list.count()):
			item = self.view.explorer_panel.file_list.item(i)
			# Zeige Item nur an, wenn Suchtext im Namen vorkommt
			item.setHidden(text.lower() not in item.text().lower())

	def handle_file_selection(self):
		"""Wird aufgerufen, wenn ein User eine Datei in der Liste anklickt."""
		selected_items = self.view.explorer_panel.file_list.selectedItems()
		if not selected_items:
			return
		
		file_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
		# Hier triggern wir die Anzeige in den anderen Panels
		self.view.metadata_panel.info_text.setText(f"Datei ausgewählt:\n{file_path}")
		# Später: self.load_media_preview(file_path)

	def handle_import_action(self):
		"""Startet den Import-Dialog über den ImportManager."""
		if self.import_manager.execute_import_dialog():
			self.handle_scan()

	def handle_change_case(self):
		"""Logik zum Wechseln des Falls (z.B. QFileDialog)."""
		from PyQt6.QtWidgets import QFileDialog
		path = QFileDialog.getExistingDirectory(self.view, "Fall-Ordner wählen", 
											   self.model.config_manager.get("case_root"))
		if path:
			if self.model.set_project_by_path(path):
				self.update_ui_state()
				self.handle_scan()

	def open_settings(self):
		"""Öffnet den Einstellungs-Dialog."""
		from ..views.dialogs.settings import SettingsDialog
		dialog = SettingsDialog(self.model.config_manager.config, self.view)
		if dialog.exec():
			self.model.config_manager.config.update(dialog.get_settings())
			self.model.config_manager.save_config()

	# --- UI Helper ---

	def update_ui_state(self):
		"""Aktualisiert Titel und Labels basierend auf dem Model-Status."""
		case_name = self.model.case_name
		self.view.setWindowTitle(f"Forensic Lab Pro - {case_name}")
		self.view.explorer_panel.file_count_label.setText(f"Aktiver Fall: {case_name}")

	def refresh_file_list(self):
		"""Liest die Dateien physisch aus dem Ordner und füllt die QListWidget."""
		self.view.explorer_panel.file_list.clear()
		folder = self.model.current_case_folder
		
		if not folder or not os.path.exists(folder):
			return

		valid_exts = ('.mp4', '.mov', '.avi', '.jpg', '.jpeg', '.png', '.mp3', '.wav')
		
		# Einfacher Scan durch den Ordner
		for root, dirs, files in os.walk(folder):
			for file in files:
				if file.lower().endswith(valid_exts):
					from PyQt6.QtWidgets import QListWidgetItem
					full_path = os.path.join(root, file)
					item = QListWidgetItem(file)
					item.setData(Qt.ItemDataRole.UserRole, full_path)
					self.view.explorer_panel.file_list.addItem(item)
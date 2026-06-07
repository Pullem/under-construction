import os
import json
from PyQt6.QtCore import QThreadPool, Qt
from PyQt6.QtWidgets import QMenu
from PyQt6.QtWidgets import QDialog

from .worker import AnalysisWorker
from .compare_window import ComparisonWindow
from .import_dialog import ImportMediaDialog

class ForensicPresenter:
	def __init__(self, model, view):
		self.model = model
		self.view = view
		self.threadpool = QThreadPool()


		# --- SIGNAL-SLOT VERBINDUNGEN ---
		self.view.start_requested.connect(self.handle_scan)
		self.view.search_changed.connect(self.handle_search)
		self.view.file_selected.connect(self.load_file_details)

		# Überwachung von Tab-Wechseln durch den User
		self.view.tabs.currentChanged.connect(self.track_tab_change)

		# Rechtsklick-Menü für die Dateiliste aktivieren
		self.view.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
		self.view.file_list.customContextMenuRequested.connect(self.show_context_menu)



		# --- IMPORT-MEDIA SIGNAL ---
		if hasattr(self.view, "import_media_requested"):
			self.view.import_media_requested.connect(self.open_import_dialog)

		
		# ---------------------------------------------------------
		# PATCH: Fallpfad + Unterordner aus dem Model übernehmen
		# ---------------------------------------------------------
		self.case_path = model.current_case_path

		# Unterordner definieren
		self.folder_evidence = self.case_path / "evidence_input"
		self.folder_analyze = self.case_path / "analyze_media"
		self.folder_exports = self.case_path / "exports"
		self.folder_reports = self.case_path / "reports"
		self.folder_thumbnails = self.case_path / "thumbnails"
		self.folder_recovered = self.case_path / "recovered"
		self.folder_logs = self.case_path / "logs"

		# Ordner sicherstellen (falls manuell gelöscht)
		for folder in [
			self.folder_evidence,
			self.folder_analyze,
			self.folder_exports,
			self.folder_reports,
			self.folder_thumbnails,
			self.folder_recovered,
			self.folder_logs
		]:
			folder.mkdir(parents=True, exist_ok=True)
		
		# ---------------------------------------------------------
		# PATCH: Fenstertitel mit Fallname setzen
		# ---------------------------------------------------------
		if self.model.current_case:
			case_name = self.model.current_case.get("project_name", "Unbekannter Fall")
			self.view.setWindowTitle(f"Forensic Analyzer – {case_name}")

		# PERSISTENTER FOKUS-SPEICHER
		self.last_tab_focus = "General" 
		
		# Speicher für den Vergleich (Dateiname -> Metadaten)
		self.comparison_data = {}
		self.comparison_window = None

		# --- SIGNAL-SLOT VERBINDUNGEN ---
		self.view.start_requested.connect(self.handle_scan)
		self.view.search_changed.connect(self.handle_search)
		self.view.file_selected.connect(self.load_file_details)
		
		# Überwachung von Tab-Wechseln durch den User
		self.view.tabs.currentChanged.connect(self.track_tab_change)

		# Rechtsklick-Menü für die Dateiliste aktivieren
		self.view.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
		self.view.file_list.customContextMenuRequested.connect(self.show_context_menu)

		print(f"System bereit. {self.threadpool.maxThreadCount()} Threads verfügbar.")
		self.refresh_ui_list()

	def track_tab_change(self, index):
		"""Speichert den Namen des Tabs, den der User gerade angeklickt hat."""
		name = self.view.get_active_tab_name()
		if name: 
			self.last_tab_focus = name

	def handle_scan(self):
		"""Startet den Scan des Watchfolders."""
		folder = self.folder_evidence  # <-- PATCH: Fallbezogener Watchfolder
		if not os.path.exists(folder):
			print(f"FEHLER: Ordner {folder} nicht gefunden.")
			return
			
		files = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.jpg', '.png'))]
		print(f"Scan gestartet... {len(files)} Dateien gefunden.")

		for f in files:
			path = os.path.join(folder, f)
			worker = AnalysisWorker(self.model, path)
			worker.signals.result.connect(self.on_analysis_finished)
			worker.signals.error.connect(self.on_analysis_error)
			self.threadpool.start(worker)

	def on_analysis_finished(self, data):
		"""Wird aufgerufen, wenn ein Worker fertig ist."""
		print(f"✅ Analyse abgeschlossen: {data['file_name']}")
		self.refresh_ui_list()

	def on_analysis_error(self, error_msg):
		print(f"❌ THREAD-FEHLER: {error_msg}")

	def refresh_ui_list(self):
		"""Lädt die Liste der Dateien aus der DB in die GUI."""
		conn = self.model.get_connection()
		if not conn: return
		
		try:
			cur = conn.cursor()
			cur.execute("SELECT file_name FROM media_files ORDER BY created_at DESC")
			files = [r[0] for r in cur.fetchall()]
			conn.close()
			self.view.update_file_list(files)
		except Exception as e:
			print(f"UI-Refresh fehlgeschlagen: {e}")

	def load_file_details(self, file_name):
		"""Lädt Details einer Datei und behält den Tab-Fokus stur bei."""
		if not file_name: return
		
		target_tab = self.last_tab_focus
		
		try:
			conn = self.model.get_connection()
			cur = conn.cursor(dictionary=True)
			cur.execute("SELECT metadata, exif_metadata, file_path FROM media_files WHERE file_name = ?", (file_name,))
			row = cur.fetchone()
			conn.close()

			if row:
				mi_data = json.loads(row['metadata'])
				if row['exif_metadata']:
					mi_data["EXIF Deep Dive"] = json.loads(row['exif_metadata'])
				
				self.view.tabs.blockSignals(True)
				self.view.display_metadata(mi_data)
				self.view.set_active_tab_by_name(target_tab)
				self.view.tabs.blockSignals(False)
				
				# Thumbnail laden
				t_path = self.model.get_thumbnail(row['file_path'])
				self.view.set_thumbnail(t_path)
		except Exception as e:
			print(f"Fehler beim Laden der Dateidetails: {e}")
			if hasattr(self.view, 'tabs'): 
				self.view.tabs.blockSignals(False)

	def handle_search(self, query):
		"""Filtert die Dateiliste in Echtzeit."""
		self.view.apply_row_filter(query)

	# --- VERGLEICHS-LOGIK ---

	def show_context_menu(self, position):
		"""Erzeugt das Rechtsklick-Menü in der Dateiliste."""
		item = self.view.file_list.itemAt(position)
		if not item: return

		menu = QMenu()
		add_action = menu.addAction(f"'{item.text()}' zum Vergleich hinzufügen")
		open_action = menu.addAction("Vergleichs-Fenster öffnen")
		clear_action = menu.addAction("Vergleichs-Liste leeren")
		
		action = menu.exec(self.view.file_list.mapToGlobal(position))
		
		if action == add_action:
			self.add_to_comparison(item.text())
		elif action == open_action:
			self.open_comparison_view()
		elif action == clear_action:
			self.comparison_data.clear()
			print("Vergleichsliste geleert.")

	def add_to_comparison(self, file_name):
		"""Holt die Daten aus der DB und legt sie in die Vergleichs-Queue."""
		try:
			conn = self.model.get_connection()
			cur = conn.cursor(dictionary=True)
			cur.execute("SELECT metadata, exif_metadata FROM media_files WHERE file_name = ?", (file_name,))
			row = cur.fetchone()
			conn.close()

			if row:
				data = json.loads(row['metadata'])
				if row['exif_metadata']:
					data["EXIF"] = json.loads(row['exif_metadata'])
				
				self.comparison_data[file_name] = data
				print(f"'{file_name}' vorgemerkt. ({len(self.comparison_data)} Dateien in Liste).")
		except Exception as e:
			print(f"Fehler beim Hinzufügen zum Vergleich: {e}")


	def open_import_dialog(self):
		"""Öffnet den Media-Import-Dialog."""
		if not self.model.current_case_id:
			print("Kein Fall ausgewählt – Import nicht möglich.")
			return

		dlg = ImportMediaDialog(self.model, parent=self.view)
		result = dlg.exec()

		if result == QDialog.DialogCode.Accepted:
			print("📥 Import abgeschlossen – aktualisiere Dateiliste…")
			self.refresh_ui_list()





	def open_comparison_view(self):
		"""Öffnet das separate Vergleichsfenster."""
		if not self.comparison_data:
			print("Keine Dateien ausgewählt!")
			return
			
		self.comparison_window = ComparisonWindow(self.comparison_data)
		self.comparison_window.show()

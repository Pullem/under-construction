import os
import json
from PyQt6.QtCore import QThreadPool
from .worker import AnalysisWorker

class ForensicPresenter:
	def __init__(self, model, view):
		self.model = model
		self.view = view
		self.threadpool = QThreadPool()
		print(f"System bereit. {self.threadpool.maxThreadCount()} Threads verfügbar.")

		self.view.start_requested.connect(self.handle_scan)
		self.view.search_changed.connect(self.handle_search)
		self.view.file_selected.connect(self.load_file_details)
		self.refresh_ui_list()

	def handle_scan(self):
		folder = self.model.proj_config.get('watchfolder', './evidence_input')
		if not os.path.exists(folder):
			print(f"FEHLER: Watchfolder {folder} existiert nicht!")
			return
			
		files = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.jpg'))]
		print(f"Scan gestartet... {len(files)} Dateien gefunden.")

		for f in files:
			path = os.path.join(folder, f)
			worker = AnalysisWorker(self.model, path)
			
			# Verbinde Signale
			worker.signals.result.connect(self.on_analysis_finished)
			worker.signals.error.connect(self.on_analysis_error)
			
			self.threadpool.start(worker)

	def on_analysis_finished(self, data):
		print(f"✅ Datei verarbeitet: {data['file_name']}")
		self.refresh_ui_list()

	def on_analysis_error(self, error_msg):
		# Das ist entscheidend: Ohne das siehst du keine Thread-Fehler!
		print(f"❌ THREAD-FEHLER: {error_msg}")

	def refresh_ui_list(self):
		"""Aktualisiert die Liste nur, wenn die DB bereit ist."""
		conn = self.model.get_connection()
		if not conn:
			# Falls keine Verbindung möglich ist, einfach abbrechen 
			# (passiert beim ersten Setup)
			return
			
		try:
			cur = conn.cursor()
			cur.execute("SELECT file_name FROM media_files ORDER BY created_at DESC")
			files = [r[0] for r in cur.fetchall()]
			conn.close()
			self.view.update_file_list(files)
		except Exception as e:
			print(f"UI-Refresh fehlgeschlagen: {e}")

	def load_file_details(self, file_name):
		if not file_name: return
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
				self.view.display_metadata(mi_data)
				
				t_path = self.model.get_thumbnail(row['file_path'])
				self.view.set_thumbnail(t_path)
		except Exception as e:
			print(f"Detail-Laden fehlgeschlagen: {e}")

	def handle_search(self, q):
		self.view.apply_row_filter(q)
		if len(q) > 1:
			res = self.model.search_db(q)
			self.view.update_file_list([r['file_name'] for r in res])
		else:
			self.refresh_ui_list()
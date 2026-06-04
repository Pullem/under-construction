import os
import json
import subprocess

class ForensicPresenter:
	def __init__(self, model, view):
		self.model = model
		self.view = view
		
		# Signale der View mit Methoden des Presenters verknüpfen
		self.view.start_requested.connect(self.handle_scan)
		self.view.config_requested.connect(self.open_config_folder)
		self.view.search_changed.connect(self.handle_search)
		self.view.file_selected.connect(self.load_file_details)

		# Beim Start bereits vorhandene Daten aus der DB anzeigen
		self.refresh_ui_list()

	def handle_scan(self):
		"""Scannt den Watchfolder und verarbeitet neue Dateien."""
		watchfolder = self.model.proj_config.get('watchfolder', './evidence_input')
		
		if not os.path.exists(watchfolder):
			print(f"Watchfolder {watchfolder} nicht gefunden!")
			return

		# Unterstützte Formate
		valid_ext = ('.mp4', '.mkv', '.mov', '.avi', '.jpg', '.jpeg', '.png')
		
		for filename in os.listdir(watchfolder):
			if filename.lower().endswith(valid_ext):
				filepath = os.path.join(watchfolder, filename)
				# Model verarbeitet die Datei (Hashing, MediaInfo, DB-Check)
				result = self.model.process_file(filepath)
				print(f"Verarbeite {filename}: {result}")
		
		# Nach dem Scan die Liste links aktualisieren
		self.refresh_ui_list()

	def refresh_ui_list(self):
		"""Holt alle bekannten Dateinamen aus der Datenbank."""
		try:
			conn = self.model.get_connection()
			cur = conn.cursor()
			cur.execute("SELECT file_name FROM media_files ORDER BY created_at DESC")
			# Resultate in eine einfache Liste umwandeln
			files = [row[0] for row in cur.fetchall()]
			conn.close()
			
			# View mitteilen, dass die Liste neu gezeichnet werden soll
			self.view.update_file_list(files)
		except Exception as e:
			print(f"Fehler beim Laden der Dateiliste: {e}")

	def load_file_details(self, file_name):
		"""Wird aufgerufen, wenn der Nutzer eine Datei in der Liste anklickt."""
		if not file_name:
			return

		try:
			conn = self.model.get_connection()
			cur = conn.cursor(dictionary=True)
			cur.execute("SELECT metadata FROM media_files WHERE file_name = ?", (file_name,))
			row = cur.fetchone()
			conn.close()

			if row and row['metadata']:
				# JSON-String aus der DB wieder in ein Python-Dictionary umwandeln
				metadata = json.loads(row['metadata'])
				self.view.display_metadata(metadata)
		except Exception as e:
			print(f"Fehler beim Laden der Details für {file_name}: {e}")

	def handle_search(self, query):
		"""Sucht global in der Datenbank."""
		if len(query) < 2:
			# Wenn das Suchfeld fast leer ist, zeigen wir wieder alle an
			self.refresh_ui_list()
			return

		results = self.model.search_db(query)
		# Extrahiere nur die Dateinamen für die linke Liste
		file_names = list(set([row['file_name'] for row in results]))
		self.view.update_file_list(file_names)

	def open_config_folder(self):
		"""Öffnet den Konfigurationsordner im Explorer."""
		config_dir = os.path.abspath('config')
		if os.name == 'nt': # Windows
			os.startfile(config_dir)
		else: # Linux / Mac
			subprocess.run(['xdg-open', config_dir])
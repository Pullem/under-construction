import mariadb
import hashlib
import os
import json
from configparser import ConfigParser
from pymediainfo import MediaInfo

class ForensicModel:
	def __init__(self):
		# Pfade zu den Konfigurationsdateien
		self.db_config_path = 'config/mariadb.ini'
		self.proj_config_path = 'config/projekt.ini'
		
		# Initiales Laden der Konfigurationen
		self.db_config = {}
		self.proj_config = {}
		self.load_configs()

	def load_configs(self):
		"""Liest die INI-Dateien neu ein."""
		parser = ConfigParser()
		
		# Datenbank-Konfiguration laden
		if os.path.exists(self.db_config_path):
			parser.read(self.db_config_path)
			if parser.has_section('database'):
				self.db_config = dict(parser.items('database'))
		
		# Projekt-Konfiguration laden
		parser = ConfigParser() # Reset für neue Datei
		if os.path.exists(self.proj_config_path):
			parser.read(self.proj_config_path)
			if parser.has_section('settings'):
				self.proj_config = dict(parser.items('settings'))
		
		# Fallbacks für Projekt-Einstellungen, falls Datei fehlt
		if not self.proj_config:
			self.proj_config = {
				'project_name': 'Default_Case',
				'watchfolder': './evidence_input'
			}

	def get_connection(self):
		"""
		Strikte Verbindung über die Parameter aus der mariadb.ini.
		Keine hartcodierten Passwörter als Fallback.
		"""
		# Vor jedem Verbindungsaufbau Config neu laden (falls Datei geändert wurde)
		self.load_configs()

		try:
			conn = mariadb.connect(
				host=self.db_config.get('host'),
				user=self.db_config.get('user'),
				password=self.db_config.get('password'),
				port=int(self.db_config.get('port', 3306)),
				database="forensic_analyzer"
			)
			return conn
		except mariadb.Error as e:
			# Re-raise des Fehlers, damit die main.py das Setup triggern kann
			raise e

	def initial_root_setup(self, root_password):
		"""
		Wird nur aufgerufen, wenn die Verbindung fehlschlägt.
		Erstellt DB, User und schreibt die mariadb.ini.
		"""
		# Festlegen des Standard-Passworts für den neuen User (nur hier!)
		assigned_user_pw = "analyzer_pw123"
		
		conn = mariadb.connect(
			host="localhost",
			user="root",
			password=root_password
		)
		cur = conn.cursor()
		
		# Datenbank und User anlegen
		cur.execute("CREATE DATABASE IF NOT EXISTS forensic_analyzer")
		cur.execute(f"CREATE USER IF NOT EXISTS 'va_user'@'localhost' IDENTIFIED BY '{assigned_user_pw}'")
		cur.execute("GRANT ALL PRIVILEGES ON forensic_analyzer.* TO 'va_user'@'localhost'")
		cur.execute("FLUSH PRIVILEGES")
		
		# Tabellen-Struktur anlegen
		cur.execute("USE forensic_analyzer")
		cur.execute("""
			CREATE TABLE IF NOT EXISTS media_files (
				id INT AUTO_INCREMENT PRIMARY KEY,
				project_name VARCHAR(100),
				file_path TEXT,
				file_name VARCHAR(255),
				file_size BIGINT,
				sha256_hash VARCHAR(64) UNIQUE,
				metadata JSON,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		""")
		
		# Konfiguration in mariadb.ini schreiben
		parser = ConfigParser()
		parser.add_section('database')
		parser.set('database', 'host', 'localhost')
		parser.set('database', 'user', 'va_user')
		parser.set('database', 'password', assigned_user_pw)
		parser.set('database', 'port', '3306')
		
		with open(self.db_config_path, 'w') as f:
			parser.write(f)
			
		conn.commit()
		conn.close()
		
		# Interne Config-Variablen aktualisieren
		self.load_configs()

	def calculate_hash(self, filepath):
		"""Erzeugt SHA256 Hash für forensische Eindeutigkeit."""
		sha256 = hashlib.sha256()
		with open(filepath, "rb") as f:
			for chunk in iter(lambda: f.read(8192), b""):
				sha256.update(chunk)
		return sha256.hexdigest()

	def process_file(self, filepath):
		"""Analysiert Datei und speichert JSON-Metadaten in der DB."""
		file_hash = self.calculate_hash(filepath)
		
		conn = self.get_connection()
		cur = conn.cursor()

		# Prüfen, ob Datei bereits existiert
		cur.execute("SELECT id FROM media_files WHERE sha256_hash = ?", (file_hash,))
		if cur.fetchone():
			conn.close()
			return "Duplicate"

		# Mediainfo auslesen
		mi = MediaInfo.parse(filepath)
		metadata_dict = {track.track_type: track.to_data() for track in mi.tracks}
		
		# Eintrag erstellen
		cur.execute(
			"""INSERT INTO media_files 
			   (project_name, file_path, file_name, file_size, sha256_hash, metadata) 
			   VALUES (?, ?, ?, ?, ?, ?)""",
			(self.proj_config.get('project_name', 'Default'), 
			 filepath, 
			 os.path.basename(filepath), 
			 os.stat(filepath).st_size, 
			 file_hash, 
			 json.dumps(metadata_dict))
		)
		
		conn.commit()
		conn.close()
		return "Success"

	def search_db(self, query):
		"""Sucht in Dateinamen und tief in den JSON-Metadaten."""
		conn = self.get_connection()
		cur = conn.cursor(dictionary=True)
		# Suche in Dateiname oder JSON-Werten
		sql = "SELECT * FROM media_files WHERE file_name LIKE ? OR JSON_SEARCH(metadata, 'one', ?) IS NOT NULL"
		like_query = f"%{query}%"
		cur.execute(sql, (like_query, like_query))
		res = cur.fetchall()
		conn.close()
		return res
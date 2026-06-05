import mariadb
import hashlib
import os
import json
import cv2
from configparser import ConfigParser
from pymediainfo import MediaInfo

class ForensicModel:
	def __init__(self):
		self.db_config_path = 'config/mariadb.ini'
		self.proj_config_path = 'config/projekt.ini'
		self.db_config = {}
		self.proj_config = {}
		self.load_configs()

	def load_configs(self):
		"""Lädt die INI-Dateien. Erstellt den config-Ordner, falls nötig."""
		if not os.path.exists('config'):
			os.makedirs('config')
			
		parser = ConfigParser()
		if os.path.exists(self.db_config_path):
			parser.read(self.db_config_path)
			if parser.has_section('database'):
				self.db_config = dict(parser.items('database'))
		
		parser = ConfigParser()
		if os.path.exists(self.proj_config_path):
			parser.read(self.proj_config_path)
			if parser.has_section('settings'):
				self.proj_config = dict(parser.items('settings'))
		
		# Standardwerte für Projekt-Einstellungen
		if not self.proj_config:
			self.proj_config = {
				'project_name': 'Default_Case', 
				'watchfolder': './evidence_input'
			}

	def get_connection(self):
		"""Gibt eine aktive Datenbankverbindung zurück oder None bei Fehlern."""
		# Ohne Passwort in der Config versuchen wir erst gar keine Verbindung
		if not self.db_config.get('password'):
			return None
			
		try:
			return mariadb.connect(
				host=self.db_config.get('host', 'localhost'),
				user=self.db_config.get('user', 'va_user'),
				password=self.db_config.get('password'),
				port=int(self.db_config.get('port', 3306)),
				database="forensic_analyzer"
			)
		except mariadb.Error as e:
			print(f"Datenbank-Verbindungsfehler: {e}")
			return None

	def initial_root_setup(self, root_password, user_password_to_set):
		"""
		Erstellt die Datenbank, den User und die Tabellen.
		Wird nur aufgerufen, wenn die mariadb.ini fehlt.
		"""
		# Verbindung als Root, um alles vorzubereiten
		conn = mariadb.connect(host="localhost", user="root", password=root_password)
		cur = conn.cursor()
		
		# 1. Datenbank & User anlegen
		cur.execute("CREATE DATABASE IF NOT EXISTS forensic_analyzer")
		cur.execute(f"CREATE USER IF NOT EXISTS 'va_user'@'localhost' IDENTIFIED BY '{user_password_to_set}'")
		cur.execute(f"ALTER USER 'va_user'@'localhost' IDENTIFIED BY '{user_password_to_set}'")
		cur.execute("GRANT ALL PRIVILEGES ON forensic_analyzer.* TO 'va_user'@'localhost'")
		cur.execute("FLUSH PRIVILEGES")
		
		# 2. Zu der neuen Datenbank wechseln
		cur.execute("USE forensic_analyzer")
		
		# 3. Tabelle mit EXIF-Support anlegen
		cur.execute("""
			CREATE TABLE IF NOT EXISTS media_files (
				id INT AUTO_INCREMENT PRIMARY KEY,
				project_name VARCHAR(100),
				file_path TEXT,
				file_name VARCHAR(255),
				file_size BIGINT,
				sha256_hash VARCHAR(64) UNIQUE,
				metadata JSON,
				exif_metadata JSON,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		""")
		
		# 4. mariadb.ini für die Zukunft speichern
		parser = ConfigParser()
		parser.add_section('database')
		parser.set('database', 'host', 'localhost')
		parser.set('database', 'user', 'va_user')
		parser.set('database', 'password', user_password_to_set)
		parser.set('database', 'port', '3306')
		
		with open(self.db_config_path, 'w') as f:
			parser.write(f)
		
		conn.commit()
		conn.close()
		
		# Configs im Programm-Objekt aktualisieren
		self.load_configs()

	def calculate_hash(self, filepath):
		"""Berechnet den SHA256-Hash einer Datei."""
		sha256 = hashlib.sha256()
		try:
			with open(filepath, "rb") as f:
				for chunk in iter(lambda: f.read(8192), b""):
					sha256.update(chunk)
			return sha256.hexdigest()
		except Exception as e:
			print(f"Fehler beim Hashing von {filepath}: {e}")
			return "HASH_ERROR"

	def get_thumbnail(self, filepath):
		"""Extrahiert ein Vorschaubild an Sekunde 1 (oder Frame 0)."""
		temp_dir = "config/thumbnails"
		if not os.path.exists(temp_dir):
			os.makedirs(temp_dir)
			
		# Eindeutiger Name basierend auf dem Dateinamen
		thumb_filename = hashlib.md5(filepath.encode()).hexdigest() + ".jpg"
		thumb_path = os.path.abspath(os.path.join(temp_dir, thumb_filename))
		
		if os.path.exists(thumb_path):
			return thumb_path

		cap = cv2.VideoCapture(filepath)
		cap.set(cv2.CAP_PROP_POS_MSEC, 1000)
		success, frame = cap.read()
		
		if not success:
			cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
			success, frame = cap.read()

		if success:
			h, w = frame.shape[:2]
			new_w = 320
			new_h = int(h * (new_w / w))
			resized = cv2.resize(frame, (new_w, new_h))
			cv2.imwrite(thumb_path, resized)
			cap.release()
			return thumb_path
		
		cap.release()
		return None

	def save_to_db(self, path, name, f_hash, mi_dict, exif_dict):
		"""Speichert die gesammelten Analyse-Daten in die MariaDB."""
		conn = self.get_connection()
		if not conn:
			raise Exception("Keine Datenbankverbindung möglich.")
			
		try:
			cur = conn.cursor()
			sql = """INSERT INTO media_files 
					 (project_name, file_path, file_name, file_size, sha256_hash, metadata, exif_metadata) 
					 VALUES (?, ?, ?, ?, ?, ?, ?)
					 ON DUPLICATE KEY UPDATE file_name=VALUES(file_name)"""
			
			cur.execute(sql, (
				self.proj_config.get('project_name', 'Default_Case'),
				path, 
				name, 
				os.stat(path).st_size, 
				f_hash,
				json.dumps(mi_dict), 
				json.dumps(exif_dict)
			))
			conn.commit()
		finally:
			conn.close()

	def search_db(self, query):
		"""Sucht in Dateinamen und Metadaten-Feldern."""
		conn = self.get_connection()
		if not conn:
			return []
			
		try:
			cur = conn.cursor(dictionary=True)
			sql = """SELECT * FROM media_files 
					 WHERE file_name LIKE ? 
					 OR JSON_SEARCH(metadata, 'one', ?) IS NOT NULL
					 OR JSON_SEARCH(exif_metadata, 'one', ?) IS NOT NULL"""
			like_q = f"%{query}%"
			cur.execute(sql, (like_q, like_q, like_q))
			return cur.fetchall()
		finally:
			conn.close()
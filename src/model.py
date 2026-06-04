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
		
		if not self.proj_config:
			self.proj_config = {'project_name': 'Default_Case', 'watchfolder': './evidence_input'}

	def get_connection(self):
		self.load_configs()
		return mariadb.connect(
			host=self.db_config.get('host'),
			user=self.db_config.get('user'),
			password=self.db_config.get('password'),
			port=int(self.db_config.get('port', 3306)),
			database="forensic_analyzer"
		)

	def initial_root_setup(self, root_password):
		assigned_user_pw = "analyzer_pw123"
		conn = mariadb.connect(host="localhost", user="root", password=root_password)
		cur = conn.cursor()
		cur.execute("CREATE DATABASE IF NOT EXISTS forensic_analyzer")
		cur.execute(f"CREATE USER IF NOT EXISTS 'va_user'@'localhost' IDENTIFIED BY '{assigned_user_pw}'")
		cur.execute("GRANT ALL PRIVILEGES ON forensic_analyzer.* TO 'va_user'@'localhost'")
		cur.execute("FLUSH PRIVILEGES")
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
		self.load_configs()

	def get_thumbnail(self, filepath):
		"""Extrahiert ein Vorschaubild (Thumbnail) aus Video oder Bild."""
		thumb_path = os.path.abspath("config/temp_thumb.jpg")
		cap = cv2.VideoCapture(filepath)
		
		# Bei Videos: Gehe zu Sekunde 1 (1000ms)
		cap.set(cv2.CAP_PROP_POS_MSEC, 1000)
		success, frame = cap.read()
		
		# Falls Sekunde 1 fehlschlägt (z.B. kurzes Video oder Bild), nimm den ersten Frame
		if not success:
			cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
			success, frame = cap.read()

		if success:
			# Auf Breite 320px skalieren
			h, w = frame.shape[:2]
			new_w = 320
			new_h = int(h * (new_w / w))
			resized = cv2.resize(frame, (new_w, new_h))
			cv2.imwrite(thumb_path, resized)
			cap.release()
			return thumb_path
		
		cap.release()
		return None

	def calculate_hash(self, filepath):
		sha256 = hashlib.sha256()
		with open(filepath, "rb") as f:
			for chunk in iter(lambda: f.read(8192), b""):
				sha256.update(chunk)
		return sha256.hexdigest()

	def process_file(self, filepath):
		file_hash = self.calculate_hash(filepath)
		conn = self.get_connection()
		cur = conn.cursor()
		cur.execute("SELECT id FROM media_files WHERE sha256_hash = ?", (file_hash,))
		if cur.fetchone():
			conn.close()
			return "Duplicate"

		mi = MediaInfo.parse(filepath)
		metadata_dict = {track.track_type: track.to_data() for track in mi.tracks}
		cur.execute(
			"INSERT INTO media_files (project_name, file_path, file_name, file_size, sha256_hash, metadata) VALUES (?, ?, ?, ?, ?, ?)",
			(self.proj_config.get('project_name', 'Default'), filepath, os.path.basename(filepath), os.stat(filepath).st_size, file_hash, json.dumps(metadata_dict))
		)
		conn.commit()
		conn.close()
		return "Success"

	def search_db(self, query):
		conn = self.get_connection()
		cur = conn.cursor(dictionary=True)
		sql = "SELECT * FROM media_files WHERE file_name LIKE ? OR JSON_SEARCH(metadata, 'one', ?) IS NOT NULL"
		like_q = f"%{query}%"
		cur.execute(sql, (like_q, like_q))
		res = cur.fetchall()
		conn.close()
		return res
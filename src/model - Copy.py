import mariadb
import hashlib
import os
import json
import cv2
from configparser import ConfigParser
from pymediainfo import MediaInfo
from pathlib import Path


class ForensicModel:
	def __init__(self, project_path=None):
		self.project_path = project_path

		# Config-Dateien
		self.db_config_path = 'config/mariadb.ini'
		self.proj_config_path = 'config/project.ini'

		# interne Configs
		self.db_config = {}
		from configparser import ConfigParser
		self.proj_config = ConfigParser()


		# aktueller Fall
		self.current_case = None
		self.current_case_id = None
		self.current_case_path = None

		# Configs laden
		self.load_configs()
		self.load_project_config()


		if self.project_path:
			self.load_project(self.project_path)

	# ---------------------------------------------------------
	# CONFIG LADEN
	# ---------------------------------------------------------
	def load_configs(self):
		if not os.path.exists('config'):
			os.makedirs('config')

		# mariadb.ini
		parser = ConfigParser()
		if os.path.exists(self.db_config_path):
			parser.read(self.db_config_path)
			if parser.has_section('database'):
				self.db_config = dict(parser.items('database'))
		else:
			self.db_config = {}

		# project.ini
		parser = ConfigParser()
		if os.path.exists(self.proj_config_path):
			parser.read(self.proj_config_path)
			if parser.has_section('settings'):
				# NICHT überschreiben – nur einlesen
				self.proj_config.read(self.proj_config_path)

		# Standardwerte, falls keine INI existiert
		if not self.proj_config.sections():
			self.proj_config["settings"] = {
				"project_name": "Default_Case",
				"watchfolder": "./evidence_input",
				"case_root": "./cases"
			}





	def load_project_config(self):
		"""Lädt project.ini und stellt sicher, dass case_root absolut ist."""
		ini_path = Path(self.proj_config_path)
		if ini_path.exists():
			self.proj_config.read(ini_path)

		case_root = self.proj_config.get("settings", "case_root", fallback="./cases")

		# IMMER absolut machen
		case_root = Path(case_root).resolve()

		# zurückschreiben
		if "settings" not in self.proj_config:
			self.proj_config["settings"] = {}

		self.proj_config["settings"]["case_root"] = str(case_root)





	# ---------------------------------------------------------
	# DB VERBINDUNG
	# ---------------------------------------------------------
	def get_connection(self):
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

	# ---------------------------------------------------------
	# ROOT-SETUP
	# ---------------------------------------------------------
	def initial_root_setup(self, root_password, user_password_to_set):
		conn = mariadb.connect(host="localhost", user="root", password=root_password)
		cur = conn.cursor()

		# Datenbank + Benutzer
		cur.execute("CREATE DATABASE IF NOT EXISTS forensic_analyzer")
		cur.execute(f"CREATE USER IF NOT EXISTS 'va_user'@'localhost' IDENTIFIED BY '{user_password_to_set}'")
		cur.execute(f"ALTER USER 'va_user'@'localhost' IDENTIFIED BY '{user_password_to_set}'")
		cur.execute("GRANT ALL PRIVILEGES ON forensic_analyzer.* TO 'va_user'@'localhost'")
		cur.execute("FLUSH PRIVILEGES")

		cur.execute("USE forensic_analyzer")

		# ---------------------------------------------------------
		# cases
		# ---------------------------------------------------------
		cur.execute("""
			CREATE TABLE IF NOT EXISTS cases (
				id INT AUTO_INCREMENT PRIMARY KEY,
				project_name VARCHAR(100) UNIQUE,
				description TEXT,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		""")

		# ---------------------------------------------------------
		# media_files
		# ---------------------------------------------------------
		cur.execute("""
			CREATE TABLE IF NOT EXISTS media_files (
				id INT AUTO_INCREMENT PRIMARY KEY,
				case_id INT,
				file_path TEXT,
				file_name VARCHAR(255),
				file_size BIGINT,
				sha256_hash VARCHAR(64) UNIQUE,
				metadata JSON,
				exif_metadata JSON,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				FOREIGN KEY (case_id) REFERENCES cases(id)
			)
		""")

		# ---------------------------------------------------------
		# suppliers
		# ---------------------------------------------------------
		cur.execute("""
			CREATE TABLE IF NOT EXISTS suppliers (
				id INT AUTO_INCREMENT PRIMARY KEY,
				name VARCHAR(255),
				contact VARCHAR(255),
				role VARCHAR(100),
				notes TEXT,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		""")

		# ---------------------------------------------------------
		# deliveries
		# ---------------------------------------------------------
		cur.execute("""
			CREATE TABLE IF NOT EXISTS deliveries (
				id INT AUTO_INCREMENT PRIMARY KEY,
				supplier_id INT,
				case_id INT,
				delivered_at TIMESTAMP,
				description TEXT,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
				FOREIGN KEY (case_id) REFERENCES cases(id)
			)
		""")

		# ---------------------------------------------------------
		# media_deliveries
		# ---------------------------------------------------------
		cur.execute("""
			CREATE TABLE IF NOT EXISTS media_deliveries (
				id INT AUTO_INCREMENT PRIMARY KEY,
				media_id INT,
				delivery_id INT,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				FOREIGN KEY (media_id) REFERENCES media_files(id),
				FOREIGN KEY (delivery_id) REFERENCES deliveries(id)
			)
		""")

		# ---------------------------------------------------------
		# mariadb.ini schreiben
		# ---------------------------------------------------------
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

		self.load_configs()


	# ---------------------------------------------------------
	# FALLVERWALTUNG
	# ---------------------------------------------------------
	def load_cases(self):
		conn = self.get_connection()
		if not conn:
			return []

		try:
			cur = conn.cursor(dictionary=True)
			cur.execute("SELECT id, project_name, description, created_at FROM cases ORDER BY created_at DESC")
			return cur.fetchall()
		finally:
			conn.close()


	def create_case(self, name, description):
		conn = self.get_connection()
		if not conn:
			raise Exception("Keine DB-Verbindung")

		try:
			cur = conn.cursor()
			cur.execute(
				"INSERT INTO cases (project_name, description) VALUES (?, ?)",
				(name, description)
			)
			conn.commit()
			case_id = cur.lastrowid
		finally:
			conn.close()

		# Absoluten case_root holen
		case_root = Path(self.proj_config.get("settings", "case_root")).resolve()
		case_path = case_root / name

		# Ordnerbaum erzeugen
		folders = [
			case_path / "evidence_input",
			case_path / "analyze_media",
			case_path / "exports",
			case_path / "reports",
			case_path / "thumbnails",
			case_path / "recovered",
			case_path / "logs"
		]

		for folder in folders:
			folder.mkdir(parents=True, exist_ok=True)

		# WICHTIG: aktuellen Fall setzen
		self.current_case_path = case_path
		self.current_case_id = case_id

		return case_id



	def load_case(self, case_id):
		conn = self.get_connection()
		if not conn:
			return None

		try:
			cur = conn.cursor(dictionary=True)
			cur.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
			case = cur.fetchone()

			if not case:
				return None

			self.current_case = case
			self.current_case_id = case_id

			# Absoluten case_root holen
			case_root = Path(self.proj_config.get("settings", "case_root")).resolve()

			# Fallpfad setzen
			self.current_case_path = case_root / case["project_name"]

			return case

		finally:
			conn.close()


	# ---------------------------------------------------------
	# HASHING
	# ---------------------------------------------------------
	def calculate_hash(self, filepath):
		sha256 = hashlib.sha256()
		try:
			with open(filepath, "rb") as f:
				for chunk in iter(lambda: f.read(8192), b""):
					sha256.update(chunk)
			return sha256.hexdigest()
		except Exception as e:
			print(f"Fehler beim Hashing von {filepath}: {e}")
			return "HASH_ERROR"

	# ---------------------------------------------------------
	# THUMBNAIL
	# ---------------------------------------------------------
	def get_thumbnail(self, filepath):
		temp_dir = "config/thumbnails"
		if not os.path.exists(temp_dir):
			os.makedirs(temp_dir)

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

	# ---------------------------------------------------------
	# DB SPEICHERN
	# ---------------------------------------------------------
	def save_to_db(self, path, name, f_hash, mi_dict, exif_dict):
		if not self.current_case_id:
			raise Exception("Kein Fall ausgewählt.")

		conn = self.get_connection()
		if not conn:
			raise Exception("Keine Datenbankverbindung möglich.")

		try:
			cur = conn.cursor()
			sql = """INSERT INTO media_files 
					 (case_id, file_path, file_name, file_size, sha256_hash, metadata, exif_metadata) 
					 VALUES (?, ?, ?, ?, ?, ?, ?)
					 ON DUPLICATE KEY UPDATE file_name=VALUES(file_name)"""

			cur.execute(sql, (
				self.current_case_id,
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

	# ---------------------------------------------------------
	# DB SUCHE
	# ---------------------------------------------------------
	def search_db(self, query):
		if not self.current_case_id:
			return []

		conn = self.get_connection()
		if not conn:
			return []

		try:
			cur = conn.cursor(dictionary=True)
			sql = """SELECT * FROM media_files 
					 WHERE case_id = ?
					 AND (
						 file_name LIKE ?
						 OR JSON_SEARCH(metadata, 'one', ?) IS NOT NULL
						 OR JSON_SEARCH(exif_metadata, 'one', ?) IS NOT NULL
					 )"""
			like_q = f"%{query}%"
			cur.execute(sql, (self.current_case_id, like_q, like_q, like_q))
			return cur.fetchall()
		finally:
			conn.close()


	# ---------------------------------------------------------
	# LIEFERANTEN & LIEFERUNGEN (NEU)
	# ---------------------------------------------------------

	def create_supplier(self, name, contact=None, role=None, notes=None):
		"""Legt einen neuen Lieferanten an."""
		conn = self.get_connection()
		if not conn:
			raise Exception("Keine DB-Verbindung")

		try:
			cur = conn.cursor()
			cur.execute(
				"INSERT INTO suppliers (name, contact, role, notes) VALUES (?, ?, ?, ?)",
				(name, contact, role, notes)
			)
			conn.commit()
			return cur.lastrowid
		finally:
			conn.close()

	def find_supplier_by_name(self, name):
		"""Sucht einen Lieferanten anhand des Namens."""
		conn = self.get_connection()
		if not conn:
			return None

		try:
			cur = conn.cursor(dictionary=True)
			cur.execute("SELECT * FROM suppliers WHERE name = ?", (name,))
			return cur.fetchone()
		finally:
			conn.close()

	def create_delivery(self, supplier_id, case_id, delivered_at, description=None):
		"""Erstellt eine Lieferung (Gruppe von Dateien eines Lieferanten)."""
		conn = self.get_connection()
		if not conn:
			raise Exception("Keine DB-Verbindung")

		try:
			cur = conn.cursor()
			cur.execute(
				"INSERT INTO deliveries (supplier_id, case_id, delivered_at, description) VALUES (?, ?, ?, ?)",
				(supplier_id, case_id, delivered_at, description)
			)
			conn.commit()
			return cur.lastrowid
		finally:
			conn.close()

	def link_media_to_delivery(self, media_id, delivery_id):
		"""Verknüpft eine Mediendatei mit einer Lieferung."""
		conn = self.get_connection()
		if not conn:
			raise Exception("Keine DB-Verbindung")

		try:
			cur = conn.cursor()
			cur.execute(
				"INSERT INTO media_deliveries (media_id, delivery_id) VALUES (?, ?)",
				(media_id, delivery_id)
			)
			conn.commit()
			return cur.lastrowid
		finally:
			conn.close()



	def get_last_delivery_for_supplier(self, supplier_id, case_id):
		conn = self.get_connection()
		if not conn:
			return None

		cur = conn.cursor(dictionary=True)
		cur.execute("""
			SELECT * FROM deliveries
			WHERE supplier_id = ? AND case_id = ?
			ORDER BY delivered_at DESC
			LIMIT 1
		""", (supplier_id, case_id))
		row = cur.fetchone()
		conn.close()
		return row




	# ---------------------------------------------------------
	# PROJEKT LADEN (optional)
	# ---------------------------------------------------------
	def load_project(self, path):
		self.project_path = path

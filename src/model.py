import mariadb
import hashlib
import os
import json
import cv2
from configparser import ConfigParser
from pymediainfo import MediaInfo
from pathlib import Path
from datetime import datetime


class ForensicModel:
	def __init__(self, project_path=None):
		self.project_path = project_path

		# Config-Dateien
		self.db_config_path = 'config/mariadb.ini'
		self.proj_config_path = 'config/project.ini'

		# interne Configs
		self.db_config = {}
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
				# in proj_config einlesen, nicht überschreiben
				self.proj_config.read(self.proj_config_path)

		# Standardwerte, falls keine INI existiert oder leer ist
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
		case_root = Path(case_root).resolve()

		if "settings" not in self.proj_config:
			self.proj_config["settings"] = {}

		self.proj_config["settings"]["case_root"] = str(case_root)

	# ---------------------------------------------------------
	# DB-VERBINDUNG
	# ---------------------------------------------------------
	def get_connection(self):
		try:
			conn = mariadb.connect(
				host=self.db_config.get("host", "localhost"),
				port=int(self.db_config.get("port", 3306)),
				user=self.db_config.get("user", "root"),
				password=self.db_config.get("password", ""),
				database=self.db_config.get("database", "forensic_analyzer")
			)
			return conn
		except mariadb.Error as e:
			print(f"[DB] Verbindungsfehler: {e}")
			return None

	# ---------------------------------------------------------
	# ROOT-SETUP   -   INITIAL-SETUP (optional, falls du Root-Setup brauchst)
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
			CREATE TABLE `cases` (
			  `id` int(11) NOT NULL AUTO_INCREMENT,
			  `project_name` varchar(255) NOT NULL,
			  `description` text DEFAULT NULL,
			  `created_at` timestamp NULL DEFAULT current_timestamp(),
			  PRIMARY KEY (`id`)
			) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci

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
			CREATE TABLE `suppliers` (
			  `id` int(11) NOT NULL AUTO_INCREMENT,
			  `name` varchar(255) NOT NULL,
			  `contact` varchar(255) DEFAULT NULL,
			  `role` varchar(255) DEFAULT NULL,
			  `notes` text DEFAULT NULL,
			  `created_at` timestamp NULL DEFAULT current_timestamp(),
			  PRIMARY KEY (`id`)
			) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci

		""")

		# ---------------------------------------------------------
		# deliveries
		# ---------------------------------------------------------
		cur.execute("""
			CREATE TABLE `deliveries` (
			  `id` int(11) NOT NULL AUTO_INCREMENT,
			  `supplier_id` int(11) NOT NULL,
			  `case_id` int(11) NOT NULL,
			  `delivered_at` datetime DEFAULT NULL,
			  `description` text DEFAULT NULL,
			  `created_at` timestamp NULL DEFAULT current_timestamp(),
			  PRIMARY KEY (`id`),
			  KEY `supplier_id` (`supplier_id`),
			  KEY `case_id` (`case_id`),
			  CONSTRAINT `1` FOREIGN KEY (`supplier_id`) REFERENCES `suppliers` (`id`),
			  CONSTRAINT `2` FOREIGN KEY (`case_id`) REFERENCES `cases` (`id`)
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
	# CASE-MANAGEMENT
	# ---------------------------------------------------------
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

		# aktuellen Fall setzen
		self.current_case_path = case_path
		self.current_case_id = case_id

		return case_id

	def load_cases(self):
		"""Lädt alle Fälle (für Fallliste im Launcher/Presenter)."""
		conn = self.get_connection()
		if not conn:
			return []

		try:
			cur = conn.cursor(dictionary=True)
			cur.execute("SELECT * FROM cases ORDER BY id DESC")
			rows = cur.fetchall()
			return rows
		finally:
			conn.close()

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
	# HASHING / THUMBNAILS / MEDIAINFO
	# ---------------------------------------------------------
	def calculate_hash(self, filepath):
		"""Berechnet SHA256-Hash einer Datei."""
		sha256 = hashlib.sha256()
		with open(filepath, "rb") as f:
			for chunk in iter(lambda: f.read(8192), b""):
				sha256.update(chunk)
		return sha256.hexdigest()

	def get_thumbnail(self, filepath):
		"""Erzeugt ein Thumbnail (Frame 0) mit OpenCV."""
		if not self.current_case_path:
			# Fallback: Thumbnail neben Datei
			thumb_dir = Path(filepath).parent
		else:
			thumb_dir = Path(self.current_case_path) / "thumbnails"

		thumb_dir.mkdir(parents=True, exist_ok=True)

		cap = cv2.VideoCapture(str(filepath))
		success, frame = cap.read()
		cap.release()

		if not success or frame is None:
			# Kein Frame → Dummy
			thumb_path = thumb_dir / (Path(filepath).stem + "_thumb.jpg")
			return str(thumb_path)

		thumb_path = thumb_dir / (Path(filepath).stem + "_thumb.jpg")
		cv2.imwrite(str(thumb_path), frame)
		return str(thumb_path)

	# ---------------------------------------------------------
	# MEDIA IN DB SPEICHERN
	# ---------------------------------------------------------
	def save_to_db(self, path, name, f_hash, mi_dict, exif_dict):
		if not self.current_case_id:
			raise Exception("Kein Fall ausgewählt.")

		conn = self.get_connection()
		if not conn:
			print("[DB] Keine Verbindung in save_to_db()")
			return

		try:
			cur = conn.cursor()
			cur.execute(
				"""
				INSERT INTO media_files
					(case_id, file_path, file_name, file_size, sha256_hash, metadata, exif_metadata)
				VALUES (?, ?, ?, ?, ?, ?, ?)
				ON DUPLICATE KEY UPDATE
					file_name = VALUES(file_name),
					metadata = VALUES(metadata),
					exif_metadata = VALUES(exif_metadata)
				""",
				(
					self.current_case_id,
					path,
					name,
					os.path.getsize(path),
					f_hash,
					json.dumps(mi_dict, ensure_ascii=False),
					json.dumps(exif_dict, ensure_ascii=False)
				)
			)
			conn.commit()
		finally:
			conn.close()

	# ---------------------------------------------------------
	# SUCHE
	# ---------------------------------------------------------
	def search_db(self, query):
		"""Einfache Volltextsuche über file_name / metadata / exif_metadata."""
		if not self.current_case_id:
			return []

		conn = self.get_connection()
		if not conn:
			return []

		try:
			cur = conn.cursor(dictionary=True)
			like = f"%{query}%"
			cur.execute(
				"""
				SELECT * FROM media_files
				WHERE case_id = ?
				  AND (
					file_name LIKE ?
					OR JSON_SEARCH(metadata, 'one', ?) IS NOT NULL
					OR JSON_SEARCH(exif_metadata, 'one', ?) IS NOT NULL
				  )
				ORDER BY id DESC
				""",
				(self.current_case_id, like, like, like)
			)
			rows = cur.fetchall()
			return rows
		finally:
			conn.close()

	# ---------------------------------------------------------
	# SUPPLIER / DELIVERY
	# ---------------------------------------------------------
	def create_supplier(self, name, contact=None, role=None, notes=None):
		conn = self.get_connection()
		if not conn:
			raise Exception("Keine DB-Verbindung")

		try:
			cur = conn.cursor()
			cur.execute(
				"""
				INSERT INTO suppliers (name, contact, role, notes)
				VALUES (?, ?, ?, ?)
				""",
				(name, contact, role, notes)
			)
			conn.commit()
			return cur.lastrowid
		finally:
			conn.close()

	def find_supplier_by_name(self, name):
		conn = self.get_connection()
		if not conn:
			return None

		try:
			cur = conn.cursor(dictionary=True)
			cur.execute(
				"SELECT * FROM suppliers WHERE name = ?",
				(name,)
			)
			row = cur.fetchone()
			return row
		finally:
			conn.close()

	def create_delivery(self, supplier_id, case_id, delivered_at, description=None):
		conn = self.get_connection()
		if not conn:
			raise Exception("Keine DB-Verbindung")

		try:
			cur = conn.cursor()
			cur.execute(
				"""
				INSERT INTO deliveries (supplier_id, case_id, delivered_at, description)
				VALUES (?, ?, ?, ?)
				""",
				(supplier_id, case_id, delivered_at, description)
			)
			conn.commit()
			return cur.lastrowid
		finally:
			conn.close()

	def link_media_to_delivery(self, media_id, delivery_id):
		conn = self.get_connection()
		if not conn:
			return

		try:
			cur = conn.cursor()
			cur.execute(
				"""
				INSERT INTO media_deliveries (delivery_id, media_id)
				VALUES (?, ?)
				""",
				(delivery_id, media_id)
			)
			conn.commit()
		finally:
			conn.close()

	def get_last_delivery_for_supplier(self, supplier_id, case_id):
		"""Letzte Lieferung eines Lieferanten in einem Fall."""
		conn = self.get_connection()
		if not conn:
			return None

		try:
			cur = conn.cursor(dictionary=True)
			cur.execute(
				"""
				SELECT *
				FROM deliveries
				WHERE supplier_id = ? AND case_id = ?
				ORDER BY delivered_at DESC, id DESC
				LIMIT 1
				""",
				(supplier_id, case_id)
			)
			row = cur.fetchone()
			return row
		finally:
			conn.close()

	# ---------------------------------------------------------
	# PROJECT-LOADING (falls du projektbezogene Pfade nutzt)
	# ---------------------------------------------------------
	def load_project(self, path):
		"""Optional: Projekt-spezifische Logik, falls du mehrere Projekte hast."""
		self.project_path = Path(path).resolve()
		# Hier könntest du z.B. weitere Configs laden, Logs, etc.
		print(f"[MODEL] Projekt geladen: {self.project_path}")

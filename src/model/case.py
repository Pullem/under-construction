import mariadb
from configparser import ConfigParser
from pathlib import Path

from .base import BASE_DIR


class CaseMixin:
	def create_case(self, name, description, incident_at=None, incident_until=None):
		conn = self.get_connection()
		if not conn:
			raise Exception("Keine DB-Verbindung")

		try:
			cur = conn.cursor()
			cur.execute(
				"INSERT INTO cases (project_name, description, incident_at, incident_until) VALUES (?, ?, ?, ?)",
				(name, description, incident_at, incident_until)
			)
			conn.commit()
			case_id = cur.lastrowid
		finally:
			conn.close()

		case_path = self.get_case_root() / name
		self.ensure_case_folders(case_path)

		self.current_case_path = case_path
		self.current_case_id = case_id

		return case_id

	def load_cases(self):
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
			self.current_case_path = self.get_case_path(case["project_name"])
			self.ensure_case_folders(self.current_case_path)

			return case
		finally:
			conn.close()

	def initial_root_setup(self, root_password, user_password_to_set):
		conn = mariadb.connect(host="localhost", user="root", password=root_password)
		cur = conn.cursor()

		cur.execute("CREATE DATABASE IF NOT EXISTS forensic_analyzer")
		cur.execute(f"CREATE USER IF NOT EXISTS 'va_user'@'localhost' IDENTIFIED BY '{user_password_to_set}'")
		cur.execute(f"ALTER USER 'va_user'@'localhost' IDENTIFIED BY '{user_password_to_set}'")
		cur.execute("GRANT ALL PRIVILEGES ON forensic_analyzer.* TO 'va_user'@'localhost'")
		cur.execute("FLUSH PRIVILEGES")

		cur.execute("USE forensic_analyzer")

		cur.execute("""
			CREATE TABLE IF NOT EXISTS `cases` (
			  `id` int(11) NOT NULL AUTO_INCREMENT,
			  `project_name` varchar(255) NOT NULL,
			  `description` text DEFAULT NULL,
			  `incident_at` datetime DEFAULT NULL,
			  `incident_until` datetime DEFAULT NULL,
			  `created_at` timestamp NULL DEFAULT current_timestamp(),
			  PRIMARY KEY (`id`)
			) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci
		""")

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

		self.db_config = {
			"host": "localhost",
			"user": "va_user",
			"password": user_password_to_set,
			"port": "3306",
		}
		self.root_password = root_password
		self.save_db_config()

		conn.commit()
		conn.close()

		self.load_configs()

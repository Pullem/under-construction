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
		# Projektpfad (optional, aber nicht mehr für DB genutzt)
		self.project_path = project_path

		# Pfade zu den Config-Dateien
		self.db_config_path = 'config/mariadb.ini'
		self.proj_config_path = 'config/projekt.ini'

		# interne Config-Strukturen
		self.db_config = {}
		self.proj_config = {}

		# aktueller Fall
		self.current_case = None
		self.current_case_id = None

		# Configs laden
		self.load_configs()

		# Projektpfad (optional)
		if self.project_path:
			self.load_project(self.project_path)

	# ---------------------------------------------------------
	# CONFIG LADEN
	# ---------------------------------------------------------
	def load_configs(self):
		"""Lädt mariadb.ini und projekt.ini. Erstellt config-Ordner falls nötig."""
		if not os.path.exists('config'):
			os.makedirs('config')

		# --- mariadb.ini ---
		parser = ConfigParser()
		if os.path.exists(self.db_config_path):
			parser.read(self.db_config_path)
			if parser.has_section('database'):
				self.db_config = dict(parser.items('database'))
		else:
			self.db_config = {}

		# --- projekt.ini ---
		parser = ConfigParser()
		if os.path.exists(self.proj_config_path):
			parser.read(self.proj_config_path)
			if parser.has_section('settings'):
				self.proj_config = dict(parser.items('settings'))

		# Standardwerte
		if not self.proj_config:
			self.proj_config = {
				'project_name': 'Default_Case',
				'watchfolder': './evidence_input'
			}

	# ---------------------------------------------------------
	# DB VERBINDUNG
	# ---------------------------------------------------------
	def get_connection(self):
		"""Gibt eine aktive MariaDB-Verbindung zurück oder None."""
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
	# ROOT-SETUP (DB anlegen, User anlegen, mariadb.ini schreiben)
	# ---------------------------------------------------------
	def initial_root_setup(self, root_password, user_password_to_set):
		conn = mariadb.connect(host="localhost", user="root", password=root_password)
		cur = conn.cursor()

		# 1. DB & User
		cur.execute("CREATE DATABASE IF NOT EXISTS forensic_analyzer")
		cur.execute(f"CREATE USER IF NOT EXISTS 'va_user'@'localhost' IDENTIFIED BY '{user_password_to_set}'")
		cur.execute(f"ALTER USER 'va_user'@'localhost' IDENTIFIED BY '{user_password_to_set}'")
		cur.execute("GRANT ALL PRIVILEGES ON forensic_analyzer.* TO 'va_user'@'localhost'")
		cur.execute("FLUSH PRIVILEGES")

		# 2. Tabellen
		cur.execute("USE forensic_analyzer")

		# --- NEU: cases-Tabelle ---
		cur.execute("""
			CREATE TABLE IF NOT EXISTS cases (
				id INT AUTO_INCREMENT PRIMARY KEY,
				project_name VARCHAR(100) UNIQUE,
				description TEXT,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		""")

		# --- media_files auf case_id umgestellt ---
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

		# 3. mariadb.ini schreiben
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

		# Configs neu laden
		self.load_configs()

	# ---------------------------------------------------------
	# FALLVERWALTUNG
	# ---------------------------------------------------------
	def load_cases(self):
		"""Lädt alle Fälle aus der DB."""
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
		"""Legt einen neuen Fall an."""
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
			return cur.lastrowid
		finally:
			conn.close()

	def load_case(self, case_id):
		"""Lädt einen Fall und speichert ihn im Model."""
		conn = self.get_connection()

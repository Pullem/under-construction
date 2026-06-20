import os
import mariadb
from configparser import ConfigParser
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent
CASE_SUBFOLDERS = (
	"evidence_input",
	"analyze_media",
	"exports",
	"reports",
	"thumbnails",
	"recovered",
	"logs",
)


class ConfigDBMixin:
	def __init__(self, project_path=None, **kwargs):
		super().__init__(**kwargs)
		self.project_path = project_path

		self.db_config_path = BASE_DIR / "config" / "mariadb.ini"
		self.proj_config_path = BASE_DIR / "config" / "project.ini"

		self.db_config = {}
		self.proj_config = ConfigParser()

		self.current_case = None
		self.current_case_id = None
		self.current_case_path = None

		self.load_configs()
		self.load_project_config()

		if self.project_path:
			self.load_project(self.project_path)

	def load_configs(self):
		config_dir = BASE_DIR / "config"
		config_dir.mkdir(parents=True, exist_ok=True)

		parser = ConfigParser()
		if self.db_config_path.exists():
			parser.read(self.db_config_path)
			if parser.has_section('database'):
				self.db_config = dict(parser.items('database'))
		else:
			self.db_config = {}

		if self.proj_config_path.exists():
			self.proj_config.read(self.proj_config_path)

	def load_project_config(self):
		if self.proj_config_path.exists():
			self.proj_config.read(self.proj_config_path)

		if "settings" not in self.proj_config:
			self.proj_config["settings"] = {}

		case_root = self.proj_config.get("settings", "case_root", fallback="").strip()
		if case_root:
			self.proj_config["settings"]["case_root"] = str(Path(case_root).resolve())

	def get_case_root(self):
		case_root = self.proj_config.get("settings", "case_root", fallback="").strip()
		if not case_root:
			raise Exception(
				"Kein case_root konfiguriert. Bitte in config/project.ini setzen "
				"oder beim ersten Start den Speicherort wählen."
			)
		return Path(case_root).resolve()

	def get_case_path(self, case_name=None):
		name = case_name
		if not name and self.current_case:
			name = self.current_case.get("project_name")
		if not name:
			raise Exception("Kein Fallname verfügbar.")
		return self.get_case_root() / name

	def ensure_case_folders(self, case_path=None):
		case_path = Path(case_path or self.current_case_path or self.get_case_path())
		for subfolder in CASE_SUBFOLDERS:
			(case_path / subfolder).mkdir(parents=True, exist_ok=True)
		return case_path

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

	def save_project_config(self):
		config_dir = self.proj_config_path.parent
		config_dir.mkdir(parents=True, exist_ok=True)
		with open(self.proj_config_path, "w") as f:
			self.proj_config.write(f)

	def load_project(self, path):
		self.project_path = Path(path).resolve()
		print(f"[MODEL] Projekt geladen: {self.project_path}")

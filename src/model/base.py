import os
import mariadb
import logging
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


logger = logging.getLogger(__name__)


class ConfigDBMixin:
	# Pool defaults
	DEFAULT_POOL_SIZE = 10
	DEFAULT_POOL_MAX_OVERFLOW = 5
	DEFAULT_POOL_TIMEOUT = 30  # seconds
	DEFAULT_POOL_RECYCLE = 3600  # seconds (1 hour)

	def __init__(self, project_path=None, **kwargs):
		super().__init__(**kwargs)
		self.project_path = project_path

		self.db_config_path = BASE_DIR / "config" / "mariadb.ini"
		self.proj_config_path = BASE_DIR / "config" / "project.ini"

		self.db_config = {}
		self.proj_config = ConfigParser()
		self.root_password = ""

		self.current_case = None
		self.current_case_id = None
		self.current_case_path = None

		# Connection pool (initialized lazily)
		self._connection_pool = None

		self.load_configs()
		self.load_project_config()

		if self.project_path:
			self.load_project(self.project_path)

	def load_configs(self):
		config_dir = BASE_DIR / "config"
		config_dir.mkdir(parents=True, exist_ok=True)

		parser = ConfigParser(interpolation=None)
		if self.db_config_path.exists():
			parser.read(self.db_config_path)
			if parser.has_section('database'):
				self.db_config = dict(parser.items('database'))
			if parser.has_section('pool'):
				# Pool settings are stored as strings, convert appropriately
				for key in ('pool_size', 'pool_max_overflow', 'pool_timeout', 'pool_recycle'):
					if parser.has_option('pool', key):
						self.db_config[key] = parser.get('pool', key)
			self.root_password = parser.get('root', 'password', fallback='') if parser.has_section('root') else ''
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

	def _get_pool_config(self):
		"""Extract pool configuration from db_config with defaults."""
		return {
			"pool_size": int(self.db_config.get("pool_size", self.DEFAULT_POOL_SIZE)),
			"pool_max_overflow": int(self.db_config.get("pool_max_overflow", self.DEFAULT_POOL_MAX_OVERFLOW)),
			"pool_timeout": int(self.db_config.get("pool_timeout", self.DEFAULT_POOL_TIMEOUT)),
			"pool_recycle": int(self.db_config.get("pool_recycle", self.DEFAULT_POOL_RECYCLE)),
		}

	def _get_connection_params(self):
		"""Extract connection parameters from db_config."""
		return {
			"host": self.db_config.get("host", "localhost"),
			"port": int(self.db_config.get("port", 3306)),
			"user": self.db_config.get("user", "root"),
			"password": self.db_config.get("password", ""),
			"database": self.db_config.get("database", "forensic_analyzer"),
		}

	def _init_pool(self):
		"""Initialize the connection pool if not already initialized."""
		if self._connection_pool is not None:
			return

		pool_config = self._get_pool_config()
		conn_params = self._get_connection_params()

		try:
			self._connection_pool = mariadb.ConnectionPool(
				pool_name="forensic_pool",
				**pool_config,
				**conn_params
			)
			logger.info("Connection pool initialized: size=%d, max_overflow=%d",
						pool_config["pool_size"], pool_config["pool_max_overflow"])
		except mariadb.Error as e:
			logger.error("Failed to initialize connection pool: %s", e)
			self._connection_pool = None
			raise

	def get_connection(self):
		"""Get a connection from the pool. Falls back to direct connection if pool unavailable."""
		# Try pool first
		if self._connection_pool is None:
			try:
				self._init_pool()
			except Exception:
				pass  # Fall through to direct connection

		if self._connection_pool is not None:
			try:
				return self._connection_pool.get_connection()
			except mariadb.PoolError as e:
				logger.warning("Pool exhausted, falling back to direct connection: %s", e)
			except mariadb.Error as e:
				logger.error("Pool connection error: %s", e)

		# Fallback: direct connection (original behavior)
		try:
			conn = mariadb.connect(**self._get_connection_params())
			return conn
		except mariadb.Error as e:
			logger.error("Database connection error: %s", e)
			return None

	def close_pool(self):
		"""Close all connections in the pool. Call on application shutdown."""
		if self._connection_pool is not None:
			try:
				self._connection_pool.close()
				logger.info("Connection pool closed")
			except Exception as e:
				logger.warning("Error closing connection pool: %s", e)
			finally:
				self._connection_pool = None

	def get_pool_status(self):
		"""Return pool status for monitoring/debugging."""
		if self._connection_pool is None:
			return {"active": False}
		try:
			return {
				"active": True,
				"pool_size": self._connection_pool.pool_size,
				"pool_max_overflow": self._connection_pool.pool_max_overflow,
				"available": self._connection_pool.available_connections,
				"in_use": self._connection_pool.pool_size - self._connection_pool.available_connections,
			}
		except Exception as e:
			logger.warning("Could not get pool status: %s", e)
			return {"active": True, "error": str(e)}

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

	def save_db_config(self):
		config_dir = self.db_config_path.parent
		config_dir.mkdir(parents=True, exist_ok=True)
		parser = ConfigParser(interpolation=None)
		parser.add_section("database")
		for k, v in self.db_config.items():
			if k.startswith("pool_"):
				continue  # Pool settings go to separate section
			parser.set("database", k, str(v))
		if self.root_password:
			parser.add_section("root")
			parser.set("root", "password", self.root_password)
		# Write pool settings to separate section
		if any(k.startswith("pool_") for k in self.db_config):
			parser.add_section("pool")
			for k, v in self.db_config.items():
				if k.startswith("pool_"):
					parser.set("pool", k, str(v))
		with open(self.db_config_path, "w") as f:
			parser.write(f)

	def save_project_config(self):
		config_dir = self.proj_config_path.parent
		config_dir.mkdir(parents=True, exist_ok=True)
		with open(self.proj_config_path, "w") as f:
			self.proj_config.write(f)

	def load_project(self, path):
		self.project_path = Path(path).resolve()
		logger.info("Project loaded: %s", self.project_path)
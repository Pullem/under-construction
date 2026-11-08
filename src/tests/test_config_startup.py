"""
Tests für das Start-/Reset-Verhalten der Konfiguration (AGENTS.md Abschnitt 12).

Nach einem kompletten Reset (mariadb.ini bzw. Datenbank gelöscht) muss die
Anwendung das Initial-Setup erneut anstoßen. Eine einmal geschriebene
mariadb.ini muss alle Pflicht-Keys für den ConfigValidator enthalten,
sonst endet der Start im Fehlerdialog ohne Ausweg.
"""

import tempfile
import unittest
from configparser import ConfigParser
from pathlib import Path

from src.model.base import ConfigDBMixin
from src.utils.config_validator import ConfigValidator

COMPLETE_DB_CONFIG = {
	"host": "localhost",
	"user": "va_user",
	"password": "secret",
	"port": "3306",
	"database": "forensic_analyzer",
}


class _StubConfig(ConfigDBMixin):
	"""ConfigDBMixin ohne Datei- und Datenbank-Initialisierung."""

	def __init__(self, db_config, config_path):
		self.project_path = None
		self.db_config_path = config_path
		self.proj_config_path = config_path.parent / "project.ini"
		self.db_config = dict(db_config)
		self.proj_config = ConfigParser()
		self.root_password = ""
		self._connection_pool = None


class DbConfigCompletenessTest(unittest.TestCase):
	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.config_path = Path(self._tmp.name) / "mariadb.ini"

	def test_complete_config(self):
		cfg = _StubConfig(COMPLETE_DB_CONFIG, self.config_path)
		self.assertTrue(cfg.is_db_config_complete())

	def test_missing_database_key(self):
		incomplete = {k: v for k, v in COMPLETE_DB_CONFIG.items() if k != "database"}
		cfg = _StubConfig(incomplete, self.config_path)
		self.assertFalse(cfg.is_db_config_complete())
		# Setup-Check darf ohne Datenbankzugriff True liefern
		self.assertTrue(cfg.db_setup_required())

	def test_empty_password(self):
		cfg = _StubConfig({**COMPLETE_DB_CONFIG, "password": ""}, self.config_path)
		self.assertFalse(cfg.is_db_config_complete())
		self.assertTrue(cfg.db_setup_required())

	def test_missing_config_file(self):
		cfg = _StubConfig({}, self.config_path)
		self.assertFalse(cfg.is_db_config_complete())
		self.assertTrue(cfg.db_setup_required())


class SaveDbConfigTest(unittest.TestCase):
	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.config_path = Path(self._tmp.name) / "mariadb.ini"

	def test_database_key_is_always_written(self):
		"""save_db_config ergänzt fehlende Pflicht-Keys (sonst scheitert der Start)."""
		cfg = _StubConfig(
			{"host": "localhost", "user": "va_user", "password": "x", "port": "3306"},
			self.config_path,
		)
		cfg.save_db_config()

		parser = ConfigParser(interpolation=None)
		parser.read(self.config_path)
		self.assertTrue(parser.has_section("database"))
		self.assertEqual(parser.get("database", "database"), "forensic_analyzer")

	def test_existing_database_key_is_kept(self):
		cfg = _StubConfig(COMPLETE_DB_CONFIG, self.config_path)
		cfg.save_db_config()

		parser = ConfigParser(interpolation=None)
		parser.read(self.config_path)
		self.assertEqual(parser.get("database", "database"), "forensic_analyzer")


class CaseRootSetupTest(unittest.TestCase):
	"""case_root aus project.ini [settings] und dessen Unterordner (Test-Signale)."""

	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.base = Path(self._tmp.name)
		self.case_root = self.base / "cases"
		self.case_root.mkdir()
		self.config_path = self.base / "config" / "mariadb.ini"

	def test_set_case_root_creates_subfolder(self):
		"""Erst case_root speichern, danach Test-Signale darin anlegen."""
		cfg = _StubConfig({}, self.config_path)

		created = cfg.set_case_root(self.case_root)

		self.assertIn(str(self.case_root / "Test-Signale"), created)
		self.assertTrue((self.case_root / "Test-Signale").is_dir())

		parser = ConfigParser(interpolation=None)
		parser.read(cfg.proj_config_path)
		self.assertEqual(Path(parser.get("settings", "case_root")), self.case_root.resolve())
		self.assertEqual(cfg.get_case_root(), self.case_root.resolve())

	def test_subfolder_is_idempotent(self):
		cfg = _StubConfig({}, self.config_path)
		cfg.set_case_root(self.case_root)
		created = cfg.ensure_case_root_folders()
		self.assertEqual(len(created), 1)

	def test_missing_case_root_is_not_created(self):
		"""Ein ungültiger case_root wird nicht stillschweigend angelegt."""
		cfg = _StubConfig({}, self.config_path)
		missing = self.base / "gibt_es_nicht"

		self.assertEqual(cfg.ensure_case_root_folders(missing), [])
		self.assertFalse(missing.exists())

	def test_unset_case_root_creates_nothing(self):
		cfg = _StubConfig({}, self.config_path)

		self.assertEqual(cfg.ensure_case_root_folders(), [])
		self.assertFalse((self.base / "Test-Signale").exists())


class ValidatorMissingKeyTest(unittest.TestCase):
	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.base_dir = Path(self._tmp.name)
		config_dir = self.base_dir / "config"
		config_dir.mkdir()

		# mariadb.ini ohne Pflicht-Key 'database'
		(config_dir / "mariadb.ini").write_text(
			"[database]\nhost = localhost\nuser = va_user\n"
			"password = secret\nport = 3306\n",
			encoding="utf-8",
		)
		# project.ini mit existierendem case_root
		case_root = self.base_dir / "cases"
		case_root.mkdir()
		(config_dir / "project.ini").write_text(
			f"[settings]\ncase_root = {case_root}\n",
			encoding="utf-8",
		)

	def test_validator_reports_missing_database_key(self):
		result = ConfigValidator(self.base_dir).validate_all(model=None)
		self.assertTrue(result.has_errors)

		messages = [str(e) for e in result.errors]
		self.assertTrue(
			any("Fehlende Keys in [database]: database" in m for m in messages),
			msg=f"Erwarteter Fehler in: {messages}",
		)
		self.assertTrue(
			any("[CONFIG_MISSING]" in m for m in messages),
			msg=f"Erwarteter ErrorCode in: {messages}",
		)


if __name__ == "__main__":
	unittest.main()

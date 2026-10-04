import logging
import subprocess
import shutil
from pathlib import Path
from configparser import ConfigParser
from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.utils.errors import AppError, ErrorCode, config_error, external_tool_error


logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
	success: bool
	errors: List[AppError]
	warnings: List[str]

	@property
	def has_errors(self) -> bool:
		return len(self.errors) > 0

	def add_error(self, error: AppError):
		self.errors.append(error)
		self.success = False

	def add_warning(self, warning: str):
		self.warnings.append(warning)


class ConfigValidator:
	"""Validates all configuration at application startup."""

	REQUIRED_EXTERNAL_TOOLS = [
		("ffmpeg.exe", "FFmpeg"),
		("ffprobe.exe", "FFprobe"),
		("exiftool.exe", "ExifTool"),
		("mediainfo", "MediaInfo CLI"),  # 'mediainfo' in PATH or mediainfo.exe
	]

	def __init__(self, base_dir: Path):
		self.base_dir = base_dir
		self.config_dir = base_dir / "config"
		self.mariadb_ini = self.config_dir / "mariadb.ini"
		self.project_ini = self.config_dir / "project.ini"

	def validate_all(self, model=None) -> ValidationResult:
		"""Run all validation checks."""
		result = ValidationResult(success=True, errors=[], warnings=[])

		# 1. Config directory
		self._validate_config_dir(result)

		# 2. mariadb.ini
		self._validate_mariadb_ini(result)

		# 3. project.ini (case_root)
		self._validate_project_ini(result)

		# 4. DB connection test (if model provided)
		if model and result.success:
			self._validate_db_connection(model, result)

		# 4. External tools
		self._validate_external_tools(result)

		# 5. Case directory writability
		if model and model.current_case_path and result.success:
			self._validate_case_directory(model, result)

		return result

	def _validate_config_dir(self, result: ValidationResult):
		if not self.config_dir.exists():
			result.add_error(config_error(
				"Config-Verzeichnis fehlt",
				config_file=str(self.config_dir),
				exc=FileNotFoundError(str(self.config_dir))
			))
		elif not self.config_dir.is_dir():
			result.add_error(config_error(
				"Config-Pfad ist keine Verzeichnis",
				config_file=str(self.config_dir)
			))

	def _validate_mariadb_ini(self, result: ValidationResult):
		if not self.mariadb_ini.exists():
			result.add_error(config_error(
				"MariaDB-Konfiguration fehlt (mariadb.ini)",
				config_file=str(self.mariadb_ini),
				exc=FileNotFoundError(str(self.mariadb_ini))
			))
			return

		parser = ConfigParser(interpolation=None)
		try:
			parser.read(self.mariadb_ini)
		except Exception as e:
			result.add_error(config_error(
				"mariadb.ini nicht lesbar / ungültiges Format",
				config_file=str(self.mariadb_ini),
				exc=e
			))
			return

		if not parser.has_section('database'):
			result.add_error(config_error(
				"mariadb.ini: Section [database] fehlt",
				config_file=str(self.mariadb_ini)
			))
			return

		required_keys = ['host', 'user', 'password', 'port', 'database']
		missing = [k for k in required_keys if not parser.has_option('database', k)]
		if missing:
			result.add_error(config_error(
				f"mariadb.ini: Fehlende Keys in [database]: {', '.join(missing)}",
				config_file=str(self.mariadb_ini)
			))

		# Validate port is integer
		if parser.has_option('database', 'port'):
			try:
				int(parser.get('database', 'port'))
			except ValueError:
				result.add_error(config_error(
					"mariadb.ini: 'port' muss eine Zahl sein",
					config_file=str(self.mariadb_ini)
				))

	def _validate_project_ini(self, result: ValidationResult):
		if not self.project_ini.exists():
			result.add_error(config_error(
				"Projekt-Konfiguration fehlt (project.ini)",
				config_file=str(self.project_ini),
				exc=FileNotFoundError(str(self.project_ini))
			))
			return

		parser = ConfigParser(interpolation=None)
		try:
			parser.read(self.project_ini)
		except Exception as e:
			result.add_error(config_error(
				"project.ini nicht lesbar / ungültiges Format",
				config_file=str(self.project_ini),
				exc=e
			))
			return

		if not parser.has_section('settings'):
			result.add_error(config_error(
				"project.ini: Section [settings] fehlt",
				config_file=str(self.project_ini)
			))
			return

		case_root = parser.get('settings', 'case_root', fallback='').strip()
		if not case_root:
			result.add_error(config_error(
				"project.ini: 'case_root' nicht gesetzt in [settings]",
				config_file=str(self.project_ini)
			))
			return

		case_root_path = Path(case_root)
		if not case_root_path.exists():
			result.add_error(config_error(
				f"project.ini: case_root Verzeichnis existiert nicht: {case_root}",
				config_file=str(self.project_ini),
				exc=FileNotFoundError(case_root)
			))
		elif not case_root_path.is_dir():
			result.add_error(config_error(
				f"project.ini: case_root ist kein Verzeichnis: {case_root}",
				config_file=str(self.project_ini)
			))
		else:
			# Test writability
			try:
				test_file = case_root_path / ".write_test"
				test_file.write_text("test")
				test_file.unlink()
			except Exception as e:
				result.add_error(config_error(
					f"project.ini: case_root nicht beschreibbar: {case_root}",
					config_file=str(self.project_ini),
					exc=e
				))

	def _validate_db_connection(self, model, result: ValidationResult):
		"""Test actual database connectivity."""
		try:
			conn = model.get_connection()
			if conn is None:
				result.add_error(AppError(
					code=ErrorCode.DB_CONNECTION,
					message="Datenbankverbindung fehlgeschlagen (get_connection returned None)",
					severity=ErrorSeverity.CRITICAL,
					recoverable=False
				))
				return
			conn.close()
			logger.info("Database connection test successful")
		except Exception as e:
			result.add_error(AppError.from_exception(
				e, code=ErrorCode.DB_CONNECTION,
				context={"host": model.db_config.get('host'), "database": model.db_config.get('database')},
				severity=ErrorSeverity.CRITICAL,
				recoverable=False
			))

	def _validate_external_tools(self, result: ValidationResult):
		"""Check required external tools are available."""
		for tool_name, display_name in self.REQUIRED_EXTERNAL_TOOLS:
			tool_path = self.base_dir / tool_name
			if tool_name == "mediainfo":
				# mediainfo might be in PATH
				found = shutil.which("mediainfo") is not None
				if not found:
					result.add_warning(f"{display_name} (mediainfo) nicht in PATH gefunden – GPS/Timecode-Extraktion eingeschränkt")
				continue

			if not tool_path.exists():
				result.add_error(external_tool_error(
					tool_name, f"{display_name} nicht gefunden", filepath=str(tool_path)
				))
			elif not os.access(tool_path, os.X_OK):
				result.add_warning(f"{display_name} gefunden aber nicht ausführbar: {tool_path}")

	def _validate_case_directory(self, model, result: ValidationResult):
		"""Validate current case directory structure."""
		case_path = model.current_case_path
		if not case_path:
			return

		for subfolder in model.CASE_SUBFOLDERS:
			folder = case_path / subfolder
			if not folder.exists():
				try:
					folder.mkdir(parents=True, exist_ok=True)
					result.add_warning(f"Fehlender Case-Unterordner erstellt: {subfolder}")
				except Exception as e:
					result.add_error(config_error(
						f"Case-Unterordner {subfolder} nicht erstellbar",
						config_file=str(folder),
						exc=e
					))


# Backward compatibility
import os
ErrorSeverity = None  # Will be imported from errors

def validate_startup(model=None, base_dir: Path = None) -> Tuple[bool, List[str]]:
	"""Legacy function for simple validation."""
	from src.utils.errors import ErrorSeverity as ES
	
	if base_dir is None:
		base_dir = Path(__file__).resolve().parent.parent.parent
	
	validator = ConfigValidator(base_dir)
	vr = validator.validate_all(model)
	
	messages = [str(e) for e in vr.errors]
	return (not vr.has_errors, messages)
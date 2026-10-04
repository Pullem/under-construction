import json
import traceback
from dataclasses import dataclass, field, asdict
from typing import Any, Optional, Dict
from enum import Enum


class ErrorCode(Enum):
	"""Standardized error codes for categorization."""
	UNKNOWN = "UNKNOWN"
	DB_CONNECTION = "DB_CONNECTION"
	DB_QUERY = "DB_QUERY"
	DB_CONSTRAINT = "DB_CONSTRAINT"
	FILE_NOT_FOUND = "FILE_NOT_FOUND"
	FILE_PERMISSION = "FILE_PERMISSION"
	FILE_CORRUPT = "FILE_CORRUPT"
	IMPORT_FAILED = "IMPORT_FAILED"
	EXPORT_FAILED = "EXPORT_FAILED"
	ANALYSIS_FAILED = "ANALYSIS_FAILED"
	EXTERNAL_TOOL_MISSING = "EXTERNAL_TOOL_MISSING"
	EXTERNAL_TOOL_FAILED = "EXTERNAL_TOOL_FAILED"
	CONFIG_MISSING = "CONFIG_MISSING"
	CONFIG_INVALID = "CONFIG_INVALID"
	WORKER_CRASHED = "WORKER_CRASHED"
	THUMBNAIL_FAILED = "THUMBNAIL_FAILED"
	FFMPEG_FAILED = "FFMPEG_FAILED"
	FFPROBE_FAILED = "FFPROBE_FAILED"
	VALIDATION_FAILED = "VALIDATION_FAILED"
	USER_CANCELLED = "USER_CANCELLED"


class ErrorSeverity(Enum):
	LOW = "low"
	MEDIUM = "medium"
	HIGH = "high"
	CRITICAL = "critical"


@dataclass
class AppError(Exception):
	"""
	Standardized application error with structured metadata.
	
	Can be emitted as JSON string via existing pyqtSignal(str) for backward compatibility.
	"""
	code: ErrorCode = ErrorCode.UNKNOWN
	message: str = ""
	context: Dict[str, Any] = field(default_factory=dict)
	severity: ErrorSeverity = ErrorSeverity.MEDIUM
	recoverable: bool = True
	original_exception: Optional[str] = None
	traceback_str: Optional[str] = None

	def __post_init__(self):
		if self.message == "" and self.original_exception:
			self.message = str(self.original_exception)

	def __str__(self) -> str:
		"""User-friendly string representation."""
		parts = [f"[{self.code.value}] {self.message}"]
		if self.context:
			ctx_parts = [f"{k}={v}" for k, v in self.context.items()]
			parts.append(" (" + ", ".join(ctx_parts) + ")")
		return "".join(parts)

	def to_json(self) -> str:
		"""Serialize to JSON for structured logging/emission."""
		data = asdict(self)
		data["code"] = self.code.value
		data["severity"] = self.severity.value
		if self.original_exception and not isinstance(self.original_exception, str):
			data["original_exception"] = str(self.original_exception)
		return json.dumps(data, ensure_ascii=False)

	@classmethod
	def from_json(cls, json_str: str) -> "AppError":
		"""Deserialize from JSON string."""
		data = json.loads(json_str)
		data["code"] = ErrorCode(data.get("code", "UNKNOWN"))
		data["severity"] = ErrorSeverity(data.get("severity", "medium"))
		return cls(**data)

	@classmethod
	def from_exception(cls, exc: Exception, code: ErrorCode = ErrorCode.UNKNOWN,
					   context: Dict[str, Any] = None, severity: ErrorSeverity = None,
					   recoverable: bool = True) -> "AppError":
		"""Create AppError from a caught exception."""
		ctx = context or {}
		if severity is None:
			severity = ErrorSeverity.HIGH if isinstance(exc, (ConnectionError, OSError)) else ErrorSeverity.MEDIUM
		
		return cls(
			code=code,
			message=str(exc),
			context=ctx,
			severity=severity,
			recoverable=recoverable,
			original_exception=str(exc),
			traceback_str=traceback.format_exc()
		)

	@classmethod
	def wrap(cls, exc: Exception, code: ErrorCode = ErrorCode.UNKNOWN,
			 context: Dict[str, Any] = None, **kwargs) -> "AppError":
		"""Convenience method to wrap any exception."""
		return cls.from_exception(exc, code, context, **kwargs)


# Convenience factory functions
def db_error(message: str, context: Dict = None, exc: Exception = None) -> AppError:
	code = ErrorCode.DB_QUERY
	if exc:
		if "connection" in str(exc).lower():
			code = ErrorCode.DB_CONNECTION
		elif "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
			code = ErrorCode.DB_CONSTRAINT
	return AppError(code=code, message=message, context=context or {}, original_exception=str(exc) if exc else None,
					traceback_str=traceback.format_exc() if exc else None)


def file_error(message: str, filepath: str = None, exc: Exception = None) -> AppError:
	code = ErrorCode.FILE_NOT_FOUND
	if exc:
		if isinstance(exc, PermissionError):
			code = ErrorCode.FILE_PERMISSION
		elif "corrupt" in str(exc).lower() or "invalid" in str(exc).lower():
			code = ErrorCode.FILE_CORRUPT
	ctx = {}  # Fixed: was using undefined 'context'
	if filepath:
		ctx["filepath"] = filepath
	return AppError(code=code, message=message, context=ctx, original_exception=str(exc) if exc else None,
					traceback_str=traceback.format_exc() if exc else None)


def analysis_error(message: str, mode: str = None, filepath: str = None, exc: Exception = None) -> AppError:
	ctx = {}  # Fixed: was using undefined 'context'
	if mode:
		ctx["analysis_mode"] = mode
	if filepath:
		ctx["filepath"] = filepath
	return AppError(code=ErrorCode.ANALYSIS_FAILED, message=message, context=ctx,
					original_exception=str(exc) if exc else None,
					traceback_str=traceback.format_exc() if exc else None)


def external_tool_error(tool: str, message: str, filepath: str = None, exc: Exception = None) -> AppError:
	code = ErrorCode.EXTERNAL_TOOL_FAILED
	if exc and ("not found" in str(exc).lower() or "no such file" in str(exc).lower()):
		code = ErrorCode.EXTERNAL_TOOL_MISSING
	ctx = {"tool": tool}
	if filepath:
		ctx["filepath"] = filepath
	return AppError(code=code, message=message, context=ctx,
					original_exception=str(exc) if exc else None,
					traceback_str=traceback.format_exc() if exc else None)


def worker_error(message: str, worker_type: str = None, exc: Exception = None) -> AppError:
	ctx = {"worker_type": worker_type} if worker_type else {}
	return AppError(code=ErrorCode.WORKER_CRASHED, message=message, context=ctx,
					severity=ErrorSeverity.HIGH, recoverable=False,
					original_exception=str(exc) if exc else None,
					traceback_str=traceback.format_exc() if exc else None)


def config_error(message: str, config_file: str = None, exc: Exception = None) -> AppError:
	code = ErrorCode.CONFIG_MISSING
	if exc and ("invalid" in str(exc).lower() or "parse" in str(exc).lower()):
		code = ErrorCode.CONFIG_INVALID
	ctx = {"config_file": config_file} if config_file else {}
	return AppError(code=code, message=message, context=ctx,
					severity=ErrorSeverity.HIGH, recoverable=False,
					original_exception=str(exc) if exc else None,
					traceback_str=traceback.format_exc() if exc else None)
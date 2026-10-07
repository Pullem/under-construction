import os
import logging
from pathlib import Path
from dataclasses import dataclass
from configparser import ConfigParser

from .errors import AppError, ErrorCode, config_error

logger = logging.getLogger(__name__)


@dataclass
class GPUConfig:
    enabled: bool = True
    device_index: int = 0
    decode_hwaccel: str = "nvdec"
    encode_preview: str = "h264_nvenc"
    thumbnail_hwaccel: bool = True
    max_vram_mb: int = 6144
    chunk_size_mb: int = 256
    fallback_cpu: bool = True

    @property
    def device(self) -> str:
        return f"cuda:{self.device_index}"

    def validate(self) -> list[str]:
        errors = []
        if self.max_vram_mb < 512:
            errors.append("max_vram_mb must be at least 512")
        if self.chunk_size_mb < 64:
            errors.append("chunk_size_mb must be at least 64")
        if self.chunk_size_mb > self.max_vram_mb:
            errors.append("chunk_size_mb cannot exceed max_vram_mb")
        if self.device_index < 0:
            errors.append("device_index must be >= 0")
        valid_hwaccel = {"nvdec", "cuda", "auto", "none", ""}
        if self.decode_hwaccel not in valid_hwaccel:
            errors.append(f"decode_hwaccel must be one of {valid_hwaccel}")
        return errors


_gpu_config: GPUConfig | None = None


def load_gpu_config(config_path: Path | str | None = None) -> GPUConfig:
    global _gpu_config
    if _gpu_config is not None:
        return _gpu_config

    if config_path is None:
        base_dir = Path(__file__).parent.parent.parent
        config_path = base_dir / "config" / "gpu.ini"

    config_path = Path(config_path)
    parser = ConfigParser()

    defaults = {
        "enabled": "true",
        "device_index": "0",
        "decode_hwaccel": "nvdec",
        "encode_preview": "h264_nvenc",
        "thumbnail_hwaccel": "true",
        "max_vram_mb": "6144",
        "chunk_size_mb": "256",
        "fallback_cpu": "true",
    }

    if config_path.exists():
        parser.read(config_path, encoding="utf-8")
        if "gpu" in parser:
            for key, default in defaults.items():
                val = parser["gpu"].get(key, default)
                defaults[key] = val
        logger.info("Loaded GPU config from %s", config_path)
    else:
        logger.warning("GPU config not found at %s, using defaults", config_path)

    _gpu_config = GPUConfig(
        enabled=defaults["enabled"].lower() in ("true", "1", "yes"),
        device_index=int(defaults["device_index"]),
        decode_hwaccel=defaults["decode_hwaccel"],
        encode_preview=defaults["encode_preview"],
        thumbnail_hwaccel=defaults["thumbnail_hwaccel"].lower() in ("true", "1", "yes"),
        max_vram_mb=int(defaults["max_vram_mb"]),
        chunk_size_mb=int(defaults["chunk_size_mb"]),
        fallback_cpu=defaults["fallback_cpu"].lower() in ("true", "1", "yes"),
    )

    errors = _gpu_config.validate()
    if errors:
        err_msg = "; ".join(errors)
        logger.error("GPU config validation failed: %s", err_msg)
        raise config_error("GPU configuration invalid", details=err_msg)

    logger.info(
        "GPU config: enabled=%s, device=%s, hwaccel=%s, max_vram=%dMB, chunk=%dMB",
        _gpu_config.enabled, _gpu_config.device, _gpu_config.decode_hwaccel,
        _gpu_config.max_vram_mb, _gpu_config.chunk_size_mb
    )
    return _gpu_config


def get_gpu_config() -> GPUConfig:
    if _gpu_config is None:
        return load_gpu_config()
    return _gpu_config


def check_cuda_available() -> tuple[bool, str | None]:
    try:
        import torch
        if not torch.cuda.is_available():
            return False, "CUDA not available in PyTorch"
        device_count = torch.cuda.device_count()
        config = get_gpu_config()
        if config.device_index >= device_count:
            return False, f"Device index {config.device_index} >= available GPUs ({device_count})"
        gpu_name = torch.cuda.get_device_name(config.device_index)
        return True, gpu_name
    except ImportError:
        return False, "PyTorch not installed"
    except Exception as e:
        return False, f"CUDA check failed: {e}"
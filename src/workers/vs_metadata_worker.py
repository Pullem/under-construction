"""
Video Metadata Worker using VapourSynth/BestSource
Replaces FfprobeWorker for video metadata extraction
"""

import os
import logging
from pathlib import Path
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject

from src.utils.errors import AppError, ErrorCode, worker_error

logger = logging.getLogger(__name__)


class VSMetadataWorkerSignals(QObject):
    """Signals for VSMetadataWorker"""
    result = pyqtSignal(str, str, object)  # filepath, mode, metadata_dict
    error = pyqtSignal(str, str)           # filepath, error_json


class VSMetadataWorker(QRunnable):
    """
    Extract video metadata using VapourSynth with BestSource plugin.
    Supports modes: 'streams', 'quickcheck' (basic info), 'format' (container info)
    """

    def __init__(self, filepath, mode, vs_plugin_path=None):
        super().__init__()
        self.filepath = filepath
        self.mode = mode
        self.vs_plugin_path = vs_plugin_path or os.environ.get(
            'VAPOURSYNTH_PLUGIN_PATH',
            str(Path(__file__).parent.parent.parent / "vapoursynth_plugins" / "bestsource.dll")
        )
        self.signals = VSMetadataWorkerSignals()
        self._core = None

    def _init_vapoursynth(self):
        """Initialize VapourSynth core and load BestSource plugin"""
        if self._core is None:
            import vapoursynth as vs
            self._core = vs.core
            if not os.path.exists(self.vs_plugin_path):
                raise FileNotFoundError(f"BestSource plugin not found: {self.vs_plugin_path}")
            # Check if plugin is already loaded to avoid duplicate load error
            plugin_identifier = "com.vapoursynth.bestsource"
            already_loaded = False
            for plugin in self._core.plugins():
                if hasattr(plugin, 'identifier') and plugin.identifier == plugin_identifier:
                    already_loaded = True
                    break
            if not already_loaded:
                self._core.std.LoadPlugin(path=self.vs_plugin_path)

    def _get_basic_metadata(self, clip):
        """Extract basic video metadata from VapourSynth clip"""
        fps_num = clip.fps.numerator
        fps_den = clip.fps.denominator
        fps = fps_num / fps_den if fps_den > 0 else 0
        
        return {
            'width': clip.width,
            'height': clip.height,
            'fps': fps,
            'fps_num': fps_num,
            'fps_den': fps_den,
            'num_frames': clip.num_frames,
            'format': clip.format.name,
            'color_family': str(clip.format.color_family),
            'sample_type': str(clip.format.sample_type),
            'bits_per_sample': clip.format.bits_per_sample,
            'num_planes': clip.format.num_planes,
            'subsampling_w': clip.format.subsampling_w,
            'subsampling_h': clip.format.subsampling_h,
            'duration_seconds': clip.num_frames / fps if fps > 0 else 0,
        }

    def run(self):
        try:
            self._init_vapoursynth()
            clip = self._core.bs.VideoSource(source=self.filepath)

            if self.mode in ('streams', 'quickcheck', 'format'):
                metadata = self._get_basic_metadata(clip)
                
                # Add format-specific info
                if self.mode == 'format':
                    metadata['container'] = Path(self.filepath).suffix.lower()
                
                # For compatibility with existing ffprobe JSON structure
                if self.mode == 'streams':
                    metadata['streams'] = [{
                        'index': 0,
                        'codec_name': 'unknown',  # BestSource doesn't expose codec directly
                        'codec_type': 'video',
                        'width': clip.width,
                        'height': clip.height,
                        'r_frame_rate': f"{clip.fps.numerator}/{clip.fps.denominator}",
                        'avg_frame_rate': f"{clip.fps.numerator}/{clip.fps.denominator}",
                        'pix_fmt': clip.format.name.lower().replace('p8', 'p').replace('p10', 'p10le'),
                    }]
                    metadata['format'] = {
                        'filename': self.filepath,
                        'format_name': Path(self.filepath).suffix[1:].lower(),
                        'duration': metadata['duration_seconds'],
                        'size': os.path.getsize(self.filepath),
                        'bit_rate': int(os.path.getsize(self.filepath) * 8 / metadata['duration_seconds']) if metadata['duration_seconds'] > 0 else 0,
                    }
                
                self.signals.result.emit(self.filepath, self.mode, metadata)
            else:
                self.signals.error.emit(self.filepath, f"Unsupported mode: {self.mode}")

        except Exception as e:
            err = worker_error(
                f"VSMetadataWorker {self.mode} failed", 
                worker_type="VSMetadataWorker", 
                exc=e
            )
            # Add filepath to context
            if err.context is None:
                err.context = {}
            err.context["filepath"] = self.filepath
            self.signals.error.emit(self.filepath, err.to_json())
            logger.exception("VSMetadataWorker error for mode %s on %s", self.mode, self.filepath)
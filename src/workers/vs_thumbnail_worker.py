"""
VapourSynth Thumbnail Worker using BestSource
Replaces ThumbnailWorker for thumbnail extraction from videos
"""

import os
import logging
import hashlib
from pathlib import Path
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject

from src.utils.errors import AppError, ErrorCode, worker_error

logger = logging.getLogger(__name__)

# Import PIL for image processing
try:
    from PIL import Image
except ImportError:
    Image = None
    logger.warning("PIL not available, thumbnail generation will be limited")

# Import numpy for array operations
try:
    import numpy as np
except ImportError:
    np = None
    logger.warning("NumPy not available, thumbnail generation will be limited")


class VSThumbnailWorkerSignals(QObject):
    """Signals for VSThumbnailWorker"""
    progress = pyqtSignal(int, int)   # current, total
    chunk = pyqtSignal(object)        # media_files chunk
    result = pyqtSignal(object)       # media_files final
    error = pyqtSignal(str)           # error_json


class VSThumbnailWorker(QRunnable):
    """
    Extract thumbnails for media files using VapourSynth/BestSource.
    Processes videos and images in a background thread.
    """

    THUMBNAIL_WIDTH = 120
    MAX_THUMBS_PER_VIDEO = 30

    def __init__(self, model, media_files, thumb_dir, vs_plugin_path=None):
        super().__init__()
        self.model = model
        self.media_files = media_files
        self.thumb_dir = Path(thumb_dir)
        self.vs_plugin_path = vs_plugin_path or os.environ.get(
            'VAPOURSYNTH_PLUGIN_PATH',
            str(Path(__file__).parent.parent.parent / "vapoursynth_plugins" / "bestsource.dll")
        )
        self.signals = VSThumbnailWorkerSignals()
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

    def _frame_to_pil(self, frame):
        """Convert VapourSynth frame to PIL Image"""
        import numpy as np
        from PIL import Image

        fmt = frame.format
        
        if fmt.name == 'YUV420P8':
            # Y plane
            y = np.asarray(frame[0])
            # U plane (upscale 2x)
            u = np.asarray(frame[1])
            u = np.repeat(np.repeat(u, 2, axis=0), 2, axis=1)
            # V plane (upscale 2x)
            v = np.asarray(frame[2])
            v = np.repeat(np.repeat(v, 2, axis=0), 2, axis=1)

            # YUV to RGB (ITU-R BT.601)
            y = y.astype(np.float32)
            u = u.astype(np.float32) - 128
            v = v.astype(np.float32) - 128

            r = np.clip(y + 1.402 * v, 0, 255).astype(np.uint8)
            g = np.clip(y - 0.344136 * u - 0.714136 * v, 0, 255).astype(np.uint8)
            b = np.clip(y + 1.772 * u, 0, 255).astype(np.uint8)

            rgb = np.stack([r, g, b], axis=-1)
            return Image.fromarray(rgb, 'RGB')

        elif fmt.name == 'YUV422P8':
            y = np.asarray(frame[0])
            u = np.asarray(frame[1])
            u = np.repeat(u, 2, axis=1)
            v = np.asarray(frame[2])
            v = np.repeat(v, 2, axis=1)

            y = y.astype(np.float32)
            u = u.astype(np.float32) - 128
            v = v.astype(np.float32) - 128

            r = np.clip(y + 1.402 * v, 0, 255).astype(np.uint8)
            g = np.clip(y - 0.344136 * u - 0.714136 * v, 0, 255).astype(np.uint8)
            b = np.clip(y + 1.772 * u, 0, 255).astype(np.uint8)

            rgb = np.stack([r, g, b], axis=-1)
            return Image.fromarray(rgb, 'RGB')

        elif fmt.name == 'YUV444P8':
            y = np.asarray(frame[0])
            u = np.asarray(frame[1])
            v = np.asarray(frame[2])

            y = y.astype(np.float32)
            u = u.astype(np.float32) - 128
            v = v.astype(np.float32) - 128

            r = np.clip(y + 1.402 * v, 0, 255).astype(np.uint8)
            g = np.clip(y - 0.344136 * u - 0.714136 * v, 0, 255).astype(np.uint8)
            b = np.clip(y + 1.772 * u, 0, 255).astype(np.uint8)

            rgb = np.stack([r, g, b], axis=-1)
            return Image.fromarray(rgb, 'RGB')

        elif fmt.name == 'RGB24':
            r = np.asarray(frame[0])
            g = np.asarray(frame[1])
            b = np.asarray(frame[2])
            rgb = np.stack([r, g, b], axis=-1)
            return Image.fromarray(rgb, 'RGB')

        elif fmt.name == 'RGB48' or fmt.name == 'RGB48LE':
            # 16-bit per channel
            r = np.asarray(frame[0])
            g = np.asarray(frame[1])
            b = np.asarray(frame[2])
            # Convert to 8-bit
            r = (r >> 8).astype(np.uint8)
            g = (g >> 8).astype(np.uint8)
            b = (b >> 8).astype(np.uint8)
            rgb = np.stack([r, g, b], axis=-1)
            return Image.fromarray(rgb, 'RGB')

        elif fmt.name == 'GRAY8':
            y = np.asarray(frame[0])
            return Image.fromarray(y, 'L')

        elif fmt.name == 'GRAY16' or fmt.name == 'GRAY16LE':
            y = np.asarray(frame[0])
            y = (y >> 8).astype(np.uint8)
            return Image.fromarray(y, 'L')

        else:
            # Fallback: use Y plane if available, or first plane
            logger.warning(f"Unsupported format {fmt.name}, using first plane as grayscale")
            plane0 = np.asarray(frame[0])
            if plane0.dtype != np.uint8:
                plane0 = (plane0 / plane0.max() * 255).astype(np.uint8) if plane0.max() > 0 else plane0.astype(np.uint8)
            return Image.fromarray(plane0, 'L')

    def _extract_video_thumbnails(self, f, fpath):
        """Extract thumbnails from video using VapourSynth"""
        f_hash = hashlib.sha256(fpath.encode()).hexdigest()[:12]
        
        try:
            self._init_vapoursynth()
            clip = self._core.bs.VideoSource(source=fpath)
            
            num_frames = clip.num_frames
            fps = clip.fps.numerator / clip.fps.denominator if clip.fps.denominator > 0 else 25
            duration = num_frames / fps if fps > 0 else 0
            
            f["_duration_sec"] = duration
            
            if duration <= 0:
                f["_thumbnails"] = []
                return

            # Calculate interval and number of thumbnails
            if duration <= 60:
                interval = 2
            elif duration <= 300:
                interval = 10
            elif duration <= 3600:
                interval = 30
            else:
                interval = 60

            num_thumbs = max(1, int(duration / interval))
            if num_thumbs > self.MAX_THUMBS_PER_VIDEO:
                num_thumbs = self.MAX_THUMBS_PER_VIDEO
                interval = duration / num_thumbs
            
            time_points = [i * interval for i in range(num_thumbs)]
            thumbnails = []

            self.thumb_dir.mkdir(parents=True, exist_ok=True)

            for t in time_points:
                thumb_name = f"{f_hash}_t{int(t)}.jpg"
                thumb_path = self.thumb_dir / thumb_name
                
                if thumb_path.exists():
                    thumbnails.append({"time_sec": t, "path": str(thumb_path)})
                    continue

                frame_num = min(int(t * fps), num_frames - 1)
                try:
                    frame = clip.get_frame(frame_num)
                    img = self._frame_to_pil(frame)
                    
                    # Resize to thumbnail width maintaining aspect ratio
                    img.thumbnail((self.THUMBNAIL_WIDTH, self.THUMBNAIL_WIDTH), Image.Resampling.LANCZOS)
                    img.save(thumb_path, 'JPEG', quality=85)
                    
                    if thumb_path.exists():
                        thumbnails.append({"time_sec": t, "path": str(thumb_path)})
                        
                except Exception as e:
                    logger.warning(f"Frame extraction failed at {t}s: {e}")

            f["_thumbnails"] = thumbnails

        except Exception as e:
            logger.error(f"Video thumbnail extraction failed for {fpath}: {e}")
            f["_thumbnails"] = []
            f["_duration_sec"] = 0

    def _extract_photo_thumbnail(self, f, fpath):
        """Extract thumbnail from image using PIL/OpenCV"""
        f_hash = hashlib.sha256(fpath.encode()).hexdigest()[:12]
        
        try:
            # Try PIL first (faster for images)
            from PIL import Image
            img = Image.open(fpath)
            img.load()  # Force load to verify
            
            thumb_name = f"{f_hash}_thumb.jpg"
            thumb_path = self.thumb_dir / thumb_name
            self.thumb_dir.mkdir(parents=True, exist_ok=True)
            
            img.thumbnail((self.THUMBNAIL_WIDTH, self.THUMBNAIL_WIDTH), Image.Resampling.LANCZOS)
            img.save(thumb_path, 'JPEG', quality=85)
            
            if thumb_path.exists():
                f["_thumbnails"] = [{"time_sec": 0, "path": str(thumb_path)}]
            else:
                f["_thumbnails"] = []
                
        except Exception as e:
            logger.warning(f"PIL thumbnail failed for {fpath}: {e}")
            # Fallback to OpenCV
            try:
                import cv2
                cap = cv2.VideoCapture(str(fpath))
                success, frame = cap.read()
                cap.release()
                if success and frame is not None:
                    thumb_name = f"{f_hash}_thumb.jpg"
                    thumb_path = self.thumb_dir / thumb_name
                    self.thumb_dir.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(str(thumb_path), frame)
                    if thumb_path.exists():
                        f["_thumbnails"] = [{"time_sec": 0, "path": str(thumb_path)}]
                    else:
                        f["_thumbnails"] = []
                else:
                    f["_thumbnails"] = []
            except Exception as e2:
                logger.warning(f"OpenCV thumbnail failed for {fpath}: {e2}")
                f["_thumbnails"] = []
        
        f["_duration_sec"] = 0

    def _process_file(self, f):
        """Process a single media file for thumbnails"""
        fname = f.get("file_name", "")
        fpath = f.get("file_path", "")
        
        if not fpath or not os.path.exists(fpath):
            f["_thumbnails"] = []
            f["_duration_sec"] = 0
            return

        fname_lower = fname.lower()
        video_exts = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".mts", ".m2ts", ".ts", ".flv", ".wmv")
        image_exts = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif")

        if fname_lower.endswith(video_exts):
            self._extract_video_thumbnails(f, fpath)
        elif fname_lower.endswith(image_exts):
            self._extract_photo_thumbnail(f, fpath)
        else:
            f["_thumbnails"] = []
            f["_duration_sec"] = 0

    def run(self):
        try:
            total = len(self.media_files)
            chunk_size = 50
            
            for idx, f in enumerate(self.media_files):
                self._process_file(f)
                self.signals.progress.emit(idx + 1, total)
                
                if (idx + 1) % chunk_size == 0:
                    self.signals.chunk.emit(self.media_files)
            
            self.signals.result.emit(self.media_files)

        except Exception as e:
            err = worker_error("VSThumbnailWorker failed", worker_type="VSThumbnailWorker", exc=e)
            self.signals.error.emit(err.to_json())
            logger.exception("VSThumbnailWorker error")
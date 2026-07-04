from .base import PresenterBase
from .file_ops import FileOpsMixin
from .scan import ScanMixin
from .comparison import ComparisonMixin
from .import_media import ImportMediaMixin
from .ffmpeg_ops import FfmpegOpsMixin


class ForensicPresenter(PresenterBase, FileOpsMixin, ScanMixin, ComparisonMixin, ImportMediaMixin, FfmpegOpsMixin):
	pass

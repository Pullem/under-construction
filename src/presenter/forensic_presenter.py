from .base import PresenterBase
from .file_ops import FileOpsMixin
from .scan import ScanMixin
from .comparison import ComparisonMixin
from .import_media import ImportMediaMixin


class ForensicPresenter(PresenterBase, FileOpsMixin, ScanMixin, ComparisonMixin, ImportMediaMixin):
	pass

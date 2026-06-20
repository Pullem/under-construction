from .base import ConfigDBMixin
from .case import CaseMixin
from .media import MediaMixin
from .chain_of_custody import ChainOfCustodyMixin


class ForensicModel(ConfigDBMixin, CaseMixin, MediaMixin, ChainOfCustodyMixin):
	pass

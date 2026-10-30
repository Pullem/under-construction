"""Tab-Builder: Exporte aller build_*_tab Funktionen."""

from .case_tab import build_case_tab
from .import_tab import build_import_tab
from .metadata_tab import build_metadata_tab
from .media_tab import (build_media_tab, build_videos_tab, build_bilder_tab,
						active_media_prefix)
from .settings_tab import build_settings_tab
from .hex_tab import build_hex_tab
from .analysis_tab import build_analysis_tab, build_placeholder_tab
from .widgets import AspectFitLabel, AnalysisTabWidget

__all__ = [
	"build_case_tab",
	"build_import_tab",
	"build_metadata_tab",
	"build_media_tab",
	"build_videos_tab",
	"build_bilder_tab",
	"active_media_prefix",
	"build_settings_tab",
	"build_hex_tab",
	"build_analysis_tab",
	"build_placeholder_tab",
	"AspectFitLabel",
	"AnalysisTabWidget",
]


def build_all_tabs(view):
	"""Baut alle Tabs in der korrekten Reihenfolge auf."""
	build_case_tab(view)
	build_import_tab(view)
	build_metadata_tab(view)
	build_videos_tab(view)
	build_bilder_tab(view)
	build_settings_tab(view)
	build_hex_tab(view)
	build_analysis_tab(view)
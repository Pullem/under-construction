import logging
from PyQt6.QtWidgets import QDialog

from ..import_dialog import ImportMediaDialog


logger = logging.getLogger(__name__)


class ImportMediaMixin:
	def open_import_dialog(self):
		if not self.model.current_case_id or not self.model.current_case_path:
			logger.warning("No case selected – import not possible.")
			return

		dlg = ImportMediaDialog(self.model, parent=self.view)
		result = dlg.exec()

		if result == QDialog.DialogCode.Accepted:
			logger.info("Import completed – refreshing file list")
			self.refresh_ui_list()
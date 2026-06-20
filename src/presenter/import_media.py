from PyQt6.QtWidgets import QDialog

from ..import_dialog import ImportMediaDialog


class ImportMediaMixin:
	def open_import_dialog(self):
		if not self.model.current_case_id or not self.model.current_case_path:
			print("Kein Fall ausgewählt – Import nicht möglich.")
			return

		dlg = ImportMediaDialog(self.model, parent=self.view)
		result = dlg.exec()

		if result == QDialog.DialogCode.Accepted:
			print("Import abgeschlossen – aktualisiere Dateiliste…")
			self.refresh_ui_list()

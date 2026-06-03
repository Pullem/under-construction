import os
import shutil
from ..views.dialogs.importer_view import ImportDialog

class ImportManager:
	def __init__(self, model, view):
		self.model = model
		self.view = view

	def execute_import_dialog(self):
		if not self.model.case.current_case_folder:
			return False

		dialog = ImportDialog(self.model.case.current_case_folder, self.view)
		if dialog.exec():
			files, target = dialog.get_data()
			return self.perform_copy(files, target)
		return False

	def perform_copy(self, files, target):
		count = 0
		for f in files:
			try:
				dest = os.path.join(target, os.path.basename(f))
				shutil.copy2(f, dest)
				count += 1
			except Exception as e:
				print(f"Fehler: {e}")
		return count > 0
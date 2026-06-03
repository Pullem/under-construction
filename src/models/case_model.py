import os

class CaseModel:
	def __init__(self):
		self.current_case_folder = None
		self.case_name = "Kein Fall geladen"
		self.files = [] # Liste von FileEntity-Objekten

	def load_case(self, folder_path):
		if os.path.exists(folder_path):
			self.current_case_folder = folder_path
			self.case_name = os.path.basename(folder_path)
			return True
		return False

	def clear(self):
		self.current_case_folder = None
		self.case_name = "Kein Fall geladen"
		self.files = []
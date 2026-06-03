import os
import datetime

class FileEntity:
	def __init__(self, full_path):
		self.full_path = full_path
		self.file_name = os.path.basename(full_path)
		self.extension = os.path.splitext(self.file_name)[1].lower()
		self.size_bytes = os.path.getsize(full_path)
		self.created_at = datetime.datetime.fromtimestamp(os.path.getctime(full_path))
		
		# Forensische Daten (werden später durch Analyzer gefüllt)
		self.hash_sha256 = None
		self.metadata = {}
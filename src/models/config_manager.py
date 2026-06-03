import json
import os

class ConfigManager:
	def __init__(self, config_path="config.json"):
		self.config_path = config_path
		self.config = self.load_config()

	def load_config(self):
		if os.path.exists(self.config_path):
			try:
				with open(self.config_path, 'r', encoding='utf-8') as f:
					return json.load(f)
			except Exception as e:
				print(f"Fehler beim Laden der Config: {e}")
		return {"case_root": os.path.expanduser("~")}

	def save_config(self):
		try:
			with open(self.config_path, 'w', encoding='utf-8') as f:
				json.dump(self.config, f, indent=4)
		except Exception as e:
			print(f"Fehler beim Speichern der Config: {e}")

	def get(self, key, default=None):
		return self.config.get(key, default)

	def set(self, key, value):
		self.config[key] = value
		self.save_config()
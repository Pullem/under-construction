import os
from .config_manager import ConfigManager
from .case_model import CaseModel

class ForensicModel:
	"""
	Das Haupt-Model der Anwendung.
	Es orchestriert die verschiedenen Daten-Subsysteme.
	"""
	def __init__(self):
		# 1. Globale Konfiguration laden (Pfade, Einstellungen)
		self.config_manager = ConfigManager()
		
		# 2. Aktuellen Fall/Projektstatus initialisieren
		self.case = CaseModel()

	# --- Delegations-Methoden (Brücken zum CaseModel) ---

	def set_project_by_path(self, folder_path):
		"""
		Wird von main.py oder dem Presenter aufgerufen.
		Gibt den Befehl zum Laden eines Falls an das CaseModel weiter.
		"""
		if not folder_path:
			return False
		return self.case.load_case(folder_path)

	# --- Properties für bequemen Zugriff ---
	# Diese erlauben es dem Presenter, weiterhin 'model.current_case_folder' 
	# statt 'model.case.current_case_folder' zu schreiben.

	@property
	def current_case_folder(self):
		"""Gibt den Pfad des aktuell geladenen Falls zurück."""
		return self.case.current_case_folder

	@property
	def case_name(self):
		"""Gibt den Namen des Falls zurück."""
		return self.case.case_name

	@property
	def files(self):
		"""Gibt die Liste der geladenen Datei-Objekte zurück."""
		return self.case.files

	# --- Hilfsmethoden ---

	def reset_current_case(self):
		"""Setzt den aktuellen Fall zurück (z.B. beim Schließen)."""
		self.case.clear()
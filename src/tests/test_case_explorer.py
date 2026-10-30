"""
Tests für die Tabellenansicht des Fallexplorers (AGENTS.md Abschnitt 12).

Reproduzierbare Testdaten: feste Fälle mit bekannten Tatzeiten.
"""

import os
import unittest
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.view.main_window import MainWindowMixin


def _cases():
	return [
		{"id": 1, "project_name": "Alpha",
		 "description": "Erster Testfall mit Foto",
		 "created_at": datetime(2026, 1, 5, 10, 0),
		 "incident_at": datetime(2025, 12, 24), "incident_until": None},
		{"id": 2, "project_name": "Beta",
		 "description": "Videoaufzeichnung Auswertung",
		 "created_at": datetime(2026, 2, 1, 9, 0),
		 "incident_at": datetime(2026, 1, 15), "incident_until": None},
	]


class CaseExplorerTableTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.app = QApplication.instance() or QApplication([])

	def setUp(self):
		self.view = MainWindowMixin()
		self.view.setup_ui()
		self.table = self.view.case_list

	def test_table_has_columns(self):
		"""Vier Spalten: Tatzeit, Fallname, Beschreibung, Erstelldatum."""
		self.assertEqual(self.table.columnCount(), 4)
		labels = [self.table.horizontalHeaderItem(i).text()
				  for i in range(self.table.columnCount())]
		self.assertEqual(labels, ["Tatzeit", "Fallname", "Beschreibung", "Erstelldatum"])

	def test_sorted_by_incident_date_newest_first(self):
		"""Grundsätzliche Sortierung: nach Tatzeit, neueste zuerst."""
		self.view.update_case_list(_cases())
		self.assertEqual(self.table.rowCount(), 2)
		self.assertEqual(self.table.item(0, 1).text(), "Beta")
		self.assertEqual(self.table.item(1, 1).text(), "Alpha")

	def test_incident_range_displayed(self):
		"""Tatzeit mit Bis-Datum zeigt Zeitraum."""
		cases = _cases()
		cases[0]["incident_until"] = datetime(2025, 12, 26)
		self.view.update_case_list(cases)
		texts = [self.table.item(r, 0).text() for r in range(self.table.rowCount())]
		self.assertIn("24.12.2025 – 26.12.2025", texts)

	def test_created_at_formatted(self):
		"""Erstelldatum im Format dd.MM.yyyy HH:MM."""
		self.view.update_case_list(_cases())
		texts = [self.table.item(r, 3).text() for r in range(self.table.rowCount())]
		self.assertIn("05.01.2026 10:00", texts)

	def test_filter_by_description(self):
		"""Beschreibungs-Suchfeld filtert die Zeilen."""
		self.view.update_case_list(_cases())
		self.view.apply_case_filter("videoaufzeichnung")
		# Nach Sortierung ist Zeile 0 = Beta (Treffer), Zeile 1 = Alpha (verborgen)
		hidden = [self.table.isRowHidden(r) for r in range(self.table.rowCount())]
		self.assertEqual(hidden, [False, True])
		self.view.apply_case_filter("")
		self.assertEqual(
			[self.table.isRowHidden(r) for r in range(self.table.rowCount())],
			[False, False])

	def test_case_selection_emits_case_id(self):
		"""Doppelklick/Auswahl meldet die Fall-ID aus der Fallname-Spalte."""
		self.view.update_case_list(_cases())
		self.table.setCurrentCell(0, 0)
		emitted = []
		self.view.case_selected.connect(emitted.append)
		self.view._on_case_selected()
		self.assertEqual(emitted, [2])


if __name__ == "__main__":
	unittest.main()

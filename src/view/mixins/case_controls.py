"""Fallverwaltung: Neuanlage, Auswahl, Fallexplorer-Liste."""

from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QDateTime, Qt

from ..sortable_table_item import _SortableTableWidgetItem
class CaseControlsMixin:
	"""Fallübersicht: Anwählen, Anlegen, Fallexplorer-Liste."""

	def _on_bis_toggled(self, checked):
		self.d_incident_until.setVisible(checked)
		self.t_incident_until.setVisible(checked)

	def _on_create_case(self):
		name = self.txt_case_name.text().strip()
		desc = self.txt_case_desc.toPlainText().strip()
		if not name:
			QMessageBox.warning(self, "Fehler", "Fallname darf nicht leer sein.")
			return
		incident_at = QDateTime(self.d_incident.date(), self.t_incident.time()).toPyDateTime()
		incident_until = QDateTime(self.d_incident_until.date(), self.t_incident_until.time()).toPyDateTime() if self.chk_bis.isChecked() else None
		if incident_until and incident_until < incident_at:
			QMessageBox.warning(self, "Fehler", "„Bis“-Tatzeit liegt vor der „Von“-Tatzeit.")
			return
		self.create_case_requested.emit(name, desc, incident_at, incident_until)

	def _on_case_selected(self):
		item = self.case_list.currentItem()
		if not item:
			return
		case_item = self.case_list.item(item.row(), 1)
		if not case_item:
			return
		self.case_selected.emit(case_item.data(Qt.ItemDataRole.UserRole))

	def set_case_name(self, name):
		self.lbl_case_name.setText(f"Aktueller Fall: {name}")

	def set_case_path(self, path):
		self._case_path = path

	def update_case_list(self, cases):
		table = self.case_list
		table.setSortingEnabled(False)
		table.setRowCount(0)
		table.setRowCount(len(cases))

		for row, c in enumerate(cases):
			created = c.get('created_at')
			incident = c.get('incident_at')
			incident_until = c.get('incident_until')

			if hasattr(created, "strftime"):
				created_text = created.strftime("%d.%m.%Y %H:%M")
				created_key = created.isoformat()
			else:
				created_text = str(created) if created else "–"
				created_key = str(created or "")

			if incident:
				incident_text = (incident.strftime("%d.%m.%Y")
								 if hasattr(incident, "strftime") else str(incident))
				if incident_until and incident_until != incident:
					incident_text += " – " + (
						incident_until.strftime("%d.%m.%Y")
						if hasattr(incident_until, "strftime") else str(incident_until))
				incident_key = (incident.isoformat()
								if hasattr(incident, "isoformat") else str(incident))
			else:
				incident_text = "–"
				incident_key = ""

			name_item = _SortableTableWidgetItem(c.get('project_name', ""))
			name_item.setData(_SortableTableWidgetItem.SORT_ROLE, c.get('project_name', ""))
			name_item.setData(Qt.ItemDataRole.UserRole, c.get('id'))

			desc_item = _SortableTableWidgetItem(c.get('description') or "")
			desc_item.setData(_SortableTableWidgetItem.SORT_ROLE, c.get('description') or "")

			created_item = _SortableTableWidgetItem(created_text)
			created_item.setData(_SortableTableWidgetItem.SORT_ROLE, created_key)

			incident_item = _SortableTableWidgetItem(incident_text)
			incident_item.setData(_SortableTableWidgetItem.SORT_ROLE, incident_key)

			table.setItem(row, 0, incident_item)
			table.setItem(row, 1, name_item)
			table.setItem(row, 2, desc_item)
			table.setItem(row, 3, created_item)

		# Grundsätzlich nach Tatzeit sortiert (neueste zuerst)
		table.setSortingEnabled(True)
		table.sortItems(0, Qt.SortOrder.DescendingOrder)

	def apply_case_filter(self, query):
		"""Fallexplorer-Zeilen nach Beschreibung filtern (Spalte 2)."""
		q = query.lower()
		for row in range(self.case_list.rowCount()):
			item = self.case_list.item(row, 2)
			text = item.text().lower() if item else ""
			self.case_list.setRowHidden(row, q not in text)

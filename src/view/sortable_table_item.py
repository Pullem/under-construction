"""Sortierbare Tabellenzelle mit chronologischem Sortierschlüssel."""

from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtCore import Qt


class _SortableTableWidgetItem(QTableWidgetItem):
	"""Sortiert über UserRole+1 – enthält für Datumsspalten ISO-Strings,
	damit chronologisch statt alphabetisch sortiert wird (Qt6 hat
	setSortRole entfernt; EditRole ist gleich DisplayRole und für
	den Sortierschlüssel daher ungeeignet)."""

	SORT_ROLE = Qt.ItemDataRole.UserRole + 1

	def __lt__(self, other):
		a = self.data(_SortableTableWidgetItem.SORT_ROLE)
		b = other.data(_SortableTableWidgetItem.SORT_ROLE) if isinstance(other, QTableWidgetItem) else None
		return str(a if a is not None else "") < str(b if b is not None else "")

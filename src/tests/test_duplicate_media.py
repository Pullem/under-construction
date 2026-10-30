"""
Tests für DuplicateMediaError in save_to_db (AGENTS.md Abschnitt 12).

Ein erneuter Import derselben Datei (gleicher SHA256) ist ein erwarteter
Zustand der Deduplizierung und wirft eine eigene, von technischen Fehlern
unterscheidbare Exception.
"""

import os
import tempfile
import unittest

from src.model.media import DuplicateMediaError, MediaMixin


class _FakeCursor:
	def __init__(self, duplicate):
		self._duplicate = duplicate
		self.executed = []

	def execute(self, query, params=None):
		self.executed.append(query)

	def fetchone(self):
		return (1,) if self._duplicate else None


class _FakeConnection:
	def __init__(self, duplicate):
		self._cursor = _FakeCursor(duplicate)

	def cursor(self, dictionary=False):
		return self._cursor

	def commit(self):
		pass

	def close(self):
		pass


class _StubModel(MediaMixin):
	def __init__(self, duplicate):
		super().__init__()
		self.current_case_id = 1
		self._conn = _FakeConnection(duplicate)

	def get_connection(self):
		return self._conn


class SaveToDbDuplicateTest(unittest.TestCase):
	def setUp(self):
		tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
		tmp.write(b"fake image bytes")
		tmp.close()
		self.path = tmp.name
		self.addCleanup(os.unlink, self.path)

	def test_duplicate_raises_duplicate_media_error(self):
		"""Vorhandener SHA256 -> DuplicateMediaError statt generellem Exception."""
		model = _StubModel(duplicate=True)
		with self.assertRaises(DuplicateMediaError) as ctx:
			model.save_to_db(self.path, "test.jpg", "hash123", {"General": {}}, {})
		self.assertIn("SHA256", str(ctx.exception))

	def test_no_duplicate_succeeds(self):
		"""Neuer Hash läuft ohne Duplikat-Ausnahme durch."""
		model = _StubModel(duplicate=False)
		model.save_to_db(self.path, "test.jpg", "hash123", {"General": {}}, {})
		# INSERT wurde ausgeführt
		queries = model._conn._cursor.executed
		self.assertTrue(any("INSERT INTO media_files" in q for q in queries))


if __name__ == "__main__":
	unittest.main()

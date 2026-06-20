class ChainOfCustodyMixin:
	def create_supplier(self, name, contact=None, role=None, notes=None):
		conn = self.get_connection()
		if not conn:
			raise Exception("Keine DB-Verbindung")

		try:
			cur = conn.cursor()
			cur.execute(
				"""
				INSERT INTO suppliers (name, contact, role, notes)
				VALUES (?, ?, ?, ?)
				""",
				(name, contact, role, notes)
			)
			conn.commit()
			return cur.lastrowid
		finally:
			conn.close()

	def find_supplier_by_name(self, name):
		conn = self.get_connection()
		if not conn:
			return None

		try:
			cur = conn.cursor(dictionary=True)
			cur.execute(
				"SELECT * FROM suppliers WHERE name = ?",
				(name,)
			)
			row = cur.fetchone()
			return row
		finally:
			conn.close()

	def create_delivery(self, supplier_id, case_id, delivered_at, description=None):
		conn = self.get_connection()
		if not conn:
			raise Exception("Keine DB-Verbindung")

		try:
			cur = conn.cursor()
			cur.execute(
				"""
				INSERT INTO deliveries (supplier_id, case_id, delivered_at, description)
				VALUES (?, ?, ?, ?)
				""",
				(supplier_id, case_id, delivered_at, description)
			)
			conn.commit()
			return cur.lastrowid
		finally:
			conn.close()

	def link_media_to_delivery(self, media_id, delivery_id):
		conn = self.get_connection()
		if not conn:
			return

		try:
			cur = conn.cursor()
			cur.execute(
				"""
				INSERT INTO media_deliveries (delivery_id, media_id)
				VALUES (?, ?)
				""",
				(delivery_id, media_id)
			)
			conn.commit()
		finally:
			conn.close()

	def get_last_delivery_for_supplier(self, supplier_id, case_id):
		conn = self.get_connection()
		if not conn:
			return None

		try:
			cur = conn.cursor(dictionary=True)
			cur.execute(
				"""
				SELECT *
				FROM deliveries
				WHERE supplier_id = ? AND case_id = ?
				ORDER BY delivered_at DESC, id DESC
				LIMIT 1
				""",
				(supplier_id, case_id)
			)
			row = cur.fetchone()
			return row
		finally:
			conn.close()

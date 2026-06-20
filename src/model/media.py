import os
import json
import hashlib
import cv2
from pathlib import Path


class MediaMixin:
	def calculate_hash(self, filepath):
		sha256 = hashlib.sha256()
		with open(filepath, "rb") as f:
			for chunk in iter(lambda: f.read(8192), b""):
				sha256.update(chunk)
		return sha256.hexdigest()

	def get_thumbnail(self, filepath):
		if not self.current_case_path:
			thumb_dir = Path(filepath).parent
		else:
			thumb_dir = Path(self.current_case_path) / "thumbnails"

		thumb_dir.mkdir(parents=True, exist_ok=True)

		cap = cv2.VideoCapture(str(filepath))
		success, frame = cap.read()
		cap.release()

		if not success or frame is None:
			thumb_path = thumb_dir / (Path(filepath).stem + "_thumb.jpg")
			return str(thumb_path)

		thumb_path = thumb_dir / (Path(filepath).stem + "_thumb.jpg")
		cv2.imwrite(str(thumb_path), frame)
		return str(thumb_path)

	def save_to_db(self, path, name, f_hash, mi_dict, exif_dict):
		if not self.current_case_id:
			raise Exception("Kein Fall ausgewählt.")

		conn = self.get_connection()
		if not conn:
			print("[DB] Keine Verbindung in save_to_db()")
			return

		try:
			cur = conn.cursor()
			cur.execute(
				"""
				INSERT INTO media_files
					(case_id, file_path, file_name, file_size, sha256_hash, metadata, exif_metadata)
				VALUES (?, ?, ?, ?, ?, ?, ?)
				ON DUPLICATE KEY UPDATE
					file_name = VALUES(file_name),
					metadata = VALUES(metadata),
					exif_metadata = VALUES(exif_metadata)
				""",
				(
					self.current_case_id,
					path,
					name,
					os.path.getsize(path),
					f_hash,
					json.dumps(mi_dict, ensure_ascii=False),
					json.dumps(exif_dict, ensure_ascii=False)
				)
			)
			conn.commit()
		finally:
			conn.close()

	def search_db(self, query):
		if not self.current_case_id:
			return []

		conn = self.get_connection()
		if not conn:
			return []

		try:
			cur = conn.cursor(dictionary=True)
			like = f"%{query}%"
			cur.execute(
				"""
				SELECT * FROM media_files
				WHERE case_id = ?
				  AND (
					file_name LIKE ?
					OR JSON_SEARCH(metadata, 'one', ?) IS NOT NULL
					OR JSON_SEARCH(exif_metadata, 'one', ?) IS NOT NULL
				  )
				ORDER BY id DESC
				""",
				(self.current_case_id, like, like, like)
			)
			rows = cur.fetchall()
			return rows
		finally:
			conn.close()

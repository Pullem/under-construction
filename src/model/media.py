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
			cur = conn.cursor(dictionary=True)
			size = os.path.getsize(path)
			md_json = json.dumps(mi_dict, ensure_ascii=False)
			exif_json = json.dumps(exif_dict, ensure_ascii=False)

			# Prüfen ob Hash bereits im selben Fall existiert
			cur.execute(
				"SELECT id FROM media_files WHERE sha256_hash = ? AND case_id = ?",
				(f_hash, self.current_case_id)
			)
			if cur.fetchone():
				raise Exception(
					"Datei wurde bereits in diesen Fall importiert (gleicher SHA256-Hash)."
				)

			insert = (
				"INSERT INTO media_files "
				"(case_id, file_path, file_name, file_size, sha256_hash, metadata, exif_metadata) "
				"VALUES (?, ?, ?, ?, ?, ?, ?)"
			)
			try:
				cur.execute(insert, (self.current_case_id, path, name, size, f_hash, md_json, exif_json))
			except Exception as e:
				if "Duplicate" in str(e) or "UNIQUE" in str(e):
					# Migration: UNIQUE-Constraint durch normale Indizes ersetzen
					cur.execute("ALTER TABLE media_files DROP INDEX sha256_hash")
					# Index-Setup für bestehende DB nachziehen
					cur.execute("ALTER TABLE media_files ADD INDEX idx_sha256_hash (sha256_hash)")
					cur.execute("ALTER TABLE media_files ADD INDEX idx_case_hash (case_id, sha256_hash)")
					conn.commit()
					cur.execute(insert, (self.current_case_id, path, name, size, f_hash, md_json, exif_json))
				else:
					raise
			conn.commit()
		finally:
			conn.close()

	def extract_thumbnails(self, filepath, interval_sec, thumb_dir):
		thumb_dir = Path(thumb_dir)
		thumb_dir.mkdir(parents=True, exist_ok=True)
		f_hash = self.calculate_hash(filepath)[:12]

		cap = cv2.VideoCapture(str(filepath))
		if not cap.isOpened():
			return []

		fps = cap.get(cv2.CAP_PROP_FPS)
		total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
		duration = total_frames / fps if fps > 0 else 0
		if duration <= 0 or fps <= 0:
			cap.release()
			return []

		frame_interval = max(1, int(interval_sec * fps))
		results = []
		time_sec = 0.0
		frame_idx = 0

		while True:
			ret, frame = cap.read()
			if not ret:
				break
			if frame_idx % frame_interval == 0:
				thumb_name = f"{f_hash}_t{int(time_sec)}.jpg"
				thumb_path = thumb_dir / thumb_name
				if not thumb_path.exists():
					h, w = frame.shape[:2]
					scale = min(120.0 / w, 80.0 / h)
					nw, nh = int(w * scale), int(h * scale)
					small = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
					cv2.imwrite(str(thumb_path), small, [cv2.IMWRITE_JPEG_QUALITY, 75])
				results.append({"time_sec": time_sec, "path": str(thumb_path)})
			time_sec += 1.0 / fps
			frame_idx += 1

		cap.release()
		return results

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

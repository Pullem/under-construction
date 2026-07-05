import os
import json
import hashlib
import subprocess
from pathlib import Path

from .base import BASE_DIR

# OpenCV stumm schalten (keine "Failed to initialize" Ausgaben)
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
import cv2
try:
	cv2.setLogLevel(0)
except AttributeError:
	pass


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
		thumb_path = thumb_dir / (Path(filepath).stem + "_thumb.jpg")

		# FFmpeg bevorzugen (zuverlässiger bei H.264 etc.)
		ffmpeg = str(BASE_DIR / "ffmpeg.exe")
		if os.path.exists(ffmpeg):
			try:
				subprocess.run(
					[ffmpeg, "-ss", "0", "-i", str(filepath),
					 "-vframes", "1", "-q:v", "2",
					 "-y", str(thumb_path)],
					capture_output=True, text=True, timeout=30
				)
				if thumb_path.exists() and thumb_path.stat().st_size > 0:
					return str(thumb_path)
			except Exception:
				pass

		# Fallback: OpenCV
		import contextlib
		with contextlib.redirect_stderr(open(os.devnull, 'w')):
			try:
				cap = cv2.VideoCapture(str(filepath))
				success, frame = cap.read()
				cap.release()
				if success and frame is not None:
					cv2.imwrite(str(thumb_path), frame)
			except Exception:
				pass

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
		results = []

		ffmpeg = str(BASE_DIR / "ffmpeg.exe")
		if not os.path.exists(ffmpeg):
			print(f"[extract_thumbnails] ffmpeg nicht gefunden: {ffmpeg}")
			return []

		# Dauer via ffprobe ermitteln
		duration = 0
		try:
			r = subprocess.run(
				[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
				 "-show_entries", "format=duration",
				 "-of", "csv=p=0", str(filepath)],
				capture_output=True, text=True, timeout=15
			)
			out = r.stdout.strip()
			if out:
				duration = float(out)
		except Exception as e:
			print(f"[extract_thumbnails] ffprobe Fehler: {e}")

		if duration <= 0:
			# Fallback: cv2 versuchen (stumm)
			import contextlib
			with contextlib.redirect_stderr(open(os.devnull, 'w')):
				try:
					cap = cv2.VideoCapture(str(filepath))
					if cap.isOpened():
						fps = cap.get(cv2.CAP_PROP_FPS)
						total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
						duration = total / fps if fps > 0 else 0
						cap.release()
				except Exception:
					pass
			if duration <= 0:
				return []

		num_thumbs = max(1, int(duration / interval_sec))
		# Extraktions-Zeitpunkte
		time_points = [i * interval_sec for i in range(num_thumbs)]

		for t in time_points:
			thumb_name = f"{f_hash}_t{int(t)}.jpg"
			thumb_path = thumb_dir / thumb_name
			if thumb_path.exists():
				results.append({"time_sec": t, "path": str(thumb_path)})
				continue
			try:
				subprocess.run(
					[ffmpeg, "-ss", str(t), "-i", str(filepath),
					 "-vframes", "1", "-q:v", "2",
					 "-vf", "scale=120:-2",
					 "-y", str(thumb_path)],
					capture_output=True, text=True, timeout=30
				)
				if thumb_path.exists():
					results.append({"time_sec": t, "path": str(thumb_path)})
			except Exception as e:
				print(f"[extract_thumbnails] Frame {t}s Fehler: {e}")

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

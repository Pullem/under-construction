import os
import json
import subprocess

class ForensicPresenter:
	def __init__(self, model, view):
		self.model = model
		self.view = view
		self.view.start_requested.connect(self.handle_scan)
		self.view.config_requested.connect(self.open_config)
		self.view.search_changed.connect(self.handle_search)
		self.view.file_selected.connect(self.load_file_details)
		self.refresh_ui_list()

	def handle_scan(self):
		folder = self.model.proj_config.get('watchfolder', './evidence_input')
		if not os.path.exists(folder): return
		ext = ('.mp4', '.mkv', '.mov', '.avi', '.jpg', '.jpeg', '.png')
		for f in os.listdir(folder):
			if f.lower().endswith(ext):
				self.model.process_file(os.path.join(folder, f))
		self.refresh_ui_list()

	def refresh_ui_list(self):
		try:
			conn = self.model.get_connection()
			cur = conn.cursor()
			cur.execute("SELECT file_name FROM media_files ORDER BY created_at DESC")
			files = [r[0] for r in cur.fetchall()]
			conn.close()
			self.view.update_file_list(files)
		except: pass

	def load_file_details(self, file_name):
		if not file_name: return
		try:
			conn = self.model.get_connection()
			cur = conn.cursor(dictionary=True)
			cur.execute("SELECT metadata, file_path FROM media_files WHERE file_name = ?", (file_name,))
			row = cur.fetchone()
			conn.close()

			if row:
				# 1. Metadaten anzeigen
				self.view.display_metadata(json.loads(row['metadata']))
				# 2. Thumbnail generieren und anzeigen
				t_path = self.model.get_thumbnail(row['file_path'])
				self.view.set_thumbnail(t_path)
		except Exception as e:
			print(f"Error: {e}")

	def handle_search(self, q):
		self.view.apply_row_filter(q)
		if len(q) >= 2:
			res = self.model.search_db(q)
			self.view.update_file_list(list(set([r['file_name'] for r in res])))
		else:
			self.refresh_ui_list()

	def open_config(self):
		path = os.path.abspath('config')
		if os.name == 'nt': os.startfile(path)
		else: subprocess.run(['xdg-open', path])
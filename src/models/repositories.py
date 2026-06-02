from datetime import datetime
from .db import DB

class MediaRepository:
    def __init__(self, db: DB):
        self.db = db

    def insert_mediafile(self, file_path, file_name, file_size, hash_value, last_modified):
        sql = """
            INSERT INTO mediafiles (file_path, file_name, file_size, hash, created_at, last_modified)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (file_path, file_name, file_size, hash_value, datetime.now(), last_modified))
            conn.commit()
            return cur.lastrowid

    def insert_parameters_bulk(self, params):
        # params: list of tuples (mediafile_id, category, parameter, value)
        sql = "INSERT INTO mi_parameter (mediafile_id, category, parameter, value) VALUES (%s, %s, %s, %s)"
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.executemany(sql, params)
            conn.commit()

    def find_parameters(self, search_text):
        sql = """
            SELECT m.file_name, p.category, p.parameter, p.value
            FROM mi_parameter p
            JOIN mediafiles m ON m.id = p.mediafile_id
            WHERE p.parameter LIKE %s OR p.value LIKE %s
            LIMIT 100
        """
        like = f"%{search_text}%"
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (like, like))
            return cur.fetchall()

    def list_media(self, limit: int = 100):
        sql = """
            SELECT id, file_path, file_name, file_size, hash, created_at
            FROM mediafiles
            ORDER BY created_at DESC
            LIMIT %s
        """
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (limit,))
            return cur.fetchall()

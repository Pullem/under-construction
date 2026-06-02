from PyQt6.QtCore import QThreadPool
from utils.threads import Worker
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

class MediaPresenter:
    def __init__(self, view, repo, mediainfo_service, hashing_service, watch_service, config):
        self.view = view
        self.repo = repo
        self.mediainfo = mediainfo_service
        self.hashing = hashing_service
        self.watch = watch_service
        self.config = config
        self.pool = QThreadPool.globalInstance()
        # Limit number of concurrent workers to the DB connection pool size
        try:
            pool_size = int(self.config.get("mariadb", "pool_size", fallback=5))
        except Exception:
            pool_size = 5
        if pool_size < 1:
            pool_size = 1
        try:
            self.pool.setMaxThreadCount(pool_size)
            logger.info("Set QThreadPool max threads to %d", pool_size)
        except Exception:
            logger.debug("Failed to set QThreadPool max threads; continuing with defaults")
        self.view.start_import_requested.connect(self.on_start_import)
        self.view.open_config_requested.connect(self.on_open_config)
        self.view.scan_requested.connect(self.on_scan_watchfolder)
        self.view.search_changed.connect(self.on_search_changed)

        # initial load of file list
        try:
            self._refresh_file_list()
        except Exception:
            logger.exception("Failed to load initial file list")

    def on_open_config(self):
        path = self.config.path
        logger.info("Opening config in editor: %s", path)
        self.view.open_file_in_editor(path)

    def on_scan_watchfolder(self):
        logger.info("Scanning watchfolder")
        files = self.watch.scan()
        logger.info("Found %d files in watchfolder", len(files))
        self.view.show_message(f"Gefundene Dateien: {len(files)}")

    def on_start_import(self):
        logger.info("Start import requested")
        files = self.watch.scan()
        logger.info("Importing %d files", len(files))
        for f in files:
            logger.debug("Queueing import worker for %s", f)
            worker = Worker(self._import_file, f)
            worker.signals.result.connect(self._on_import_result)
            worker.signals.error.connect(self._on_import_error)
            self.pool.start(worker)

    def _import_file(self, file_path):
        logger.info("Importing file: %s", file_path)
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        last_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        logger.debug("File metadata: name=%s size=%d last_modified=%s", file_name, file_size, last_modified)
        hashv = self.hashing.sha256_file(file_path)
        logger.debug("Computed hash for %s: %s", file_path, hashv)
        mi = self.mediainfo.parse_media(file_path)
        logger.debug("Parsed mediainfo for %s: %s", file_path, bool(mi))
        media_id = self.repo.insert_mediafile(file_path, file_name, file_size, hashv, last_modified)
        logger.info("Inserted mediafile id=%s for %s", media_id, file_path)
        params = []
        for cat, attrs in mi.items():
            for k, v in attrs:
                params.append((media_id, cat, k, v))
        if params:
            logger.debug("Inserting %d parameters for media_id=%s", len(params), media_id)
            self.repo.insert_parameters_bulk(params)
        return file_path

    def _on_import_result(self, file_path):
        logger.info("Import finished for %s", file_path)
        self.view.show_message(f"Import fertig: {file_path}")
        # refresh list from repository
        try:
            self._refresh_file_list()
        except Exception:
            logger.exception("Failed to refresh file list after import")

    def _on_import_error(self, exc):
        logger.exception("Error during import: %s", exc)
        self.view.show_message(f"Fehler beim Import: {exc}")

    def on_search_changed(self, text):
        self.view.apply_search(text)

    def _refresh_file_list(self):
        items = self.repo.list_media(100)
        # delegate to view to display
        try:
            self.view.file_list.set_items(items)
        except Exception:
            logger.exception("Failed to set items on FileListView")

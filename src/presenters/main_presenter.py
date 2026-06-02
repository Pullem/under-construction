import logging
from models.db import DB
from models.repositories import MediaRepository
from services.mediainfo_service import MediaInfoService
from services.hashing_service import HashingService
from services.watchfolder_service import WatchfolderService
from presenters.media_presenter import MediaPresenter

class MainPresenter:
    def __init__(self, view, config):
        self.logger = logging.getLogger(__name__)
        self.view = view
        self.config = config

        db_cfg = config.get_section("mariadb")
        self.db = DB(
            host=db_cfg.get("host", "localhost"),
            port=int(db_cfg.get("port", 3306)),
            user=db_cfg.get("user", "vfa_user"),
            password=db_cfg.get("password", "vfa_password"),
            database=db_cfg.get("database", "vfa_db")
        )
        self.repo = MediaRepository(self.db)
        self.mediainfo = MediaInfoService()
        self.hashing = HashingService()
        self.watch = WatchfolderService(config.get("project", "watchfolder", fallback="watch"))
        self.media_presenter = MediaPresenter(self.view, self.repo, self.mediainfo, self.hashing, self.watch, config)
        self.logger.info("MainPresenter initialized; repo=%s", type(self.repo).__name__)

    def on_start_import(self):
        """Forward start import request to the media presenter."""
        self.logger.debug("on_start_import called")
        return self.media_presenter.on_start_import()

    def on_open_config(self):
        """Forward open config request to the media presenter."""
        self.logger.debug("on_open_config called")
        return self.media_presenter.on_open_config()

    def on_scan_watchfolder(self):
        """Forward scan watchfolder request to the media presenter."""
        self.logger.debug("on_scan_watchfolder called")
        return self.media_presenter.on_scan_watchfolder()

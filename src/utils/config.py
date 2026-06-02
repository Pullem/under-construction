import configparser
from pathlib import Path

class Config:
    def __init__(self, path="config/project.ini"):
        self.path = Path(path)
        self.cfg = configparser.ConfigParser()
        if self.path.exists():
            self.cfg.read(self.path)
        else:
            self._create_default()

    def _create_default(self):
        self.cfg["project"] = {"project_name": "video-forensik", "watchfolder": "watch"}
        self.cfg["mariadb"] = {"host": "localhost", "port": "3306", "user": "vfa_user", "password": "vfa_password", "database": "vfa_db"}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            self.cfg.write(f)

    def get(self, section, key, fallback=None):
        return self.cfg.get(section, key, fallback=fallback)

    def get_section(self, section):
        return dict(self.cfg[section]) if section in self.cfg else {}

    def set(self, section, key, value):
        if section not in self.cfg:
            self.cfg[section] = {}
        self.cfg[section][key] = str(value)
        with open(self.path, "w") as f:
            self.cfg.write(f)

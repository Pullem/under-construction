import os
from pathlib import Path

class WatchfolderService:
    def __init__(self, watchfolder):
        self.watchfolder = Path(watchfolder)
        self.watchfolder.mkdir(parents=True, exist_ok=True)

    def scan(self):
        files = []
        for p in self.watchfolder.iterdir():
            if p.is_file():
                if p.suffix.lower() in (".mp4", ".mkv", ".mov", ".avi", ".jpg", ".png", ".jpeg", ".tiff"):
                    files.append(str(p.resolve()))
        return files

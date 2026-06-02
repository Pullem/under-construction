import importlib
from pathlib import Path

class PluginManager:
    def __init__(self, plugin_folder="src/plugins"):
        self.plugin_folder = Path(plugin_folder)
        self.plugins = []

    def load_plugins(self):
        for p in self.plugin_folder.glob("*.py"):
            name = p.stem
            mod = importlib.import_module(f"plugins.{name}")
            if hasattr(mod, "register"):
                self.plugins.append(mod)

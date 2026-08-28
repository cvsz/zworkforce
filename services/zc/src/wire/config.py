"""config.py — Configuration management"""
import json
import os

CONFIG_PATH = os.path.expanduser("~/.ai-coder-config.json")

class Config:
    def __init__(self):
        self._data = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH) as f:
                    self._data = json.load(f)
            except Exception:
                pass

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        with open(CONFIG_PATH, "w") as f:
            json.dump(self._data, f, indent=2)

    def all(self):
        return dict(self._data)

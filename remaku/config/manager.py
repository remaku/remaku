"""Configuration loading and persistence for the Remaku application."""

import json
from pathlib import Path

from platformdirs import user_documents_dir

from remaku.config.models import AppConfig


class ConfigManager:
    def __init__(self, app_name: str = "remaku"):
        self.data_dir = Path(user_documents_dir()) / app_name
        self.config_path = self.data_dir / "config.json"

    def load(self) -> AppConfig:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        default_config = AppConfig()

        if not self.config_path.exists():
            self.save(default_config)
            return default_config

        try:
            with self.config_path.open("r", encoding="utf-8") as file:
                raw_data = json.load(file)
        except (OSError, json.JSONDecodeError):
            self.save(default_config)
            return default_config

        if not isinstance(raw_data, dict):
            self.save(default_config)
            return default_config

        merged_data = self.merge_defaults(default_config.to_dict(), raw_data)
        config = AppConfig.from_dict(merged_data)

        if merged_data != raw_data:
            self.save(config)

        return config

    def save(self, config: AppConfig) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

        with self.config_path.open("w", encoding="utf-8") as file:
            json.dump(config.to_dict(), file, indent=2, ensure_ascii=False)
            file.write("\n")

    def merge_defaults(self, defaults: dict, data: dict) -> dict:
        merged: dict = {}

        for key, default_value in defaults.items():
            value = data.get(key, default_value)

            if isinstance(default_value, dict) and isinstance(value, dict):
                merged[key] = self.merge_defaults(default_value, value)
                continue

            merged[key] = value

        return merged

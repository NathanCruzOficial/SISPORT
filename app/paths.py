"""
app/paths.py — Caminhos centralizados do Sisport
==================================================
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "SISPORT"


def _get_base_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_DIR_NAME

    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME

    else:
        base = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
        return Path(base) / APP_DIR_NAME


APP_DIR     = _get_base_dir()
DB_DIR      = APP_DIR / "db"
UPLOADS_DIR = APP_DIR / "uploads"
LOG_DIR     = APP_DIR / "logs"
CONFIG_DIR  = APP_DIR / "config"
BACKUP_DIR  = APP_DIR / "backups"

_ALL_DIRS = (DB_DIR, UPLOADS_DIR, LOG_DIR, CONFIG_DIR, BACKUP_DIR)


def ensure_app_dirs() -> None:
    for d in _ALL_DIRS:
        d.mkdir(parents=True, exist_ok=True)


def db_path(filename: str = "data.sqlite3") -> Path:
    return DB_DIR / filename


def log_path(filename: str = "sisport.log") -> Path:
    return LOG_DIR / filename


def config_path(filename: str = "settings.json") -> Path:
    return CONFIG_DIR / filename

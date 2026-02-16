# models/settings.py
from __future__ import annotations

from sqlalchemy import String, Text
from app.extensions import db


class AppSetting(db.Model):
    __tablename__ = "app_settings"

    key = db.Column(String(64), primary_key=True)
    value = db.Column(Text, nullable=False)


def get_setting(key: str, default: str | None = None) -> str | None:
    row = db.session.get(AppSetting, key)
    return row.value if row else default


def set_setting(key: str, value: str) -> None:
    row = db.session.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.session.add(AppSetting(key=key, value=value))

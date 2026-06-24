"""
database/__init__.py - Módulo de base de datos del bot YSL.
"""

from .mongo import (
    users_col,
    weekly_snapshots_col,
    guild_settings_col,
    warnings_col,
    events_col,
    tickets_col,
    ensure_indexes,
)

__all__ = [
    "users_col",
    "weekly_snapshots_col",
    "guild_settings_col",
    "warnings_col",
    "events_col",
    "tickets_col",
    "ensure_indexes",
]

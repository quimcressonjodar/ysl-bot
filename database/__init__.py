"""
database/__init__.py - Database module for the YSL Bot.
"""

from .mongo import (
    users_col,
    weekly_snapshots_col,
    guild_settings_col,
    warnings_col,
    events_col,
    ensure_indexes,
)

__all__ = [
    "users_col",
    "weekly_snapshots_col",
    "guild_settings_col",
    "warnings_col",
    "events_col",
    "ensure_indexes",
]

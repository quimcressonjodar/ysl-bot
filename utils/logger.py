"""
utils/logger.py — centralised action logging to MongoDB (bot_logs_col).

Each call writes one document to the `bot_logs` collection so staff can
query moderation and modmail activity per guild via the dashboard.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from database import bot_logs_col

log = logging.getLogger("weekly-xp-bot")


def log_action(
    *,
    guild_id: int,
    log_type: str,
    action: str,
    actor_id: int,
    actor_name: str,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    reason: Optional[str] = None,
    channel_id: Optional[int] = None,
    channel_name: Optional[str] = None,
) -> None:
    """Insert one action-log document into MongoDB.

    Parameters
    ----------
    guild_id:    Discord guild (server) ID.
    log_type:    Category string, e.g. ``"moderation"`` or ``"modmail"``.
    action:      Specific action, e.g. ``"ban"``, ``"ticket_opened"``.
    actor_id:    Discord ID of the staff member who triggered the action.
    actor_name:  Display name / tag of the actor at the time of the action.
    target_id:   Discord ID of the affected user (optional).
    target_name: Display name of the affected user (optional).
    reason:      Human-readable reason string (optional).
    channel_id:  Channel where the action occurred (optional).
    channel_name: Channel name (optional).
    """
    doc = {
        "guild_id": guild_id,
        "type": log_type,
        "action": action,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "timestamp": datetime.now(timezone.utc),
    }

    if target_id is not None:
        doc["target_id"] = target_id
    if target_name is not None:
        doc["target_name"] = target_name
    if reason is not None:
        doc["reason"] = reason
    if channel_id is not None:
        doc["channel_id"] = channel_id
    if channel_name is not None:
        doc["channel_name"] = channel_name

    try:
        bot_logs_col.insert_one(doc)
    except Exception as exc:
        # Never let a logging failure crash the bot.
        log.warning("log_action: failed to insert log document: %s", exc)

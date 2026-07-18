"""
Centralised activity logger for YSL Bot.
All calls are fire-and-forget — exceptions are swallowed so logging
never breaks bot functionality.
"""

from datetime import datetime, timezone
from database import bot_logs_col


def log_action(
    guild_id,
    log_type: str,   # "command" | "economy" | "moderation"
    action: str,     # command name / "ban" / "kick" / "warn" / "daily" / etc.
    actor_id,
    actor_name: str,
    target_id=None,
    target_name: str = None,
    amount: int = None,
    reason: str = None,
    channel_id=None,
    channel_name: str = None,
    metadata: dict = None,
):
    try:
        bot_logs_col.insert_one({
            "guild_id":    int(guild_id) if guild_id is not None else None,
            "type":        log_type,
            "action":      action,
            "actor_id":    str(actor_id),
            "actor_name":  str(actor_name),
            "target_id":   str(target_id) if target_id is not None else None,
            "target_name": str(target_name) if target_name is not None else None,
            "amount":      int(amount) if amount is not None else None,
            "reason":      reason,
            "channel_id":  str(channel_id) if channel_id is not None else None,
            "channel_name": str(channel_name) if channel_name is not None else None,
            "metadata":    metadata or {},
            "timestamp":   datetime.now(timezone.utc),
        })
    except Exception:
        pass  # logging must never crash the bot

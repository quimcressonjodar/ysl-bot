"""
utils/helpers.py - General utility functions for the YSL Bot.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord

import config

logger = logging.getLogger("ysl-bot.helpers")


def utcnow() -> datetime:
    """Returns the current time in UTC."""
    return datetime.now(timezone.utc)


def format_date(dt: datetime) -> str:
    """Formats a datetime object as a human-readable string."""
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def get_week_date_str(dt: Optional[datetime] = None) -> str:
    """
    Returns a string identifier for the week of the given date.
    Format: YYYY-WXX (e.g., 2026-W26)
    """
    if dt is None:
        dt = utcnow()
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def is_admin_interaction(interaction: discord.Interaction) -> bool:
    """Checks if the interaction user has administrator permissions."""
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    return interaction.user.guild_permissions.administrator


def is_mod_interaction(interaction: discord.Interaction) -> bool:
    """Checks if the interaction user has moderator permissions."""
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    perms = interaction.user.guild_permissions
    return perms.administrator or perms.manage_messages or perms.kick_members or perms.ban_members


def parse_duration(duration_str: str) -> Optional[timedelta]:
    """
    Parses a duration string (e.g., '1d', '2h', '30m') into a timedelta.
    Returns None if the format is invalid.
    """
    if not duration_str:
        return None

    try:
        duration_str = duration_str.strip().lower()
        amount = int(duration_str[:-1])
        unit = duration_str[-1]

        if unit == "s":
            return timedelta(seconds=amount)
        elif unit == "m":
            return timedelta(minutes=amount)
        elif unit == "h":
            return timedelta(hours=amount)
        elif unit == "d":
            return timedelta(days=amount)
        else:
            return None
    except (ValueError, IndexError):
        return None


def error_embed(description: str, title: str = "Error") -> discord.Embed:
    """Creates a standard error embed."""
    return discord.Embed(
        title=f"{config.EMOJI_ERROR} {title}",
        description=description,
        color=config.COLOR_ERROR,
        timestamp=utcnow(),
    )


def success_embed(description: str, title: str = "Success") -> discord.Embed:
    """Creates a standard success embed."""
    return discord.Embed(
        title=f"{config.EMOJI_SUCCESS} {title}",
        description=description,
        color=config.COLOR_SUCCESS,
        timestamp=utcnow(),
    )

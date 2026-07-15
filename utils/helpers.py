from datetime import timedelta

import discord
from discord.ext import commands

from database import warns_col


from config import OWNER_IDS

OWNER_ID = 1436417791615045785

def is_admin(ctx: commands.Context) -> bool:
    return ctx.author.id in OWNER_IDS


def parse_duration(duration_str: str) -> timedelta | None:
    try:
        if duration_str.endswith("m"):
            return timedelta(minutes=int(duration_str[:-1]))
        elif duration_str.endswith("h"):
            return timedelta(hours=int(duration_str[:-1]))
        elif duration_str.endswith("d"):
            return timedelta(days=int(duration_str[:-1]))
        else:
            return timedelta(minutes=int(duration_str))
    except ValueError:
        return None


def load_warns() -> dict:
    doc = warns_col.find_one({"_id": "all_warns"})
    return doc["data"] if doc else {}


def save_warns(data: dict) -> None:
    warns_col.update_one({"_id": "all_warns"}, {"$set": {"data": data}}, upsert=True)


def get_next_warn_id() -> int:
    """
    Returns a permanent, ever-increasing warn ID (server-wide, never reused).
    Warn IDs must stay fixed even after other warnings are deleted, so callers
    should NOT re-number remaining warnings after a delete.
    """
    doc = warns_col.find_one_and_update(
        {"_id": "warn_counter"},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=True,
    )
    return doc["value"]


def can_moderate(ctx: commands.Context, member: discord.Member) -> str | None:
    """
    Shared safety checks for moderation commands.
    Anyone can be moderated — owners, admins, and even the moderator
    themselves are not protected. The only hard block left is the bot's own
    account, since it can't meaningfully ban/kick/warn/timeout itself.
    Returns an error message if the action should be blocked, or None if it's allowed.
    """
    if member.id == ctx.bot.user.id:
        return "❌ I can't use this on myself."
    return None

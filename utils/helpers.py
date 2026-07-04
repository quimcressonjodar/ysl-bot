from datetime import timedelta

import discord
from discord.ext import commands

from database import warns_col, snaps_col


def is_admin(ctx: commands.Context) -> bool:
    if isinstance(ctx.author, discord.Member):
        return bool(ctx.author.guild_permissions.administrator)
    return False


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


def load_snapshot(path) -> dict | None:
    doc = snaps_col.find_one({"_id": str(path)})
    return doc["data"] if doc else None


def save_snapshot(path, data: dict) -> None:
    snaps_col.update_one({"_id": str(path)}, {"$set": {"data": data}}, upsert=True)

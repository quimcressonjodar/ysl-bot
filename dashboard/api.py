import os
from functools import wraps

import requests
from bson.decimal128 import Decimal128
from flask import Blueprint, jsonify, request, session

from database import (
    eco_col,
    starboard_messages_col,
    bot_guilds_col,
    dashboard_modules_col,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")

DISCORD_API = "https://discord.com/api/v10"

MODULE_DEFAULTS = [
    {"name": "economy",   "display_name": "Economy",      "description": "Coins, balance, daily rewards, and transactions",   "enabled": True,  "icon": "coins"},
    {"name": "pets",      "display_name": "Pets",         "description": "Adopt, train, and battle virtual pets",             "enabled": True,  "icon": "paw-print"},
    {"name": "games",     "display_name": "Games",        "description": "Slots, coinflip, blackjack, and more casino games", "enabled": True,  "icon": "dice-5"},
    {"name": "stocks",    "display_name": "Stocks",       "description": "Simulated stock market to invest in",               "enabled": True,  "icon": "trending-up"},
    {"name": "bounties",  "display_name": "Bounties",     "description": "Place and claim bounties on other members",         "enabled": False, "icon": "crosshair"},
    {"name": "business",  "display_name": "Business",     "description": "Run virtual businesses and earn passive income",    "enabled": True,  "icon": "briefcase"},
    {"name": "starboard", "display_name": "Starboard",    "description": "Highlight the best messages in a dedicated channel","enabled": True,  "icon": "star"},
    {"name": "modmail",   "display_name": "Modmail",      "description": "Private DM-based moderation support inbox",         "enabled": False, "icon": "mail"},
    {"name": "troll",     "display_name": "Troll",        "description": "Prank commands and fun chaos tools",                "enabled": False, "icon": "zap"},
    {"name": "horserace", "display_name": "Horse Racing", "description": "Bet on simulated horse races with your coins",      "enabled": True,  "icon": "flag"},
    {"name": "events",    "display_name": "Events",       "description": "Schedule and announce server events",               "enabled": False, "icon": "calendar"},
    {"name": "admin",     "display_name": "Admin",        "description": "Moderation, warnings, kicks, bans, and jail system","enabled": True,  "icon": "shield"},
]


def _from_decimal128(value) -> int:
    if isinstance(value, Decimal128):
        return int(value.to_decimal())
    if value is None:
        return 0
    return int(value)


def _discord_get(path: str, token: str):
    resp = requests.get(
        f"{DISCORD_API}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def _is_admin(permissions: int) -> bool:
    ADMINISTRATOR = 0x8
    MANAGE_GUILD = 0x20
    return bool(permissions & (ADMINISTRATOR | MANAGE_GUILD))


# ── Auth / user ───────────────────────────────────────────────────────────────

@api_bp.route("/me")
@login_required
def me():
    return jsonify(session["user"])


# ── Guilds ────────────────────────────────────────────────────────────────────

@api_bp.route("/guilds")
@login_required
def guilds():
    token = session.get("access_token", "")
    try:
        user_guilds = _discord_get("/users/@me/guilds", token)
    except Exception:
        return jsonify([])

    bot_guild_ids = {
        doc["guild_id"] for doc in bot_guilds_col.find({}, {"guild_id": 1})
    }

    result = []
    for g in user_guilds:
        perms = int(g.get("permissions", 0))
        if not _is_admin(perms):
            continue
        guild_id = int(g["id"])
        result.append({
            "id": g["id"],
            "name": g["name"],
            "icon": g.get("icon"),
            "member_count": 0,
            "bot_present": guild_id in bot_guild_ids,
        })

    return jsonify(result)


@api_bp.route("/guilds/<guild_id>")
@login_required
def guild_detail(guild_id: str):
    pipeline = [
        {"$addFields": {
            "wallet_num": {"$toDouble": "$wallet"},
            "bank_num":   {"$toDouble": "$bank"},
        }},
        {"$addFields": {"total": {"$add": ["$wallet_num", "$bank_num"]}}},
        {"$group": {
            "_id": None,
            "total_coins": {"$sum": "$total"},
            "user_count":  {"$sum": 1},
        }},
    ]
    agg = list(eco_col.aggregate(pipeline))
    total_coins = int(agg[0]["total_coins"]) if agg else 0
    user_count  = agg[0]["user_count"] if agg else 0

    return jsonify({
        "id": guild_id,
        "name": "Your Server",
        "icon": None,
        "member_count": user_count,
        "online_count": 0,
        "bot_online": True,
        "prefix": "!",
        "commands_today": 0,
        "commands_total": eco_col.count_documents({}),
    })


@api_bp.route("/guilds/<guild_id>/stats")
@login_required
def guild_stats(guild_id: str):
    pipeline = [
        {"$addFields": {
            "wallet_num": {"$toDouble": "$wallet"},
            "bank_num":   {"$toDouble": "$bank"},
        }},
        {"$addFields": {"total": {"$add": ["$wallet_num", "$bank_num"]}}},
        {"$group": {
            "_id": None,
            "total_coins": {"$sum": "$total"},
        }},
    ]
    agg = list(eco_col.aggregate(pipeline))
    total_coins  = int(agg[0]["total_coins"]) if agg else 0
    active_users = eco_col.count_documents({"last_daily": {"$exists": True}})

    return jsonify({
        "commands_per_day": [],
        "top_commands": [
            {"command": "balance",     "count": 0},
            {"command": "daily",       "count": 0},
            {"command": "slots",       "count": 0},
            {"command": "flip",        "count": 0},
            {"command": "leaderboard", "count": 0},
        ],
        "active_users": active_users,
        "total_transactions": eco_col.count_documents({}),
        "total_coins_in_circulation": total_coins,
    })


# ── Modules ───────────────────────────────────────────────────────────────────

@api_bp.route("/guilds/<guild_id>/modules")
@login_required
def get_modules(guild_id: str):
    gid = int(guild_id)
    overrides = {
        doc["module"]: doc["enabled"]
        for doc in dashboard_modules_col.find({"guild_id": gid})
    }
    result = [
        {**mod, "enabled": overrides.get(mod["name"], mod["enabled"])}
        for mod in MODULE_DEFAULTS
    ]
    return jsonify(result)


@api_bp.route("/guilds/<guild_id>/modules/<module_name>", methods=["PATCH"])
@login_required
def update_module(guild_id: str, module_name: str):
    gid = int(guild_id)
    body = request.get_json(silent=True) or {}
    enabled = bool(body.get("enabled", False))

    dashboard_modules_col.update_one(
        {"guild_id": gid, "module": module_name},
        {"$set": {"enabled": enabled}},
        upsert=True,
    )

    mod_meta = next((m for m in MODULE_DEFAULTS if m["name"] == module_name), None)
    if not mod_meta:
        return jsonify({"error": "Module not found"}), 404

    return jsonify({**mod_meta, "enabled": enabled})


# ── Economy leaderboard ───────────────────────────────────────────────────────

@api_bp.route("/guilds/<guild_id>/economy/leaderboard")
@login_required
def economy_leaderboard(guild_id: str):
    pipeline = [
        {"$addFields": {
            "wallet_num": {"$toDouble": "$wallet"},
            "bank_num":   {"$toDouble": "$bank"},
        }},
        {"$addFields": {"total": {"$add": ["$wallet_num", "$bank_num"]}}},
        {"$sort": {"total": -1}},
        {"$limit": 10},
        {"$project": {"_id": 1, "total": 1}},
    ]
    docs = list(eco_col.aggregate(pipeline))
    result = [
        {
            "user_id":  doc["_id"],
            "username": f"User {doc['_id'][:6]}",
            "avatar":   None,
            "balance":  int(doc.get("total") or 0),
            "rank":     i + 1,
            "level":    None,
        }
        for i, doc in enumerate(docs)
    ]
    return jsonify(result)


# ── Starboard top ─────────────────────────────────────────────────────────────

@api_bp.route("/guilds/<guild_id>/starboard/top")
@login_required
def starboard_top(guild_id: str):
    gid = int(guild_id)
    docs = list(
        starboard_messages_col.find({"guild_id": gid})
        .sort("starboard_message_id", -1)
        .limit(10)
    )
    result = [
        {
            "message_id":    str(doc.get("original_message_id", 0)),
            "author_id":     "0",
            "author_name":   "Unknown",
            "author_avatar": None,
            "content":       f"Message ID: {doc.get('original_message_id', 0)}",
            "star_count":    doc.get("star_count", 1),
            "channel_name":  "starboard",
            "jump_url":      f"https://discord.com/channels/{guild_id}/{doc.get('original_message_id', 0)}",
        }
        for doc in docs
    ]
    return jsonify(result)

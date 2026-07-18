import os
from functools import wraps

import requests
from bson import ObjectId
from flask import Blueprint, jsonify, request, session

from database import bot_guilds_col, bot_logs_col

api_bp = Blueprint("api", __name__, url_prefix="/api")

DISCORD_API = "https://discord.com/api/v10"


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    return bool(permissions & (0x8 | 0x20))  # ADMINISTRATOR | MANAGE_GUILD


def _serialize_log(doc: dict) -> dict:
    ts = doc.get("timestamp")
    return {
        "id":           str(doc["_id"]),
        "type":         doc.get("type", "command"),
        "action":       doc.get("action", ""),
        "actor_id":     doc.get("actor_id"),
        "actor_name":   doc.get("actor_name", "Unknown"),
        "target_id":    doc.get("target_id"),
        "target_name":  doc.get("target_name"),
        "amount":       doc.get("amount"),
        "reason":       doc.get("reason"),
        "channel_name": doc.get("channel_name"),
        "timestamp":    ts.isoformat() + "Z" if ts else None,
    }


# ── Auth / me ─────────────────────────────────────────────────────────────────

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
            "id":           g["id"],
            "name":         g["name"],
            "icon":         g.get("icon"),
            "member_count": 0,
            "bot_present":  guild_id in bot_guild_ids,
        })

    return jsonify(result)


@api_bp.route("/guilds/<guild_id>")
@login_required
def guild_detail(guild_id: str):
    gid = int(guild_id)
    total_logs = bot_logs_col.count_documents({"guild_id": gid})
    mod_actions = bot_logs_col.count_documents({"guild_id": gid, "type": "moderation"})
    return jsonify({
        "id":           guild_id,
        "name":         "Your Server",
        "icon":         None,
        "total_logs":   total_logs,
        "mod_actions":  mod_actions,
        "bot_online":   True,
    })


# ── Activity logs ─────────────────────────────────────────────────────────────

@api_bp.route("/guilds/<guild_id>/logs")
@login_required
def get_logs(guild_id: str):
    gid   = int(guild_id)
    ftype = request.args.get("type", "all")      # all | command | economy | moderation
    page  = max(1, int(request.args.get("page", 1)))
    limit = min(100, max(10, int(request.args.get("limit", 50))))
    skip  = (page - 1) * limit

    query: dict = {"guild_id": gid}
    if ftype != "all":
        query["type"] = ftype

    total = bot_logs_col.count_documents(query)
    docs  = list(
        bot_logs_col.find(query)
        .sort("timestamp", -1)
        .skip(skip)
        .limit(limit)
    )

    return jsonify({
        "logs":     [_serialize_log(d) for d in docs],
        "total":    total,
        "page":     page,
        "has_more": (skip + limit) < total,
    })

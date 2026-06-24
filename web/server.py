"""
web/server.py - Flask backend for the YSL Bot.
"""

import logging
import os
from datetime import datetime, timezone
from threading import Thread

from flask import Flask, jsonify, request

logger = logging.getLogger("ysl-bot.web")

app = Flask("ysl-bot-web")
app.config["JSON_SORT_KEYS"] = False

_bot_ref = None

def set_bot(bot) -> None:
    global _bot_ref
    _bot_ref = bot

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "service": "YSL Bot · Protox.io Clan",
        "version": "1.1.0",
        "description": "Official bot for the YSL Clan on Protox.io",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

@app.route("/health", methods=["GET"])
def health():
    bot_ready = _bot_ref is not None and _bot_ref.is_ready() if _bot_ref else False
    return jsonify({
        "status": "healthy",
        "bot_ready": bot_ready,
    }), 200

@app.route("/api/stats", methods=["GET"])
def get_stats():
    try:
        from database import users_col, weekly_snapshots_col
        total_users = users_col.count_documents({})
        total_snapshots = weekly_snapshots_col.count_documents({})

        return jsonify({
            "clan": "YSL",
            "registered_players": total_users,
            "total_snapshots": total_snapshots,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error(f"Error in /api/stats: {e}")
        return jsonify({"error": "Internal server error"}), 500

def _run_flask() -> None:
    port = int(os.getenv("PORT", "10000"))
    logger.info(f"Flask server starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def start_web_server(bot=None) -> None:
    if bot is not None:
        set_bot(bot)
    thread = Thread(target=_run_flask, name="flask-server", daemon=True)
    thread.start()
    logger.info("Flask server started in a separate thread.")

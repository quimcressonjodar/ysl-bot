"""
database/mongo.py - MongoDB connection and collections for the YSL Bot.
"""

import os
import logging
import pymongo
from pymongo import MongoClient
from pymongo.collection import Collection

import config

logger = logging.getLogger("ysl-bot.database")

# ============================================================
# MongoDB Connection
# ============================================================
_MONGO_URI = os.getenv("MONGO_URI", "")
_DB_NAME = os.getenv("DB_NAME", "ysl_bot")

try:
    # Added tlsAllowInvalidCertificates=True as a fallback for some hosting environments
    # but the primary fix for Atlas is ensuring the connection string is correct.
    # We also set a serverSelectionTimeoutMS to fail faster if connection is bad.
    _client: MongoClient = MongoClient(
        _MONGO_URI,
        serverSelectionTimeoutMS=5000,
        tlsAllowInvalidCertificates=True 
    )
    _db = _client[_DB_NAME]
    logger.info(f"Connected to MongoDB. Database: '{_DB_NAME}'")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

# ============================================================
# Collections
# ============================================================
users_col: Collection = _db["users"]
weekly_snapshots_col: Collection = _db["weekly_snapshots"]
guild_settings_col: Collection = _db["guild_settings"]
warnings_col: Collection = _db["warnings"]
events_col: Collection = _db["events"]

# ============================================================
# Indexes
# ============================================================
def ensure_indexes() -> None:
    """Creates necessary indexes in MongoDB."""
    try:
        users_col.create_index("discord_id", unique=True, background=True)
        users_col.create_index("protox_player_id", background=True)

        weekly_snapshots_col.create_index(
            [("player_id", pymongo.ASCENDING), ("week_date", pymongo.DESCENDING)],
            background=True,
        )

        warnings_col.create_index("user_id", background=True)

        events_col.create_index(
            [("guild_id", pymongo.ASCENDING), ("event_type", pymongo.ASCENDING)],
            background=True,
        )

        logger.info("MongoDB indexes verified.")
    except Exception as e:
        logger.warning(f"Could not verify some indexes: {e}")

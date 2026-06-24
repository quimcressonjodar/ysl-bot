"""
database/mongo.py - Conexión y colecciones de MongoDB para el bot YSL.

Expone las colecciones principales del bot de forma centralizada.
"""

import os
import logging
import pymongo
from pymongo import MongoClient
from pymongo.collection import Collection

logger = logging.getLogger("ysl-bot.database")

# ============================================================
# Conexión a MongoDB
# ============================================================
_MONGO_URI = os.getenv("MONGO_URI", "")
_DB_NAME = os.getenv("DB_NAME", "ysl_bot")

try:
    _client: MongoClient = MongoClient(_MONGO_URI)
    _db = _client[_DB_NAME]
    logger.info(f"Conexión a MongoDB establecida. Base de datos: '{_DB_NAME}'")
except Exception as e:
    logger.error(f"Error al conectar con MongoDB: {e}")
    raise

# ============================================================
# Colecciones
# ============================================================

# Usuarios registrados: vinculación Discord ID <-> Protox Player ID
users_col: Collection = _db["users"]

# Snapshots semanales de XP por jugador
weekly_snapshots_col: Collection = _db["weekly_snapshots"]

# Configuración del servidor (canales, roles, etc.)
guild_settings_col: Collection = _db["guild_settings"]

# Advertencias de moderación
warnings_col: Collection = _db["warnings"]

# Eventos del servidor (logs)
events_col: Collection = _db["events"]

# Tickets de soporte
tickets_col: Collection = _db["tickets"]

# ============================================================
# Índices recomendados (ejecutar una sola vez al iniciar)
# ============================================================

def ensure_indexes() -> None:
    """Crea los índices necesarios en MongoDB si no existen."""
    try:
        # users: búsqueda por discord_id y por protox_player_id
        users_col.create_index("discord_id", unique=True, background=True)
        users_col.create_index("protox_player_id", background=True)

        # weekly_snapshots: búsqueda por player_id y por semana
        weekly_snapshots_col.create_index(
            [("player_id", pymongo.ASCENDING), ("week_date", pymongo.DESCENDING)],
            background=True,
        )

        # warnings: búsqueda por discord_id
        warnings_col.create_index("discord_id", background=True)

        # events: búsqueda por guild_id y tipo
        events_col.create_index(
            [("guild_id", pymongo.ASCENDING), ("event_type", pymongo.ASCENDING)],
            background=True,
        )

        # tickets: búsqueda por guild_id y estado
        tickets_col.create_index(
            [("guild_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)],
            background=True,
        )

        logger.info("Índices de MongoDB verificados/creados correctamente.")
    except Exception as e:
        logger.warning(f"No se pudieron crear algunos índices: {e}")

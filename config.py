"""
config.py - Configuración central del bot YSL de Protox.io
Carga las variables de entorno y define constantes globales.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# Logging estructurado
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ysl-bot")

# ============================================================
# Discord
# ============================================================
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
OWNER_IDS: set[int] = set(
    int(x) for x in os.getenv("OWNER_IDS", "").split(",") if x.strip().isdigit()
)

# ============================================================
# MongoDB
# ============================================================
MONGO_URI: str = os.getenv("MONGO_URI", "")
DB_NAME: str = os.getenv("DB_NAME", "ysl_bot")

# ============================================================
# Protox.io API
# ============================================================
PROTOX_API_BASE: str = os.getenv("PROTOX_API_BASE", "https://api.protox.io")
PROTOX_API_KEY: str = os.getenv("PROTOX_API_KEY", "")
CLAN_NAME: str = os.getenv("CLAN_NAME", "YSL")

# ============================================================
# Configuración del clan
# ============================================================
WEEKLY_XP_REQUIREMENT: int = int(os.getenv("WEEKLY_XP_REQUIREMENT", "50000"))

# ============================================================
# HTTP Client
# ============================================================
HTTP_TIMEOUT_SECONDS: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))
HTTP_MAX_RETRIES: int = int(os.getenv("HTTP_MAX_RETRIES", "3"))
HTTP_RETRY_BASE_DELAY: float = float(os.getenv("HTTP_RETRY_BASE_DELAY", "0.8"))

# ============================================================
# Flask / Web
# ============================================================
PORT: int = int(os.getenv("PORT", "10000"))

# ============================================================
# Colores para embeds (tema Protox.io)
# ============================================================
COLOR_PRIMARY = 0x5865F2      # Azul Discord/Protox
COLOR_SUCCESS = 0x57F287      # Verde éxito
COLOR_WARNING = 0xFEE75C      # Amarillo advertencia
COLOR_ERROR = 0xED4245        # Rojo error
COLOR_INFO = 0x5865F2         # Azul información
COLOR_GOLD = 0xFFD700         # Dorado para logros
COLOR_DARK = 0x2B2D31         # Oscuro para embeds neutros

# ============================================================
# Emojis del clan YSL
# ============================================================
EMOJI_PROTOX = "🎮"
EMOJI_CLAN = "🏆"
EMOJI_XP = "⭐"
EMOJI_WEEK = "📅"
EMOJI_PLAYER = "👤"
EMOJI_MOD = "🛡️"
EMOJI_ADMIN = "👑"
EMOJI_TICKET = "🎫"
EMOJI_SUCCESS = "✅"
EMOJI_ERROR = "❌"
EMOJI_WARNING = "⚠️"
EMOJI_INFO = "ℹ️"

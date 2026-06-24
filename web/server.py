"""
web/server.py - Backend Flask del bot YSL de Protox.io.

Proporciona endpoints REST para:
- Monitorización del estado del bot (UptimeRobot, Render).
- Consulta de usuarios y estadísticas del clan.
- Dashboard preparado para futuras páginas web.

Se ejecuta en un hilo separado para no bloquear el event loop de Discord.
"""

import logging
import os
from datetime import datetime, timezone
from threading import Thread

from flask import Flask, jsonify, request

logger = logging.getLogger("ysl-bot.web")

# ============================================================
# Aplicación Flask
# ============================================================

app = Flask("ysl-bot-web")
app.config["JSON_SORT_KEYS"] = False

# Referencia al bot de Discord (se inyecta desde main.py)
_bot_ref = None


def set_bot(bot) -> None:
    """Inyecta la referencia al bot de Discord en el servidor Flask."""
    global _bot_ref
    _bot_ref = bot


# ============================================================
# Endpoints
# ============================================================


@app.route("/", methods=["GET"])
def home():
    """
    Endpoint raíz del dashboard.
    Devuelve información básica del bot y el estado del servicio.
    """
    return jsonify({
        "status": "online",
        "service": "YSL Bot · Clan Protox.io",
        "version": "1.0.0",
        "description": "Bot oficial del clan YSL de Protox.io",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints": {
            "health": "/health",
            "users": "/api/users",
            "stats": "/api/stats",
            "leaderboard": "/api/leaderboard",
        },
    })


@app.route("/health", methods=["GET"])
def health():
    """
    Endpoint de salud para UptimeRobot y Render.
    Devuelve 200 OK si el servicio está activo.
    """
    bot_ready = _bot_ref is not None and _bot_ref.is_ready() if _bot_ref else False

    return jsonify({
        "status": "healthy",
        "bot_ready": bot_ready,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route("/api/users", methods=["GET"])
def get_users():
    """
    Endpoint REST para consultar los usuarios registrados del clan.

    Query params:
        - limit (int): Número máximo de usuarios a devolver (default: 50, max: 200).
        - offset (int): Desplazamiento para paginación (default: 0).
    """
    try:
        from database import users_col

        limit = min(int(request.args.get("limit", 50)), 200)
        offset = int(request.args.get("offset", 0))

        total = users_col.count_documents({})
        users = list(
            users_col.find(
                {},
                {"_id": 0, "discord_id": 1, "protox_player_id": 1, "username": 1, "registered_at": 1},
            )
            .skip(offset)
            .limit(limit)
        )

        return jsonify({
            "total": total,
            "limit": limit,
            "offset": offset,
            "users": users,
        })
    except Exception as e:
        logger.error(f"Error en /api/users: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500


@app.route("/api/users/<discord_id>", methods=["GET"])
def get_user(discord_id: str):
    """
    Endpoint REST para consultar un usuario específico por su Discord ID.

    Args:
        discord_id: ID de Discord del usuario.
    """
    try:
        from database import users_col, weekly_snapshots_col

        user = users_col.find_one(
            {"discord_id": discord_id},
            {"_id": 0},
        )

        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # Obtener los últimos 5 snapshots del jugador
        snapshots = list(
            weekly_snapshots_col.find(
                {"player_id": user.get("protox_player_id")},
                {"_id": 0, "week_date": 1, "total_xp": 1, "created_at": 1},
                sort=[("week_date", -1)],
                limit=5,
            )
        )

        return jsonify({
            "user": user,
            "recent_snapshots": snapshots,
        })
    except Exception as e:
        logger.error(f"Error en /api/users/{discord_id}: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """
    Endpoint REST para consultar estadísticas generales del clan.
    """
    try:
        from database import users_col, weekly_snapshots_col, events_col

        total_users = users_col.count_documents({})
        total_snapshots = weekly_snapshots_col.count_documents({})
        total_events = events_col.count_documents({})

        # Última semana con datos
        latest_snapshot = weekly_snapshots_col.find_one(
            {},
            {"_id": 0, "week_date": 1},
            sort=[("week_date", -1)],
        )

        bot_ready = _bot_ref is not None and _bot_ref.is_ready() if _bot_ref else False
        bot_latency = round(_bot_ref.latency * 1000) if bot_ready else None

        return jsonify({
            "clan": "YSL",
            "game": "Protox.io",
            "registered_players": total_users,
            "total_xp_snapshots": total_snapshots,
            "total_events_logged": total_events,
            "latest_week": latest_snapshot.get("week_date") if latest_snapshot else None,
            "bot": {
                "ready": bot_ready,
                "latency_ms": bot_latency,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error(f"Error en /api/stats: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500


@app.route("/api/leaderboard", methods=["GET"])
def get_leaderboard():
    """
    Endpoint REST para consultar el ranking de XP semanal del clan.

    Query params:
        - week (str): Semana en formato "YYYY-WXX" (default: última semana con datos).
        - limit (int): Número máximo de entradas (default: 20, max: 100).
    """
    try:
        from database import weekly_snapshots_col

        limit = min(int(request.args.get("limit", 20)), 100)
        week = request.args.get("week")

        if not week:
            # Obtener la última semana con datos
            latest = weekly_snapshots_col.find_one(
                {},
                {"week_date": 1},
                sort=[("week_date", -1)],
            )
            if not latest:
                return jsonify({"week": None, "leaderboard": []})
            week = latest["week_date"]

        # Obtener snapshots de la semana solicitada
        current_snaps = list(
            weekly_snapshots_col.find(
                {"week_date": week},
                {"_id": 0, "player_id": 1, "username": 1, "total_xp": 1},
            )
        )

        # Obtener semana anterior para calcular XP ganada
        from datetime import timedelta
        year, week_num = week.split("-W")
        from datetime import datetime as dt
        base_date = dt.strptime(f"{year}-W{week_num}-0", "%Y-W%W-%w")
        prev_date = base_date - timedelta(weeks=1)
        prev_week = f"{prev_date.isocalendar()[0]}-W{prev_date.isocalendar()[1]:02d}"

        prev_snaps = {
            s["player_id"]: s.get("total_xp", 0)
            for s in weekly_snapshots_col.find({"week_date": prev_week})
        }

        # Calcular XP ganada y ordenar
        leaderboard = []
        for snap in current_snaps:
            player_id = snap["player_id"]
            current_xp = snap.get("total_xp", 0)
            prev_xp = prev_snaps.get(player_id, 0)
            weekly_xp = max(0, current_xp - prev_xp)
            leaderboard.append({
                "player_id": player_id,
                "username": snap.get("username", player_id),
                "weekly_xp": weekly_xp,
                "total_xp": current_xp,
            })

        leaderboard.sort(key=lambda x: x["weekly_xp"], reverse=True)

        return jsonify({
            "week": week,
            "total_players": len(leaderboard),
            "leaderboard": leaderboard[:limit],
        })
    except Exception as e:
        logger.error(f"Error en /api/leaderboard: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500


@app.route("/api/snapshots/<player_id>", methods=["GET"])
def get_player_snapshots(player_id: str):
    """
    Endpoint REST para consultar el historial de snapshots de un jugador.

    Args:
        player_id: Player ID del jugador en Protox.io.

    Query params:
        - limit (int): Número máximo de snapshots (default: 10, max: 52).
    """
    try:
        from database import weekly_snapshots_col

        limit = min(int(request.args.get("limit", 10)), 52)

        snapshots = list(
            weekly_snapshots_col.find(
                {"player_id": player_id},
                {"_id": 0, "week_date": 1, "total_xp": 1, "created_at": 1},
                sort=[("week_date", -1)],
                limit=limit,
            )
        )

        if not snapshots:
            return jsonify({"error": "Jugador no encontrado o sin snapshots"}), 404

        return jsonify({
            "player_id": player_id,
            "total_snapshots": len(snapshots),
            "snapshots": snapshots,
        })
    except Exception as e:
        logger.error(f"Error en /api/snapshots/{player_id}: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500


# ============================================================
# Servidor en hilo separado
# ============================================================


def _run_flask() -> None:
    """Inicia el servidor Flask en el hilo actual."""
    port = int(os.getenv("PORT", "10000"))
    logger.info(f"Servidor Flask iniciando en el puerto {port}...")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )


def start_web_server(bot=None) -> None:
    """
    Inicia el servidor Flask en un hilo daemon separado.

    Args:
        bot: Referencia al bot de Discord para inyectar en los endpoints.
    """
    if bot is not None:
        set_bot(bot)

    thread = Thread(target=_run_flask, name="flask-server", daemon=True)
    thread.start()
    logger.info("Servidor Flask iniciado en hilo separado.")

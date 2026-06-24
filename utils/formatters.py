"""
utils/formatters.py - Funciones de formateo para embeds y presentación de datos.

Centraliza la creación de embeds complejos para mantener consistencia
visual en todas las respuestas del bot.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import discord

import config

logger = logging.getLogger("ysl-bot.formatters")


def build_profile_embed(
    user_data: dict[str, Any],
    player_data: dict[str, Any],
    member: discord.Member,
) -> discord.Embed:
    """
    Construye el embed del perfil de un jugador de Protox.io.

    Args:
        user_data: Datos del usuario almacenados en MongoDB.
        player_data: Datos del jugador obtenidos de la API de Protox.io.
        member: Miembro de Discord.

    Returns:
        Embed de Discord con el perfil del jugador.
    """
    player_id = user_data.get("protox_player_id", "N/A")
    username = user_data.get("username") or player_data.get("name") or member.display_name

    xp = _extract_xp(player_data)
    rank = player_data.get("rank") or player_data.get("level") or "N/A"
    clan = player_data.get("clan") or player_data.get("clanName") or config.CLAN_NAME

    embed = discord.Embed(
        title=f"{config.EMOJI_PLAYER} Perfil de {username}",
        description=f"Miembro del clan **{clan}** en Protox.io",
        color=config.COLOR_PRIMARY,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(name="Discord", value=member.mention, inline=True)
    embed.add_field(name="Player ID", value=f"`{player_id}`", inline=True)
    embed.add_field(name=f"{config.EMOJI_XP} XP Total", value=f"**{xp:,}**", inline=True)

    if rank != "N/A":
        embed.add_field(name="Rango", value=f"**{rank}**", inline=True)

    embed.set_footer(text="Protox.io · Clan YSL", icon_url=member.guild.icon.url if member.guild.icon else None)
    return embed


def build_weekly_xp_embed(
    user_data: dict[str, Any],
    weekly_xp: int,
    current_xp: int,
    week_date: str,
    member: discord.Member,
) -> discord.Embed:
    """
    Construye el embed de XP semanal de un jugador.

    Args:
        user_data: Datos del usuario almacenados en MongoDB.
        weekly_xp: XP ganada durante la semana actual.
        current_xp: XP total actual del jugador.
        week_date: Cadena identificadora de la semana (e.g., "2026-W26").
        member: Miembro de Discord.

    Returns:
        Embed de Discord con la XP semanal.
    """
    username = user_data.get("username") or member.display_name
    requirement = config.WEEKLY_XP_REQUIREMENT

    if weekly_xp >= requirement:
        status_emoji = "✅"
        status_text = "Requisito cumplido"
        color = config.COLOR_SUCCESS
    elif weekly_xp >= requirement * 0.5:
        status_emoji = "⚠️"
        status_text = "En progreso"
        color = config.COLOR_WARNING
    else:
        status_emoji = "❌"
        status_text = "Requisito no cumplido"
        color = config.COLOR_ERROR

    progress_pct = min(100, int((weekly_xp / requirement) * 100)) if requirement > 0 else 0
    progress_bar = _build_progress_bar(progress_pct)

    embed = discord.Embed(
        title=f"{config.EMOJI_XP} XP Semanal · {username}",
        description=f"Semana: **{week_date}**",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(
        name="XP Esta Semana",
        value=f"**{weekly_xp:,}** XP",
        inline=True,
    )
    embed.add_field(
        name="Requisito Semanal",
        value=f"**{requirement:,}** XP",
        inline=True,
    )
    embed.add_field(
        name="XP Total Actual",
        value=f"**{current_xp:,}** XP",
        inline=True,
    )
    embed.add_field(
        name=f"Progreso ({progress_pct}%)",
        value=progress_bar,
        inline=False,
    )
    embed.add_field(
        name="Estado",
        value=f"{status_emoji} {status_text}",
        inline=False,
    )

    embed.set_footer(text="Protox.io · Clan YSL")
    return embed


def build_history_embed(
    user_data: dict[str, Any],
    snapshots: list[dict[str, Any]],
    member: discord.Member,
) -> discord.Embed:
    """
    Construye el embed del historial semanal de XP de un jugador.

    Args:
        user_data: Datos del usuario almacenados en MongoDB.
        snapshots: Lista de snapshots semanales ordenados por fecha descendente.
        member: Miembro de Discord.

    Returns:
        Embed de Discord con el historial de XP.
    """
    username = user_data.get("username") or member.display_name

    embed = discord.Embed(
        title=f"📊 Historial XP Semanal · {username}",
        description=f"Últimas **{len(snapshots)}** semanas registradas",
        color=config.COLOR_INFO,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    if not snapshots:
        embed.add_field(
            name="Sin datos",
            value="No hay snapshots registrados aún. El bot registra XP automáticamente cada domingo.",
            inline=False,
        )
    else:
        # Calcular XP semanal entre snapshots consecutivos
        history_lines = []
        for i, snap in enumerate(snapshots[:10]):  # Máximo 10 semanas
            week = snap.get("week_date", "N/A")
            total_xp = snap.get("total_xp", 0)

            if i + 1 < len(snapshots):
                prev_xp = snapshots[i + 1].get("total_xp", 0)
                weekly_gained = total_xp - prev_xp
                gained_str = f"+{weekly_gained:,}" if weekly_gained >= 0 else f"{weekly_gained:,}"
            else:
                gained_str = "—"

            req = config.WEEKLY_XP_REQUIREMENT
            if i + 1 < len(snapshots):
                weekly_gained_val = total_xp - snapshots[i + 1].get("total_xp", 0)
                status = "✅" if weekly_gained_val >= req else "❌"
            else:
                status = "📌"

            history_lines.append(f"{status} **{week}** · {gained_str} XP (Total: {total_xp:,})")

        embed.add_field(
            name="Historial",
            value="\n".join(history_lines),
            inline=False,
        )

    embed.set_footer(text="Protox.io · Clan YSL")
    return embed


def build_mod_log_embed(
    action: str,
    target: discord.Member,
    moderator: discord.Member,
    reason: str,
    duration: Optional[str] = None,
    color: int = config.COLOR_WARNING,
) -> discord.Embed:
    """
    Construye el embed de log de moderación.

    Args:
        action: Tipo de acción (ban, kick, warn, mute, etc.).
        target: Miembro afectado por la acción.
        moderator: Moderador que ejecutó la acción.
        reason: Razón de la acción.
        duration: Duración opcional (para mutes/timeouts).
        color: Color del embed.

    Returns:
        Embed de Discord para el canal de logs de moderación.
    """
    action_emojis = {
        "ban": "🔨",
        "unban": "🔓",
        "kick": "👢",
        "warn": "⚠️",
        "mute": "🔇",
        "unmute": "🔊",
        "purge": "🧹",
    }
    emoji = action_emojis.get(action.lower(), "🛡️")

    embed = discord.Embed(
        title=f"{emoji} Acción de Moderación: {action.upper()}",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Usuario", value=f"{target.mention} (`{target.id}`)", inline=True)
    embed.add_field(name="Moderador", value=f"{moderator.mention}", inline=True)
    embed.add_field(name="Razón", value=reason or "Sin razón especificada", inline=False)

    if duration:
        embed.add_field(name="Duración", value=duration, inline=True)

    embed.set_footer(text=f"ID del usuario: {target.id}")
    return embed


# ============================================================
# Funciones auxiliares internas
# ============================================================

def _extract_xp(player_data: dict[str, Any]) -> int:
    """Extrae el XP total de los datos del jugador."""
    for key in ("xp", "experience", "totalXp", "total_xp", "allScores", "scores", "points"):
        value = player_data.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    return 0


def _build_progress_bar(percentage: int, length: int = 20) -> str:
    """
    Construye una barra de progreso visual con bloques Unicode.

    Args:
        percentage: Porcentaje de progreso (0-100).
        length: Longitud total de la barra en caracteres.

    Returns:
        Cadena con la barra de progreso.
    """
    filled = int(length * percentage / 100)
    bar = "█" * filled + "░" * (length - filled)
    return f"`{bar}` {percentage}%"

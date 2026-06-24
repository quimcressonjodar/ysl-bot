"""
utils/helpers.py - Funciones auxiliares reutilizables en todo el bot.

Incluye verificaciones de permisos, parseo de duraciones,
formateo de fechas y otras utilidades comunes.
"""

import logging
from datetime import timedelta, datetime, timezone
from typing import Optional

import discord
from discord.ext import commands

logger = logging.getLogger("ysl-bot.helpers")


# ============================================================
# Verificación de permisos
# ============================================================

def is_admin(ctx: commands.Context) -> bool:
    """
    Verifica si el autor del contexto tiene permisos de administrador.

    Args:
        ctx: Contexto del comando de discord.py.

    Returns:
        True si el autor es administrador, False en caso contrario.
    """
    if isinstance(ctx.author, discord.Member):
        return bool(ctx.author.guild_permissions.administrator)
    return False


def is_moderator(ctx: commands.Context) -> bool:
    """
    Verifica si el autor del contexto tiene permisos de moderación.
    Considera como moderador a quien tenga ban_members o manage_messages.

    Args:
        ctx: Contexto del comando de discord.py.

    Returns:
        True si el autor puede moderar, False en caso contrario.
    """
    if isinstance(ctx.author, discord.Member):
        perms = ctx.author.guild_permissions
        return bool(
            perms.administrator
            or perms.ban_members
            or perms.kick_members
            or perms.manage_messages
        )
    return False


def is_admin_interaction(interaction: discord.Interaction) -> bool:
    """
    Verifica si el usuario de una Interaction tiene permisos de administrador.

    Args:
        interaction: Interacción de Discord.

    Returns:
        True si el usuario es administrador, False en caso contrario.
    """
    if isinstance(interaction.user, discord.Member):
        return bool(interaction.user.guild_permissions.administrator)
    return False


def is_moderator_interaction(interaction: discord.Interaction) -> bool:
    """
    Verifica si el usuario de una Interaction tiene permisos de moderación.

    Args:
        interaction: Interacción de Discord.

    Returns:
        True si el usuario puede moderar, False en caso contrario.
    """
    if isinstance(interaction.user, discord.Member):
        perms = interaction.user.guild_permissions
        return bool(
            perms.administrator
            or perms.ban_members
            or perms.kick_members
            or perms.manage_messages
        )
    return False


# ============================================================
# Parseo de duraciones
# ============================================================

def parse_duration(duration_str: str) -> Optional[timedelta]:
    """
    Parsea una cadena de duración en un objeto timedelta.

    Formatos soportados:
        - ``30s`` → 30 segundos
        - ``10m`` → 10 minutos
        - ``2h``  → 2 horas
        - ``1d``  → 1 día
        - ``7d``  → 7 días

    Args:
        duration_str: Cadena de duración (e.g., "10m", "2h", "1d").

    Returns:
        timedelta si el formato es válido, None en caso contrario.
    """
    try:
        duration_str = duration_str.strip().lower()
        if duration_str.endswith("s"):
            return timedelta(seconds=int(duration_str[:-1]))
        elif duration_str.endswith("m"):
            return timedelta(minutes=int(duration_str[:-1]))
        elif duration_str.endswith("h"):
            return timedelta(hours=int(duration_str[:-1]))
        elif duration_str.endswith("d"):
            return timedelta(days=int(duration_str[:-1]))
        else:
            return timedelta(minutes=int(duration_str))
    except (ValueError, IndexError):
        return None


def format_duration(td: timedelta) -> str:
    """
    Formatea un timedelta en una cadena legible.

    Args:
        td: Objeto timedelta a formatear.

    Returns:
        Cadena legible (e.g., "2h 30m", "1d 4h").
    """
    total_seconds = int(td.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds and not days:
        parts.append(f"{seconds}s")

    return " ".join(parts) if parts else "0s"


# ============================================================
# Formateo de números y fechas
# ============================================================

def format_xp(xp: int) -> str:
    """
    Formatea un valor de XP con separadores de miles.

    Args:
        xp: Valor de XP entero.

    Returns:
        Cadena formateada (e.g., "1,234,567").
    """
    return f"{xp:,}"


def format_date(dt: datetime) -> str:
    """
    Formatea una fecha en formato legible.

    Args:
        dt: Objeto datetime.

    Returns:
        Cadena de fecha (e.g., "24/06/2026 14:30 UTC").
    """
    return dt.strftime("%d/%m/%Y %H:%M UTC")


def utcnow() -> datetime:
    """Devuelve la fecha y hora actual en UTC."""
    return datetime.now(timezone.utc)


def get_week_date_str(dt: Optional[datetime] = None) -> str:
    """
    Devuelve la cadena de la semana actual en formato ISO (YYYY-WXX).

    Args:
        dt: Fecha base. Si es None, usa la fecha actual en UTC.

    Returns:
        Cadena de semana (e.g., "2026-W26").
    """
    if dt is None:
        dt = utcnow()
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


# ============================================================
# Utilidades de embeds
# ============================================================

def error_embed(description: str, title: str = "Error") -> discord.Embed:
    """
    Crea un embed de error estándar.

    Args:
        description: Descripción del error.
        title: Título del embed.

    Returns:
        Embed de Discord con estilo de error.
    """
    return discord.Embed(
        title=f"❌ {title}",
        description=description,
        color=0xED4245,
        timestamp=utcnow(),
    )


def success_embed(description: str, title: str = "Éxito") -> discord.Embed:
    """
    Crea un embed de éxito estándar.

    Args:
        description: Descripción del éxito.
        title: Título del embed.

    Returns:
        Embed de Discord con estilo de éxito.
    """
    return discord.Embed(
        title=f"✅ {title}",
        description=description,
        color=0x57F287,
        timestamp=utcnow(),
    )


def info_embed(description: str, title: str = "Información") -> discord.Embed:
    """
    Crea un embed informativo estándar.

    Args:
        description: Descripción informativa.
        title: Título del embed.

    Returns:
        Embed de Discord con estilo informativo.
    """
    return discord.Embed(
        title=f"ℹ️ {title}",
        description=description,
        color=0x5865F2,
        timestamp=utcnow(),
    )

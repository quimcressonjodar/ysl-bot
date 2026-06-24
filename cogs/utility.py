"""
cogs/utility.py - Comandos de utilidad general para el clan YSL de Protox.io.

Incluye: help, userinfo, serverinfo, avatar, ping, estadísticas del servidor.
"""

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.helpers import utcnow, format_date

logger = logging.getLogger("ysl-bot.utility")


class UtilityCog(commands.Cog, name="Utility"):
    """Cog de utilidades generales para el clan YSL de Protox.io."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        logger.info("UtilityCog cargado correctamente.")

    # ============================================================
    # /help
    # ============================================================

    @app_commands.command(name="help", description="Ver todos los comandos disponibles del bot")
    async def help_command(self, interaction: discord.Interaction) -> None:
        """Muestra la lista completa de comandos del bot."""
        embed = discord.Embed(
            title=f"🏆 Bot del Clan YSL · Protox.io",
            description=(
                "Bot oficial del clan **YSL** de Protox.io.\n"
                "Todos los comandos son slash commands (`/`)."
            ),
            color=config.COLOR_PRIMARY,
            timestamp=utcnow(),
        )

        # Protox.io
        protox_cmds = (
            "**`/register`** — Vincular tu cuenta de Protox.io.\n"
            "**`/profile`** — Ver tu perfil de Protox.io.\n"
            "**`/weeklyxp`** — Ver tu XP ganada esta semana.\n"
            "**`/history`** — Ver tu historial semanal de XP.\n"
            "**`/leaderboard`** — Ranking semanal del clan."
        )
        embed.add_field(name="🎮 Protox.io", value=protox_cmds, inline=False)

        # Utilidades
        utility_cmds = (
            "**`/help`** — Mostrar este mensaje.\n"
            "**`/userinfo`** — Ver información de un miembro.\n"
            "**`/serverinfo`** — Ver información del servidor.\n"
            "**`/avatar`** — Ver el avatar de un miembro.\n"
            "**`/ping`** — Ver la latencia del bot.\n"
            "**`/stats`** — Estadísticas del servidor."
        )
        embed.add_field(name="🔧 Utilidades", value=utility_cmds, inline=False)

        # Tickets
        ticket_cmds = (
            "**`/ticketsetup`** — [Admin] Configurar el panel de tickets.\n"
            "**`/ticketslist`** — [Mod] Ver tickets abiertos."
        )
        embed.add_field(name="🎫 Tickets", value=ticket_cmds, inline=False)

        # Moderación
        mod_cmds = (
            "**`/warn`** — Advertir a un miembro.\n"
            "**`/mute`** — Silenciar a un miembro.\n"
            "**`/unmute`** — Quitar el silenciamiento.\n"
            "**`/kick`** — Expulsar a un miembro.\n"
            "**`/ban`** — Banear a un miembro.\n"
            "**`/unban`** — Desbanear a un usuario.\n"
            "**`/purge`** — Eliminar mensajes.\n"
            "**`/report`** — Reportar a un usuario."
        )
        embed.add_field(name="🛡️ Moderación", value=mod_cmds, inline=False)

        # Administración
        admin_cmds = (
            "**`/setwelcome`** — Configurar canal de bienvenida.\n"
            "**`/setlog`** — Configurar canal de logs.\n"
            "**`/setapi`** — Configurar URL de la API.\n"
            "**`/memberinfo`** — Información avanzada de un miembro.\n"
            "**`/lock`** / **`/unlock`** — Bloquear/desbloquear canal.\n"
            "**`/slowmode`** — Configurar modo lento.\n"
            "**`/setnick`** — Cambiar apodo de un miembro.\n"
            "**`/role_add`** / **`/role_remove`** — Gestionar roles.\n"
            "**`/say`** / **`/sayembed`** — Enviar mensajes como el bot.\n"
            "**`/snapshot`** — [Admin] Forzar snapshot de XP."
        )
        embed.add_field(name="👑 Administración", value=admin_cmds, inline=False)

        embed.set_footer(
            text="Clan YSL · Protox.io",
            icon_url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============================================================
    # /userinfo
    # ============================================================

    @app_commands.command(
        name="userinfo",
        description="Ver información detallada de un miembro del servidor",
    )
    @app_commands.describe(member="El miembro a consultar (por defecto, tú mismo)")
    async def userinfo(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        """Muestra información detallada de un miembro del servidor."""
        target = member or interaction.user
        if not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id) or target

        roles = [r.mention for r in target.roles[1:]] if isinstance(target, discord.Member) else []

        embed = discord.Embed(
            title=f"👤 Información de {target.display_name}",
            color=config.COLOR_PRIMARY,
            timestamp=utcnow(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(name="Usuario", value=str(target), inline=True)
        embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
        embed.add_field(name="Bot", value="Sí" if target.bot else "No", inline=True)

        embed.add_field(
            name="Cuenta creada",
            value=format_date(target.created_at),
            inline=True,
        )

        if isinstance(target, discord.Member) and target.joined_at:
            embed.add_field(
                name="Se unió al servidor",
                value=format_date(target.joined_at),
                inline=True,
            )

        if isinstance(target, discord.Member) and target.premium_since:
            embed.add_field(
                name="Boost activo desde",
                value=format_date(target.premium_since),
                inline=True,
            )

        if roles:
            embed.add_field(
                name=f"Roles ({len(roles)})",
                value=" ".join(roles[:10]) + (" ..." if len(roles) > 10 else ""),
                inline=False,
            )

        embed.set_footer(text=f"Clan YSL · Protox.io | ID: {target.id}")
        await interaction.response.send_message(embed=embed)

    # ============================================================
    # /serverinfo
    # ============================================================

    @app_commands.command(
        name="serverinfo",
        description="Ver información general del servidor",
    )
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        """Muestra información general del servidor de Discord."""
        guild = interaction.guild

        embed = discord.Embed(
            title=f"🏰 {guild.name}",
            description=guild.description or "Servidor del Clan YSL de Protox.io",
            color=config.COLOR_PRIMARY,
            timestamp=utcnow(),
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)

        embed.add_field(
            name="Propietario",
            value=guild.owner.mention if guild.owner else "Desconocido",
            inline=True,
        )
        embed.add_field(
            name="Miembros",
            value=f"👥 {guild.member_count:,}",
            inline=True,
        )
        embed.add_field(
            name="Creado",
            value=format_date(guild.created_at),
            inline=True,
        )
        embed.add_field(
            name="Canales",
            value=(
                f"📝 {len(guild.text_channels)} texto\n"
                f"🔊 {len(guild.voice_channels)} voz\n"
                f"📂 {len(guild.categories)} categorías"
            ),
            inline=True,
        )
        embed.add_field(
            name="Roles",
            value=f"🏷️ {len(guild.roles)}",
            inline=True,
        )
        embed.add_field(
            name="Boost",
            value=(
                f"✨ Nivel {guild.premium_tier}\n"
                f"({guild.premium_subscription_count} boosts)"
            ),
            inline=True,
        )

        embed.set_footer(text=f"ID del servidor: {guild.id}")
        await interaction.response.send_message(embed=embed)

    # ============================================================
    # /avatar
    # ============================================================

    @app_commands.command(
        name="avatar",
        description="Ver el avatar de un miembro en alta resolución",
    )
    @app_commands.describe(member="El miembro (por defecto, tú mismo)")
    async def avatar(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        """Muestra el avatar de un miembro en alta resolución."""
        target = member or interaction.user

        embed = discord.Embed(
            title=f"🖼️ Avatar de {target.display_name}",
            color=config.COLOR_PRIMARY,
            timestamp=utcnow(),
        )
        embed.set_image(url=target.display_avatar.url)
        embed.set_footer(text="Clan YSL · Protox.io")

        await interaction.response.send_message(embed=embed)

    # ============================================================
    # /ping
    # ============================================================

    @app_commands.command(name="ping", description="Ver la latencia del bot")
    async def ping(self, interaction: discord.Interaction) -> None:
        """Muestra la latencia del bot en milisegundos."""
        latency_ms = round(self.bot.latency * 1000)

        if latency_ms < 100:
            color = config.COLOR_SUCCESS
            status = "Excelente"
        elif latency_ms < 200:
            color = config.COLOR_WARNING
            status = "Buena"
        else:
            color = config.COLOR_ERROR
            status = "Alta"

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"**Latencia:** `{latency_ms}ms` — {status}",
            color=color,
            timestamp=utcnow(),
        )
        embed.set_footer(text="Clan YSL · Protox.io")

        await interaction.response.send_message(embed=embed)

    # ============================================================
    # /stats
    # ============================================================

    @app_commands.command(
        name="stats",
        description="Ver estadísticas generales del bot y del clan YSL",
    )
    async def stats(self, interaction: discord.Interaction) -> None:
        """Muestra estadísticas generales del bot y el servidor."""
        from database import users_col, weekly_snapshots_col

        guild = interaction.guild

        # Estadísticas de la base de datos
        total_registered = users_col.count_documents({"guild_id": str(guild.id)})
        total_snapshots = weekly_snapshots_col.count_documents({})

        embed = discord.Embed(
            title=f"📊 Estadísticas · Clan YSL",
            color=config.COLOR_INFO,
            timestamp=utcnow(),
        )

        embed.add_field(
            name="Servidor",
            value=(
                f"👥 **{guild.member_count:,}** miembros\n"
                f"📝 **{len(guild.text_channels)}** canales de texto\n"
                f"🏷️ **{len(guild.roles)}** roles"
            ),
            inline=True,
        )
        embed.add_field(
            name="Protox.io",
            value=(
                f"🎮 **{total_registered}** jugadores registrados\n"
                f"📅 **{total_snapshots}** snapshots de XP\n"
                f"🏆 Clan: **{config.CLAN_NAME}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Bot",
            value=(
                f"⚡ Latencia: **{round(self.bot.latency * 1000)}ms**\n"
                f"🔧 Versión: **1.0.0**\n"
                f"🐍 discord.py"
            ),
            inline=True,
        )

        embed.set_footer(
            text="Clan YSL · Protox.io",
            icon_url=guild.icon.url if guild.icon else None,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Registra el cog en el bot."""
    await bot.add_cog(UtilityCog(bot))

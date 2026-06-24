"""
cogs/admin.py - Comandos de administración del servidor para el clan YSL.

Incluye: setwelcome, setlog, setapi, memberinfo, gestión de roles,
lock/unlock de canales, slowmode, setnick y comandos de utilidad admin.
"""

import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import guild_settings_col, warnings_col
from utils.helpers import (
    is_admin,
    is_admin_interaction,
    utcnow,
    format_date,
)

logger = logging.getLogger("ysl-bot.admin")


class AdminCog(commands.Cog, name="Admin"):
    """Cog de administración para el clan YSL de Protox.io."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        logger.info("AdminCog cargado correctamente.")

    # ============================================================
    # /setwelcome
    # ============================================================

    @app_commands.command(
        name="setwelcome",
        description="Configurar el canal de bienvenida del servidor",
    )
    @app_commands.describe(channel="Canal donde se enviarán los mensajes de bienvenida")
    @app_commands.default_permissions(administrator=True)
    async def setwelcome(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        """Configura el canal de bienvenida en la base de datos."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Solo los administradores pueden usar este comando.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        guild_settings_col.update_one(
            {"guild_id": str(interaction.guild_id)},
            {"$set": {"welcome_channel_id": str(channel.id)}},
            upsert=True,
        )

        embed = discord.Embed(
            title="✅ Canal de bienvenida configurado",
            description=f"Los mensajes de bienvenida y despedida se enviarán en {channel.mention}.",
            color=config.COLOR_SUCCESS,
            timestamp=utcnow(),
        )
        await interaction.response.send_message(embed=embed)
        logger.info(f"Canal de bienvenida configurado: #{channel.name} en {interaction.guild.name}")

    # ============================================================
    # /setlog
    # ============================================================

    @app_commands.command(
        name="setlog",
        description="Configurar el canal de logs de moderación",
    )
    @app_commands.describe(channel="Canal donde se enviarán los logs de moderación")
    @app_commands.default_permissions(administrator=True)
    async def setlog(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        """Configura el canal de logs de moderación en la base de datos."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Solo los administradores pueden usar este comando.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        guild_settings_col.update_one(
            {"guild_id": str(interaction.guild_id)},
            {"$set": {"log_channel_id": str(channel.id)}},
            upsert=True,
        )

        embed = discord.Embed(
            title="✅ Canal de logs configurado",
            description=f"Los logs de moderación se enviarán en {channel.mention}.",
            color=config.COLOR_SUCCESS,
            timestamp=utcnow(),
        )
        await interaction.response.send_message(embed=embed)
        logger.info(f"Canal de logs configurado: #{channel.name} en {interaction.guild.name}")

    # ============================================================
    # /setapi
    # ============================================================

    @app_commands.command(
        name="setapi",
        description="Configurar la URL base de la API de Protox.io para este servidor",
    )
    @app_commands.describe(api_base="URL base de la API de Protox.io (ej: https://api.protox.io)")
    @app_commands.default_permissions(administrator=True)
    async def setapi(
        self,
        interaction: discord.Interaction,
        api_base: str,
    ) -> None:
        """Configura la URL base de la API de Protox.io."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Solo los administradores pueden usar este comando.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        if not api_base.startswith("http"):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ La URL debe comenzar con `http://` o `https://`.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        guild_settings_col.update_one(
            {"guild_id": str(interaction.guild_id)},
            {"$set": {"protox_api_base": api_base.rstrip("/")}},
            upsert=True,
        )

        embed = discord.Embed(
            title="✅ API de Protox.io configurada",
            description=f"URL base configurada: `{api_base}`",
            color=config.COLOR_SUCCESS,
            timestamp=utcnow(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ============================================================
    # /memberinfo
    # ============================================================

    @app_commands.command(
        name="memberinfo",
        description="Ver información avanzada de un miembro del servidor",
    )
    @app_commands.describe(member="El miembro a consultar (por defecto, tú mismo)")
    @app_commands.default_permissions(moderate_members=True)
    async def memberinfo(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        """Muestra información detallada de un miembro del servidor."""
        target = member or interaction.user
        if not isinstance(target, discord.Member):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No se pudo obtener la información del miembro.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        # Obtener advertencias
        warn_doc = warnings_col.find_one({
            "guild_id": str(interaction.guild_id),
            "discord_id": str(target.id),
        })
        total_warns = len(warn_doc.get("warnings", [])) if warn_doc else 0

        # Roles del miembro
        roles = [r.mention for r in target.roles[1:]]  # Excluir @everyone

        embed = discord.Embed(
            title=f"👤 Información de {target.display_name}",
            color=config.COLOR_PRIMARY,
            timestamp=utcnow(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(name="Nombre de usuario", value=str(target), inline=True)
        embed.add_field(name="ID de Discord", value=f"`{target.id}`", inline=True)
        embed.add_field(name="Es bot", value="Sí" if target.bot else "No", inline=True)

        embed.add_field(
            name="Cuenta creada",
            value=format_date(target.created_at),
            inline=True,
        )
        embed.add_field(
            name="Se unió al servidor",
            value=format_date(target.joined_at) if target.joined_at else "Desconocido",
            inline=True,
        )
        embed.add_field(
            name="Advertencias",
            value=f"⚠️ {total_warns}",
            inline=True,
        )

        if target.premium_since:
            embed.add_field(
                name="Boost activo desde",
                value=format_date(target.premium_since),
                inline=True,
            )

        if target.timed_out_until:
            embed.add_field(
                name="Timeout hasta",
                value=format_date(target.timed_out_until),
                inline=True,
            )

        embed.add_field(
            name=f"Roles ({len(roles)})",
            value=" ".join(roles) if roles else "Sin roles",
            inline=False,
        )

        embed.set_footer(
            text=f"Consultado por {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )

        await interaction.response.send_message(embed=embed)

    # ============================================================
    # /lock
    # ============================================================

    @app_commands.command(name="lock", description="Bloquear un canal de texto")
    @app_commands.describe(channel="El canal a bloquear (por defecto, el canal actual)")
    @app_commands.default_permissions(manage_channels=True)
    async def lock(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Bloquea el envío de mensajes en un canal."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tienes permisos suficientes.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        target = channel or interaction.channel
        try:
            await target.set_permissions(interaction.guild.default_role, send_messages=False)
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"🔒 {target.mention} ha sido bloqueado.",
                    color=config.COLOR_WARNING,
                    timestamp=utcnow(),
                )
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tengo permisos para bloquear este canal.", color=config.COLOR_ERROR),
                ephemeral=True,
            )

    # ============================================================
    # /unlock
    # ============================================================

    @app_commands.command(name="unlock", description="Desbloquear un canal de texto")
    @app_commands.describe(channel="El canal a desbloquear (por defecto, el canal actual)")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Desbloquea el envío de mensajes en un canal."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tienes permisos suficientes.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        target = channel or interaction.channel
        try:
            await target.set_permissions(interaction.guild.default_role, send_messages=None)
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"🔓 {target.mention} ha sido desbloqueado.",
                    color=config.COLOR_SUCCESS,
                    timestamp=utcnow(),
                )
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tengo permisos para desbloquear este canal.", color=config.COLOR_ERROR),
                ephemeral=True,
            )

    # ============================================================
    # /slowmode
    # ============================================================

    @app_commands.command(name="slowmode", description="Configurar el modo lento de un canal")
    @app_commands.describe(
        seconds="Segundos de espera entre mensajes (0 para desactivar)",
        channel="El canal a configurar (por defecto, el canal actual)",
    )
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode(
        self,
        interaction: discord.Interaction,
        seconds: int,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Configura el modo lento de un canal."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tienes permisos suficientes.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        target = channel or interaction.channel
        seconds = max(0, min(21600, seconds))  # Discord limita a 6 horas

        try:
            await target.edit(slowmode_delay=seconds)
            if seconds == 0:
                msg = f"⏱️ Modo lento desactivado en {target.mention}."
            else:
                msg = f"⏱️ Modo lento configurado a **{seconds}s** en {target.mention}."
            await interaction.response.send_message(
                embed=discord.Embed(description=msg, color=config.COLOR_SUCCESS, timestamp=utcnow())
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tengo permisos para modificar este canal.", color=config.COLOR_ERROR),
                ephemeral=True,
            )

    # ============================================================
    # /setnick
    # ============================================================

    @app_commands.command(name="setnick", description="Cambiar el apodo de un miembro")
    @app_commands.describe(
        member="El miembro al que cambiar el apodo",
        nickname="Nuevo apodo (dejar vacío para restablecer)",
    )
    @app_commands.default_permissions(manage_nicknames=True)
    async def setnick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        nickname: str | None = None,
    ) -> None:
        """Cambia el apodo de un miembro del servidor."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tienes permisos suficientes.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        try:
            await member.edit(nick=nickname)
            if nickname:
                msg = f"✅ Apodo de **{member.name}** cambiado a `{nickname}`."
            else:
                msg = f"✅ Apodo de **{member.name}** restablecido."
            await interaction.response.send_message(
                embed=discord.Embed(description=msg, color=config.COLOR_SUCCESS, timestamp=utcnow())
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tengo permisos para cambiar el apodo de este miembro.", color=config.COLOR_ERROR),
                ephemeral=True,
            )

    # ============================================================
    # /role_add / /role_remove
    # ============================================================

    @app_commands.command(name="role_add", description="Asignar un rol a un miembro")
    @app_commands.describe(member="El miembro", role="El rol a asignar")
    @app_commands.default_permissions(manage_roles=True)
    async def role_add(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
    ) -> None:
        """Asigna un rol a un miembro del servidor."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tienes permisos suficientes.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        try:
            await member.add_roles(role)
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"✅ Rol {role.mention} asignado a {member.mention}.",
                    color=config.COLOR_SUCCESS,
                    timestamp=utcnow(),
                )
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tengo permisos para asignar este rol.", color=config.COLOR_ERROR),
                ephemeral=True,
            )

    @app_commands.command(name="role_remove", description="Quitar un rol a un miembro")
    @app_commands.describe(member="El miembro", role="El rol a quitar")
    @app_commands.default_permissions(manage_roles=True)
    async def role_remove(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
    ) -> None:
        """Quita un rol a un miembro del servidor."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tienes permisos suficientes.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        try:
            await member.remove_roles(role)
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"✅ Rol {role.mention} quitado a {member.mention}.",
                    color=config.COLOR_SUCCESS,
                    timestamp=utcnow(),
                )
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tengo permisos para quitar este rol.", color=config.COLOR_ERROR),
                ephemeral=True,
            )

    # ============================================================
    # /say / /sayembed
    # ============================================================

    @app_commands.command(name="say", description="Hacer que el bot envíe un mensaje en un canal")
    @app_commands.describe(
        message="El mensaje a enviar",
        channel="Canal destino (por defecto, el canal actual)",
    )
    @app_commands.default_permissions(administrator=True)
    async def say(
        self,
        interaction: discord.Interaction,
        message: str,
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Envía un mensaje como el bot en el canal especificado."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Solo los administradores pueden usar este comando.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        target = channel or interaction.channel
        try:
            await target.send(message)
            await interaction.response.send_message(
                embed=discord.Embed(description=f"✅ Mensaje enviado en {target.mention}.", color=config.COLOR_SUCCESS),
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tengo permisos para enviar mensajes en ese canal.", color=config.COLOR_ERROR),
                ephemeral=True,
            )

    @app_commands.command(name="sayembed", description="Enviar un embed personalizado en un canal")
    @app_commands.describe(
        title="Título del embed",
        description="Descripción del embed",
        color_hex="Color en hexadecimal (ej: FF5733, por defecto azul)",
        channel="Canal destino (por defecto, el canal actual)",
    )
    @app_commands.default_permissions(administrator=True)
    async def sayembed(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        color_hex: str = "5865F2",
        channel: discord.TextChannel | None = None,
    ) -> None:
        """Envía un embed personalizado en el canal especificado."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Solo los administradores pueden usar este comando.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        try:
            color = int(color_hex.lstrip("#"), 16)
        except ValueError:
            color = config.COLOR_PRIMARY

        target = channel or interaction.channel
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=utcnow(),
        )
        embed.set_footer(text="Clan YSL · Protox.io")

        try:
            await target.send(embed=embed)
            await interaction.response.send_message(
                embed=discord.Embed(description=f"✅ Embed enviado en {target.mention}.", color=config.COLOR_SUCCESS),
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tengo permisos para enviar mensajes en ese canal.", color=config.COLOR_ERROR),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    """Registra el cog en el bot."""
    await bot.add_cog(AdminCog(bot))

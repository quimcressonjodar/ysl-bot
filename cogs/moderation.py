"""
cogs/moderation.py - Comandos de moderación para el clan YSL de Protox.io.

Incluye: warn, mute, unmute, kick, ban, unban, purge, report.
Todos los comandos son slash commands con permisos de moderador/admin.
"""

import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import warnings_col, guild_settings_col, events_col
from utils.helpers import (
    is_moderator,
    is_moderator_interaction,
    parse_duration,
    format_duration,
    utcnow,
)

logger = logging.getLogger("ysl-bot.moderation")


class ModerationCog(commands.Cog, name="Moderation"):
    """Cog de moderación para el clan YSL de Protox.io."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        logger.info("ModerationCog cargado correctamente.")

    # ============================================================
    # Métodos auxiliares
    # ============================================================

    async def _send_mod_log(
        self,
        guild: discord.Guild,
        embed: discord.Embed,
    ) -> None:
        """Envía un embed al canal de logs de moderación."""
        doc = guild_settings_col.find_one({"guild_id": str(guild.id)})
        if doc and doc.get("log_channel_id"):
            channel = guild.get_channel(int(doc["log_channel_id"]))
            if isinstance(channel, discord.TextChannel):
                try:
                    await channel.send(embed=embed)
                except Exception as e:
                    logger.warning(f"No se pudo enviar log de moderación: {e}")

    def _build_mod_embed(
        self,
        action: str,
        target: discord.Member | discord.User,
        moderator: discord.Member,
        reason: str,
        color: int,
        duration: str | None = None,
    ) -> discord.Embed:
        """Construye un embed estándar para acciones de moderación."""
        action_emojis = {
            "ban": "🔨",
            "unban": "🔓",
            "kick": "👢",
            "warn": "⚠️",
            "mute": "🔇",
            "unmute": "🔊",
            "purge": "🧹",
            "report": "📢",
        }
        emoji = action_emojis.get(action.lower(), "🛡️")

        embed = discord.Embed(
            title=f"{emoji} {action.upper()} · Clan YSL",
            color=color,
            timestamp=utcnow(),
        )
        embed.add_field(
            name="Usuario",
            value=f"{target.mention} (`{target.id}`)",
            inline=True,
        )
        embed.add_field(name="Moderador", value=moderator.mention, inline=True)
        embed.add_field(
            name="Razón",
            value=reason or "Sin razón especificada",
            inline=False,
        )
        if duration:
            embed.add_field(name="Duración", value=duration, inline=True)
        embed.set_footer(text=f"ID: {target.id}")
        return embed

    def _log_mod_action(
        self,
        guild_id: str,
        action: str,
        target_id: str,
        moderator_id: str,
        reason: str,
        extra: dict | None = None,
    ) -> None:
        """Registra una acción de moderación en MongoDB."""
        try:
            events_col.insert_one({
                "guild_id": guild_id,
                "event_type": f"mod_{action}",
                "target_id": target_id,
                "moderator_id": moderator_id,
                "reason": reason,
                "timestamp": utcnow().isoformat(),
                **(extra or {}),
            })
        except Exception as e:
            logger.warning(f"No se pudo registrar acción de moderación '{action}': {e}")

    # ============================================================
    # /warn
    # ============================================================

    @app_commands.command(name="warn", description="Emitir una advertencia a un miembro del servidor")
    @app_commands.describe(
        member="El miembro a advertir",
        reason="Razón de la advertencia",
    )
    @app_commands.default_permissions(moderate_members=True)
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ) -> None:
        """Emite una advertencia a un miembro y la registra en MongoDB."""
        if not is_moderator_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tienes permisos de moderación.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        if member.bot:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No puedes advertir a un bot.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        # Registrar advertencia en MongoDB
        warn_doc = {
            "reason": reason,
            "moderator_id": str(interaction.user.id),
            "moderator_name": str(interaction.user),
            "timestamp": utcnow().isoformat(),
        }
        warnings_col.update_one(
            {"guild_id": str(interaction.guild_id), "discord_id": str(member.id)},
            {"$push": {"warnings": warn_doc}},
            upsert=True,
        )

        # Contar advertencias totales
        doc = warnings_col.find_one({
            "guild_id": str(interaction.guild_id),
            "discord_id": str(member.id),
        })
        total_warns = len(doc.get("warnings", [])) if doc else 1

        # Notificar al usuario
        try:
            await member.send(
                embed=discord.Embed(
                    title=f"⚠️ Has recibido una advertencia en **{interaction.guild.name}**",
                    description=(
                        f"**Razón:** {reason}\n"
                        f"*Tienes un total de {total_warns} advertencia(s).*"
                    ),
                    color=config.COLOR_WARNING,
                    timestamp=utcnow(),
                )
            )
        except discord.Forbidden:
            pass

        embed = self._build_mod_embed(
            action="warn",
            target=member,
            moderator=interaction.user,
            reason=reason,
            color=config.COLOR_WARNING,
        )
        embed.add_field(name="Total advertencias", value=str(total_warns), inline=True)

        await interaction.response.send_message(embed=embed)
        await self._send_mod_log(interaction.guild, embed)
        self._log_mod_action(
            str(interaction.guild_id), "warn",
            str(member.id), str(interaction.user.id), reason,
        )

    # ============================================================
    # /mute
    # ============================================================

    @app_commands.command(name="mute", description="Silenciar (timeout) a un miembro temporalmente")
    @app_commands.describe(
        member="El miembro a silenciar",
        duration="Duración (ej: 10m, 2h, 1d)",
        reason="Razón del silenciamiento",
    )
    @app_commands.default_permissions(moderate_members=True)
    async def mute(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: str,
        reason: str = "Sin razón especificada",
    ) -> None:
        """Aplica un timeout a un miembro por la duración especificada."""
        if not is_moderator_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tienes permisos de moderación.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        time_delta = parse_duration(duration)
        if not time_delta:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=(
                        "❌ Formato de duración inválido.\n"
                        "Usa: `10s`, `5m`, `2h`, `1d`"
                    ),
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        try:
            await member.send(
                embed=discord.Embed(
                    title=f"🔇 Has sido silenciado en **{interaction.guild.name}**",
                    description=f"**Duración:** {format_duration(time_delta)}\n**Razón:** {reason}",
                    color=config.COLOR_WARNING,
                    timestamp=utcnow(),
                )
            )
        except discord.Forbidden:
            pass

        try:
            await member.timeout(time_delta, reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ No tengo permisos para silenciar a este miembro.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        duration_str = format_duration(time_delta)
        embed = self._build_mod_embed(
            action="mute",
            target=member,
            moderator=interaction.user,
            reason=reason,
            color=config.COLOR_WARNING,
            duration=duration_str,
        )
        await interaction.response.send_message(embed=embed)
        await self._send_mod_log(interaction.guild, embed)
        self._log_mod_action(
            str(interaction.guild_id), "mute",
            str(member.id), str(interaction.user.id), reason,
            {"duration": duration_str},
        )

    # ============================================================
    # /unmute
    # ============================================================

    @app_commands.command(name="unmute", description="Quitar el silenciamiento a un miembro")
    @app_commands.describe(member="El miembro al que quitar el silenciamiento")
    @app_commands.default_permissions(moderate_members=True)
    async def unmute(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        """Elimina el timeout activo de un miembro."""
        if not is_moderator_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tienes permisos de moderación.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        try:
            await member.timeout(None, reason=f"Timeout eliminado por {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ No tengo permisos para quitar el silenciamiento.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        embed = self._build_mod_embed(
            action="unmute",
            target=member,
            moderator=interaction.user,
            reason="Timeout eliminado manualmente",
            color=config.COLOR_SUCCESS,
        )
        await interaction.response.send_message(embed=embed)
        await self._send_mod_log(interaction.guild, embed)

    # ============================================================
    # /kick
    # ============================================================

    @app_commands.command(name="kick", description="Expulsar a un miembro del servidor")
    @app_commands.describe(
        member="El miembro a expulsar",
        reason="Razón de la expulsión",
    )
    @app_commands.default_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "Sin razón especificada",
    ) -> None:
        """Expulsa a un miembro del servidor."""
        if not is_moderator_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tienes permisos suficientes.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        try:
            await member.send(
                embed=discord.Embed(
                    title=f"👢 Has sido expulsado de **{interaction.guild.name}**",
                    description=f"**Razón:** {reason}",
                    color=config.COLOR_ERROR,
                    timestamp=utcnow(),
                )
            )
        except discord.Forbidden:
            pass

        try:
            await member.kick(reason=reason)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ No tengo permisos para expulsar a este miembro.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        embed = self._build_mod_embed(
            action="kick",
            target=member,
            moderator=interaction.user,
            reason=reason,
            color=config.COLOR_ERROR,
        )
        await interaction.response.send_message(embed=embed)
        await self._send_mod_log(interaction.guild, embed)
        self._log_mod_action(
            str(interaction.guild_id), "kick",
            str(member.id), str(interaction.user.id), reason,
        )

    # ============================================================
    # /ban
    # ============================================================

    @app_commands.command(name="ban", description="Banear permanentemente a un miembro del servidor")
    @app_commands.describe(
        member="El miembro a banear",
        reason="Razón del baneo",
        delete_days="Días de mensajes a eliminar (0-7)",
    )
    @app_commands.default_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "Sin razón especificada",
        delete_days: int = 0,
    ) -> None:
        """Banea permanentemente a un miembro del servidor."""
        if not is_moderator_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tienes permisos suficientes.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        delete_days = max(0, min(7, delete_days))

        try:
            await member.send(
                embed=discord.Embed(
                    title=f"🔨 Has sido baneado de **{interaction.guild.name}**",
                    description=f"**Razón:** {reason}",
                    color=config.COLOR_ERROR,
                    timestamp=utcnow(),
                )
            )
        except discord.Forbidden:
            pass

        try:
            await member.ban(reason=reason, delete_message_days=delete_days)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ No tengo permisos para banear a este miembro.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        embed = self._build_mod_embed(
            action="ban",
            target=member,
            moderator=interaction.user,
            reason=reason,
            color=config.COLOR_ERROR,
        )
        await interaction.response.send_message(embed=embed)
        await self._send_mod_log(interaction.guild, embed)
        self._log_mod_action(
            str(interaction.guild_id), "ban",
            str(member.id), str(interaction.user.id), reason,
        )

    # ============================================================
    # /unban
    # ============================================================

    @app_commands.command(name="unban", description="Desbanear a un usuario por su ID de Discord")
    @app_commands.describe(
        user_id="ID de Discord del usuario a desbanear",
        reason="Razón del desbaneo",
    )
    @app_commands.default_permissions(ban_members=True)
    async def unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str = "Sin razón especificada",
    ) -> None:
        """Desbanea a un usuario del servidor por su ID."""
        if not is_moderator_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tienes permisos suficientes.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=reason)
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ ID de usuario inválido.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return
        except discord.NotFound:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ Usuario no encontrado o no está baneado.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ No tengo permisos para desbanear usuarios.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🔓 UNBAN · Clan YSL",
            description=f"**{user}** (`{user.id}`) ha sido desbaneado.",
            color=config.COLOR_SUCCESS,
            timestamp=utcnow(),
        )
        embed.add_field(name="Moderador", value=interaction.user.mention, inline=True)
        embed.add_field(name="Razón", value=reason, inline=True)

        await interaction.response.send_message(embed=embed)
        await self._send_mod_log(interaction.guild, embed)

    # ============================================================
    # /purge
    # ============================================================

    @app_commands.command(name="purge", description="Eliminar un número de mensajes del canal actual")
    @app_commands.describe(amount="Número de mensajes a eliminar (1-100)")
    @app_commands.default_permissions(manage_messages=True)
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: int,
    ) -> None:
        """Elimina mensajes del canal actual."""
        if not is_moderator_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No tienes permisos suficientes.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        if amount <= 0 or amount > 100:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ El número de mensajes debe estar entre 1 y 100.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await interaction.channel.purge(limit=amount)
            count = len(deleted)
        except discord.Forbidden:
            await interaction.followup.send(
                embed=discord.Embed(
                    description="❌ No tengo permisos para eliminar mensajes en este canal.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            embed=discord.Embed(
                description=f"🧹 Se han eliminado **{count}** mensajes correctamente.",
                color=config.COLOR_SUCCESS,
            ),
            ephemeral=True,
        )

        # Log de moderación
        log_embed = discord.Embed(
            title="🧹 PURGE · Clan YSL",
            description=f"**{count}** mensajes eliminados en {interaction.channel.mention}",
            color=config.COLOR_WARNING,
            timestamp=utcnow(),
        )
        log_embed.add_field(name="Moderador", value=interaction.user.mention, inline=True)
        await self._send_mod_log(interaction.guild, log_embed)

    # ============================================================
    # /report
    # ============================================================

    @app_commands.command(name="report", description="Reportar a un usuario al equipo de moderación")
    @app_commands.describe(
        member="El miembro a reportar",
        reason="Razón del reporte",
    )
    async def report(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ) -> None:
        """Envía un reporte de usuario al canal de logs de moderación."""
        if member.id == interaction.user.id:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No puedes reportarte a ti mismo.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        if member.bot:
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ No puedes reportar a un bot.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        # Confirmar al reportador
        await interaction.response.send_message(
            embed=discord.Embed(
                title="📢 Reporte enviado",
                description=(
                    f"Tu reporte contra **{member.display_name}** ha sido enviado al equipo de moderación.\n"
                    f"**Razón:** {reason}"
                ),
                color=config.COLOR_INFO,
                timestamp=utcnow(),
            ),
            ephemeral=True,
        )

        # Enviar al canal de logs
        log_embed = discord.Embed(
            title="📢 NUEVO REPORTE · Clan YSL",
            color=config.COLOR_WARNING,
            timestamp=utcnow(),
        )
        log_embed.add_field(
            name="Usuario Reportado",
            value=f"{member.mention} (`{member.id}`)",
            inline=True,
        )
        log_embed.add_field(
            name="Reportado por",
            value=f"{interaction.user.mention} (`{interaction.user.id}`)",
            inline=True,
        )
        log_embed.add_field(name="Razón", value=reason, inline=False)
        log_embed.set_footer(text="Revisa el caso y toma las medidas necesarias.")

        await self._send_mod_log(interaction.guild, log_embed)

        # Registrar en MongoDB
        self._log_mod_action(
            str(interaction.guild_id), "report",
            str(member.id), str(interaction.user.id), reason,
        )


async def setup(bot: commands.Bot) -> None:
    """Registra el cog en el bot."""
    await bot.add_cog(ModerationCog(bot))

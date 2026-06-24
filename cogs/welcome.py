"""
cogs/welcome.py - Sistema de bienvenida y despedida del clan YSL.

Gestiona los eventos on_member_join y on_member_remove, enviando
mensajes personalizados en los canales configurados del servidor.
"""

import logging
import time
from datetime import datetime, timezone

import discord
from discord.ext import commands

import config
from database import guild_settings_col, events_col

logger = logging.getLogger("ysl-bot.welcome")


class WelcomeCog(commands.Cog, name="Welcome"):
    """Cog de bienvenida y despedida para el clan YSL de Protox.io."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Protección anti-duplicados: {(event, member_id): timestamp}
        self._recent_events: dict[tuple, float] = {}
        logger.info("WelcomeCog cargado correctamente.")

    # ============================================================
    # Métodos auxiliares
    # ============================================================

    def _should_process(self, event: str, member_id: int, cooldown: float = 5.0) -> bool:
        """Evita procesar el mismo evento dos veces en un corto periodo."""
        key = (event, member_id)
        now = time.monotonic()
        last = self._recent_events.get(key)
        if last and now - last < cooldown:
            return False
        self._recent_events[key] = now
        return True

    async def _get_channel(self, guild: discord.Guild, setting_key: str) -> discord.TextChannel | None:
        """
        Obtiene el canal configurado para un tipo de evento.

        Args:
            guild: Servidor de Discord.
            setting_key: Clave de configuración en guild_settings.

        Returns:
            Canal de texto si existe, None en caso contrario.
        """
        doc = guild_settings_col.find_one({"guild_id": str(guild.id)})
        if doc and doc.get(setting_key):
            channel = guild.get_channel(int(doc[setting_key]))
            if isinstance(channel, discord.TextChannel):
                return channel
        return None

    async def _log_event(
        self,
        guild_id: str,
        event_type: str,
        member: discord.Member,
        extra: dict | None = None,
    ) -> None:
        """Registra un evento en la colección de eventos de MongoDB."""
        try:
            events_col.insert_one({
                "guild_id": guild_id,
                "event_type": event_type,
                "member_id": str(member.id),
                "member_name": str(member),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **(extra or {}),
            })
        except Exception as e:
            logger.warning(f"No se pudo registrar el evento '{event_type}': {e}")

    # ============================================================
    # Eventos de Discord
    # ============================================================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Envía un mensaje de bienvenida cuando un miembro se une al servidor."""
        if member.bot:
            return
        if not self._should_process("join", member.id):
            return

        logger.info(f"Nuevo miembro: {member} ({member.id}) en {member.guild.name}")

        # Registrar evento en MongoDB
        await self._log_event(
            guild_id=str(member.guild.id),
            event_type="member_join",
            member=member,
        )

        # Obtener canal de bienvenida
        channel = await self._get_channel(member.guild, "welcome_channel_id")
        if not channel:
            logger.warning(
                f"Canal de bienvenida no configurado en {member.guild.name}. "
                "Usa /setwelcome para configurarlo."
            )
            return

        embed = discord.Embed(
            title=f"¡Bienvenido al clan YSL, {member.display_name}!",
            description=(
                f"Hola {member.mention}, ¡nos alegra tenerte aquí! 🎮\n\n"
                f"**Clan YSL · Protox.io**\n\n"
                f"📜 Lee las reglas del servidor antes de participar.\n"
                f"🏆 Vincula tu cuenta de Protox.io con `/register` para "
                f"aparecer en el seguimiento de XP semanal.\n\n"
                f"¡Buena suerte en el campo de batalla!"
            ),
            color=config.COLOR_PRIMARY,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(
            text=f"Miembro #{member.guild.member_count} · Protox.io",
            icon_url=member.guild.icon.url if member.guild.icon else None,
        )

        try:
            await channel.send(content=f"¡Bienvenido {member.mention}!", embed=embed)
        except discord.Forbidden:
            logger.error(f"Sin permisos para enviar mensajes en #{channel.name}.")
        except Exception as e:
            logger.error(f"Error al enviar mensaje de bienvenida: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Envía un mensaje de despedida cuando un miembro abandona el servidor."""
        if member.bot:
            return
        if not self._should_process("leave", member.id):
            return

        logger.info(f"Miembro salió: {member} ({member.id}) de {member.guild.name}")

        # Registrar evento en MongoDB
        await self._log_event(
            guild_id=str(member.guild.id),
            event_type="member_leave",
            member=member,
        )

        # Obtener canal de logs (o welcome si no hay log separado)
        channel = await self._get_channel(member.guild, "log_channel_id")
        if not channel:
            channel = await self._get_channel(member.guild, "welcome_channel_id")
        if not channel:
            return

        embed = discord.Embed(
            title="Un miembro ha abandonado el servidor",
            description=(
                f"**{member.display_name}** (`{member.id}`) ha salido del clan YSL.\n"
                f"¡Hasta pronto!"
            ),
            color=config.COLOR_ERROR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Quedan {member.guild.member_count} miembros")

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.error(f"Sin permisos para enviar mensajes en #{channel.name}.")
        except Exception as e:
            logger.error(f"Error al enviar mensaje de despedida: {e}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Maneja errores de comandos de forma global."""
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                embed=discord.Embed(
                    description="❌ No tienes permisos para usar este comando.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(
                embed=discord.Embed(
                    description="❌ El bot no tiene los permisos necesarios para ejecutar esta acción.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
        else:
            logger.error(f"Error en comando '{ctx.command}': {error}", exc_info=error)


async def setup(bot: commands.Bot) -> None:
    """Registra el cog en el bot."""
    await bot.add_cog(WelcomeCog(bot))

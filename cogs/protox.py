"""
cogs/protox.py - Sistema de seguimiento de XP de Protox.io para el clan YSL.

Incluye:
- /register: Vincular cuenta Discord con jugador de Protox.io.
- /profile: Mostrar perfil del jugador.
- /weeklyxp: Mostrar XP ganada esta semana.
- /history: Ver historial semanal de XP.
- Task programada: Snapshot automático cada domingo a las 23:59 UTC.
"""

import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from database import users_col, weekly_snapshots_col
from utils.helpers import utcnow, get_week_date_str, is_admin_interaction
from utils.formatters import (
    build_profile_embed,
    build_weekly_xp_embed,
    build_history_embed,
)

logger = logging.getLogger("ysl-bot.protox")


class ProtoxCog(commands.Cog, name="Protox"):
    """Cog de seguimiento de XP de Protox.io para el clan YSL."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.weekly_snapshot_task.start()
        logger.info("ProtoxCog cargado correctamente.")

    def cog_unload(self) -> None:
        """Cancela las tareas al descargar el cog."""
        self.weekly_snapshot_task.cancel()

    # ============================================================
    # /register
    # ============================================================

    @app_commands.command(
        name="register",
        description="Vincular tu cuenta de Discord con tu jugador de Protox.io",
    )
    @app_commands.describe(
        player_id="Tu Player ID de Protox.io",
        username="Tu nombre de usuario en Protox.io",
    )
    async def register(
        self,
        interaction: discord.Interaction,
        player_id: str,
        username: str,
    ) -> None:
        """
        Vincula la cuenta de Discord del usuario con su jugador de Protox.io.

        El Player ID y el username se almacenan en MongoDB para el
        seguimiento de XP semanal.
        """
        await interaction.response.defer(ephemeral=True)

        player_id = player_id.strip()
        username = username.strip()

        if not player_id:
            await interaction.followup.send(
                embed=discord.Embed(
                    description="❌ El Player ID no puede estar vacío.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        # Verificar si ya existe un registro con ese player_id (otro usuario)
        existing_player = users_col.find_one({
            "protox_player_id": player_id,
            "discord_id": {"$ne": str(interaction.user.id)},
        })
        if existing_player:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=(
                        f"❌ El Player ID `{player_id}` ya está vinculado a otra cuenta de Discord.\n"
                        "Si crees que es un error, contacta con un administrador."
                    ),
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        # Verificar si el jugador existe en la API de Protox.io
        player_data = {}
        try:
            player_data = await self.bot.protox_client.get_player(player_id)
        except Exception as e:
            logger.warning(f"No se pudo verificar el jugador {player_id} en la API: {e}")
            # Continuamos con el registro aunque la API falle

        # Guardar o actualizar en MongoDB
        users_col.update_one(
            {"discord_id": str(interaction.user.id)},
            {
                "$set": {
                    "discord_id": str(interaction.user.id),
                    "protox_player_id": player_id,
                    "username": username,
                    "registered_at": utcnow().isoformat(),
                    "guild_id": str(interaction.guild_id),
                }
            },
            upsert=True,
        )

        embed = discord.Embed(
            title=f"✅ Cuenta vinculada · Clan YSL",
            description=(
                f"Tu cuenta de Discord ha sido vinculada con éxito.\n\n"
                f"**Discord:** {interaction.user.mention}\n"
                f"**Player ID:** `{player_id}`\n"
                f"**Username:** `{username}`\n\n"
                f"Ahora aparecerás en el seguimiento de XP semanal del clan YSL. "
                f"Usa `/weeklyxp` para ver tu progreso."
            ),
            color=config.COLOR_SUCCESS,
            timestamp=utcnow(),
        )
        embed.set_footer(text="Protox.io · Clan YSL")

        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Usuario registrado: {interaction.user} → Player ID: {player_id}")

    # ============================================================
    # /profile
    # ============================================================

    @app_commands.command(
        name="profile",
        description="Ver el perfil de Protox.io de un miembro del clan",
    )
    @app_commands.describe(member="El miembro a consultar (por defecto, tú mismo)")
    async def profile(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        """Muestra el perfil de Protox.io de un miembro del clan."""
        await interaction.response.defer()

        target = member or interaction.user
        if not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id) or target

        # Buscar en MongoDB
        user_data = users_col.find_one({"discord_id": str(target.id)})
        if not user_data:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=(
                        f"❌ {target.mention} no tiene una cuenta de Protox.io vinculada.\n"
                        f"Usa `/register` para vincular tu cuenta."
                    ),
                    color=config.COLOR_ERROR,
                )
            )
            return

        # Obtener datos del jugador desde la API
        player_data = {}
        try:
            player_data = await self.bot.protox_client.get_player(
                user_data["protox_player_id"]
            )
        except Exception as e:
            logger.warning(f"No se pudo obtener datos de la API para {user_data['protox_player_id']}: {e}")

        embed = build_profile_embed(user_data, player_data, target)
        await interaction.followup.send(embed=embed)

    # ============================================================
    # /weeklyxp
    # ============================================================

    @app_commands.command(
        name="weeklyxp",
        description="Ver la XP ganada esta semana en Protox.io",
    )
    @app_commands.describe(member="El miembro a consultar (por defecto, tú mismo)")
    async def weeklyxp(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        """Muestra la XP ganada durante la semana actual."""
        await interaction.response.defer()

        target = member or interaction.user
        if not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id) or target

        # Buscar usuario en MongoDB
        user_data = users_col.find_one({"discord_id": str(target.id)})
        if not user_data:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=(
                        f"❌ {target.mention} no tiene una cuenta de Protox.io vinculada.\n"
                        f"Usa `/register` para vincular tu cuenta."
                    ),
                    color=config.COLOR_ERROR,
                )
            )
            return

        player_id = user_data["protox_player_id"]
        week_date = get_week_date_str()

        # Obtener XP actual desde la API
        current_xp = 0
        try:
            current_xp = await self.bot.protox_client.get_player_xp(player_id)
        except Exception as e:
            logger.warning(f"No se pudo obtener XP actual de {player_id}: {e}")

        # Obtener snapshot del domingo anterior
        prev_snapshot = weekly_snapshots_col.find_one(
            {"player_id": player_id},
            sort=[("week_date", -1)],
        )

        if prev_snapshot:
            weekly_xp = max(0, current_xp - prev_snapshot.get("total_xp", 0))
        else:
            weekly_xp = 0

        embed = build_weekly_xp_embed(
            user_data=user_data,
            weekly_xp=weekly_xp,
            current_xp=current_xp,
            week_date=week_date,
            member=target,
        )
        await interaction.followup.send(embed=embed)

    # ============================================================
    # /history
    # ============================================================

    @app_commands.command(
        name="history",
        description="Ver el historial semanal de XP en Protox.io",
    )
    @app_commands.describe(
        member="El miembro a consultar (por defecto, tú mismo)",
        weeks="Número de semanas a mostrar (máximo 10)",
    )
    async def history(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
        weeks: int = 5,
    ) -> None:
        """Muestra el historial de snapshots semanales de XP."""
        await interaction.response.defer()

        target = member or interaction.user
        if not isinstance(target, discord.Member):
            target = interaction.guild.get_member(target.id) or target

        # Buscar usuario en MongoDB
        user_data = users_col.find_one({"discord_id": str(target.id)})
        if not user_data:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=(
                        f"❌ {target.mention} no tiene una cuenta de Protox.io vinculada.\n"
                        f"Usa `/register` para vincular tu cuenta."
                    ),
                    color=config.COLOR_ERROR,
                )
            )
            return

        player_id = user_data["protox_player_id"]
        weeks = max(1, min(10, weeks))

        # Obtener snapshots de MongoDB
        snapshots = list(
            weekly_snapshots_col.find(
                {"player_id": player_id},
                sort=[("week_date", -1)],
                limit=weeks + 1,  # +1 para calcular la diferencia de la primera semana
            )
        )

        embed = build_history_embed(user_data, snapshots, target)
        await interaction.followup.send(embed=embed)

    # ============================================================
    # Tarea programada: Snapshot semanal
    # ============================================================

    @tasks.loop(hours=1)
    async def weekly_snapshot_task(self) -> None:
        """
        Tarea que se ejecuta cada hora para verificar si es domingo.
        Si es domingo a las 23:00 UTC o posterior, toma el snapshot semanal
        de todos los jugadores registrados.
        """
        now = utcnow()

        # Ejecutar solo los domingos entre las 23:00 y las 23:59 UTC
        if now.weekday() != 6 or now.hour != 23:
            return

        week_date = get_week_date_str(now)
        logger.info(f"Iniciando snapshot semanal automático para la semana {week_date}...")

        # Verificar si ya se tomó el snapshot esta semana
        existing = weekly_snapshots_col.find_one(
            {"week_date": week_date, "snapshot_type": "weekly_auto"}
        )
        if existing:
            logger.info(f"Snapshot de la semana {week_date} ya existe. Saltando.")
            return

        await self._take_weekly_snapshot(week_date)

    @weekly_snapshot_task.before_loop
    async def before_weekly_snapshot(self) -> None:
        """Espera a que el bot esté listo antes de iniciar la tarea."""
        await self.bot.wait_until_ready()
        logger.info("Tarea de snapshot semanal iniciada y esperando al bot.")

    async def _take_weekly_snapshot(self, week_date: str) -> None:
        """
        Toma un snapshot de XP de todos los jugadores registrados.

        Args:
            week_date: Identificador de la semana (e.g., "2026-W26").
        """
        registered_users = list(users_col.find({}))
        if not registered_users:
            logger.info("No hay usuarios registrados para el snapshot semanal.")
            return

        success_count = 0
        error_count = 0

        for user in registered_users:
            player_id = user.get("protox_player_id")
            if not player_id:
                continue

            try:
                xp = await self.bot.protox_client.get_player_xp(player_id)

                # Guardar snapshot sin sobrescribir los anteriores
                weekly_snapshots_col.update_one(
                    {"player_id": player_id, "week_date": week_date},
                    {
                        "$set": {
                            "player_id": player_id,
                            "discord_id": user.get("discord_id"),
                            "username": user.get("username"),
                            "week_date": week_date,
                            "total_xp": xp,
                            "snapshot_type": "weekly_auto",
                            "created_at": utcnow().isoformat(),
                        }
                    },
                    upsert=True,
                )
                success_count += 1

                # Pequeña pausa para no saturar la API
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error al obtener XP de {player_id}: {e}")
                error_count += 1

        logger.info(
            f"Snapshot semanal completado para {week_date}. "
            f"Éxitos: {success_count}, Errores: {error_count}"
        )

    # ============================================================
    # Comando manual para forzar snapshot (solo admin)
    # ============================================================

    @app_commands.command(
        name="snapshot",
        description="[ADMIN] Forzar un snapshot manual de XP para todos los jugadores",
    )
    @app_commands.default_permissions(administrator=True)
    async def force_snapshot(self, interaction: discord.Interaction) -> None:
        """Fuerza un snapshot manual de XP (solo administradores)."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Solo los administradores pueden usar este comando.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        week_date = get_week_date_str()
        await self._take_weekly_snapshot(week_date)

        await interaction.followup.send(
            embed=discord.Embed(
                title="✅ Snapshot manual completado",
                description=f"Se ha tomado un snapshot de XP para la semana **{week_date}**.",
                color=config.COLOR_SUCCESS,
                timestamp=utcnow(),
            ),
            ephemeral=True,
        )

    # ============================================================
    # /leaderboard (XP semanal del clan)
    # ============================================================

    @app_commands.command(
        name="leaderboard",
        description="Ver el ranking de XP semanal del clan YSL",
    )
    @app_commands.describe(weeks_back="Semanas hacia atrás (0 = semana actual)")
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        weeks_back: int = 0,
    ) -> None:
        """Muestra el ranking de XP semanal del clan YSL."""
        await interaction.response.defer()

        now = utcnow()
        # Calcular la semana objetivo
        from datetime import timedelta
        target_date = now - timedelta(weeks=weeks_back)
        week_date = get_week_date_str(target_date)

        # Obtener snapshots de esa semana
        current_snaps = {
            s["player_id"]: s
            for s in weekly_snapshots_col.find({"week_date": week_date})
        }

        if not current_snaps:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=f"❌ No hay datos de XP para la semana **{week_date}**.",
                    color=config.COLOR_ERROR,
                )
            )
            return

        # Obtener snapshots de la semana anterior para calcular XP ganada
        prev_target = target_date - timedelta(weeks=1)
        prev_week_date = get_week_date_str(prev_target)
        prev_snaps = {
            s["player_id"]: s
            for s in weekly_snapshots_col.find({"week_date": prev_week_date})
        }

        # Calcular XP ganada por jugador
        rows = []
        for player_id, snap in current_snaps.items():
            current_xp = snap.get("total_xp", 0)
            prev_xp = prev_snaps.get(player_id, {}).get("total_xp", 0)
            weekly_xp = max(0, current_xp - prev_xp)
            username = snap.get("username", player_id)
            rows.append((username, weekly_xp))

        # Ordenar por XP ganada (descendente)
        rows.sort(key=lambda x: x[1], reverse=True)

        # Construir embed
        embed = discord.Embed(
            title=f"🏆 Ranking XP Semanal · Clan YSL",
            description=f"Semana: **{week_date}**",
            color=config.COLOR_GOLD,
            timestamp=utcnow(),
        )

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (username, xp) in enumerate(rows[:15]):
            medal = medals[i] if i < 3 else f"`{i+1}.`"
            req_met = "✅" if xp >= config.WEEKLY_XP_REQUIREMENT else "❌"
            lines.append(f"{medal} **{username}** — {xp:,} XP {req_met}")

        embed.add_field(
            name=f"Top {min(15, len(rows))} jugadores",
            value="\n".join(lines) if lines else "Sin datos",
            inline=False,
        )
        embed.set_footer(
            text=f"Requisito semanal: {config.WEEKLY_XP_REQUIREMENT:,} XP · Protox.io",
        )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Registra el cog en el bot."""
    await bot.add_cog(ProtoxCog(bot))

"""
cogs/protox.py - Protox.io XP tracking system for the YSL Clan.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

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
    """XP tracking system for Protox.io."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        logger.info("ProtoxCog loaded.")

    # ============================================================
    # /register
    # ============================================================

    @app_commands.command(
        name="register",
        description="Link your Discord account with your Protox.io player",
    )
    @app_commands.describe(
        player_id="Your Protox.io Player ID",
        username="Your Protox.io username",
    )
    async def register(
        self,
        interaction: discord.Interaction,
        player_id: str,
        username: str,
    ) -> None:
        """Links a Discord account with a Protox.io player."""
        await interaction.response.defer(ephemeral=True)

        player_id = player_id.strip()
        username = username.strip()

        # Check if player_id is already linked to another user
        existing = users_col.find_one({
            "protox_player_id": player_id,
            "discord_id": {"$ne": str(interaction.user.id)},
        })
        if existing:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=f"❌ Player ID `{player_id}` is already linked to another user.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        # Save or update in MongoDB
        users_col.update_one(
            {"discord_id": str(interaction.user.id)},
            {
                "$set": {
                    "discord_id": str(interaction.user.id),
                    "protox_player_id": player_id,
                    "username": username,
                    "registered_at": utcnow().isoformat(),
                }
            },
            upsert=True,
        )

        embed = discord.Embed(
            title="✅ Account Linked",
            description=(
                f"Successfully linked your account.\n\n"
                f"**Discord:** {interaction.user.mention}\n"
                f"**Player ID:** `{player_id}`\n"
                f"**Username:** `{username}`\n\n"
                f"Use `/weeklyxp` to check your progress."
            ),
            color=config.COLOR_SUCCESS,
            timestamp=utcnow(),
        )
        embed.set_footer(text=f"{config.CLAN_NAME} Clan · Protox.io")

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ============================================================
    # /profile
    # ============================================================

    @app_commands.command(
        name="profile",
        description="View Protox.io profile of a clan member",
    )
    @app_commands.describe(member="Member to check (defaults to you)")
    async def profile(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        """Shows the Protox.io profile of a member."""
        await interaction.response.defer()

        target = member or interaction.user
        user_data = users_col.find_one({"discord_id": str(target.id)})
        
        if not user_data:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=f"❌ {target.mention} has not linked their Protox.io account. Use `/register`.",
                    color=config.COLOR_ERROR,
                )
            )
            return

        player_data = await self.bot.protox_client.get_player(user_data["protox_player_id"])
        embed = build_profile_embed(user_data, player_data, target)
        await interaction.followup.send(embed=embed)

    # ============================================================
    # /weeklyxp
    # ============================================================

    @app_commands.command(
        name="weeklyxp",
        description="Check XP earned this week",
    )
    @app_commands.describe(member="Member to check (defaults to you)")
    async def weeklyxp(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        """Shows weekly XP progress."""
        await interaction.response.defer()

        target = member or interaction.user
        user_data = users_col.find_one({"discord_id": str(target.id)})
        
        if not user_data:
            await interaction.followup.send(
                embed=discord.Embed(
                    description=f"❌ {target.mention} has not linked their account.",
                    color=config.COLOR_ERROR,
                )
            )
            return

        player_id = user_data["protox_player_id"]
        current_xp = await self.bot.protox_client.get_player_xp(player_id)
        
        prev_snapshot = weekly_snapshots_col.find_one(
            {"player_id": player_id},
            sort=[("week_date", -1)],
        )

        weekly_xp = max(0, current_xp - prev_snapshot["total_xp"]) if prev_snapshot else 0
        embed = build_weekly_xp_embed(user_data, weekly_xp, current_xp, get_week_date_str(), target)
        await interaction.followup.send(embed=embed)

    # ============================================================
    # /history
    # ============================================================

    @app_commands.command(
        name="history",
        description="View weekly XP history",
    )
    @app_commands.describe(member="Member to check (defaults to you)")
    async def history(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        """Shows weekly XP history snapshots."""
        await interaction.response.defer()

        target = member or interaction.user
        user_data = users_col.find_one({"discord_id": str(target.id)})
        
        if not user_data:
            await interaction.followup.send(
                embed=discord.Embed(description="❌ Account not linked.", color=config.COLOR_ERROR)
            )
            return

        snapshots = list(
            weekly_snapshots_col.find(
                {"player_id": user_data["protox_player_id"]},
                sort=[("week_date", -1)],
                limit=11,
            )
        )
        embed = build_history_embed(user_data, snapshots, target)
        await interaction.followup.send(embed=embed)

    # ============================================================
    # /leaderboard
    # ============================================================

    @app_commands.command(
        name="leaderboard",
        description="View the weekly XP leaderboard for the YSL Clan",
    )
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        """Shows the weekly XP ranking."""
        await interaction.response.defer()

        week_date = get_week_date_str()
        current_snaps = {s["player_id"]: s for s in weekly_snapshots_col.find({"week_date": week_date})}

        if not current_snaps:
            await interaction.followup.send(
                embed=discord.Embed(description="❌ No data for this week yet.", color=config.COLOR_ERROR)
            )
            return

        # Find previous week snapshots to calculate gain
        from datetime import timedelta
        prev_week_date = get_week_date_str(utcnow() - timedelta(weeks=1))
        prev_snaps = {s["player_id"]: s["total_xp"] for s in weekly_snapshots_col.find({"week_date": prev_week_date})}

        rows = []
        for pid, snap in current_snaps.items():
            gain = max(0, snap["total_xp"] - prev_snaps.get(pid, 0))
            rows.append((snap.get("username", pid), gain))

        rows.sort(key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title=f"🏆 Weekly Leaderboard · {config.CLAN_NAME}",
            description=f"Week: **{week_date}**",
            color=config.COLOR_GOLD,
            timestamp=utcnow(),
        )

        lines = []
        for i, (user, xp) in enumerate(rows[:15]):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"`{i+1}.`"
            lines.append(f"{medal} **{user}** — {xp:,} XP")

        embed.add_field(name="Top Players", value="\n".join(lines) if lines else "No data", inline=False)
        await interaction.followup.send(embed=embed)

    # ============================================================
    # Manual Snapshot (Admin Only)
    # ============================================================

    @app_commands.command(name="snapshot", description="[ADMIN] Force a manual XP snapshot")
    @app_commands.default_permissions(administrator=True)
    async def force_snapshot(self, interaction: discord.Interaction) -> None:
        """Manually triggers a snapshot for all registered users."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message("❌ Admin only.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        week_date = get_week_date_str()
        
        users = list(users_col.find({}))
        for user in users:
            pid = user["protox_player_id"]
            xp = await self.bot.protox_client.get_player_xp(pid)
            weekly_snapshots_col.update_one(
                {"player_id": pid, "week_date": week_date},
                {
                    "$set": {
                        "player_id": pid, 
                        "username": user["username"], 
                        "week_date": week_date, 
                        "total_xp": xp, 
                        "created_at": utcnow().isoformat()
                    }
                },
                upsert=True,
            )
        
        await interaction.followup.send("✅ Snapshot completed.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProtoxCog(bot))

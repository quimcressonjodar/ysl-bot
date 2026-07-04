from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands

import config
from config import CLAN_NAME, MONDAY_SNAPSHOT_PATH, SUNDAY_SNAPSHOT_PATH
from database import snaps_col
from utils.helpers import is_admin, load_snapshot, save_snapshot
from utils.kirka_api import extract_member_map, build_weekly_rows

class ProtoxCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name="register", description="Weekly snapshot registration system")
    async def register_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand: `monday` or `sunday`.")

    @register_group.command(name="monday", description="🔥 FIRST (START OF WEEK): Run on Mondays to start the new week.")
    async def register_monday(self, ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        await ctx.defer()
        try:
            clan_data = await self.bot.clan_client.get_clan_data(CLAN_NAME)
            snapshot = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "clan_name": clan_data.get("name", CLAN_NAME),
                "members": extract_member_map(clan_data),
            }
            save_snapshot(MONDAY_SNAPSHOT_PATH, snapshot)
            await ctx.send(f"Monday snapshot saved in `{MONDAY_SNAPSHOT_PATH}` with {len(snapshot['members'])} members.")
        except Exception as exc:
            await ctx.send(f"Failed to save Monday snapshot: {exc}")

    @register_group.command(name="sunday", description="✅ SECOND (END OF WEEK): Run after having used /register monday.")
    async def register_sunday(self, ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        await ctx.defer()
        try:
            clan_data = await self.bot.clan_client.get_clan_data(CLAN_NAME)
            snapshot = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "clan_name": clan_data.get("name", CLAN_NAME),
                "members": extract_member_map(clan_data),
            }
            save_snapshot(SUNDAY_SNAPSHOT_PATH, snapshot)
            await ctx.send(f"Sunday snapshot saved in `{SUNDAY_SNAPSHOT_PATH}` with {len(snapshot['members'])} members.")
        except Exception as exc:
            await ctx.send(f"Failed to save Sunday snapshot: {exc}")

    @commands.hybrid_command(name="weekly_lb", description="Build weekly leaderboard from Monday/Sunday snapshots")
    async def weekly_lb(self, ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        await ctx.defer()
        try:
            monday_data = load_snapshot(MONDAY_SNAPSHOT_PATH)
            sunday_data = load_snapshot(SUNDAY_SNAPSHOT_PATH)
            if not monday_data or not sunday_data:
                return await ctx.send(
                    "Need both files first. Run `/register monday` and `/register sunday` before `/weekly_lb`."
                )

            rows = build_weekly_rows(monday_data["members"], sunday_data["members"])
            total_weekly_xp = sum(row[3] for row in rows)

            lines = []
            header = f"{'Player':<18} {'Short ID':<10} {'XP':>10}   Status"
            lines.append(header)
            lines.append("-" * 60)

            role_colors = {"LEADER": "\u001b[33;1m", "OFFICER": "\u001b[34;1m", "NEWBIE": "\u001b[36m"}
            status_colors = {
                "OK": "\u001b[32m", "MISSING": "\u001b[31m", "REVIEW": "\u001b[33m",
                "JOINED": "\u001b[36m", "LEFT": "\u001b[35m",
            }
            reset = "\u001b[0m"

            for row in rows:
                player = str(row[0])[:18]
                short_id = str(row[1])[:10]
                role = str(row[2]).upper()
                xp = f"{row[3]:,}"
                status = row[4]
                player_color = role_colors.get(role, "\u001b[37m")
                status_color = status_colors.get(status, "\u001b[0m")
                lines.append(
                    f"{player_color}{player:<18}{reset} {short_id:<10} {xp:>10}   {status_color}{status}{reset}"
                )

            report_header = (
                f"Clan: {sunday_data['clan_name']}\n"
                f"Total Weekly XP: {total_weekly_xp:,}\n"
                f"Requirement: {config.WEEKLY_XP_REQUIREMENT:,} XP\n"
                f"Monday: {monday_data['timestamp_utc']}\n"
                f"Sunday: {sunday_data['timestamp_utc']}\n\n"
            )

            chunks = []
            current_chunk = report_header + "```ansi\n"
            for line in lines:
                test_chunk = current_chunk + line + "\n```"
                if len(test_chunk) > 1900:
                    current_chunk += "```"
                    chunks.append(current_chunk)
                    current_chunk = "```ansi\n" + line + "\n"
                else:
                    current_chunk += line + "\n"
            current_chunk += "```"
            chunks.append(current_chunk)

            for i, chunk in enumerate(chunks):
                if i == 0:
                    await ctx.send(chunk)
                else:
                    await ctx.channel.send(chunk)

        except Exception as exc:
            await ctx.send(f"Failed to build leaderboard: {exc}")

    @commands.hybrid_command(name="set_xp", description="Set weekly XP requirement (admin only)")
    @app_commands.describe(xp="New weekly XP requirement")
    async def set_xp(self, ctx: commands.Context, xp: int):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        if xp <= 0:
            return await ctx.send("XP requirement must be greater than 0.", ephemeral=True)
        config.WEEKLY_XP_REQUIREMENT = xp
        await ctx.send(f"Weekly XP requirement updated to {config.WEEKLY_XP_REQUIREMENT:,} XP.")

    @commands.hybrid_command(name="delete_snaps", description="Delete Monday and Sunday snapshots")
    async def delete_snaps(self, ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        try:
            snaps_col.delete_many({})
            await ctx.send("Deleted snapshots: Monday, Sunday")
        except Exception as exc:
            await ctx.send(f"Failed deleting snapshots: {exc}")

async def setup(bot: commands.Bot):
    await bot.add_cog(ProtoxCog(bot))

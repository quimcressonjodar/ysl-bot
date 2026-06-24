"""
cogs/moderation.py - Moderation system for the YSL Clan.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

import config
from database import warnings_col, guild_settings_col
from utils.helpers import utcnow, is_mod_interaction, parse_duration, error_embed, success_embed
from utils.formatters import build_mod_log_embed

logger = logging.getLogger("ysl-bot.moderation")


class ModerationCog(commands.Cog, name="Moderation"):
    """Moderation commands for managing the server."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        logger.info("ModerationCog loaded.")

    async def _log_action(self, interaction: discord.Interaction, embed: discord.Embed):
        """Sends a moderation log to the configured log channel."""
        settings = guild_settings_col.find_one({"guild_id": str(interaction.guild_id)})
        if settings and settings.get("log_channel_id"):
            channel = interaction.guild.get_channel(int(settings["log_channel_id"]))
            if channel:
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass

    # ============================================================
    # /warn
    # ============================================================

    @app_commands.command(name="warn", description="Issue a warning to a member")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @app_commands.default_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str) -> None:
        """Issues a warning to a member."""
        await interaction.response.defer()

        if not is_mod_interaction(interaction):
            await interaction.followup.send(embed=error_embed("You don't have permission to use this command."), ephemeral=True)
            return

        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.followup.send(embed=error_embed("You cannot warn someone with a higher or equal role."), ephemeral=True)
            return

        warn_data = {
            "guild_id": str(interaction.guild_id),
            "user_id": str(member.id),
            "moderator_id": str(interaction.user.id),
            "reason": reason,
            "timestamp": utcnow().isoformat(),
        }
        warnings_col.insert_one(warn_data)
        
        count = warnings_col.count_documents({"guild_id": str(interaction.guild_id), "user_id": str(member.id)})

        log_embed = build_mod_log_embed("warn", member, interaction.user, reason)
        log_embed.add_field(name="Total Warnings", value=str(count), inline=True)
        await self._log_action(interaction, log_embed)

        try:
            await member.send(embed=error_embed(f"You have been warned in **{interaction.guild.name}**.\n**Reason:** {reason}\n**Total Warnings:** {count}", title="Warning Received"))
        except Exception:
            pass

        await interaction.followup.send(embed=success_embed(f"Successfully warned {member.mention}. (Total: {count})"))

    # ============================================================
    # /mute (Timeout)
    # ============================================================

    @app_commands.command(name="mute", description="Temporarily mute a member (Timeout)")
    @app_commands.describe(member="Member to mute", duration="Duration (e.g., 10m, 1h, 1d)", reason="Reason")
    @app_commands.default_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str) -> None:
        """Applies a timeout to a member."""
        await interaction.response.defer()

        if not is_mod_interaction(interaction):
            await interaction.followup.send(embed=error_embed("Permission denied."), ephemeral=True)
            return

        delta = parse_duration(duration)
        if not delta:
            await interaction.followup.send(embed=error_embed("Invalid duration format. Use e.g., 10m, 1h, 1d."), ephemeral=True)
            return

        try:
            await member.timeout(delta, reason=reason)
            log_embed = build_mod_log_embed("mute", member, interaction.user, reason, duration)
            await self._log_action(interaction, log_embed)
            await interaction.followup.send(embed=success_embed(f"Muted {member.mention} for {duration}."))
        except Exception as e:
            await interaction.followup.send(embed=error_embed(f"Failed to mute member: {e}"), ephemeral=True)

    @app_commands.command(name="unmute", description="Remove timeout from a member")
    @app_commands.default_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided") -> None:
        """Removes a timeout from a member."""
        await interaction.response.defer()
        try:
            await member.timeout(None, reason=reason)
            log_embed = build_mod_log_embed("unmute", member, interaction.user, reason)
            await self._log_action(interaction, log_embed)
            await interaction.followup.send(embed=success_embed(f"Unmuted {member.mention}."))
        except Exception as e:
            await interaction.followup.send(embed=error_embed(f"Failed to unmute: {e}"), ephemeral=True)

    # ============================================================
    # /kick & /ban
    # ============================================================

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str) -> None:
        """Kicks a member."""
        await interaction.response.defer()
        if not is_mod_interaction(interaction): return
        try:
            await member.kick(reason=reason)
            await self._log_action(interaction, build_mod_log_embed("kick", member, interaction.user, reason))
            await interaction.followup.send(embed=success_embed(f"Kicked {member.mention}."))
        except Exception as e:
            await interaction.followup.send(embed=error_embed(str(e)), ephemeral=True)

    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str, delete_messages: bool = False) -> None:
        """Bans a member."""
        await interaction.response.defer()
        if not is_mod_interaction(interaction): return
        try:
            await member.ban(reason=reason, delete_message_days=1 if delete_messages else 0)
            await self._log_action(interaction, build_mod_log_embed("ban", member, interaction.user, reason))
            await interaction.followup.send(embed=success_embed(f"Banned {member.mention}."))
        except Exception as e:
            await interaction.followup.send(embed=error_embed(str(e)), ephemeral=True)

    @app_commands.command(name="unban", description="Unban a user from the server")
    @app_commands.describe(user_id="The Discord ID of the user to unban")
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided") -> None:
        """Unbans a user."""
        await interaction.response.defer()
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=reason)
            await self._log_action(interaction, build_mod_log_embed("unban", user, interaction.user, reason))
            await interaction.followup.send(embed=success_embed(f"Unbanned {user.name}."))
        except Exception as e:
            await interaction.followup.send(embed=error_embed(f"User not found or not banned: {e}"), ephemeral=True)

    # ============================================================
    # /purge
    # ============================================================

    @app_commands.command(name="purge", description="Delete a number of messages from the channel")
    @app_commands.describe(amount="Number of messages to delete (1-100)")
    @app_commands.default_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: int) -> None:
        """Deletes messages in bulk."""
        if amount < 1 or amount > 100:
            await interaction.response.send_message(embed=error_embed("Amount must be between 1 and 100."), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(embed=success_embed(f"Deleted {len(deleted)} messages."), ephemeral=True)

    # ============================================================
    # /report
    # ============================================================

    @app_commands.command(name="report", description="Report a user to the staff")
    @app_commands.describe(member="User to report", reason="Reason for the report")
    async def report(self, interaction: discord.Interaction, member: discord.Member, reason: str) -> None:
        """Submits a report to the log channel."""
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title=f"{config.EMOJI_WARNING} New Report",
            color=config.COLOR_WARNING,
            timestamp=utcnow(),
        )
        embed.add_field(name="Reported User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="Reporter", value=f"{interaction.user.mention}", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)

        settings = guild_settings_col.find_one({"guild_id": str(interaction.guild_id)})
        if settings and settings.get("log_channel_id"):
            channel = interaction.guild.get_channel(int(settings["log_channel_id"]))
            if channel:
                await channel.send(embed=embed)
                await interaction.followup.send(embed=success_embed("Your report has been submitted to the staff."), ephemeral=True)
                return

        await interaction.followup.send(embed=error_embed("Report system is not configured (log channel missing)."), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationCog(bot))

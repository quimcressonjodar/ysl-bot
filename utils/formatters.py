"""
utils/formatters.py - Embed generators for consistent visual style in English.
"""

import discord
import config
from utils.helpers import utcnow


def build_profile_embed(user_data: dict, player_data: dict, member: discord.Member) -> discord.Embed:
    """Builds the profile embed for a player."""
    embed = discord.Embed(
        title=f"{config.EMOJI_PLAYER} {member.display_name}'s Profile",
        color=config.COLOR_PRIMARY,
        timestamp=utcnow(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    # Database Info
    embed.add_field(name="Protox ID", value=f"`{user_data['protox_player_id']}`", inline=True)
    embed.add_field(name="Username", value=f"`{user_data['username']}`", inline=True)

    # API Info (if available)
    if player_data:
        embed.add_field(name="Level", value=str(player_data.get("level", "N/A")), inline=True)
        embed.add_field(name="Total XP", value=f"{player_data.get('total_xp', 0):,}", inline=True)
        embed.add_field(name="Clan", value=player_data.get("clan", "None"), inline=True)

    embed.set_footer(text=f"{config.CLAN_NAME} Clan · Protox.io")
    return embed


def build_weekly_xp_embed(user_data: dict, weekly_xp: int, current_xp: int, week_date: str, member: discord.Member) -> discord.Embed:
    """Builds the weekly XP progress embed."""
    embed = discord.Embed(
        title=f"{config.EMOJI_XP} Weekly XP Progress",
        description=f"Progress for week **{week_date}**",
        color=config.COLOR_GOLD if weekly_xp >= config.WEEKLY_XP_REQUIREMENT else config.COLOR_INFO,
        timestamp=utcnow(),
    )
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)

    req = config.WEEKLY_XP_REQUIREMENT
    percentage = min(100, (weekly_xp / req) * 100) if req > 0 else 100
    
    # Simple progress bar
    bar_length = 10
    filled = int(percentage / 10)
    bar = "🟦" * filled + "⬜" * (bar_length - filled)

    embed.add_field(name="Weekly XP Earned", value=f"**{weekly_xp:,}** XP", inline=True)
    embed.add_field(name="Weekly Requirement", value=f"{req:,} XP", inline=True)
    embed.add_field(name="Current Total XP", value=f"{current_xp:,} XP", inline=True)
    
    status = "✅ Requirement Met" if weekly_xp >= req else f"❌ {req - weekly_xp:,} XP remaining"
    embed.add_field(name="Status", value=f"{bar} ({percentage:.1f}%)\n{status}", inline=False)

    embed.set_footer(text=f"{config.CLAN_NAME} Clan · Protox.io")
    return embed


def build_history_embed(user_data: dict, snapshots: list, member: discord.Member) -> discord.Embed:
    """Builds the weekly XP history embed."""
    embed = discord.Embed(
        title=f"{config.EMOJI_WEEK} XP History",
        description=f"Weekly snapshots for **{user_data['username']}**",
        color=config.COLOR_INFO,
        timestamp=utcnow(),
    )
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)

    if not snapshots or len(snapshots) < 2:
        embed.description = "Not enough data to show history yet. Snapshots are taken every Sunday."
    else:
        lines = []
        for i in range(len(snapshots) - 1):
            curr = snapshots[i]
            prev = snapshots[i+1]
            gain = max(0, curr["total_xp"] - prev["total_xp"])
            lines.append(f"📅 **{curr['week_date']}**: +{gain:,} XP")
        
        embed.add_field(name="Recent Weeks", value="\n".join(lines[:10]), inline=False)

    embed.set_footer(text=f"{config.CLAN_NAME} Clan · Protox.io")
    return embed


def build_mod_log_embed(action: str, target: discord.User, moderator: discord.Member, reason: str, duration: str = None) -> discord.Embed:
    """Builds a moderation log embed."""
    embed = discord.Embed(
        title=f"{config.EMOJI_MOD} Moderation Action: {action.upper()}",
        color=config.COLOR_WARNING if action != "ban" else config.COLOR_ERROR,
        timestamp=utcnow(),
    )
    embed.add_field(name="Target", value=f"{target.mention} (`{target.id}`)", inline=True)
    embed.add_field(name="Moderator", value=f"{moderator.mention}", inline=True)
    embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
    
    if duration:
        embed.add_field(name="Duration", value=duration, inline=True)
        
    embed.set_footer(text=f"User ID: {target.id}")
    return embed

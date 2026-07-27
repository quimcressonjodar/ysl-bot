"""
cogs/afk.py — AFK status and reminder system.

AFK:
  !afk [reason]  — marks you as AFK; bot notifies anyone who pings/names you.
  Sending any message (except !afk itself) clears your AFK automatically.

Remindme:
  !remindme <duration> <text>  — reminds you in the original channel (or DM).
  Supports: 10m · 2h · 1d · 1h30m · combinations.
"""

import logging
import re
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from database import afk_col, reminders_col

logger = logging.getLogger("weekly-xp-bot")


# ── Helpers ───────────────────────────────────────────────────────────────────

_DURATION_RE = re.compile(
    r"(?:(\d+)\s*d(?:ays?)?)?\s*"
    r"(?:(\d+)\s*h(?:ours?)?)?\s*"
    r"(?:(\d+)\s*m(?:in(?:utes?)?)?)?\s*"
    r"(?:(\d+)\s*s(?:ec(?:onds?)?)?)?",
    re.IGNORECASE,
)


def _parse_duration(text: str) -> int | None:
    """Return total seconds for strings like '10m', '2h30m', '1d'. None if invalid."""
    m = _DURATION_RE.fullmatch(text.strip())
    if not m or not any(m.groups()):
        return None
    days, hours, minutes, seconds = (int(v or 0) for v in m.groups())
    total = days * 86400 + hours * 3600 + minutes * 60 + seconds
    return total if total > 0 else None


def _fmt(seconds: int) -> str:
    """Human-readable duration: '1h 23m 4s'."""
    parts: list[str] = []
    for unit, label in ((86400, "d"), (3600, "h"), (60, "m"), (1, "s")):
        if seconds >= unit:
            parts.append(f"{seconds // unit}{label}")
            seconds %= unit
    return " ".join(parts) or "0s"


# ── Cog ───────────────────────────────────────────────────────────────────────

class AFKCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._reminder_loop.start()

    def cog_unload(self) -> None:
        self._reminder_loop.cancel()

    # ── !afk ─────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="afk", description="Set yourself as AFK with an optional reason")
    @app_commands.describe(reason="Why you're going AFK (optional, defaults to 'AFK')")
    async def afk(self, ctx: commands.Context, *, reason: str = "AFK"):
        afk_col.update_one(
            {"_id": str(ctx.author.id)},
            {"$set": {"reason": reason, "since": datetime.now(timezone.utc)}},
            upsert=True,
        )
        embed = discord.Embed(
            description=f"💤 {ctx.author.mention} is now AFK: **{reason}**",
            color=0x99AAB5,
        )
        await ctx.send(embed=embed)

    # ── on_message — AFK logic ────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        # ── 1. Remove AFK when the AFK user sends a message ──────────────────
        doc = afk_col.find_one({"_id": str(message.author.id)})
        if doc:
            # Only keep AFK if they're re-setting it with !afk / /afk
            content_lower = message.content.lower().lstrip()
            is_setting_afk = content_lower.startswith("!afk") or content_lower.startswith("/afk")
            if not is_setting_afk:
                afk_col.delete_one({"_id": str(message.author.id)})
                since: datetime = doc["since"]
                if since.tzinfo is None:
                    since = since.replace(tzinfo=timezone.utc)
                elapsed = int((datetime.now(timezone.utc) - since).total_seconds())
                embed = discord.Embed(
                    description=(
                        f"👋 Welcome back, {message.author.mention}! "
                        f"AFK removed *(away for {_fmt(elapsed)})*"
                    ),
                    color=0x57F287,
                )
                try:
                    await message.channel.send(embed=embed, delete_after=10)
                except discord.HTTPException:
                    pass

        # ── 2. Notify when an AFK user is pinged or named ────────────────────
        notified: set[str] = set()

        # Check explicit @mentions
        for mentioned in message.mentions:
            uid = str(mentioned.id)
            if uid == str(message.author.id) or uid in notified:
                continue
            afk_doc = afk_col.find_one({"_id": uid})
            if not afk_doc:
                continue
            await self._send_afk_notice(message.channel, mentioned, afk_doc)
            notified.add(uid)

        # Check if any AFK user's display name appears in the message text
        if message.mentions:
            # Already handled all mentions above — skip name scan to avoid duplicates
            return

        content = message.content
        if not content:
            return

        all_afk = list(afk_col.find())
        for afk_doc in all_afk:
            uid = afk_doc["_id"]
            if uid == str(message.author.id) or uid in notified:
                continue
            member = message.guild.get_member(int(uid))
            if member is None:
                continue
            # Match display name or username as a whole word (case-insensitive)
            for name in (member.display_name, member.name):
                if len(name) < 3:
                    continue
                if re.search(r"\b" + re.escape(name) + r"\b", content, re.IGNORECASE):
                    await self._send_afk_notice(message.channel, member, afk_doc)
                    notified.add(uid)
                    break

    async def _send_afk_notice(
        self,
        channel: discord.abc.Messageable,
        member: discord.abc.User,
        afk_doc: dict,
    ) -> None:
        since: datetime = afk_doc["since"]
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        elapsed = int((datetime.now(timezone.utc) - since).total_seconds())
        embed = discord.Embed(
            description=(
                f"💤 **{member.display_name}** is AFK: **{afk_doc['reason']}**\n"
                f"*(away for {_fmt(elapsed)})*"
            ),
            color=0x99AAB5,
        )
        try:
            await channel.send(embed=embed, delete_after=15)
        except discord.HTTPException:
            pass

    # ── !remindme ─────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="remindme",
        description="Set a reminder — e.g. !remindme 2h Check the oven",
    )
    @app_commands.describe(
        duration="When to remind you — e.g. 10m, 2h, 1d, 1h30m",
        reminder="What to remind you about",
    )
    async def remindme(self, ctx: commands.Context, duration: str, *, reminder: str):
        seconds = _parse_duration(duration)
        if seconds is None:
            return await ctx.send(
                "❌ Invalid duration. Examples: `10m` · `2h` · `1d` · `1h30m`",
                ephemeral=True,
            )
        if seconds > 30 * 86400:
            return await ctx.send("❌ Max reminder duration is 30 days.", ephemeral=True)

        due_at = datetime.now(timezone.utc).timestamp() + seconds
        reminders_col.insert_one({
            "user_id": str(ctx.author.id),
            "channel_id": ctx.channel.id,
            "guild_id": ctx.guild.id if ctx.guild else None,
            "reminder": reminder,
            "due_at": due_at,
            "sent": False,
        })

        embed = discord.Embed(
            description=f"⏰ Got it! I'll remind you <t:{int(due_at)}:R> about: **{reminder}**",
            color=0x5865F2,
        )
        await ctx.send(embed=embed)

    # ── Background reminder delivery ──────────────────────────────────────────

    @tasks.loop(seconds=30)
    async def _reminder_loop(self) -> None:
        now = datetime.now(timezone.utc).timestamp()
        due = list(reminders_col.find({"sent": False, "due_at": {"$lte": now}}))
        for doc in due:
            reminders_col.update_one({"_id": doc["_id"]}, {"$set": {"sent": True}})
            try:
                user = (
                    self.bot.get_user(int(doc["user_id"]))
                    or await self.bot.fetch_user(int(doc["user_id"]))
                )
            except (discord.NotFound, discord.HTTPException):
                continue

            embed = discord.Embed(
                title="⏰ Reminder!",
                description=doc["reminder"],
                color=0x5865F2,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text="You asked me to remind you about this")

            # Try the original channel first, fall back to DM
            delivered = False
            channel_id = doc.get("channel_id")
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        channel = None
                if channel:
                    try:
                        await channel.send(content=user.mention, embed=embed)
                        delivered = True
                    except (discord.Forbidden, discord.HTTPException):
                        pass

            if not delivered:
                try:
                    await user.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass

    @_reminder_loop.before_loop
    async def _before_reminder_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AFKCog(bot))

"""
Polls & Giveaways cog — full-featured like Carlbot / GiveawayBoat.

POLLS
─────
!poll <duration> <question> | <opt1> | <opt2> ...   multi-choice (up to 10)
!quickpoll <question>                                yes / no

GIVEAWAYS
─────────
!gstart <duration> <winners>w <prize>               quick start
!gend <message_id>                                  end early & pick winners
!greroll <message_id>                               reroll winners
!glist                                              list active giveaways

Duration format: 30s · 10m · 2h · 1d  (combinable: 1h30m)
"""

import asyncio
import logging
import random
import re
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from config import OWNER_IDS
from database import polls_col, giveaways_col

logger = logging.getLogger("weekly-xp-bot")

# ── Constants ─────────────────────────────────────────────────────────────────

POLL_COLOR     = 0x3498DB
GIVEAWAY_COLOR = 0xF1C40F
WIN_COLOR      = 0x2ECC71
END_COLOR      = 0x95A5A6

NUMBER_EMOJIS = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
GIVEAWAY_EMOJI = "🎉"
YES_EMOJI      = "👍"
NO_EMOJI       = "👎"

# ── Duration parser ───────────────────────────────────────────────────────────

_DURATION_RE = re.compile(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")

def parse_duration(text: str) -> int | None:
    """Parse duration string like '1h30m' into total seconds. Returns None if invalid."""
    m = _DURATION_RE.fullmatch(text.strip())
    if not m or not any(m.groups()):
        return None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    total = d * 86400 + h * 3600 + mi * 60 + s
    return total if total > 0 else None


def fmt_duration(seconds: int) -> str:
    """Turn seconds into a human-readable string."""
    d, rem = divmod(int(seconds), 86400)
    h, rem = divmod(rem, 3600)
    m, s   = divmod(rem, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s: parts.append(f"{s}s")
    return " ".join(parts) or "0s"


def fmt_ts(dt: datetime) -> str:
    return f"<t:{int(dt.timestamp())}:R>"


# ── Permission helpers ────────────────────────────────────────────────────────

def is_mod(ctx: commands.Context) -> bool:
    if ctx.author.id in OWNER_IDS:
        return True
    if isinstance(ctx.author, discord.Member):
        return ctx.author.guild_permissions.manage_guild
    return False


# ── Cog ───────────────────────────────────────────────────────────────────────

class GiveawayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._check_loop.start()

    def cog_unload(self):
        self._check_loop.cancel()

    # ══════════════════════════════════════════════════════════════════════════
    # POLLS
    # ══════════════════════════════════════════════════════════════════════════

    @commands.command(name="poll")
    async def poll(self, ctx: commands.Context, duration: str, *, rest: str):
        """
        Create a multi-option poll.
        Usage: !poll <duration> <question> | <opt1> | <opt2> [| opt3 ...]
        Example: !poll 10m Best game? | Valorant | Minecraft | GTA
        """
        if not is_mod(ctx):
            return await ctx.send("❌ You need **Manage Server** to create polls.", delete_after=8)

        secs = parse_duration(duration)
        if secs is None:
            return await ctx.send("❌ Invalid duration. Examples: `30m`, `1h`, `1d`", delete_after=8)
        if secs > 7 * 86400:
            return await ctx.send("❌ Maximum poll duration is **7 days**.", delete_after=8)

        parts = [p.strip() for p in rest.split("|")]
        if len(parts) < 3:
            return await ctx.send(
                "❌ You need a question and at least **2 options**.\n"
                "Usage: `!poll 10m Question? | Option A | Option B`",
                delete_after=10,
            )
        question = parts[0]
        options  = parts[1:11]  # max 10

        ends_at = datetime.now(timezone.utc).timestamp() + secs

        desc_lines = [f"**{question}**\n"]
        for i, opt in enumerate(options):
            desc_lines.append(f"{NUMBER_EMOJIS[i]}  {opt}")
        desc_lines.append(f"\n⏱️ Ends {fmt_ts(datetime.fromtimestamp(ends_at, tz=timezone.utc))}")

        embed = discord.Embed(
            title="📊 Poll",
            description="\n".join(desc_lines),
            color=POLL_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Started by {ctx.author.display_name} • {fmt_duration(secs)}")

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        msg = await ctx.channel.send(embed=embed)
        for i in range(len(options)):
            await msg.add_reaction(NUMBER_EMOJIS[i])

        polls_col.insert_one({
            "message_id": msg.id,
            "channel_id": ctx.channel.id,
            "guild_id":   ctx.guild.id,
            "question":   question,
            "options":    options,
            "ends_at":    ends_at,
            "author_id":  ctx.author.id,
            "ended":      False,
        })

    @commands.command(name="quickpoll")
    async def quickpoll(self, ctx: commands.Context, *, question: str):
        """
        Create a quick yes/no poll.
        Usage: !quickpoll Should we do a giveaway?
        """
        embed = discord.Embed(
            title="📊 Quick Poll",
            description=f"**{question}**",
            color=POLL_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Asked by {ctx.author.display_name}")

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        msg = await ctx.channel.send(embed=embed)
        await msg.add_reaction(YES_EMOJI)
        await msg.add_reaction(NO_EMOJI)

    async def _end_poll(self, doc: dict):
        """Fetch reactions, compute results and edit the poll message."""
        channel = self.bot.get_channel(doc["channel_id"])
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(doc["channel_id"])
            except Exception:
                polls_col.update_one({"_id": doc["_id"]}, {"$set": {"ended": True}})
                return

        try:
            msg = await channel.fetch_message(doc["message_id"])
        except Exception:
            polls_col.update_one({"_id": doc["_id"]}, {"$set": {"ended": True}})
            return

        options = doc["options"]
        counts  = []
        for i, opt in enumerate(options):
            emoji = NUMBER_EMOJIS[i]
            rxn   = discord.utils.get(msg.reactions, emoji=emoji)
            # subtract 1 for the bot's own reaction
            counts.append(max((rxn.count - 1) if rxn else 0, 0))

        total    = sum(counts)
        max_vote = max(counts) if counts else 0

        lines = [f"**{doc['question']}**\n"]
        for i, (opt, cnt) in enumerate(zip(options, counts)):
            pct    = (cnt / total * 100) if total else 0
            bar    = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
            winner = " 🏆" if cnt == max_vote and max_vote > 0 else ""
            lines.append(f"{NUMBER_EMOJIS[i]}  **{opt}**{winner}\n`{bar}` {cnt} votes ({pct:.1f}%)\n")

        lines.append(f"**Total votes: {total}**")

        embed = discord.Embed(
            title="📊 Poll — Results",
            description="\n".join(lines),
            color=END_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="Poll ended")

        try:
            await msg.edit(embed=embed)
        except Exception:
            pass

        polls_col.update_one({"_id": doc["_id"]}, {"$set": {"ended": True}})

    # ══════════════════════════════════════════════════════════════════════════
    # GIVEAWAYS
    # ══════════════════════════════════════════════════════════════════════════

    @commands.command(name="gstart")
    async def gstart(self, ctx: commands.Context, duration: str, winners: str, *, prize: str):
        """
        Start a giveaway.
        Usage: !gstart <duration> <winners>w <prize>
        Example: !gstart 1h 2w Discord Nitro
        Optional: add --role @RoleName to require a role to enter.
        """
        if not is_mod(ctx):
            return await ctx.send("❌ You need **Manage Server** to start giveaways.", delete_after=8)

        secs = parse_duration(duration)
        if secs is None:
            return await ctx.send("❌ Invalid duration. Examples: `30m`, `1h`, `1d`", delete_after=8)
        if secs > 30 * 86400:
            return await ctx.send("❌ Maximum giveaway duration is **30 days**.", delete_after=8)

        if not winners.lower().endswith("w") or not winners[:-1].isdigit():
            return await ctx.send("❌ Winners format: `2w`, `1w`, `5w`", delete_after=8)
        winner_count = int(winners[:-1])
        if winner_count < 1 or winner_count > 20:
            return await ctx.send("❌ Winners must be between 1 and 20.", delete_after=8)

        # Optional role requirement
        required_role_id = None
        if "--role" in prize:
            parts = prize.split("--role")
            prize = parts[0].strip()
            role_mention = parts[1].strip()
            role = discord.utils.find(
                lambda r: r.mention == role_mention or r.name == role_mention,
                ctx.guild.roles,
            )
            if role:
                required_role_id = role.id

        ends_at = datetime.now(timezone.utc).timestamp() + secs
        ends_dt = datetime.fromtimestamp(ends_at, tz=timezone.utc)

        embed = self._build_giveaway_embed(
            prize=prize,
            winner_count=winner_count,
            ends_dt=ends_dt,
            host=ctx.author,
            required_role_id=required_role_id,
            guild=ctx.guild,
            entry_count=0,
        )

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        msg = await ctx.channel.send(embed=embed)
        await msg.add_reaction(GIVEAWAY_EMOJI)

        giveaways_col.insert_one({
            "message_id":       msg.id,
            "channel_id":       ctx.channel.id,
            "guild_id":         ctx.guild.id,
            "prize":            prize,
            "winner_count":     winner_count,
            "ends_at":          ends_at,
            "host_id":          ctx.author.id,
            "required_role_id": required_role_id,
            "ended":            False,
            "winners":          [],
        })

    @commands.command(name="gend")
    async def gend(self, ctx: commands.Context, message_id: int):
        """End a giveaway early and pick winners. Usage: !gend <message_id>"""
        if not is_mod(ctx):
            return await ctx.send("❌ You need **Manage Server** to end giveaways.", delete_after=8)

        doc = giveaways_col.find_one({"message_id": message_id, "guild_id": ctx.guild.id})
        if not doc:
            return await ctx.send("❌ Giveaway not found.", delete_after=8)
        if doc.get("ended"):
            return await ctx.send("❌ That giveaway has already ended.", delete_after=8)

        await self._end_giveaway(doc)
        await ctx.send("✅ Giveaway ended!", delete_after=5)

    @commands.command(name="greroll")
    async def greroll(self, ctx: commands.Context, message_id: int):
        """Reroll winners for an ended giveaway. Usage: !greroll <message_id>"""
        if not is_mod(ctx):
            return await ctx.send("❌ You need **Manage Server** to reroll giveaways.", delete_after=8)

        doc = giveaways_col.find_one({"message_id": message_id, "guild_id": ctx.guild.id})
        if not doc:
            return await ctx.send("❌ Giveaway not found.", delete_after=8)
        if not doc.get("ended"):
            return await ctx.send("❌ That giveaway hasn't ended yet. Use `!gend` first.", delete_after=8)

        channel = self.bot.get_channel(doc["channel_id"])
        if channel is None:
            return await ctx.send("❌ Couldn't find the giveaway channel.", delete_after=8)

        try:
            msg = await channel.fetch_message(message_id)
        except Exception:
            return await ctx.send("❌ Couldn't find the giveaway message.", delete_after=8)

        winners = await self._pick_winners(msg, doc)
        if not winners:
            return await ctx.send("❌ No valid entries to reroll from.", delete_after=8)

        mentions = ", ".join(w.mention for w in winners)
        await ctx.channel.send(
            f"🎉 **Giveaway Reroll!** New winner(s) for **{doc['prize']}**: {mentions}\nCongratulations!"
        )
        giveaways_col.update_one(
            {"_id": doc["_id"]},
            {"$set": {"winners": [w.id for w in winners]}},
        )

    @commands.command(name="glist")
    async def glist(self, ctx: commands.Context):
        """List all active giveaways in this server."""
        docs = list(giveaways_col.find({"guild_id": ctx.guild.id, "ended": False}))
        if not docs:
            return await ctx.send("📭 No active giveaways right now.")

        embed = discord.Embed(
            title="🎉 Active Giveaways",
            color=GIVEAWAY_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        for doc in docs[:10]:
            ends_dt = datetime.fromtimestamp(doc["ends_at"], tz=timezone.utc)
            channel = self.bot.get_channel(doc["channel_id"])
            ch_mention = channel.mention if channel else f"<#{doc['channel_id']}>"
            embed.add_field(
                name=f"🎁 {doc['prize']}",
                value=(
                    f"Channel: {ch_mention}\n"
                    f"Winners: **{doc['winner_count']}**\n"
                    f"Ends: {fmt_ts(ends_dt)}\n"
                    f"[Jump](<https://discord.com/channels/{doc['guild_id']}/{doc['channel_id']}/{doc['message_id']}>)"
                ),
                inline=True,
            )
        embed.set_footer(text=f"{len(docs)} active giveaway(s)")
        await ctx.send(embed=embed)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_giveaway_embed(
        self,
        *,
        prize: str,
        winner_count: int,
        ends_dt: datetime,
        host: discord.Member,
        required_role_id: int | None,
        guild: discord.Guild,
        entry_count: int,
    ) -> discord.Embed:
        desc = [
            f"React with {GIVEAWAY_EMOJI} to enter!\n",
            f"🏆 **Winners:** {winner_count}",
            f"⏱️ **Ends:** {fmt_ts(ends_dt)}",
            f"👤 **Hosted by:** {host.mention}",
        ]
        if required_role_id:
            desc.append(f"🔒 **Required role:** <@&{required_role_id}>")
        if entry_count:
            desc.append(f"📋 **Entries:** {entry_count}")

        embed = discord.Embed(
            title=f"🎉 {prize}",
            description="\n".join(desc),
            color=GIVEAWAY_COLOR,
            timestamp=ends_dt,
        )
        embed.set_footer(text="Ends at")
        return embed

    async def _pick_winners(self, msg: discord.Message, doc: dict) -> list[discord.Member]:
        rxn = discord.utils.get(msg.reactions, emoji=GIVEAWAY_EMOJI)
        if rxn is None:
            return []

        guild = self.bot.get_guild(doc["guild_id"])
        entries = []
        async for user in rxn.users():
            if user.bot:
                continue
            member = guild.get_member(user.id) if guild else None
            if member is None:
                continue
            # Role requirement check
            if doc.get("required_role_id"):
                if not any(r.id == doc["required_role_id"] for r in member.roles):
                    continue
            entries.append(member)

        if not entries:
            return []

        count   = min(doc["winner_count"], len(entries))
        return random.sample(entries, count)

    async def _end_giveaway(self, doc: dict):
        channel = self.bot.get_channel(doc["channel_id"])
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(doc["channel_id"])
            except Exception:
                giveaways_col.update_one({"_id": doc["_id"]}, {"$set": {"ended": True}})
                return

        try:
            msg = await channel.fetch_message(doc["message_id"])
        except Exception:
            giveaways_col.update_one({"_id": doc["_id"]}, {"$set": {"ended": True}})
            return

        winners = await self._pick_winners(msg, doc)

        # Edit the original embed to show ended state
        host = channel.guild.get_member(doc["host_id"])
        host_mention = host.mention if host else f"<@{doc['host_id']}>"

        if winners:
            winner_mentions = ", ".join(w.mention for w in winners)
            desc = [
                f"🏆 **Winner(s):** {winner_mentions}\n",
                f"👤 **Hosted by:** {host_mention}",
            ]
        else:
            winner_mentions = None
            desc = [
                "⚠️ **No valid entries!**\n",
                f"👤 **Hosted by:** {host_mention}",
            ]

        embed = discord.Embed(
            title=f"🎉 {doc['prize']} — Ended",
            description="\n".join(desc),
            color=END_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="Giveaway ended")

        try:
            await msg.edit(embed=embed)
        except Exception:
            pass

        # Announce winners
        if winner_mentions:
            await channel.send(
                f"🎊 Congratulations {winner_mentions}! You won **{doc['prize']}**!\n"
                f"*(Hosted by {host_mention})*"
            )
        else:
            await channel.send(
                f"😔 No valid entries for **{doc['prize']}** — giveaway ended with no winner."
            )

        giveaways_col.update_one(
            {"_id": doc["_id"]},
            {"$set": {"ended": True, "winners": [w.id for w in winners]}},
        )

    # ── Background loop ───────────────────────────────────────────────────────

    @tasks.loop(seconds=15)
    async def _check_loop(self):
        now = datetime.now(timezone.utc).timestamp()

        # End expired polls
        for doc in polls_col.find({"ended": False, "ends_at": {"$lte": now}}):
            try:
                await self._end_poll(doc)
            except Exception as e:
                logger.warning("Failed to end poll %s: %s", doc.get("message_id"), e)
                polls_col.update_one({"_id": doc["_id"]}, {"$set": {"ended": True}})

        # End expired giveaways
        for doc in giveaways_col.find({"ended": False, "ends_at": {"$lte": now}}):
            try:
                await self._end_giveaway(doc)
            except Exception as e:
                logger.warning("Failed to end giveaway %s: %s", doc.get("message_id"), e)
                giveaways_col.update_one({"_id": doc["_id"]}, {"$set": {"ended": True}})

    @_check_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(GiveawayCog(bot))

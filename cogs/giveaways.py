"""
Polls & Giveaways cog — hybrid commands (prefix ! and slash /).

POLLS
─────
/poll  duration question option1 option2 [option3…option8]
/quickpoll question

GIVEAWAYS
─────────
/gstart  duration winners prize [require_role] [blacklist_role]
         [bonus_role] [bonus_amount]
/gend    message_id
/greroll message_id
/glist
"""

import logging
import random
import re
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import OWNER_IDS
from database import polls_col, giveaways_col

logger = logging.getLogger("weekly-xp-bot")

# ── Colours ───────────────────────────────────────────────────────────────────
POLL_COLOR     = 0x5865F2
GIVEAWAY_COLOR = 0xF1C40F
END_COLOR      = 0x4F545C

NUMBER_EMOJIS = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣"]
YES_EMOJI, NO_EMOJI = "👍", "👎"

# ── Duration helpers ──────────────────────────────────────────────────────────
_DUR_RE = re.compile(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")

def parse_duration(text: str) -> int | None:
    m = _DUR_RE.fullmatch(text.strip())
    if not m or not any(m.groups()):
        return None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    total = d * 86400 + h * 3600 + mi * 60 + s
    return total if total > 0 else None

def fmt_duration(seconds: int) -> str:
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

def is_mod(ctx: commands.Context) -> bool:
    if ctx.author.id in OWNER_IDS:
        return True
    if isinstance(ctx.author, discord.Member):
        return ctx.author.guild_permissions.manage_guild
    return False

# ── Giveaway embed ────────────────────────────────────────────────────────────
def build_giveaway_embed(
    *,
    prize: str,
    winner_count: int,
    ends_dt: datetime,
    host: discord.Member | discord.User,
    require_role: Optional[discord.Role],
    blacklist_role: Optional[discord.Role],
    bonus_role: Optional[discord.Role],
    bonus_amount: int,
    entry_count: int,
    description: Optional[str] = None,
) -> discord.Embed:
    lines = ["**Click the button below to enter!**\n"]
    if description:
        lines.append(f"📝  {description}\n")
    lines.append(f"🏆  **Winners:** {winner_count}")
    lines.append(f"⏱️  **Ends:** {fmt_ts(ends_dt)}")
    lines.append(f"👤  **Hosted by:** {host.mention}")
    if require_role:
        lines.append(f"🔒  **Required role:** {require_role.mention}")
    if blacklist_role:
        lines.append(f"🚫  **Blacklisted:** {blacklist_role.mention}")
    if bonus_role and bonus_amount > 1:
        lines.append(f"⭐  **Bonus entries:** {bonus_role.mention} ×{bonus_amount}")
    lines.append(f"\n🎟️  **Entries:** {entry_count}")

    embed = discord.Embed(
        title=f"🎉  {prize}",
        description="\n".join(lines),
        color=GIVEAWAY_COLOR,
        timestamp=ends_dt,
    )
    embed.set_footer(text="Ends at")
    return embed

# ── Persistent entry button ───────────────────────────────────────────────────
class GiveawayView(discord.ui.View):
    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id
        btn = discord.ui.Button(
            label="Enter Giveaway",
            emoji="🎉",
            style=discord.ButtonStyle.primary,
            custom_id=f"giveaway_enter:{message_id}",
        )
        btn.callback = self._enter_callback
        self.add_item(btn)

    async def _enter_callback(self, interaction: discord.Interaction):
        doc = giveaways_col.find_one({"message_id": self.message_id})
        if not doc or doc.get("ended"):
            return await interaction.response.send_message(
                "❌ This giveaway has already ended.", ephemeral=True
            )

        member       = interaction.user
        member_roles = {r.id for r in member.roles}

        # Blacklist
        bl = doc.get("blacklist_role_id")
        if bl and bl in member_roles:
            role = interaction.guild.get_role(bl)
            return await interaction.response.send_message(
                f"❌ You have the **{role.name if role else 'blacklisted'}** role and cannot enter.",
                ephemeral=True,
            )

        # Required role
        rr = doc.get("require_role_id")
        if rr and rr not in member_roles:
            return await interaction.response.send_message(
                f"❌ You need <@&{rr}> to enter this giveaway.",
                ephemeral=True,
            )

        uid     = member.id
        entries = doc.get("entries", [])

        if uid in entries:
            new_entries = [e for e in entries if e != uid]
            giveaways_col.update_one(
                {"message_id": self.message_id}, {"$set": {"entries": new_entries}}
            )
            msg = "↩️  You have **left** the giveaway."
        else:
            # Bonus multiplier
            br  = doc.get("bonus_role_id")
            bam = doc.get("bonus_amount", 1)
            mult = bam if (br and br in member_roles) else 1
            new_entries = entries + [uid] * mult
            giveaways_col.update_one(
                {"message_id": self.message_id}, {"$set": {"entries": new_entries}}
            )
            msg = (
                f"✅  Entered with **{mult} entries**! Good luck! 🍀"
                if mult > 1 else
                "✅  You're in! Good luck! 🍀"
            )

        unique_count = len(set(new_entries))

        # Refresh embed
        ends_dt = datetime.fromtimestamp(doc["ends_at"], tz=timezone.utc)
        guild   = interaction.guild
        host    = guild.get_member(doc["host_id"]) or await interaction.client.fetch_user(doc["host_id"])

        def _get_role(rid):
            return guild.get_role(rid) if rid else None

        embed = build_giveaway_embed(
            prize         = doc["prize"],
            winner_count  = doc["winner_count"],
            ends_dt       = ends_dt,
            host          = host,
            require_role  = _get_role(doc.get("require_role_id")),
            blacklist_role= _get_role(doc.get("blacklist_role_id")),
            bonus_role    = _get_role(doc.get("bonus_role_id")),
            bonus_amount  = doc.get("bonus_amount", 1),
            entry_count   = unique_count,
            description   = doc.get("description"),
        )
        try:
            await interaction.message.edit(embed=embed)
        except discord.HTTPException:
            pass

        await interaction.response.send_message(msg, ephemeral=True)

# ── Cog ───────────────────────────────────────────────────────────────────────
class GiveawayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        for doc in giveaways_col.find({"ended": False}):
            view = GiveawayView(doc["message_id"])
            self.bot.add_view(view, message_id=doc["message_id"])
        self._check_loop.start()

    def cog_unload(self):
        self._check_loop.cancel()

    # ══════════════════════════════════════════════════════════════════════════
    #  POLLS
    # ══════════════════════════════════════════════════════════════════════════

    @commands.hybrid_command(name="poll")
    @app_commands.describe(
        duration="Duration: 10m · 1h · 1d · 1h30m",
        question="The poll question",
        option1="Option 1", option2="Option 2",
        option3="Option 3 (optional)", option4="Option 4 (optional)",
        option5="Option 5 (optional)", option6="Option 6 (optional)",
        option7="Option 7 (optional)", option8="Option 8 (optional)",
    )
    async def poll(
        self, ctx: commands.Context,
        duration: str,
        question: str,
        option1: str,
        option2: str,
        option3: Optional[str] = None,
        option4: Optional[str] = None,
        option5: Optional[str] = None,
        option6: Optional[str] = None,
        option7: Optional[str] = None,
        option8: Optional[str] = None,
    ):
        """Create a multi-option poll that closes automatically."""
        if not is_mod(ctx):
            return await ctx.send("❌ You need **Manage Server** to create polls.", ephemeral=True)

        secs = parse_duration(duration)
        if secs is None:
            return await ctx.send("❌ Invalid duration. Examples: `30m`, `1h`, `1d`", ephemeral=True)
        if secs > 7 * 86400:
            return await ctx.send("❌ Maximum poll duration is **7 days**.", ephemeral=True)

        options = [o for o in [option1, option2, option3, option4,
                                option5, option6, option7, option8] if o]

        ends_at = datetime.now(timezone.utc).timestamp() + secs
        ends_dt = datetime.fromtimestamp(ends_at, tz=timezone.utc)

        lines = [f"**{question}**\n"]
        for i, opt in enumerate(options):
            lines.append(f"{NUMBER_EMOJIS[i]}  {opt}")
        lines.append(f"\n⏱️  Ends {fmt_ts(ends_dt)}")

        embed = discord.Embed(
            title="📊  Poll",
            description="\n".join(lines),
            color=POLL_COLOR,
            timestamp=ends_dt,
        )
        embed.set_footer(text=f"Started by {ctx.author.display_name} • {fmt_duration(secs)}")

        if not ctx.interaction:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass

        msg = await ctx.send(embed=embed)
        # ctx.send with interactions returns a different object; fetch if needed
        if ctx.interaction:
            msg = await ctx.interaction.original_response()

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

    @commands.hybrid_command(name="quickpoll")
    @app_commands.describe(question="The yes/no question to ask")
    async def quickpoll(self, ctx: commands.Context, *, question: str):
        """Create a quick 👍 / 👎 poll."""
        embed = discord.Embed(
            title="📊  Quick Poll",
            description=f"**{question}**",
            color=POLL_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Asked by {ctx.author.display_name}")

        if not ctx.interaction:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass

        msg = await ctx.send(embed=embed)
        if ctx.interaction:
            msg = await ctx.interaction.original_response()

        await msg.add_reaction(YES_EMOJI)
        await msg.add_reaction(NO_EMOJI)

    async def _end_poll(self, doc: dict):
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
        for i in range(len(options)):
            rxn = discord.utils.get(msg.reactions, emoji=NUMBER_EMOJIS[i])
            counts.append(max((rxn.count - 1) if rxn else 0, 0))

        total    = sum(counts)
        max_vote = max(counts) if counts else 0

        lines = [f"**{doc['question']}**\n"]
        for i, (opt, cnt) in enumerate(zip(options, counts)):
            pct    = (cnt / total * 100) if total else 0
            bar    = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
            trophy = "  🏆" if cnt == max_vote and max_vote > 0 else ""
            lines.append(
                f"{NUMBER_EMOJIS[i]}  **{opt}**{trophy}\n"
                f"`{bar}` {cnt} vote{'s' if cnt != 1 else ''} ({pct:.1f}%)\n"
            )
        lines.append(f"**Total votes: {total}**")

        embed = discord.Embed(
            title="📊  Poll — Results",
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
    #  GIVEAWAYS
    # ══════════════════════════════════════════════════════════════════════════

    @commands.hybrid_command(name="gstart")
    @app_commands.describe(
        duration      = "Duration: 10m · 1h · 2d · 1h30m",
        winners       = "Number of winners (1–20)",
        prize         = "What you're giving away",
        description   = "Optional description shown in the giveaway embed",
        require_role  = "Users must have this role to enter",
        blacklist_role= "Users with this role cannot enter",
        bonus_role    = "This role gets extra entries",
        bonus_amount  = "How many extra entries for the bonus role (2–10)",
    )
    async def gstart(
        self, ctx: commands.Context,
        duration: str,
        winners: app_commands.Range[int, 1, 20],
        prize: str,
        description:    Optional[str] = None,
        require_role:   Optional[discord.Role] = None,
        blacklist_role: Optional[discord.Role] = None,
        bonus_role:     Optional[discord.Role] = None,
        bonus_amount:   app_commands.Range[int, 2, 10] = 2,
    ):
        """Start a giveaway with optional role requirements and bonus entries."""
        if not is_mod(ctx):
            return await ctx.send("❌ You need **Manage Server** to start giveaways.", ephemeral=True)

        secs = parse_duration(duration)
        if secs is None:
            return await ctx.send("❌ Invalid duration. Examples: `30m`, `1h`, `1d`", ephemeral=True)
        if secs > 30 * 86400:
            return await ctx.send("❌ Maximum giveaway duration is **30 days**.", ephemeral=True)

        ends_at = datetime.now(timezone.utc).timestamp() + secs
        ends_dt = datetime.fromtimestamp(ends_at, tz=timezone.utc)

        embed = build_giveaway_embed(
            prize         = prize,
            winner_count  = winners,
            ends_dt       = ends_dt,
            host          = ctx.author,
            require_role  = require_role,
            blacklist_role= blacklist_role,
            bonus_role    = bonus_role,
            bonus_amount  = bonus_amount,
            entry_count   = 0,
            description   = description,
        )

        if not ctx.interaction:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
            msg = await ctx.send(embed=embed)
        else:
            await ctx.send(embed=embed)
            msg = await ctx.interaction.original_response()

        real_view = GiveawayView(msg.id)
        self.bot.add_view(real_view, message_id=msg.id)
        await msg.edit(view=real_view)

        giveaways_col.insert_one({
            "message_id":     msg.id,
            "channel_id":     ctx.channel.id,
            "guild_id":       ctx.guild.id,
            "prize":          prize,
            "description":    description,
            "winner_count":   winners,
            "ends_at":        ends_at,
            "host_id":        ctx.author.id,
            "require_role_id":   require_role.id   if require_role   else None,
            "blacklist_role_id": blacklist_role.id if blacklist_role else None,
            "bonus_role_id":     bonus_role.id     if bonus_role     else None,
            "bonus_amount":      bonus_amount,
            "entries":        [],
            "ended":          False,
            "winners":        [],
        })

    @commands.hybrid_command(name="gend")
    @app_commands.describe(message_id="ID of the giveaway message")
    async def gend(self, ctx: commands.Context, message_id: str):
        """End a giveaway early and pick winners."""
        if not is_mod(ctx):
            return await ctx.send("❌ You need **Manage Server**.", ephemeral=True)
        try:
            mid = int(message_id)
        except ValueError:
            return await ctx.send("❌ Invalid message ID.", ephemeral=True)
        doc = giveaways_col.find_one({"message_id": mid, "guild_id": ctx.guild.id})
        if not doc:
            return await ctx.send("❌ Giveaway not found.", ephemeral=True)
        if doc.get("ended"):
            return await ctx.send("❌ Already ended.", ephemeral=True)
        await self._end_giveaway(doc)
        await ctx.send("✅ Giveaway ended!", ephemeral=True)

    @commands.hybrid_command(name="greroll")
    @app_commands.describe(message_id="ID of the ended giveaway message")
    async def greroll(self, ctx: commands.Context, message_id: str):
        """Reroll the winners of a finished giveaway."""
        if not is_mod(ctx):
            return await ctx.send("❌ You need **Manage Server**.", ephemeral=True)
        try:
            mid = int(message_id)
        except ValueError:
            return await ctx.send("❌ Invalid message ID.", ephemeral=True)
        doc = giveaways_col.find_one({"message_id": mid, "guild_id": ctx.guild.id})
        if not doc:
            return await ctx.send("❌ Giveaway not found.", ephemeral=True)
        if not doc.get("ended"):
            return await ctx.send("❌ Use `/gend` first.", ephemeral=True)

        winners = self._pick_winners(doc)
        if not winners:
            return await ctx.send("❌ No entries to reroll from.", ephemeral=True)

        channel  = self.bot.get_channel(doc["channel_id"]) or ctx.channel
        mentions = ", ".join(f"<@{uid}>" for uid in winners)
        await channel.send(
            f"🎉  **Giveaway Reroll!**\nNew winner(s) for **{doc['prize']}**: {mentions}\nCongratulations! 🎊"
        )
        giveaways_col.update_one({"_id": doc["_id"]}, {"$set": {"winners": winners}})
        await ctx.send("✅ Rerolled!", ephemeral=True)

    @commands.hybrid_command(name="glist")
    async def glist(self, ctx: commands.Context):
        """Show all active giveaways in this server."""
        docs = list(giveaways_col.find({"guild_id": ctx.guild.id, "ended": False}))
        if not docs:
            return await ctx.send("📭 No active giveaways right now.", ephemeral=True)

        embed = discord.Embed(
            title="🎉  Active Giveaways",
            color=GIVEAWAY_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        for doc in docs[:10]:
            ends_dt    = datetime.fromtimestamp(doc["ends_at"], tz=timezone.utc)
            channel    = self.bot.get_channel(doc["channel_id"])
            ch_mention = channel.mention if channel else f"<#{doc['channel_id']}>"
            entries    = len(set(doc.get("entries", [])))
            embed.add_field(
                name=f"🎁  {doc['prize']}",
                value=(
                    f"Channel: {ch_mention}\n"
                    f"Winners: **{doc['winner_count']}**\n"
                    f"Entries: **{entries}**\n"
                    f"Ends: {fmt_ts(ends_dt)}\n"
                    f"[Jump](<https://discord.com/channels/{doc['guild_id']}/{doc['channel_id']}/{doc['message_id']}>)"
                ),
                inline=True,
            )
        embed.set_footer(text=f"{len(docs)} active giveaway(s)")
        await ctx.send(embed=embed, ephemeral=True)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _pick_winners(self, doc: dict) -> list[int]:
        entries = doc.get("entries", [])
        if not entries:
            return []
        unique = list(set(entries))
        count  = min(doc["winner_count"], len(unique))
        # Weighted: shuffle the full pool (with duplicates), pick first N unique
        pool = entries[:]
        random.shuffle(pool)
        winners, seen = [], set()
        for uid in pool:
            if uid not in seen:
                winners.append(uid)
                seen.add(uid)
            if len(winners) == count:
                break
        return winners

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

        winners  = self._pick_winners(doc)
        host     = channel.guild.get_member(doc["host_id"])
        host_str = host.mention if host else f"<@{doc['host_id']}>"

        if winners:
            w_mentions = ", ".join(f"<@{uid}>" for uid in winners)
            desc = f"🏆  **Winner{'s' if len(winners) > 1 else ''}:** {w_mentions}\n👤  **Hosted by:** {host_str}"
        else:
            w_mentions = None
            desc = f"⚠️  **No valid entries**\n👤  **Hosted by:** {host_str}"

        embed = discord.Embed(
            title=f"🎉  {doc['prize']} — Ended",
            description=desc,
            color=END_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="Giveaway ended")

        disabled_view = discord.ui.View()
        disabled_view.add_item(discord.ui.Button(
            label="Giveaway Ended",
            emoji="🔒",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            custom_id=f"giveaway_ended:{doc['message_id']}",
        ))

        try:
            await msg.edit(embed=embed, view=disabled_view)
        except Exception:
            pass

        if w_mentions:
            await channel.send(
                f"🎊  Congratulations {w_mentions}! You won **{doc['prize']}**!\n*(Hosted by {host_str})*"
            )
        else:
            await channel.send(
                f"😔  No valid entries for **{doc['prize']}** — giveaway ended with no winner."
            )

        giveaways_col.update_one(
            {"_id": doc["_id"]},
            {"$set": {"ended": True, "winners": winners}},
        )

    @tasks.loop(seconds=15)
    async def _check_loop(self):
        now = datetime.now(timezone.utc).timestamp()
        for doc in polls_col.find({"ended": False, "ends_at": {"$lte": now}}):
            try:
                await self._end_poll(doc)
            except Exception as e:
                logger.warning("Poll end error %s: %s", doc.get("message_id"), e)
                polls_col.update_one({"_id": doc["_id"]}, {"$set": {"ended": True}})
        for doc in giveaways_col.find({"ended": False, "ends_at": {"$lte": now}}):
            try:
                await self._end_giveaway(doc)
            except Exception as e:
                logger.warning("Giveaway end error %s: %s", doc.get("message_id"), e)
                giveaways_col.update_one({"_id": doc["_id"]}, {"$set": {"ended": True}})

    @_check_loop.before_loop
    async def _before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(GiveawayCog(bot))

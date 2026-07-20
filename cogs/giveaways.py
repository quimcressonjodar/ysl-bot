"""
Polls & Giveaways cog — professional, full-featured.

POLLS
─────
!poll <duration> <question> | <opt1> | <opt2> ...   multi-choice (up to 10)
!quickpoll <question>                                yes / no

GIVEAWAYS
─────────
!gstart <duration> <winners>w <prize>
        [--require @role1 @role2]     must have at least one role
        [--blacklist @role1 @role2]   cannot have any of these roles
        [--bonus @role1:2 @role2:3]   extra entries multiplier per role
!gend <message_id>                    end early & pick winners
!greroll <message_id>                 reroll winners
!glist                                list active giveaways

Duration format: 30s · 10m · 2h · 1d  (combinable: 1h30m)
"""

import logging
import random
import re
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from config import OWNER_IDS
from database import polls_col, giveaways_col

logger = logging.getLogger("weekly-xp-bot")

# ── Colours & constants ───────────────────────────────────────────────────────

POLL_COLOR     = 0x5865F2   # Discord blurple
GIVEAWAY_COLOR = 0xF1C40F   # Gold
WIN_COLOR      = 0x57F287   # Green
END_COLOR      = 0x4F545C   # Grey

NUMBER_EMOJIS = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
YES_EMOJI = "👍"
NO_EMOJI  = "👎"

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

# ── Permission helper ─────────────────────────────────────────────────────────

def is_mod(ctx: commands.Context) -> bool:
    if ctx.author.id in OWNER_IDS:
        return True
    if isinstance(ctx.author, discord.Member):
        return ctx.author.guild_permissions.manage_guild
    return False

# ── Giveaway flag parser ──────────────────────────────────────────────────────

def _parse_role_ids(text: str, guild: discord.Guild) -> list[int]:
    """Extract role IDs from a space-separated list of mentions / names."""
    ids = []
    for token in text.split():
        # <@&12345>
        m = re.match(r"<@&(\d+)>", token)
        if m:
            ids.append(int(m.group(1)))
            continue
        # bare ID
        if token.isdigit():
            ids.append(int(token))
            continue
        # name
        role = discord.utils.find(lambda r: r.name.lower() == token.lower(), guild.roles)
        if role:
            ids.append(role.id)
    return ids

def _parse_bonus(text: str, guild: discord.Guild) -> dict[int, int]:
    """
    Parse bonus role tokens like '@Booster:2 @VIP:3'.
    Returns {role_id: multiplier}.
    """
    result = {}
    for token in text.split():
        # <@&12345>:N  or  Name:N
        m = re.match(r"(<@&\d+>|\d+|\S+):(\d+)", token)
        if not m:
            continue
        role_part, mult = m.group(1), int(m.group(2))
        rm = re.match(r"<@&(\d+)>", role_part)
        if rm:
            result[int(rm.group(1))] = mult
        elif role_part.isdigit():
            result[int(role_part)] = mult
        else:
            role = discord.utils.find(lambda r: r.name.lower() == role_part.lower(), guild.roles)
            if role:
                result[role.id] = mult
    return result

def _split_flags(text: str) -> dict[str, str]:
    """
    Split a string like 'Prize Name --require @A --blacklist @B --bonus @C:2'
    into {'_': 'Prize Name', 'require': '@A', 'blacklist': '@B', 'bonus': '@C:2'}.
    """
    result: dict[str, str] = {}
    parts  = re.split(r"\s+--(\w+)", text)
    # parts[0] is the text before any flag
    result["_"] = parts[0].strip()
    it = iter(parts[1:])
    for key in it:
        val = next(it, "").strip()
        result[key] = val
    return result

# ── Giveaway embed builder ────────────────────────────────────────────────────

def build_giveaway_embed(
    *,
    prize: str,
    winner_count: int,
    ends_dt: datetime,
    host: discord.Member | discord.User,
    required_role_ids: list[int],
    blacklisted_role_ids: list[int],
    bonus_roles: dict[int, int],
    entry_count: int,
    guild: discord.Guild,
) -> discord.Embed:
    lines = [f"**Click the button below to enter!**\n"]
    lines.append(f"🏆  **Winners:** {winner_count}")
    lines.append(f"⏱️  **Ends:** {fmt_ts(ends_dt)}")
    lines.append(f"👤  **Hosted by:** {host.mention}")

    if required_role_ids:
        roles = [f"<@&{rid}>" for rid in required_role_ids]
        lines.append(f"🔒  **Required role:** {' or '.join(roles)}")

    if blacklisted_role_ids:
        roles = [f"<@&{rid}>" for rid in blacklisted_role_ids]
        lines.append(f"🚫  **Blacklisted:** {' '.join(roles)}")

    if bonus_roles:
        parts = []
        for rid, mult in bonus_roles.items():
            parts.append(f"<@&{rid}> ×{mult}")
        lines.append(f"⭐  **Bonus entries:** {', '.join(parts)}")

    lines.append(f"\n🎟️  **Entries:** {entry_count}")

    embed = discord.Embed(
        title=f"🎉  {prize}",
        description="\n".join(lines),
        color=GIVEAWAY_COLOR,
        timestamp=ends_dt,
    )
    embed.set_footer(text="Ends at")
    return embed

# ── Persistent giveaway button view ──────────────────────────────────────────

class GiveawayView(discord.ui.View):
    """
    Persistent view — survives bot restarts.
    One instance per active giveaway message.
    """
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

        # Blacklist check
        for rid in doc.get("blacklisted_role_ids", []):
            if rid in member_roles:
                role = interaction.guild.get_role(rid)
                return await interaction.response.send_message(
                    f"❌ You have the **{role.name if role else 'blacklisted'}** role and cannot enter.",
                    ephemeral=True,
                )

        # Required role check
        required = doc.get("required_role_ids", [])
        if required and not any(rid in member_roles for rid in required):
            mentions = " or ".join(f"<@&{rid}>" for rid in required)
            return await interaction.response.send_message(
                f"❌ You need one of these roles to enter: {mentions}",
                ephemeral=True,
            )

        uid     = member.id
        entries = doc.get("entries", [])

        # Toggle: leave if already entered
        if uid in entries:
            new_entries = [e for e in entries if e != uid]
            giveaways_col.update_one(
                {"message_id": self.message_id},
                {"$set": {"entries": new_entries}},
            )
            unique_count = len(set(new_entries))
            await interaction.response.send_message(
                "↩️  You have **left** the giveaway.", ephemeral=True
            )
        else:
            # Bonus multiplier — take the highest applicable
            mult = 1
            for rid, m in doc.get("bonus_roles", {}).items():
                if int(rid) in member_roles:
                    mult = max(mult, m)
            new_entries = entries + [uid] * mult
            giveaways_col.update_one(
                {"message_id": self.message_id},
                {"$set": {"entries": new_entries}},
            )
            unique_count = len(set(new_entries))
            if mult > 1:
                await interaction.response.send_message(
                    f"✅  Entered with **{mult} entries**! Good luck! 🍀", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "✅  You're in! Good luck! 🍀", ephemeral=True
                )

        # Refresh embed entry count
        ends_dt = datetime.fromtimestamp(doc["ends_at"], tz=timezone.utc)
        guild   = interaction.guild
        host    = guild.get_member(doc["host_id"]) or await interaction.client.fetch_user(doc["host_id"])
        embed   = build_giveaway_embed(
            prize               = doc["prize"],
            winner_count        = doc["winner_count"],
            ends_dt             = ends_dt,
            host                = host,
            required_role_ids   = doc.get("required_role_ids", []),
            blacklisted_role_ids= doc.get("blacklisted_role_ids", []),
            bonus_roles         = {int(k): v for k, v in doc.get("bonus_roles", {}).items()},
            entry_count         = unique_count,
            guild               = guild,
        )
        try:
            await interaction.message.edit(embed=embed)
        except discord.HTTPException:
            pass


# ── Main cog ──────────────────────────────────────────────────────────────────

class GiveawayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Re-register persistent views for all active giveaways on (re)start
        for doc in giveaways_col.find({"ended": False}):
            view = GiveawayView(doc["message_id"])
            self.bot.add_view(view, message_id=doc["message_id"])
        self._check_loop.start()

    def cog_unload(self):
        self._check_loop.cancel()

    # ══════════════════════════════════════════════════════════════════════════
    #  POLLS
    # ══════════════════════════════════════════════════════════════════════════

    @commands.command(name="poll")
    async def poll(self, ctx: commands.Context, duration: str, *, rest: str):
        """
        Multi-option poll with auto-close and results.
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

        parts    = [p.strip() for p in rest.split("|")]
        question = parts[0]
        options  = parts[1:11]
        if len(options) < 2:
            return await ctx.send(
                "❌ Need a question **and at least 2 options**.\n"
                "Usage: `!poll 10m Question? | Option A | Option B`",
                delete_after=10,
            )

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
        """Quick yes/no poll. Usage: !quickpoll Should we host a giveaway?"""
        embed = discord.Embed(
            title="📊  Quick Poll",
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
            pct     = (cnt / total * 100) if total else 0
            filled  = int(pct / 10)
            bar     = "█" * filled + "░" * (10 - filled)
            winner  = "  🏆" if cnt == max_vote and max_vote > 0 else ""
            lines.append(f"{NUMBER_EMOJIS[i]}  **{opt}**{winner}\n`{bar}` {cnt} vote{'s' if cnt != 1 else ''} ({pct:.1f}%)\n")
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

    @commands.command(name="gstart")
    async def gstart(self, ctx: commands.Context, duration: str, winners: str, *, rest: str):
        """
        Start a giveaway.
        Usage: !gstart <duration> <winners>w <prize>
               [--require @role1 @role2]
               [--blacklist @role1 @role2]
               [--bonus @role1:2 @role2:3]
        Example: !gstart 1h 2w Discord Nitro --require @Member --bonus @Booster:3
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
        if not 1 <= winner_count <= 20:
            return await ctx.send("❌ Winners must be between 1 and 20.", delete_after=8)

        flags = _split_flags(rest)
        prize = flags.get("_", "").strip()
        if not prize:
            return await ctx.send("❌ Please provide a prize name.", delete_after=8)

        guild                = ctx.guild
        required_role_ids    = _parse_role_ids(flags.get("require",   ""), guild)
        blacklisted_role_ids = _parse_role_ids(flags.get("blacklist", ""), guild)
        bonus_roles          = _parse_bonus(flags.get("bonus", ""), guild)

        ends_at = datetime.now(timezone.utc).timestamp() + secs
        ends_dt = datetime.fromtimestamp(ends_at, tz=timezone.utc)

        embed = build_giveaway_embed(
            prize                = prize,
            winner_count         = winner_count,
            ends_dt              = ends_dt,
            host                 = ctx.author,
            required_role_ids    = required_role_ids,
            blacklisted_role_ids = blacklisted_role_ids,
            bonus_roles          = bonus_roles,
            entry_count          = 0,
            guild                = guild,
        )

        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        view = GiveawayView.__new__(GiveawayView)
        discord.ui.View.__init__(view, timeout=None)
        view.message_id = 0   # placeholder — updated after send
        btn = discord.ui.Button(
            label="Enter Giveaway",
            emoji="🎉",
            style=discord.ButtonStyle.primary,
            custom_id="__placeholder__",
        )
        view.add_item(btn)

        msg = await ctx.channel.send(embed=embed)

        # Now create the real view with the correct message_id
        real_view = GiveawayView(msg.id)
        self.bot.add_view(real_view, message_id=msg.id)
        await msg.edit(view=real_view)

        doc = {
            "message_id":           msg.id,
            "channel_id":           ctx.channel.id,
            "guild_id":             guild.id,
            "prize":                prize,
            "winner_count":         winner_count,
            "ends_at":              ends_at,
            "host_id":              ctx.author.id,
            "required_role_ids":    required_role_ids,
            "blacklisted_role_ids": blacklisted_role_ids,
            "bonus_roles":          {str(k): v for k, v in bonus_roles.items()},
            "entries":              [],
            "ended":                False,
            "winners":              [],
        }
        giveaways_col.insert_one(doc)

    @commands.command(name="gend")
    async def gend(self, ctx: commands.Context, message_id: int):
        """End a giveaway early. Usage: !gend <message_id>"""
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
            return await ctx.send("❌ Use `!gend` first.", delete_after=8)

        winners = self._pick_winners(doc)
        if not winners:
            return await ctx.send("❌ No entries to reroll from.", delete_after=8)

        channel = self.bot.get_channel(doc["channel_id"]) or ctx.channel
        mentions = ", ".join(f"<@{uid}>" for uid in winners)
        await channel.send(
            f"🎉  **Giveaway Reroll!**\nNew winner(s) for **{doc['prize']}**: {mentions}\nCongratulations! 🎊"
        )
        giveaways_col.update_one({"_id": doc["_id"]}, {"$set": {"winners": winners}})

    @commands.command(name="glist")
    async def glist(self, ctx: commands.Context):
        """List all active giveaways in this server."""
        docs = list(giveaways_col.find({"guild_id": ctx.guild.id, "ended": False}))
        if not docs:
            return await ctx.send("📭 No active giveaways right now.")

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
                    f"[Jump to message](<https://discord.com/channels/{doc['guild_id']}/{doc['channel_id']}/{doc['message_id']}>)"
                ),
                inline=True,
            )
        embed.set_footer(text=f"{len(docs)} active giveaway(s)")
        await ctx.send(embed=embed)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _pick_winners(self, doc: dict) -> list[int]:
        """Weighted random selection from entries list (bonus roles already baked in)."""
        entries = doc.get("entries", [])
        if not entries:
            return []
        pool    = entries  # duplicates = extra weight
        unique  = list(set(entries))
        count   = min(doc["winner_count"], len(unique))
        # Weighted sample: pick from pool, deduplicate as we go
        winners = []
        remaining = list(pool)
        seen = set()
        random.shuffle(remaining)
        for uid in remaining:
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

        # Disable the button
        disabled_view = discord.ui.View()
        disabled_btn  = discord.ui.Button(
            label="Giveaway Ended",
            emoji="🔒",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            custom_id=f"giveaway_ended:{doc['message_id']}",
        )
        disabled_view.add_item(disabled_btn)

        try:
            await msg.edit(embed=embed, view=disabled_view)
        except Exception:
            pass

        if w_mentions:
            await channel.send(
                f"🎊  Congratulations {w_mentions}! You won **{doc['prize']}**!\n"
                f"*(Hosted by {host_str})*"
            )
        else:
            await channel.send(
                f"😔  No valid entries for **{doc['prize']}** — giveaway ended with no winner."
            )

        giveaways_col.update_one(
            {"_id": doc["_id"]},
            {"$set": {"ended": True, "winners": winners}},
        )

    # ── Background loop ───────────────────────────────────────────────────────

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

"""Message-based leveling system with rank cards, leaderboards, and role rewards."""

import logging
import random
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import LEVEL_ROLES, XP_COOLDOWN, XP_MIN, XP_MAX
from database import levels_col
from utils.level_card import generate_rank_card

logger = logging.getLogger("weekly-xp-bot")

# ── XP math ───────────────────────────────────────────────────────────────────

def xp_to_next(level: int) -> int:
    """XP required to advance from `level` to `level + 1`."""
    return 5 * level * level + 50 * level + 100


def compute_level(total_xp: int) -> tuple[int, int, int]:
    """Return (level, xp_in_current_level, xp_needed_for_next_level)."""
    level = 0
    cumulative = 0
    while True:
        needed = xp_to_next(level)
        if cumulative + needed > total_xp:
            return level, total_xp - cumulative, needed
        cumulative += needed
        level += 1
        if level > 1_000:
            return level, 0, xp_to_next(level)


# ── Pagination view ───────────────────────────────────────────────────────────

class LeaderboardView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=120)
        self.pages = pages
        self.current = 0
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current == len(self.pages) - 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)


# ── Cog ───────────────────────────────────────────────────────────────────────

class LevelingCog(commands.Cog):
    """Awards XP for messages, tracks levels, and assigns roles at milestones."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory cooldown: user_id → timestamp of last XP award
        self._cooldown: dict[int, float] = {}

    # ── XP internals ──────────────────────────────────────────────────────────

    def _get_doc(self, user_id: str) -> dict:
        return levels_col.find_one({"_id": user_id}) or {
            "_id": user_id, "xp": 0, "level": 0, "messages": 0,
        }

    def _add_xp(self, user_id: str, amount: int) -> tuple[int, int, bool]:
        """
        Increment the user's XP and message count.
        Returns (old_level, new_level, leveled_up).
        """
        doc = self._get_doc(user_id)
        old_level = doc.get("level", 0)
        new_xp = doc.get("xp", 0) + amount
        new_messages = doc.get("messages", 0) + 1
        new_level, _, _ = compute_level(new_xp)

        levels_col.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "xp": new_xp,
                    "level": new_level,
                    "messages": new_messages,
                    "last_active": datetime.now(timezone.utc),
                },
            },
            upsert=True,
        )
        return old_level, new_level, new_level > old_level

    def _get_rank(self, user_id: str, sort_field: str = "xp") -> int:
        doc = self._get_doc(user_id)
        value = doc.get(sort_field, 0)
        return levels_col.count_documents({sort_field: {"$gt": value}}) + 1

    # ── Role helpers ──────────────────────────────────────────────────────────

    async def _assign_level_role(
        self, member: discord.Member, new_level: int
    ) -> discord.Role | None:
        """Give the member the highest earned level role. Returns the role if newly granted."""
        guild = member.guild
        earned = [lvl for lvl in sorted(LEVEL_ROLES) if lvl <= new_level]
        if not earned:
            return None

        highest = earned[-1]
        role_id = LEVEL_ROLES.get(highest, 0)
        if not role_id:
            return None

        role = guild.get_role(role_id)
        if role is None or role in member.roles:
            return None

        try:
            await member.add_roles(role, reason=f"Reached Level {highest}")
            return role
        except discord.HTTPException:
            return None

    # ── Listener ──────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if not message.content.strip() and not message.attachments:
            return

        user_id = message.author.id
        now = time.monotonic()

        # Always count the message, but only award XP after the cooldown.
        if now - self._cooldown.get(user_id, 0) < XP_COOLDOWN:
            levels_col.update_one(
                {"_id": str(user_id)},
                {"$inc": {"messages": 1}},
                upsert=True,
            )
            return

        self._cooldown[user_id] = now
        amount = random.randint(XP_MIN, XP_MAX)
        old_level, new_level, leveled_up = self._add_xp(str(user_id), amount)

        if not leveled_up:
            return

        # ── Level-up announcement ─────────────────────────────────────────────
        _, xp_in, xp_need = compute_level(self._get_doc(str(user_id)).get("xp", 0))
        embed = discord.Embed(
            description=f"🎉 {message.author.mention} just reached **Level {new_level}**!",
            color=0x00DCFF,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f"Next level: {xp_need - xp_in:,} XP to go")

        if isinstance(message.author, discord.Member):
            role = await self._assign_level_role(message.author, new_level)
            if role:
                embed.add_field(name="🏅 Role Unlocked", value=role.mention, inline=False)

        try:
            await message.channel.send(embed=embed)
        except discord.HTTPException:
            pass

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="rank", description="Show your (or another user's) level card")
    @app_commands.describe(member="The member to look up (defaults to yourself)")
    async def rank(self, ctx: commands.Context, member: discord.Member | None = None):
        target = member or ctx.author
        await ctx.defer()

        doc = self._get_doc(str(target.id))
        total_xp = doc.get("xp", 0)
        level, xp_in, xp_need = compute_level(total_xp)
        rank = self._get_rank(str(target.id), "xp")
        messages = doc.get("messages", 0)

        try:
            buf = await generate_rank_card(target, level, xp_in, xp_need, rank, messages)
            await ctx.send(file=discord.File(buf, filename=f"rank_{target.id}.png"))
        except Exception as e:
            logger.error("Rank card generation failed: %s", e)
            embed = discord.Embed(color=0x00DCFF)
            embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
            embed.add_field(name="Level",    value=str(level),                inline=True)
            embed.add_field(name="Rank",     value=f"#{rank}",                inline=True)
            embed.add_field(name="XP",       value=f"{xp_in:,} / {xp_need:,}", inline=True)
            embed.add_field(name="Messages", value=f"{messages:,}",           inline=True)
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="lvltop", description="Leaderboard sorted by level / XP")
    @app_commands.describe(page="Page number (default: 1)")
    async def lvltop(self, ctx: commands.Context, page: int = 1):
        await ctx.defer()
        await self._send_leaderboard(
            ctx, sort_field="xp",
            title="🏆 Level Leaderboard",
            row_fn=self._level_row, page=page,
        )

    @commands.hybrid_command(name="msgtop", description="Leaderboard sorted by message count")
    @app_commands.describe(page="Page number (default: 1)")
    async def msgtop(self, ctx: commands.Context, page: int = 1):
        await ctx.defer()
        await self._send_leaderboard(
            ctx, sort_field="messages",
            title="💬 Messages Leaderboard",
            row_fn=self._msg_row, page=page,
        )

    # ── Leaderboard helpers ───────────────────────────────────────────────────

    PER_PAGE = 10

    async def _send_leaderboard(
        self,
        ctx: commands.Context,
        sort_field: str,
        title: str,
        row_fn,
        page: int,
    ) -> None:
        total = levels_col.count_documents({sort_field: {"$gt": 0}})
        if total == 0:
            return await ctx.send("No data yet — start chatting to appear here!")

        total_pages = max((total + self.PER_PAGE - 1) // self.PER_PAGE, 1)
        page = max(1, min(page, total_pages))

        all_docs = list(
            levels_col.find({sort_field: {"$gt": 0}})
            .sort(sort_field, -1)
            .skip((page - 1) * self.PER_PAGE)
            .limit(self.PER_PAGE)
        )

        caller_id = str(ctx.author.id)
        caller_doc = self._get_doc(caller_id)
        caller_rank = levels_col.count_documents(
            {sort_field: {"$gt": caller_doc.get(sort_field, 0)}}
        ) + 1

        embed = discord.Embed(
            title=f"{title} — Page {page}/{total_pages}",
            color=0x00DCFF,
            timestamp=datetime.now(timezone.utc),
        )
        lines = []
        global_start = (page - 1) * self.PER_PAGE
        for i, doc in enumerate(all_docs):
            pos = global_start + i + 1
            user = self.bot.get_user(int(doc["_id"]))
            name = user.mention if user else f"`{doc['_id']}`"
            lines.append(f"**{pos}.** {name} — {row_fn(doc)}")

        embed.description = "\n".join(lines) or "No entries on this page."
        embed.set_footer(text=f"Your position: #{caller_rank}")
        await ctx.send(embed=embed)

    def _level_row(self, doc: dict) -> str:
        level, _, _ = compute_level(doc.get("xp", 0))
        return f"Level **{level}** • {doc.get('xp', 0):,} XP"

    def _msg_row(self, doc: dict) -> str:
        level, _, _ = compute_level(doc.get("xp", 0))
        return f"**{doc.get('messages', 0):,}** messages • Level {level}"

    # ── /createlevelroles ─────────────────────────────────────────────────────

    @app_commands.command(
        name="createlevelroles",
        description="Create all level milestone roles and return their IDs (Admin only)",
    )
    @app_commands.default_permissions(administrator=True)
    async def createlevelroles(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        ROLE_DEFS = [
            ("Level 1",  discord.Color(0x80DEEA)),  # light cyan
            ("Level 5",  discord.Color(0x4DD0E1)),  # cyan
            ("Level 10", discord.Color(0x26C6DA)),  # medium cyan
            ("Level 15", discord.Color(0x00ACC1)),  # cyan-teal
            ("Level 20", discord.Color(0x0097A7)),  # teal
            ("Level 30", discord.Color(0x006064)),  # deep teal  ← tone shift
            ("Level 50", discord.Color(0x01579B)),  # deep blue (same cool family)
        ]

        lines = []
        failed = []
        for name, color in ROLE_DEFS:
            try:
                role = await interaction.guild.create_role(
                    name=name,
                    color=color,
                    reason="Level milestone role — created by /createlevelroles",
                )
                lines.append(f"**{name}** → `{role.id}`")
            except discord.HTTPException as e:
                failed.append(f"**{name}**: {e}")

        result = "✅ **Level roles created — send these IDs to the bot admin:**\n\n"
        result += "\n".join(lines)
        if failed:
            result += "\n\n❌ **Failed:**\n" + "\n".join(failed)

        await interaction.followup.send(result, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingCog(bot))

"""Message-based leveling system with rank cards, embed leaderboards, and role rewards."""

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

EMBED_COLOR = 0x00B4FF   # bright blue — matches the cyan accent

# ── XP math ───────────────────────────────────────────────────────────────────

def xp_to_next(level: int) -> int:
    return 5 * level * level + 50 * level + 100


def compute_level(total_xp: int) -> tuple[int, int, int]:
    """Return (level, xp_in_current_level, xp_needed_for_next_level)."""
    level, cumulative = 0, 0
    while True:
        needed = xp_to_next(level)
        if cumulative + needed > total_xp:
            return level, total_xp - cumulative, needed
        cumulative += needed
        level += 1
        if level > 1_000:
            return level, 0, xp_to_next(level)


# ── Go To Page modal ──────────────────────────────────────────────────────────

class GoToPageModal(discord.ui.Modal, title="Go to page"):
    page_input = discord.ui.TextInput(
        label="Page number",
        placeholder="Enter a number…",
        min_length=1,
        max_length=6,
    )

    def __init__(self, view: "LeaderboardView"):
        super().__init__()
        self._view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_input.value)
        except ValueError:
            return await interaction.response.send_message(
                "Please enter a valid number.", ephemeral=True
            )
        page = max(1, min(page, self._view.total_pages))
        self._view.current_page = page
        self._view._update_buttons()
        embed = await self._view._build_embed()
        await interaction.response.edit_message(embed=embed, view=self._view)


# ── Leaderboard View ──────────────────────────────────────────────────────────

class LeaderboardView(discord.ui.View):
    PER_PAGE = 10

    def __init__(
        self,
        cog: "LevelingCog",
        caller: discord.Member | discord.User,
        sort_field: str,
        title: str,
        stat_fn,
        total_pages: int,
        current_page: int = 1,
    ):
        super().__init__(timeout=120)
        self.cog          = cog
        self.caller       = caller
        self.sort_field   = sort_field
        self.title        = title
        self.stat_fn      = stat_fn
        self.total_pages  = total_pages
        self.current_page = current_page
        self.message: discord.Message | None = None
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_btn.disabled = self.current_page <= 1
        self.next_btn.disabled = self.current_page >= self.total_pages

    async def _build_embed(self) -> discord.Embed:
        page = self.current_page
        docs = list(
            levels_col.find({self.sort_field: {"$gt": 0}})
            .sort(self.sort_field, -1)
            .skip((page - 1) * self.PER_PAGE)
            .limit(self.PER_PAGE)
        )

        caller_doc  = self.cog._get_doc(str(self.caller.id))
        caller_rank = levels_col.count_documents(
            {self.sort_field: {"$gt": caller_doc.get(self.sort_field, 0)}}
        ) + 1

        lines = []
        global_start = (page - 1) * self.PER_PAGE
        for i, doc in enumerate(docs):
            pos  = global_start + i + 1
            uid  = int(doc["_id"])
            stat = self.stat_fn(doc)
            lines.append(f"{pos}. <@{uid}> - {stat}")

        embed = discord.Embed(
            title=f"🏆 {self.title} (Page {page}/{self.total_pages})",
            description="\n".join(lines) or "No entries yet.",
            color=EMBED_COLOR,
        )
        embed.set_footer(
            text=f"\U0001f50e {self.caller.display_name}'s Position: #{caller_rank}"
        )
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self._update_buttons()
        embed = await self._build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Go To Page", style=discord.ButtonStyle.primary)
    async def goto_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GoToPageModal(self))

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self._update_buttons()
        embed = await self._build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass


# ── Cog ───────────────────────────────────────────────────────────────────────

class LevelingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cooldown: dict[int, float] = {}

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _get_doc(self, user_id: str) -> dict:
        return levels_col.find_one({"_id": user_id}) or {
            "_id": user_id, "xp": 0, "level": 0, "messages": 0,
        }

    def _add_xp(self, user_id: str, amount: int) -> tuple[int, int, bool]:
        doc     = self._get_doc(user_id)
        old_lvl = doc.get("level", 0)
        new_xp  = doc.get("xp", 0) + amount
        new_msgs= doc.get("messages", 0) + 1
        new_lvl, _, _ = compute_level(new_xp)
        levels_col.update_one(
            {"_id": user_id},
            {"$set": {
                "xp": new_xp, "level": new_lvl, "messages": new_msgs,
                "last_active": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
        return old_lvl, new_lvl, new_lvl > old_lvl

    def _get_rank(self, user_id: str, sort_field: str = "xp") -> int:
        doc   = self._get_doc(user_id)
        value = doc.get(sort_field, 0)
        return levels_col.count_documents({sort_field: {"$gt": value}}) + 1

    # ── Role helper ───────────────────────────────────────────────────────────

    async def _assign_level_role(
        self, member: discord.Member, new_level: int
    ) -> discord.Role | None:
        earned = [lvl for lvl in sorted(LEVEL_ROLES) if lvl <= new_level]
        if not earned:
            return None
        role_id = LEVEL_ROLES.get(earned[-1], 0)
        if not role_id:
            return None
        role = member.guild.get_role(role_id)
        if role is None or role in member.roles:
            return None
        try:
            await member.add_roles(role, reason=f"Reached Level {earned[-1]}")
            return role
        except discord.HTTPException:
            return None

    # ── XP listener ───────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if not message.content.strip() and not message.attachments:
            return

        uid = message.author.id
        now = time.monotonic()

        if now - self._cooldown.get(uid, 0) < XP_COOLDOWN:
            levels_col.update_one(
                {"_id": str(uid)}, {"$inc": {"messages": 1}}, upsert=True
            )
            return

        self._cooldown[uid] = now
        amount = random.randint(XP_MIN, XP_MAX)
        old_lvl, new_lvl, leveled_up = self._add_xp(str(uid), amount)
        if not leveled_up:
            return

        _, xp_in, xp_need = compute_level(self._get_doc(str(uid)).get("xp", 0))
        embed = discord.Embed(
            description=f"GG {message.author.mention}, you just reached **Level {new_lvl}**!",
            color=EMBED_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f"Next level: {xp_need - xp_in:,} XP to go")

        if isinstance(message.author, discord.Member):
            role = await self._assign_level_role(message.author, new_lvl)
            if role:
                embed.add_field(name="Role Unlocked", value=role.mention, inline=False)

        try:
            await message.channel.send(embed=embed)
        except discord.HTTPException:
            pass

    # ── !rank ─────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="rank", description="Show your (or another user's) level card")
    @app_commands.describe(member="The member to look up (defaults to yourself)")
    async def rank(self, ctx: commands.Context, member: discord.Member | None = None):
        target = member or ctx.author
        await ctx.defer()

        doc      = self._get_doc(str(target.id))
        total_xp = doc.get("xp", 0)
        level, xp_in, xp_need = compute_level(total_xp)
        rank     = self._get_rank(str(target.id), "xp")
        messages = doc.get("messages", 0)

        try:
            buf = await generate_rank_card(target, level, xp_in, xp_need, rank, messages)
            await ctx.send(file=discord.File(buf, filename=f"rank_{target.id}.png"))
        except Exception as e:
            logger.error("Rank card failed: %s", e)
            embed = discord.Embed(color=EMBED_COLOR)
            embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
            embed.add_field(name="Level",    value=str(level),                  inline=True)
            embed.add_field(name="Rank",     value=f"#{rank}",                  inline=True)
            embed.add_field(name="XP",       value=f"{xp_in:,} / {xp_need:,}", inline=True)
            await ctx.send(embed=embed)

    # ── !lvltop ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="lvltop", description="Leaderboard sorted by level / XP")
    @app_commands.describe(page="Page number (default: 1)")
    async def lvltop(self, ctx: commands.Context, page: int = 1):
        await ctx.defer()
        await self._send_leaderboard(
            ctx, sort_field="xp",
            title="Leaderboard Levels",
            stat_fn=self._level_stat,
            page=page,
        )

    # ── !msgtop ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="msgtop", description="Leaderboard sorted by message count")
    @app_commands.describe(page="Page number (default: 1)")
    async def msgtop(self, ctx: commands.Context, page: int = 1):
        await ctx.defer()
        await self._send_leaderboard(
            ctx, sort_field="messages",
            title="Leaderboard Messages",
            stat_fn=self._msg_stat,
            page=page,
        )

    # ── Leaderboard sender ────────────────────────────────────────────────────

    _PER_PAGE = 10

    async def _send_leaderboard(
        self,
        ctx: commands.Context,
        sort_field: str,
        title: str,
        stat_fn,
        page: int,
    ) -> None:
        total = levels_col.count_documents({sort_field: {"$gt": 0}})
        if total == 0:
            return await ctx.send("No data yet — start chatting to appear here!")

        total_pages = max((total + self._PER_PAGE - 1) // self._PER_PAGE, 1)
        page = max(1, min(page, total_pages))

        view = LeaderboardView(
            cog=self, caller=ctx.author,
            sort_field=sort_field, title=title, stat_fn=stat_fn,
            total_pages=total_pages, current_page=page,
        )
        embed = await view._build_embed()
        msg   = await ctx.send(embed=embed, view=view)
        view.message = msg

    # ── Stat formatters ───────────────────────────────────────────────────────

    def _level_stat(self, doc: dict) -> str:
        level, _, _ = compute_level(doc.get("xp", 0))
        return f"Level {level}"

    def _msg_stat(self, doc: dict) -> str:
        return f"{doc.get('messages', 0):,} messages"

    # ── /createlevelroles ─────────────────────────────────────────────────────

    @app_commands.command(
        name="createlevelroles",
        description="Create all level milestone roles and return their IDs (Admin only)",
    )
    @app_commands.default_permissions(administrator=True)
    async def createlevelroles(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ROLE_DEFS = [
            ("Level 1",  discord.Color(0x80DEEA)),
            ("Level 5",  discord.Color(0x4DD0E1)),
            ("Level 10", discord.Color(0x26C6DA)),
            ("Level 15", discord.Color(0x00ACC1)),
            ("Level 20", discord.Color(0x0097A7)),
            ("Level 30", discord.Color(0x006064)),
            ("Level 50", discord.Color(0x01579B)),
        ]
        lines, failed = [], []
        for name, color in ROLE_DEFS:
            try:
                role = await interaction.guild.create_role(
                    name=name, color=color,
                    reason="Level milestone role — created by /createlevelroles",
                )
                lines.append(f"**{name}** → `{role.id}`")
            except discord.HTTPException as e:
                failed.append(f"**{name}**: {e}")

        result = "**Level roles created — send these IDs to the bot admin:**\n\n"
        result += "\n".join(lines)
        if failed:
            result += "\n\n**Failed:**\n" + "\n".join(failed)
        await interaction.followup.send(result, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(LevelingCog(bot))

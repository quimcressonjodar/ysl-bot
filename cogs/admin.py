from datetime import datetime, timezone
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import is_admin, parse_duration, load_warns, save_warns, get_next_warn_id, can_moderate
from database import eco_col, pets_col
from config import ROLE_SHOP, STOCKS, ADD_ALLOWED_IDS, MAX_ECONOMY_AMOUNT
from utils.stocks import stocks_col, user_stocks_col, stock_alerts_col, ipo_col
from utils.bounties import bounties_col


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="ban", description="Ban a member from the server (Admin only)")
    @app_commands.describe(member="The member to ban", reason="The reason for the ban")
    @app_commands.default_permissions(administrator=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
        if not is_admin(ctx):
            return await ctx.send("❌ You do not have permission to use this command.", ephemeral=True)
        block_reason = can_moderate(ctx, member)
        if block_reason:
            return await ctx.send(block_reason, ephemeral=True)

        dm_sent = True
        try:
            await member.send(
                embed=discord.Embed(
                    title="🔨 You Have Been Banned",
                    description=f"You were banned from **{ctx.guild.name}**.",
                    color=0xE02B2B,
                ).add_field(name="Reason", value=reason)
            )
        except discord.Forbidden:
            dm_sent = False

        try:
            await member.ban(reason=f"{reason} | Moderator: {ctx.author}")
        except Exception as e:
            return await ctx.send(f"❌ Failed to ban **{member}**: {e}", ephemeral=True)

        embed = discord.Embed(title="🔨 Member Banned", color=0xE02B2B, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        if not dm_sent:
            embed.set_footer(text=f"Moderator: {ctx.author} • Could not DM user", icon_url=ctx.author.display_avatar.url)
        else:
            embed.set_footer(text=f"Moderator: {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="unban", description="Unban a user by their Discord ID (Admin only)")
    @app_commands.describe(user_id="The unique ID of the user to unban")
    @app_commands.default_permissions(administrator=True)
    async def unban(self, ctx: commands.Context, user_id: str):
        if not is_admin(ctx):
            return await ctx.send("❌ You do not have permission to use this command.", ephemeral=True)
        try:
            uid = int(user_id)
        except ValueError:
            return await ctx.send("❌ That doesn't look like a valid user ID.", ephemeral=True)
        try:
            user = await self.bot.fetch_user(uid)
            await ctx.guild.unban(user, reason=f"Unbanned by {ctx.author}")
        except discord.NotFound:
            return await ctx.send("❌ That user is not currently banned.", ephemeral=True)
        except Exception as e:
            return await ctx.send(f"❌ Failed to unban user: {e}", ephemeral=True)

        embed = discord.Embed(title="✅ Member Unbanned", color=0x2ECC71, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=False)
        embed.set_footer(text=f"Moderator: {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="bans", description="List all banned users in this server (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def bans(self, ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("❌ You do not have permission to use this command.", ephemeral=True)
        await ctx.defer()
        entries = [entry async for entry in ctx.guild.bans(limit=100)]
        if not entries:
            return await ctx.send("✅ There are no banned users in this server.")

        embed = discord.Embed(
            title=f"🔨 Banned Users ({len(entries)})",
            color=0xE02B2B,
            timestamp=datetime.now(timezone.utc),
        )
        lines = []
        for entry in entries[:25]:
            reason = entry.reason or "No reason provided"
            lines.append(f"**{entry.user}** (`{entry.user.id}`)\n> {reason}")
        embed.description = "\n\n".join(lines)
        if len(entries) > 25:
            embed.set_footer(text=f"Showing 25 of {len(entries)} banned users.")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="kick", description="Kick a member from the server (Admin only)")
    @app_commands.describe(member="The member to kick", reason="The reason for the kick")
    @app_commands.default_permissions(administrator=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
        if not is_admin(ctx):
            return await ctx.send("❌ You do not have permission to use this command.", ephemeral=True)
        block_reason = can_moderate(ctx, member)
        if block_reason:
            return await ctx.send(block_reason, ephemeral=True)

        dm_sent = True
        try:
            await member.send(
                embed=discord.Embed(
                    title="👢 You Have Been Kicked",
                    description=f"You were kicked from **{ctx.guild.name}**.",
                    color=0xE67E22,
                ).add_field(name="Reason", value=reason)
            )
        except discord.Forbidden:
            dm_sent = False

        try:
            await member.kick(reason=f"{reason} | Moderator: {ctx.author}")
        except Exception as e:
            return await ctx.send(f"❌ Failed to kick **{member}**: {e}", ephemeral=True)

        embed = discord.Embed(title="👢 Member Kicked", color=0xE67E22, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        footer = f"Moderator: {ctx.author}" + ("" if dm_sent else " • Could not DM user")
        embed.set_footer(text=footer, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="timeout", description="Timeout/Mute a member temporarily (Admin only)")
    @app_commands.describe(member="The member", duration="Duration (e.g. 10m, 2h, 1d)", reason="Reason for timeout")
    @app_commands.default_permissions(administrator=True)
    async def timeout(self, ctx: commands.Context, member: discord.Member, duration: str, reason: str = "No reason provided"):
        if not is_admin(ctx):
            return await ctx.send("❌ You do not have permission to use this command.", ephemeral=True)
        block_reason = can_moderate(ctx, member)
        if block_reason:
            return await ctx.send(block_reason, ephemeral=True)

        time_delta = parse_duration(duration)
        if not time_delta:
            return await ctx.send(
                "❌ Invalid duration format! Use formats like `10m` (minutes), `2h` (hours), or `1d` (days).",
                ephemeral=True,
            )
        if time_delta.days > 28:
            return await ctx.send("❌ Timeouts can't exceed 28 days (Discord limit).", ephemeral=True)

        dm_sent = True
        try:
            await member.send(
                embed=discord.Embed(
                    title="🔇 You Have Been Timed Out",
                    description=f"You were timed out in **{ctx.guild.name}** for `{duration}`.",
                    color=0x95A5A6,
                ).add_field(name="Reason", value=reason)
            )
        except discord.Forbidden:
            dm_sent = False

        try:
            await member.timeout(time_delta, reason=f"{reason} | Moderator: {ctx.author}")
        except Exception as e:
            return await ctx.send(f"❌ Failed to apply timeout: {e}", ephemeral=True)

        embed = discord.Embed(title="🔇 Member Timed Out", color=0x95A5A6, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        footer = f"Moderator: {ctx.author}" + ("" if dm_sent else " • Could not DM user")
        embed.set_footer(text=footer, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="untimeout", description="Remove timeout from a member (Admin only)")
    @app_commands.describe(member="The member to untimeout")
    @app_commands.default_permissions(administrator=True)
    async def untimeout(self, ctx: commands.Context, member: discord.Member):
        if not is_admin(ctx):
            return await ctx.send("❌ You do not have permission to use this command.", ephemeral=True)
        if not member.is_timed_out():
            return await ctx.send(f"❌ **{member}** is not currently timed out.", ephemeral=True)
        try:
            await member.timeout(None, reason=f"Timeout removed by {ctx.author}")
        except Exception as e:
            return await ctx.send(f"❌ Failed to remove timeout: {e}", ephemeral=True)

        embed = discord.Embed(title="🔊 Timeout Removed", color=0x2ECC71, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.set_footer(text=f"Moderator: {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="purge", description="Purge a specified amount of messages (Admin only)")
    @app_commands.describe(amount="Amount of messages to delete")
    @app_commands.default_permissions(administrator=True)
    async def purge(self, ctx: commands.Context, amount: int):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        if amount <= 0:
            return await ctx.send("Please specify a number greater than 0.", ephemeral=True)
        await ctx.defer(ephemeral=True)
        try:
            # If prefix command, we need to delete the command message itself as well
            limit = amount if ctx.interaction else amount + 1
            deleted = await ctx.channel.purge(limit=limit)
            
            # Count excludes the command message if it was a prefix command
            count = len(deleted) if ctx.interaction else len(deleted) - 1
            
            msg = await ctx.send(f"🧹 Successfully deleted **{count}** messages.", ephemeral=True)
            
            # Auto-delete success message for prefix commands
            if not ctx.interaction:
                await asyncio.sleep(3)
                try:
                    await msg.delete()
                except discord.NotFound:
                    pass
        except Exception as e:
            await ctx.send(f"❌ Failed to purge messages: {e}", ephemeral=True)

    @commands.hybrid_command(name="warn", description="Issue a warning to a member (Admin only)")
    @app_commands.describe(member="The member to warn", reason="The reason for the warning")
    @app_commands.default_permissions(administrator=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        if not is_admin(ctx):
            return await ctx.send("❌ You do not have permission to use this command.", ephemeral=True)
        block_reason = can_moderate(ctx, member)
        if block_reason:
            return await ctx.send(block_reason, ephemeral=True)

        warns_data = load_warns()
        user_id = str(member.id)
        warns_data.setdefault(user_id, [])
        # Warn IDs are a permanent, server-wide counter — they never get
        # reused or renumbered, even after other warnings are deleted.
        warn_id = get_next_warn_id()
        new_warn = {
            "id": warn_id,
            "reason": reason,
            "moderator": ctx.author.name,
            "moderator_id": ctx.author.id,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        }
        warns_data[user_id].append(new_warn)
        save_warns(warns_data)

        dm_sent = True
        try:
            await member.send(
                embed=discord.Embed(
                    title="⚠️ You Received a Warning",
                    description=f"You were warned in **{ctx.guild.name}**.",
                    color=0xFFAA00,
                ).add_field(name="Reason", value=reason)
                .add_field(name="Total Warnings", value=str(len(warns_data[user_id])))
            )
        except discord.Forbidden:
            dm_sent = False

        embed = discord.Embed(title="⚠️ Member Warned", color=0xFFAA00, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.add_field(name="Warn ID", value=f"`{warn_id}`", inline=True)
        embed.add_field(name="Total Warnings", value=str(len(warns_data[user_id])), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        footer = f"Moderator: {ctx.author}" + ("" if dm_sent else " • Could not DM user")
        embed.set_footer(text=footer, icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="warns", description="Check a member's warning history (Admin only)")
    @app_commands.describe(member="The member to check")
    @app_commands.default_permissions(administrator=True)
    async def check_warns(self, ctx: commands.Context, member: discord.Member):
        if not is_admin(ctx):
            return await ctx.send("❌ You do not have permission to use this command.", ephemeral=True)
        warns_data = load_warns()
        user_id = str(member.id)
        user_warns = warns_data.get(user_id, [])
        if not user_warns:
            return await ctx.send(f"✅ **{member}** has a clean record (0 warnings).")

        embed = discord.Embed(
            title=f"⚠️ Warning Record: {member}",
            description=f"Total warnings: **{len(user_warns)}**",
            color=0xFFAA00,
            timestamp=datetime.now(timezone.utc),
        )
        def _sort_key(w):
            try:
                return int(w["id"])
            except (ValueError, TypeError):
                return 0
        for w in sorted(user_warns, key=_sort_key):
            embed.add_field(
                name=f"Warn ID {w['id']} • {w['date']}",
                value=f"**Reason:** {w['reason']}\n**Moderator:** {w['moderator']}",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="delwarn", description="Delete a specific warning from a member (Admin only)")
    @app_commands.describe(member="The member", warn_id="The permanent ID of the warning to remove (see !warns)")
    @app_commands.default_permissions(administrator=True)
    async def delwarn(self, ctx: commands.Context, member: discord.Member, warn_id: int):
        if not is_admin(ctx):
            return await ctx.send("❌ You do not have permission to use this command.", ephemeral=True)
        warns_data = load_warns()
        user_id = str(member.id)
        user_warns = warns_data.get(user_id, [])
        # Only remove the matching warning by its fixed ID — the remaining
        # warnings keep their original IDs, they are never renumbered.
        # Compared as strings for backwards compatibility with older warns
        # that were stored with string IDs before this system existed.
        updated_warns = [w for w in user_warns if str(w["id"]) != str(warn_id)]
        if len(updated_warns) == len(user_warns):
            return await ctx.send(f"❌ No warning with ID `{warn_id}` found for **{member}**.", ephemeral=True)
        warns_data[user_id] = updated_warns
        save_warns(warns_data)

        embed = discord.Embed(title="✅ Warning Deleted", color=0x2ECC71, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.add_field(name="Deleted Warn ID", value=f"`{warn_id}`", inline=True)
        embed.add_field(name="Remaining Warnings", value=str(len(updated_warns)), inline=True)
        embed.set_footer(text=f"Moderator: {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="clearwarns", description="Clear all warnings from a member (Admin only)")
    @app_commands.describe(member="The member to clear")
    @app_commands.default_permissions(administrator=True)
    async def clearwarns(self, ctx: commands.Context, member: discord.Member):
        if not is_admin(ctx):
            return await ctx.send("❌ You do not have permission to use this command.", ephemeral=True)
        warns_data = load_warns()
        user_id = str(member.id)
        count = len(warns_data.get(user_id, []))
        if user_id in warns_data:
            del warns_data[user_id]
            save_warns(warns_data)

        embed = discord.Embed(title="✅ Warnings Cleared", color=0x2ECC71, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.add_field(name="Warnings Removed", value=str(count), inline=True)
        embed.set_footer(text=f"Moderator: {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="say", description="Make the bot say something (Admin only)")
    @app_commands.describe(message="The message you want the bot to repeat")
    @app_commands.default_permissions(administrator=True)
    async def say(self, ctx: commands.Context, *, message: str):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)
        if ctx.interaction is None:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            await ctx.send(message)
        else:
            await ctx.send("Message sent!", ephemeral=True)
            await ctx.channel.send(message)

    # Friendly color names on top of raw hex codes, so admins don't have to
    # look up a hex value for common choices.
    EMBED_COLOR_NAMES = {
        "blurple": 0x5865F2, "blood red": 0x8B0000, "bloodred": 0x8B0000,
        "red": 0xE02B2B, "green": 0x2ECC71, "blue": 0x3498DB, "yellow": 0xF1C40F,
        "orange": 0xE67E22, "purple": 0x9B59B6, "pink": 0xEB459E, "gold": 0xFFD700,
        "black": 0x23272A, "white": 0xFFFFFF, "grey": 0x2B2D31, "gray": 0x2B2D31,
        "teal": 0x1ABC9C, "cyan": 0x00FFFF,
    }

    def _resolve_embed_color(self, color: str) -> int:
        key = color.strip().lower()
        if key in self.EMBED_COLOR_NAMES:
            return self.EMBED_COLOR_NAMES[key]
        try:
            return int(color.lstrip("#"), 16)
        except ValueError:
            return 0x2B2D31

    @commands.hybrid_command(
        name="sayembed",
        description="Send a fully customizable embed message (Admin only)",
    )
    @app_commands.describe(
        title="Title of the embed",
        description="The main text of the embed (use \\n for new lines)",
        color="Color name (e.g. blood red, blurple, gold) or hex code (e.g. ff0000)",
        footer="Small text shown at the bottom of the embed",
        image_url="Big image shown at the bottom of the embed",
        thumbnail_url="Small image shown in the top-right corner",
        author_name="Text shown above the title, with a small icon",
        author_icon_url="Icon shown next to the author text (needs author_name)",
        url="Makes the title clickable, linking to this URL",
        timestamp="Add the current date/time to the embed footer",
        channel="Channel to send the embed to (defaults to this channel)",
    )
    @app_commands.default_permissions(administrator=True)
    async def sayembed(
        self,
        ctx: commands.Context,
        title: str,
        description: str,
        color: str = "blurple",
        footer: str = None,
        image_url: str = None,
        thumbnail_url: str = None,
        author_name: str = None,
        author_icon_url: str = None,
        url: str = None,
        timestamp: bool = False,
        channel: discord.TextChannel = None,
    ):
        if not is_admin(ctx):
            return await ctx.send("Admin only command.", ephemeral=True)

        color_int = self._resolve_embed_color(color)
        description = description.replace("\\n", "\n")

        embed = discord.Embed(
            title=title,
            description=description,
            color=color_int,
            url=url,
            timestamp=datetime.now(timezone.utc) if timestamp else None,
        )
        if footer:
            embed.set_footer(text=footer)
        if image_url:
            embed.set_image(url=image_url)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        if author_name:
            embed.set_author(name=author_name, icon_url=author_icon_url)

        target = channel or ctx.channel

        if ctx.interaction is None:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            await target.send(embed=embed)
        else:
            await ctx.send(f"Embed sent to {target.mention}!", ephemeral=True)
            await target.send(embed=embed)

    @commands.hybrid_command(name="add", description="Add coins to a user (Admin only)")
    @app_commands.describe(member="The member to give coins to", amount="Amount of coins to add")
    @app_commands.default_permissions(administrator=True)
    async def add(self, ctx: commands.Context, member: discord.Member, amount: str):
        if not is_admin(ctx) and ctx.author.id not in ADD_ALLOWED_IDS:
            return await ctx.send("❌ Admin only command.", ephemeral=True)
        from utils.economy import update_wallet, get_wallet, parse_economy_amount
        amount = parse_economy_amount(amount, 0)
        if amount == -1:
            return await ctx.send(
                "❌ Invalid amount. Use a number (e.g. `100k`, `2.5m`, `1t`).", ephemeral=True,
            )
        if amount <= 0:
            return await ctx.send("❌ Amount must be greater than 0.", ephemeral=True)
        if amount > MAX_ECONOMY_AMOUNT:
            return await ctx.send(
                f"❌ That amount is too large. The max per `!add` is 🪙 **{MAX_ECONOMY_AMOUNT:,}**.",
                ephemeral=True,
            )
        current = get_wallet(str(member.id))
        if current + amount > MAX_ECONOMY_AMOUNT:
            return await ctx.send(
                f"❌ That would push {member.mention}'s wallet past the safety limit of "
                f"🪙 **{MAX_ECONOMY_AMOUNT:,}**. Reduce the amount.",
                ephemeral=True,
            )
        update_wallet(str(member.id), amount)
        wallet = get_wallet(str(member.id))
        embed = discord.Embed(
            title="💰 Coins Added",
            description=f"Added 🪙 **{amount:,}** to {member.mention}\n\nNew Wallet Balance: 🪙 **{wallet:,}**",
            color=0x00FF00,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="remove", description="Remove coins from a user's wallet (Admin only)")
    @app_commands.describe(member="The member to remove coins from", amount="Amount of coins to remove")
    @app_commands.default_permissions(administrator=True)
    async def remove(self, ctx: commands.Context, member: discord.Member, amount: str):
        if not is_admin(ctx):
            return await ctx.send("❌ Admin only command.", ephemeral=True)
        from utils.economy import update_wallet, get_wallet, parse_economy_amount
        amount = parse_economy_amount(amount, 0)
        if amount == -1:
            return await ctx.send(
                "❌ Invalid amount. Use a number (e.g. `100k`, `2.5m`, `1t`).", ephemeral=True,
            )
        if amount <= 0:
            return await ctx.send("❌ Amount must be greater than 0.", ephemeral=True)
        if amount > MAX_ECONOMY_AMOUNT:
            return await ctx.send(
                f"❌ That amount is too large. The max per `!remove` is 🪙 **{MAX_ECONOMY_AMOUNT:,}**.",
                ephemeral=True,
            )
        current = get_wallet(str(member.id))
        deduct = min(amount, current)
        update_wallet(str(member.id), -deduct)
        wallet = get_wallet(str(member.id))
        embed = discord.Embed(
            title="💸 Coins Removed",
            description=f"Removed 🪙 **{deduct:,}** from {member.mention}\n\nNew Wallet Balance: 🪙 **{wallet:,}**",
            color=0xFF4444,
        )
        if deduct < amount:
            embed.set_footer(text=f"Note: user only had {current:,} coins — removed all of them.")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="reset_economy", description="RESETS EVERYTHING: coins, pets, items, and roles (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def reset_economy(self, ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("❌ Admin only command.", ephemeral=True)

        await ctx.defer()

        # 1. Clear coins, inventory and all cooldowns in eco_col for all users
        eco_col.update_many(
            {},
            {
                "$set": {"wallet": 0, "bank": 0, "inventory": []},
                "$unset": {
                    "last_daily": "",
                    "last_weekly": "",
                    "last_claim": "",
                    "last_work": "",
                    "last_crime": "",
                    "last_rob": "",
                    "last_adventure": "",
                    "balance": ""
                }
            }
        )

        # 2. Clear pets in pets_col for all users
        pets_col.update_many({}, {"$set": {"pets": []}})

        # 3. Clear all stock-related data
        user_stocks_col.delete_many({})   # user portfolios
        stocks_col.delete_many({})        # price history & charts
        stock_alerts_col.delete_many({})  # price alerts
        ipo_col.delete_many({})           # persisted IPO companies

        # Also evict IPO stocks from the live STOCKS dict
        # (base stocks defined in config.py are preserved on next restart)
        from config import STOCKS as _base_stocks_check
        base_symbols = set(_base_stocks_check.keys())
        for sym in list(STOCKS.keys()):
            if sym not in base_symbols:
                STOCKS.pop(sym, None)

        # 4. Clear bounties
        bounties_col.delete_many({})

        # 5. Remove shop roles from all members in the guild
        role_ids = [data["role_id"] for data in ROLE_SHOP.values() if "role_id" in data]
        roles_to_remove = []
        for rid in role_ids:
            role = ctx.guild.get_role(rid)
            if role:
                roles_to_remove.append(role)

        removed_count = 0
        if roles_to_remove:
            for member in ctx.guild.members:
                member_roles_to_remove = [r for r in roles_to_remove if r in member.roles]
                if member_roles_to_remove:
                    try:
                        await member.remove_roles(*member_roles_to_remove, reason="Economy Reset")
                        removed_count += 1
                    except Exception:
                        pass

        embed = discord.Embed(
            title="🧨 Economy Reset Complete",
            description=(
                "The economy has been fully reset!\n\n"
                "✅ All wallets and banks set to 🪙 0\n"
                "✅ All inventories and cooldowns cleared\n"
                "✅ All pets removed\n"
                "✅ All stock portfolios wiped\n"
                "✅ All stock price history cleared\n"
                "✅ All price alerts deleted\n"
                "✅ All IPO companies delisted\n"
                "✅ All bounties cleared\n"
                f"✅ Removed shop roles from **{removed_count}** members"
            ),
            color=0xFF0000,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)


    @commands.hybrid_command(name="leaveserver", description="Make the bot leave a specific server by ID (Owner only)")
    @app_commands.describe(server_id="The ID of the server the bot should leave")
    @app_commands.default_permissions(administrator=True)
    async def leaveserver(self, ctx: commands.Context, server_id: str):
        if not is_admin(ctx):
            return await ctx.send("❌ You do not have permission to use this command.", ephemeral=True)
        try:
            sid = int(server_id)
        except ValueError:
            return await ctx.send("❌ That doesn't look like a valid server ID.", ephemeral=True)

        guild = self.bot.get_guild(sid)
        if not guild:
            return await ctx.send("❌ I'm not in a server with that ID.", ephemeral=True)

        name = guild.name
        try:
            await ctx.send(f"👋 Leaving **{name}** (`{sid}`)...")
            await guild.leave()
        except Exception as e:
            await ctx.send(f"❌ Failed to leave **{name}**: {e}", ephemeral=True)

    @commands.hybrid_command(name="setuproles", description="Create all shop roles in this server and update their IDs (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def setuproles(self, ctx: commands.Context):
        if not is_admin(ctx):
            return await ctx.send("❌ Admin only command.", ephemeral=True)

        await ctx.defer()

        # Role definitions: key matches ROLE_SHOP, display name, color
        ROLE_DEFS = [
            ("bronze",   "Bronze",   discord.Color.from_rgb(205, 127, 50)),
            ("silver",   "Silver",   discord.Color.from_rgb(192, 192, 192)),
            ("gold",     "Gold",     discord.Color.from_rgb(255, 215, 0)),
            ("diamond",  "Diamond",  discord.Color.from_rgb(185, 242, 255)),
            ("emerald",  "Emerald",  discord.Color.from_rgb(80, 200, 120)),
            ("mythic",   "Mythic",   discord.Color.from_rgb(155, 89, 182)),
            ("cosmic",   "Cosmic",   discord.Color.from_rgb(26, 26, 255)),
            ("eternal",  "Eternal",  discord.Color.from_rgb(255, 107, 53)),
            ("secret",   "Secret",   discord.Color.from_rgb(255, 20, 147)),
            ("godlike",  "Godlike",  discord.Color.from_rgb(255, 50, 50)),
            ("celestial","Celestial",discord.Color.from_rgb(230, 230, 255)),
            ("ascended", "Ascended", discord.Color.from_rgb(255, 255, 0)),
        ]

        created = []
        skipped = []
        errors = []

        # Map existing role names for deduplication
        existing_roles = {r.name.lower(): r for r in ctx.guild.roles}

        new_ids: dict[str, int] = {}

        for key, display_name, color in ROLE_DEFS:
            if display_name.lower() in existing_roles:
                role = existing_roles[display_name.lower()]
                new_ids[key] = role.id
                skipped.append(f"**{display_name}** — already exists → `{role.id}`")
            else:
                try:
                    role = await ctx.guild.create_role(
                        name=display_name,
                        color=color,
                        mentionable=False,
                        reason="setuproles command"
                    )
                    new_ids[key] = role.id
                    created.append(f"**{display_name}** → `{role.id}`")
                except Exception as e:
                    errors.append(f"**{display_name}**: {e}")

        # Update ROLE_SHOP in memory
        for key, role_id in new_ids.items():
            if key in ROLE_SHOP:
                ROLE_SHOP[key]["role_id"] = role_id

        # Patch config.py on disk so IDs survive restarts
        import re, pathlib
        config_path = pathlib.Path(__file__).parent.parent / "config.py"
        not_patched: list[str] = []
        try:
            text = config_path.read_text()
            for key, role_id in new_ids.items():
                # Match the entry anywhere in the dict (handles multi-line formatting)
                pattern = rf'("{re.escape(key)}"\s*:\s*\{{[^}}]*?"role_id"\s*:\s*)\d+'
                new_text, n = re.subn(
                    pattern,
                    lambda m, rid=role_id: m.group(1) + str(rid),
                    text,
                    flags=re.DOTALL,
                )
                if n == 0:
                    not_patched.append(key)
                else:
                    text = new_text
            config_path.write_text(text)
            patched = len(not_patched) == 0
        except Exception as e:
            patched = False
            not_patched = list(new_ids.keys())
            errors.append(f"config.py patch failed: {e}")

        lines = []
        if created:
            lines.append("✅ **Created:**\n" + "\n".join(created))
        if skipped:
            lines.append("⏭️ **Already existed:**\n" + "\n".join(skipped))
        if errors:
            lines.append("❌ **Errors:**\n" + "\n".join(errors))
        if patched:
            lines.append("💾 `config.py` updated on disk — IDs will persist after restart.")
        else:
            missed = ", ".join(not_patched) if not_patched else "unknown"
            lines.append(f"⚠️ `config.py` patch incomplete — these keys were NOT updated: `{missed}`. Update them manually.")

        embed = discord.Embed(
            title="🛠️ Shop Roles Setup",
            description="\n\n".join(lines),
            color=0x00FF88,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))

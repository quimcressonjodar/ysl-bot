import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

from config import MODMAIL_GUILD_ID, MODMAIL_CHANNEL_ID
from database import modmail_col

logger = logging.getLogger("weekly-xp-bot")

# Reacted onto the bot's own confirmation prompt so the user has something
# to tap. A modmail ticket is only ever opened after the user reacts with
# this emoji — this stops misdirected/accidental DMs from becoming tickets.
CONFIRM_EMOJI = "✅"

# Reacted onto a relayed message once it has actually been delivered.
# This is the only proof of delivery — it cannot be faked by a third party,
# since only the bot can react as itself.
DELIVERED_EMOJI = "☑️"


def _safe_thread_name(user: discord.abc.User) -> str:
    name = f"{user.name} ({user.id})"
    return name[:100]


class ModMail(commands.Cog):
    """Relays DMs sent to the bot into threads in a dedicated staff server,
    and relays staff replies inside those threads back to the user's DMs.

    Before a ticket is opened, the user must confirm intent by reacting to a
    prompt from the bot. This filters out accidental/misdirected DMs so
    staff only see genuine modmail conversations."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Thread helpers ───────────────────────────────────────────────────────

    async def _get_target_channel(self) -> discord.TextChannel | None:
        channel = self.bot.get_channel(MODMAIL_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(MODMAIL_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.error("Modmail channel %s not found/accessible.", MODMAIL_CHANNEL_ID)
                return None
        if not isinstance(channel, discord.TextChannel):
            logger.error("Modmail channel %s is not a text channel.", MODMAIL_CHANNEL_ID)
            return None
        return channel

    async def _get_open_thread(self, user_id: str) -> discord.Thread | None:
        doc = modmail_col.find_one({"_id": user_id, "status": "open"})
        if not doc:
            return None

        thread = self.bot.get_channel(doc["thread_id"])
        if thread is None:
            try:
                thread = await self.bot.fetch_channel(doc["thread_id"])
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                thread = None

        if thread is None or not isinstance(thread, discord.Thread) or thread.archived:
            modmail_col.update_one({"_id": user_id}, {"$set": {"status": "closed"}})
            return None

        return thread

    async def _relay_message_to_thread(self, thread: discord.Thread, message: discord.Message) -> bool:
        embed = discord.Embed(
            description=message.content or "*(no text content)*",
            color=0x5865F2,
            timestamp=message.created_at,
        )
        embed.set_author(
            name=f"{message.author.display_name} ({message.author.id})",
            icon_url=message.author.display_avatar.url,
        )
        embed.set_footer(text="User Message")

        files = []
        for attachment in message.attachments:
            try:
                files.append(await attachment.to_file())
            except discord.HTTPException:
                pass

        try:
            await thread.send(embed=embed, files=files, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException as e:
            logger.error("Failed to relay DM to modmail thread: %s", e)
            return False
        return True

    # ── DM side ──────────────────────────────────────────────────────────────

    async def _send_confirmation_prompt(self, message: discord.Message) -> None:
        try:
            prompt = await message.channel.send(
                "👋 It looks like you're trying to reach our staff team.\n"
                f"React with {CONFIRM_EMOJI} below to confirm and open a support conversation. "
                "If you messaged us by mistake, just ignore this."
            )
            await prompt.add_reaction(CONFIRM_EMOJI)
        except discord.HTTPException as e:
            logger.error("Failed to send modmail confirmation prompt to %s: %s", message.author.id, e)
            return

        modmail_col.update_one(
            {"_id": str(message.author.id)},
            {
                "$set": {
                    "status": "pending",
                    "confirm_message_id": prompt.id,
                    "dm_channel_id": message.channel.id,
                    "username": str(message.author),
                },
                "$setOnInsert": {"pending_message_ids": []},
            },
            upsert=True,
        )
        modmail_col.update_one(
            {"_id": str(message.author.id)},
            {"$push": {"pending_message_ids": message.id}},
        )

    async def _handle_dm(self, message: discord.Message) -> None:
        user_id = str(message.author.id)
        doc = modmail_col.find_one({"_id": user_id})

        if doc and doc.get("status") == "open":
            thread = await self._get_open_thread(user_id)
            if thread is None:
                # Thread went away (deleted/archived) — ask for confirmation again.
                await self._send_confirmation_prompt(message)
                return
            delivered = await self._relay_message_to_thread(thread, message)
            if delivered:
                try:
                    await message.add_reaction(DELIVERED_EMOJI)
                except discord.HTTPException:
                    pass
            else:
                try:
                    await message.channel.send(
                        "We couldn't deliver your message to staff right now. Please try again shortly."
                    )
                except discord.HTTPException:
                    pass
            return

        if doc and doc.get("status") == "pending":
            # Already waiting on the user to confirm — queue this message,
            # it'll be relayed once they react to the confirmation prompt.
            modmail_col.update_one({"_id": user_id}, {"$push": {"pending_message_ids": message.id}})
            return

        # No conversation yet (or the previous one was closed) — ask for confirmation.
        await self._send_confirmation_prompt(message)

    # ── Confirmation reaction ────────────────────────────────────────────────

    async def _handle_confirmation(self, payload: discord.RawReactionActionEvent) -> None:
        doc = modmail_col.find_one({"_id": str(payload.user_id), "status": "pending"})
        if not doc or doc.get("confirm_message_id") != payload.message_id:
            return

        dm_channel = self.bot.get_channel(payload.channel_id)
        if dm_channel is None:
            try:
                user = self.bot.get_user(payload.user_id) or await self.bot.fetch_user(payload.user_id)
                dm_channel = user.dm_channel or await user.create_dm()
            except (discord.NotFound, discord.HTTPException):
                return

        channel = await self._get_target_channel()
        if channel is None:
            try:
                await dm_channel.send(
                    "We couldn't open a support conversation right now. Please try again shortly."
                )
            except discord.HTTPException:
                pass
            return

        try:
            user = self.bot.get_user(payload.user_id) or await self.bot.fetch_user(payload.user_id)
        except (discord.NotFound, discord.HTTPException):
            return

        try:
            thread = await channel.create_thread(
                name=_safe_thread_name(user),
                type=discord.ChannelType.public_thread,
                reason="Modmail ticket",
            )
        except discord.HTTPException as e:
            logger.error("Failed to create modmail thread for %s: %s", user.id, e)
            return

        modmail_col.update_one(
            {"_id": str(user.id)},
            {
                "$set": {
                    "status": "open",
                    "thread_id": thread.id,
                    "guild_id": MODMAIL_GUILD_ID,
                    "opened_at": datetime.now(timezone.utc),
                },
                "$unset": {"confirm_message_id": "", "dm_channel_id": ""},
            },
        )

        try:
            await thread.send(
                f"📨 **New modmail ticket** — {user.mention} (`{user.id}`)\n"
                f"Confirmed by the user. Reply in this thread to respond directly to them. "
                f"Use `!close` to close the ticket."
            )
        except discord.HTTPException:
            pass

        # Relay every message the user sent while awaiting confirmation, in order.
        pending_ids = doc.get("pending_message_ids") or []
        for msg_id in pending_ids:
            try:
                original = await dm_channel.fetch_message(msg_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
            await self._relay_message_to_thread(thread, original)

        modmail_col.update_one({"_id": str(user.id)}, {"$set": {"pending_message_ids": []}})

        try:
            await dm_channel.send(
                "✅ Confirmed. Your message has been forwarded to our staff team, and you'll receive "
                "replies right here in this DM."
            )
        except discord.HTTPException:
            pass

    # ── Staff side ───────────────────────────────────────────────────────────

    async def _forward_thread_to_dm(self, message: discord.Message) -> None:
        doc = modmail_col.find_one({"thread_id": message.channel.id, "status": "open"})
        if not doc:
            return

        try:
            user = self.bot.get_user(int(doc["_id"])) or await self.bot.fetch_user(int(doc["_id"]))
        except (discord.NotFound, discord.HTTPException):
            await message.reply(
                "Could not find that user (their account may have been deleted).", mention_author=False
            )
            return

        embed = discord.Embed(
            description=message.content or "*(no text content)*",
            color=0x57F287,
            timestamp=message.created_at,
        )
        embed.set_author(
            name=f"Staff — {message.author.display_name}",
            icon_url=message.author.display_avatar.url,
        )
        embed.set_footer(text="Support Team")

        files = []
        for attachment in message.attachments:
            try:
                files.append(await attachment.to_file())
            except discord.HTTPException:
                pass

        try:
            await user.send(embed=embed, files=files, allowed_mentions=discord.AllowedMentions.none())
            await message.add_reaction(DELIVERED_EMOJI)
        except discord.Forbidden:
            await message.reply(
                "Delivery failed — this user has DMs disabled or has blocked the bot.",
                mention_author=False,
            )
        except discord.HTTPException as e:
            logger.error("Failed to relay thread reply to DM: %s", e)

    # ── Listeners ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.guild is None:
            if not message.content.strip() and not message.attachments:
                return
            await self._handle_dm(message)
            return

        if (
            message.guild.id == MODMAIL_GUILD_ID
            and isinstance(message.channel, discord.Thread)
            and message.channel.parent_id == MODMAIL_CHANNEL_ID
            and not message.content.startswith(self.bot.command_prefix)
        ):
            await self._forward_thread_to_dm(message)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is not None:
            return  # confirmations only happen in DMs
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != CONFIRM_EMOJI:
            return
        await self._handle_confirmation(payload)

    # ── Commands ─────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="close", description="Close the current modmail ticket")
    async def close(self, ctx: commands.Context):
        if not (
            ctx.guild
            and ctx.guild.id == MODMAIL_GUILD_ID
            and isinstance(ctx.channel, discord.Thread)
            and ctx.channel.parent_id == MODMAIL_CHANNEL_ID
        ):
            return await ctx.send("This command can only be used inside a modmail ticket thread.", ephemeral=True)

        doc = modmail_col.find_one({"thread_id": ctx.channel.id})
        if not doc:
            return await ctx.send("This thread isn't registered as a modmail ticket.", ephemeral=True)

        modmail_col.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": "closed", "closed_at": datetime.now(timezone.utc)}},
        )

        try:
            user = self.bot.get_user(int(doc["_id"])) or await self.bot.fetch_user(int(doc["_id"]))
            await user.send(
                "This conversation has been closed by our staff team. "
                "If you need anything else, feel free to message us again."
            )
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

        await ctx.send("✅ Ticket closed.")
        try:
            await ctx.channel.edit(archived=True, locked=True)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ModMail(bot))

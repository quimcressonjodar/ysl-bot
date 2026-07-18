import html
import io
import logging
import re
from datetime import datetime, timezone

import discord
from discord.ext import commands

from config import (
    MODMAIL_GUILD_ID,
    MODMAIL_CATEGORY_ID,
    MODMAIL_MOD_ROLE_ID,
    MODMAIL_TRANSCRIPT_CHANNEL_ID,
)
from database import modmail_col
from utils.logger import log_action

logger = logging.getLogger("weekly-xp-bot")

# Reacted onto the bot's own confirmation prompt so the user has something
# to tap. A modmail ticket is only ever opened after the user reacts with
# this emoji — this stops misdirected/accidental DMs from becoming tickets.
CONFIRM_EMOJI = "✅"

# Reacted onto a relayed message once it has actually been delivered.
# This is the only proof of delivery — it cannot be faked by a third party,
# since only the bot can react as itself.
DELIVERED_EMOJI = "☑️"


def _safe_channel_name(user: discord.abc.User) -> str:
    """Build a valid Discord channel name from the user's username and ID.

    Discord channel names must be 1–100 characters, lowercase, and may only
    contain alphanumerics, hyphens, and underscores.
    """
    base = f"{user.name}-{user.id}".lower()
    base = re.sub(r"[^a-z0-9\-_]", "", base.replace(" ", "-"))
    base = re.sub(r"-+", "-", base).strip("-")
    return base[:100] or f"modmail-{user.id}"


def _build_transcript_html(channel: discord.TextChannel, messages: list[discord.Message]) -> str:
    """Renders the ticket's message history as a simple, self-contained HTML file
    styled to loosely resemble Discord's own dark theme."""
    rows = []
    for message in messages:
        ts = message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        author = html.escape(str(message.author))
        avatar = message.author.display_avatar.url

        # Relayed modmail messages are sent as embeds (not plain content), so
        # fall back to the embed's text when the message itself has none.
        text = message.content or ""
        if not text and message.embeds:
            parts = []
            for embed in message.embeds:
                if embed.author and embed.author.name:
                    parts.append(embed.author.name)
                if embed.description:
                    parts.append(embed.description)
                for field in embed.fields:
                    parts.append(f"{field.name}: {field.value}")
                if embed.footer and embed.footer.text:
                    parts.append(f"— {embed.footer.text}")
            text = "\n".join(parts)
        content = html.escape(text).replace("\n", "<br>")

        attachments_html = ""
        if message.attachments:
            links = "".join(
                f'<div><a href="{html.escape(a.url)}" target="_blank">📎 {html.escape(a.filename)}</a></div>'
                for a in message.attachments
            )
            attachments_html = f'<div class="attachments">{links}</div>'

        rows.append(
            f'<div class="message">'
            f'<img class="avatar" src="{avatar}">'
            f'<div class="body">'
            f'<div class="meta"><span class="author">{author}</span>'
            f'<span class="timestamp">{ts}</span></div>'
            f'<div class="content">{content}</div>'
            f"{attachments_html}"
            f"</div></div>"
        )

    body = "\n".join(rows) if rows else '<p style="color:#949ba4;">No messages were recorded in this ticket.</p>'

    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>Transcript - {html.escape(channel.name)}</title>"
        "<style>"
        "body{background:#313338;color:#dbdee1;font-family:'gg sans','Helvetica Neue',Arial,sans-serif;"
        "margin:0;padding:24px;}"
        "h1{color:#fff;font-size:20px;border-bottom:1px solid #3f4147;padding-bottom:12px;}"
        ".message{display:flex;gap:14px;margin-top:16px;}"
        ".avatar{width:40px;height:40px;border-radius:50%;flex-shrink:0;}"
        ".meta{font-size:13px;margin-bottom:3px;}"
        ".author{font-weight:600;color:#fff;}"
        ".timestamp{color:#949ba4;font-size:12px;margin-left:8px;}"
        ".content{font-size:15px;line-height:1.4;white-space:pre-wrap;word-break:break-word;}"
        ".attachments a{color:#00a8fc;text-decoration:none;font-size:14px;}"
        "</style></head><body>"
        f"<h1>📄 Transcript — {html.escape(channel.name)}</h1>"
        f"{body}"
        "</body></html>"
    )


class ModMail(commands.Cog):
    """Relays DMs sent to the bot into dedicated channels inside a staff category,
    and relays staff replies inside those channels back to the user's DMs.

    Before a ticket is opened, the user must confirm intent by reacting to a
    prompt from the bot. This filters out accidental/misdirected DMs so
    staff only see genuine modmail conversations."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Channel helpers ──────────────────────────────────────────────────────

    async def _get_modmail_category(self) -> discord.CategoryChannel | None:
        """Fetch the category where ticket channels are created."""
        guild = self.bot.get_guild(MODMAIL_GUILD_ID)
        if guild is None:
            try:
                guild = await self.bot.fetch_guild(MODMAIL_GUILD_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.error("Modmail guild %s not found/accessible.", MODMAIL_GUILD_ID)
                return None

        category = guild.get_channel(MODMAIL_CATEGORY_ID)
        if category is None:
            try:
                category = await self.bot.fetch_channel(MODMAIL_CATEGORY_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.error("Modmail category %s not found/accessible.", MODMAIL_CATEGORY_ID)
                return None

        if not isinstance(category, discord.CategoryChannel):
            logger.error("Channel %s is not a category.", MODMAIL_CATEGORY_ID)
            return None

        return category

    async def _get_open_channel(self, user_id: str) -> discord.TextChannel | None:
        """Return the open ticket channel for a user, or None if none exists."""
        doc = modmail_col.find_one({"_id": user_id, "status": "open"})
        if not doc:
            return None

        channel = self.bot.get_channel(doc["thread_id"])
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(doc["thread_id"])
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                channel = None

        if channel is None or not isinstance(channel, discord.TextChannel):
            modmail_col.update_one({"_id": user_id}, {"$set": {"status": "closed"}})
            return None

        # Make sure the channel is still in the modmail category
        if channel.category_id != MODMAIL_CATEGORY_ID:
            modmail_col.update_one({"_id": user_id}, {"$set": {"status": "closed"}})
            return None

        return channel

    async def _relay_message_to_channel(self, channel: discord.TextChannel, message: discord.Message) -> bool:
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
            await channel.send(embed=embed, files=files, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException as e:
            logger.error("Failed to relay DM to modmail channel: %s", e)
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
                    # Replace any previously queued messages with only this one.
                    # If the user sent messages earlier without confirming, those
                    # are discarded — staff only receive the message that actually
                    # prompted the user to open the ticket.
                    "pending_message_ids": [message.id],
                },
            },
            upsert=True,
        )

    async def _handle_dm(self, message: discord.Message) -> None:
        user_id = str(message.author.id)
        doc = modmail_col.find_one({"_id": user_id})

        if doc and doc.get("status") == "open":
            channel = await self._get_open_channel(user_id)
            if channel is None:
                # Channel went away (deleted) — ask for confirmation again.
                await self._send_confirmation_prompt(message)
                return
            delivered = await self._relay_message_to_channel(channel, message)
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
            # The user sent another message without reacting to the confirmation
            # prompt. Re-send it so they have a fresh ✅ to tap, and queue this
            # message so it's relayed once they confirm.
            await self._send_confirmation_prompt(message)
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

        category = await self._get_modmail_category()
        if category is None:
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
            ticket_channel = await category.guild.create_text_channel(
                name=_safe_channel_name(user),
                category=category,
                reason="Modmail ticket",
            )
        except discord.HTTPException as e:
            logger.error("Failed to create modmail channel for %s: %s", user.id, e)
            return

        modmail_col.update_one(
            {"_id": str(user.id)},
            {
                "$set": {
                    "status": "open",
                    "thread_id": ticket_channel.id,  # reuse field name; now stores channel ID
                    "guild_id": MODMAIL_GUILD_ID,
                    "opened_at": datetime.now(timezone.utc),
                },
                "$unset": {"confirm_message_id": "", "dm_channel_id": ""},
            },
        )

        try:
            log_action(
                guild_id=MODMAIL_GUILD_ID,
                log_type="modmail",
                action="ticket_opened",
                actor_id=user.id,
                actor_name=str(user),
            )
        except Exception:
            pass

        try:
            await ticket_channel.send(
                f"<@&{MODMAIL_MOD_ROLE_ID}> 📨 **New modmail ticket** — {user.mention} (`{user.id}`)\n"
                f"Confirmed by the user. Reply in this channel to respond directly to them. "
                f"Use `!close` to close the ticket.",
                allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
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
            await self._relay_message_to_channel(ticket_channel, original)

        modmail_col.update_one({"_id": str(user.id)}, {"$set": {"pending_message_ids": []}})

        try:
            await dm_channel.send(
                "✅ Confirmed. Your message has been forwarded to our staff team, and you'll receive "
                "replies right here in this DM."
            )
        except discord.HTTPException:
            pass

    # ── Staff side ───────────────────────────────────────────────────────────

    async def _forward_channel_to_dm(self, message: discord.Message) -> None:
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
            try:
                log_action(
                    guild_id=MODMAIL_GUILD_ID,
                    log_type="modmail",
                    action="staff_reply",
                    actor_id=message.author.id,
                    actor_name=str(message.author),
                    target_id=int(doc["_id"]),
                    target_name=doc.get("username", "Unknown user"),
                )
            except Exception:
                pass
        except discord.Forbidden:
            await message.reply(
                "Delivery failed — this user has DMs disabled or has blocked the bot.",
                mention_author=False,
            )
        except discord.HTTPException as e:
            logger.error("Failed to relay channel reply to DM: %s", e)

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
            and isinstance(message.channel, discord.TextChannel)
            and message.channel.category_id == MODMAIL_CATEGORY_ID
            and not message.content.startswith(self.bot.command_prefix)
        ):
            await self._forward_channel_to_dm(message)

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
            and isinstance(ctx.channel, discord.TextChannel)
            and ctx.channel.category_id == MODMAIL_CATEGORY_ID
        ):
            return await ctx.send("This command can only be used inside a modmail ticket channel.", ephemeral=True)

        doc = modmail_col.find_one({"thread_id": ctx.channel.id})
        if not doc:
            return await ctx.send("This channel isn't registered as a modmail ticket.", ephemeral=True)

        modmail_col.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": "closed", "closed_at": datetime.now(timezone.utc)}},
        )

        try:
            log_action(
                guild_id=MODMAIL_GUILD_ID,
                log_type="modmail",
                action="ticket_closed",
                actor_id=ctx.author.id,
                actor_name=str(ctx.author),
                target_id=int(doc["_id"]),
                target_name=doc.get("username", "Unknown user"),
            )
        except Exception:
            pass

        try:
            owner = self.bot.get_user(int(doc["_id"])) or await self.bot.fetch_user(int(doc["_id"]))
        except (discord.NotFound, discord.HTTPException):
            owner = None

        if owner is not None:
            try:
                await owner.send(
                    "This conversation has been closed by our staff team. "
                    "If you need anything else, feel free to message us again."
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        await ctx.send("✅ Ticket closed. Posting transcript…")
        await self._post_transcript(ctx.channel, doc, owner, closed_by=ctx.author)

    @commands.hybrid_command(name="delete", description="Delete the current modmail ticket channel")
    async def delete(self, ctx: commands.Context):
        if not (
            ctx.guild
            and ctx.guild.id == MODMAIL_GUILD_ID
            and isinstance(ctx.channel, discord.TextChannel)
            and ctx.channel.category_id == MODMAIL_CATEGORY_ID
        ):
            return await ctx.send("This command can only be used inside a modmail ticket channel.", ephemeral=True)

        doc = modmail_col.find_one({"thread_id": ctx.channel.id})
        if not doc:
            return await ctx.send("This channel isn't registered as a modmail ticket.", ephemeral=True)

        if doc.get("status") == "open":
            return await ctx.send(
                "This ticket is still open. Use `!close` first before deleting the channel.",
                ephemeral=True,
            )

        await ctx.send("🗑️ Deleting channel…")
        try:
            await ctx.channel.delete(reason=f"Modmail ticket deleted by {ctx.author}")
        except discord.HTTPException as e:
            logger.error("Failed to delete modmail channel: %s", e)

    async def _post_transcript(
        self,
        channel: discord.TextChannel,
        doc: dict,
        owner: discord.abc.User | None,
        closed_by: discord.abc.User,
    ) -> None:
        try:
            messages = [m async for m in channel.history(limit=None, oldest_first=True)]
        except discord.HTTPException as e:
            logger.error("Failed to fetch modmail channel history for transcript: %s", e)
            messages = []

        transcript_html = _build_transcript_html(channel, messages)
        transcript_file = discord.File(
            io.BytesIO(transcript_html.encode("utf-8")),
            filename=f"transcript-{channel.id}.html",
        )

        counts: dict[int, dict] = {}
        for message in messages:
            entry = counts.setdefault(message.author.id, {"user": message.author, "count": 0})
            entry["count"] += 1
        sorted_counts = sorted(counts.values(), key=lambda c: c["count"], reverse=True)
        users_lines = [f"{c['count']} - {c['user'].mention} - {c['user']}" for c in sorted_counts[:15]]
        users_text = "\n".join(users_lines) if users_lines else "No participants recorded."

        embed = discord.Embed(color=0x5865F2, timestamp=datetime.now(timezone.utc))
        embed.set_author(
            name=str(owner) if owner else doc.get("username", "Unknown user"),
            icon_url=owner.display_avatar.url if owner else discord.Embed.Empty,
        )
        embed.add_field(
            name="Ticket Owner",
            value=owner.mention if owner else f"`{doc['_id']}`",
            inline=False,
        )
        embed.add_field(name="Ticket Name", value=channel.name, inline=False)
        embed.add_field(name="Panel Name", value="Direct Message Modmail", inline=False)
        embed.add_field(name="Closed By", value=closed_by.mention, inline=False)
        embed.add_field(name="Users in Transcript", value=users_text[:1024], inline=False)
        embed.set_footer(text=f"{len(messages)} messages")

        transcript_channel = self.bot.get_channel(MODMAIL_TRANSCRIPT_CHANNEL_ID)
        if transcript_channel is None:
            try:
                transcript_channel = await self.bot.fetch_channel(MODMAIL_TRANSCRIPT_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.error("Modmail transcript channel %s not found/accessible.", MODMAIL_TRANSCRIPT_CHANNEL_ID)
                return

        try:
            await transcript_channel.send(embed=embed, file=transcript_file)
        except discord.HTTPException as e:
            logger.error("Failed to post modmail transcript: %s", e)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModMail(bot))

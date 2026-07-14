import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

from config import MODMAIL_GUILD_ID, MODMAIL_CHANNEL_ID
from database import modmail_col

logger = logging.getLogger("weekly-xp-bot")


def _safe_thread_name(user: discord.abc.User) -> str:
    name = f"{user.name} ({user.id})"
    return name[:100]


class ModMail(commands.Cog):
    """Relays DMs sent to the bot into threads in a dedicated staff server,
    and relays staff replies inside those threads back to the user's DMs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _get_open_thread(self, user: discord.abc.User) -> discord.Thread | None:
        doc = modmail_col.find_one({"_id": str(user.id), "status": "open"})
        if not doc:
            return None

        thread = self.bot.get_channel(doc["thread_id"])
        if thread is None:
            try:
                thread = await self.bot.fetch_channel(doc["thread_id"])
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                thread = None

        if thread is None or not isinstance(thread, discord.Thread) or thread.archived:
            # Stale/archived/deleted thread reference — start fresh next time.
            modmail_col.update_one({"_id": str(user.id)}, {"$set": {"status": "closed"}})
            return None

        return thread

    async def _create_thread(self, user: discord.abc.User) -> discord.Thread | None:
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

        try:
            thread = await channel.create_thread(
                name=_safe_thread_name(user),
                type=discord.ChannelType.public_thread,
                reason="Modmail ticket",
            )
        except discord.HTTPException as e:
            logger.error("Failed to create modmail thread for %s: %s", user.id, e)
            return None

        modmail_col.update_one(
            {"_id": str(user.id)},
            {
                "$set": {
                    "thread_id": thread.id,
                    "guild_id": MODMAIL_GUILD_ID,
                    "status": "open",
                    "username": str(user),
                    "opened_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

        await thread.send(
            f"📨 Nuevo ticket de modmail — {user.mention} (`{user.id}`)\n"
            f"Respondan acá y el mensaje se le reenvía por DM. Usen `!close` para cerrar el ticket."
        )
        return thread

    async def _forward_dm_to_thread(self, message: discord.Message) -> None:
        thread = await self._get_open_thread(message.author)
        is_new = thread is None
        if thread is None:
            thread = await self._create_thread(message.author)
        if thread is None:
            try:
                await message.channel.send(
                    "❌ No pude entregar tu mensaje al staff en este momento. Intenta de nuevo más tarde."
                )
            except discord.HTTPException:
                pass
            return

        embed = discord.Embed(
            description=message.content or "*(sin texto)*",
            color=0x5865F2,
            timestamp=message.created_at,
        )
        embed.set_author(
            name=f"{message.author} ({message.author.id})",
            icon_url=message.author.display_avatar.url,
        )

        files = []
        for attachment in message.attachments:
            try:
                files.append(await attachment.to_file())
            except discord.HTTPException:
                pass

        try:
            await thread.send(embed=embed, files=files)
        except discord.HTTPException as e:
            logger.error("Failed to relay DM to modmail thread: %s", e)
            return

        if is_new:
            try:
                await message.channel.send(
                    "✅ Tu mensaje fue enviado al staff. Te van a responder por aquí mismo, en este chat."
                )
            except discord.HTTPException:
                pass

    async def _forward_thread_to_dm(self, message: discord.Message) -> None:
        doc = modmail_col.find_one({"thread_id": message.channel.id, "status": "open"})
        if not doc:
            return

        try:
            user = self.bot.get_user(int(doc["_id"])) or await self.bot.fetch_user(int(doc["_id"]))
        except (discord.NotFound, discord.HTTPException):
            await message.reply("❌ No pude encontrar a ese usuario (¿eliminó su cuenta?).", mention_author=False)
            return

        embed = discord.Embed(
            description=message.content or "*(sin texto)*",
            color=0x57F287,
            timestamp=message.created_at,
        )
        embed.set_author(
            name=f"Staff: {message.author.display_name}",
            icon_url=message.author.display_avatar.url,
        )

        files = []
        for attachment in message.attachments:
            try:
                files.append(await attachment.to_file())
            except discord.HTTPException:
                pass

        try:
            await user.send(embed=embed, files=files)
            await message.add_reaction("✅")
        except discord.Forbidden:
            await message.reply(
                "❌ No pude entregar el mensaje — el usuario tiene los DMs cerrados o bloqueó al bot.",
                mention_author=False,
            )
        except discord.HTTPException as e:
            logger.error("Failed to relay thread reply to DM: %s", e)

    # ── Listener ─────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # DM to the bot -> forward to (or open) the user's modmail thread.
        if message.guild is None:
            if not message.content.strip() and not message.attachments:
                return
            await self._forward_dm_to_thread(message)
            return

        # Staff reply inside a modmail thread -> forward to the user's DM.
        if (
            message.guild.id == MODMAIL_GUILD_ID
            and isinstance(message.channel, discord.Thread)
            and message.channel.parent_id == MODMAIL_CHANNEL_ID
            and not message.content.startswith(self.bot.command_prefix)
        ):
            await self._forward_thread_to_dm(message)

    # ── Commands ─────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="close", description="Cierra el ticket de modmail actual")
    async def close(self, ctx: commands.Context):
        if not (
            ctx.guild
            and ctx.guild.id == MODMAIL_GUILD_ID
            and isinstance(ctx.channel, discord.Thread)
            and ctx.channel.parent_id == MODMAIL_CHANNEL_ID
        ):
            return await ctx.send("❌ Este comando solo se puede usar dentro de un ticket de modmail.", ephemeral=True)

        doc = modmail_col.find_one({"thread_id": ctx.channel.id})
        if not doc:
            return await ctx.send("❌ Este hilo no está registrado como ticket de modmail.", ephemeral=True)

        modmail_col.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": "closed", "closed_at": datetime.now(timezone.utc)}},
        )

        try:
            user = self.bot.get_user(int(doc["_id"])) or await self.bot.fetch_user(int(doc["_id"]))
            await user.send("🔒 El staff cerró esta conversación. Si necesitas algo más, escríbenos de nuevo por aquí.")
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

        await ctx.send("✅ Ticket cerrado.")
        try:
            await ctx.channel.edit(archived=True, locked=True)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ModMail(bot))

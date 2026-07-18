import discord
from discord.ext import commands
from discord import app_commands
from database import starboard_col, starboard_messages_col
import logging
from datetime import datetime

logger = logging.getLogger("weekly-xp-bot")

class StarboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_group(name="starboard", description="Manage Starboard settings")
    @app_commands.default_permissions(administrator=True)
    async def starboard(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Use `!starboard setup` or `!starboard config`", ephemeral=True)

    @starboard.command(name="setup", description="Setup or update Starboard configuration")
    @app_commands.describe(channel="The channel where starred messages will be posted", threshold="Minimum stars required (default: 4)")
    async def setup(self, ctx: commands.Context, channel: discord.TextChannel, threshold: int = 4):
        if threshold < 1:
            return await ctx.send("❌ Threshold must be at least 1.", ephemeral=True)
        
        starboard_col.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"channel_id": channel.id, "threshold": threshold}},
            upsert=True
        )
        await ctx.send(f"✅ Starboard set to {channel.mention} with a threshold of **{threshold}** stars.")

    @starboard.command(name="config", description="Show current Starboard configuration")
    async def config(self, ctx: commands.Context):
        config = starboard_col.find_one({"guild_id": ctx.guild.id})
        if not config:
            return await ctx.send("❌ Starboard is not configured for this server.")
        
        channel = self.bot.get_channel(config["channel_id"])
        channel_name = channel.mention if channel else "Unknown/Deleted"
        await ctx.send(f"📋 **Starboard Configuration:**\n- **Channel:** {channel_name}\n- **Threshold:** {config['threshold']} ⭐")

    def create_starboard_embed(self, message: discord.Message, star_count: int):
        embed = discord.Embed(
            description=message.content,
            color=0x2B2D31,
            timestamp=message.created_at
        )
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        embed.set_footer(text=f"⭐ {star_count} • #{message.channel.name}")
        embed.add_field(name="Original", value=f"[Jump!]({message.jump_url})")
        
        # Attachments support
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    embed.set_image(url=attachment.url)
                    break
        
        return embed

    def get_starboard_content(self, message: discord.Message, star_count: int):
        return f"⭐ **{star_count}** {message.channel.mention} (ID: {message.id})"

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "⭐":
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        config = starboard_col.find_one({"guild_id": guild.id})
        if not config or not config.get("channel_id"):
            return

        starboard_channel = self.bot.get_channel(config["channel_id"])
        if not starboard_channel or payload.channel_id == starboard_channel.id:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        if message.author.bot:
            return

        # Count stars
        reaction = discord.utils.get(message.reactions, emoji="⭐")
        if not reaction:
            return
        
        star_count = reaction.count
        threshold = config.get("threshold", 4)

        starboard_entry = starboard_messages_col.find_one({"original_message_id": message.id})

        if star_count >= threshold:
            embed = self.create_starboard_embed(message, star_count)
            content = self.get_starboard_content(message, star_count)

            if starboard_entry:
                try:
                    starboard_message = await starboard_channel.fetch_message(starboard_entry["starboard_message_id"])
                    await starboard_message.edit(content=content, embed=embed)
                except discord.NotFound:
                    # Message was deleted from starboard, repost it
                    new_starboard_msg = await starboard_channel.send(content=content, embed=embed)
                    starboard_messages_col.update_one(
                        {"original_message_id": message.id},
                        {"$set": {"starboard_message_id": new_starboard_msg.id}}
                    )
            else:
                new_starboard_msg = await starboard_channel.send(content=content, embed=embed)
                starboard_messages_col.insert_one({
                    "original_message_id": message.id,
                    "starboard_message_id": new_starboard_msg.id,
                    "guild_id": guild.id
                })
        elif starboard_entry:
            # Star count is below threshold but the entry still exists.
            # Removal on reaction-remove is handled by on_raw_reaction_remove.
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "⭐":
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        config = starboard_col.find_one({"guild_id": guild.id})
        if not config or not config.get("channel_id"):
            return

        starboard_channel = self.bot.get_channel(config["channel_id"])
        if not starboard_channel:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        starboard_entry = starboard_messages_col.find_one({"original_message_id": message.id})
        if not starboard_entry:
            return

        reaction = discord.utils.get(message.reactions, emoji="⭐")
        star_count = reaction.count if reaction else 0
        threshold = config.get("threshold", 4)

        content = self.get_starboard_content(message, star_count)
        embed = self.create_starboard_embed(message, star_count)

        try:
            starboard_message = await starboard_channel.fetch_message(starboard_entry["starboard_message_id"])
            if star_count < threshold:
                await starboard_message.delete()
                starboard_messages_col.delete_one({"original_message_id": message.id})
            else:
                await starboard_message.edit(content=content, embed=embed)
        except discord.NotFound:
            starboard_messages_col.delete_one({"original_message_id": message.id})

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        starboard_entry = starboard_messages_col.find_one({"original_message_id": payload.message_id})
        if not starboard_entry:
            return

        config = starboard_col.find_one({"guild_id": payload.guild_id})
        if not config or not config.get("channel_id"):
            return

        starboard_channel = self.bot.get_channel(config["channel_id"])
        if not starboard_channel:
            return

        try:
            starboard_message = await starboard_channel.fetch_message(starboard_entry["starboard_message_id"])
            await starboard_message.delete()
        except discord.NotFound:
            pass
        
        starboard_messages_col.delete_one({"original_message_id": payload.message_id})

async def setup(bot: commands.Bot):
    await bot.add_cog(StarboardCog(bot))

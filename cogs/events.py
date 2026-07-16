import random
import time
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

import state
from config import (
    WELCOME_CHANNEL_ID,
    RULES_CHANNEL_ID,
    JOIN_APPLY_CHANNEL_ID,
    ADVENTURE_LOOT,
    BOOST_THANKS_CHANNEL_ID,
)
from database import eco_col
from utils.economy import to_decimal128, normalize_economy_doc

logger = logging.getLogger("weekly-xp-bot")

GLOBAL_DROP_CHANNEL_ID = 1513755454029959239
GLOBAL_DROP_COIN_REWARDS = [50000, 75000, 100000, 125000, 150000, 200000]
BOOST_COLOR = 0xF47FFF


class EventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info(f"EVENTS COG LOADED {id(self)}")
        self.spawn_global_drop.start()
        self.process_interests.start()

    def cog_unload(self):
        self.spawn_global_drop.cancel()
        self.process_interests.cancel()

    def _should_process_member_event(self, event_name: str, member_id: int, cooldown: float = 5.0) -> bool:
        key = (event_name, member_id)
        now = time.monotonic()
        last = state.recent_member_events.get(key)
        if last and now - last < cooldown:
            return False
        state.recent_member_events[key] = now
        return True

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot or not self._should_process_member_event("join", member.id):
            return
        channel = self.bot.get_channel(WELCOME_CHANNEL_ID)
        if not channel:
            return
        member_count = member.guild.member_count
        embed = discord.Embed(
            title=f"Welcome to the server, {member.name}! \U0001f389",
            description=(
                f"Hello {member.mention}, we are glad to have you here!\n\n"
                f"\U0001f4dc **First Step:** Please, read the rules in <#{RULES_CHANNEL_ID}>\n"
                f"\u2694\ufe0f **Want to join?** If you want to apply for the clan, go to <#{JOIN_APPLY_CHANNEL_ID}>\n\n"
                f"You are our **{member_count}** member!\n\n"
                f"Enjoy your stay!"
            ),
            color=0x8B0000,
        )
        embed.set_image(url="https://i.ibb.co/Rd2szwm/1jkdq5x.png")
        await channel.send(content=f"Welcome {member.mention}!", embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Discord itself generates a system message when a member boosts the
        # server; its (usually hidden) content holds the boost count when a
        # member applies more than one boost at once.
        if message.type != discord.MessageType.premium_guild_subscription:
            return

        channel = self.bot.get_channel(BOOST_THANKS_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(BOOST_THANKS_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.error("Boost thanks channel %s not found/accessible.", BOOST_THANKS_CHANNEL_ID)
                return

        times = int(message.content) if message.content and message.content.isdigit() else 1
        times_text = f"**{times}** time" + ("s" if times != 1 else "")

        embed = discord.Embed(
            description=f"Thank you for boosting the server {times_text}, {message.author.mention}! \U0001f49c",
            color=BOOST_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text="Server Boost")

        try:
            await channel.send(
                content=message.author.mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except discord.HTTPException as e:
            logger.error("Failed to send boost thank-you message: %s", e)

        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass  # Already deleted or no permission — not critical

    @tasks.loop(hours=9)
    async def spawn_global_drop(self):
        channel = self.bot.get_channel(GLOBAL_DROP_CHANNEL_ID)
        if not channel:
            return

        drop_type = random.choice(["coins", "coins", "coins", "item", "item"])

        if drop_type == "coins":
            reward = random.choice(GLOBAL_DROP_COIN_REWARDS)
            state.active_global_drop = {"type": "coins", "reward": reward}
            embed = discord.Embed(
                title="\U0001f320 GLOBAL DROP",
                description=(
                    "\U0001f4b8 A MASSIVE treasure drop appeared!\nFirst person to claim it wins!\n"
                    "Use `!claimdrop` first!"
                ),
                color=0xF1C40F,
            )
            embed.add_field(name="\U0001f4b0 Coin Reward", value=f"\U0001fa99 {reward:,}")
        else:
            rarity_roll = random.randint(1, 100)
            if rarity_roll <= 50:
                rarity = "common"
            elif rarity_roll <= 80:
                rarity = "rare"
            elif rarity_roll <= 94:
                rarity = "epic"
            elif rarity_roll <= 99:
                rarity = "legendary"
            else:
                rarity = "godly"

            item_name, item_value = random.choice(ADVENTURE_LOOT[rarity])
            rarity_colors = {
                "common": 0x95A5A6, "rare": 0x3498DB, "epic": 0x9B59B6,
                "legendary": 0xF1C40F, "godly": 0xFF00FF,
            }
            embed = discord.Embed(
                title="\U0001f320 GLOBAL ITEM DROP",
                description="A mysterious item appeared from the skies!\n\nUse `!claimdrop` first!",
                color=rarity_colors[rarity],
            )
            embed.add_field(name="\U0001f381 Item", value=item_name)
            embed.add_field(name="\u2728 Rarity", value=rarity.capitalize())
            state.active_global_drop = {
                "type": "item",
                "item": {"name": item_name, "value": item_value, "rarity": rarity},
            }

        if drop_type == "item" and rarity in ("godly", "legendary"):
            hype = (
                "\U0001f30c A GODLY item has appeared!!! THE UNIVERSE TREMBLES!"
                if rarity == "godly"
                else "\U0001f30c A LEGENDARY item has appeared!!!"
            )
            await channel.send(hype)
        await channel.send(embed=embed)

    @spawn_global_drop.before_loop
    async def before_spawn_global_drop(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=1)
    async def process_interests(self):
        """Aplica un 2% de interés diario prorrateado a los préstamos activos."""
        now = time.time()
        users_with_loans = eco_col.find({"loan_amount": {"$gt": 0}})

        for user_data in users_with_loans:
            normalize_economy_doc(user_data)
            user_id   = user_data["_id"]
            last_calc = user_data.get("last_interest_calc", now)
            time_diff = now - last_calc

            if time_diff >= 3600:
                loan_amount = user_data.get("loan_amount", 0)
                interest    = int(loan_amount * 0.02 * (time_diff / 86400))

                if interest > 0:
                    eco_col.update_one(
                        {"_id": user_id},
                        {
                            "$inc": {"interest_accrued": to_decimal128(interest)},
                            "$set": {"last_interest_calc": now},
                        },
                    )
                    logger.info(f"Applied {interest} interest to user {user_id} for {time_diff/3600:.2f} hours")
                elif time_diff >= 86400:
                    eco_col.update_one({"_id": user_id}, {"$set": {"last_interest_calc": now}})

    @process_interests.before_loop
    async def before_process_interests(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            return
        from utils.economy import JailCheckError
        if isinstance(error, JailCheckError):
            return

        logger.error(f"Error in command {ctx.command}: {error}", exc_info=error)

        if isinstance(error, commands.MissingPermissions):
            await ctx.send("\u274c You don't have permission to use this command.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("\u274c I don't have permission to do that.", ephemeral=True)
        elif isinstance(error, commands.CommandOnCooldown):
            next_ts = int(time.time() + error.retry_after)
            await ctx.send(f"\u23f3 This command is on cooldown. Try again <t:{next_ts}:R>.", ephemeral=True)
        else:
            await ctx.send(f"\u274c An error occurred: {str(error)}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))

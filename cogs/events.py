import random
import asyncio
import time
import logging

import discord
from discord.ext import commands, tasks
from datetime import timedelta

import state
from config import WELCOME_CHANNEL_ID, ADVENTURE_LOOT
from database import eco_col, bot_state_col
logger = logging.getLogger("weekly-xp-bot")


GLOBAL_DROP_CHANNEL_ID = 1513755454029959239
GLOBAL_DROP_COIN_REWARDS = [50000, 75000, 100000, 125000, 150000, 200000]


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

        embed = discord.Embed(
            title=f"Welcome to the server, {member.name}! 🎉",
            description=(
                f"Hello {member.mention}, we are glad to have you here!\n\n"
                f"📜 **First Step:** Please, read the rules in <#1206222685143826485>\n"
                f"⚔️ **Want to join?** If you want to apply for the clan, go to <#1206198139686617088>\n\n"
                f"Enjoy your stay!"
            ),
            color=0x2B2D31,
        )
        embed.set_image(url="https://i.ibb.co/d4r7Z6f8/248-AB2-AF-21-F0-4384-A53-D-404328353301.png")
        await channel.send(content=f"Welcome {member.mention}!", embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot or not self._should_process_member_event("leave", member.id):
            return

        channel = self.bot.get_channel(WELCOME_CHANNEL_ID)
        if not channel:
            return

        embed = discord.Embed(
            title="Goodbye! 👋",
            description=f"**{member.name}** has left the server. We will miss you!",
            color=0xFF2A2A,
        )
        await channel.send(embed=embed)

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
                title="U0001f320 GLOBAL DROP",
                description=(
                    "U0001f4b8 A MASSIVE treasure drop appeared!\nFirst person to claim it wins!\n"
                    "Use `!claimdrop` first!"
                ),
                color=0xF1C40F,
            )
            embed.add_field(name="U0001f4b0 Coin Reward", value=f"U0001fa99 {reward:,}")
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
                title="U0001f320 GLOBAL ITEM DROP",
                description="A mysterious item appeared from the skies!\n\nUse `!claimdrop` first!",
                color=rarity_colors[rarity],
            )
            embed.add_field(name="U0001f381 Item", value=item_name)
            embed.add_field(name="✨ Rarity", value=rarity.capitalize())
            state.active_global_drop = {
                "type": "item",
                "item": {"name": item_name, "value": item_value, "rarity": rarity},
            }

        if drop_type == "item" and rarity in ("godly", "legendary"):
            hype = "U0001f30c A GODLY item has appeared!!! THE UNIVERSE TREMBLES!" if rarity == "godly" else "U0001f30c A LEGENDARY item has appeared!!!"
            await channel.send(hype)
        await channel.send(embed=embed)

    @spawn_global_drop.before_loop
    async def before_spawn_global_drop(self):
        await self.bot.wait_until_ready()


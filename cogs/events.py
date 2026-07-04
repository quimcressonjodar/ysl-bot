import random
import asyncio
import time
import logging

import discord
from discord.ext import commands, tasks
from datetime import timedelta

import state
from config import WELCOME_CHANNEL_ID, ADVENTURE_LOOT
from database import eco_col
logger = logging.getLogger("weekly-xp-bot")


GLOBAL_DROP_CHANNEL_ID = 1206197908399980575
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

    @tasks.loop(minutes=30) # Check more frequently but only spawn every 5 hours
    async def spawn_global_drop(self):
        # Check if 5 hours have passed since the last drop
        last_drop_time = state.last_global_drop_time if hasattr(state, 'last_global_drop_time') else 0
        if time.time() - last_drop_time < 18000: # 5 hours in seconds
            return

        channel = self.bot.get_channel(GLOBAL_DROP_CHANNEL_ID)
        state.last_global_drop_time = time.time()

        drop_type = random.choice(["coins", "coins", "coins", "item", "item"])

        if drop_type == "coins":
            reward = random.choice(GLOBAL_DROP_COIN_REWARDS)
            state.active_global_drop = {"type": "coins", "reward": reward}

            embed = discord.Embed(
                title="🌠 GLOBAL DROP",
                description=(
                    "💸 A MASSIVE treasure drop appeared!\nFirst person to claim it wins!\n"
                    "Use `!claimdrop` first!"
                ),
                color=0xF1C40F,
            )
            embed.add_field(name="💰 Coin Reward", value=f"🪙 {reward:,}")
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

            if rarity == "godly" and channel:
                await channel.send("🌌 A GODLY item has appeared!!! THE UNIVERSE TREMBLES!")
            elif rarity == "legendary" and channel:
                await channel.send("🌌 A LEGENDARY item has appeared!!!")

            state.active_global_drop = {
                "type": "item",
                "item": {"name": item_name, "value": item_value, "rarity": rarity},
            }

            rarity_colors = {
                "common": 0x95A5A6, "rare": 0x3498DB, "epic": 0x9B59B6, "legendary": 0xF1C40F, "godly": 0xFF00FF,
            }
            embed = discord.Embed(
                title="🌠 GLOBAL ITEM DROP",
                description="A mysterious item appeared from the skies!\n\nUse `!claimdrop` first!",
                color=rarity_colors[rarity],
            )
            embed.add_field(name="🎁 Item", value=item_name)
            embed.add_field(name="✨ Rarity", value=rarity.capitalize())

        if channel:
            await channel.send(embed=embed)

    @spawn_global_drop.before_loop
    async def before_spawn_global_drop(self):
        await self.bot.wait_until_ready()
        # Initialize last_drop_time if it doesn't exist
        if not hasattr(state, 'last_global_drop_time'):
            state.last_global_drop_time = 0

    @tasks.loop(hours=1)
    async def process_interests(self):
        """
        Procesa los intereses de los préstamos cada hora.
        Aplica un 2% de interés diario prorrateado por el tiempo transcurrido.
        """
        now = time.time()
        # Buscamos usuarios con préstamos activos (principal > 0)
        users_with_loans = eco_col.find({"loan_amount": {"$gt": 0}})
        
        for user_data in users_with_loans:
            user_id = user_data["_id"]
            last_calc = user_data.get("last_interest_calc", now)
            
            time_diff = now - last_calc
            # Si ha pasado al menos una hora (para evitar cálculos excesivos)
            if time_diff >= 3600:
                loan_amount = user_data.get("loan_amount", 0)
                # Tasa diaria del 2% (0.02). Calculamos la proporción del tiempo transcurrido.
                # interés = principal * tasa_diaria * (segundos_transcurridos / segundos_en_un_día)
                interest = int(loan_amount * 0.02 * (time_diff / 86400))
                
                if interest > 0:
                    eco_col.update_one(
                        {"_id": user_id},
                        {
                            "$inc": {"interest_accrued": interest},
                            "$set": {"last_interest_calc": now}
                        }
                    )
                    logger.info(f"Applied {interest} interest to user {user_id} for {time_diff/3600:.2f} hours")
                elif time_diff >= 86400:
                    # Si ha pasado un día pero el interés es 0 (préstamo muy pequeño),
                    # actualizamos el timestamp para evitar bucles infinitos
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
            return  # jail message already sent; swallow silently

        logger.error(f"Error in command {ctx.command}: {error}", exc_info=error)
        
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I don't have permission to do that.", ephemeral=True)
        elif isinstance(error, commands.CommandOnCooldown):
            next_ts = int(time.time() + error.retry_after)
            await ctx.send(f"⏳ This command is on cooldown. Try again <t:{next_ts}:R>.", ephemeral=True)
        else:
            await ctx.send(f"❌ An error occurred: {str(error)}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))

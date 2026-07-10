import discord
from discord.ext import commands, tasks
import time
from utils.bounties import get_active_bounties, spawn_new_bounty
from database import db
from config import STOCK_NEWS_CHANNEL_ID

class Bounties(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bounty_spawner.start()

    def cog_unload(self):
        self.bounty_spawner.cancel()

    @tasks.loop(hours=12)
    async def bounty_spawner(self):
        """Ensures there are always 3 active bounties on the board."""
        try:
            active = get_active_bounties()
            needed = 3 - len(active)

            if needed <= 0:
                return

            channel = self.bot.get_channel(STOCK_NEWS_CHANNEL_ID)

            for _ in range(needed):
                new_b = spawn_new_bounty()
                if not new_b:
                    continue

                # Announce each new bounty
                if channel:
                    embed = discord.Embed(
                        title="🎯 NEW BOUNTY POSTED",
                        description=f"A new contract is available on the board!\n\n**{new_b['name']}**\n{new_b['description']}",
                        color=0xE67E22
                    )
                    embed.add_field(name="💰 Reward", value=f"🪙 {new_b['reward']:,}")
                    embed.set_footer(text="Use !bounties to see all active contracts.")
                    await channel.send(embed=embed)
        except Exception as e:
            print(f"BOUNTY SPAWNER ERROR: {e}")

    @bounty_spawner.before_loop
    async def before_bounty_spawner(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(name="bounties", description="View active bounty contracts")
    async def bounties(self, ctx: commands.Context):
        active = get_active_bounties()
        
        if not active:
            return await ctx.send("📋 The bounty board is currently empty. Check back later!")

        embed = discord.Embed(title="🎯 Active Bounty Board", color=0xE67E22)
        
        for b in active:
            user_progress = b.get("participants", {}).get(str(ctx.author.id), 0)
            progress_bar = f"Progress: `{user_progress:,} / {b['goal']:,}`"
            
            embed.add_field(
                name=f"📜 {b['name']}",
                value=f"{b['description']}\n💰 Reward: 🪙 {b['reward']:,}\n📊 {progress_bar}",
                inline=False
            )
            
        embed.set_footer(text="Be the first to complete the goal to claim the reward!")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Bounties(bot))

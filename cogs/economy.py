import random
import time
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands

import state
from config import ROLE_SHOP
from database import eco_col
from utils.economy import (
    get_user_data,
    get_wallet,
    get_bank,
    update_wallet,
    update_bank,
    parse_economy_amount,
    get_debt,
    update_loan,
    update_interest,
    apply_amortization,
)
from views.economy_views import SellView


class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="balance", aliases=["bal"], description="Check your economy profile")
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        wallet = get_wallet(str(target.id))
        bank = get_bank(str(target.id))
        total = wallet + bank
        embed = discord.Embed(title=f"💳 {target.display_name}'s Economy", color=0x2B2D31)
        embed.add_field(name="💵 Wallet", value=f"🪙 {wallet:,}", inline=True)
        from utils.economy import get_prestige_level
        from config import PRESTIGE_LEVELS
        level = get_prestige_level(total)
        p_name = PRESTIGE_LEVELS[level]["name"] if level > 0 else "None"

        embed.add_field(name="🏦 Bank", value=f"🪙 {bank:,}", inline=True)
        embed.add_field(name="📈 Total Net Worth", value=f"🪙 {total:,}", inline=False)
        embed.add_field(name="🏆 Prestige", value=f"**{p_name}**", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="deposit", aliases=["dep"], description="Deposit coins into your bank")
    @app_commands.describe(amount="The amount to deposit ('all', 'half', or a number)")
    async def deposit(self, ctx: commands.Context, amount: str):
        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)
        parsed_amount = parse_economy_amount(amount, wallet)
        if parsed_amount <= 0:
            return await ctx.send("❌ Invalid amount. Please specify a positive number, 'all', or 'half'.", ephemeral=True)
        if parsed_amount > wallet:
            return await ctx.send(f"❌ You don't have enough coins. You only have 🪙 {wallet:,}.", ephemeral=True)
        update_wallet(user_id, -parsed_amount)
        update_bank(user_id, parsed_amount)
        embed = discord.Embed(
            title="🏦 Deposit Successful",
            description=f"You deposited 🪙 {parsed_amount:,} coins into your bank.",
            color=0x00FF00,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="withdraw", aliases=["with"], description="Withdraw coins from your bank")
    @app_commands.describe(amount="The amount to withdraw ('all', 'half', or a number)")
    async def withdraw(self, ctx: commands.Context, amount: str):
        user_id = str(ctx.author.id)
        bank = get_bank(user_id)
        parsed_amount = parse_economy_amount(amount, bank)
        if parsed_amount <= 0:
            return await ctx.send("❌ Invalid amount. Please specify a positive number, 'all', or 'half'.", ephemeral=True)
        if parsed_amount > bank:
            return await ctx.send(f"❌ You don't have enough bank coins. You only have 🪙 {bank:,} in the bank.", ephemeral=True)
        update_bank(user_id, -parsed_amount)
        update_wallet(user_id, parsed_amount)
        embed = discord.Embed(
            title="💸 Withdrawal Successful",
            description=f"You withdrew 🪙 {parsed_amount:,} coins from your bank.",
            color=0x3498DB,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="daily", description="Claim your daily free coins")
    async def daily(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        last_daily = user_data.get("last_daily")
        already_claimed = False

        if isinstance(last_daily, str):
            already_claimed = last_daily == today_str
        elif isinstance(last_daily, (int, float)):
            last_date = datetime.fromtimestamp(last_daily, tz=timezone.utc)
            already_claimed = last_date.strftime("%Y-%m-%d") == today_str
        elif hasattr(last_daily, "strftime"):
            already_claimed = last_daily.strftime("%Y-%m-%d") == today_str

        if already_claimed:
            next_midnight = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)
            return await ctx.send(
                f"❌ You already claimed your daily! Wait until <t:{int(next_midnight.timestamp())}:R>.",
                ephemeral=True,
            )

        base_amount = 1000
        amount = apply_amortization(user_id, base_amount)
        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"wallet": amount}, "$set": {"last_daily": today_str}},
            upsert=True,
        )
        
        # Bounty Tracking
        from utils.bounties import track_bounty_progress
        await track_bounty_progress(self.bot, user_id, "DAILY_CLAIMER", 1)
        
        msg = f"📆 You claimed your daily reward of 🪙 {base_amount:,} coins!"
        if amount < base_amount:
            msg += f"\n📉 🪙 {base_amount - amount:,} coins were automatically used to pay your debt."
        await ctx.send(msg)

    @commands.hybrid_command(name="weekly", description="Claim your massive weekly reward")
    async def weekly(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        now = datetime.now(timezone.utc)
        week_str = f"{now.year}-W{now.isocalendar()[1]}"
        last_weekly = user_data.get("last_weekly")
        already_claimed = False

        if isinstance(last_weekly, str):
            already_claimed = last_weekly == week_str
        elif isinstance(last_weekly, (int, float)):
            last_date = datetime.fromtimestamp(last_weekly, tz=timezone.utc)
            saved_week = f"{last_date.year}-W{last_date.isocalendar()[1]}"
            already_claimed = saved_week == week_str
        elif hasattr(last_weekly, "isocalendar"):
            saved_week = f"{last_weekly.year}-W{last_weekly.isocalendar()[1]}"
            already_claimed = saved_week == week_str

        if already_claimed:
            days_until_next_monday = 7 - now.weekday()
            next_monday = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=days_until_next_monday)
            return await ctx.send(
                f"❌ You already claimed your weekly! Wait until <t:{int(next_monday.timestamp())}:R>.",
                ephemeral=True,
            )

        base_amount = 25000
        amount = apply_amortization(user_id, base_amount)
        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"wallet": amount}, "$set": {"last_weekly": week_str}},
            upsert=True,
        )
        
        # Bounty Tracking
        from utils.bounties import track_bounty_progress
        await track_bounty_progress(self.bot, user_id, "DAILY_CLAIMER", 1)
        
        msg = f"✨ You claimed your weekly reward of 🪙 {base_amount:,} coins!"
        if amount < base_amount:
            msg += f"\n📉 🪙 {base_amount - amount:,} coins used to pay debt."
        await ctx.send(msg)

    @commands.hybrid_command(name="claim", description="Claim rewards from your roles")
    async def claim(self, ctx: commands.Context):
        await ctx.defer()
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        now = datetime.now(timezone.utc)
        last_claim = user_data.get("last_claim")

        if last_claim:
            if isinstance(last_claim, str):
                last_claim = datetime.fromisoformat(last_claim)
            elapsed = (now - last_claim).total_seconds()
            if elapsed < 3600:
                remaining = int(3600 - elapsed)
                next_claim_ts = int((now + timedelta(seconds=remaining)).timestamp())
                return await ctx.send(
                    f"❌ You already claimed your rewards. Try again <t:{next_claim_ts}:R>.",
                    ephemeral=True,
                )

        total = 0
        breakdown = []
        for key, data in ROLE_SHOP.items():
            role_id = data.get("role_id")
            if not role_id:
                continue
            role = ctx.guild.get_role(int(role_id))
            if role and role in ctx.author.roles:
                reward = data["claim"]
                total += reward
                breakdown.append(f"✨ **{role.name}** → 🪙 {reward:,}")

        if total == 0:
            return await ctx.send("❌ You don't own any claim roles.")

        actual_total = apply_amortization(user_id, total)
        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"wallet": actual_total}, "$set": {"last_claim": now.isoformat()}},
            upsert=True,
        )
        next_claim_ts = int(now.timestamp() + 3600)
        
        desc = "\n".join(breakdown)
        if actual_total < total:
            desc += f"\n\n📉 🪙 {total - actual_total:,} coins used to pay debt."
        desc += f"\n\nCome back <t:{next_claim_ts}:R> for more rewards."
        
        embed = discord.Embed(
            title="💰 Claim Rewards", 
            description=desc, 
            color=0x00FF99
        )
        embed.add_field(name="Total Received", value=f"🪙 {actual_total:,}", inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pay", description="Send coins to another member")
    @app_commands.describe(member="The member to send coins to", amount="Amount ('all', 'half', or number)")
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: str):
        sender_id = str(ctx.author.id)
        receiver_id = str(member.id)
        if member.bot:
            return await ctx.send("❌ You cannot send coins to bots.", ephemeral=True)
        if sender_id == receiver_id:
            return await ctx.send("❌ You cannot pay yourself.", ephemeral=True)
        sender_wallet = get_wallet(sender_id)
        parsed_amount = parse_economy_amount(amount, sender_wallet)
        if parsed_amount <= 0:
            return await ctx.send("❌ Invalid amount. Please use a positive number, 'all', or 'half'.", ephemeral=True)
        if sender_wallet < parsed_amount:
            return await ctx.send(f"❌ You only have 🪙 {sender_wallet:,} in your wallet.", ephemeral=True)
        update_wallet(sender_id, -parsed_amount)
        update_wallet(receiver_id, parsed_amount)
        embed = discord.Embed(
            title="💸 Payment Sent",
            description=f"{ctx.author.mention} sent 🪙 **{parsed_amount:,}** coins to {member.mention}.",
            color=0x00FF99,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="leaderboard", aliases=["lb", "top"], description="Shows the richest members")
    async def leaderboard(self, ctx: commands.Context):
        users = sorted(
            eco_col.find(),
            key=lambda u: u.get("wallet", 0) + u.get("bank", 0),
            reverse=True,
        )[:10]

        embed = discord.Embed(title="🏆 Global Economy Leaderboard", color=0xFFD700)
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        description = ""
        for index, user_data in enumerate(users, start=1):
            user_id = int(user_data["_id"])
            total = user_data.get("wallet", 0) + user_data.get("bank", 0)
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"Unknown User ({user_id})"
            medal = medals.get(index, f"`#{index}`")
            description += f"{medal} **{name}** — 🪙 {total:,}\n"
        embed.description = description
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="work", description="Work to earn coins")
    async def work(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        cooldown = 2700
        last_work = user_data.get("last_work", 0)
        now = time.time()
        if now - last_work < cooldown:
            next_work_ts = int(last_work + cooldown)
            return await ctx.send(f"⏳ You are too tired! Come back to work <t:{next_work_ts}:R>.", ephemeral=True)

        base_earnings = random.randint(250, 800)
        earnings = apply_amortization(user_id, base_earnings)
        
        jobs = [
            "developed a futuristic Discord bot for a billionaire", "won a late-night poker tournament",
            "repaired a military drone for a secret agency", "hacked into an abandoned crypto vault",
            "worked overtime at a cyberpunk nightclub", "delivered illegal space tacos across the galaxy",
            "streamed games for 14 hours straight", "sold rare dragon eggs on the black market",
            "worked as a bodyguard for a mafia boss", "found ancient treasure hidden underground",
            "completed dangerous bounty hunter missions", "managed a shady underground casino",
            "worked at a futuristic AI laboratory", "helped a millionaire recover lost crypto",
            "participated in illegal street races", "sold enchanted weapons to traveling merchants",
            "worked as a mercenary during clan wars", "created viral memes that exploded online",
            "found money hidden behind a vending machine", "worked at a haunted hotel overnight",
            "hacked the mainframe of a rival megacorp", "smuggled rare alien artifacts past customs",
            "won a high-stakes underground racing tournament", "tamed a wild cyber-dragon for a wealthy eccentric",
            "fixed the hyperdrive on a stranded space cruiser", "defused a ticking time bomb in the city square",
            "won a legendary rap battle against an AI",
        ]
        reason = random.choice(jobs)
        next_work_ts = int(now + cooldown)
        eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": earnings}, "$set": {"last_work": now}}, upsert=True)
        
        # Bounty Tracking
        from utils.bounties import track_bounty_progress
        await track_bounty_progress(self.bot, user_id, "WORKER", 1)
        
        desc = f"You {reason} and earned 🪙 **{earnings:,}** coins."
        if earnings < base_earnings:
            desc += f"\n📉 🪙 {base_earnings - earnings:,} coins were automatically used to pay your debt."
        desc += f"\n\nCome back <t:{next_work_ts}:R> for another shift."
        
        embed = discord.Embed(
            title="💼 Work Complete",
            description=desc,
            color=0x00FF99,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="crime", description="Commit a crime for big money, but risk getting caught!")
    async def crime(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        wallet = user_data.get("wallet", 0)
        cooldown = 7200
        last_crime = user_data.get("last_crime", 0)
        now = time.time()
        if now - last_crime < cooldown:
            next_crime_ts = int(last_crime + cooldown)
            return await ctx.send(
                f"⏳ The heat is too high! Lay low <t:{next_crime_ts}:R> before committing another crime.",
                ephemeral=True,
            )
        if wallet < 1000:
            return await ctx.send("❌ You need at least 🪙 1,000 in your wallet to commit a crime (to bribe the cops just in case).", ephemeral=True)

        success = random.choice([True, False])
        if success:
            base_earnings = random.randint(2000, 6500)
            earnings = apply_amortization(user_id, base_earnings)
            eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": earnings}, "$set": {"last_crime": now}}, upsert=True)
            msg = random.choice([
                "robbed an underground casino", "hacked a billionaire's bank account",
                "stole a cybernetic sports car", "smuggled rare alien artifacts",
                "sold counterfeit Protox skins on the black market",
            ])
            
            desc = f"You {msg} and got away with 🪙 **{base_earnings:,}** coins!"
            if earnings < base_earnings:
                desc += f"\n📉 🪙 {base_earnings - earnings:,} coins used to pay debt."
            eco_col.update_one({"_id": user_id}, {"$set": {"wanted_until": int(now + 2700)}}, upsert=True)
            desc += "\n\n🚨 **You are now WANTED** for 45 minutes. Watch your back!"

            # Bounty Tracking
            from utils.bounties import track_bounty_progress
            await track_bounty_progress(self.bot, user_id, "GAMBLER", base_earnings)

            embed = discord.Embed(title="🦹 Crime Successful", description=desc, color=0x2ECC71)
        else:
            fine = random.randint(1000, min(3500, wallet))
            eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": -fine}, "$set": {"last_crime": now}}, upsert=True)
            msg = random.choice([
                "tripped over a trash can while running from the cops", "left your ID at the crime scene",
                "tried to hack a government server but forgot to turn on your VPN",
                "got caught by a cybernetic guard dog", "were betrayed by your getaway driver",
            ])
            eco_col.update_one({"_id": user_id}, {"$set": {"wanted_until": int(now + 2700)}}, upsert=True)
            embed = discord.Embed(title="🚔 BUSTED!", description=f"You {msg}.\n\nYou were fined 🪙 **{fine:,}** coins.\n\n🚨 **You are now WANTED** for 45 minutes!", color=0xE74C3C)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="rob", description="Attempt to rob another member")
    async def rob(self, ctx: commands.Context, member: discord.Member):
        thief_id = str(ctx.author.id)
        target_id = str(member.id)
        user_data = get_user_data(thief_id)
        target_data = get_user_data(target_id)
        cooldown = 3600
        last_rob = user_data.get("last_rob", 0)
        now = time.time()
        if now - last_rob < cooldown:
            next_rob_ts = int(last_rob + cooldown)
            return await ctx.send(f"⏳ The cops are still looking for you! Lay low <t:{next_rob_ts}:R>.", ephemeral=True)
        if thief_id == target_id:
            return await ctx.send("❌ You cannot rob yourself.", ephemeral=True)
        if target_data.get("wallet", 0) < 300:
            return await ctx.send("❌ This user doesn't have enough wallet coins to rob.", ephemeral=True)

        success = random.choice([True, False])
        if success:
            base_stolen = random.randint(150, int(target_data.get("wallet", 0) * 0.30))
            stolen = apply_amortization(thief_id, base_stolen)
            eco_col.update_one({"_id": thief_id}, {"$inc": {"wallet": stolen}, "$set": {"last_rob": now}}, upsert=True)
            eco_col.update_one({"_id": target_id}, {"$inc": {"wallet": -base_stolen}}, upsert=True)
            msg = random.choice([
                "jumped through a window like a movie thief", "pickpocketed them during a crowded concert",
                "used fake security credentials to access their vault", "escaped through the rooftops after the robbery",
                "executed the perfect stealth mission", "used smoke grenades and escaped unseen",
                "hacked their crypto wallet remotely", "bribed the guards and walked out the front door",
                "used a teleporter to snatch their wallet", "distracted them with a hologram and grabbed the cash",
                "disguised yourself as a pizza delivery driver and looted the place",
            ])
            
            desc = f"You {msg}.\n\nYou stole 🪙 **{base_stolen:,}** from {member.mention}."
            if stolen < base_stolen:
                desc += f"\n📉 🪙 {base_stolen - stolen:,} coins used to pay debt."
            eco_col.update_one({"_id": thief_id}, {"$set": {"wanted_until": int(now + 2700)}}, upsert=True)
            desc += "\n\n🚨 **You are now WANTED** for 45 minutes. Watch your back!"

            # Bounty Tracking
            from utils.bounties import track_bounty_progress
            await track_bounty_progress(self.bot, thief_id, "ROBBER", 1)
            await track_bounty_progress(self.bot, thief_id, "GAMBLER", base_stolen)

            embed = discord.Embed(title="🥷 Successful Robbery", description=desc, color=0x00FF00)
        else:
            fine = random.randint(150, 500)
            eco_col.update_one(
                {"_id": thief_id},
                {"$inc": {"wallet": -fine}, "$set": {"last_rob": now, "wanted_until": int(now + 2700)}},
                upsert=True,
            )
            msg = random.choice([
                "tripped the alarm system", "got caught by security cameras",
                "accidentally robbed a police officer", "left fingerprints everywhere",
                "triggered laser security defenses", "was betrayed by your getaway driver",
                "got tackled by bodyguards", "got outsmarted by a decoy safe",
                "was chased down by a cybernetic guard dog", "dropped the loot while trying to escape over a fence",
                "sneezed loudly while hiding in the closet",
            ])
            embed = discord.Embed(
                title="🚨 Robbery Failed",
                description=(
                    f"You {msg}.\n\n"
                    f"You paid a fine of 🪙 **{fine:,}**.\n\n"
                    "🚨 **You are now WANTED** for 45 minutes. Watch your back!"
                ),
                color=0xFF0000,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="catch", description="Catch a wanted criminal and claim a reward")
    @commands.cooldown(1, 900, commands.BucketType.user)
    @app_commands.describe(member="The wanted criminal to catch")
    async def catch(self, ctx: commands.Context, member: discord.Member):
        catcher_id = str(ctx.author.id)
        target_id = str(member.id)

        if catcher_id == target_id:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("❌ You can't catch yourself!", ephemeral=True)

        target_data = get_user_data(target_id)
        now = time.time()
        wanted_until = target_data.get("wanted_until", 0)

        if wanted_until < now:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(f"❌ **{member.display_name}** is not wanted right now.", ephemeral=True)

        # 50% chance the criminal escapes
        if random.random() < 0.50:
            escape_msg = random.choice([
                "vanished into a crowd before you could react",
                "bribed a passerby to block your path",
                "jumped on a getaway bike and disappeared",
                "ducked into an alley and gave you the slip",
                "threw a smoke bomb and sprinted away",
                "disguised themselves at the last second",
                "spotted you coming and bolted before you got close",
            ])
            embed = discord.Embed(
                title="💨 They Got Away!",
                description=(
                    f"**{member.display_name}** {escape_msg}.\n\n"
                    "Better luck next time — they're still WANTED! 🚨"
                ),
                color=0xE74C3C,
            )
            return await ctx.send(embed=embed)

        # Success — clear wanted, jail the criminal, reward the catcher
        from utils.economy import set_jail
        from utils.bounties import track_bounty_progress

        reward = random.randint(500, 2000)
        release_ts = set_jail(target_id)
        eco_col.update_one({"_id": target_id}, {"$set": {"wanted_until": 0}}, upsert=True)
        update_wallet(catcher_id, reward)

        await track_bounty_progress(self.bot, catcher_id, "HUNTER", 1)

        remaining = int(wanted_until - now)
        embed = discord.Embed(
            title="🚔 Criminal Caught!",
            description=(
                f"You caught **{member.display_name}** and turned them in!\n"
                f"They had **{remaining // 60}m {remaining % 60}s** left on their wanted timer.\n\n"
                f"💰 Reward: 🪙 **{reward:,}** coins\n\n"
                f"🔒 **{member.display_name}** has been sent to jail until <t:{release_ts}:t> "
                f"(<t:{release_ts}:R>) and cannot use any commands."
            ),
            color=0x3498DB,
        )
        embed.set_footer(text=f"Your new wallet: 🪙 {get_wallet(catcher_id):,}")
        await ctx.send(embed=embed)

        # DM the jailed player
        try:
            jail_embed = discord.Embed(
                title="🔒 You've been sent to jail!",
                description=(
                    f"**{ctx.author.display_name}** caught you and turned you in.\n\n"
                    f"You cannot use any bot commands until <t:{release_ts}:t> (<t:{release_ts}:R>)."
                ),
                color=0xE74C3C,
            )
            await member.send(embed=jail_embed)
        except discord.Forbidden:
            pass

    @commands.hybrid_command(name="sell", description="Sell an item from your inventory")
    async def sell(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        from utils.economy import get_user_data as _get
        user_data = _get(user_id)
        inventory = user_data.get("inventory", [])
        if not inventory:
            return await ctx.send("🎒 Your inventory is empty.")
        embed = discord.Embed(title="💰 Sell Item", description="Choose an item to sell.", color=0xE67E22)
        _sell_view = SellView(ctx, inventory)
        _sell_view.message = await ctx.send(embed=embed, view=_sell_view)

    @commands.hybrid_command(name="inventory", aliases=["inv"], description="View your inventory")
    async def inventory(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        from utils.economy import get_user_data as _get
        user_data = _get(user_id)
        inventory = user_data.get("inventory", [])
        if not inventory:
            return await ctx.send("🎒 Your inventory is empty.")
        rarity_emojis = {
            "common": "⚪",
            "rare": "🔵",
            "epic": "🟣",
            "legendary": "🟡",
            "godly": "🌌",
        }
        embed = discord.Embed(title=f"🎒 {ctx.author.name}'s Inventory", color=0x2ECC71)
        total_value = 0
        text = ""
        for item in inventory[:25]:
            rarity = item["rarity"]
            emoji = rarity_emojis.get(rarity, "⚪")
            text += f"{emoji} {item['name']} • 🪙 {item['value']:,}\n"
            total_value += item["value"]
        embed.description = text
        embed.add_field(name="💰 Total Inventory Value", value=f"🪙 {total_value:,}", inline=False)
        embed.set_footer(text=f"{len(inventory)} items stored")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="claimdrop", description="Claim the active global drop")
    async def claimdrop(self, ctx: commands.Context):
        # Grab and clear the drop atomically (before any await) to prevent race conditions
        drop = state.active_global_drop
        if not drop:
            return await ctx.send("❌ No active global drop.")
        state.active_global_drop = None  # claimed — no one else can take it now
        user_id = str(ctx.author.id)
        if drop["type"] == "coins":
            base_reward = drop["reward"]
            reward = apply_amortization(user_id, base_reward)
            eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": reward}}, upsert=True)
            msg = f"🌠 {ctx.author.mention} claimed the drop and received 🪙 {reward:,}!"
            if reward < base_reward:
                msg += f"\n📉 🪙 {base_reward - reward:,} coins were automatically used to pay your debt."
            await ctx.send(msg)
        else:
            item = drop["item"]
            eco_col.update_one({"_id": user_id}, {"$push": {"inventory": item}}, upsert=True)
            await ctx.send(
                f"🌠 {ctx.author.mention} claimed:\n\n{item['name']} • {item['rarity'].capitalize()}!"
            )

    @commands.hybrid_command(name="loan", description="Request a loan from the clan bank")
    @app_commands.describe(amount="Amount to borrow (e.g. 1000 or 'max')")
    async def loan(self, ctx: commands.Context, amount: str):
        user_id = str(ctx.author.id)
        
        user_data = get_user_data(user_id)
        wallet = user_data.get("wallet", 0)
        bank = user_data.get("bank", 0)
        net_worth = max(0, wallet + bank)
        
        from utils.economy import get_prestige_level
        level = get_prestige_level(net_worth)
        
        # Credit limit based on prestige and net worth (ULTRA AGGRESSIVE)
        ratios = {
            0: 1.0,   # None: 100%
            1: 1.0,   # Bronze: 100%
            2: 2.0,   # Silver: 200%
            3: 5.0,   # Gold: 500%
            4: 10.0,  # Platinum: 1,000%
            5: 20.0,  # Emerald: 2,000%
            6: 50.0,  # Diamond: 5,000%
            7: 100.0  # Master: 10,000%
        }
        ratio = ratios.get(level, 1.0)
        # Minimum limit of 50,000 for new/poor players, otherwise use the aggressive ratio
        limit = max(50000, int(net_worth * ratio))

        # Parse amount
        if amount.lower() in ["max", "all"]:
            parsed_amount = limit
        else:
            try:
                parsed_amount = int(amount.replace(",", ""))
            except ValueError:
                return await ctx.send("❌ Invalid amount. Please use a number or 'max'.", ephemeral=True)

        # Validación de entrada
        if parsed_amount <= 0:
            if limit <= 0:
                return await ctx.send("❌ Your credit limit is 0 because you have no net worth.", ephemeral=True)
            return await ctx.send("❌ Please specify a positive amount.", ephemeral=True)
            
        current_debt = get_debt(user_id)
        if current_debt > 0:
            return await ctx.send(f"❌ You already have an active debt of 🪙 {current_debt:,}. Pay it back first!", ephemeral=True)

        if parsed_amount > limit:
            return await ctx.send(f"❌ Your credit limit is 🪙 {limit:,} based on your net worth and prestige.", ephemeral=True)

        # No fixed business cap anymore — rich enough players scale past it via
        # their own net worth-based credit limit. The only remaining ceiling
        # is MongoDB's storage limit (8-byte int), which would crash the bot
        # rather than being a real gameplay limit.
        from config import MAX_ECONOMY_AMOUNT
        if parsed_amount > MAX_ECONOMY_AMOUNT or wallet + parsed_amount > MAX_ECONOMY_AMOUNT:
            return await ctx.send(
                f"❌ Even your credit limit can't be paid out — it would exceed the safe storage limit of "
                f"🪙 **{MAX_ECONOMY_AMOUNT:,}**. Try a smaller amount.",
                ephemeral=True,
            )
            
        # Operación atómica para evitar duplicación
        now = time.time()
        result = eco_col.update_one(
            {"_id": user_id, "$or": [{"loan_amount": {"$exists": False}}, {"loan_amount": {"$lte": 0}}]},
            {
                "$inc": {"loan_amount": parsed_amount, "wallet": parsed_amount},
                "$set": {"last_interest_calc": now, "loan_start_time": now}
            }
        )
        
        if result.modified_count == 0:
            return await ctx.send("❌ Could not process loan. You might already have one or an error occurred.", ephemeral=True)
        
        embed = discord.Embed(
            title="🏦 Loan Approved",
            description=f"You borrowed 🪙 **{parsed_amount:,}** coins.\n\n⚠️ **Note:** A 2% interest will be applied every 24 hours. 30% of your future earnings will be automatically used to repay this loan.",
            color=0xF1C40F
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="repay", description="Repay your active loan")
    @app_commands.describe(amount="Amount to repay ('all', 'half', or number)")
    async def repay(self, ctx: commands.Context, amount: str):
        user_id = str(ctx.author.id)
        debt = get_debt(user_id)
        
        if debt <= 0:
            return await ctx.send("✅ You don't have any active loans to repay.", ephemeral=True)
            
        wallet = get_wallet(user_id)
        parsed_amount = parse_economy_amount(amount, min(wallet, debt))
        
        if parsed_amount <= 0:
            return await ctx.send("❌ Invalid amount. Please specify a positive number, 'all', or 'half'.", ephemeral=True)
            
        if wallet < parsed_amount:
            return await ctx.send(f"❌ You don't have enough coins in your wallet. You need 🪙 {parsed_amount:,}.", ephemeral=True)
            
        user_data = get_user_data(user_id)
        interest = user_data.get("interest_accrued", 0)
        
        # Pay interest first, then principal, all in one atomic update
        if parsed_amount <= interest:
            eco_col.update_one(
                {"_id": user_id},
                {
                    "$inc": {
                        "interest_accrued": -parsed_amount,
                        "wallet": -parsed_amount
                    }
                }
            )
        else:
            remaining = parsed_amount - interest
            eco_col.update_one(
                {"_id": user_id},
                {
                    "$inc": {
                        "interest_accrued": -interest,
                        "loan_amount": -remaining,
                        "wallet": -parsed_amount
                    }
                }
            )
        
        new_debt = get_debt(user_id)
        
        # Bounty Tracking
        from utils.bounties import track_bounty_progress
        await track_bounty_progress(self.bot, user_id, "LOAN_PAYER", parsed_amount)
        
        embed = discord.Embed(
            title="🏦 Loan Repayment",
            description=f"You repaid 🪙 **{parsed_amount:,}** coins.\n\n**Remaining Debt:** 🪙 {new_debt:,}",
            color=0x2ECC71
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="debt", description="Check your current debt status")
    async def debt(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        loan = user_data.get("loan_amount", 0)
        
        if loan <= 0 and user_data.get("interest_accrued", 0) <= 0:
            return await ctx.send("✅ You are debt-free! Congratulations.")

        # Use get_debt to get the dynamically calculated total including pending interest
        total = get_debt(user_id)
        interest = total - loan
        
        last_calc = user_data.get("last_interest_calc", time.time())
        # Next calculation is in 1 hour (since process_interests runs hourly)
        next_calc = int(last_calc + 3600)
        
        embed = discord.Embed(title="📉 Financial Debt Report", color=0xFF2A2A)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        
        desc = (
            f"### 🏦 Outstanding Balance\n"
            f"> **Total Owed:** 🪙 `{total:,}`\n\n"
            f"**Details:**\n"
            f"💵 **Principal:** 🪙 `{loan:,}`\n"
            f"📈 **Accrued Interest:** 🪙 `{interest:,}`\n\n"
            f"--- \n"
            f"📊 **Interest Rate:** `2% daily` (Calculated hourly)\n"
            f"⏳ **Next Update:** <t:{next_calc}:R>\n"
            f"📉 **Auto-Payment:** `30%` of all future earnings"
        )
        embed.description = desc
        embed.set_footer(text="Pay back your loan with !repay to avoid further interest.")
        
        await ctx.send(embed=embed)


    @commands.hybrid_command(name="prestige", description="Check your wealth prestige milestones")
    async def prestige(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)
        bank = get_bank(user_id)
        net_worth = wallet + bank
        
        from utils.economy import get_prestige_level
        from config import PRESTIGE_LEVELS
        
        current_level = get_prestige_level(net_worth)
        
        embed = discord.Embed(title="🏆 Wealth Prestige Milestones", color=0xFFD700)
        embed.description = f"Your Net Worth: **🪙 {net_worth:,}**\n\n"
        
        for level, data in PRESTIGE_LEVELS.items():
            indicator = "✅" if level <= current_level else "🔒"
            text = (
                f"{indicator} **{data['name']}**\n"
                f"• Required: 🪙 {data['threshold']:,}\n"
                f"• Shop Discount: {data['discount']*100}%\n"
            )
            embed.add_field(name="\u200b", value=text, inline=False)
            
        embed.set_footer(text="Reach higher wealth to unlock permanent discounts!")
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))

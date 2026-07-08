import uuid
import time
import uuid
import random

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import PET_SHOP, ROLE_SHOP, FOOD_ITEMS
from database import pets_col, eco_col
from utils.economy import get_wallet, update_wallet
from utils.pets import get_current_hunger, get_pet_state, is_pet_dead
from views.pet_views import AdventureView, BattleRequestView, ShopView, SellPetView, FeedView


class PetsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_load(self):
        self.pet_death_task.start()
        self.bot.loop.create_task(self.migrate_pets())

    def cog_unload(self):
        self.pet_death_task.cancel()

    async def migrate_pets(self):
        all_pet_owners = pets_col.find()
        now = time.time()
        for owner_data in all_pet_owners:
            user_id = owner_data["_id"]
            pets = owner_data.get("pets", [])
            updated = False
            for pet in pets:
                if "hunger" not in pet:
                    pet["hunger"] = 100
                    pet["last_fed"] = now
                    updated = True
            if updated:
                pets_col.update_one({"_id": user_id}, {"$set": {"pets": pets}})

    @tasks.loop(hours=24)
    async def pet_death_task(self):
        all_pet_owners = pets_col.find()
        for owner_data in all_pet_owners:
            user_id = owner_data["_id"]
            pets = owner_data.get("pets", [])
            new_pets = []
            removed = []
            
            for pet in pets:
                if is_pet_dead(pet):
                    removed.append(pet['type'].capitalize())
                else:
                    new_pets.append(pet)
            
            if removed:
                pets_col.update_one({"_id": user_id}, {"$set": {"pets": new_pets}})
                try:
                    user = self.bot.get_user(int(user_id))
                    if user:
                        await user.send(f"☠️ Your pet(s) {', '.join(removed)} have died from neglect.")
                except:
                    pass

    async def _send_response(self, target, content=None, embed=None, view=None, ephemeral=False):
        if isinstance(target, discord.Interaction):
            await target.response.send_message(content=content, embed=embed, view=view, ephemeral=ephemeral)
        else:
            await target.send(content=content, embed=embed, view=view)

    async def _process_shop(self, target, action: str = "view", pet_name: str = None):
        guild = target.guild
        author = target.user if isinstance(target, discord.Interaction) else target.author
        user_id = str(author.id)

        if action.lower() == "view":
            view = ShopView(target, PET_SHOP, ROLE_SHOP)
            embed = view._build_embed(guild)
            if isinstance(target, discord.Interaction):
                await target.response.send_message(embed=embed, view=view)
            else:
                view.message = await target.send(embed=embed, view=view)
            return

        if action.lower() == "buy":
            if not pet_name:
                return await self._send_response(target, content="❌ Please specify a pet, role, or food name.")

            item_key = pet_name.lower()
            balance = get_wallet(user_id)

            from utils.economy import get_prestige_level, get_bank
            from config import PRESTIGE_LEVELS
            wallet_bal = get_wallet(user_id)
            bank_bal = get_bank(user_id)
            net_worth = wallet_bal + bank_bal
            level = get_prestige_level(net_worth)
            discount = PRESTIGE_LEVELS[level]["discount"] if level > 0 else 0.0

            if item_key in FOOD_ITEMS:
                food_data = FOOD_ITEMS[item_key]
                price = int(food_data["price"] * (1 - discount))
                if balance < price:
                    return await self._send_response(target, content=f"❌ You need 🪙 {price:,}")
                
                from database import eco_col
                item = {
                    "name": food_data["name"],
                    "type": "food",
                    "hunger_gain": food_data["hunger"],
                    "rarity": "common",
                    "value": int(food_data["price"] * 0.5),
                    "key": item_key
                }
                eco_col.update_one({"_id": user_id}, {"$push": {"inventory": item}}, upsert=True)
                update_wallet(user_id, -price)
                
                # Bounty Tracking
                from utils.bounties import track_bounty_progress
                await track_bounty_progress(self.bot, user_id, "BIG_SPENDER", price)
                
                embed = discord.Embed(
                    title="🍱 Food Purchased",
                    description=f"You bought {food_data['emoji']} **{food_data['name']}**!",
                    color=0x00FF00,
                )
                return await self._send_response(target, embed=embed)

            if item_key in PET_SHOP:
                pet_data = PET_SHOP[item_key]
                price = int(pet_data["price"] * (1 - discount))
                if balance < price:
                    return await self._send_response(target, content=f"❌ You need 🪙 {price:,}")
                pet_instance = {
                    "pet_id": str(uuid.uuid4()),
                    "type": item_key,
                    "hp": pet_data["hp"],
                    "damage": pet_data["damage"],
                    "hunger": 100,
                    "last_fed": time.time(),
                }
                pets_col.update_one({"_id": user_id}, {"$push": {"pets": pet_instance}}, upsert=True)
                update_wallet(user_id, -price)
                
                # Bounty Tracking
                from utils.bounties import track_bounty_progress
                await track_bounty_progress(self.bot, user_id, "BIG_SPENDER", price)
                
                embed = discord.Embed(
                    title="🎉 Pet Purchased",
                    description=f"You bought a {pet_data['emoji']} **{item_key.capitalize()}**!",
                    color=0x00FF00,
                )
                return await self._send_response(target, embed=embed)

            if item_key in ROLE_SHOP:
                role_data = ROLE_SHOP[item_key]
                price = int(role_data["price"] * (1 - discount))
                if balance < price:
                    return await self._send_response(target, content=f"❌ You need 🪙 {price:,}")
                role = guild.get_role(int(role_data["role_id"]))
                if not role:
                    return await self._send_response(target, content=f"❌ Role ID {role_data['role_id']} not found.")
                if role in author.roles:
                    return await self._send_response(target, content="❌ You already own this role.")
                update_wallet(user_id, -price)
                await author.add_roles(role)
                
                # Bounty Tracking
                from utils.bounties import track_bounty_progress
                await track_bounty_progress(self.bot, user_id, "BIG_SPENDER", price)
                
                embed = discord.Embed(
                    title="💎 Role Purchased",
                    description=(
                        f"You bought **{role.name}**\n\n"
                        f"Cost: 🪙 {price:,}\n"
                        f"Claim: 🪙 {role_data['claim']:,}/hour"
                    ),
                    color=0xF1C40F,
                )
                return await self._send_response(target, embed=embed)

            return await self._send_response(target, content="❌ That pet or role does not exist.")

    @commands.hybrid_command(name="shop", aliases=["buy"], description="View and buy pets or roles")
    @app_commands.describe(
        action="Choose 'view' to see the shop or 'buy' to purchase",
        pet_name="Name of the pet or role to buy",
)
    async def shop(self, ctx: commands.Context, action: str = "view", pet_name: str = None):
        await self._process_shop(ctx, action, pet_name)

    

    @commands.hybrid_command(name="pets", description="View your pets")
    async def pets(self, ctx: commands.Context):
        data = pets_col.find_one({"_id": str(ctx.author.id)})
        if not data or not data.get("pets"):
            return await ctx.send("❌ You don't own any pets.")
        embed = discord.Embed(title=f"🐾 {ctx.author.display_name}'s Pets", color=0x3498DB)
        
        # Sort pets by price from PET_SHOP
        sorted_pets = sorted(
            data["pets"], 
            key=lambda p: PET_SHOP.get(p["type"].lower(), {}).get("price", 0)
        )
        
        for pet in sorted_pets:
            hunger = get_current_hunger(pet)
            state_name, _ = get_pet_state(pet)
            embed.add_field(
                name=f"🐾 {pet['type'].capitalize()} ({state_name})",
                value=f"❤️ HP: {pet['hp']}\n⚔️ Damage: {pet['damage']}\n🍖 Hunger: {int(hunger)}/100",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="feed", description="Feed your pet")
    async def feed(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_pets_data = pets_col.find_one({"_id": user_id})
        if not user_pets_data or not user_pets_data.get("pets"):
            return await ctx.send("❌ You don't own any pets.")
        
        user_data = eco_col.find_one({"_id": user_id})
        inventory = user_data.get("inventory", []) if user_data else []
        food_items = [item for item in inventory if item.get("type") == "food"]
        
        if not food_items:
            return await ctx.send("❌ You don't have any food in your inventory! Buy some in the `/shop`.")
        
        _feed_view = FeedView(ctx, user_pets_data["pets"], food_items)
        _feed_view.message = await ctx.send("🍖 Select a pet and food to feed:", view=_feed_view)

    @commands.hybrid_command(name="battle", description="Battle your pet against another member's pet!")
    async def battle(self, ctx: commands.Context, opponent: discord.Member):
        if opponent.bot:
            return await ctx.send("❌ You can't battle a bot!", ephemeral=True)
        if opponent.id == ctx.author.id:
            return await ctx.send("❌ You can't battle yourself!", ephemeral=True)

        user_id = str(ctx.author.id)
        opp_id = str(opponent.id)
        user_pets_data = pets_col.find_one({"_id": user_id})
        opp_pets_data = pets_col.find_one({"_id": opp_id})

        if not user_pets_data or not user_pets_data.get("pets"):
            return await ctx.send("❌ You don't have any pets!")
        
        if all(get_current_hunger(p) < 30 for p in user_pets_data["pets"]):
            return await ctx.send("😿 Your pet is too weak and needs food before it can participate.")

        if not opp_pets_data or not opp_pets_data.get("pets"):
            return await ctx.send(f"❌ {opponent.display_name} has no pets!")
        
        if all(get_current_hunger(p) < 30 for p in opp_pets_data["pets"]):
            return await ctx.send(f"❌ {opponent.display_name}'s pets are too weak to fight right now.")

        embed = discord.Embed(
            title="⚔️ Pet Battle Challenge",
            description=(
                f"{ctx.author.mention} has challenged {opponent.mention} to a pet battle!\n\n"
                "Waiting for response..."
            ),
            color=0xE74C3C,
        )
        view = BattleRequestView(ctx, opponent)
        view.message = await ctx.send(content=opponent.mention, embed=embed, view=view)

    @commands.hybrid_command(name="adventures", aliases=["adv"], description="Send your pet on an adventure")
    async def adventures(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_pets = pets_col.find_one({"_id": user_id})
        if not user_pets or not user_pets.get("pets"):
            return await ctx.send("❌ You don't own any pets.", ephemeral=True)
        
        if all(get_current_hunger(p) < 30 for p in user_pets["pets"]):
            return await ctx.send("😿 Your pet is too weak and needs food before it can participate.")

        _adv_view = AdventureView(ctx, user_pets["pets"])
        _adv_view.message = await ctx.send("🌍 Choose a pet for the adventure:", view=_adv_view)

    @commands.hybrid_command(name="sell_pet", description="Sell one of your pets for 50% of its shop price")
    async def sell_pet(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_pets_data = pets_col.find_one({"_id": user_id})
        if not user_pets_data or not user_pets_data.get("pets"):
            return await ctx.send("❌ You don't own any pets.")
        
        embed = discord.Embed(title="💰 Sell Pet", description="Choose a pet to sell back to the shop.", color=0xE67E22)
        _sell_pet_view = SellPetView(ctx, user_pets_data["pets"])
        _sell_pet_view.message = await ctx.send(embed=embed, view=_sell_pet_view)

    @commands.hybrid_command(name="breed", description="Breed two pets to create a stronger one!")
    async def breed(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_pets_data = pets_col.find_one({"_id": user_id})
        if not user_pets_data or len(user_pets_data.get("pets", [])) < 2:
            return await ctx.send("❌ You need at least 2 pets to breed.")
        
        from views.pet_views import BreedView
        embed = discord.Embed(
            title="🐾 Pet Breeding", 
            description="Select two pets to breed. This will cost 25% of their combined value.", 
            color=0xFF69B4
        )
        _breed_view = BreedView(ctx, user_pets_data["pets"])
        _breed_view.message = await ctx.send(embed=embed, view=_breed_view)


async def setup(bot: commands.Bot):
    await bot.add_cog(PetsCog(bot))

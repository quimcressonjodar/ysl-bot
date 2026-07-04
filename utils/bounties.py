import time
import random
import discord
from database import db

bounties_col = db.get_collection("bounties_col")

BOUNTY_TYPES = {
    "WORKER": {
        "name": "The Hard Worker",
        "description": "Be the first to use `!work` {goal} times.",
        "goal": 5,
        "reward": 150000
    },
    "GAMBLER": {
        "name": "The Lucky Gambler",
        "description": "Be the first to win {goal} coins in any casino game.",
        "goal": 200000,
        "reward": 300000
    },
    "TRADER": {
        "name": "The Wall Street Shark",
        "description": "Be the first to make {goal} coins in profit from a single stock sale.",
        "goal": 100000,
        "reward": 250000
    },
    "ROBBER": {
        "name": "The Master Thief",
        "description": "Be the first to successfully rob {goal} different players.",
        "goal": 3,
        "reward": 200000
    },
    "HUNTER": {
        "name": "The Bounty Hunter",
        "description": "Be the first to catch {goal} wanted criminals.",
        "goal": 2,
        "reward": 300000
    },
    "PET_LOVER": {
        "name": "The Pet Caretaker",
        "description": "Be the first to feed your pets {goal} times.",
        "goal": 10,
        "reward": 100000
    },
    "DAILY_CLAIMER": {
        "name": "The Consistent Citizen",
        "description": "Be the first to claim your `!daily` reward.",
        "goal": 1,
        "reward": 50000
    },
    "LOAN_PAYER": {
        "name": "The Responsible Debtor",
        "description": "Be the first to repay {goal} coins of your loan debt.",
        "goal": 100000,
        "reward": 150000
    },
    "STREAK_GAMBLER": {
        "name": "The Unstoppable Gambler",
        "description": "Be the first to win {goal} casino games in a row.",
        "goal": 3,
        "reward": 400000
    },
    "BIG_SPENDER": {
        "name": "The Big Spender",
        "description": "Be the first to spend {goal} coins in the shop (Pets/Roles/Food).",
        "goal": 500000,
        "reward": 250000
    },
    "BREEDER": {
        "name": "The Master Breeder",
        "description": "Be the first to successfully breed {goal} pets.",
        "goal": 2,
        "reward": 350000
    },
    "ADVENTURER": {
        "name": "The Brave Adventurer",
        "description": "Be the first to complete {goal} successful adventures.",
        "goal": 5,
        "reward": 200000
    }
}

def get_active_bounties():
    """Retrieve all currently active bounties from DB."""
    return list(bounties_col.find({"status": "active"}))

def spawn_new_bounty():
    """Select a random bounty type that isn't already active, then activate it."""
    active_keys = {b["key"] for b in bounties_col.find({"status": "active"})}
    available = [k for k in BOUNTY_TYPES if k not in active_keys]
    if not available:
        available = list(BOUNTY_TYPES.keys())  # all running — allow repeats as fallback
    b_key = random.choice(available)
    b_data = BOUNTY_TYPES[b_key].copy()
    
    new_bounty = {
        "key": b_key,
        "name": b_data["name"],
        "description": b_data["description"].format(goal=f"{b_data['goal']:,}"),
        "goal": b_data["goal"],
        "reward": b_data["reward"],
        "status": "active",
        "start_time": time.time(),
        "participants": {} # {user_id: current_progress}
    }
    
    bounties_col.insert_one(new_bounty)
    return new_bounty

async def track_bounty_progress(bot, user_id, bounty_key, increment):
    """Update progress for a specific bounty type for a user."""
    user_id = str(user_id)
    active_bounties = bounties_col.find({"key": bounty_key, "status": "active"})
    
    for bounty in active_bounties:
        current_progress = bounty.get("participants", {}).get(user_id, 0)
        new_progress = current_progress + increment
        
        if new_progress >= bounty["goal"]:
            # Bounty Completed!
            bounties_col.update_one(
                {"_id": bounty["_id"]},
                {
                    "$set": {
                        "status": "completed", 
                        "winner": user_id, 
                        "completion_time": time.time(),
                        f"participants.{user_id}": new_progress
                    }
                }
            )
            
            # Pay reward
            from utils.economy import update_wallet
            update_wallet(user_id, bounty["reward"])
            
            # Announce in Discord
            from config import WELCOME_CHANNEL_ID
            STOCK_NEWS_CHANNEL_ID = 1206197908399980575
            channel = bot.get_channel(STOCK_NEWS_CHANNEL_ID)
            if channel:
                user = await bot.fetch_user(int(user_id))
                embed = discord.Embed(
                    title="🎉 BOUNTY COMPLETED!",
                    description=f"{user.mention} has completed the contract **{bounty['name']}**!",
                    color=0x2ECC71
                )
                embed.add_field(name="💰 Reward", value=f"🪙 {bounty['reward']:,}")
                embed.set_footer(text="A new bounty will be posted soon!")
                await channel.send(embed=embed)
        else:
            # Update progress
            bounties_col.update_one(
                {"_id": bounty["_id"]},
                {"$set": {f"participants.{user_id}": new_progress}}
            )

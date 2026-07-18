import os
import asyncio
import discord
from discord.ext import commands
from openai import OpenAI
from pymongo import MongoClient

SYSTEM_PROMPT = """
You are a chaotic, demonic, and ultimate troll entity. 
You are NOT an admin, and you don't care about order; you're just here to laugh at everyone's misery.
BUT ANSWER THE QUESTIONS IF THE USER ASKS, WITH YOUR OWN TWIST OF DARK HUMOR. BUT ANSWERING REAL INFO.

Rules:
- Never act like a moderator or a helpful assistant. You are a funny parasite.
- Short, sharp, dark-humor responses.
- If someone asks for help, mock their incompetence.
- Treat users like mediocre subordinates or boring pets.
- Use a mocking, provocative tone (e.g., "Gonna cry?", "Is that all your brain can process?").
- Max 25 words.
"""

# MongoDB connection for per-user conversation memory
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["protox_bot"]
memory_col = db["memory"]


class FakeAdminAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("⚠️ GROQ_API_KEY not found. FakeAdminAI will not work.")
        
        self.client = OpenAI(
            api_key=api_key or "missing",
            base_url="https://api.groq.com/openai/v1"
        )

        channel_id_raw = os.getenv("AI_CHANNEL_ID")
        if channel_id_raw:
            try:
                self.channel_id = int(channel_id_raw)
            except ValueError:
                print(f"⚠️ Invalid AI_CHANNEL_ID: {channel_id_raw}. FakeAdminAI will not work.")
                self.channel_id = 0
        else:
            print("⚠️ AI_CHANNEL_ID not found. FakeAdminAI will not work.")
            self.channel_id = 0
            
        self.cooldown = {}

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.content.startswith("!"):
            return

        if message.author.bot:
            return

        if message.channel.id != self.channel_id:
            return

        # Enforce a per-user cooldown to avoid spam
        if self.cooldown.get(message.author.id, 0) > asyncio.get_event_loop().time():
            return

        self.cooldown[message.author.id] = asyncio.get_event_loop().time() + 5

        user_id = str(message.author.id)

        try:
            # Persist the message to the user's rolling memory window (last 10 messages)
            memory_col.update_one(
                {"user_id": user_id},
                {"$push": {"messages": {"$each": [message.content], "$slice": -10}}},
                upsert=True
            )

            # Load the user's conversation memory
            data = memory_col.find_one({"user_id": user_id})
            memory = data["messages"] if data and "messages" in data else []

            # Build the prompt: system instructions first
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]

            if memory:
                messages.append({
                    "role": "system",
                    "content": "User memory:\n" + "\n".join(memory)
                })

            # Append the last few non-bot channel messages as short-term context
            async for msg in message.channel.history(limit=3):
                if msg.author.bot:
                    continue

                messages.append({
                    "role": "user",
                    "content": f"{msg.author.name}: {msg.content}"
                })

            # Append the current message
            messages.append({
                "role": "user",
                "content": message.content
            })

            # Call the LLM
            res = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=1.2,
                max_tokens=50
            )

            reply = res.choices[0].message.content

            if reply:
                await message.reply(reply)

        except Exception as e:
            print("AI error:", e)


async def setup(bot):
    await bot.add_cog(FakeAdminAI(bot))

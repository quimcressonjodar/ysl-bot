"""
AutoReply cog — fuzzy keyword triggers with per-channel cooldowns.
"""
import difflib
import logging
import time

import discord
from discord.ext import commands

logger = logging.getLogger("weekly-xp-bot")

# Cooldown in seconds per trigger per channel
COOLDOWN = 60

# XP channel (used in the leveling reply)
XP_CHANNEL_ID = 1512485221541478402

# ── Trigger definitions ───────────────────────────────────────────────────────
# Each entry: (trigger_id, keywords, reply_factory)
# reply_factory(message) → str | discord.Embed

def _modmail_reply(message: discord.Message):
    embed = discord.Embed(
        title="📬 Need to reach Staff?",
        description=(
            "Just **DM me** and I'll open a Modmail ticket for you!\n\n"
            "Your message goes straight to the staff team — we'll get back to you ASAP."
        ),
        color=0x9B59B6,
    )
    embed.set_footer(text="YSL Helper • Modmail System")
    return embed


def _leveling_reply(message: discord.Message):
    embed = discord.Embed(
        title="📈 How Leveling Works",
        description=(
            "Chat in any channel to earn XP!\n\n"
            "• Messages must have **more than one word** — no spam counting\n"
            "• There's a short cooldown between XP gains\n"
            "• The more active you are, the faster you rank up!\n\n"
            "Check your level with **`!rank`**, message leaderboard with **`!msgtop`** and XP leaderboard with **`!lvltop`**"
        ),
        color=0x2ECC71,
    )
    embed.set_footer(text="YSL Helper • Leveling System")
    return embed


def _bot_reply(message: discord.Message):
    embed = discord.Embed(
        title="🤖 YSL Helper — What can I do?",
        description=(
            "I'm the official bot for the **YSL clan** on Protox.io!\n\n"
            "Here's what I've got:"
        ),
        color=0xF1C40F,
    )
    embed.add_field(
        name="💰 Economy",
        value="Earn coins, open businesses, trade stocks, bet on horse races and more with `!help`",
        inline=False,
    )
    embed.add_field(
        name="📈 Leveling",
        value="Gain XP by chatting, rank up and earn exclusive roles",
        inline=False,
    )
    embed.add_field(
        name="📬 Modmail",
        value="DM me anytime to open a private ticket with staff",
        inline=False,
    )
    embed.add_field(
        name="🎮 Games & Pets",
        value="Minigames, pet collecting, bounties and clan events",
        inline=False,
    )
    embed.set_footer(text="YSL Helper • Type !help for commands")
    return embed


TRIGGERS = [
    {
        "id": "modmail",
        "keywords": [
            "modmail", "mod mail", "dm the bot", "dm me", "contact staff",
            "open ticket", "open a ticket", "report someone", "reach staff",
            "talk to staff", "message staff",
        ],
        "reply": _modmail_reply,
    },
    {
        "id": "leveling",
        "keywords": [
            "level up", "levelup", "leveling", "how do i level", "gain xp",
            "earn xp", "get xp", "how xp works", "xp system", "rank up",
            "how does leveling", "how do you level",
        ],
        "reply": _leveling_reply,
    },
    {
        "id": "bot_info",
        "keywords": [
            "ysl bot", "ysl helper", "what is the bot", "what can the bot do",
            "bot commands", "what does the bot do", "what does ysl bot do",
            "how does the bot work", "bot info", "about the bot",
        ],
        "reply": _bot_reply,
    },
]


# ── Fuzzy match helper ────────────────────────────────────────────────────────

def _matches(text: str, keywords: list[str], threshold: float = 0.82) -> bool:
    """
    Returns True if `text` contains any keyword (substring) or is
    close enough via SequenceMatcher ratio (fuzzy).
    """
    text_lower = text.lower()
    for kw in keywords:
        # Direct substring match
        if kw in text_lower:
            return True
        # Fuzzy match against every same-length window in the text
        kw_len = len(kw)
        for i in range(len(text_lower) - kw_len + 1):
            window = text_lower[i:i + kw_len]
            ratio = difflib.SequenceMatcher(None, kw, window).ratio()
            if ratio >= threshold:
                return True
    return False


# ── Cog ───────────────────────────────────────────────────────────────────────

class AutoReplyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # {(channel_id, trigger_id): last_fired_timestamp}
        self._cooldowns: dict[tuple[int, str], float] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots and DMs
        if message.author.bot or message.guild is None:
            return
        # Ignore commands
        if message.content.startswith("!"):
            return

        content = message.content.strip()
        if not content:
            return

        now = time.monotonic()

        for trigger in TRIGGERS:
            tid = trigger["id"]
            key = (message.channel.id, tid)

            # Skip if on cooldown for this channel
            if now - self._cooldowns.get(key, 0) < COOLDOWN:
                continue

            if _matches(content, trigger["keywords"]):
                reply = trigger["reply"](message)
                try:
                    if isinstance(reply, discord.Embed):
                        await message.channel.send(embed=reply)
                    else:
                        await message.channel.send(reply)
                    self._cooldowns[key] = now
                    logger.info(
                        "AutoReply [%s] triggered by %s in #%s",
                        tid, message.author, message.channel,
                    )
                except discord.HTTPException as e:
                    logger.warning("AutoReply send failed: %s", e)
                # Only fire one trigger per message
                break


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoReplyCog(bot))

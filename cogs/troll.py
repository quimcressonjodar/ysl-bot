import random
import re
import discord
from discord.ext import commands

from config import OWNER_IDS

# ── UwU transformation ────────────────────────────────────────────────────────

CUTE_REPLACEMENTS = {
    "no": "nyo",
    "you": "chu",
    "love": "wuv",
    "what": "wat",
    "the": "da",
    "hi": "hewwo",
    "hello": "hewwo",
    "ok": "owkay",
    "okay": "owkay",
    "please": "pwease",
    "friend": "fwend",
    "cool": "kewl",
    "cute": "kawaii",
    "good": "gweat",
    "sorry": "sowwy",
    "thanks": "thankies",
    "thank you": "thankies",
    "yes": "yesh",
    "nice": "nyice",
    "wow": "wowie",
    "really": "weawwy",
    "right": "wight",
    "little": "wittle",
    "beautiful": "bewwiful",
    "stupid": "stoopid",
    "stop": "stahp",
    "come": "come hewe",
    "bro": "bwoo",
    "dude": "duude",
    "lol": "lolol",
    "lmao": "wmaoo",
    "omg": "owmg",
    "wtf": "wtheck",
}

TROLL_EMOJIS = ["🥺", "✨", "😭", "💖", "uwu", "OwO", "uwu~", "😳", "🌸", "💕", "🥹", "🫶", "😚", "🐾", "💫"]

TYPO_SWAPS = {
    "a": "aa", "e": "ee", "i": "ii", "o": "oo",
    "s": "ss", "t": "tt", "l": "ll", "n": "nn",
}


def _apply_uwu(text: str) -> str:
    # 1. Cute word replacements (case-insensitive, whole word)
    for word, replacement in CUTE_REPLACEMENTS.items():
        text = re.sub(rf'\b{re.escape(word)}\b', replacement, text, flags=re.IGNORECASE)

    # 2. r/l → w
    text = re.sub(r'(?<![a-zA-Z])[Rr](?=[a-zA-Z])', lambda m: 'W' if m.group().isupper() else 'w', text)
    text = re.sub(r'(?<![a-zA-Z])[Ll](?=[a-zA-Z])', lambda m: 'W' if m.group().isupper() else 'w', text)
    text = re.sub(r'(?<=[a-zA-Z])[Rr]', lambda m: 'W' if m.group().isupper() else 'w', text)
    text = re.sub(r'(?<=[a-zA-Z])[Ll]', lambda m: 'W' if m.group().isupper() else 'w', text)

    # 3. "n" before vowel → "ny" (nyan effect, ~40% chance per word)
    def nyanify(m):
        return m.group(1) + 'ny' + m.group(2) if random.random() < 0.4 else m.group(0)
    text = re.sub(r'([Nn])([aeiouAEIOU])', nyanify, text)

    # 4. Random stutter on first letter of some words (~20% chance)
    def stutter(m):
        if random.random() < 0.2:
            c = m.group(1)
            return f'{c}-{m.group(0)}'
        return m.group(0)
    text = re.sub(r'\b([a-zA-Z])([a-zA-Z]{2,})', stutter, text)

    # 5. Random single-character typo (~15% chance per word)
    words = text.split()
    result = []
    for word in words:
        if random.random() < 0.15 and len(word) > 3:
            idx = random.randint(0, len(word) - 1)
            char = word[idx].lower()
            if char in TYPO_SWAPS:
                word = word[:idx] + TYPO_SWAPS[char] + word[idx + 1:]
        result.append(word)
    text = ' '.join(result)

    # 6. Sprinkle emojis: 1 at the end, maybe 1 in the middle
    end_emoji = random.choice(TROLL_EMOJIS)
    text = text.rstrip() + f' {end_emoji}'
    if len(text.split()) > 6 and random.random() < 0.5:
        mid_emoji = random.choice(TROLL_EMOJIS)
        words = text.split()
        mid = len(words) // 2
        words.insert(mid, mid_emoji)
        text = ' '.join(words)

    return text


# ── Cog ───────────────────────────────────────────────────────────────────────

class TrollCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Set of user IDs currently in impostor mode
        self.impostor_users: set[int] = set()
        # Cache: channel_id → webhook
        self._webhook_cache: dict[int, discord.Webhook] = {}

    def _is_owner(self, ctx: commands.Context) -> bool:
        return ctx.author.id in OWNER_IDS

    # ── !impostor command ──────────────────────────────────────────────────────

    @commands.command(name="impostor", description="Toggle impostor mode for a user (Owner only)")
    async def impostor(self, ctx: commands.Context, member: discord.Member):
        if not self._is_owner(ctx):
            return  # Silently ignore — don't reveal the command exists

        # Delete the invoking command message
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        if member.id in self.impostor_users:
            self.impostor_users.discard(member.id)
            msg = await ctx.send(f"✅ Impostor mode **disabled** for {member.mention}.")
        else:
            self.impostor_users.add(member.id)
            msg = await ctx.send(f"👻 Impostor mode **enabled** for {member.mention}.")

        # Auto-delete feedback after 5 s
        await msg.delete(delay=5)

    # ── Webhook helper ─────────────────────────────────────────────────────────

    async def _get_webhook(self, channel: discord.TextChannel) -> discord.Webhook | None:
        """Return a bot-owned webhook for the channel, creating one if needed."""
        cached = self._webhook_cache.get(channel.id)
        if cached is not None:
            return cached
        try:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                # Prefer webhooks this bot owns with our tag name
                if wh.name == "ImpostorHook" and wh.user and wh.user.id == self.bot.user.id:
                    self._webhook_cache[channel.id] = wh
                    return wh
            # None found — create one
            wh = await channel.create_webhook(name="ImpostorHook")
            self._webhook_cache[channel.id] = wh
            return wh
        except (discord.Forbidden, discord.HTTPException):
            return None

    async def _send_via_webhook(
        self,
        channel: discord.TextChannel,
        content: str,
        username: str,
        avatar_url: str,
    ) -> bool:
        """Try to send through a webhook; retry once if the cached hook is stale."""
        for attempt in range(2):
            webhook = await self._get_webhook(channel)
            if webhook is None:
                return False
            try:
                await webhook.send(
                    content=content,
                    username=username,
                    avatar_url=avatar_url,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return True
            except discord.NotFound:
                # Webhook was deleted externally — invalidate cache and retry
                self._webhook_cache.pop(channel.id, None)
            except discord.HTTPException:
                return False
        return False

    # ── Message listener ───────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots, DMs, and non-impostor users
        if message.author.bot:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return
        if message.author.id not in self.impostor_users:
            return
        # Skip command messages (let the bot process them normally)
        if message.content.startswith("!"):
            return
        # Skip empty messages (e.g. image-only)
        if not message.content.strip():
            return

        transformed = _apply_uwu(message.content)
        username = message.author.display_name
        avatar_url = message.author.display_avatar.url

        # Send FIRST — only delete original if relay succeeded to avoid data loss
        sent = await self._send_via_webhook(message.channel, transformed, username, avatar_url)
        if sent:
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(TrollCog(bot))

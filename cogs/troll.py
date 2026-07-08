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
    # 1. Cute word replacements — only the most recognisable ones
    for word, replacement in CUTE_REPLACEMENTS.items():
        text = re.sub(rf'\b{re.escape(word)}\b', replacement, text, flags=re.IGNORECASE)

    # 2. r/l → w, ~85% of occurrences
    def maybe_w(m):
        if random.random() < 0.85:
            return 'W' if m.group().isupper() else 'w'
        return m.group()
    text = re.sub(r'[Rr]', maybe_w, text)
    text = re.sub(r'[Ll]', maybe_w, text)

    # 3. Occasional stutter on the first word only (~25% of messages)
    if random.random() < 0.25:
        def stutter(m):
            c = m.group(1)
            return f'{c}-{m.group(0)}'
        text = re.sub(r'\b([a-zA-Z])([a-zA-Z]{2,})', stutter, text, count=1)

    # 4. Typos: 1–2 per message, ~55% chance each word (words >3 chars)
    words = text.split()
    for i, word in enumerate(words):
        if len(word) > 3 and random.random() < 0.55:
            ci = random.randint(0, len(word) - 1)
            char = word[ci].lower()
            if char in TYPO_SWAPS:
                words[i] = word[:ci] + TYPO_SWAPS[char] + word[ci + 1:]
    text = ' '.join(words)

    # 5. Emoji: only ~35% of messages get one, always at the end
    if random.random() < 0.35:
        text = text.rstrip() + ' ' + random.choice(TROLL_EMOJIS)

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

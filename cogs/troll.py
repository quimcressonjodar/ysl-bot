import random
import re
import discord
from discord.ext import commands

from config import OWNER_IDS, IMPOSTOR_ALLOWED_IDS

# ── UwU transformation ────────────────────────────────────────────────────────

CUTE_REPLACEMENTS = {
    "no": "nyo",
    "you": "chu",
    "love": "wuv",
    "what": "wat",
    "the": "da",
    "that": "dat",
    "this": "dis",
    "is": "ish",
    "are": "awe",
    "was": "waz",
    "sad": "saaad",
    "bad": "baad",
    "mad": "maaad",
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
    "because": "becuz",
    "when": "wen",
    "why": "wai",
    "how": "howw",
    "just": "juwst",
    "but": "buwt",
    "so": "soo",
    "not": "nwot",
    "my": "mwy",
    "me": "mwe",
    "its": "itz",
    "it": "eet",
    "he": "hee",
    "she": "shee",
    "they": "dey",
    "we": "wee",
    "do": "doo",
    "can": "cwan",
    "will": "wiww",
    "got": "got >w<",
    "going": "goinggg",
    "idk": "idkk uwu",
    "ngl": "ngl bestie",
    "fr": "fwr",
    "bruh": "bwuh",
    "man": "myan",
    "guys": "guyyys",
}

TROLL_EMOJIS = ["🥺", "✨", "😭", "💖", "😳", "🌸", "💕", "🥹", "🫶", "😚", "🐾", "💫"]

UWU_FACES = ["OwO", "UwU", ":3", "^w^", ";;w;;", "uwu", ">w<", "^-^", "x3", "(◡ ω ◡)"]

ROLEPLAY_ACTIONS = [
    "***blushes***", "***screams***", "***sweats***", "***cries***",
    "***runs away***", "***looks at you***", "***screeches***",
    "***whispers to self***", "***wags my tail***", "***boops your nose***",
    "***huggles tightly***", "***nuzzles your necky wecky***",
    "***pounces on you***", "***walks away nervously***", "***smirks smugly***",
]

EXCLAMATION_REPLACEMENTS = {
    "!":  ["!", "!!", "!!!",  "!!11", "!!1!"],
    "?":  ["?", "??", "???", "?!", "?!?1", "?!?!"],
}

TYPO_SWAPS = {
    "a": "aa", "e": "ee", "i": "ii", "o": "oo",
    "s": "ss", "t": "tt", "l": "ll", "n": "nn",
}

# Regex to detect Discord tokens that must not be transformed
_PROTECT_RE = re.compile(
    r'(@everyone|@here)'          # global mentions
    r'|(<[@#!&][^>]+>)'           # user/channel/role mentions
    r'|(<a?:[a-zA-Z0-9_]+:\d+>)' # custom emoji
    r'|(https?://\S+)'            # URLs
)


def _apply_uwu(text: str) -> str:
    original = text
    # 0. Split into protected tokens and normal text so we never mangle
    #    mentions, custom emoji, or URLs.
    parts = []       # list of (is_protected, chunk)
    last = 0
    for m in _PROTECT_RE.finditer(text):
        if m.start() > last:
            parts.append((False, text[last:m.start()]))
        parts.append((True, m.group()))
        last = m.end()
    if last < len(text):
        parts.append((False, text[last:]))

    transformed = []
    for protected, chunk in parts:
        if protected:
            transformed.append(chunk)
            continue

        # 1. Cute word replacements
        for word, replacement in CUTE_REPLACEMENTS.items():
            chunk = re.sub(rf'\b{re.escape(word)}\b', replacement, chunk, flags=re.IGNORECASE)

        # 2. r / l  →  w  (~85 % of occurrences)
        def maybe_w(mo):
            return ('W' if mo.group().isupper() else 'w') if random.random() < 0.85 else mo.group()
        chunk = re.sub(r'[Rr]', maybe_w, chunk)
        chunk = re.sub(r'[Ll]', maybe_w, chunk)

        # 3. v before vowel → w  ("very" → "wery")
        chunk = re.sub(r'[Vv]([aeiouAEIOU])', lambda mo: ('W' if mo.group(0)[0].isupper() else 'w') + mo.group(1), chunk)

        # 4. Common letter-pattern substitutions (from uwuipy)
        chunk = re.sub(r'ove\b', 'uv', chunk, flags=re.IGNORECASE)
        chunk = re.sub(r'ose\b', 'owse', chunk, flags=re.IGNORECASE)
        chunk = re.sub(r'([Oo])h\b', r'\1wh', chunk)
        chunk = re.sub(r'([Nn])([aeiouAEIOU])', lambda mo: mo.group(1) + 'y' + mo.group(2) if random.random() < 0.5 else mo.group(), chunk)

        # 5. Exclamation mark multiplying
        def multi_exclaim(mo):
            return random.choice(EXCLAMATION_REPLACEMENTS[mo.group()])
        chunk = re.sub(r'[!?]', multi_exclaim, chunk)

        # 6. Doubled-letter typos (~55 % chance per word >3 chars)
        words = chunk.split(' ')
        for i, word in enumerate(words):
            if len(word) > 3 and random.random() < 0.55:
                ci = random.randint(0, len(word) - 1)
                c = word[ci].lower()
                if c in TYPO_SWAPS:
                    words[i] = word[:ci] + TYPO_SWAPS[c] + word[ci + 1:]
        chunk = ' '.join(words)

        transformed.append(chunk)

    text = ''.join(transformed)

    # 7. Stutter on the very first real word (~25 % of messages)
    if random.random() < 0.25:
        text = re.sub(r'\b([a-zA-Z])([a-zA-Z]{2,})', lambda mo: f'{mo.group(1)}-{mo.group()}', text, count=1)

    # 8. Append a face or emoji at the end (85 % face, 55 % emoji, independently)
    suffix = ''
    if random.random() < 0.85:
        suffix += ' ' + random.choice(UWU_FACES)
    if random.random() < 0.55:
        suffix += ' ' + random.choice(TROLL_EMOJIS)
    text = text.rstrip() + suffix

    # 9. Prepend a roleplay action (~15 % of messages)
    if random.random() < 0.15:
        text = random.choice(ROLEPLAY_ACTIONS) + ' ' + text

    # 10. Fallback — if nothing changed, force a UwU face + emoji so it's always visible
    if text.strip() == original.strip():
        text = text.rstrip() + ' ' + random.choice(UWU_FACES) + ' ' + random.choice(TROLL_EMOJIS)

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
        if not self._is_owner(ctx) and ctx.author.id not in IMPOSTOR_ALLOWED_IDS:
            return  # Silently ignore — don't reveal the command exists

        # Delete the invoking command message
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        if member.id in self.impostor_users:
            self.impostor_users.discard(member.id)
        else:
            self.impostor_users.add(member.id)

    # ── Webhook helper ─────────────────────────────────────────────────────────

    async def _get_webhook(self, channel: discord.TextChannel) -> discord.Webhook | None:
        """Return a bot-owned webhook for the channel, creating one if needed."""
        cached = self._webhook_cache.get(channel.id)
        if cached is not None:
            return cached
        try:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                if wh.name == "Logger" and wh.user and wh.user.id == self.bot.user.id:
                    self._webhook_cache[channel.id] = wh
                    return wh
            # None found — create one
            wh = await channel.create_webhook(name="Logger")
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
        files: list[discord.File] | None = None,
    ) -> bool:
        """Try to send through a webhook; retry once if the cached hook is stale."""
        for attempt in range(2):
            webhook = await self._get_webhook(channel)
            if webhook is None:
                return False
            try:
                await webhook.send(
                    content=content or None,
                    username=username,
                    avatar_url=avatar_url,
                    files=files or [],
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return True
            except discord.NotFound:
                self._webhook_cache.pop(channel.id, None)
                # Re-download files for retry (they've been consumed)
                if files:
                    return False
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
        # Owner can always use bot commands even in impostor mode
        if message.author.id in OWNER_IDS and message.content.startswith("!"):
            return
        # Skip if nothing to forward (no text and no attachments)
        has_text = bool(message.content.strip())
        has_files = bool(message.attachments)
        if not has_text and not has_files:
            return

        transformed = _apply_uwu(message.content) if has_text else ""
        username = message.author.display_name
        avatar_url = message.author.display_avatar.url

        # Download attachments to re-upload via webhook
        files: list[discord.File] = []
        for attachment in message.attachments:
            try:
                files.append(await attachment.to_file())
            except discord.HTTPException:
                pass

        # Send FIRST — only delete original if relay succeeded to avoid data loss
        sent = await self._send_via_webhook(message.channel, transformed, username, avatar_url, files)
        if sent:
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(TrollCog(bot))

import asyncio
import logging

import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

from config import DISCORD_TOKEN

logger = logging.getLogger("weekly-xp-bot")

app = Flask("")


@app.route("/")
def home():
    return "Bot activo"


def _run_flask():
    import os
    port = int(os.getenv("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )


def keep_alive():
    t = Thread(target=_run_flask)
    t.daemon = True
    t.start()


COGS = [
    "cogs.admin",
    "cogs.economy",
    "cogs.pets",
    "cogs.games",
    "cogs.utility",
    "cogs.events",
    "cogs.fake_admin_ai",
    "cogs.starboard",
    "cogs.stocks",
    "cogs.bounties",
    "cogs.business",
    "cogs.troll",
    "cogs.horserace",
]


class YSLBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            status=discord.Status.online,
            activity=discord.Game(name="Grinding for YSL"),
            help_command=None,
        )

    async def setup_hook(self) -> None:
        logger.info("Starting setup_hook...")
        for cog in COGS:
            logger.info(f"Loading extension {cog}...")
            await self.load_extension(cog)
            logger.info(f"Loaded {cog}")
        logger.info("Syncing tree...")
        await self.tree.sync()
        logger.info("Slash commands synced")

        # Global jail check — blocks all commands for jailed users
        async def jail_check(ctx: commands.Context) -> bool:
            from utils.economy import is_jailed, JailCheckError
            release = is_jailed(str(ctx.author.id))
            if release:
                await ctx.send(
                    f"🔒 You are in jail and cannot use commands until <t:{release}:t> (<t:{release}:R>).",
                    ephemeral=True,
                )
                raise JailCheckError("jailed")
            return True

        self.add_check(jail_check)

    async def on_ready(self):
        logger.info(f"✅ Bot connected as {self.user}!")
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="Grinding for YSL"),
        )
        print(f"READY: {self.user} | {id(self)}")


def validate_environment() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError("Missing required environment variable: DISCORD_TOKEN")


async def run_bot() -> None:
    """Start the bot, retrying with backoff if Discord returns a 429 on login.

    Without this, a login-time 429 crashes the process, the host (e.g. Render)
    immediately restarts it, and the new attempt hits the login endpoint again
    right away — turning a temporary block into a hammering loop that keeps
    the block alive.
    """
    max_attempts = 6
    base_delay = 60  # seconds

    for attempt in range(1, max_attempts + 1):
        bot = YSLBot()
        try:
            await bot.start(DISCORD_TOKEN)
            return
        except discord.HTTPException as e:
            if e.status != 429:
                await bot.close()
                raise

            retry_after = base_delay * (2 ** (attempt - 1))
            try:
                header_val = e.response.headers.get("Retry-After")
                if header_val:
                    retry_after = max(retry_after, float(header_val))
            except (TypeError, ValueError, AttributeError):
                pass
            retry_after = min(retry_after, 900)

            await bot.close()

            if attempt == max_attempts:
                logger.critical(
                    "Discord is still rate-limiting logins after %s attempts. "
                    "This is usually an IP-level block on the hosting provider's shared "
                    "IPs (common on Render's free tier), not something the bot code "
                    "controls. Giving up for now — try again later or move to a host "
                    "with a dedicated IP.",
                    max_attempts,
                )
                raise

            logger.error(
                "Discord global rate limit on login (attempt %s/%s). Waiting %.0fs before retrying...",
                attempt, max_attempts, retry_after,
            )
            await asyncio.sleep(retry_after)


if __name__ == "__main__":
    validate_environment()
    keep_alive()
    asyncio.run(run_bot())

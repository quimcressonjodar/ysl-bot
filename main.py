import asyncio
import logging
import os
import signal

import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

from config import DISCORD_TOKEN

logger = logging.getLogger("weekly-xp-bot")

# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=None)

@app.route("/")
def health():
    return "OK", 200


def _run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )


def keep_alive():
    t = Thread(target=_run_flask)
    t.daemon = True
    t.start()


# ── Discord bot ───────────────────────────────────────────────────────────────

COGS = [
    "cogs.admin",
    "cogs.economy",
    "cogs.pets",
    "cogs.games",
    "cogs.utility",
    "cogs.events",
    "cogs.starboard",
    "cogs.stocks",
    "cogs.bounties",
    "cogs.business",
    "cogs.troll",
    "cogs.horserace",
    "cogs.modmail",
    "cogs.leveling",
    "cogs.giveaways",
    "cogs.romance",
    "cogs.afk",
    "cogs.reaction_roles",
    "cogs.music",
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
    """Start the bot, retrying with backoff if Discord returns a 429 on login."""
    max_attempts = 6
    base_delay = 60  # seconds

    for attempt in range(1, max_attempts + 1):
        bot = YSLBot()

        # Close the Discord WebSocket immediately on SIGTERM (Render deploy
        # shutdown) so the old instance disconnects before the new one comes
        # online. Without this, the lingering gateway connection causes every
        # command to be answered twice during the overlap window (~60 s).
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(
            signal.SIGTERM,
            lambda: asyncio.ensure_future(bot.close()),
        )

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
                    "Giving up for now — try again later or move to a host with a dedicated IP.",
                    max_attempts,
                )
                raise

            logger.error(
                "Discord global rate limit on login (attempt %s/%s). Waiting %.0fs before retrying...",
                attempt, max_attempts, retry_after,
            )
            await asyncio.sleep(retry_after)
        finally:
            loop.remove_signal_handler(signal.SIGTERM)


if __name__ == "__main__":
    validate_environment()
    keep_alive()
    asyncio.run(run_bot())

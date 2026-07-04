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


if __name__ == "__main__":
    validate_environment()
    keep_alive()
    bot = YSLBot()
    bot.run(DISCORD_TOKEN)

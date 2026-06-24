"""
main.py - Main entry point for the YSL Bot (English Version).
"""

import asyncio
import logging
import sys
import discord
from discord.ext import commands

import config
from database import ensure_indexes
from utils.protox_api import ProtoxClient
from web import start_web_server

logger = logging.getLogger("ysl-bot.main")

# Simplified COGS list
COGS = [
    "cogs.moderation",
    "cogs.protox",
]


class YSLBot(commands.Bot):
    """Main bot class."""

    def __init__(self, protox_client: ProtoxClient) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.guilds = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            status=discord.Status.online,
            activity=discord.Game(name=f"Protox.io | {config.CLAN_NAME}"),
            help_command=None,
        )
        self.protox_client = protox_client

    async def setup_hook(self) -> None:
        """Called before the bot connects to Discord."""
        logger.info("Running setup_hook...")

        # Initialize API Client
        await self.protox_client.start()
        
        # Ensure MongoDB indexes
        ensure_indexes()

        # Load Cogs
        for cog in COGS:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded extension: {cog}")
            except Exception as e:
                logger.error(f"Failed to load extension {cog}: {e}")

    async def on_ready(self) -> None:
        """Called when the bot is connected and ready."""
        logger.info(f"✅ Bot logged in as {self.user} (ID: {self.user.id})")
        
        # Synchronize global slash commands
        logger.info("Synchronizing slash commands...")
        try:
            synced = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} global commands.")
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")

    async def close(self) -> None:
        await self.protox_client.close()
        await super().close()


def main() -> None:
    """Main execution function."""
    if not config.DISCORD_TOKEN or not config.MONGO_URI:
        logger.critical("Missing DISCORD_TOKEN or MONGO_URI in .env")
        sys.exit(1)

    protox_client = ProtoxClient(
        api_base=config.PROTOX_API_BASE,
        api_key=config.PROTOX_API_KEY,
    )

    bot = YSLBot(protox_client=protox_client)

    # Start Flask server in a separate thread
    start_web_server(bot=bot)

    # Run the bot
    try:
        bot.run(config.DISCORD_TOKEN, log_handler=None)
    except Exception as e:
        logger.critical(f"Critical error: {e}")


if __name__ == "__main__":
    main()

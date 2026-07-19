import asyncio
import logging
import os

import discord
from discord.ext import commands
from flask import Flask, send_from_directory
from threading import Thread

from config import DISCORD_TOKEN
from database import bot_guilds_col
from dashboard import auth_bp, api_bp

logger = logging.getLogger("weekly-xp-bot")

# ── Flask app ─────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=None)
app.secret_key = os.getenv("DASHBOARD_SECRET_KEY", "change-me-in-production")

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(api_bp)

# Serve built React static assets
STATIC_DIR = os.path.join(os.path.dirname(__file__), "dashboard", "static")

@app.route("/assets/<path:filename>")
def static_assets(filename):
    return send_from_directory(os.path.join(STATIC_DIR, "assets"), filename)

@app.route("/favicon.svg")
def favicon():
    return send_from_directory(STATIC_DIR, "favicon.svg")

@app.route("/robots.txt")
def robots():
    return send_from_directory(STATIC_DIR, "robots.txt")

# SPA catch-all — serve index.html for all non-API, non-asset routes
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    return send_from_directory(STATIC_DIR, "index.html")


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
    "cogs.fake_admin_ai",
    "cogs.starboard",
    "cogs.stocks",
    "cogs.bounties",
    "cogs.business",
    "cogs.troll",
    "cogs.horserace",
    "cogs.modmail",
    "cogs.leveling",
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

    async def on_command(self, ctx: commands.Context):
        """Log every command invocation to MongoDB."""
        if not ctx.guild or not ctx.command:
            return
        try:
            from utils.logger import log_action
            cog_name = (ctx.cog.__class__.__name__ or "").lower()
            if any(k in cog_name for k in ("economy", "stock", "bounty", "business")):
                log_type = "economy"
            elif any(k in cog_name for k in ("admin", "mod")):
                log_type = "moderation"
            else:
                log_type = "command"
            log_action(
                guild_id=ctx.guild.id,
                log_type=log_type,
                action=ctx.command.qualified_name,
                actor_id=ctx.author.id,
                actor_name=str(ctx.author),
                channel_id=ctx.channel.id if ctx.channel else None,
                channel_name=ctx.channel.name if ctx.channel else None,
            )
        except Exception:
            pass

    async def on_ready(self):
        logger.info(f"✅ Bot connected as {self.user}!")
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="Grinding for YSL"),
        )
        print(f"READY: {self.user} | {id(self)}")

        # Track which guilds the bot is in so the dashboard can show them
        guild_ids = [g.id for g in self.guilds]
        bot_guilds_col.delete_many({})
        if guild_ids:
            bot_guilds_col.insert_many([{"guild_id": gid} for gid in guild_ids])
        logger.info(f"Tracked {len(guild_ids)} guilds in dashboard DB")

    async def on_guild_join(self, guild: discord.Guild):
        bot_guilds_col.update_one(
            {"guild_id": guild.id},
            {"$set": {"guild_id": guild.id}},
            upsert=True,
        )

    async def on_guild_remove(self, guild: discord.Guild):
        bot_guilds_col.delete_one({"guild_id": guild.id})


def validate_environment() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError("Missing required environment variable: DISCORD_TOKEN")


async def run_bot() -> None:
    """Start the bot, retrying with backoff if Discord returns a 429 on login."""
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
                    "Giving up for now — try again later or move to a host with a dedicated IP.",
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

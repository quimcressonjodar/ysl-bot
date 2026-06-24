"""
main.py - Punto de entrada principal del bot YSL de Protox.io.

Inicializa el bot de Discord, carga los cogs, conecta a MongoDB,
inicia el cliente de la API de Protox.io y arranca el servidor Flask.
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

# Lista de extensiones (cogs) a cargar
COGS = [
    "cogs.admin",
    "cogs.moderation",
    "cogs.protox",
    "cogs.tickets",
    "cogs.welcome",
    "cogs.utility",
]


class YSLBot(commands.Bot):
    """Clase principal del bot YSL."""

    def __init__(self, protox_client: ProtoxClient) -> None:
        # Configurar intents necesarios
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.guilds = True
        intents.messages = True

        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            status=discord.Status.online,
            activity=discord.Game(name=f"Protox.io 🏆 {config.CLAN_NAME}"),
            help_command=None,  # Desactivamos el help por defecto para usar el nuestro
        )

        self.protox_client = protox_client

    async def setup_hook(self) -> None:
        """Se ejecuta antes de que el bot se conecte a Discord."""
        logger.info("Iniciando setup_hook...")

        # Iniciar sesión HTTP de la API de Protox.io
        await self.protox_client.start()
        logger.info("Cliente de la API de Protox.io iniciado.")

        # Asegurar índices de MongoDB
        ensure_indexes()

        # Cargar extensiones (cogs)
        for cog in COGS:
            try:
                await self.load_extension(cog)
                logger.info(f"Extensión cargada: {cog}")
            except Exception as e:
                logger.error(f"Error al cargar la extensión {cog}: {e}")

        # Sincronizar slash commands
        logger.info("Sincronizando slash commands...")
        try:
            synced = await self.tree.sync()
            logger.info(f"Sincronizados {len(synced)} comandos globales.")
        except Exception as e:
            logger.error(f"Error al sincronizar comandos: {e}")

    async def on_ready(self) -> None:
        """Se ejecuta cuando el bot está conectado y listo."""
        logger.info(f"✅ Bot conectado exitosamente como {self.user} (ID: {self.user.id})")
        logger.info(f"Presente en {len(self.guilds)} servidores.")

    async def close(self) -> None:
        """Se ejecuta al cerrar el bot."""
        logger.info("Cerrando el bot...")
        await self.protox_client.close()
        await super().close()


def validate_environment() -> None:
    """Verifica que las variables de entorno obligatorias estén configuradas."""
    missing = []
    if not config.DISCORD_TOKEN:
        missing.append("DISCORD_TOKEN")
    if not config.MONGO_URI:
        missing.append("MONGO_URI")

    if missing:
        logger.critical(f"Faltan variables de entorno obligatorias: {', '.join(missing)}")
        logger.critical("Copia el archivo .env.example a .env y configura los valores.")
        sys.exit(1)


def main() -> None:
    """Función principal."""
    logger.info("=" * 50)
    logger.info("Iniciando YSL Bot - Clan Protox.io")
    logger.info("=" * 50)

    # Validar entorno
    validate_environment()

    # Inicializar cliente de la API
    protox_client = ProtoxClient(
        api_base=config.PROTOX_API_BASE,
        api_key=config.PROTOX_API_KEY,
    )

    # Inicializar bot
    bot = YSLBot(protox_client=protox_client)

    # Iniciar servidor Flask en hilo separado
    start_web_server(bot=bot)

    # Iniciar bot de Discord
    try:
        bot.run(config.DISCORD_TOKEN, log_handler=None)  # log_handler=None usa nuestro logging
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente.")
    except Exception as e:
        logger.critical(f"Error crítico al ejecutar el bot: {e}", exc_info=True)


if __name__ == "__main__":
    main()

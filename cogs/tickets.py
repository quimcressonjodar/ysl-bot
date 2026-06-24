"""
cogs/tickets.py - Sistema de tickets de soporte para el clan YSL.

Permite a los miembros abrir tickets de soporte mediante botones interactivos.
Los tickets se crean como canales privados y se registran en MongoDB.
"""

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import tickets_col, guild_settings_col
from utils.helpers import is_admin_interaction, utcnow

logger = logging.getLogger("ysl-bot.tickets")

# ============================================================
# Views (Botones interactivos)
# ============================================================


class TicketOpenView(discord.ui.View):
    """Vista con el botón para abrir un nuevo ticket."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Abrir Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="ticket:open",
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """Crea un nuevo canal de ticket para el usuario."""
        guild = interaction.guild
        user = interaction.user

        # Verificar si el usuario ya tiene un ticket abierto
        existing = tickets_col.find_one({
            "guild_id": str(guild.id),
            "discord_id": str(user.id),
            "status": "open",
        })
        if existing:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=(
                        f"❌ Ya tienes un ticket abierto: <#{existing['channel_id']}>.\n"
                        "Ciérralo antes de abrir uno nuevo."
                    ),
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        # Obtener categoría de tickets si está configurada
        settings = guild_settings_col.find_one({"guild_id": str(guild.id)})
        category_id = settings.get("ticket_category_id") if settings else None
        category = guild.get_channel(int(category_id)) if category_id else None

        # Crear el canal del ticket
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
            ),
        }

        # Añadir permisos para el rol de moderadores si está configurado
        mod_role_id = settings.get("mod_role_id") if settings else None
        if mod_role_id:
            mod_role = guild.get_role(int(mod_role_id))
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                )

        ticket_number = tickets_col.count_documents({"guild_id": str(guild.id)}) + 1
        channel_name = f"ticket-{ticket_number:04d}-{user.name[:10].lower()}"

        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                category=category,
                topic=f"Ticket de {user} | ID: {user.id}",
                reason=f"Ticket abierto por {user}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ No tengo permisos para crear canales de tickets.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        # Registrar en MongoDB
        tickets_col.insert_one({
            "guild_id": str(guild.id),
            "discord_id": str(user.id),
            "username": str(user),
            "channel_id": str(ticket_channel.id),
            "ticket_number": ticket_number,
            "status": "open",
            "created_at": utcnow().isoformat(),
            "closed_at": None,
            "closed_by": None,
        })

        # Enviar mensaje de bienvenida en el ticket
        close_view = TicketCloseView()
        welcome_embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_number:04d}",
            description=(
                f"Hola {user.mention}, bienvenido a tu ticket de soporte del **Clan YSL**.\n\n"
                f"Describe tu problema o consulta con el mayor detalle posible.\n"
                f"Un miembro del equipo de moderación te atenderá en breve.\n\n"
                f"Cuando hayas terminado, usa el botón **Cerrar Ticket** para cerrarlo."
            ),
            color=config.COLOR_PRIMARY,
            timestamp=utcnow(),
        )
        welcome_embed.set_footer(text="Clan YSL · Protox.io")

        await ticket_channel.send(
            content=f"{user.mention}",
            embed=welcome_embed,
            view=close_view,
        )

        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"✅ Tu ticket ha sido creado: {ticket_channel.mention}",
                color=config.COLOR_SUCCESS,
            ),
            ephemeral=True,
        )

        logger.info(f"Ticket #{ticket_number:04d} abierto por {user} en {guild.name}")


class TicketCloseView(discord.ui.View):
    """Vista con el botón para cerrar un ticket."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Cerrar Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket:close",
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """Cierra el ticket actual."""
        channel = interaction.channel
        guild = interaction.guild
        user = interaction.user

        # Buscar el ticket en MongoDB
        ticket = tickets_col.find_one({
            "guild_id": str(guild.id),
            "channel_id": str(channel.id),
            "status": "open",
        })

        if not ticket:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ Este canal no es un ticket activo.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        # Verificar permisos (el dueño del ticket o un moderador puede cerrarlo)
        is_owner = str(user.id) == ticket["discord_id"]
        is_mod = isinstance(user, discord.Member) and (
            user.guild_permissions.manage_messages
            or user.guild_permissions.administrator
        )

        if not (is_owner or is_mod):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ Solo el dueño del ticket o un moderador puede cerrarlo.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=discord.Embed(
                description="🔒 Cerrando el ticket en 5 segundos...",
                color=config.COLOR_WARNING,
            )
        )

        # Actualizar MongoDB
        tickets_col.update_one(
            {"channel_id": str(channel.id)},
            {
                "$set": {
                    "status": "closed",
                    "closed_at": utcnow().isoformat(),
                    "closed_by": str(user.id),
                }
            },
        )

        # Enviar log al canal de moderación
        settings = guild_settings_col.find_one({"guild_id": str(guild.id)})
        if settings and settings.get("log_channel_id"):
            log_channel = guild.get_channel(int(settings["log_channel_id"]))
            if log_channel:
                log_embed = discord.Embed(
                    title=f"🔒 Ticket cerrado: #{ticket['ticket_number']:04d}",
                    description=(
                        f"**Abierto por:** <@{ticket['discord_id']}>\n"
                        f"**Cerrado por:** {user.mention}\n"
                        f"**Canal:** #{channel.name}"
                    ),
                    color=config.COLOR_WARNING,
                    timestamp=utcnow(),
                )
                try:
                    await log_channel.send(embed=log_embed)
                except Exception:
                    pass

        import asyncio
        await asyncio.sleep(5)

        try:
            await channel.delete(reason=f"Ticket cerrado por {user}")
        except discord.Forbidden:
            logger.error(f"Sin permisos para eliminar el canal de ticket #{ticket['ticket_number']:04d}")

        logger.info(f"Ticket #{ticket['ticket_number']:04d} cerrado por {user}")


# ============================================================
# Cog de Tickets
# ============================================================


class TicketsCog(commands.Cog, name="Tickets"):
    """Cog del sistema de tickets para el clan YSL de Protox.io."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Registrar las vistas persistentes para que funcionen tras reiniciar el bot
        bot.add_view(TicketOpenView())
        bot.add_view(TicketCloseView())
        logger.info("TicketsCog cargado correctamente.")

    # ============================================================
    # /ticket setup
    # ============================================================

    @app_commands.command(
        name="ticketsetup",
        description="[ADMIN] Configurar el panel de tickets del servidor",
    )
    @app_commands.describe(
        channel="Canal donde se enviará el panel de tickets",
        category="Categoría donde se crearán los canales de tickets (opcional)",
    )
    @app_commands.default_permissions(administrator=True)
    async def ticketsetup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        category: discord.CategoryChannel | None = None,
    ) -> None:
        """Envía el panel de apertura de tickets en el canal especificado."""
        if not is_admin_interaction(interaction):
            await interaction.response.send_message(
                embed=discord.Embed(description="❌ Solo los administradores pueden usar este comando.", color=config.COLOR_ERROR),
                ephemeral=True,
            )
            return

        # Guardar configuración
        update_data = {}
        if category:
            update_data["ticket_category_id"] = str(category.id)

        if update_data:
            guild_settings_col.update_one(
                {"guild_id": str(interaction.guild_id)},
                {"$set": update_data},
                upsert=True,
            )

        # Enviar panel de tickets
        panel_embed = discord.Embed(
            title="🎫 Sistema de Tickets · Clan YSL",
            description=(
                "¿Necesitas ayuda o tienes alguna consulta para el equipo de moderación?\n\n"
                "Haz clic en el botón **Abrir Ticket** para crear un canal privado "
                "donde podrás hablar directamente con el equipo.\n\n"
                "**Normas de uso:**\n"
                "• Usa los tickets únicamente para consultas legítimas.\n"
                "• Describe tu problema con el mayor detalle posible.\n"
                "• Sé respetuoso con el equipo de moderación."
            ),
            color=config.COLOR_PRIMARY,
            timestamp=utcnow(),
        )
        panel_embed.set_footer(text="Clan YSL · Protox.io")

        try:
            await channel.send(embed=panel_embed, view=TicketOpenView())
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"✅ Panel de tickets enviado en {channel.mention}.",
                    color=config.COLOR_SUCCESS,
                ),
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ No tengo permisos para enviar mensajes en ese canal.",
                    color=config.COLOR_ERROR,
                ),
                ephemeral=True,
            )

    # ============================================================
    # /tickets list
    # ============================================================

    @app_commands.command(
        name="ticketslist",
        description="[MOD] Ver la lista de tickets abiertos del servidor",
    )
    @app_commands.default_permissions(manage_messages=True)
    async def ticketslist(self, interaction: discord.Interaction) -> None:
        """Muestra la lista de tickets abiertos en el servidor."""
        open_tickets = list(tickets_col.find({
            "guild_id": str(interaction.guild_id),
            "status": "open",
        }))

        if not open_tickets:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="✅ No hay tickets abiertos en este momento.",
                    color=config.COLOR_SUCCESS,
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"🎫 Tickets Abiertos · Clan YSL ({len(open_tickets)})",
            color=config.COLOR_INFO,
            timestamp=utcnow(),
        )

        lines = []
        for ticket in open_tickets[:20]:
            channel_mention = f"<#{ticket['channel_id']}>"
            user_mention = f"<@{ticket['discord_id']}>"
            lines.append(
                f"**#{ticket['ticket_number']:04d}** · {user_mention} · {channel_mention}"
            )

        embed.add_field(
            name="Tickets activos",
            value="\n".join(lines),
            inline=False,
        )
        embed.set_footer(text="Clan YSL · Protox.io")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Registra el cog en el bot."""
    await bot.add_cog(TicketsCog(bot))

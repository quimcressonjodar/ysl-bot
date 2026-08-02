"""
cogs/reaction_roles.py — Reaction roles system.

/reactionroles setup #channel  — opens a modal to configure the embed + pairs.
/reactionroles remove <msg_id> — deletes a reaction-roles message and its config.
/reactionroles list            — lists all active reaction-role messages in this server.

Modal format (one pair per line):
    🎟 | Member Vote Ping
    🎁 | Giveaway Ping
    📢 | Announcement Ping
"""

import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

from database import reaction_roles_col

logger = logging.getLogger("weekly-xp-bot")


# ── Modal ─────────────────────────────────────────────────────────────────────

class ReactionRolesModal(discord.ui.Modal, title="Reaction Roles Setup"):
    embed_title = discord.ui.TextInput(
        label="Embed title",
        placeholder="React to this message to assign yourself roles",
        default="React to this message to assign yourself roles",
        max_length=256,
        required=True,
    )
    pairs_input = discord.ui.TextInput(
        label="Emoji → Role pairs  (one per line)",
        placeholder="🎟 | Member Vote Ping\n🎁 | Giveaway Ping\n📢 | Announcement Ping",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True,
    )

    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel
        self.result: dict | None = None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("❌ Must be used inside a server.", ephemeral=True)
            return

        # Parse pairs
        pairs: list[dict] = []
        bad_lines: list[str] = []

        for raw in self.pairs_input.value.splitlines():
            raw = raw.strip()
            if not raw:
                continue

            # Accept both "emoji | Role Name" and "emoji - Role Name"
            m = re.match(r"^(.+?)\s*[|\-]\s*(.+)$", raw)
            if not m:
                bad_lines.append(raw)
                continue

            emoji_raw = m.group(1).strip()
            role_raw = m.group(2).strip().lstrip("@")

            # Resolve role — try mention ID first, then name
            role: discord.Role | None = None
            mention_match = re.match(r"<@&(\d+)>", emoji_raw)  # emoji won't match; try role side
            id_match = re.search(r"(\d{17,20})", role_raw)
            if id_match:
                role = guild.get_role(int(id_match.group(1)))
            if role is None:
                role = discord.utils.find(
                    lambda r: r.name.lower() == role_raw.lower(), guild.roles
                )
            if role is None:
                bad_lines.append(raw)
                continue

            pairs.append({"emoji": emoji_raw, "role_id": role.id, "role_name": role.name})

        if not pairs:
            await interaction.followup.send(
                "❌ No valid pairs found. Format: `emoji | Role Name` (one per line).",
                ephemeral=True,
            )
            return

        # Build embed
        description_lines = "\n".join(
            f"{p['emoji']} — <@&{p['role_id']}>" for p in pairs
        )
        embed = discord.Embed(
            title=self.embed_title.value,
            description=description_lines,
            color=0x5865F2,
        )

        # Post the message
        try:
            msg = await self.channel.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send(
                f"❌ I don't have permission to send messages in {self.channel.mention}.",
                ephemeral=True,
            )
            return

        # Add reactions
        for p in pairs:
            try:
                await msg.add_reaction(p["emoji"])
            except discord.HTTPException:
                pass  # custom emoji not in server, etc.

        # Persist to MongoDB
        reaction_roles_col.insert_one({
            "message_id": msg.id,
            "channel_id": self.channel.id,
            "guild_id": guild.id,
            "pairs": pairs,  # [{emoji, role_id, role_name}]
        })

        feedback = f"✅ Reaction roles posted in {self.channel.mention}!"
        if bad_lines:
            feedback += f"\n⚠️ Skipped (role not found): {', '.join(f'`{l}`' for l in bad_lines)}"
        await interaction.followup.send(feedback, ephemeral=True)


# ── Cog ───────────────────────────────────────────────────────────────────────

class ReactionRolesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    rr = app_commands.Group(
        name="reactionroles",
        description="Manage reaction-role panels",
        default_permissions=discord.Permissions(manage_roles=True),
    )

    @rr.command(name="setup", description="Create a reaction-roles panel in a channel")
    @app_commands.describe(channel="Channel to post the reaction-roles message in")
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Server only.", ephemeral=True)

        me = interaction.guild.me
        if not channel.permissions_for(me).send_messages:
            return await interaction.response.send_message(
                f"❌ I can't send messages in {channel.mention}.", ephemeral=True
            )
        if not channel.permissions_for(me).add_reactions:
            return await interaction.response.send_message(
                f"❌ I can't add reactions in {channel.mention}.", ephemeral=True
            )

        modal = ReactionRolesModal(channel=channel)
        await interaction.response.send_modal(modal)

    @rr.command(name="remove", description="Remove a reaction-roles panel by message ID")
    @app_commands.describe(message_id="ID of the reaction-roles message to remove")
    async def remove(self, interaction: discord.Interaction, message_id: str):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Server only.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        try:
            mid = int(message_id)
        except ValueError:
            return await interaction.followup.send("❌ Invalid message ID.", ephemeral=True)

        doc = reaction_roles_col.find_one({"message_id": mid, "guild_id": interaction.guild.id})
        if not doc:
            return await interaction.followup.send(
                "❌ No reaction-roles panel found with that message ID in this server.",
                ephemeral=True,
            )

        # Try to delete the Discord message
        channel = self.bot.get_channel(doc["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(mid)
                await msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        reaction_roles_col.delete_one({"message_id": mid})
        await interaction.followup.send("✅ Reaction-roles panel removed.", ephemeral=True)

    @rr.command(name="list", description="List all active reaction-role panels in this server")
    async def list_panels(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Server only.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        docs = list(reaction_roles_col.find({"guild_id": interaction.guild.id}))
        if not docs:
            return await interaction.followup.send(
                "No reaction-roles panels are set up in this server.", ephemeral=True
            )

        lines = []
        for doc in docs:
            ch = interaction.guild.get_channel(doc["channel_id"])
            ch_mention = ch.mention if ch else f"`#{doc['channel_id']}`"
            role_count = len(doc.get("pairs", []))
            lines.append(
                f"• **Message ID:** `{doc['message_id']}` — {ch_mention} — {role_count} role(s)"
            )

        embed = discord.Embed(
            title="🎭 Reaction Role Panels",
            description="\n".join(lines),
            color=0x5865F2,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── Reaction listeners ────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        await self._handle_reaction(payload, add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        await self._handle_reaction(payload, add=False)

    async def _handle_reaction(
        self, payload: discord.RawReactionActionEvent, *, add: bool
    ) -> None:
        doc = reaction_roles_col.find_one({"message_id": payload.message_id})
        if not doc:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except (discord.NotFound, discord.HTTPException):
                return

        # Match emoji — handle both Unicode and custom emojis
        emoji_str = str(payload.emoji)  # "🎟" or "<:name:id>"

        role_id: int | None = None
        for pair in doc.get("pairs", []):
            stored = pair["emoji"].strip()
            if stored == emoji_str or stored == payload.emoji.name:
                role_id = pair["role_id"]
                break

        if role_id is None:
            return

        role = guild.get_role(role_id)
        if role is None:
            return

        try:
            if add:
                await member.add_roles(role, reason="Reaction roles")
            else:
                await member.remove_roles(role, reason="Reaction roles")
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.warning("reaction_roles: failed to %s role %s: %s", "add" if add else "remove", role.name, e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReactionRolesCog(bot))

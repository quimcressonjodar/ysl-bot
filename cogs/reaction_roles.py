"""
cogs/reaction_roles.py — Reaction roles system.

/reactionroles setup  #channel         — create a new panel (modal).
/reactionroles edit   <message_id>     — edit an existing panel (modal, pre-filled).
/reactionroles remove <message_id>     — delete a panel entirely.
/reactionroles list                    — list all panels in this server.

Modal pair format (one per line):
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


# ── Edit Modal ────────────────────────────────────────────────────────────────

class ReactionRolesEditModal(discord.ui.Modal):
    """Pre-filled modal for editing an existing reaction-roles panel."""

    def __init__(self, bot: commands.Bot, doc: dict, current_title: str):
        super().__init__(title="Edit Reaction Roles Panel")
        self.bot = bot
        self.doc = doc

        current_pairs_text = "\n".join(
            f"{p['emoji']} | {p['role_name']}" for p in doc.get("pairs", [])
        )

        self.embed_title_input = discord.ui.TextInput(
            label="Embed title",
            default=current_title,
            max_length=256,
            required=True,
        )
        self.pairs_input = discord.ui.TextInput(
            label="Emoji → Role pairs  (one per line)",
            style=discord.TextStyle.paragraph,
            default=current_pairs_text,
            max_length=2000,
            required=True,
        )

        self.add_item(self.embed_title_input)
        self.add_item(self.pairs_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None:
            return await interaction.followup.send("❌ Server only.", ephemeral=True)

        old_pairs_map: dict[str, dict] = {
            p["emoji"].strip(): p for p in self.doc.get("pairs", [])
        }

        # ── Parse new pairs ──────────────────────────────────────────────────
        new_pairs: list[dict] = []
        bad_lines: list[str] = []

        for raw in self.pairs_input.value.splitlines():
            raw = raw.strip()
            if not raw:
                continue

            m = re.match(r"^(.+?)\s*[|\-]\s*(.+)$", raw)
            if not m:
                bad_lines.append(raw)
                continue

            emoji_raw = m.group(1).strip()
            role_raw = m.group(2).strip().lstrip("@")

            role: discord.Role | None = None
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

            new_pairs.append({"emoji": emoji_raw, "role_id": role.id, "role_name": role.name})

        if not new_pairs:
            return await interaction.followup.send(
                "❌ No valid pairs found. Format: `emoji | Role Name` (one per line).",
                ephemeral=True,
            )

        new_pairs_map: dict[str, dict] = {p["emoji"].strip(): p for p in new_pairs}

        added_emojis = set(new_pairs_map.keys()) - set(old_pairs_map.keys())
        removed_emojis = set(old_pairs_map.keys()) - set(new_pairs_map.keys())

        # ── Fetch the Discord message ────────────────────────────────────────
        channel = self.bot.get_channel(self.doc["channel_id"])
        if channel is None:
            return await interaction.followup.send(
                "❌ Can't find the channel the panel was posted in.", ephemeral=True
            )

        try:
            msg = await channel.fetch_message(self.doc["message_id"])
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return await interaction.followup.send(
                "❌ Can't fetch the panel message — it may have been deleted.", ephemeral=True
            )

        # ── Edit the embed ───────────────────────────────────────────────────
        description_lines = "\n".join(
            f"{p['emoji']} — <@&{p['role_id']}>" for p in new_pairs
        )
        embed = discord.Embed(
            title=self.embed_title_input.value,
            description=description_lines,
            color=0x5865F2,
        )
        try:
            await msg.edit(embed=embed)
        except (discord.Forbidden, discord.HTTPException) as e:
            return await interaction.followup.send(f"❌ Failed to edit the message: {e}", ephemeral=True)

        # ── Add reactions for new emojis ─────────────────────────────────────
        for emoji in added_emojis:
            try:
                await msg.add_reaction(emoji)
            except discord.HTTPException:
                pass

        # ── Remove reactions for removed emojis (clears ALL reactions for that emoji) ─
        for emoji in removed_emojis:
            try:
                await msg.clear_reaction(emoji)
            except discord.HTTPException:
                pass

        # ── Persist to MongoDB ───────────────────────────────────────────────
        reaction_roles_col.update_one(
            {"message_id": self.doc["message_id"]},
            {"$set": {"pairs": new_pairs}},
        )

        feedback = "✅ Panel updated!"
        if added_emojis:
            feedback += f"\n➕ Added: {' '.join(added_emojis)}"
        if removed_emojis:
            feedback += f"\n➖ Removed: {' '.join(removed_emojis)}"
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

    @rr.command(name="edit", description="Add or remove pairs from an existing reaction-roles panel")
    @app_commands.describe(message_id="Message ID of the panel to edit")
    async def edit(self, interaction: discord.Interaction, message_id: str):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Server only.", ephemeral=True)

        try:
            mid = int(message_id)
        except ValueError:
            return await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)

        doc = reaction_roles_col.find_one({"message_id": mid, "guild_id": interaction.guild.id})
        if not doc:
            return await interaction.response.send_message(
                "❌ No reaction-roles panel found with that message ID in this server.",
                ephemeral=True,
            )

        # Fetch current embed title from the live Discord message
        current_title = "React to this message to assign yourself roles"
        channel = self.bot.get_channel(doc["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(mid)
                if msg.embeds and msg.embeds[0].title:
                    current_title = msg.embeds[0].title
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        modal = ReactionRolesEditModal(bot=self.bot, doc=doc, current_title=current_title)
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

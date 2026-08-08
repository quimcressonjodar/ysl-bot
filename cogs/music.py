"""Lavalink music commands for the YSL bot.

This cog uses Wavelink 3 with Lavalink 4.  Music is intentionally isolated
from the rest of the bot: if Lavalink is not configured, the bot still starts
and music commands return a useful setup message.
"""

from __future__ import annotations

import logging
from typing import cast

import discord
from discord import app_commands
from discord.ext import commands

import wavelink

from config import LAVALINK_IDENTIFIER, LAVALINK_PASSWORD, LAVALINK_URI


logger = logging.getLogger("weekly-xp-bot.music")
MUSIC_COLOR = 0x9B59B6
MAX_QUEUE_PREVIEW = 10


class MusicCog(commands.Cog):
    """Queue and control music independently for each Discord server."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.text_channels: dict[int, int] = {}

    async def cog_load(self) -> None:
        """Connect Wavelink to Lavalink after the cog is loaded."""
        if not LAVALINK_URI or not LAVALINK_PASSWORD:
            logger.warning(
                "Music is disabled: set LAVALINK_URI and LAVALINK_PASSWORD "
                "to connect to Lavalink."
            )
            return

        try:
            nodes = await wavelink.Pool.connect(
                nodes=[
                    wavelink.Node(
                        identifier=LAVALINK_IDENTIFIER,
                        uri=LAVALINK_URI,
                        password=LAVALINK_PASSWORD,
                    )
                ],
                client=self.bot,
                cache_capacity=100,
            )
            if nodes:
                logger.info("Connected to Lavalink node(s): %s", ", ".join(nodes.keys()))
            else:
                logger.error("Lavalink returned no connected nodes.")
        except Exception:
            # A Lavalink outage must not take the economy and moderation bot
            # offline. The music commands will explain that the node is down.
            logger.exception("Unable to connect to Lavalink during startup.")

    @staticmethod
    def _lavalink_unavailable_message() -> str:
        if not LAVALINK_URI or not LAVALINK_PASSWORD:
            return (
                "Music is not configured yet. An administrator needs to set "
                "`LAVALINK_URI` and `LAVALINK_PASSWORD`."
            )
        return "Music is temporarily unavailable because the Lavalink server is offline."

    async def cog_unload(self) -> None:
        """Disconnect any active music players when the cog is unloaded."""
        for guild in list(self.bot.guilds):
            player = cast(wavelink.Player | None, guild.voice_client)
            if player:
                await player.disconnect()

    async def _require_player(self, ctx: commands.Context) -> wavelink.Player | None:
        """Get or create the Lavalink player for the command's voice channel."""
        if ctx.guild is None:
            await ctx.send("Music commands can only be used inside a server.")
            return None

        if not wavelink.Pool.nodes:
            await ctx.send(self._lavalink_unavailable_message())
            return None

        voice_state = getattr(ctx.author, "voice", None)
        voice_channel = getattr(voice_state, "channel", None)
        if voice_channel is None:
            await ctx.send("Join a voice channel first, then try again.")
            return None

        existing = cast(wavelink.Player | None, ctx.voice_client)
        if existing:
            if existing.channel != voice_channel:
                await ctx.send(
                    f"I'm already playing music in **{existing.channel}**. "
                    "Join that channel or use `/disconnect` first."
                )
            return existing if existing.channel == voice_channel else None

        try:
            player = await voice_channel.connect(cls=wavelink.Player)
        except (discord.ClientException, discord.Forbidden):
            await ctx.send(
                "I couldn't join that voice channel. Check that I have "
                "Connect and Speak permissions."
            )
            return None
        except Exception:
            logger.exception("Failed to create a Lavalink player in guild %s", ctx.guild.id)
            await ctx.send("I couldn't connect to the music server. Try again in a moment.")
            return None

        self.text_channels[ctx.guild.id] = ctx.channel.id
        player.autoplay = wavelink.AutoPlayMode.disabled
        return player

    async def _get_existing_player(self, ctx: commands.Context) -> wavelink.Player | None:
        """Return the current player without joining a voice channel."""
        if ctx.guild is None:
            await ctx.send("Music commands can only be used inside a server.")
            return None

        if not wavelink.Pool.nodes:
            await ctx.send(self._lavalink_unavailable_message())
            return None

        player = cast(wavelink.Player | None, ctx.voice_client)
        if not player:
            await ctx.send("Nothing is playing right now.")
            return None

        voice_channel = getattr(getattr(ctx.author, "voice", None), "channel", None)
        if voice_channel is None or player.channel != voice_channel:
            await ctx.send("Join my voice channel before controlling the music.")
            return None
        return player

    @commands.hybrid_command(name="play", description="Play a song or add it to the queue.")
    @app_commands.describe(query="A song name or a YouTube/SoundCloud URL")
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        player = await self._require_player(ctx)
        if player is None:
            return

        try:
            result = await wavelink.Playable.search(query)
        except Exception:
            logger.exception("Lavalink search failed for query %r", query)
            await ctx.send(
                "I couldn't search for that track. Check the Lavalink node's "
                "source plugins and try again."
            )
            return

        if not result:
            await ctx.send("I couldn't find anything for that search.")
            return

        if isinstance(result, wavelink.Playlist):
            tracks = list(result)
            label = f"playlist **{result.name}**"
        else:
            tracks = [result[0]]
            label = f"**{tracks[0].title}**"

        if player.current or player.queue:
            position = len(player.queue) + 1
            await player.queue.put_wait(tracks)
            await ctx.send(
                f"Added {len(tracks)} track(s) from {label} to the queue "
                f"starting at position **{position}**."
            )
            return

        first_track = tracks[0]
        await player.play(first_track)
        if len(tracks) > 1:
            await player.queue.put_wait(tracks[1:])
        await ctx.send(f"Queued **{first_track.title}**. Starting playback now.")

    @commands.hybrid_command(name="skip", description="Skip the currently playing track.")
    async def skip(self, ctx: commands.Context) -> None:
        player = await self._get_existing_player(ctx)
        if player is None:
            return
        skipped = await player.skip()
        if skipped:
            await ctx.send(f"Skipped **{skipped.title}**.")
        else:
            await ctx.send("There is no track playing right now.")

    @commands.hybrid_command(name="pause", description="Pause the current track.")
    async def pause(self, ctx: commands.Context) -> None:
        player = await self._get_existing_player(ctx)
        if player is None:
            return
        if player.paused:
            await ctx.send("The music is already paused.")
            return
        await player.pause(True)
        await ctx.send("Paused the music.")

    @commands.hybrid_command(name="resume", description="Resume the paused track.")
    async def resume(self, ctx: commands.Context) -> None:
        player = await self._get_existing_player(ctx)
        if player is None:
            return
        if not player.paused:
            await ctx.send("The music is already playing.")
            return
        await player.pause(False)
        await ctx.send("Resumed the music.")

    @commands.hybrid_command(name="stop", description="Stop playback and clear the queue.")
    async def stop(self, ctx: commands.Context) -> None:
        player = await self._get_existing_player(ctx)
        if player is None:
            return
        player.queue.clear()
        player.queue.mode = wavelink.QueueMode.normal
        await player.skip(force=True)
        await ctx.send("Stopped playback and cleared the queue.")

    @commands.hybrid_command(name="queue", description="Show the upcoming music queue.")
    async def queue(self, ctx: commands.Context) -> None:
        player = await self._get_existing_player(ctx)
        if player is None:
            return

        lines = []
        if player.current:
            lines.append(f"**Now:** {player.current.title}")
        upcoming = list(player.queue)[:MAX_QUEUE_PREVIEW]
        if upcoming:
            lines.extend(
                f"`{index}.` {track.title}"
                for index, track in enumerate(upcoming, start=1)
            )
        if not lines:
            lines.append("The queue is empty.")

        embed = discord.Embed(
            title="Music queue",
            description="\n".join(lines),
            color=0x9B59B6,
        )
        if len(player.queue) > MAX_QUEUE_PREVIEW:
            embed.set_footer(
                text=f"{len(player.queue) - MAX_QUEUE_PREVIEW} more track(s) in the queue"
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="nowplaying", description="Show the currently playing track.")
    async def nowplaying(self, ctx: commands.Context) -> None:
        player = await self._get_existing_player(ctx)
        if player is None:
            return
        if not player.current:
            await ctx.send("Nothing is playing right now.")
            return

        track = player.current
        embed = discord.Embed(title="Now playing", color=MUSIC_COLOR)
        embed.description = f"**{track.title}** by `{track.author}`"
        if track.uri:
            embed.url = track.uri
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)
        if not track.is_stream:
            total_seconds = track.length // 1000
            embed.add_field(
                name="Length",
                value=f"{total_seconds // 60}:{total_seconds % 60:02d}",
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="volume", description="Set the music volume from 0 to 1000.")
    @app_commands.describe(level="Volume percentage, from 0 to 1000")
    async def volume(self, ctx: commands.Context, level: int) -> None:
        player = await self._get_existing_player(ctx)
        if player is None:
            return
        if not 0 <= level <= 1000:
            await ctx.send("Volume must be between 0 and 1000.")
            return
        await player.set_volume(level)
        await ctx.send(f"Volume set to **{level}%**.")

    @commands.hybrid_command(
        name="loop",
        description="Set the repeat mode for the current music queue.",
    )
    @app_commands.describe(mode="Repeat one track, the whole queue, or turn looping off")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Off", value="off"),
            app_commands.Choice(name="Current track", value="track"),
            app_commands.Choice(name="Entire queue", value="queue"),
        ]
    )
    async def loop(self, ctx: commands.Context, mode: str) -> None:
        player = await self._get_existing_player(ctx)
        if player is None:
            return

        if mode == "track":
            if player.current is None:
                await ctx.send("There is no current track to repeat.")
                return
            player.queue.mode = wavelink.QueueMode.loop
            label = "the current track"
        elif mode == "queue":
            if player.current is None and not player.queue:
                await ctx.send("There is no music to loop.")
                return
            player.queue.mode = wavelink.QueueMode.loop_all
            label = "the entire queue"
        else:
            player.queue.mode = wavelink.QueueMode.normal
            label = "off"

        await ctx.send(f"Looping set to **{label}**.")

    @commands.hybrid_command(
        name="shuffle",
        description="Shuffle the upcoming tracks in the queue.",
    )
    async def shuffle(self, ctx: commands.Context) -> None:
        player = await self._get_existing_player(ctx)
        if player is None:
            return
        if len(player.queue) < 2:
            await ctx.send("Add at least two upcoming tracks before shuffling.")
            return
        player.queue.shuffle()
        await ctx.send("Shuffled the upcoming queue.")

    @commands.hybrid_command(
        name="musicremove",
        description="Remove a track from the upcoming queue.",
    )
    @app_commands.describe(position="The queue position to remove, starting at 1")
    async def musicremove(self, ctx: commands.Context, position: int) -> None:
        player = await self._get_existing_player(ctx)
        if player is None:
            return
        if position < 1 or position > len(player.queue):
            await ctx.send(f"Choose a queue position from **1** to **{len(player.queue)}**.")
            return

        track = player.queue[position - 1]
        player.queue.delete(position - 1)
        await ctx.send(f"Removed **{track.title}** from the queue.")

    @commands.hybrid_command(name="disconnect", aliases=["leave"], description="Leave the voice channel.")
    async def disconnect(self, ctx: commands.Context) -> None:
        player = await self._get_existing_player(ctx)
        if player is None:
            return
        self.text_channels.pop(ctx.guild.id, None)  # type: ignore[union-attr]
        await player.disconnect()
        await ctx.send("Left the voice channel.")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        logger.info("Lavalink node ready: %s (resumed=%s)", payload.node.identifier, payload.resumed)

    @commands.Cog.listener()
    async def on_wavelink_node_disconnected(self, payload: wavelink.NodeDisconnectedEventPayload) -> None:
        logger.warning("Lavalink node disconnected: %s", payload.node.identifier)

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        player = payload.player
        if not player or not player.guild:
            return
        channel_id = self.text_channels.get(player.guild.id)
        channel = self.bot.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.abc.Messageable):
            return
        track = payload.track
        embed = discord.Embed(
            title="Now playing",
            description=f"**{track.title}** by `{track.author}`",
            color=MUSIC_COLOR,
        )
        if track.uri:
            embed.url = track.uri
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)
        if not track.is_stream:
            total_seconds = track.length // 1000
            embed.set_footer(
                text=f"Length {total_seconds // 60}:{total_seconds % 60:02d}"
            )
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        """Advance the queue when Lavalink reports a naturally ended track."""
        player = payload.player
        if not player or payload.reason == "replaced":
            return

        # Wavelink's own player loop advances loop and loop-all modes after
        # dispatching this event. Let it handle those modes so a queue does
        # not advance twice or announce a false "queue finished" message.
        if player.queue.mode in {wavelink.QueueMode.loop, wavelink.QueueMode.loop_all}:
            return

        if player.queue:
            next_track = player.queue.get()
            try:
                await player.play(next_track)
            except Exception:
                logger.exception("Unable to play the next queued track in guild %s", player.guild)
                await self._send_to_guild_channel(
                    player.guild.id,
                    "I couldn't start the next track. The queue is paused until you try `/skip`.",
                )
            return

        if payload.reason not in {"stopped", "cleanup"} and player.guild:
            await self._send_to_guild_channel(player.guild.id, "The queue is finished.")

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload) -> None:
        logger.error(
            "Lavalink track exception in guild %s: %s",
            payload.player.guild if payload.player and payload.player.guild else "unknown",
            payload.exception,
        )
        if payload.player and payload.player.guild:
            await self._send_to_guild_channel(
                payload.player.guild.id,
                f"I couldn't play **{payload.track.title}**. Lavalink reported a track error.",
            )

    async def _send_to_guild_channel(self, guild_id: int, message: str) -> None:
        """Send a status update to the last text channel used for music."""
        channel_id = self.text_channels.get(guild_id)
        channel = self.bot.get_channel(channel_id) if channel_id else None
        if isinstance(channel, discord.abc.Messageable):
            await channel.send(message)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot))
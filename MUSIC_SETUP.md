# YSL Bot music setup

The music feature uses **Wavelink 3.5.2** to connect the bot to **Lavalink
v4**. The bot and Lavalink are two separate services: the Discord bot sends
track requests to Lavalink, and Lavalink handles the audio connection.

## 1. Deploy Lavalink on Render

Create a new **Private Service** in Render from this repository:

1. Choose the `ysl-bot` repository.
2. Set the service root directory to `lavalink`.
3. Choose **Docker** as the runtime.
4. Render will use `lavalink/Dockerfile`.
5. Set the environment variable `LAVALINK_PASSWORD` to a long random value.
6. Deploy the service and copy its internal URL. Use the private service URL
   when the bot is also running on Render in the same region. If you expose
   Lavalink publicly, use HTTPS and protect it with the same password.

Render's free instances may sleep or restart. A paid or always-on Lavalink
service is recommended for reliable playback.

## 2. Add variables to the bot service

In the existing Render service that runs `python main.py`, add:

| Variable | Value |
| --- | --- |
| `LAVALINK_URI` | The Lavalink URL, including `http://` or `https://` |
| `LAVALINK_PASSWORD` | Exactly the same value used by the Lavalink service |
| `LAVALINK_IDENTIFIER` | Optional; defaults to `ysl-lavalink` |

Do not put these values in the repository. Render environment variables are
the correct place for them.

## 3. Discord permissions

The bot needs these permissions in the server:

- Connect
- Speak
- Send Messages
- Embed Links

Users can use both prefix and slash commands:

```text
!play <song name or URL>
!queue
!nowplaying
!skip
!pause
!resume
!stop
!volume <0-1000>
!loop <off|track|queue>
!shuffle
!remove <position>
!disconnect
```

The same commands are available with `/`. A user must be in the voice channel
where the bot is playing to control that server's queue.

`/loop` offers the same modes as the prefix command: **Off**, **Current track**,
and **Entire queue**. Queue positions shown by `!queue` start at 1, so
`!remove 2` removes the second upcoming track.

## 4. Supported sources

The included Lavalink configuration enables YouTube search through the
official YouTube source plugin, plus direct SoundCloud and HTTP sources.
Spotify URLs are not enabled by this setup. Adding Spotify support requires
deploying LavaSrc and configuring Spotify credentials separately.

## 5. Deploy the bot

After adding the variables, redeploy the bot service. On startup, look for:

```text
Lavalink node ready
```

If the Lavalink variables are missing or the service is offline, the rest of
the bot will still start and music commands will explain that music is not
available.
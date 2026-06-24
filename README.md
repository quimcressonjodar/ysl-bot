# 🏆 YSL Bot - Protox.io Clan

Official Discord bot for the **YSL** clan on [Protox.io](https://protox.io).

## ✨ Features

*   **🎮 Protox.io Integration**:
    *   Link Discord accounts with Protox Player IDs.
    *   Weekly XP tracking with automatic snapshots every Sunday.
    *   Weekly clan leaderboard.
*   **🛡️ Moderation**:
    *   Warnings, Timeouts (Mute), Kicks, and Bans.
    *   Message purging.
    *   Staff report system.
*   **🌐 Web Backend**:
    *   Flask server with health checks and basic stats API.
    *   Compatible with Render and UptimeRobot.

## 🚀 Setup

1.  **Clone the repo**: `git clone https://github.com/quimcressonjodar/ysl-bot.git`
2.  **Install requirements**: `pip install -r requirements.txt`
3.  **Configure environment**: Create a `.env` file based on `.env.example`.
4.  **Run the bot**: `python main.py`

## 📝 Commands

*   `/register <player_id> <username>`: Link your Protox account.
*   `/profile`: View your Protox profile.
*   `/weeklyxp`: Check your XP earned this week.
*   `/leaderboard`: View the clan's top players for the week.
*   `/warn`, `/mute`, `/kick`, `/ban`, `/purge`: Moderation tools.

## 📄 License
MIT

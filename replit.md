# YSL Bot

A Discord bot built with `discord.py` using a modular Cog-based architecture. Features include economy, pets, games, stocks, starboard, bounties, and business systems — all backed by MongoDB.

## Stack
- **Python** + `discord.py`
- **MongoDB** (via `pymongo`) — database for all user data
- **Flask** — keep-alive HTTP server running in a background thread
- **OpenAI** — used by the `fake_admin_ai` cog

## Required Secrets
| Secret | Description |
|--------|-------------|
| `DISCORD_TOKEN` | Discord bot token |
| `MONGO_URI` | MongoDB connection string |
| `GITHUB_TOKEN` | GitHub PAT for pushing changes |
| `OPENAI_API_KEY` | OpenAI key (for fake_admin_ai cog) |

## How to run
```bash
python main.py
```

## Structure
- `main.py` — entry point, loads cogs, starts Flask keep-alive
- `cogs/` — feature modules (admin, economy, pets, games, utility, events, fake_admin_ai, starboard, stocks, bounties, business)
- `utils/` — shared helpers and DB operations
- `views/` — Discord UI components (buttons, selects)
- `config.py` — constants, loot tables, shop prices, env vars
- `database.py` — MongoDB connection and collection references

## Git workflow
After each requested change, push to `origin main` on GitHub using the configured `GITHUB_TOKEN`.

## User preferences
- Make requested code changes then git push after each one.

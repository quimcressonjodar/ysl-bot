# Repository Guidelines

## Project Structure & Module Organization
The project is a Discord bot built with `discord.py`, following a modular Cog-based architecture.

- **`.\main.py`**: Entry point. Initializes the `WeeklyXPBot`, loads extensions (Cogs), and starts a Flask server in a background thread for keep-alive functionality.
- **`.\cogs\`**: Contains feature-specific modules (e.g., `admin`, `economy`, `pets`, `protox`). Each file defines a `commands.Cog` class.
- **`.\utils\`**: Shared utility functions and API clients.
    - `.\utils\economy.py`: Core database operations for the currency system.
    - `.\utils\protox_api.py`: `ClanClient` for interacting with the Protox.io API.
    - `.\utils\helpers.py`: Common helpers (e.g., permission checks, duration parsing).
- **`.\views\`**: Discord UI components (Buttons, Select menus) used for interactive messages.
- **`.\config.py`**: Centralized configuration, constants (e.g., loot tables, shop prices), and environment variable management.
- **`.\database.py`**: MongoDB connection setup using `pymongo`.

## Build, Test, and Development Commands
The project uses standard Python tools. Ensure a `.env` file is present with `DISCORD_TOKEN` and `PROTOX_API_KEY`.

- **Install dependencies**: `pip install -r requirements.txt`
- **Run the bot**: `python main.py`
- **Environment**: Managed via `python-dotenv`. Port for Flask defaults to `10000` (configurable via `PORT`).

## Coding Style & Naming Conventions
- **Asynchronous Code**: All Discord interactions and API calls must use `async`/`await`.
- **Naming**: Follow PEP 8 (snake_case for functions/variables, PascalCase for classes).
- **Configuration**: Avoid hardcoding values; use `.\config.py` for constants and environment variables.
- **Database**: Use the centralized collections defined in `.\database.py` (e.g., `eco_col`).

## Commit & Pull Request Guidelines
- **Commit Messages**: Use short, imperative summaries of changes (e.g., "Add pet trading system", "Fix economy exploit").
- **Refactoring**: When moving logic, ensure Cog loading in `main.py` is updated accordingly.

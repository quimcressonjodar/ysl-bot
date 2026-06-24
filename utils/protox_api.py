"""
utils/protox_api.py - Async HTTP client for the Protox.io API.
"""

import logging
import aiohttp
import asyncio
from typing import Any, Optional

import config

logger = logging.getLogger("ysl-bot.api")


class ProtoxClient:
    """Asynchronous client for Protox.io API."""

    def __init__(self, api_base: str, api_key: str = ""):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Initializes the aiohttp session."""
        if self.session is None or self.session.closed:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=config.HTTP_TIMEOUT_SECONDS)
            )
            logger.info("ProtoxClient HTTP session started.")

    async def close(self):
        """Closes the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("ProtoxClient HTTP session closed.")

    async def get_player(self, player_id: str) -> dict:
        """
        Fetches player data from the API.
        Update this method once the actual API structure is known.
        """
        if not self.session:
            await self.start()

        url = f"{self.api_base}/api/player/{player_id}"
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"API status {response.status} for player {player_id}")
                    return {}
        except Exception as e:
            logger.error(f"Error fetching player {player_id}: {e}")
            return {}

    async def get_player_xp(self, player_id: str) -> int:
        """
        Fetches the total XP of a player.
        Update this method once the actual API structure is known.
        """
        data = await self.get_player(player_id)
        # Placeholder keys - update with real API keys
        for key in ("total_xp", "xp", "experience", "points", "totalXp"):
            if key in data:
                try:
                    return int(data[key])
                except (ValueError, TypeError):
                    continue
        
        # Check nested data
        for nested in ("data", "stats", "player"):
            if nested in data and isinstance(data[nested], dict):
                for key in ("total_xp", "xp", "experience", "totalXp"):
                    if key in data[nested]:
                        try:
                            return int(data[nested][key])
                        except (ValueError, TypeError):
                            continue
        return 0

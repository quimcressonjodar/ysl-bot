"""
utils/protox_api.py - Cliente HTTP asíncrono para la API de Protox.io.

Gestiona todas las peticiones a la API de Protox.io con reintentos
automáticos, manejo de errores y caché básica en memoria.
"""

import asyncio
import logging
import time
from typing import Any, Optional
from urllib.parse import quote

import aiohttp
import config

logger = logging.getLogger("ysl-bot.protox_api")


class ProtoxClient:
    """
    Cliente asíncrono para la API de Protox.io.

    Gestiona la sesión HTTP, los reintentos y la caché en memoria
    para reducir la carga sobre la API externa.
    """

    def __init__(self, api_base: str, api_key: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        # Caché simple: {cache_key: (timestamp, data)}
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl: float = 300.0  # 5 minutos

    async def start(self) -> None:
        """Inicializa la sesión HTTP."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=config.HTTP_TIMEOUT_SECONDS)
        )
        logger.info("Sesión HTTP de ProtoxClient iniciada.")

    async def close(self) -> None:
        """Cierra la sesión HTTP."""
        if self.session:
            await self.session.close()
            logger.info("Sesión HTTP de ProtoxClient cerrada.")

    # ============================================================
    # Métodos públicos de la API
    # ============================================================

    async def get_player(self, player_id: str) -> dict[str, Any]:
        """
        Obtiene los datos de un jugador por su Player ID.

        Args:
            player_id: Identificador único del jugador en Protox.io.

        Returns:
            Diccionario con los datos del jugador.
        """
        cache_key = f"player:{player_id}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        url = f"{self.api_base}/api/player/{quote(player_id, safe='')}"
        data = await self._request_with_retry("GET", url)
        self._set_cache(cache_key, data)
        return data

    async def get_player_xp(self, player_id: str) -> int:
        """
        Obtiene el XP total actual de un jugador.

        Args:
            player_id: Identificador único del jugador en Protox.io.

        Returns:
            XP total del jugador como entero.
        """
        player_data = await self.get_player(player_id)
        return self._extract_xp(player_data)

    async def get_clan_data(self, clan_name: str) -> dict[str, Any]:
        """
        Obtiene los datos del clan por su nombre.

        Args:
            clan_name: Nombre o tag del clan en Protox.io.

        Returns:
            Diccionario con los datos del clan y sus miembros.
        """
        cache_key = f"clan:{clan_name}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        encoded = quote(clan_name.strip(), safe="")
        url = f"{self.api_base}/api/clan/{encoded}"
        data = await self._request_with_retry("GET", url)
        self._set_cache(cache_key, data)
        return data

    async def get_clan_members(self, clan_name: str) -> list[dict[str, Any]]:
        """
        Obtiene la lista de miembros del clan.

        Args:
            clan_name: Nombre o tag del clan en Protox.io.

        Returns:
            Lista de diccionarios con los datos de cada miembro.
        """
        clan_data = await self.get_clan_data(clan_name)
        return self._extract_members(clan_data)

    async def get_player_stats(self, player_id: str) -> dict[str, Any]:
        """
        Obtiene las estadísticas detalladas de un jugador.

        Args:
            player_id: Identificador único del jugador en Protox.io.

        Returns:
            Diccionario con las estadísticas del jugador.
        """
        cache_key = f"stats:{player_id}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        url = f"{self.api_base}/api/player/{quote(player_id, safe='')}/stats"
        try:
            data = await self._request_with_retry("GET", url)
            self._set_cache(cache_key, data)
            return data
        except Exception:
            # Si el endpoint de stats no existe, devolver datos básicos del jugador
            return await self.get_player(player_id)

    # ============================================================
    # Métodos internos
    # ============================================================

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        json_payload: Optional[dict] = None,
    ) -> Any:
        """
        Realiza una petición HTTP con reintentos automáticos.

        Args:
            method: Método HTTP (GET, POST, etc.).
            url: URL de la petición.
            json_payload: Cuerpo JSON opcional para peticiones POST.

        Returns:
            Respuesta JSON deserializada.

        Raises:
            RuntimeError: Si todos los reintentos fallan.
        """
        if not self.session:
            raise RuntimeError("La sesión HTTP no está inicializada. Llama a start() primero.")

        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["ApiKey"] = self.api_key

        last_error: Optional[Exception] = None

        for attempt in range(1, config.HTTP_MAX_RETRIES + 1):
            try:
                async with self.session.request(
                    method.upper(),
                    url,
                    headers=headers,
                    json=json_payload,
                ) as response:
                    body = await response.text()

                    if response.status == 429:
                        retry_after = float(
                            response.headers.get("Retry-After", "0") or 0
                        )
                        delay = retry_after if retry_after > 0 else config.HTTP_RETRY_BASE_DELAY * attempt
                        logger.warning(f"Rate limit alcanzado. Esperando {delay:.1f}s...")
                        await asyncio.sleep(delay)
                        continue

                    if response.status >= 500:
                        raise RuntimeError(
                            f"Error temporal del servidor Protox.io [{response.status}]: {body[:200]}"
                        )

                    if response.status in {401, 403}:
                        raise RuntimeError(
                            "La API de Protox.io rechazó la clave de autenticación (401/403). "
                            "Verifica PROTOX_API_KEY en el archivo .env."
                        )

                    if response.status == 404:
                        raise RuntimeError(
                            f"Recurso no encontrado en la API de Protox.io (404): {url}"
                        )

                    if not (200 <= response.status < 300):
                        raise RuntimeError(
                            f"Error de la API de Protox.io [{response.status}]: {body[:300]}"
                        )

                    return await response.json(content_type=None)

            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
                last_error = exc
                logger.warning(
                    f"Intento {attempt}/{config.HTTP_MAX_RETRIES} fallido para {url}: {exc}"
                )
                if attempt < config.HTTP_MAX_RETRIES:
                    await asyncio.sleep(config.HTTP_RETRY_BASE_DELAY * attempt)

        raise RuntimeError(
            f"Petición fallida tras {config.HTTP_MAX_RETRIES} intentos a {url}: {last_error}"
        )

    def _extract_xp(self, player_data: dict[str, Any]) -> int:
        """Extrae el XP total de los datos del jugador."""
        for key in ("xp", "experience", "totalXp", "total_xp", "allScores", "scores", "points"):
            value = player_data.get(key)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass
        # Buscar en datos anidados
        for nested_key in ("stats", "data", "player"):
            nested = player_data.get(nested_key)
            if isinstance(nested, dict):
                for key in ("xp", "experience", "totalXp", "total_xp", "allScores"):
                    value = nested.get(key)
                    if value is not None:
                        try:
                            return int(value)
                        except (TypeError, ValueError):
                            pass
        logger.warning(f"No se pudo extraer XP de los datos del jugador: {list(player_data.keys())}")
        return 0

    def _extract_members(self, clan_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extrae la lista de miembros del clan."""
        for key in ("members", "clanUsers", "users", "players"):
            members = clan_data.get(key)
            if isinstance(members, list):
                return members
        # Buscar en datos anidados
        for nested_key in ("data", "clan"):
            nested = clan_data.get(nested_key)
            if isinstance(nested, dict):
                for key in ("members", "clanUsers", "users", "players"):
                    members = nested.get(key)
                    if isinstance(members, list):
                        return members
        return []

    # ============================================================
    # Caché en memoria
    # ============================================================

    def _get_cache(self, key: str) -> Optional[Any]:
        """Obtiene un valor de la caché si no ha expirado."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        timestamp, data = entry
        if time.monotonic() - timestamp > self._cache_ttl:
            del self._cache[key]
            return None
        return data

    def _set_cache(self, key: str, data: Any) -> None:
        """Almacena un valor en la caché."""
        self._cache[key] = (time.monotonic(), data)

    def clear_cache(self) -> None:
        """Limpia toda la caché en memoria."""
        self._cache.clear()
        logger.info("Caché de ProtoxClient limpiada.")

"""
web/__init__.py - Módulo web del bot YSL.
"""

from .server import start_web_server, app

__all__ = ["start_web_server", "app"]

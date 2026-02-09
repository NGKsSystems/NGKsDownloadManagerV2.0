"""
UI Adapter Package - Engine isolation layer for V4 UI
Provides thread-safe access to download engine functionality
"""

from .api import UIAdapter
from .events import UIEventManager, UIEvent

__all__ = ['UIAdapter', 'UIEventManager', 'UIEvent']
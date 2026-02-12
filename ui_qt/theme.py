#!/usr/bin/env python3
"""
NGKsAcquisitionCore — Theme + Asset Loader
F19/F21 compliant: safe path resolution, no cwd assumptions.
"""

import os
from typing import Optional

# === Path Resolution (safe, portable) ===

# Base directory of ui_qt package
_UI_QT_DIR = os.path.dirname(os.path.abspath(__file__))
# Project root (one level up)
_PROJECT_ROOT = os.path.dirname(_UI_QT_DIR)
# Brand assets folder
ASSET_DIR = os.path.join(_PROJECT_ROOT, "assets", "brand")

# Logo paths (prefer PNG for Qt compatibility in packaged builds)
LOGO_512 = os.path.join(ASSET_DIR, "logo_512.png")
LOGO_256 = os.path.join(ASSET_DIR, "logo_256.png")
LOGO_128 = os.path.join(ASSET_DIR, "logo_128.png")
LOGO_64 = os.path.join(ASSET_DIR, "logo_64.png")
LOGO_SVG = os.path.join(ASSET_DIR, "ngks_acquisitioncore_logo.svg")


def get_logo_path(size: int = 128) -> Optional[str]:
    """Get the path to the logo of the requested size.
    
    Falls back to smaller sizes if requested size not found.
    Returns None if no logo file exists.
    """
    size_map = {
        512: LOGO_512,
        256: LOGO_256,
        128: LOGO_128,
        64: LOGO_64,
    }
    # Try exact size first
    if size in size_map and os.path.isfile(size_map[size]):
        return size_map[size]
    # Fallback chain
    for fallback_size in [128, 64, 256, 512]:
        if os.path.isfile(size_map.get(fallback_size, "")):
            return size_map[fallback_size]
    # Last resort: SVG
    if os.path.isfile(LOGO_SVG):
        return LOGO_SVG
    return None


# === Theme Colors (F21 locked values) ===

class Colors:
    """NGKsAcquisitionCore brand color palette."""
    BG = "#0B1320"           # Deep navy background
    PANEL = "#101B2D"        # Panel/card background
    TEXT = "#EAF0FF"         # Primary text
    MUTED = "#A9B7D0"        # Secondary/muted text
    BORDER = "#21314D"       # Border color
    ACCENT_BLUE = "#2F8CFF"  # Primary accent (blue)
    ACCENT_GREEN = "#37D39A" # Success accent (green)
    DANGER = "#FF5C5C"       # Error/danger (red)


# === App Identity ===

APP_NAME = "NGKsAcquisitionCore"
APP_VERSION = "2.0.1"
APP_TAGLINE = "Powered by: NGKsSystems"


def get_window_title() -> str:
    """Get the standard window title string."""
    return f"{APP_NAME} v{APP_VERSION} — {APP_TAGLINE}"


def get_status_ready() -> str:
    """Get the standard status bar 'ready' message."""
    return f"Ready — {APP_NAME} v{APP_VERSION} — {APP_TAGLINE}"


# === Qt Stylesheet ===

def get_stylesheet() -> str:
    """Get the main application stylesheet (dark navy theme)."""
    return f"""
        QMainWindow {{
            background-color: {Colors.BG};
        }}
        QWidget {{
            background-color: {Colors.BG};
            color: {Colors.TEXT};
            font-family: "Segoe UI", sans-serif;
        }}
        QGroupBox {{
            font-weight: bold;
            border: 1px solid {Colors.BORDER};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 10px;
            background-color: {Colors.PANEL};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            color: {Colors.TEXT};
        }}
        QTabWidget::pane {{
            border: 1px solid {Colors.BORDER};
            background-color: {Colors.PANEL};
            border-radius: 4px;
        }}
        QTabBar::tab {{
            background-color: {Colors.PANEL};
            color: {Colors.MUTED};
            border: 1px solid {Colors.BORDER};
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        QTabBar::tab:selected {{
            background-color: {Colors.ACCENT_BLUE};
            color: {Colors.TEXT};
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {Colors.BORDER};
        }}
        QTableWidget {{
            gridline-color: {Colors.BORDER};
            background-color: {Colors.PANEL};
            alternate-background-color: {Colors.BG};
            border: 1px solid {Colors.BORDER};
            border-radius: 4px;
            color: {Colors.TEXT};
        }}
        QHeaderView::section {{
            background-color: {Colors.BG};
            color: {Colors.TEXT};
            border: none;
            border-right: 1px solid {Colors.BORDER};
            border-bottom: 1px solid {Colors.BORDER};
            padding: 6px;
            font-weight: bold;
        }}
        QPushButton {{
            background-color: {Colors.ACCENT_BLUE};
            color: {Colors.TEXT};
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: #4DA3FF;
        }}
        QPushButton:pressed {{
            background-color: #1A6FD9;
        }}
        QPushButton:disabled {{
            background-color: {Colors.BORDER};
            color: {Colors.MUTED};
        }}
        QPushButton[danger="true"] {{
            background-color: {Colors.DANGER};
        }}
        QPushButton[danger="true"]:hover {{
            background-color: #FF7A7A;
        }}
        QPushButton[success="true"] {{
            background-color: {Colors.ACCENT_GREEN};
        }}
        QPushButton[success="true"]:hover {{
            background-color: #4FE8B0;
        }}
        QLineEdit {{
            border: 1px solid {Colors.BORDER};
            border-radius: 4px;
            padding: 8px;
            background-color: {Colors.PANEL};
            color: {Colors.TEXT};
        }}
        QLineEdit:focus {{
            border-color: {Colors.ACCENT_BLUE};
        }}
        QComboBox {{
            border: 1px solid {Colors.BORDER};
            border-radius: 4px;
            padding: 6px;
            background-color: {Colors.PANEL};
            color: {Colors.TEXT};
        }}
        QComboBox:focus {{
            border-color: {Colors.ACCENT_BLUE};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {Colors.PANEL};
            color: {Colors.TEXT};
            selection-background-color: {Colors.ACCENT_BLUE};
        }}
        QCheckBox {{
            spacing: 8px;
            color: {Colors.TEXT};
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 1px solid {Colors.BORDER};
            border-radius: 3px;
            background-color: {Colors.PANEL};
        }}
        QCheckBox::indicator:checked {{
            background-color: {Colors.ACCENT_BLUE};
            border-color: {Colors.ACCENT_BLUE};
        }}
        QSpinBox, QDoubleSpinBox {{
            border: 1px solid {Colors.BORDER};
            border-radius: 4px;
            padding: 6px;
            background-color: {Colors.PANEL};
            color: {Colors.TEXT};
        }}
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {Colors.ACCENT_BLUE};
        }}
        QProgressBar {{
            border: 1px solid {Colors.BORDER};
            border-radius: 4px;
            text-align: center;
            background-color: {Colors.PANEL};
            color: {Colors.TEXT};
        }}
        QProgressBar::chunk {{
            background-color: {Colors.ACCENT_BLUE};
            border-radius: 3px;
        }}
        QStatusBar {{
            background-color: {Colors.BG};
            color: {Colors.MUTED};
            border-top: 1px solid {Colors.BORDER};
        }}
        QScrollBar:vertical {{
            border: none;
            background-color: {Colors.BG};
            width: 12px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background-color: {Colors.BORDER};
            border-radius: 6px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {Colors.MUTED};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QLabel {{
            color: {Colors.TEXT};
        }}
        QLabel[muted="true"] {{
            color: {Colors.MUTED};
        }}
        QMessageBox {{
            background-color: {Colors.PANEL};
        }}
        QMessageBox QLabel {{
            color: {Colors.TEXT};
        }}
    """

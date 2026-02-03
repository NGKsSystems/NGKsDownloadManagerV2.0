"""
V4 UI Application Entry Point - PySide6
Launch via: python -m ui_qt.app
Separate launcher - does NOT modify V1 (main.py)
"""

import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication
from ui_qt.main_window import MainWindow


def main():
    """V4 UI main entry point"""
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("NGK's Download Manager")
    app.setApplicationVersion("4.0")
    app.setOrganizationName("NGK Systems")
    
    # Set Fusion style for modern look
    app.setStyle('Fusion')
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
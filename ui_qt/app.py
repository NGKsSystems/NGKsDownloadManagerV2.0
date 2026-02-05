"""
V4 UI Application Entry Point - PySide6
Launch via: python -m ui_qt.app
Separate launcher - does NOT modify V1 (main.py)
"""

import sys
import os
import logging
import traceback
import signal
import threading
import shutil
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class _StreamToLogger:
    """File-like stream object that redirects writes to a logger."""
    def __init__(self, logger: logging.Logger, level: int):
        self.logger = logger
        self.level = level
        self._buffer = ""

    def write(self, message: str):
        if not message:
            return
        self._buffer += message
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.rstrip()
            if line:
                self.logger.log(self.level, line)

    def flush(self):
        buf = self._buffer.strip()
        if buf:
            self.logger.log(self.level, buf)
        self._buffer = ""


def setup_ui_logging():
    """Setup file logging for UI application"""
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(project_root, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Setup file logger
    log_file = os.path.join(logs_dir, 'ui.log')
    
    # Configure logging
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_handler.flush = lambda: file_handler.stream.flush() if hasattr(file_handler, 'stream') else None
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            file_handler,
            logging.StreamHandler()  # Also log to console
        ]
    )
    
    logger = logging.getLogger('ui')
    
    # Capture uncaught exceptions to log file
    def _excepthook(exc_type, exc, tb):
        logger.error("UNCAUGHT EXCEPTION", exc_info=(exc_type, exc, tb))
    sys.excepthook = _excepthook

    # Capture uncaught thread exceptions too (Python 3.8+)
    if hasattr(threading, "excepthook"):
        def _thread_excepthook(args):
            logger.error(
                "UNCAUGHT THREAD EXCEPTION",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
            )
        threading.excepthook = _thread_excepthook

    # Redirect stdout/stderr into the logger (reduces copy/paste from terminal)
    sys.stdout = _StreamToLogger(logger, logging.INFO)
    sys.stderr = _StreamToLogger(logger, logging.ERROR)
    
    logger.info("=" * 60)
    logger.info("NGK'S DOWNLOAD MANAGER V4.0 UI STARTED")
    logger.info("=" * 60)
    
    return logger


def auto_save_logs(reason="shutdown"):
    """Automatically save logs to DL Manager Logs folder with timestamp"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logs_dir = r"C:\Users\suppo\Downloads\DL Manager Logs"
        
        # Create directory if it doesn't exist
        os.makedirs(logs_dir, exist_ok=True)
        
        # Create destination filename
        log_filename = f"NGKs_DownloadManager_Log_{reason}_{timestamp}.log"
        dest_path = os.path.join(logs_dir, log_filename)
        
        # Copy log file if it exists
        log_file = os.path.join(project_root, 'logs', 'ui.log')
        if os.path.exists(log_file):
            shutil.copy2(log_file, dest_path)
            print(f"LOG SAVED: {dest_path}")
            return dest_path
        else:
            print("No log file found to save")
            return None
    except Exception as e:
        print(f"Failed to auto-save log: {e}")
        return None


def main():
    """V4 UI main entry point"""
    # Setup logging first
    logger = setup_ui_logging()
    
    try:
        from PySide6.QtWidgets import QApplication
        from ui_qt.main_window import MainWindow
        
        logger.info("Creating Qt application...")
        
        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("NGK's Download Manager")
        app.setApplicationVersion("4.0")
        app.setOrganizationName("NGK Systems")
        
        # Set Fusion style for modern look
        app.setStyle('Fusion')
        
        logger.info("Creating main window...")
        
        # Create and show main window
        window = MainWindow()
        window.show()
        
        logger.info("UI launched successfully - entering event loop")
        
        # Run event loop
        exit_code = app.exec()
        
        # Auto-save logs on normal exit
        logger.info("Application closing normally")
        auto_save_logs("normal_exit")
        
        return exit_code
        
    except Exception as e:
        logger.error(f"FATAL ERROR: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        # Auto-save logs on error
        auto_save_logs("error_exit")
        
        return 1


if __name__ == "__main__":
    try:
        # Prevent Ctrl+C / SIGINT from spamming KeyboardInterrupt tracebacks in a GUI app
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except Exception:
        # If the platform/runtime doesn't support it, fail harmlessly
        pass

    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # Auto-save logs on forced exit
        auto_save_logs("interrupted_exit")
        # Clean, silent exit (no traceback spam)
        sys.exit(0)
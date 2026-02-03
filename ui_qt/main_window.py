"""
V4 Main Window - PySide6 UI with V1 parity
All controls wired via ui_adapter (no direct engine access)
Modern Qt Fusion styling with proper spacing/fonts
"""

import os
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
    QLineEdit, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QCheckBox, QSpinBox, QProgressBar, QFrame, QGroupBox, QFormLayout
)
from PySide6.QtCore import QTimer, Qt, QThread, Signal
from PySide6.QtGui import QFont

# UI imports (only these allowed)
from ui_adapter.api import get_adapter, shutdown_adapter
from ui_adapter.events import get_event_manager, shutdown_events, UIEvent


class DownloadsTab(QWidget):
    """Downloads tab with V1 parity + full wiring"""
    
    def __init__(self, adapter):
        super().__init__()
        self.adapter = adapter
        self.setup_ui()
    
    def setup_ui(self):
        """Setup downloads tab UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # URL input group
        url_group = QGroupBox("Download URL")
        url_group.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        url_layout = QVBoxLayout()
        
        # URL input with validation
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Enter URL to download...")
        self.url_entry.setFont(QFont("Consolas", 10))
        self.url_entry.textChanged.connect(self.on_url_changed)
        self.url_entry.returnPressed.connect(self.start_download)
        
        # URL info display
        self.url_info_label = QLabel("")
        self.url_info_label.setFont(QFont("Segoe UI", 9))
        self.url_info_label.setStyleSheet("color: #0078d4; font-style: italic;")
        
        url_layout.addWidget(self.url_entry)
        url_layout.addWidget(self.url_info_label)
        url_group.setLayout(url_layout)
        
        # Destination group
        dest_group = QGroupBox("Download Options")
        dest_group.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        dest_layout = QFormLayout()
        
        # Destination folder
        dest_widget = QWidget()
        dest_hlayout = QHBoxLayout(dest_widget)
        dest_hlayout.setContentsMargins(0, 0, 0, 0)
        
        self.dest_entry = QLineEdit()
        self.dest_entry.setText(os.path.expanduser("~/Downloads"))
        self.dest_entry.setFont(QFont("Consolas", 9))
        self.dest_entry.setReadOnly(True)
        
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setFont(QFont("Segoe UI", 9))
        self.browse_btn.clicked.connect(self.browse_destination)
        
        dest_hlayout.addWidget(self.dest_entry)
        dest_hlayout.addWidget(self.browse_btn)
        
        dest_layout.addRow("Destination:", dest_widget)
        dest_group.setLayout(dest_layout)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("Download")
        self.download_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.download_btn.clicked.connect(self.start_download)
        
        self.paste_btn = QPushButton("Paste URL")
        self.paste_btn.setFont(QFont("Segoe UI", 9))
        self.paste_btn.clicked.connect(self.paste_url)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFont(QFont("Segoe UI", 9))
        self.clear_btn.clicked.connect(self.clear_url)
        
        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(self.paste_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()
        
        # Progress group
        progress_group = QGroupBox("Download Progress")
        progress_group.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        progress_layout = QVBoxLayout()
        
        # Downloads table
        self.downloads_table = QTableWidget()
        self.downloads_table.setColumnCount(6)
        self.downloads_table.setHorizontalHeaderLabels([
            "ID", "Filename", "URL Type", "Progress", "Speed", "Status"
        ])
        self.downloads_table.setFont(QFont("Segoe UI", 9))
        
        # Configure table headers
        header = self.downloads_table.horizontalHeader()
        header.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # Filename
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # URL Type
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Progress
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Speed
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Status
        
        # Table style
        self.downloads_table.setAlternatingRowColors(True)
        self.downloads_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setFont(QFont("Segoe UI", 9))
        self.pause_btn.clicked.connect(self.pause_download)
        
        self.resume_btn = QPushButton("Resume")
        self.resume_btn.setFont(QFont("Segoe UI", 9))
        self.resume_btn.clicked.connect(self.resume_download)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFont(QFont("Segoe UI", 9))
        self.cancel_btn.clicked.connect(self.cancel_download)
        
        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.setFont(QFont("Segoe UI", 9))
        self.open_folder_btn.clicked.connect(self.open_folder)
        
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.resume_btn)
        control_layout.addWidget(self.cancel_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.open_folder_btn)
        
        progress_layout.addWidget(self.downloads_table)
        progress_layout.addLayout(control_layout)
        progress_group.setLayout(progress_layout)
        
        # Add all groups to main layout
        layout.addWidget(url_group)
        layout.addWidget(dest_group)
        layout.addLayout(button_layout)
        layout.addWidget(progress_group)
    
    def on_url_changed(self, text):
        """Handle URL input change - validate via adapter"""
        if text.strip():
            result = self.adapter.validate_url(text.strip())
            if result['valid']:
                self.url_info_label.setText(f"Detected: {result['type']}")
                self.url_info_label.setStyleSheet("color: #107c10; font-style: italic;")
            else:
                self.url_info_label.setText(f"Invalid: {result.get('error', 'Unknown error')}")
                self.url_info_label.setStyleSheet("color: #d13438; font-style: italic;")
        else:
            self.url_info_label.setText("")
    
    def paste_url(self):
        """Paste URL from clipboard"""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.url_entry.setText(text.strip())
    
    def clear_url(self):
        """Clear URL input"""
        self.url_entry.clear()
    
    def browse_destination(self):
        """Browse for destination directory"""
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select Download Directory", 
            self.dest_entry.text()
        )
        if directory:
            self.dest_entry.setText(directory)
    
    def start_download(self):
        """Start download via adapter"""
        url = self.url_entry.text().strip()
        destination = self.dest_entry.text().strip()
        
        if not url:
            QMessageBox.warning(self, "Warning", "Please enter a URL to download")
            return
        
        if not destination:
            QMessageBox.warning(self, "Warning", "Please select a destination directory")
            return
        
        try:
            download_id = self.adapter.start_download(url, destination)
            self.url_entry.clear()  # Clear URL after starting
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start download: {str(e)}")
    
    def get_selected_download_id(self):
        """Get currently selected download ID"""
        current_row = self.downloads_table.currentRow()
        if current_row >= 0:
            id_item = self.downloads_table.item(current_row, 0)
            if id_item:
                return id_item.text()
        return None
    
    def pause_download(self):
        """Pause selected download via adapter"""
        download_id = self.get_selected_download_id()
        if download_id:
            success = self.adapter.pause(download_id)
            if not success:
                QMessageBox.warning(self, "Warning", "Failed to pause download")
    
    def resume_download(self):
        """Resume selected download via adapter"""
        download_id = self.get_selected_download_id()
        if download_id:
            success = self.adapter.resume(download_id)
            if not success:
                QMessageBox.warning(self, "Warning", "Failed to resume download")
    
    def cancel_download(self):
        """Cancel selected download via adapter"""
        download_id = self.get_selected_download_id()
        if download_id:
            reply = QMessageBox.question(
                self, "Confirm", 
                "Are you sure you want to cancel this download?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                success = self.adapter.cancel(download_id)
                if not success:
                    QMessageBox.warning(self, "Warning", "Failed to cancel download")
    
    def open_folder(self):
        """Open folder of selected download via adapter"""
        download_id = self.get_selected_download_id()
        if download_id:
            success = self.adapter.open_folder(download_id)
            if not success:
                QMessageBox.warning(self, "Warning", "Failed to open folder")
    
    def update_downloads_table(self, downloads):
        """Update downloads table with current data"""
        self.downloads_table.setRowCount(len(downloads))
        
        for row, download in enumerate(downloads):
            # Download ID
            id_item = QTableWidgetItem(download['download_id'])
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.downloads_table.setItem(row, 0, id_item)
            
            # Filename
            filename_item = QTableWidgetItem(download['filename'])
            filename_item.setFlags(filename_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.downloads_table.setItem(row, 1, filename_item)
            
            # URL Type
            type_item = QTableWidgetItem(download['url_type'])
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.downloads_table.setItem(row, 2, type_item)
            
            # Progress
            progress_item = QTableWidgetItem(download['progress'])
            progress_item.setFlags(progress_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.downloads_table.setItem(row, 3, progress_item)
            
            # Speed
            speed_item = QTableWidgetItem(download['speed'])
            speed_item.setFlags(speed_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.downloads_table.setItem(row, 4, speed_item)
            
            # Status
            status_item = QTableWidgetItem(download['status'])
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.downloads_table.setItem(row, 5, status_item)


class SettingsTab(QWidget):
    """Settings tab with V1 parity + persistence"""
    
    def __init__(self, adapter):
        super().__init__()
        self.adapter = adapter
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Setup settings tab UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Hugging Face settings
        hf_group = QGroupBox("Hugging Face Settings")
        hf_group.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        hf_layout = QFormLayout()
        
        # HF Token entry
        token_widget = QWidget()
        token_layout = QHBoxLayout(token_widget)
        token_layout.setContentsMargins(0, 0, 0, 0)
        
        self.hf_token_entry = QLineEdit()
        self.hf_token_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.hf_token_entry.setFont(QFont("Consolas", 9))
        
        self.test_token_btn = QPushButton("Test Token")
        self.test_token_btn.setFont(QFont("Segoe UI", 9))
        self.test_token_btn.clicked.connect(self.test_hf_token)
        
        token_layout.addWidget(self.hf_token_entry)
        token_layout.addWidget(self.test_token_btn)
        
        hf_layout.addRow("HF Token:", token_widget)
        hf_group.setLayout(hf_layout)
        
        # YouTube settings
        yt_group = QGroupBox("YouTube Settings")
        yt_group.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        yt_layout = QVBoxLayout()
        
        self.auto_quality_check = QCheckBox("Auto-select best quality")
        self.auto_quality_check.setFont(QFont("Segoe UI", 9))
        self.auto_quality_check.setChecked(True)
        
        self.extract_audio_check = QCheckBox("Extract audio only")
        self.extract_audio_check.setFont(QFont("Segoe UI", 9))
        self.extract_audio_check.setChecked(False)
        
        yt_layout.addWidget(self.auto_quality_check)
        yt_layout.addWidget(self.extract_audio_check)
        yt_group.setLayout(yt_layout)
        
        # General settings
        general_group = QGroupBox("General Settings")
        general_group.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        general_layout = QFormLayout()
        
        self.max_downloads_spin = QSpinBox()
        self.max_downloads_spin.setFont(QFont("Segoe UI", 9))
        self.max_downloads_spin.setMinimum(1)
        self.max_downloads_spin.setMaximum(10)
        self.max_downloads_spin.setValue(3)
        
        general_layout.addRow("Max concurrent downloads:", self.max_downloads_spin)
        general_group.setLayout(general_layout)
        
        # Save button
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.save_btn.clicked.connect(self.save_settings)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addStretch()
        
        # Add all groups
        layout.addWidget(hf_group)
        layout.addWidget(yt_group)
        layout.addWidget(general_group)
        layout.addLayout(button_layout)
        layout.addStretch()
    
    def load_settings(self):
        """Load settings from adapter"""
        try:
            settings = self.adapter.get_settings()
            
            self.hf_token_entry.setText(settings.get('hf_token', ''))
            self.auto_quality_check.setChecked(settings.get('auto_quality', True))
            self.extract_audio_check.setChecked(settings.get('extract_audio', False))
            self.max_downloads_spin.setValue(settings.get('max_downloads', 3))
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to load settings: {str(e)}")
    
    def save_settings(self):
        """Save settings via adapter"""
        try:
            settings = {
                'hf_token': self.hf_token_entry.text(),
                'auto_quality': self.auto_quality_check.isChecked(),
                'extract_audio': self.extract_audio_check.isChecked(),
                'max_downloads': self.max_downloads_spin.value()
            }
            
            success = self.adapter.set_settings(settings)
            if success:
                self.adapter.save_settings()
                QMessageBox.information(self, "Success", "Settings saved successfully")
            else:
                QMessageBox.warning(self, "Warning", "Failed to save settings")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")
    
    def test_hf_token(self):
        """Test HF token via adapter"""
        token = self.hf_token_entry.text().strip()
        if not token:
            QMessageBox.warning(self, "Warning", "Please enter a Hugging Face token")
            return
        
        # Test in background to avoid UI blocking
        def test_worker():
            try:
                if self.adapter.test_hf_token(token):
                    QMessageBox.information(self, "Success", "Hugging Face token is valid")
                else:
                    QMessageBox.warning(self, "Invalid", "Hugging Face token is invalid")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Token test failed: {str(e)}")
        
        import threading
        thread = threading.Thread(target=test_worker, daemon=True)
        thread.start()


class HistoryTab(QWidget):
    """History tab with V1 parity"""
    
    def __init__(self, adapter):
        super().__init__()
        self.adapter = adapter
        self.setup_ui()
        self.load_history()
    
    def setup_ui(self):
        """Setup history tab UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # History table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels([
            "Date", "Filename", "URL", "Status", "Size"
        ])
        self.history_table.setFont(QFont("Segoe UI", 9))
        
        # Configure table headers
        header = self.history_table.horizontalHeader()
        header.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Date
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # Filename  
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)           # URL
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Status
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Size
        
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.clear_history_btn = QPushButton("Clear History")
        self.clear_history_btn.setFont(QFont("Segoe UI", 9))
        self.clear_history_btn.clicked.connect(self.clear_history)
        
        self.export_history_btn = QPushButton("Export History")
        self.export_history_btn.setFont(QFont("Segoe UI", 9))
        self.export_history_btn.clicked.connect(self.export_history)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setFont(QFont("Segoe UI", 9))
        self.refresh_btn.clicked.connect(self.load_history)
        
        button_layout.addWidget(self.clear_history_btn)
        button_layout.addWidget(self.export_history_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.refresh_btn)
        
        layout.addWidget(self.history_table)
        layout.addLayout(button_layout)
    
    def load_history(self):
        """Load history from adapter"""
        try:
            history = self.adapter.get_history()
            self.history_table.setRowCount(len(history))
            
            for row, entry in enumerate(history):
                # Date
                date_item = QTableWidgetItem(entry.get('timestamp', ''))
                date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.history_table.setItem(row, 0, date_item)
                
                # Filename
                filename_item = QTableWidgetItem(entry.get('filename', ''))
                filename_item.setFlags(filename_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.history_table.setItem(row, 1, filename_item)
                
                # URL
                url_item = QTableWidgetItem(entry.get('url', ''))
                url_item.setFlags(url_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.history_table.setItem(row, 2, url_item)
                
                # Status
                status_item = QTableWidgetItem('Completed')  # History only shows completed
                status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.history_table.setItem(row, 3, status_item)
                
                # Size
                size_item = QTableWidgetItem(entry.get('size', 'Unknown'))
                size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.history_table.setItem(row, 4, size_item)
                
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to load history: {str(e)}")
    
    def clear_history(self):
        """Clear history via adapter"""
        reply = QMessageBox.question(
            self, "Confirm", 
            "Are you sure you want to clear all download history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                success = self.adapter.clear_history()
                if success:
                    self.load_history()
                    QMessageBox.information(self, "Success", "History cleared")
                else:
                    QMessageBox.warning(self, "Warning", "Failed to clear history")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear history: {str(e)}")
    
    def export_history(self):
        """Export history via adapter"""
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            "Export History", 
            "download_history.json",
            "JSON files (*.json);;All files (*.*)"
        )
        
        if filename:
            try:
                success = self.adapter.export_history(filename)
                if success:
                    QMessageBox.information(self, "Success", f"History exported to {filename}")
                else:
                    QMessageBox.warning(self, "Warning", "Failed to export history")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export history: {str(e)}")


class MainWindow(QMainWindow):
    """V4 Main Window - PySide6 with V1 parity + modern styling"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize adapter and event manager
        self.adapter = get_adapter()
        self.event_manager = get_event_manager()
        
        # Setup window
        self.setWindowTitle("NGK's Download Manager V4.0")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        # Apply modern styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f3f3f3;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTableWidget {
                gridline-color: #e0e0e0;
                background-color: white;
                alternate-background-color: #f8f8f8;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #e1e1e1;
                border: none;
                border-right: 1px solid #cccccc;
                padding: 6px;
            }
            QPushButton {
                background-color: #e1e1e1;
                border: 1px solid #adadad;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #e5f1fb;
                border-color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #cce4f7;
            }
            QLineEdit {
                border: 2px solid #cccccc;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
            QCheckBox {
                spacing: 8px;
            }
            QSpinBox {
                border: 2px solid #cccccc;
                border-radius: 4px;
                padding: 4px;
                background-color: white;
            }
            QSpinBox:focus {
                border-color: #0078d4;
            }
        """)
        
        self.setup_ui()
        self.setup_events()
    
    def setup_ui(self):
        """Setup main window UI"""
        # Create central widget and tab container
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("Segoe UI", 10))
        
        # Create tabs with adapter
        self.downloads_tab = DownloadsTab(self.adapter)
        self.settings_tab = SettingsTab(self.adapter)
        self.history_tab = HistoryTab(self.adapter)
        
        # Add tabs
        self.tab_widget.addTab(self.downloads_tab, "Downloads")
        self.tab_widget.addTab(self.settings_tab, "Settings")  
        self.tab_widget.addTab(self.history_tab, "History")
        
        layout.addWidget(self.tab_widget)
        
        # Status bar
        self.statusBar().showMessage("Ready - NGK's Download Manager V4.0")
        self.statusBar().setFont(QFont("Segoe UI", 9))
    
    def setup_events(self):
        """Setup event handling from adapter"""
        # Timer to process events from event manager
        self.event_timer = QTimer()
        self.event_timer.timeout.connect(self.process_events)
        self.event_timer.start(200)  # Process every 200ms
        
        # Subscribe to UI events
        self.event_manager.add_subscriber(self.handle_ui_event)
    
    def process_events(self):
        """Process events from event manager"""
        try:
            events = self.event_manager.process_events()
            # Events are handled by handle_ui_event via subscription
        except Exception:
            # Don't let event processing errors crash UI
            pass
        
        # Update downloads table periodically
        try:
            downloads = self.adapter.list_active()
            self.downloads_tab.update_downloads_table(downloads)
        except Exception:
            pass
    
    def handle_ui_event(self, event: UIEvent):
        """Handle UI events from event manager"""
        if event.event_type == 'download_started':
            self.statusBar().showMessage(f"Download started: {event.data.get('filename', 'Unknown')}")
        elif event.event_type == 'download_completed':
            self.statusBar().showMessage(f"Download completed: {event.data.get('filename', 'Unknown')}")
        elif event.event_type == 'download_failed':
            self.statusBar().showMessage(f"Download failed: {event.data.get('filename', 'Unknown')}")
    
    def closeEvent(self, event):
        """Clean shutdown"""
        # Stop timer
        if hasattr(self, 'event_timer'):
            self.event_timer.stop()
        
        # Shutdown adapters
        shutdown_events()
        shutdown_adapter()
        
        event.accept()
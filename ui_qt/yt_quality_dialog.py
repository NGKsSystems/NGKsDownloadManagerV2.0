# ui_qt/yt_quality_dialog.py
"""
YouTube Quality Selection Dialog
Lightweight modal used when multiple video qualities are available.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QHBoxLayout,
)
from PySide6.QtCore import Qt


class YouTubeQualityDialog(QDialog):
    def __init__(self, qualities, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select YouTube Quality")
        self.setModal(True)
        self.resize(360, 300)

        self.selected_quality = None

        layout = QVBoxLayout(self)

        label = QLabel("Select video quality:")
        layout.addWidget(label)

        self.list_widget = QListWidget()
        for q in qualities:
            self.list_widget.addItem(str(q))
        self.list_widget.setCurrentRow(0)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("Download")
        btn_ok.clicked.connect(self._accept)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)

    def _accept(self):
        item = self.list_widget.currentItem()
        if item:
            self.selected_quality = item.text()
        self.accept()

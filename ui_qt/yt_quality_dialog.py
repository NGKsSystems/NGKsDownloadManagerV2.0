# ui_qt/yt_quality_dialog.py
"""
YouTube Quality Selection Dialog
Modal dialog shown before starting a YouTube download.
User picks quality preset and audio-only flag; get_options() returns
a dict consumable by adapter.start_download().
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QCheckBox,
    QPushButton,
)
from PySide6.QtCore import Qt

# Built-in quality presets (matches yt-dlp height filters)
_QUALITY_PRESETS = ["best", "1080", "720", "480", "360", "240"]


class YouTubeQualityDialog(QDialog):
    """Self-contained YouTube quality selector.

    Constructor requires NO external qualities list.
    Call ``exec()``; if accepted, ``get_options()`` returns a dict.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("YouTube Download Options")
        self.setModal(True)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)

        # --- Quality row ---
        layout.addWidget(QLabel("Video quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(_QUALITY_PRESETS)
        self.quality_combo.setCurrentText("best")
        layout.addWidget(self.quality_combo)

        # --- Extract-audio checkbox ---
        self.extract_audio_cb = QCheckBox("Extract audio only")
        layout.addWidget(self.extract_audio_cb)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_ok = QPushButton("Download")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_options(self) -> dict:
        """Return options dict after dialog is accepted.

        Keys:
            quality       (str)  – "best", "1080", "720", …
            auto_quality  (bool) – True when quality == "best"
            extract_audio (bool) – True when audio-only requested
        """
        quality = self.quality_combo.currentText()
        return {
            "quality": quality,
            "auto_quality": quality == "best",
            "extract_audio": self.extract_audio_cb.isChecked(),
        }

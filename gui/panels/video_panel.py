from PyQt5.QtWidgets import QGroupBox, QLabel, QVBoxLayout
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
import os

IMAGE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "shared", "latest_frame.jpg"
)

class VideoPanel(QGroupBox):
    def __init__(self, controller):
        super().__init__("Camera Preview")
        self.controller = controller

        self.label = QLabel("No Image")
        self.label.setFixedSize(640, 480)
        self.label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

    def refresh_image(self):
        if os.path.exists(IMAGE_PATH):
            pixmap = QPixmap(IMAGE_PATH)
            self.label.setPixmap(
                pixmap.scaled(
                    self.label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )

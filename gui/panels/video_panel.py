from PyQt5.QtWidgets import QGroupBox, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt

class VideoPanel(QGroupBox):
    def __init__(self):
        super().__init__("Camera / YOLO View")

        self.video_label = QLabel("Camera Stream")
        self.video_label.setFixedSize(640, 480)
        self.video_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        self.setLayout(layout)

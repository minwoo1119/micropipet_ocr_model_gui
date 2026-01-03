from PyQt5.QtWidgets import QGroupBox, QLabel, QPushButton, QVBoxLayout
from PyQt5.QtCore import Qt


class VideoPanel(QGroupBox):
    def __init__(self, controller):
        super().__init__("Camera Preview")
        self.controller = controller

        self.video_label = QLabel("No Frame")
        self.video_label.setFixedSize(640, 480)
        self.video_label.setAlignment(Qt.AlignCenter)

        self.btn_capture = QPushButton("Capture Frame")
        self.btn_capture.clicked.connect(self.capture_frame)

        layout = QVBoxLayout()
        layout.addWidget(self.video_label)
        layout.addWidget(self.btn_capture)
        self.setLayout(layout)

    def capture_frame(self):
        self.controller.capture_frame()
        self.video_label.setText("Frame Captured (preview later)")

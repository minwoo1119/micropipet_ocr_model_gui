import subprocess
import os
from PyQt5.QtWidgets import QGroupBox, QPushButton, QHBoxLayout

class YoloPanel(QGroupBox):
    def __init__(self):
        super().__init__("YOLO Object Detection")

        self.project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))
        )
        self.worker = os.path.join(self.project_root, "worker", "worker.py")

        btn_detect = QPushButton("YOLO 인식 시작")
        btn_redetect = QPushButton("재인식")

        btn_detect.clicked.connect(self.start_yolo)
        btn_redetect.clicked.connect(self.redetect_yolo)

        layout = QHBoxLayout()
        layout.addWidget(btn_detect)
        layout.addWidget(btn_redetect)
        self.setLayout(layout)

    def start_yolo(self):
        subprocess.Popen([
            "conda", "run", "-n", "pipet_env",
            "python", self.worker, "--yolo"
        ])

    def redetect_yolo(self):
        subprocess.Popen([
            "conda", "run", "-n", "pipet_env",
            "python", self.worker, "--yolo", "--reset"
        ])

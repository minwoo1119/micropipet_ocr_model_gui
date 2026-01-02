import subprocess
import os
from PyQt5.QtWidgets import (
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QComboBox, QHBoxLayout
)

class MotorTestPanel(QGroupBox):
    def __init__(self):
        super().__init__("Motor Test")

        self.project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))
        )
        self.worker = os.path.join(self.project_root, "worker", "worker.py")

        self.dir_box = QComboBox()
        self.dir_box.addItems(["CW", "CCW"])

        self.power = QLineEdit("50")
        self.time = QLineEdit("2.0")

        btn_run = QPushButton("▶ 테스트 실행")
        btn_run.clicked.connect(self.run_test)

        layout = QHBoxLayout()
        layout.addWidget(QLabel("방향"))
        layout.addWidget(self.dir_box)
        layout.addWidget(QLabel("세기"))
        layout.addWidget(self.power)
        layout.addWidget(QLabel("시간"))
        layout.addWidget(self.time)
        layout.addWidget(btn_run)

        self.setLayout(layout)

    def run_test(self):
        subprocess.Popen([
            "conda", "run", "-n", "pipet_env",
            "python", self.worker,
            "--motor-test",
            "--dir", self.dir_box.currentText(),
            "--power", self.power.text(),
            "--time", self.time.text()
        ])

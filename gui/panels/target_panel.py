import subprocess
import os
from PyQt5.QtWidgets import QGroupBox, QLabel, QLineEdit, QPushButton, QHBoxLayout

class TargetPanel(QGroupBox):
    def __init__(self):
        super().__init__("Target Dispensing Control")

        self.project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))
        )
        self.worker = os.path.join(self.project_root, "worker", "worker.py")

        self.target_input = QLineEdit("120")
        btn_run = QPushButton("▶ 목표 도달 실행")

        btn_run.clicked.connect(self.run_target)

        layout = QHBoxLayout()
        layout.addWidget(QLabel("목표 분주량"))
        layout.addWidget(self.target_input)
        layout.addWidget(btn_run)

        self.setLayout(layout)

    def run_target(self):
        subprocess.Popen([
            "conda", "run", "-n", "pipet_env",
            "python", self.worker,
            "--target", self.target_input.text()
        ])

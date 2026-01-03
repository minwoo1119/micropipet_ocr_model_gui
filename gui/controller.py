import subprocess
import os
from PyQt5.QtCore import QTimer

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

class Controller:
    def __init__(self):
        self.video_panel = None  # MainWindow에서 주입됨

    def capture_frame(self):
        """카메라 프레임 1장 캡처"""
        subprocess.Popen([
            "conda", "run", "-n", "pipet_env",
            "python",
            os.path.join(PROJECT_ROOT, "worker", "capture_frame.py")
        ])

        # 0.5초 후 GUI 이미지 갱신
        if self.video_panel:
            QTimer.singleShot(500, self.video_panel.refresh_image)

    def run_yolo(self):
        """YOLO 객체 인식 (프레임 1장 기준)"""
        subprocess.Popen([
            "conda", "run", "-n", "pipet_env",
            "python",
            os.path.join(PROJECT_ROOT, "worker", "yolo_worker.py")
        ])

        if self.video_panel:
            QTimer.singleShot(500, self.video_panel.refresh_image)

    def motor_test(self, direction, strength, duration):
        subprocess.Popen([
            "conda", "run", "-n", "pipet_env",
            "python",
            os.path.join(PROJECT_ROOT, "worker", "motor_test.py"),
            str(direction), str(strength), str(duration)
        ])

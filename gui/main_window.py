from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from worker.serial_controller import SerialController
from gui.controller import Controller
from gui.panels.video_panel import VideoPanel
from gui.panels.yolo_panel import YoloPanel
from gui.panels.target_panel import TargetPanel
from gui.panels.pipette_panel import PipettePanel


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Pipette Integrated Control (GUI = single serial session)"
        )
        self.resize(1100, 1050)

        # ===============================
        # ✅ SerialController 단 1회 생성
        # ===============================
        self.serial = SerialController(
            port="/dev/ttyUSB0",
            baudrate=115200,
        )
        self.serial.connect()

        # ===============================
        # ✅ Controller에 serial 주입
        # ===============================
        self.controller = Controller(self.serial)

        # ---------- Panels ----------
        self.video_panel = VideoPanel(self.controller)
        self.yolo_panel = YoloPanel(self.controller, self.video_panel)
        self.target_panel = TargetPanel(self.controller)
        self.pipette_panel = PipettePanel(self.controller)

        # ---------- Right side ----------
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.yolo_panel)
        right_layout.addWidget(self.target_panel)
        right_layout.addWidget(self.pipette_panel)
        right_layout.addStretch(1)

        # ---------- Main layout ----------
        main_layout = QHBoxLayout()
        main_layout.addWidget(self.video_panel)
        main_layout.addLayout(right_layout)

        main_layout.setStretch(0, 3)
        main_layout.setStretch(1, 2)

        self.setLayout(main_layout)

    def closeEvent(self, event):
        """GUI 종료 시 시리얼 정리"""
        try:
            self.serial.close()
        except Exception:
            pass
        event.accept()

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from gui.controller import Controller
from gui.panels.video_panel import VideoPanel
from gui.panels.yolo_panel import YoloPanel
from gui.panels.target_panel import TargetPanel
from gui.panels.pipette_panel import PipettePanel


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            "Pipette Integrated Control (GUI=system python, Worker=conda)"
        )
        self.resize(1100, 1050)

        self.controller = Controller()

        # ---------- Panels ----------
        self.video_panel = VideoPanel(self.controller)
        self.yolo_panel = YoloPanel(self.controller, self.video_panel)
        self.target_panel = TargetPanel(self.controller)
        self.pipette_panel = PipettePanel(self.controller)

        # ---------- Right side (stacked) ----------
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.yolo_panel)
        right_layout.addWidget(self.target_panel)
        right_layout.addWidget(self.pipette_panel)
        right_layout.addStretch(1)  # 아래 여백

        # ---------- Main layout ----------
        main_layout = QHBoxLayout()
        main_layout.addWidget(self.video_panel)
        main_layout.addLayout(right_layout)

        # 좌우 비율 조정 (선택)
        main_layout.setStretch(0, 3)  # VideoPanel
        main_layout.setStretch(1, 2)  # Right panels

        self.setLayout(main_layout)

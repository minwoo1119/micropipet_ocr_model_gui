from PyQt5.QtWidgets import QWidget, QVBoxLayout

from gui.controller import Controller
from gui.panels.video_panel import VideoPanel
from gui.panels.yolo_panel import YoloPanel
from gui.panels.target_panel import TargetPanel
from gui.panels.motor_test_panel import MotorTestPanel


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pipette Integrated Control (GUI=system python, Worker=conda)")
        self.resize(860, 980)

        self.controller = Controller()

        layout = QVBoxLayout()

        self.video_panel = VideoPanel(self.controller)
        self.yolo_panel = YoloPanel(self.controller, self.video_panel)
        self.target_panel = TargetPanel(self.controller)
        self.motor_test_panel = MotorTestPanel(self.controller)

        layout.addWidget(self.video_panel)
        layout.addWidget(self.yolo_panel)
        layout.addWidget(self.target_panel)
        layout.addWidget(self.motor_test_panel)

        self.setLayout(layout)

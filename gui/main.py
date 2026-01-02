# system python
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout

from panels.video_panel import VideoPanel
from panels.yolo_panel import YoloPanel
from panels.target_panel import TargetPanel
from panels.motor_test_panel import MotorTestPanel

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pipette Integrated Control")

        layout = QVBoxLayout()

        self.video_panel = VideoPanel()
        self.yolo_panel = YoloPanel()
        self.target_panel = TargetPanel()
        self.motor_test_panel = MotorTestPanel()

        layout.addWidget(self.video_panel)
        layout.addWidget(self.yolo_panel)
        layout.addWidget(self.target_panel)
        layout.addWidget(self.motor_test_panel)

        self.setLayout(layout)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

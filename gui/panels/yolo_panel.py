from PyQt5.QtWidgets import QGroupBox, QPushButton, QVBoxLayout


class YoloPanel(QGroupBox):
    def __init__(self, controller):
        super().__init__("YOLO Object Detection")
        self.controller = controller

        self.btn_detect = QPushButton("Detect Objects")
        self.btn_reset = QPushButton("Re-detect / Reset")

        self.btn_detect.clicked.connect(self.controller.run_yolo)
        self.btn_reset.clicked.connect(self.controller.reset_yolo)

        layout = QVBoxLayout()
        layout.addWidget(self.btn_detect)
        layout.addWidget(self.btn_reset)
        self.setLayout(layout)

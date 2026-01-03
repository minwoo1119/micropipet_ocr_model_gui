from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout,
    QComboBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QLabel
)


class MotorTestPanel(QGroupBox):
    def __init__(self, controller):
        super().__init__("Motor Test")
        self.controller = controller

        self.dir_box = QComboBox()
        self.dir_box.addItems(["CW", "CCW"])

        self.power_box = QSpinBox()
        self.power_box.setRange(0, 100)
        self.power_box.setValue(50)

        self.time_box = QDoubleSpinBox()
        self.time_box.setRange(0.1, 10.0)
        self.time_box.setValue(1.0)

        self.btn_test = QPushButton("Run Motor Test")
        self.btn_test.clicked.connect(self.run_test)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Direction"))
        layout.addWidget(self.dir_box)
        layout.addWidget(QLabel("Power"))
        layout.addWidget(self.power_box)
        layout.addWidget(QLabel("Duration (s)"))
        layout.addWidget(self.time_box)
        layout.addWidget(self.btn_test)
        self.setLayout(layout)

    def run_test(self):
        self.controller.motor_test(
            direction=self.dir_box.currentText(),
            power=self.power_box.value(),
            duration=self.time_box.value()
        )

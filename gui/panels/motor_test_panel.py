from PyQt5.QtWidgets import (
    QGroupBox, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QSpinBox, QComboBox
)


class MotorTestPanel(QGroupBox):
    def __init__(self, controller):
        super().__init__("Motor Test")

        self.controller = controller

        self.dir_combo = QComboBox()
        self.dir_combo.addItem("0 (Increase)", 0)
        self.dir_combo.addItem("1 (Decrease)", 1)

        self.str_spin = QSpinBox()
        self.str_spin.setRange(0, 100)
        self.str_spin.setValue(30)

        self.dur_spin = QSpinBox()
        self.dur_spin.setRange(1, 5000)
        self.dur_spin.setValue(200)

        self.btn_run = QPushButton("⚙ Run Motor")
        self.btn_run.clicked.connect(self.on_run)

        self.status = QLabel("Status: Idle")
        self.status.setWordWrap(True)

        row = QHBoxLayout()
        row.addWidget(QLabel("Direction:"))
        row.addWidget(self.dir_combo)
        row.addWidget(QLabel("Strength:"))
        row.addWidget(self.str_spin)
        row.addWidget(QLabel("Duration(ms):"))
        row.addWidget(self.dur_spin)
        row.addStretch(1)
        row.addWidget(self.btn_run)

        layout = QVBoxLayout()
        layout.addLayout(row)
        layout.addWidget(self.status)
        self.setLayout(layout)

    def on_run(self):
        d = int(self.dir_combo.currentData())
        s = int(self.str_spin.value())
        t = int(self.dur_spin.value())
        res = self.controller.motor_test(d, s, t)
        if not res.ok:
            self.status.setText("Status: Motor test failed (check terminal).")
            return
        self.status.setText(f"Status: sent d={d}, s={s}, t={t}ms")

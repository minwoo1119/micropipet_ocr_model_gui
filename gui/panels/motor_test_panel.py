from PyQt5.QtWidgets import (
    QGroupBox, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QSpinBox, QComboBox
)
from PyQt5.QtCore import QTimer


class MotorTestPanel(QGroupBox):
    def __init__(self, controller):
        super().__init__("Motor Test")

        self.controller = controller
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.on_auto_stop)

        # ---------------- UI ----------------
        self.dir_combo = QComboBox()
        self.dir_combo.addItem("Increase (dir=0)", 0)
        self.dir_combo.addItem("Decrease (dir=1)", 1)

        self.str_spin = QSpinBox()
        self.str_spin.setRange(0, 100)
        self.str_spin.setValue(30)

        self.dur_spin = QSpinBox()
        self.dur_spin.setRange(1, 5000)
        self.dur_spin.setValue(200)

        self.btn_run = QPushButton("▶ Run")
        self.btn_run.clicked.connect(self.on_run)

        self.btn_stop = QPushButton("■ Stop")
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_stop.setEnabled(False)

        self.status = QLabel("Status: Idle")
        self.status.setWordWrap(True)

        # ---------------- Layout ----------------
        row = QHBoxLayout()
        row.addWidget(QLabel("Direction"))
        row.addWidget(self.dir_combo)
        row.addWidget(QLabel("Duty"))
        row.addWidget(self.str_spin)
        row.addWidget(QLabel("Hold Time (ms)"))
        row.addWidget(self.dur_spin)
        row.addStretch(1)
        row.addWidget(self.btn_run)
        row.addWidget(self.btn_stop)

        layout = QVBoxLayout()
        layout.addLayout(row)
        layout.addWidget(self.status)
        self.setLayout(layout)

    # ---------------- Logic ----------------
    def on_run(self):
        direction = int(self.dir_combo.currentData())
        duty = int(self.str_spin.value())
        duration = int(self.dur_spin.value())

        self.status.setText(
            f"Running motor: dir={direction}, duty={duty}, hold={duration}ms"
        )

        res = self.controller.motor_test(direction, duty, duration)
        if not res.ok:
            self.status.setText("Motor test failed (check terminal logs).")
            return

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)

        # GUI 타이머로 자동 stop
        self.timer.start(duration)

    def on_stop(self):
        self.timer.stop()
        self.controller.motor_stop()

        self.status.setText("Motor stopped manually.")
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def on_auto_stop(self):
        self.controller.motor_stop()

        self.status.setText("Motor stopped (auto).")
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

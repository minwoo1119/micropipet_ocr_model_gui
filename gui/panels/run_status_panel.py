from PyQt5.QtWidgets import (
    QGroupBox, QLabel, QVBoxLayout, QGridLayout
)
from PyQt5.QtCore import QTimer


class RunStatusPanel(QGroupBox):
    def __init__(self, controller):
        super().__init__("Run-To-Target Status")

        self.controller = controller

        # ---------- Labels ----------
        self.lbl_status = QLabel("Idle")
        self.lbl_step = QLabel("-")
        self.lbl_target = QLabel("----")
        self.lbl_current = QLabel("----")
        self.lbl_error = QLabel("0")
        self.lbl_direction = QLabel("-")
        self.lbl_duty = QLabel("0")

        grid = QGridLayout()
        grid.addWidget(QLabel("Status"), 0, 0)
        grid.addWidget(self.lbl_status, 0, 1)

        grid.addWidget(QLabel("Step"), 1, 0)
        grid.addWidget(self.lbl_step, 1, 1)

        grid.addWidget(QLabel("Target"), 2, 0)
        grid.addWidget(self.lbl_target, 2, 1)

        grid.addWidget(QLabel("Current"), 3, 0)
        grid.addWidget(self.lbl_current, 3, 1)

        grid.addWidget(QLabel("Error"), 4, 0)
        grid.addWidget(self.lbl_error, 4, 1)

        grid.addWidget(QLabel("Direction"), 5, 0)
        grid.addWidget(self.lbl_direction, 5, 1)

        grid.addWidget(QLabel("Duty"), 6, 0)
        grid.addWidget(self.lbl_duty, 6, 1)

        layout = QVBoxLayout()
        layout.addLayout(grid)
        self.setLayout(layout)

        # ---------- Timer ----------
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(200)  # 5 Hz 갱신

    def refresh(self):
        s = self.controller.run_state

        self.lbl_status.setText(s["status"])
        self.lbl_step.setText(str(s["step"]))
        self.lbl_target.setText(f"{s['target']:04d}")
        self.lbl_current.setText(f"{s['current']:04d}")
        self.lbl_error.setText(f"{s['error']:+d}")
        self.lbl_direction.setText(
            s["direction"] if s["direction"] else "-"
        )
        self.lbl_duty.setText(str(s["duty"]))

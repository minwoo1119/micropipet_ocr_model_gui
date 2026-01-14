from PyQt5.QtWidgets import (
    QGroupBox, QLabel, QVBoxLayout, QGridLayout
)
from PyQt5.QtCore import Qt


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

        # (선택) 숫자 정렬 예쁘게
        for lbl in (
            self.lbl_step,
            self.lbl_target,
            self.lbl_current,
            self.lbl_error,
            self.lbl_duty,
        ):
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        grid = QGridLayout()
        grid.addWidget(QLabel("Status"),    0, 0)
        grid.addWidget(self.lbl_status,     0, 1)

        grid.addWidget(QLabel("Step"),      1, 0)
        grid.addWidget(self.lbl_step,       1, 1)

        grid.addWidget(QLabel("Target"),    2, 0)
        grid.addWidget(self.lbl_target,     2, 1)

        grid.addWidget(QLabel("Current"),   3, 0)
        grid.addWidget(self.lbl_current,    3, 1)

        grid.addWidget(QLabel("Error"),     4, 0)
        grid.addWidget(self.lbl_error,      4, 1)

        grid.addWidget(QLabel("Direction"), 5, 0)
        grid.addWidget(self.lbl_direction,  5, 1)

        grid.addWidget(QLabel("Duty"),      6, 0)
        grid.addWidget(self.lbl_duty,       6, 1)

        layout = QVBoxLayout()
        layout.addLayout(grid)
        self.setLayout(layout)

        # =========================================
        # 🔥 Controller Signal 연결 (핵심)
        # =========================================
        if hasattr(controller, "run_state_updated"):
            controller.run_state_updated.connect(self.on_state_updated)

    # =================================================
    # 🔥 Signal Slot (매 루프마다 호출됨)
    # =================================================
    def on_state_updated(self, s: dict):
        """
        Controller.run_state_updated Signal 슬롯
        """

        self.lbl_status.setText(s.get("status", ""))
        self.lbl_step.setText(str(s.get("step", "-")))
        self.lbl_target.setText(f"{s.get('target', 0):04d}")
        self.lbl_current.setText(f"{s.get('current', 0):04d}")
        self.lbl_error.setText(f"{s.get('error', 0):+d}")

        direction = s.get("direction", None)
        if direction is None:
            self.lbl_direction.setText("-")
        else:
            self.lbl_direction.setText(
                "CCW" if direction == 1 else "CW"
            )

        self.lbl_duty.setText(str(s.get("duty", 0)))

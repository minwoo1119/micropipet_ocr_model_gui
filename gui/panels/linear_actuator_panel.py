from PyQt5.QtWidgets import (
    QGroupBox, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QSpinBox, QComboBox
)


class LinearActuatorPanel(QGroupBox):
    """
    Linear Actuator Control Panel

    - 흡인 / 분주  : UP / DOWN 버튼
    - 팁 교체     : UP / DOWN 버튼
    - 용량 조절   : position 입력 + Move
    """

    def __init__(self, controller):
        super().__init__("Linear Actuator Control")

        self.controller = controller

        # =========================
        # Actuator mode selector
        # =========================
        self.act_combo = QComboBox()
        self.act_combo.addItem("흡인 / 분주", "pipetting")
        self.act_combo.addItem("팁 교체", "tip")
        self.act_combo.addItem("용량 조절 (Linear)", "volume")
        self.act_combo.currentIndexChanged.connect(self.on_act_changed)

        # =========================
        # Buttons
        # =========================
        self.btn_up = QPushButton("▲ UP")
        self.btn_down = QPushButton("▼ DOWN")
        self.btn_move = QPushButton("Move")

        self.btn_up.clicked.connect(self.on_up)
        self.btn_down.clicked.connect(self.on_down)
        self.btn_move.clicked.connect(self.on_move)

        # =========================
        # Position input (only for volume linear)
        # =========================
        self.pos_spin = QSpinBox()
        self.pos_spin.setRange(0, 65535)
        self.pos_spin.setValue(0)

        # =========================
        # Status
        # =========================
        self.status = QLabel("Status: Idle")
        self.status.setWordWrap(True)

        # =========================
        # Layout
        # =========================
        top = QHBoxLayout()
        top.addWidget(QLabel("Mode"))
        top.addWidget(self.act_combo)
        top.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_up)
        btn_row.addWidget(self.btn_down)
        btn_row.addWidget(QLabel("Position"))
        btn_row.addWidget(self.pos_spin)
        btn_row.addWidget(self.btn_move)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addLayout(btn_row)
        layout.addWidget(self.status)

        self.setLayout(layout)

        # 초기 UI 상태 반영
        self.on_act_changed()

    # =================================================
    # UI mode switching
    # =================================================
    def on_act_changed(self):
        mode = self.act_combo.currentData()

        is_volume = (mode == "volume")

        # volume linear → position 입력 ON
        self.pos_spin.setVisible(is_volume)
        self.btn_move.setVisible(is_volume)

        # pipetting / tip → up/down 버튼 ON
        self.btn_up.setVisible(not is_volume)
        self.btn_down.setVisible(not is_volume)

        self.status.setText(f"Status: Mode = {mode}")

    # =================================================
    # Button handlers
    # =================================================
    def on_up(self):
        mode = self.act_combo.currentData()

        if mode == "pipetting":
            res = self.controller.pipetting_up()
            label = "흡인 / 분주 상승"

        elif mode == "tip":
            res = self.controller.tip_change_up()
            label = "팁 교체 상승"

        else:
            return

        if not res.ok:
            self.status.setText(f"{label} 실패 (터미널 확인)")
            return

        self.status.setText(f"{label} 실행")

    def on_down(self):
        mode = self.act_combo.currentData()

        if mode == "pipetting":
            res = self.controller.pipetting_down()
            label = "흡인 / 분주 하강"

        elif mode == "tip":
            res = self.controller.tip_change_down()
            label = "팁 교체 하강"

        else:
            return

        if not res.ok:
            self.status.setText(f"{label} 실패 (터미널 확인)")
            return

        self.status.setText(f"{label} 실행")

    def on_move(self):
        pos = int(self.pos_spin.value())

        res = self.controller.volume_linear_move(pos)
        if not res.ok:
            self.status.setText("용량 조절 이동 실패 (터미널 확인)")
            return

        self.status.setText(f"용량 Linear 이동 → position={pos}")

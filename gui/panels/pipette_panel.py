from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt

from gui.controller import Controller
from worker.actuator_volume_dc import VolumeDCActuator


class PipettePanel(QWidget):
    """
    C# Form1 Pipette / End-Effector FULL panel (1:1 대응)
    """

    def __init__(self, controller: Controller, parent=None):
        super().__init__(parent)

        self.controller = controller

        # ===== Volume Rotary DC motor =====
        self.volume_dc = VolumeDCActuator(
            serial=self.controller.serial,
            actuator_id=0x0C,
        )

        self._build_ui()

    # ==========================================================
    # UI
    # ==========================================================
    def _build_ui(self):
        main = QVBoxLayout(self)

        main.addWidget(QLabel("<b>Pipette / End-Effector Control</b>"))

        # ======================================================
        # Linear Down Control (흡인/팁/볼륨 하강)
        # ======================================================
        down_box = QGroupBox("Linear Motor - Down")
        down_layout = QHBoxLayout(down_box)

        btn_pip_down = QPushButton("흡인분주 하강")
        btn_pip_down.clicked.connect(self.controller.pipetting_down)

        btn_tip_down = QPushButton("팁 교체 하강")
        btn_tip_down.clicked.connect(self.controller.tip_change_down)

        btn_vol_down = QPushButton("용량 조절 하강")
        btn_vol_down.clicked.connect(
            lambda: self.controller.linear_move(actuator_id=0x0A, position=0)
        )

        down_layout.addWidget(btn_pip_down)
        down_layout.addWidget(btn_tip_down)
        down_layout.addWidget(btn_vol_down)

        main.addWidget(down_box)

        # ======================================================
        # Linear Move (목표 위치 이동)
        # ======================================================
        move_box = QGroupBox("Linear Motor - Move To Position")
        grid = QGridLayout(move_box)

        self.tb_pip_pos = QLineEdit()
        self.tb_tip_pos = QLineEdit()
        self.tb_vol_pos = QLineEdit()

        grid.addWidget(QLabel("흡인분주 목표"), 0, 0)
        grid.addWidget(self.tb_pip_pos, 0, 1)
        grid.addWidget(
            self._btn("흡인분주 이동",
                      lambda: self._linear_move(0x08, self.tb_pip_pos)),
            0, 2
        )

        grid.addWidget(QLabel("팁 교체 목표"), 1, 0)
        grid.addWidget(self.tb_tip_pos, 1, 1)
        grid.addWidget(
            self._btn("팁 교체 이동",
                      lambda: self._linear_move(0x09, self.tb_tip_pos)),
            1, 2
        )

        grid.addWidget(QLabel("용량 조절 목표"), 2, 0)
        grid.addWidget(self.tb_vol_pos, 2, 1)
        grid.addWidget(
            self._btn("용량 조절 이동",
                      lambda: self._linear_move(0x0A, self.tb_vol_pos)),
            2, 2
        )

        main.addWidget(move_box)

        # ======================================================
        # Rotary Volume Control (중공축 DC 모터)
        # ======================================================
        rotary_box = QGroupBox("Volume Rotary Motor")
        rotary_layout = QVBoxLayout(rotary_box)

        duty_layout = QHBoxLayout()
        duty_layout.addWidget(QLabel("Duty"))
        self.tb_duty = QLineEdit("40")
        duty_layout.addWidget(self.tb_duty)

        rotary_layout.addLayout(duty_layout)

        btn_row = QHBoxLayout()

        btn_cw = QPushButton("CW")
        btn_ccw = QPushButton("CCW")
        btn_stop = QPushButton("정지")

        btn_cw.pressed.connect(lambda: self._rotary_start(direction=1))
        btn_cw.released.connect(self.volume_dc.stop)

        btn_ccw.pressed.connect(lambda: self._rotary_start(direction=0))
        btn_ccw.released.connect(self.volume_dc.stop)

        btn_stop.clicked.connect(self.volume_dc.stop)

        btn_row.addWidget(btn_cw)
        btn_row.addWidget(btn_stop)
        btn_row.addWidget(btn_ccw)

        rotary_layout.addLayout(btn_row)
        main.addWidget(rotary_box)

        main.addStretch(1)

    # ==========================================================
    # Helpers
    # ==========================================================
    def _btn(self, text, cb):
        b = QPushButton(text)
        b.clicked.connect(cb)
        return b

    def _linear_move(self, actuator_id: int, edit: QLineEdit):
        try:
            pos = int(edit.text())
            self.controller.linear_move(actuator_id, pos)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _rotary_start(self, direction: int):
        try:
            duty = int(self.tb_duty.text())
            self.volume_dc.run(direction=direction, duty=duty)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

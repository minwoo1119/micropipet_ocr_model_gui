from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QGroupBox,
)
from PyQt5.QtCore import Qt, QTimer

from gui.controller import Controller


class PipettePanel(QWidget):
    """
    Pipette DC motor panel
    C# GUI 구조 1:1 대응
    (VolumeDCActuator API 기준)
    """

    TIMER_MS = 50  # C# DispatcherTimer 주기

    def __init__(self, controller: Controller, parent=None):
        super().__init__(parent)

        self.controller = controller
        self.volume_dc = controller.volume_dc

        self.duty = 40
        self.direction = None  # 1 or 0 or None

        self.timer = QTimer(self)
        self.timer.setInterval(self.TIMER_MS)
        self.timer.timeout.connect(self._on_timer)

        self._build_ui()

    # -------------------------------------------------
    # UI
    # -------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Pipette Control (C# identical)</b>"))

        # =====================
        # Duty
        # =====================
        duty_box = QGroupBox("Duty (%)")
        duty_layout = QVBoxLayout(duty_box)

        self.duty_slider = QSlider(Qt.Horizontal)
        self.duty_slider.setRange(0, 100)
        self.duty_slider.setValue(self.duty)
        self.duty_slider.valueChanged.connect(self._on_duty_change)

        self.duty_label = QLabel(f"{self.duty} %")

        duty_layout.addWidget(self.duty_slider)
        duty_layout.addWidget(self.duty_label)

        layout.addWidget(duty_box)

        # =====================
        # Control buttons
        # =====================
        ctrl_box = QGroupBox("Pipette")
        ctrl_layout = QVBoxLayout(ctrl_box)

        btn_asp = QPushButton("Aspirate (Hold)")
        btn_disp = QPushButton("Dispense (Hold)")

        btn_asp.pressed.connect(lambda: self._start(1))
        btn_asp.released.connect(self._stop)

        btn_disp.pressed.connect(lambda: self._start(0))
        btn_disp.released.connect(self._stop)

        ctrl_layout.addWidget(btn_asp)
        ctrl_layout.addWidget(btn_disp)

        layout.addWidget(ctrl_box)

        # =====================
        # STOP
        # =====================
        btn_stop = QPushButton("STOP")
        btn_stop.setStyleSheet("background-color:red;color:white;")
        btn_stop.clicked.connect(self._stop)
        layout.addWidget(btn_stop)

        layout.addStretch(1)

    # -------------------------------------------------
    # Logic (C# identical)
    # -------------------------------------------------
    def _on_duty_change(self, value: int):
        self.duty = value
        self.duty_label.setText(f"{value} %")

    def _start(self, direction: int):
        self.direction = direction
        if not self.timer.isActive():
            self.timer.start()

    def _stop(self):
        self.timer.stop()
        self.direction = None
        self.volume_dc.stop()

    def _on_timer(self):
        """
        50ms마다 동일 명령 반복 송신
        """
        if self.direction is None:
            return

        if self.direction == 1:
            self.volume_dc.increase(self.duty)
        else:
            self.volume_dc.decrease(self.duty)

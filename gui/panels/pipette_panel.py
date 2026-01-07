from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QLineEdit,
    QGroupBox,
    QMessageBox,
)
from PyQt5.QtCore import Qt

from gui.controller import Controller


class PipettePanel(QWidget):
    """
    Pipette control panel (PyQt5)
    C# GUI 버튼 구조 그대로 대응
    Controller 중심 구조
    """

    def __init__(self, controller: Controller, parent=None):
        super().__init__(parent)

        # -----------------------------
        # Controller / Actuator binding
        # -----------------------------
        self.controller = controller
        self.volume_dc = controller.volume_dc  # 핵심 수정 포인트

        # Parameters
        self.duty = 40
        self.duration = 800  # ms

        self._build_ui()

    # -------------------------------------------------
    # UI
    # -------------------------------------------------
    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        main_layout.addWidget(QLabel("<b>Pipette Control Panel</b>"))

        # =====================
        # Parameters
        # =====================
        param_box = QGroupBox("Parameters")
        param_layout = QVBoxLayout(param_box)

        # Duty
        param_layout.addWidget(QLabel("Duty (%)"))
        self.duty_slider = QSlider(Qt.Horizontal)
        self.duty_slider.setRange(0, 100)
        self.duty_slider.setValue(self.duty)
        self.duty_slider.valueChanged.connect(self._on_duty_change)
        param_layout.addWidget(self.duty_slider)

        self.duty_label = QLabel(f"{self.duty} %")
        param_layout.addWidget(self.duty_label)

        # Duration
        param_layout.addWidget(QLabel("Duration (ms)"))
        self.duration_edit = QLineEdit(str(self.duration))
        param_layout.addWidget(self.duration_edit)

        main_layout.addWidget(param_box)

        # =====================
        # Aspirate / Dispense
        # =====================
        io_box = QGroupBox("Aspirate / Dispense")
        io_layout = QVBoxLayout(io_box)

        btn_asp = QPushButton("Aspirate")
        btn_asp.clicked.connect(lambda: self._run(direction=1))
        io_layout.addWidget(btn_asp)

        btn_disp = QPushButton("Dispense")
        btn_disp.clicked.connect(lambda: self._run(direction=0))
        io_layout.addWidget(btn_disp)

        main_layout.addWidget(io_box)

        # =====================
        # Volume Adjust
        # =====================
        vol_box = QGroupBox("Volume Adjust")
        vol_layout = QVBoxLayout(vol_box)

        btn_plus = QPushButton("Volume +")
        btn_plus.clicked.connect(lambda: self._run(direction=1))
        vol_layout.addWidget(btn_plus)

        btn_minus = QPushButton("Volume -")
        btn_minus.clicked.connect(lambda: self._run(direction=0))
        vol_layout.addWidget(btn_minus)

        main_layout.addWidget(vol_box)

        # =====================
        # Tip Control
        # =====================
        tip_box = QGroupBox("Tip Control")
        tip_layout = QVBoxLayout(tip_box)

        btn_attach = QPushButton("Tip Attach")
        btn_attach.clicked.connect(lambda: self._run(direction=1))
        tip_layout.addWidget(btn_attach)

        btn_detach = QPushButton("Tip Detach")
        btn_detach.clicked.connect(lambda: self._run(direction=0))
        tip_layout.addWidget(btn_detach)

        main_layout.addWidget(tip_box)

        # =====================
        # STOP
        # =====================
        btn_stop = QPushButton("STOP")
        btn_stop.clicked.connect(self.volume_dc.stop)
        btn_stop.setStyleSheet("background-color: red; color: white;")
        main_layout.addWidget(btn_stop)

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _on_duty_change(self, value: int):
        self.duty = value
        self.duty_label.setText(f"{value} %")

    def _run(self, direction: int):
        try:
            duration = int(self.duration_edit.text())

            if duration <= 0:
                raise ValueError("Duration must be > 0")

            self.volume_dc.run_for(
                direction=direction,
                duty=self.duty,
                duration_ms=duration,
            )

        except Exception as e:
            QMessageBox.critical(self, "Invalid Parameter", str(e))

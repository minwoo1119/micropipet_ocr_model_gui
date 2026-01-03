from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QLineEdit, QPushButton, QLabel


class TargetPanel(QGroupBox):
    def __init__(self, controller):
        super().__init__("Target Volume Control")
        self.controller = controller

        self.input_target = QLineEdit()
        self.input_target.setPlaceholderText("Target volume (uL)")

        self.btn_move = QPushButton("Move to Target")
        self.btn_move.clicked.connect(self.move_to_target)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Target Volume"))
        layout.addWidget(self.input_target)
        layout.addWidget(self.btn_move)
        self.setLayout(layout)

    def move_to_target(self):
        try:
            target = float(self.input_target.text())
            self.controller.move_to_target(target)
        except ValueError:
            print("[TargetPanel] Invalid target input")

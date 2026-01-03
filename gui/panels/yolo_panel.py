import json
from PyQt5.QtWidgets import QGroupBox, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit


class YoloPanel(QGroupBox):
    def __init__(self, controller, video_panel):
        super().__init__("YOLO ROI Detection (4 boxes)")

        self.controller = controller
        self.video_panel = video_panel

        self.btn_detect = QPushButton("Detect ROIs")
        self.btn_reset  = QPushButton("Re-Detect (reset)")

        self.btn_detect.clicked.connect(self.on_detect)
        self.btn_reset.clicked.connect(self.on_reset)

        self.roi_text = QTextEdit()
        self.roi_text.setReadOnly(True)
        self.roi_text.setFixedHeight(120)

        top = QHBoxLayout()
        top.addWidget(self.btn_detect)
        top.addWidget(self.btn_reset)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(QLabel("Detected ROIs (x,y,w,h):"))
        layout.addWidget(self.roi_text)
        self.setLayout(layout)

    def _run(self, reset: bool):
        cam = int(self.video_panel.camera_spin.value())
        res = self.controller.yolo_detect(reset=reset, camera_index=cam)
        if not res.ok:
            self.roi_text.setPlainText("YOLO failed.\nCheck terminal logs.")
            return

        rois = res.data.get("rois", [])
        self.roi_text.setPlainText(json.dumps(rois, indent=2, ensure_ascii=False))

        annotated = res.data.get("annotated_path", "")
        if annotated:
            self.video_panel.show_image(annotated)

    def on_detect(self):
        print("[GUI] YOLO detect button clicked")
        self._run(reset=False)

    def on_reset(self):
        self._run(reset=True)

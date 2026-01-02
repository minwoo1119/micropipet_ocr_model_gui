pipet_gui/
├── main.py
├── requirements.txt
│
├── ui/
│   └── main_window.py
│
├── vision/
│   ├── camera.py
│   ├── yolo.py
│   └── ocr_trt.py
│
├── control/
│   ├── serial_ctrl.py
│   ├── motor.py
│   └── pi_control.py
│
├── models/
│   ├── yolo/
│   │   └── best_rotate_yolo.pt
│   └── trt/
│       └── efficientnet_b0_fp16_dynamic.trt
│
└── assets/
    └── README.md

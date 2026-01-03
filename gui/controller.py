class Controller:
    def __init__(self):
        print("[Controller] Initialized")

    # ===== Camera =====
    def capture_frame(self):
        print("[Controller] Capture single frame")
        # TODO: cv2.VideoCapture로 1프레임 캡처
        return None

    # ===== YOLO =====
    def run_yolo(self):
        print("[Controller] Run YOLO detection")

    def reset_yolo(self):
        print("[Controller] Reset YOLO")

    # ===== Target volume control =====
    def move_to_target(self, target_ul: float):
        print(f"[Controller] Move to target: {target_ul} uL")

    # ===== Motor test =====
    def motor_test(self, direction: str, power: int, duration: float):
        print(f"[Controller] Motor test → dir={direction}, power={power}, time={duration}s")

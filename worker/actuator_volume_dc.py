import time
from worker.serial_controller import SerialController


class VolumeDCActuator:
    """
    Geared DC motor for pipette volume change
    (C# GEAREDDCMOTOR 동일 개념)
    """

    def __init__(
        self,
        serial: SerialController,
        actuator_id: int,
    ):
        self.serial = serial
        self.actuator_id = actuator_id

    # -------------------------------------------------
    # C# ChangeVolume 대응 (🔥 핵심 추가)
    # -------------------------------------------------
    def change(self, direction: int, duty: int):
        """
        direction : 0 / 1
        duty      : 0 ~ 100
        """
        direction = 0 if int(direction) <= 0 else 1
        duty = max(0, min(100, int(duty)))

        self.serial.send_pipette_change_volume(
            actuator_id=self.actuator_id,
            direction=direction,
            duty=duty,
        )

    # -------------------------------------------------
    # High-level helpers (기존)
    # -------------------------------------------------
    def increase(self, duty: int):
        self.change(direction=1, duty=duty)

    def decrease(self, duty: int):
        self.change(direction=0, duty=duty)

    def stop(self):
        self.change(direction=0, duty=0)

    def run_for(self, direction: int, duty: int, duration_ms: int):
        self.change(direction, duty)
        time.sleep(duration_ms / 1000.0)
        self.stop()

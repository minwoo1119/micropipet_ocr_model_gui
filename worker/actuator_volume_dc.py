import time
from worker.serial_controller import SerialController
import threading


class VolumeDCActuator:
    """
    Geared DC motor for pipette volume change
    (based on CEO firmware: GEAREDDCMOTOR)
    """

    def __init__(
        self,
        serial: SerialController,
        actuator_id: int,
    ):
        self.serial = serial
        self.actuator_id = actuator_id

    # -------------------------------------------------
    # Basic motions (START only)
    # -------------------------------------------------
    def increase(self, duty: int):
        """
        Volume UP (CW in CEO UI)
        dir = 1
        """
        self.serial.send_pipette_change_volume(
            actuator_id=self.actuator_id,
            direction=1,
            duty=duty,
        )

    def decrease(self, duty: int):
        """
        Volume DOWN (CCW in CEO UI)
        dir = 0
        """
        self.serial.send_pipette_change_volume(
            actuator_id=self.actuator_id,
            direction=0,
            duty=duty,
        )

    def stop(self):
        """
        Stop motor (duty = 0)
        """
        self.serial.send_pipette_stop(self.actuator_id)

    # -------------------------------------------------
    # Timed helper (Python-side duration control)
    # -------------------------------------------------
    def run_for(self, direction: int, duty: int, duration_ms: int):
        def _worker():
            self.serial.send_pipette_change_volume(
                actuator_id=self.actuator_id,
                direction=direction,
                duty=duty,
            )
            time.sleep(duration_ms / 1000.0)
            self.stop()

        threading.Thread(target=_worker, daemon=True).start()
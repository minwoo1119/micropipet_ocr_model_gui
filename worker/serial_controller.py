import time
import serial
from typing import Optional

from worker.make_packet import MakePacket


class SerialController:
    # =========================
    # Init / Connection
    # =========================
    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 115200,
        timeout: float = 1.0,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

    def connect(self) -> bool:
        """
        Open serial port
        """
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
        )
        time.sleep(0.5)  # MCU boot / buffer settle
        return self.ser.is_open

    def close(self):
        """
        Close serial port
        """
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None

    def is_connected(self) -> bool:
        return self.ser is not None and self.ser.is_open

    # =========================
    # Internal send
    # =========================
    def _send(self, packet: bytes):
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port not open")

        print(f"[TX] {packet.hex()}")

        self.ser.write(packet)
        self.ser.flush()

    # =========================
    # MightyZap Linear Actuator
    # =========================
    def send_mightyzap_set_position(self, actuator_id: int, position: int):
        """
        MightyZap: Set Position
        C# : MIGHTYZAP_MakePacket_SetPosition
        """
        packet = MakePacket.set_position(
            id_=actuator_id,
            position=position,
        )
        self._send(packet)

    def send_mightyzap_set_speed(self, actuator_id: int, speed: int):
        """
        MightyZap: Set Speed
        C# : MIGHTYZAP_MakePacket_SetSpeed
        """
        packet = MakePacket.set_speed(
            id_=actuator_id,
            speed=speed,
        )
        self._send(packet)

    def send_mightyzap_set_current(self, actuator_id: int, current: int):
        """
        MightyZap: Set Current
        C# : MIGHTYZAP_MakePacket_SetCurrent
        """
        packet = MakePacket.set_current(
            id_=actuator_id,
            current=current,
        )
        self._send(packet)

    def send_mightyzap_force_onoff(self, actuator_id: int, onoff: int):
        """
        MightyZap: Force ON/OFF
        C# : MIGHTYZAP_MakePacket_SetForceOnOff
        """
        onoff = 1 if onoff else 0
        packet = MakePacket.set_force_onoff(
            id_=actuator_id,
            onoff=onoff,
        )
        self._send(packet)

    def send_mightyzap_get_moving(self, actuator_id: int):
        """
        MightyZap: Get Moving State
        C# : MIGHTYZAP_MakePacket_GetMoving
        """
        packet = MakePacket.get_moving(
            id_=actuator_id,
        )
        self._send(packet)

    def send_mightyzap_get_feedback(self, actuator_id: int):
        """
        MightyZap: Get Feedback Data
        C# : MIGHTYZAP_MakePacket_GetFeedbackData
        """
        packet = MakePacket.get_feedback(
            id_=actuator_id,
        )
        self._send(packet)

    # =========================
    # MyActuator (Absolute Angle)
    # =========================
    def send_myactuator_set_absolute_angle(
        self,
        actuator_id: int,
        speed: int,
        angle: int,
    ):
        """
        MyActuator: Set Absolute Angle
        C# : MYACTUATOR_makePacket_setAbsoluteAngle
        """
        packet = MakePacket.myactuator_set_absolute_angle(
            id_=actuator_id,
            speed=speed,
            angle=angle,
        )
        self._send(packet)

    def send_myactuator_get_absolute_angle(self, actuator_id: int):
        """
        MyActuator: Get Absolute Angle
        C# : MYACTUATOR_makePacket_getAbsoluteAngle
        """
        packet = MakePacket.myactuator_get_absolute_angle(
            id_=actuator_id,
        )
        self._send(packet)

    # =========================
    # Geared DC Motor (Pipette)
    # =========================
    def send_pipette_change_volume(
        self,
        actuator_id: int,
        direction: int,
        duty: int,
    ):
        """
        Geared DC Motor: Change Pipette Volume
        C# : GEAREDDCMOTOR_makePacket_ChangePipetteVolume

        direction : 0 / 1
        duty      : 0 ~ 100
        """
        direction = 0 if int(direction) <= 0 else 1
        duty = max(0, min(100, int(duty)))

        packet = MakePacket.pipette_change_volume(
            id_=actuator_id,
            direction=direction,
            duty=duty,
        )
        self._send(packet)

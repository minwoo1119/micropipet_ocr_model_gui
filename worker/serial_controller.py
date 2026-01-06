import time
import serial


class SerialController:
    """
    Serial controller for pipette motor
    Protocol based on CEO firmware:
    GEAREDDCMOTOR_makePacket_ChangePipetteVolume
    """

    # ---------- Protocol constants ----------
    HEADER1 = 0xEA
    HEADER2 = 0xEB
    ENDOFBYTE = 0xED

    CMD_CHANGE_VOLUME = 0xA1  # GEAREDDCMOTOR_makePacket_ChangePipetteVolume

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 115200,
        motor_id: int = 0x01,
    ):
        self.port = port
        self.baudrate = baudrate
        self.motor_id = motor_id
        self.ser: serial.Serial | None = None

    # -------------------------------------------------
    # Connection
    # -------------------------------------------------
    def connect(self) -> bool:
        self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
        time.sleep(0.5)  # MCU boot / buffer settle
        return self.ser.is_open

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None

    # -------------------------------------------------
    # Low-level helpers
    # -------------------------------------------------
    def _send_packet(self, packet: bytes):
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial not open")
        self.ser.write(packet)

    @staticmethod
    def _checksum(data: bytes) -> int:
        """
        checksum = 0xFF - (sum(data) % 256)
        """
        return (0xFF - (sum(data) % 256)) & 0xFF

    # -------------------------------------------------
    # Packet builders
    # -------------------------------------------------
    def make_change_volume_packet(self, direction: int, duty: int) -> bytes:
        """
        direction: 0 or 1
        duty: 0 ~ 100 (PWM duty)
        """

        direction = 0 if int(direction) <= 0 else 1
        duty = max(0, min(100, int(duty)))

        packet = bytearray(13)
        packet[0] = self.HEADER1
        packet[1] = self.HEADER2
        packet[2] = self.motor_id
        packet[3] = 0x07
        packet[4] = self.CMD_CHANGE_VOLUME
        packet[5] = direction
        packet[6] = duty
        packet[7] = 0x00
        packet[8] = 0x00
        packet[9] = 0x00
        packet[10] = 0x00

        packet[11] = self._checksum(packet[4:11])
        packet[12] = self.ENDOFBYTE

        return bytes(packet)

    # -------------------------------------------------
    # High-level API (used by workers)
    # -------------------------------------------------
    def run_motor(self, direction: int, duty: int):
        """
        Send volume-change command to motor.
        Duration is controlled by caller (Python sleep).
        """
        packet = self.make_change_volume_packet(direction, duty)
        self._send_packet(packet)

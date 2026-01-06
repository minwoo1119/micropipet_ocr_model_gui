import time
import serial
from typing import Optional


class SerialController:
    """
    Low-level serial controller.
    - ONLY responsible for packet creation & transmission
    - Protocol exactly follows CEO C# firmware
    """

    # =================================================
    # Protocol constants (common)
    # =================================================
    HEADER1 = 0xEA
    HEADER2 = 0xEB
    ENDOFBYTE = 0xED

    # =================================================
    # Command codes
    # =================================================
    # --- Geared DC Motor (Volume Change) ---
    CMD_CHANGE_VOLUME = 0xA1

    # --- MightyZap Linear ---
    CMD_MZ_SET_POSITION = 0x01

    # =================================================
    # Init / connection
    # =================================================
    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 115200,
    ):
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None

    def connect(self) -> bool:
        self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
        time.sleep(0.5)  # MCU boot / buffer settle
        return self.ser.is_open

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None

    # =================================================
    # Low-level helpers
    # =================================================
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

    # =================================================
    # Packet builder
    # =================================================
    def _build_packet(self, actuator_id: int, cmd: int, payload: bytes) -> bytes:
        """
        Generic packet builder (13 bytes fixed)
        """
        packet = bytearray(13)
        packet[0] = self.HEADER1
        packet[1] = self.HEADER2
        packet[2] = actuator_id
        packet[3] = 0x07
        packet[4] = cmd

        # payload (max 6 bytes)
        for i in range(6):
            packet[5 + i] = payload[i] if i < len(payload) else 0x00

        packet[11] = self._checksum(packet[4:11])
        packet[12] = self.ENDOFBYTE
        return bytes(packet)

    # =================================================
    # Public APIs (used by actuator classes)
    # =================================================

    # ---------- Geared DC Motor ----------
    def send_volume_dc(self, actuator_id: int, direction: int, duty: int):
        """
        direction: 0 / 1
        duty: 0 ~ 100
        """
        direction = 0 if int(direction) <= 0 else 1
        duty = max(0, min(100, int(duty)))

        payload = bytes([direction, duty])
        packet = self._build_packet(
            actuator_id=actuator_id,
            cmd=self.CMD_CHANGE_VOLUME,
            payload=payload,
        )
        self._send_packet(packet)

    # ---------- MightyZap Linear (low-level) ----------
    def send_linear_position(self, actuator_id: int, position: int):
        """
        position: ushort (0 ~ 65535)
        """
        pos = max(0, min(0xFFFF, int(position)))
        payload = bytes([
            pos & 0xFF,
            (pos >> 8) & 0xFF,
        ])
        packet = self._build_packet(
            actuator_id=actuator_id,
            cmd=self.CMD_MZ_SET_POSITION,
            payload=payload,
        )
        self._send_packet(packet)

    # ---------- MightyZap Linear (semantic alias) ----------
    def send_mightyzap_set_position(self, actuator_id: int, position: int):
        """
        Semantic wrapper for MightyZap SetPosition.
        Actuator classes should call THIS method.
        """
        self.send_linear_position(actuator_id, position)

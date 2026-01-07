from typing import ByteString


class MakePacket:
    # ===== Constants =====
    HEADER1 = 0xEA
    HEADER2 = 0xEB
    ENDOFBYTE = 0xED

    # ==============================
    # Command Codes (C# 기준)
    # ==============================
    MIGHTYZAP_SetPosition        = 0x01
    MIGHTYZAP_SetSpeed           = 0x02
    MIGHTYZAP_SetCurrent         = 0x03
    MIGHTYZAP_SetForceOnOff      = 0x04
    MIGHTYZAP_GetMovingState     = 0x05
    MIGHTYZAP_GetFeedbackData    = 0x07

    MyActuator_setAbsoluteAngle  = 0xA4
    MyActuator_getAbsoluteAngle  = 0x92

    GearedDC_changePipetteVolume = 0xA1

    # ==============================
    # Checksum (C# 동일)
    # ==============================
    @staticmethod
    def _checksum(packet: ByteString) -> int:
        checksum_raw = sum(packet[4:11])
        return (0xFF - (checksum_raw % 256)) & 0xFF

    # ==============================
    # Base Packet (13 bytes)
    # ==============================
    @staticmethod
    def _base_packet(id_: int, cmd: int, data: list[int]) -> bytes:
        packet = bytearray(13)
        packet[0] = MakePacket.HEADER1
        packet[1] = MakePacket.HEADER2
        packet[2] = id_              # ✅ actuator ID
        packet[3] = 0x07
        packet[4] = cmd              # ✅ command

        for i in range(6):
            packet[5 + i] = data[i] if i < len(data) else 0x00

        packet[11] = MakePacket._checksum(packet)
        packet[12] = MakePacket.ENDOFBYTE
        return bytes(packet)

    # ==============================
    # MightyZap
    # ==============================
    @staticmethod
    def set_position(id_: int, position: int) -> bytes:
        return MakePacket._base_packet(
            id_,
            MakePacket.MIGHTYZAP_SetPosition,
            [position & 0xFF, (position >> 8) & 0xFF]
        )

    @staticmethod
    def set_speed(id_: int, speed: int) -> bytes:
        return MakePacket._base_packet(
            id_,
            MakePacket.MIGHTYZAP_SetSpeed,
            [speed & 0xFF, (speed >> 8) & 0xFF]
        )

    @staticmethod
    def set_current(id_: int, current: int) -> bytes:
        return MakePacket._base_packet(
            id_,
            MakePacket.MIGHTYZAP_SetCurrent,
            [current & 0xFF, (current >> 8) & 0xFF]
        )

    @staticmethod
    def set_force_onoff(id_: int, onoff: int) -> bytes:
        return MakePacket._base_packet(
            id_,
            MakePacket.MIGHTYZAP_SetForceOnOff,
            [1 if onoff else 0]
        )

    @staticmethod
    def get_moving(id_: int) -> bytes:
        return MakePacket._base_packet(
            id_,
            MakePacket.MIGHTYZAP_GetMovingState,
            []
        )

    @staticmethod
    def get_feedback(id_: int) -> bytes:
        return MakePacket._base_packet(
            id_,
            MakePacket.MIGHTYZAP_GetFeedbackData,
            []
        )

    # ==============================
    # Status Polling (C# 동일)
    # ==============================
    @staticmethod
    def request_check_operate_status() -> bytes:
        packet = bytearray(13)
        packet[0] = MakePacket.HEADER1
        packet[1] = MakePacket.HEADER2
        packet[2] = 0xFF
        packet[3] = 0x07
        packet[4] = 0x01
        packet[5] = 0x02
        packet[6] = 0x03
        packet[7] = 0x04
        packet[8] = 0x05
        packet[9] = 0x06
        packet[10] = 0x07
        packet[11] = MakePacket._checksum(packet)
        packet[12] = MakePacket.ENDOFBYTE
        return bytes(packet)

    # ==============================
    # MyActuator
    # ==============================
    @staticmethod
    def myactuator_set_absolute_angle(id_: int, speed: int, angle: int) -> bytes:
        data = [
            speed & 0xFF,
            (speed >> 8) & 0xFF,
            angle & 0xFF,
            (angle >> 8) & 0xFF,
            (angle >> 16) & 0xFF,
            (angle >> 24) & 0xFF,
        ]
        return MakePacket._base_packet(
            id_,
            MakePacket.MyActuator_setAbsoluteAngle,
            data
        )

    @staticmethod
    def myactuator_get_absolute_angle(id_: int) -> bytes:
        return MakePacket._base_packet(
            id_,
            MakePacket.MyActuator_getAbsoluteAngle,
            []
        )

    # ==============================
    # Geared DC Motor (Pipette Volume)
    # ==============================
    @staticmethod
    def pipette_change_volume(id_: int, direction: int, duty: int) -> bytes:
        """
        id_    : 0x0C (메모 기준)
        direction : 0 = CCW, 1 = CW
        duty      : 0 ~ 100 (그대로 byte 전송)
        """
        direction = 1 if direction > 0 else 0
        duty = max(0, min(100, duty))

        return MakePacket._base_packet(
            id_,
            MakePacket.GearedDC_changePipetteVolume,
            [direction, duty]
        )

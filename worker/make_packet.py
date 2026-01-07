from typing import ByteString

class MakePacket:
    # ===== Constants =====
    HEADER1 = 0xEA
    HEADER2 = 0xEB
    ENDOFBYTE = 0xED

    WAIT_CMD = 0x00

    MIGHTYZAP_WAIT_COMMAND      = 0x00
    MIGHTYZAP_SetPosition       = 0x01
    MIGHTYZAP_SetSpeed          = 0x02
    MIGHTYZAP_SetCurrent        = 0x03
    MIGHTYZAP_SetForceOnOff     = 0x04
    MIGHTYZAP_GetMovingState    = 0x05
    MIGHTYZAP_GetFeedbackData   = 0x07

    # ==============================
    # 내부 공통 함수
    # ==============================
    @staticmethod
    def _checksum(packet: ByteString) -> int:
        """
        C#:
        for (int i = 4; i < 11; i++)
            checksumRaw += packet[i];
        checksum = 0xFF - (checksumRaw % 256)
        """
        checksum_raw = sum(packet[4:11])
        return (0xFF - (checksum_raw % 256)) & 0xFF

    @staticmethod
    def _base_packet(id_: int, cmd: int, data: list[int]) -> bytes:
        """
        공통 패킷 생성기 (13바이트 고정)
        """
        packet = bytearray(13)
        packet[0]  = MakePacket.HEADER1
        packet[1]  = MakePacket.HEADER2
        packet[2]  = id_
        packet[3]  = 0x07
        packet[4]  = cmd

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
            [
                position & 0xFF,
                (position >> 8) & 0xFF,
            ]
        )

    @staticmethod
    def set_speed(id_: int, speed: int) -> bytes:
        return MakePacket._base_packet(
            id_,
            MakePacket.MIGHTYZAP_SetSpeed,
            [
                speed & 0xFF,
                (speed >> 8) & 0xFF,
            ]
        )

    @staticmethod
    def set_current(id_: int, current: int) -> bytes:
        return MakePacket._base_packet(
            id_,
            MakePacket.MIGHTYZAP_SetCurrent,
            [
                current & 0xFF,
                (current >> 8) & 0xFF,
            ]
        )

    @staticmethod
    def set_force_onoff(id_: int, onoff: int) -> bytes:
        return MakePacket._base_packet(
            id_,
            MakePacket.MIGHTYZAP_SetForceOnOff,
            [onoff]
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
        packet = bytearray(13)
        packet[0] = MakePacket.HEADER1
        packet[1] = MakePacket.HEADER2
        packet[2] = id_
        packet[3] = 0x07
        packet[4] = 0xA4

        for i in range(6):
            packet[5 + i] = data[i]

        packet[11] = MakePacket._checksum(packet)
        packet[12] = MakePacket.ENDOFBYTE
        return bytes(packet)

    @staticmethod
    def myactuator_get_absolute_angle(id_: int) -> bytes:
        return MakePacket._base_packet(
            id_,
            0x92,
            []
        )

    # ==============================
    # Geared DC Motor (Pipette)
    # ==============================
    @staticmethod
    def pipette_change_volume(id_: int, direction: int, duty: int) -> bytes:
        
        duty_hex_encoded = int(f"{duty}", 16) & 0xFF
        return MakePacket._base_packet(
            id_,
            0xA1,
            [direction, duty_hex_encoded]
        )

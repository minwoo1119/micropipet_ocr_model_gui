import time
import serial
import threading
import queue

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
        device_id: int = 1,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.device_id = device_id

        self.ser: Optional[serial.Serial] = None

        # ===== C# 대응 제어 구조 =====
        self.tx_queue: queue.Queue[bytes] = queue.Queue()
        self.running: bool = False

        self._last_packet: Optional[bytes] = None


    # =========================
    # Connection
    # =========================
    def connect(self) -> bool:
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )

        time.sleep(0.5)  # MCU boot / buffer settle
        self.running = True

        # TX worker (C# CommThreadProc + 50ms Sleep 대응)
        threading.Thread(
            target=self._tx_worker,
            daemon=True,
        ).start()

        # RX debug worker
        threading.Thread(
            target=self._rx_worker,
            daemon=True,
        ).start()

        return self.ser.is_open

    def close(self):
        self.running = False
        time.sleep(0.1)

        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None

    def is_connected(self) -> bool:
        return self.ser is not None and self.ser.is_open


    # =========================
    # Internal send (QUEUE ONLY)
    # =========================
    def _send(self, packet: bytes):
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("Serial port not open")

        # 🔒 동일 패킷 연속 전송 방지
        if packet == self._last_packet:
            return

        self._last_packet = packet
        self.tx_queue.put(packet)
        print(f"[ENQUEUE] {packet.hex(' ')}")


    # =========================
    # TX Worker (50ms Tick)
    # =========================
    def _tx_worker(self):
        """
        ✔ 50ms 주기
        ✔ 큐에 있는 패킷만 전송
        """
        while self.running:
            try:
                packet = None

                if not self.tx_queue.empty():
                    packet = self.tx_queue.get()

                if packet is not None and self.ser and self.ser.is_open:
                    self.ser.write(packet)
                    print(f"[TX] {packet.hex(' ')}")

            except Exception as e:
                print("[TX ERROR]", e)

            time.sleep(0.05)


    # =========================
    # RX Worker (Debug / ACK 확인용)
    # =========================
    def _rx_worker(self):
        buffer = bytearray()

        while self.running:
            try:
                if self.ser and self.ser.in_waiting:
                    buffer += self.ser.read(self.ser.in_waiting)

                    while True:
                        if len(buffer) < 6:
                            break

                        if buffer[0] != 0xEA or buffer[1] != 0xEB:
                            buffer.pop(0)
                            continue

                        try:
                            end = buffer.index(0xED)
                        except ValueError:
                            break

                        frame = buffer[:end + 1]
                        buffer = buffer[end + 1:]

                        print(f"[RX FRAME] {frame.hex(' ')}")

            except Exception as e:
                print("[RX ERROR]", e)

            time.sleep(0.01)


    # =========================
    # MightyZap Linear Actuator
    # =========================
    def send_mightyzap_set_position(self, actuator_id: int, position: int):
        """
        ✔ C#과 동일: SetPosition ONLY
        """
        self._send(MakePacket.set_position(actuator_id, position))

    def send_mightyzap_set_speed(self, actuator_id: int, speed: int):
        self._send(MakePacket.set_speed(actuator_id, speed))

    def send_mightyzap_set_current(self, actuator_id: int, current: int):
        self._send(MakePacket.set_current(actuator_id, current))


    # =========================
    # MyActuator (Hollow Shaft)
    # =========================
    def send_myactuator_set_absolute_angle(
        self,
        actuator_id: int,
        speed: int,
        angle: int
    ):
        self._send(
            MakePacket.myactuator_set_absolute_angle(
                actuator_id, speed, angle
            )
        )


    # =========================
    # Geared DC Motor (Volume)
    # =========================
    def send_pipette_change_volume(
        self,
        actuator_id: int,
        direction: int,
        duty: int
    ):
        direction = 0 if int(direction) <= 0 else 1
        duty = max(0, min(100, int(duty)))

        self._send(
            MakePacket.pipette_change_volume(
                actuator_id, direction, duty
            )
        )

    def send_pipette_stop(self, actuator_id: int):
        self._send(
            MakePacket.pipette_change_volume(actuator_id, 0, 0)
        )

    def send_mightyzap_force_onoff(self, actuator_id: int, onoff: int):
        self._send(MakePacket.set_force_onoff(actuator_id, 1 if onoff else 0))


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

        # status 주기 제어
        self._last_status_time = 0.0
        self._status_interval = 0.2  # 200ms (idle 상태에서만)


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

        # 단일 TX 워커만 사용 (C# Timer 역할)
        threading.Thread(
            target=self._tx_worker,
            daemon=True,
        ).start()

        # (선택) RX 로그용 – 있으면 디버깅에 도움
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

        self.tx_queue.put(packet)
        print(f"[ENQUEUE] {packet.hex(' ')}")


    # =========================
    # TX Worker (Single 50ms Tick)
    # =========================
    def _tx_worker(self):
        """
        C# Timer.Interval = 50ms 구조 대응
        - 명령 우선
        - idle 시에만 status 1개 전송
        """
        while self.running:
            try:
                packet = None

                # 1️⃣ 명령 우선
                if not self.tx_queue.empty():
                    packet = self.tx_queue.get()

                # 2️⃣ idle 상태에서만 status polling
                else:
                    now = time.time()
                    if now - self._last_status_time >= self._status_interval:
                        packet = MakePacket.request_check_operate_status()
                        self._last_status_time = now

                if packet is not None and self.ser and self.ser.is_open:
                    self.ser.write(packet)
                    print(f"[TX] {packet.hex(' ')}")

            except Exception as e:
                print("[TX ERROR]", e)

            time.sleep(0.05)  # ★ 단일 50ms Tick


    # =========================
    # RX Worker (debug / ACK 확인용)
    # =========================
    def _rx_worker(self):
        buffer = bytearray()

        while self.running:
            try:
                if self.ser and self.ser.in_waiting:
                    buffer += self.ser.read(self.ser.in_waiting)

                    while True:
                        # 최소 프레임 길이
                        if len(buffer) < 6:
                            break

                        # 헤더 찾기
                        if buffer[0] != 0xEA or buffer[1] != 0xEB:
                            buffer.pop(0)
                            continue

                        # 푸터 찾기 (ED)
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
        self._send(MakePacket.set_position(actuator_id, position))

    def send_mightyzap_set_speed(self, actuator_id: int, speed: int):
        self._send(MakePacket.set_speed(actuator_id, speed))

    def send_mightyzap_set_current(self, actuator_id: int, current: int):
        self._send(MakePacket.set_current(actuator_id, current))

    def send_mightyzap_force_onoff(self, actuator_id: int, onoff: int):
        self._send(MakePacket.set_force_onoff(actuator_id, 1 if onoff else 0))

    def send_mightyzap_get_moving(self, actuator_id: int):
        self._send(MakePacket.get_moving(actuator_id))

    def send_mightyzap_get_feedback(self, actuator_id: int):
        self._send(MakePacket.get_feedback(actuator_id))


    # =========================
    # MyActuator
    # =========================
    def send_myactuator_set_absolute_angle(self, actuator_id: int, speed: int, angle: int):
        self._send(MakePacket.myactuator_set_absolute_angle(actuator_id, speed, angle))

    def send_myactuator_get_absolute_angle(self, actuator_id: int):
        self._send(MakePacket.myactuator_get_absolute_angle(actuator_id))


    # =========================
    # Geared DC Motor (Pipette)
    # =========================
    def send_pipette_change_volume(self, actuator_id: int, direction: int, duty: int):
        direction = 0 if int(direction) <= 0 else 1
        duty = max(0, min(100, int(duty)))
        self._send(MakePacket.pipette_change_volume(actuator_id, direction, duty))

    def send_pipette_stop(self, actuator_id: int):
        self._send(MakePacket.pipette_change_volume(actuator_id, 0, 0))

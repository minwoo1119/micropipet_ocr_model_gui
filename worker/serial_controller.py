import time
import threading
import queue
from typing import Optional

import serial

from worker.make_packet import MakePacket


class SerialController:
    """
    - poll 완전 OFF
    - TX: 50ms tick로 큐에서 1개씩 전송
    - RX: length 기반 프레임 파싱 (LEN + 6)
    """

    MAX_QUEUE = 50          # 🔥 3이면 GUI에서 연속 클릭할 때 너무 쉽게 DROP됨
    TX_TICK_SEC = 0.05      # 50ms

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 115200,
        timeout: float = 0.05,   # 🔥 RX가 빨라야 응답을 잘 본다
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

        self.ser: Optional[serial.Serial] = None
        self.running: bool = False

        self.tx_queue: "queue.Queue[bytes]" = queue.Queue()

        # 디버그
        self.rx_debug: bool = True
        self.tx_debug: bool = True

    # =========================
    # Connection
    # =========================
    def connect(self) -> bool:
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            write_timeout=0.2,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            rtscts=False,
            dsrdtr=False,
        )

        # 버퍼 초기화 (중요)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        time.sleep(0.2)
        self.running = True

        threading.Thread(target=self._tx_worker, daemon=True).start()
        threading.Thread(target=self._rx_worker, daemon=True).start()

        return self.ser.is_open

    def close(self):
        self.running = False
        time.sleep(0.05)
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        finally:
            self.ser = None

    # =========================
    # ENQUEUE
    # =========================
    def enqueue(self, packet: bytes):
        if not self.ser or not self.ser.is_open:
            print("[ENQUEUE] serial not open, skip")
            return

        if self.tx_queue.qsize() >= self.MAX_QUEUE:
            print(f"[DROP] queue full({self.tx_queue.qsize()}) {packet.hex(' ')}")
            return

        self.tx_queue.put(packet)
        if self.tx_debug:
            print(f"[ENQUEUE] {packet.hex(' ')}")

    # =========================
    # TX Worker
    # =========================
    def _tx_worker(self):
        while self.running:
            try:
                if self.ser and self.ser.is_open:
                    try:
                        packet = self.tx_queue.get_nowait()
                    except queue.Empty:
                        packet = None

                    if packet:
                        self.ser.write(packet)
                        self.ser.flush()
                        if self.tx_debug:
                            print(f"[TX] {packet.hex(' ')}")

            except Exception as e:
                print("[TX ERROR]", e)

            time.sleep(self.TX_TICK_SEC)

    # =========================
    # RX Worker (LEN 기반)
    # =========================
    def _rx_worker(self):
        buf = bytearray()

        while self.running:
            try:
                if not (self.ser and self.ser.is_open):
                    time.sleep(0.01)
                    continue

                n = self.ser.in_waiting
                if n:
                    chunk = self.ser.read(n)
                    if not chunk:
                        # 이게 뜨면 보통 포트 다중접속/케이블/전원 문제
                        # 또는 timeout 설정 꼬임
                        time.sleep(0.01)
                        continue

                    buf += chunk

                # 프레임 파싱: EA EB | ID | LEN | ... (LEN bytes) | CHK | ED
                while True:
                    if len(buf) < 6:
                        break

                    # 헤더 정렬
                    if not (buf[0] == 0xEA and buf[1] == 0xEB):
                        buf.pop(0)
                        continue

                    length = buf[3]
                    frame_len = int(length) + 6  # ✅ 핵심

                    if len(buf) < frame_len:
                        break

                    frame = bytes(buf[:frame_len])
                    del buf[:frame_len]

                    if self.rx_debug:
                        print(f"[RX] {frame.hex(' ')}")

            except Exception as e:
                print("[RX ERROR]", e)

            time.sleep(0.005)

    # =========================
    # High-level APIs
    # =========================
    def send_mightyzap_set_position(self, actuator_id: int, position: int):
        self.enqueue(MakePacket.set_position(actuator_id, position))

    def send_mightyzap_set_speed(self, actuator_id: int, speed: int):
        self.enqueue(MakePacket.set_speed(actuator_id, speed))

    def send_mightyzap_set_current(self, actuator_id: int, current: int):
        self.enqueue(MakePacket.set_current(actuator_id, current))

    def send_mightyzap_force_onoff(self, actuator_id: int, onoff: int):
        self.enqueue(MakePacket.set_force_onoff(actuator_id, 1 if onoff else 0))

    def send_pipette_change_volume(self, actuator_id: int, direction: int, duty: int):
        direction = 0 if int(direction) <= 0 else 1
        duty = max(0, min(100, int(duty)))
        self.enqueue(MakePacket.pipette_change_volume(actuator_id, direction, duty))

    def send_pipette_stop(self, actuator_id: int):
        self.enqueue(MakePacket.pipette_change_volume(actuator_id, 0, 0))

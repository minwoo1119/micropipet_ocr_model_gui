import time
import threading
import queue
from typing import Optional, Dict

import serial
import termios

from worker.make_packet import MakePacket


class SerialController:
    MAX_QUEUE = 50

    STX1 = 0xEA
    STX2 = 0xEB
    ETX  = 0xED

    HEADER_SIZE = 5   # EA EB ID LEN CMD
    MIN_FRAME   = 8   # header + checksum + ETX

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 115200,
        timeout: float = 0.05,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

        self.ser: Optional[serial.Serial] = None
        self.running: bool = False

        self.tx_queue: "queue.Queue[bytes]" = queue.Queue()

        self.states: Dict[int, Dict] = {}
        self._state_lock = threading.Lock()

        self.rx_buffer = bytearray()

        self.rx_debug = True
        self.tx_debug = True

    # =========================
    # Connection
    # =========================
    def connect(self) -> bool:
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            write_timeout=None,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )

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
        if self.ser and self.ser.is_open:
            self.ser.close()

    # =========================
    # TX
    # =========================
    def enqueue(self, packet: bytes):
        if not (self.ser and self.ser.is_open):
            return

        if self.tx_queue.qsize() >= self.MAX_QUEUE:
            return

        self.tx_queue.put(packet)

        if self.tx_debug:
            print(f"[ENQUEUE] {packet.hex(' ')}")

    def _tx_worker(self):
        while self.running:
            try:
                packet = self.tx_queue.get(timeout=0.1)

                self.ser.write(packet)
                self.ser.flush()
                termios.tcdrain(self.ser.fileno())

                if self.tx_debug:
                    print(f"[TX] {packet.hex(' ')}")

                time.sleep(0.003)

            except queue.Empty:
                pass
            except Exception as e:
                print("[TX ERROR]", e)

    # =========================
    # RX Worker (✔ C# 동일 구조)
    # =========================
    def _rx_worker(self):
        while self.running:
            try:
                n = self.ser.in_waiting
                if n:
                    self.rx_buffer += self.ser.read(n)

                self._process_rx_buffer()

            except Exception as e:
                print("[RX ERROR]", e)

            time.sleep(0.001)

    # =========================
    # RX Parser (완성본)
    # =========================
    def _process_rx_buffer(self):
        while True:
            if len(self.rx_buffer) < self.MIN_FRAME:
                return

            # STX 동기화
            if not (self.rx_buffer[0] == self.STX1 and self.rx_buffer[1] == self.STX2):
                self.rx_buffer.pop(0)
                continue

            length = self.rx_buffer[3]
            frame_len = self.HEADER_SIZE + length + 2  # checksum + ETX

            if len(self.rx_buffer) < frame_len:
                return

            frame = bytes(self.rx_buffer[:frame_len])

            if frame[-1] != self.ETX:
                self.rx_buffer.pop(0)
                continue

            if not self._check_checksum(frame):
                self.rx_buffer.pop(0)
                continue

            del self.rx_buffer[:frame_len]

            if self.rx_debug:
                print(f"[RX] {frame.hex(' ')}")

            self._handle_frame(frame)

    # =========================
    # Checksum (C# 동일)
    # =========================
    def _check_checksum(self, frame: bytes) -> bool:
        checksum = 0
        for b in frame[:-2]:   # ETX, checksum 제외
            checksum ^= b
        return checksum == frame[-2]

    # =========================
    # Frame Handler
    # =========================
    def _handle_frame(self, frame: bytes):
        actuator_id = frame[2]
        response_type = frame[4]

        if response_type != 0x11:
            return

        moving = frame[8]

        with self._state_lock:
            self.states[actuator_id] = {
                "moving": moving,
                "timestamp": time.time(),
                "raw": frame,
            }

    # =========================
    # High-level APIs
    # =========================
    def move_and_wait(self, actuator_id: int, position: int, timeout: float = 5.0) -> bool:
        self.enqueue(MakePacket.set_position(actuator_id, position))

        start = time.time()

        while time.time() - start < timeout:
            self.enqueue(MakePacket.get_moving(actuator_id))

            with self._state_lock:
                st = self.states.get(actuator_id)

            if st and st["moving"] == 0:
                return True

            time.sleep(0.05)

        raise TimeoutError("Move timeout")


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
        direction = 1 if direction > 0 else 0
        duty = max(0, min(100, duty))
        self.enqueue(MakePacket.pipette_change_volume(actuator_id, direction, duty))

    def send_pipette_stop(self, actuator_id: int):
        self.enqueue(MakePacket.pipette_change_volume(actuator_id, 0, 0))

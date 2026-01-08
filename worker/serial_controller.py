import time
import threading
import queue
from typing import Optional, Dict

import serial

from worker.make_packet import MakePacket


class SerialController:
    """
    ✔ Windows(C#) MightyZap 제어와 동작 1:1 동일
    ✔ poll OFF
    ✔ SetPosition + GetMoving polling
    ✔ 자동 RS485 대응 (TX → RX 전환 보장)
    """

    MAX_QUEUE = 50

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

        # MightyZap 상태 (C# struct 대응)
        self.states: Dict[int, Dict] = {}
        self._state_lock = threading.Lock()

        # 디버그
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
            write_timeout=None,  # 🔥 중요: write block 허용
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            rtscts=False,
            dsrdtr=False,
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
        self.ser = None

    def is_connected(self) -> bool:
        return self.ser is not None and self.ser.is_open

    # =========================
    # TX enqueue
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
    # TX Worker (C# Write() 동일)
    # =========================
    def _tx_worker(self):
        """
        ✔ Windows(C#) SerialPort.Write() 와 1:1 동작
        ✔ write → flush → tcdrain 보장
        ✔ RS485 자동 방향 전환 안정화
        """
        import termios

        while self.running:
            try:
                # 큐에서 패킷 대기 (busy loop 방지)
                packet = self.tx_queue.get(timeout=0.1)

                if not (self.ser and self.ser.is_open):
                    continue

                self.ser.write(packet)
                self.ser.flush()

                termios.tcdrain(self.ser.fileno())

                if self.tx_debug:
                    print(f"[TX] {packet.hex(' ')}")

                time.sleep(0.003)

            except queue.Empty:
                # 전송할 게 없으면 자연스럽게 대기
                pass
            except Exception as e:
                print("[TX ERROR]", e)


    # =========================
    # RX Worker (END BYTE 기반)
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
                    buf += self.ser.read(n)

                while True:
                    if len(buf) < 13:
                        break

                    if buf[0] != 0xEA or buf[1] != 0xEB:
                        buf.pop(0)
                        continue

                    try:
                        end_idx = buf.index(0xED)
                    except ValueError:
                        break

                    frame = bytes(buf[:end_idx + 1])
                    del buf[:end_idx + 1]

                    if self.rx_debug:
                        print(f"[RX] {frame.hex(' ')}")

                    self._handle_frame(frame)

            except Exception as e:
                print("[RX ERROR]", e)

            time.sleep(0.002)

    # =========================
    # RX Frame Handler (C# 동일)
    # =========================
    def _handle_frame(self, frame: bytes):
        if len(frame) < 12:
            return

        actuator_id = frame[2]
        response_type = frame[4]

        # MightyZap status response
        if response_type != 0x11:
            return

        # 로그 기준 moving flag = frame[8]
        moving = frame[8]

        with self._state_lock:
            self.states[actuator_id] = {
                "moving": moving,
                "timestamp": time.time(),
                "raw": frame,
            }

    # =========================
    # C#과 동일한 move_and_wait
    # =========================
    def move_and_wait(
        self,
        actuator_id: int,
        position: int,
        timeout: float = 5.0,
    ) -> bool:
        """
        C# 로직:
            SetPosition()
            while(GetMoving()) sleep
        """
        self.send_mightyzap_set_position(actuator_id, position)

        start = time.time()

        while time.time() - start < timeout:
            self.enqueue(MakePacket.get_moving(actuator_id))

            with self._state_lock:
                st = self.states.get(actuator_id)

            if st and st.get("moving") == 0:
                return True

            time.sleep(0.05)

        raise TimeoutError(f"MightyZap {hex(actuator_id)} move timeout")

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

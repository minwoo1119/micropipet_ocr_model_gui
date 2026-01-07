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
        self._poll_step: int = 0
        self._last_enq: float = 0.0
        self._min_gap_sec: float = 0.015  # 15ms
        self._max_queue: int = 3


    # =========================
    # Connection
    # =========================
    def connect(self) -> bool:
        """
        Open serial port and start workers
        """
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

        # 송신 워커 (50ms 주기)
        threading.Thread(
            target=self._tx_worker,
            daemon=True,
        ).start()

        # 상태 체크 워커 (keep-alive)
        threading.Thread(
            target=self._status_worker,
            daemon=True,
        ).start()

        return self.ser.is_open

    def close(self):
        """
        Stop workers and close serial port
        """
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

        # C#과 동일: 바로 write ❌, 큐에 적재 ⭕
        print(f"[ENQUEUE] {packet.hex(' ')}")
        self.tx_queue.put(packet)

    # =========================
    # TX Worker (50ms loop)
    # =========================
    def _tx_worker(self):
        """
        C# Thread.Sleep(50) 송신 루프 대응
        """
        while self.running:
            # ⚠️ C#과 동일하게: "50ms마다 1번"만 시도
            try:
                packet = self.tx_queue.get_nowait()
            except queue.Empty:
                packet = None

            if packet is not None:
                try:
                    if self.ser and self.ser.is_open:
                        # flush()는 일부 환경에서 지연을 크게 만들어서 제거
                        self.ser.write(packet)
                        print(f"[TX] {packet.hex(' ')}")
                except Exception as e:
                    print("[TX ERROR]", e)

            time.sleep(0.05)  # ★ 50ms 고정


    # =========================
    # Status Worker (keep-alive)
    # =========================
    def _status_worker(self):
        """
        C# mightyZap_Data_Tick 로직 대응:
        - 큐가 쌓이면 더 생산하지 않음
        - 최소 간격 보장
        - 한 번에 딱 1개만 넣는 라운드로빈
        """
        while self.running:
            try:
                if not (self.ser and self.ser.is_open):
                    time.sleep(0.2)
                    continue

                # 1) 큐가 쌓이면 더 생산하지 않음 (지연 누적 방지)
                if self.tx_queue.qsize() >= self._max_queue:
                    time.sleep(0.02)
                    continue

                # 2) 너무 빠른 루프면 최소 간격 보장
                now = time.time()
                if now - self._last_enq < self._min_gap_sec:
                    time.sleep(0.01)
                    continue

                # 3) 한 번에 "딱 1개"만 넣기 (라운드로빈)
                if self._poll_step == 0:
                    pkt = MakePacket.request_check_operate_status()
                    self.tx_queue.put(pkt)
                elif self._poll_step == 1:
                    # 필요 시: selected actuator feedback 폴링 추가 가능
                    pass
                elif self._poll_step == 2:
                    # 필요 시: myactuator angle 폴링 추가 가능
                    pass

                self._poll_step = (self._poll_step + 1) % 3
                self._last_enq = now

            except Exception as e:
                print("[STATUS ERROR]", e)

            time.sleep(0.05)


    # =========================
    # MightyZap Linear Actuator
    # =========================
    def send_mightyzap_set_position(self, actuator_id: int, position: int):
        packet = MakePacket.set_position(
            id_=actuator_id,
            position=position,
        )
        self._send(packet)

    def send_mightyzap_set_speed(self, actuator_id: int, speed: int):
        packet = MakePacket.set_speed(
            id_=actuator_id,
            speed=speed,
        )
        self._send(packet)

    def send_mightyzap_set_current(self, actuator_id: int, current: int):
        packet = MakePacket.set_current(
            id_=actuator_id,
            current=current,
        )
        self._send(packet)

    def send_mightyzap_force_onoff(self, actuator_id: int, onoff: int):
        onoff = 1 if onoff else 0
        packet = MakePacket.set_force_onoff(
            id_=actuator_id,
            onoff=onoff,
        )
        self._send(packet)

    def send_mightyzap_get_moving(self, actuator_id: int):
        packet = MakePacket.get_moving(
            id_=actuator_id,
        )
        self._send(packet)

    def send_mightyzap_get_feedback(self, actuator_id: int):
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
        packet = MakePacket.myactuator_set_absolute_angle(
            id_=actuator_id,
            speed=speed,
            angle=angle,
        )
        self._send(packet)

    def send_myactuator_get_absolute_angle(self, actuator_id: int):
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
        direction : 0 / 1
        duty      : 0 ~ 100 (C#과 동일하게 HEX 재해석은 MakePacket에서 처리)
        """
        direction = 0 if int(direction) <= 0 else 1
        duty = max(0, min(100, int(duty)))

        packet = MakePacket.pipette_change_volume(
            id_=actuator_id,
            direction=direction,
            duty=duty,
        )
        self._send(packet)
        
    def send_pipette_stop(self, actuator_id: int):
        """
        DC Motor STOP
        C#에서 duty=0을 보내던 역할
        """
        packet = MakePacket.pipette_change_volume(
            id_=actuator_id,
            direction=0,
            duty=0,
        )
        self._send(packet)
        
    def run_pipette_for(
        self,
        actuator_id: int,
        direction: int,
        duty: int,
        duration_sec: float,
    ):
        """
        DC Motor를 일정 시간 동안만 동작시키는 함수
        (START → wait → STOP)
        """

        self.send_pipette_change_volume(
            actuator_id=actuator_id,
            direction=direction,
            duty=duty,
        )

        time.sleep(duration_sec)

        self.send_pipette_stop(actuator_id)



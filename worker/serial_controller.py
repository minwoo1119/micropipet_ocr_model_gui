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
            try:
                packet = self.tx_queue.get(timeout=0.05)

                if self.ser and self.ser.is_open:
                    self.ser.write(packet)
                    self.ser.flush()
                    print(f"[TX] {packet.hex(' ')}")

            except queue.Empty:
                pass
            except Exception as e:
                print("[TX ERROR]", e)

            time.sleep(0.05)  # ★ 핵심

    # =========================
    # Status Worker (keep-alive)
    # =========================
    def _status_worker(self):
        """
        C#에서 주기적으로 보내던 상태 체크 패킷
        """
        while self.running:
            try:
                pkt = MakePacket.get_moving(self.device_id)
                self.tx_queue.put(pkt)
            except Exception as e:
                print("[STATUS ERROR]", e)

            time.sleep(0.2)  # 200ms 주기

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



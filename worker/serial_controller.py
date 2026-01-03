import time
import serial


class SerialController:
    def __init__(self, port="/dev/ttyUSB0", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None

    def connect(self):
        self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
        time.sleep(0.5)
        return self.ser.isOpen()

    def close(self):
        if self.ser and self.ser.isOpen():
            self.ser.close()

    def send_motor_command(self, direction: int, strength: int, duration_ms: int):
        if self.ser is None or not self.ser.isOpen():
            raise RuntimeError("Serial not open")

        direction = 0 if int(direction) <= 0 else 1
        strength = max(0, min(100, int(strength)))
        duration_ms = max(1, int(duration_ms))

        cmd = f"${direction},{strength},{duration_ms}#"
        self.ser.write(cmd.encode("utf-8"))

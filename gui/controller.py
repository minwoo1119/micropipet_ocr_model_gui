import json
import time
import os
import subprocess
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

from worker.serial_controller import SerialController
from worker.actuator_linear import LinearActuator
from worker.actuator_volume_dc import VolumeDCActuator


@dataclass
class WorkerResult:
    ok: bool
    data: Dict[str, Any]
    raw: str


class Controller:
    """
    ✔ Vision / OCR / Run-to-target : subprocess (conda 유지)
    ✔ Linear actuator              : GUI process + SerialController
    ✔ DC motor                     : GUI process + SerialController
    """

    # ==============================
    # Init
    # ==============================
    def __init__(self, conda_env: str = "pipet_env"):
        self.conda_env = conda_env
        self.root_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )

        self.long_proc: Optional[subprocess.Popen] = None

        # ------------------------------
        # Serial (GUI 생명주기 동안 1개)
        # ------------------------------
        self.serial = SerialController("/dev/ttyUSB0")
        self.serial.connect()

        # ------------------------------
        # Linear actuators
        # ------------------------------
        self.pipetting_linear = LinearActuator(self.serial, 0x0B)
        self.volume_linear = LinearActuator(self.serial, 0x0A)

        # ------------------------------
        # Volume DC motor
        # ------------------------------
        self.volume_dc = VolumeDCActuator(self.serial, 0x0C)

        # ------------------------------
        # MightyZap 초기화 (C# 동일)
        # ------------------------------
        for aid in (0x0B, 0x0A):
            self.serial.send_mightyzap_force_onoff(aid, 1)
            time.sleep(0.1)
            self.serial.send_mightyzap_set_speed(aid, 500)
            time.sleep(0.1)
            self.serial.send_mightyzap_set_current(aid, 300)
            time.sleep(0.1)
            self.serial.send_mightyzap_set_position(aid, 300)
            time.sleep(0.1)

    # =================================================
    # Worker runner (Vision / OCR)
    # =================================================
    def _run_worker(
        self,
        args: List[str],
        timeout: Optional[int] = 120,
    ) -> WorkerResult:

        cmd = [
            "conda", "run", "-n", self.conda_env,
            "python", "-u", "-m", "worker.worker",
        ] + args

        p = subprocess.run(
            cmd,
            cwd=self.root_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )

        raw = (p.stdout or "").strip()

        if p.stderr:
            print("[WORKER-ERR]")
            print(p.stderr)

        if p.returncode != 0:
            return WorkerResult(False, {}, raw)

        try:
            data = json.loads(raw.splitlines()[-1])
            return WorkerResult(bool(data.get("ok", True)), data, raw)
        except Exception:
            return WorkerResult(False, {}, raw)

    # =================================================
    # Vision / OCR APIs
    # =================================================
    def capture_frame(self, camera_index: int = 0) -> WorkerResult:
        return self._run_worker(["--capture", f"--camera={camera_index}"], 60)

    def yolo_detect(self, reset: bool = False, camera_index: int = 0) -> WorkerResult:
        args = ["--yolo", f"--camera={camera_index}"]
        if reset:
            args.append("--reset-rois")
        return self._run_worker(args, 120)

    def ocr_read_volume(self, camera_index: int = 0) -> WorkerResult:
        return self._run_worker(["--ocr", f"--camera={camera_index}"], 120)

    # =================================================
    # Run-to-target (🔥 핵심 수정 부분)
    # =================================================
    def start_run_to_target(self, target: int, camera_index: int = 0) -> None:
        self.stop_run_to_target()

        cmd = [
            "conda", "run", "-n", self.conda_env,
            "python", "-u", "-m", "worker.worker",
            "--run-target",
            f"--target={target}",
            f"--camera={camera_index}",
        ]

        self.long_proc = subprocess.Popen(
            cmd,
            cwd=self.root_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        threading.Thread(
            target=self._read_worker_log,
            daemon=True,
        ).start()


    def stop_run_to_target(self) -> None:
        if self.long_proc and self.long_proc.poll() is None:
            try:
                self.long_proc.terminate()
            except Exception:
                pass
        self.long_proc = None

    def _read_worker_log(self):
        proc = self.long_proc
        if not proc:
            return

        if proc.stdout:
            for line in proc.stdout:
                print("[WORKER]", line.rstrip())

        if proc.stderr:
            for line in proc.stderr:
                print("[WORKER-ERR]", line.rstrip())





    # =================================================
    # 종료 처리
    # =================================================
    def close(self):
        try:
            self.volume_dc.stop()
        except Exception:
            pass
        self.serial.close()

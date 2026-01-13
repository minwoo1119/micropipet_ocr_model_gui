import json
import time
import os
import subprocess
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
    ✔ Linear actuator              : GUI process + SerialController (C# 동일)
    ✔ DC motor                     : GUI process + SerialController
    """

    # ==============================
    # Init
    # ==============================
    def __init__(self, conda_env: str = "pipet_env"):
        # -------------------------------------------------
        # Worker (conda subprocess) 관련
        # -------------------------------------------------
        self.conda_env = conda_env
        self.root_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )
        self.worker_path = os.path.join(
            self.root_dir, "worker", "worker.py"
        )
        self.long_proc: Optional[subprocess.Popen] = None

        # -------------------------------------------------
        # ✅ SerialController (GUI 생명주기 동안 단 1개)
        # -------------------------------------------------
        self.serial = SerialController("/dev/ttyUSB0")
        self.serial.connect()

        # -------------------------------------------------
        # ✅ Linear actuators (직접 제어, C# 동일)
        # -------------------------------------------------
        # 0x0B : 흡인분주 / 팁교체 리니어
        self.pipetting_linear = LinearActuator(
            serial=self.serial,
            actuator_id=0x0B,
        )

        # 0x0A : 용량 조절 리니어
        self.volume_linear = LinearActuator(
            serial=self.serial,
            actuator_id=0x0A,
        )

        # -------------------------------------------------
        # ✅ Volume DC motor (0x0C)
        # -------------------------------------------------
        self.volume_dc = VolumeDCActuator(
            serial=self.serial,
            actuator_id=0x0C,
        )

        # -------------------------------------------------
        # 상태 플래그 (GUI 토글용)
        # -------------------------------------------------
        self._pipetting_down = False
        self._tip_down = False
        self._volume_down = False

        # ==============================
        # MightyZap 초기화 (C#과 1:1)
        # ==============================

        # ---- 0x0B : 흡인분주 / 팁교체 ----
        self.serial.send_mightyzap_force_onoff(0x0B, 1)
        time.sleep(0.1)

        self.serial.send_mightyzap_set_speed(0x0B, 500)
        time.sleep(0.1)

        self.serial.send_mightyzap_set_current(0x0B, 300)
        time.sleep(0.1)

        self.serial.send_mightyzap_set_position(0x0B, 300)
        time.sleep(0.1)

        # ---- 0x0A : 용량 조절 리니어 ----
        self.serial.send_mightyzap_force_onoff(0x0A, 1)
        time.sleep(0.1)

        self.serial.send_mightyzap_set_speed(0x0A, 500)
        time.sleep(0.1)

        self.serial.send_mightyzap_set_current(0x0A, 300)
        time.sleep(0.1)

        self.serial.send_mightyzap_set_position(0x0A, 300)
        time.sleep(0.1)

    # =================================================
    # Internal worker runner (Vision only)
    # =================================================
    def _run_worker(
        self,
        args: List[str],
        timeout: Optional[int] = 120,
    ) -> WorkerResult:

        safe_args: List[str] = []
        for a in args:
            if not isinstance(a, str):
                raise TypeError(
                    f"_run_worker args must be str, got {type(a)} : {a}"
                )
            safe_args.append(a)

        cmd = [
            "conda", "run", "-n", self.conda_env,
            "python", "-m", "worker.worker",
        ] + safe_args

        print("\n[Controller] Running worker command:")
        print(" ".join(cmd))


        p = subprocess.run(
            cmd,
            cwd=self.root_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )

        if p.stdout:
            print("\n[Worker STDOUT]")
            print(p.stdout)

        if p.stderr:
            print("\n[Worker STDERR]")
            print(p.stderr)

        raw = (p.stdout or "").strip()

        if p.returncode != 0:
            return WorkerResult(False, {}, raw)

        try:
            data = json.loads(raw.splitlines()[-1])
            return WorkerResult(bool(data.get("ok", True)), data, raw)
        except Exception:
            return WorkerResult(False, {}, raw)

    # =================================================
    # Vision / OCR (conda subprocess 유지)
    # =================================================
    def capture_frame(self, camera_index: int = 0) -> WorkerResult:
        return self._run_worker(
            ["--capture", f"--camera={camera_index}"],
            timeout=60,
        )

    def yolo_detect(
        self,
        reset: bool = False,
        camera_index: int = 0,
    ) -> WorkerResult:
        args = ["--yolo", f"--camera={camera_index}"]
        if reset:
            args.append("--reset-rois")
        return self._run_worker(args, timeout=120)

    def ocr_read_volume(self, camera_index: int = 0) -> WorkerResult:
        return self._run_worker(
            ["--ocr", f"--camera={camera_index}"],
            timeout=120,
        )

    # =================================================
    # Linear actuator (GUI에서 직접 제어)
    # =================================================
    # ---- 흡인분주 (0x0B) ----
    def pipetting_down(self):
        self.pipetting_linear.move_to(900)
        self._pipetting_down = True

    def pipetting_up(self):
        self.pipetting_linear.move_to(1200)
        self._pipetting_down = False

    # ---- 팁 교체 (0x0B) ----
    def tip_change_down(self):
        self.pipetting_linear.move_to(400)
        self._tip_down = True

    def tip_change_up(self):
        self.pipetting_linear.move_to(2000)
        self._tip_down = False

    # ---- 용량 조절 리니어 (0x0A) ----
    def volume_down(self):
        self.volume_linear.move_to(900)
        self._volume_down = True

    def volume_up(self):
        self.volume_linear.move_to(1500)
        self._volume_down = False

    # ---- 범용 리니어 이동 ----
    def linear_move(self, actuator_id: int, position: int):
        act = LinearActuator(
            serial=self.serial,
            actuator_id=actuator_id,
        )
        act.move_to(position)

    # =================================================
    # Volume DC motor (0x0C)
    # =================================================
    def volume_cw(self, duty: int):
        self.volume_dc.run(direction=1, duty=duty)

    def volume_ccw(self, duty: int):
        self.volume_dc.run(direction=0, duty=duty)

    def volume_stop(self):
        self.volume_dc.stop()

    # =================================================
    # Run-to-target (conda 유지)
    # =================================================
    def start_run_to_target(
            self,
            target: int,
            camera_index: int = 0,
        ) -> None:
            self.stop_run_to_target()

            cmd = [
                "conda", "run", "-n", self.conda_env,
                "python", "-m", "worker.worker",
                "--run-target",
                f"--target={target}",
                f"--camera={camera_index}",
            ]

            self.long_proc = subprocess.Popen(
                cmd,
                cwd=self.root_dir,
            )


    def stop_run_to_target(self) -> None:
        if self.long_proc and self.long_proc.poll() is None:
            try:
                self.long_proc.terminate()
            except Exception:
                pass
        self.long_proc = None

    # =================================================
    # 종료 처리 (GUI 닫힐 때 호출 권장)
    # =================================================
    def close(self):
        try:
            self.volume_dc.stop()
        except Exception:
            pass
        self.serial.close()

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

from worker.serial_controller import SerialController


@dataclass
class WorkerResult:
    ok: bool
    data: Dict[str, Any]
    raw: str


class Controller:
    """
    GUI(system python) <-> Worker(conda pipet_env)

    ✔ subprocess 기반:
        - YOLO
        - OCR
        - linear actuator (흡인/팁/용량 하강·이동)

    ✔ direct serial 기반:
        - pipette DC motor (GUI → SerialController 직결)
    """

    def __init__(self, conda_env: str = "pipet_env"):
        # ---------------------------
        # Worker (subprocess) 관련
        # ---------------------------
        self.conda_env = conda_env
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.worker_path = os.path.join(self.root_dir, "worker", "worker.py")
        self.long_proc: Optional[subprocess.Popen] = None

        # ---------------------------
        # 🔥 Serial only (DC motor 포함)
        # ---------------------------
        self.serial = SerialController("/dev/ttyUSB0")
        self.serial.connect()

    # =================================================
    # Internal worker runner
    # =================================================
    def _run_worker(self, args: List[str], timeout: Optional[int] = 120) -> WorkerResult:
        cmd = [
            "conda", "run", "-n", self.conda_env,
            "python", "-m", "worker.worker"
        ] + args

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
            return WorkerResult(
                False,
                {
                    "returncode": p.returncode,
                    "stdout": p.stdout,
                    "stderr": p.stderr,
                },
                raw,
            )

        lines = raw.splitlines()
        last_line = lines[-1] if lines else ""

        try:
            data = json.loads(last_line)
            return WorkerResult(
                bool(data.get("ok", True)),
                data,
                raw,
            )
        except json.JSONDecodeError as e:
            return WorkerResult(
                False,
                {
                    "error": "Invalid JSON from worker",
                    "exception": str(e),
                    "stdout": p.stdout,
                    "stderr": p.stderr,
                },
                raw,
            )

    # =================================================
    # Camera / Vision
    # =================================================
    def capture_frame(self, camera_index: int = 0) -> WorkerResult:
        return self._run_worker(["--capture", f"--camera={camera_index}"], timeout=60)

    def yolo_detect(self, reset: bool = False, camera_index: int = 0) -> WorkerResult:
        args = ["--yolo", f"--camera={camera_index}"]
        if reset:
            args.append("--reset-rois")
        return self._run_worker(args, timeout=120)

    def ocr_read_volume(self, camera_index: int = 0) -> WorkerResult:
        return self._run_worker(["--ocr", f"--camera={camera_index}"], timeout=120)

    # =================================================
    # Linear actuator (subprocess)
    # =================================================
    def linear_move(self, actuator_id: int, position: int) -> WorkerResult:
        return self._run_worker(
            [
                "--linear-move",
                f"--actuator-id={hex(actuator_id)}",
                f"--position={position}",
            ],
            timeout=20,
        )

    def pipetting_up(self) -> WorkerResult:
        return self._run_worker(["--linear-pipetting-up"], timeout=20)

    def pipetting_down(self) -> WorkerResult:
        return self._run_worker(["--linear-pipetting-down"], timeout=20)

    def tip_change_up(self) -> WorkerResult:
        return self._run_worker(["--tip-change-up"], timeout=20)

    def tip_change_down(self) -> WorkerResult:
        return self._run_worker(["--tip-change-down"], timeout=20)

    def volume_linear_move(self, position: int) -> WorkerResult:
        return self._run_worker(
            [
                "--linear-move",
                "--actuator-id=0x0A",
                f"--position={int(position)}",
            ],
            timeout=20,
        )

    # =================================================
    # Run-to-target (long process)
    # =================================================
    def start_run_to_target(self, target: int, camera_index: int = 0) -> None:
        self.stop_run_to_target()

        cmd = [
            "conda", "run", "-n", self.conda_env,
            "python", self.worker_path,
            "--run-target",
            f"--target={target}",
            f"--camera={camera_index}",
        ]
        self.long_proc = subprocess.Popen(cmd, cwd=self.root_dir)

    def stop_run_to_target(self) -> None:
        if self.long_proc and self.long_proc.poll() is None:
            try:
                self.long_proc.terminate()
            except Exception:
                pass
        self.long_proc = None

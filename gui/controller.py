import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Optional, List


@dataclass
class WorkerResult:
    ok: bool
    data: Dict[str, Any]
    raw: str


class Controller:
    """
    GUI(system python) <-> Worker(conda pipet_env)
    - short task: subprocess.run() + JSON 결과 파싱
    - long task(목표 도달): subprocess.Popen() 유지 + stop 지원
    """
    def __init__(self, conda_env: str = "pipet_env"):
        self.conda_env = conda_env
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.worker_path = os.path.join(self.root_dir, "worker", "worker.py")
        self.long_proc: Optional[subprocess.Popen] = None

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
            print(f"[Controller] Worker exited with code {p.returncode}")
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
            print("[Controller] JSON parse failed")
            print("Last line:", last_line)

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

    # ----------- Camera / Preview -----------
    def capture_frame(self, camera_index: int = 0) -> WorkerResult:
        return self._run_worker(["--capture", f"--camera={camera_index}"], timeout=60)

    # ----------- YOLO -----------
    def yolo_detect(self, reset: bool = False, camera_index: int = 0) -> WorkerResult:
        
        print("[Controller] run_yolo called")
        args = ["--yolo", f"--camera={camera_index}"]
        if reset:
            args.append("--reset-rois")
        return self._run_worker(args, timeout=120)

    # ----------- OCR(TRT) -----------
    def ocr_read_volume(self, camera_index: int = 0) -> WorkerResult:
        return self._run_worker(["--ocr", f"--camera={camera_index}"], timeout=120)

    # ----------- Motor Test -----------
    def motor_test(self, direction: int, strength: int, duration_ms: int) -> WorkerResult:
        return self._run_worker(
            ["--motor-test", f"--direction={direction}", f"--strength={strength}", f"--duration={duration_ms}"],
            timeout=30,
        )
    
    def motor_stop(self):
        return self._run_worker(
            ["--motor-test", "--direction=0", "--strength=0", "--duration=1"],
            timeout=5,
        )

    # ----------- Run-to-target (long) -----------
    def start_run_to_target(self, target: int, camera_index: int = 0) -> None:
        self.stop_run_to_target()

        cmd = [
            "conda", "run", "-n", self.conda_env, "python", self.worker_path,
            "--run-target", f"--target={target}", f"--camera={camera_index}"
        ]
        self.long_proc = subprocess.Popen(cmd, cwd=self.root_dir)

    def stop_run_to_target(self) -> None:
        if self.long_proc and self.long_proc.poll() is None:
            try:
                self.long_proc.terminate()
            except Exception:
                pass
        self.long_proc = None

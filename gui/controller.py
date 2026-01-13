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
from worker.paths import FRAME_JPG_PATH


# =================================================
# Result wrapper
# =================================================
@dataclass
class WorkerResult:
    ok: bool
    data: Dict[str, Any]
    raw: str


# =================================================
# Controller
# =================================================
class Controller:
    """
    ✔ Vision / OCR / Run-to-target : subprocess (conda 유지)
    ✔ Linear actuator              : GUI process + SerialController
    ✔ DC motor                     : GUI process + SerialController
    ✔ VideoPanel frame 갱신 중계
    """

    # ==============================
    # Init
    # ==============================
    def __init__(self, conda_env: str = "pipet_env"):
        self.conda_env = conda_env
        self.root_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )

        # worker long-running process
        self.long_proc: Optional[subprocess.Popen] = None

        # GUI panel references
        self.video_panel = None   # 🔥 VideoPanel 연결용

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

        # ===============================
        # Run-to-target 상태 저장 (GUI용)
        # ===============================
        self.run_state = {
            "running": False,
            "step": 0,
            "current": 0,
            "target": 0,
            "error": 0,
            "direction": None,
            "duty": 0,
            "status": "Idle",
        }


    # =================================================
    # Video panel 연결
    # =================================================
    def set_video_panel(self, panel):
        """
        main_window 에서 VideoPanel 생성 후 반드시 호출
        """
        self.video_panel = panel

    def refresh_camera_view(self):
        """
        FRAME_JPG_PATH 에 저장된 최신 프레임을
        VideoPanel에 표시
        """
        if not self.video_panel:
            return

        if not os.path.exists(FRAME_JPG_PATH):
            return

        self.video_panel.show_image(FRAME_JPG_PATH)

    # =================================================
    # Internal worker runner (Vision / OCR)
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
        res = self._run_worker(
            ["--capture", f"--camera={camera_index}"], 60
        )
        if res.ok:
            self.refresh_camera_view()
        return res

    def yolo_detect(
        self,
        reset: bool = False,
        camera_index: int = 0,
    ) -> WorkerResult:
        args = ["--yolo", f"--camera={camera_index}"]
        if reset:
            args.append("--reset-rois")

        res = self._run_worker(args, 120)
        if res.ok:
            self.refresh_camera_view()
        return res

    def ocr_read_volume(self, camera_index: int = 0) -> WorkerResult:
        res = self._run_worker(
            ["--ocr", f"--camera={camera_index}"], 120
        )
        if res.ok:
            self.refresh_camera_view()
        return res

    # =================================================
    # Run-to-target (worker subprocess)
    # =================================================
    def start_run_to_target(self, target: int, camera_index: int = 0) -> None:
        self.stop_run_to_target()

        # 상태 초기화
        self.run_state.update({
            "running": True,
            "step": 0,
            "current": 0,
            "target": target,
            "error": 0,
            "direction": None,
            "duty": 0,
            "status": "Running",
        })

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
            target=self._run_to_target_loop,
            daemon=True,
        ).start()

    def _run_to_target_loop(self):
        proc = self.long_proc
        if not proc or not proc.stdout:
            return

        for line in proc.stdout:
            line = line.strip()

            # 1️⃣ 사람이 보는 로그
            if not line.startswith("{"):
                print("[WORKER]", line)
                continue

            # 2️⃣ JSON 명령 파싱
            try:
                msg = json.loads(line)
            except Exception:
                continue

            if msg.get("cmd") != "volume":
                continue

            direction = msg["direction"]
            duty = msg["duty"]
            duration_ms = msg["duration_ms"]

            # 3️⃣ 모터 제어 (🔥 여기서 실제 동작)
            self.volume_dc.run(direction=direction, duty=duty)
            time.sleep(duration_ms / 1000.0)
            self.volume_dc.stop()

            # 4️⃣ 상태 업데이트 (GUI용)
            self.run_state.update({
                "direction": direction,
                "duty": duty,
                "status": "Running",
            })

        # 종료
        self.run_state["running"] = False
        self.run_state["status"] = "Done"



    def stop_run_to_target(self) -> None:
        if self.long_proc and self.long_proc.poll() is None:
            try:
                self.long_proc.terminate()
            except Exception:
                pass

        self.volume_dc.stop()

        self.run_state["running"] = False
        self.run_state["status"] = "Stopped"
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

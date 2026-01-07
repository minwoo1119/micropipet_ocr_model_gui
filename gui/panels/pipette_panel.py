import tkinter as tk
from tkinter import ttk, messagebox

from worker.actuator_volume_dc import VolumeDCActuator


class PipettePanel(tk.Frame):
    """
    Pipette control panel
    (C# GUI equivalent, with duty / duration input)
    """

    def __init__(
        self,
        master,
        volume_dc: VolumeDCActuator,
    ):
        super().__init__(master)

        self.volume_dc = volume_dc

        # default values (C# 기준값)
        self.duty_var = tk.IntVar(value=40)
        self.duration_var = tk.IntVar(value=800)

        self._build_ui()

    # -------------------------------------------------
    # UI Layout
    # -------------------------------------------------
    def _build_ui(self):
        self.columnconfigure(0, weight=1)

        title = ttk.Label(self, text="Pipette Control Panel", font=("Arial", 14, "bold"))
        title.grid(row=0, column=0, pady=10)

        # =============================
        # Parameter Input
        # =============================
        frame_param = ttk.LabelFrame(self, text="Parameters")
        frame_param.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        # Duty slider
        ttk.Label(frame_param, text="Duty (%)").grid(row=0, column=0, sticky="w")
        duty_scale = ttk.Scale(
            frame_param,
            from_=0,
            to=100,
            orient="horizontal",
            command=self._on_duty_change,
        )
        duty_scale.set(self.duty_var.get())
        duty_scale.grid(row=1, column=0, sticky="ew", pady=3)

        self.duty_label = ttk.Label(
            frame_param, text=f"{self.duty_var.get()} %"
        )
        self.duty_label.grid(row=1, column=1, padx=5)

        # Duration entry
        ttk.Label(frame_param, text="Duration (ms)").grid(row=2, column=0, sticky="w")
        duration_entry = ttk.Entry(
            frame_param, textvariable=self.duration_var, width=10
        )
        duration_entry.grid(row=3, column=0, sticky="w", pady=3)

        frame_param.columnconfigure(0, weight=1)

        # =============================
        # Aspirate / Dispense
        # =============================
        frame_io = ttk.LabelFrame(self, text="Aspirate / Dispense")
        frame_io.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        ttk.Button(
            frame_io,
            text="Aspirate",
            command=lambda: self._run(direction=1),
        ).pack(fill="x", padx=5, pady=3)

        ttk.Button(
            frame_io,
            text="Dispense",
            command=lambda: self._run(direction=0),
        ).pack(fill="x", padx=5, pady=3)

        # =============================
        # Volume Adjust
        # =============================
        frame_vol = ttk.LabelFrame(self, text="Volume Adjust")
        frame_vol.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        ttk.Button(
            frame_vol,
            text="Volume +",
            command=lambda: self._run(direction=1),
        ).pack(fill="x", padx=5, pady=3)

        ttk.Button(
            frame_vol,
            text="Volume -",
            command=lambda: self._run(direction=0),
        ).pack(fill="x", padx=5, pady=3)

        # =============================
        # Tip Control
        # =============================
        frame_tip = ttk.LabelFrame(self, text="Tip Control")
        frame_tip.grid(row=4, column=0, padx=10, pady=5, sticky="ew")

        ttk.Button(
            frame_tip,
            text="Tip Attach",
            command=lambda: self._run(direction=1),
        ).pack(fill="x", padx=5, pady=3)

        ttk.Button(
            frame_tip,
            text="Tip Detach",
            command=lambda: self._run(direction=0),
        ).pack(fill="x", padx=5, pady=3)

        # =============================
        # Stop
        # =============================
        ttk.Button(
            self,
            text="STOP",
            command=self.volume_dc.stop,
            style="Danger.TButton",
        ).grid(row=5, column=0, padx=10, pady=10, sticky="ew")

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _on_duty_change(self, value):
        duty = int(float(value))
        self.duty_var.set(duty)
        self.duty_label.config(text=f"{duty} %")

    def _run(self, direction: int):
        """
        Read GUI parameters and run motor
        """
        try:
            duty = int(self.duty_var.get())
            duration = int(self.duration_var.get())

            if not (0 <= duty <= 100):
                raise ValueError("Duty must be 0~100")

            if duration <= 0:
                raise ValueError("Duration must be > 0")

            self.volume_dc.run_for(
                direction=direction,
                duty=duty,
                duration_ms=duration,
            )

        except Exception as e:
            messagebox.showerror("Invalid Parameter", str(e))

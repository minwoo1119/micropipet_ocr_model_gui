import tkinter as tk
from tkinter import ttk

from worker.actuator_volume_dc import VolumeDCActuator


class PipettePanel(tk.Frame):
    """
    Pipette control panel
    (C# GUI equivalent)
    """

    def __init__(
        self,
        master,
        volume_dc: VolumeDCActuator,
        default_duty: int = 40,
    ):
        super().__init__(master)

        self.volume_dc = volume_dc
        self.default_duty = default_duty

        self._build_ui()

    # -------------------------------------------------
    # UI Layout
    # -------------------------------------------------
    def _build_ui(self):
        self.columnconfigure(0, weight=1)

        title = ttk.Label(self, text="Pipette Control Panel", font=("Arial", 14, "bold"))
        title.grid(row=0, column=0, pady=10)

        # -----------------------------
        # Aspirate / Dispense
        # -----------------------------
        frame_io = ttk.LabelFrame(self, text="Aspirate / Dispense")
        frame_io.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        ttk.Button(
            frame_io,
            text="Aspirate",
            command=lambda: self.volume_dc.run_for(
                direction=1,
                duty=self.default_duty,
                duration_ms=800,
            ),
        ).pack(fill="x", padx=5, pady=3)

        ttk.Button(
            frame_io,
            text="Dispense",
            command=lambda: self.volume_dc.run_for(
                direction=0,
                duty=self.default_duty,
                duration_ms=800,
            ),
        ).pack(fill="x", padx=5, pady=3)

        # -----------------------------
        # Volume Adjust
        # -----------------------------
        frame_vol = ttk.LabelFrame(self, text="Volume Adjust")
        frame_vol.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        ttk.Button(
            frame_vol,
            text="Volume +",
            command=lambda: self.volume_dc.run_for(
                direction=1,
                duty=self.default_duty,
                duration_ms=400,
            ),
        ).pack(fill="x", padx=5, pady=3)

        ttk.Button(
            frame_vol,
            text="Volume -",
            command=lambda: self.volume_dc.run_for(
                direction=0,
                duty=self.default_duty,
                duration_ms=400,
            ),
        ).pack(fill="x", padx=5, pady=3)

        # -----------------------------
        # Tip Control
        # -----------------------------
        frame_tip = ttk.LabelFrame(self, text="Tip Control")
        frame_tip.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        ttk.Button(
            frame_tip,
            text="Tip Attach",
            command=lambda: self.volume_dc.run_for(
                direction=1,
                duty=self.default_duty,
                duration_ms=1200,
            ),
        ).pack(fill="x", padx=5, pady=3)

        ttk.Button(
            frame_tip,
            text="Tip Detach",
            command=lambda: self.volume_dc.run_for(
                direction=0,
                duty=self.default_duty,
                duration_ms=1200,
            ),
        ).pack(fill="x", padx=5, pady=3)

        # -----------------------------
        # Stop
        # -----------------------------
        ttk.Button(
            self,
            text="STOP",
            command=self.volume_dc.stop,
            style="Danger.TButton",
        ).grid(row=4, column=0, padx=10, pady=10, sticky="ew")


# -------------------------------------------------
# Optional test runner
# -------------------------------------------------
if __name__ == "__main__":
    from worker.serial_controller import SerialController

    serial = SerialController(port="/dev/ttyUSB0")
    serial.connect()

    volume_dc = VolumeDCActuator(serial, actuator_id=1)

    root = tk.Tk()
    root.title("Pipette GUI")

    panel = PipettePanel(root, volume_dc)
    panel.pack(fill="both", expand=True)

    root.mainloop()

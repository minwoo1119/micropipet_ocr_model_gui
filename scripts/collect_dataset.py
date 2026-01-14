# scripts/collect_dataset.py
from worker.serial_controller import SerialController
from worker.actuator_volume_dc import VolumeDCActuator
from worker.ocr_trt import TRTWrapper
from worker.dataset_collector import run_dataset_collection
from worker.paths import OCR_TRT_PATH

serial = SerialController()
serial.connect()

actuator = VolumeDCActuator(
    serial=serial,
    actuator_id=0x01
)

ocr = TRTWrapper(OCR_TRT_PATH)

run_dataset_collection(
    actuator=actuator,
    ocr=ocr,
    max_iter=2000   # None이면 무한
)

import fcntl
import queue
import threading
import time
import uuid
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Type, TypeVar, Union

from pyre_extensions import none_throws

from serial import PARITY_NONE, Serial


class SerialDevice(ABC):
    WAIT_TIME_AFTER_WRITE_MS: float = 0.0

    _serial_controller: Optional["SerialController"]

    def __init__(
        self,
        port: str,
        baudrate: int,
        bytesize: int = 8,
        parity: str = PARITY_NONE,
        stopbits: int = 1,
        xonxoff: bool = False,
        timeout_ms: Optional[float] = None,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.xonxoff = xonxoff
        self.timeout_ms = timeout_ms

        self._serial_controller = None

    @property
    def serial_controller(self) -> "SerialController":
        return none_throws(
            self._serial_controller,
            "Attempted to access SerialDevice without opening it first",
        )

    def _write(self, msg: bytes) -> None:
        self.serial_controller.write(msg)

    def _query(self, msg: bytes) -> str:
        return self.serial_controller.query(msg)

    def open(self) -> None:
        serial_controller = SerialController.get_or_create(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
            xonxoff=self.xonxoff,
            timeout_ms=self.timeout_ms,
            wait_time_after_write_ms=self.WAIT_TIME_AFTER_WRITE_MS,
        )
        if not serial_controller.is_alive():
            serial_controller.start()
        self._serial_controller = serial_controller
        self._on_open()

    def close(self) -> None:
        self.serial_controller.close()

    def _on_open(self) -> None:
        pass


REGISTRY_LOCK = threading.Lock()
SERIAL_CONTROLLERS: Dict[str, "SerialController"] = {}


class SerialControllerJobPriority(Enum):
    HIGH = 0
    LOW = 10


class SerialControllerJobType(Enum):
    WRITE = 0
    QUERY = 1
    CLOSE = 2


@dataclass(frozen=True, order=True)
class SerialControllerJob:
    condition: threading.Condition = field(init=False, compare=False)
    uuid: str = field(init=False, compare=False)
    type: SerialControllerJobType = field(compare=False)
    message: bytes = field(default=b"", compare=False)
    priority: SerialControllerJobPriority = SerialControllerJobPriority.LOW

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition", threading.Condition())
        object.__setattr__(self, "uuid", str(uuid.uuid4()))


TResult = TypeVar("TResult")


class SerialController(threading.Thread):
    port: str
    serial: Serial
    job_queue: "queue.PriorityQueue[SerialControllerJob]"
    job_results: Dict[str, Union[str, Exception]]
    num_clients: int
    wait_time_after_write_ms: float

    def __init__(
        self,
        port: str,
        baudrate: int,
        bytesize: int,
        parity: str,
        stopbits: int,
        xonxoff: bool,
        timeout_ms: Optional[float],
        wait_time_after_write_ms: float,
    ) -> None:
        super().__init__()
        self.daemon = True

        self.port = port

        self.serial = Serial()
        self.serial.port = port
        self.serial.baudrate = baudrate
        self.serial.bytesize = bytesize
        self.serial.parity = parity
        self.serial.stopbits = stopbits
        self.serial.xonxoff = xonxoff
        self.serial.timeout = timeout_ms / 1000.0 if timeout_ms else None

        self.wait_time_after_write_ms = wait_time_after_write_ms

        self.job_queue = queue.PriorityQueue()
        self.job_results = {}
        self.num_clients = 0

    @classmethod
    def get_or_create(
        cls,
        port: str,
        baudrate: int,
        bytesize: int,
        parity: str,
        stopbits: int,
        xonxoff: bool,
        timeout_ms: Optional[float],
        wait_time_after_write_ms: float,
    ) -> "SerialController":
        with REGISTRY_LOCK:
            if (
                port in SERIAL_CONTROLLERS.keys()
                and SERIAL_CONTROLLERS[port].is_alive()
            ):
                serial_controller = SERIAL_CONTROLLERS[port]
            else:
                serial_controller = SerialController(
                    port=port,
                    baudrate=baudrate,
                    bytesize=bytesize,
                    parity=parity,
                    stopbits=stopbits,
                    xonxoff=xonxoff,
                    timeout_ms=timeout_ms,
                    wait_time_after_write_ms=wait_time_after_write_ms,
                )
                SERIAL_CONTROLLERS[port] = serial_controller
            serial_controller.num_clients += 1
            return serial_controller

    def _run_and_wait(self, job: SerialControllerJob) -> None:
        with job.condition:
            self.job_queue.put(job)
            job.condition.wait()

    def _read_result(
        self, job: SerialControllerJob, result_type: Type[TResult]
    ) -> TResult:
        result = self.job_results.get(job.uuid)
        try:
            del self.job_results[job.uuid]
        except KeyError:
            pass
        if isinstance(result, result_type):
            return result
        assert isinstance(result, Exception)
        raise result

    def write(self, message: bytes) -> None:
        job = SerialControllerJob(type=SerialControllerJobType.WRITE, message=message)
        self._run_and_wait(job)
        return self._read_result(job, type(None))

    def query(self, message: bytes) -> str:
        job = SerialControllerJob(type=SerialControllerJobType.QUERY, message=message)
        self._run_and_wait(job)
        return self._read_result(job, str)

    def close(self) -> None:
        job = SerialControllerJob(type=SerialControllerJobType.CLOSE)
        self._run_and_wait(job)
        return self._read_result(job, type(None))

    def _write(self, message: bytes) -> None:
        self.serial.write(message)
        time.sleep(self.wait_time_after_write_ms / 1000.0)

    def _execute_job(self, job: SerialControllerJob) -> None:
        try:
            if job.type == SerialControllerJobType.CLOSE:
                with REGISTRY_LOCK:
                    self.num_clients -= 1
                    if self.num_clients == 0:
                        del SERIAL_CONTROLLERS[self.port]
                return

            if not self.serial.is_open:
                self.serial.open()
                fcntl.flock(self.serial, fcntl.LOCK_EX | fcntl.LOCK_NB)

            if job.type == SerialControllerJobType.WRITE:
                self._write(job.message)
                return

            if job.type == SerialControllerJobType.QUERY:
                self._write(job.message)
                response = self.serial.readline()[:-2].decode("utf-8")
                self.job_results[job.uuid] = response
                return
        except Exception as ex:
            self.job_results[job.uuid] = ex

    def run(self) -> None:
        try:
            while self.serial.port in SERIAL_CONTROLLERS.keys():
                job = self.job_queue.get()
                with job.condition:
                    self._execute_job(job)
                    job.condition.notify()
                self.job_queue.task_done()

            assert self.job_queue.empty()

        finally:
            self.serial.close()

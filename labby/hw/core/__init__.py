import fcntl
import inspect
import time
from abc import ABC, abstractmethod
from enum import Enum
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Type

from serial import Serial


class PowerSupplyMode(Enum):
    CONSTANT_VOLTAGE = 0
    CONSTANT_CURRENT = 1


ALL_DRIVERS: Dict[str, Type["Device"]] = {}


class Device(ABC):
    name: str = "unnamed device"

    def __init_subclass__(cls) -> None:
        ALL_DRIVERS[f"{cls.__module__}.{cls.__name__}"] = cls

    @abstractmethod
    def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def test_connection(self) -> None:
        raise NotImplementedError

    @classmethod
    def create(cls, name: str, driver: str, args: Dict[str, Any]) -> "Device":
        klass = ALL_DRIVERS[driver]
        signature = inspect.signature(klass)
        typed_args = {
            key: signature.parameters[key].annotation(value)
            for key, value in args.items()
        }
        # pyre-ignore[45]: Cannot instantiate abstract class Device
        device = klass(**typed_args)
        device.name = name
        return device


class SerialDevice(ABC):
    WAIT_TIME_AFTER_WRITE_MS: float = 0.0

    serial: Serial

    def __init__(self, port: str, baudrate: int) -> None:
        self.serial = Serial()
        self.serial.port = port
        self.serial.baudrate = baudrate

    def _read_line(self) -> str:
        return self.serial.readline()[:-2].decode("utf-8")

    def _write(self, msg: bytes) -> None:
        self.serial.write(msg)
        time.sleep(self.WAIT_TIME_AFTER_WRITE_MS / 1000.0)

    def _query(self, msg: bytes) -> str:
        self._write(msg)
        return self._read_line()

    def open(self) -> None:
        self.serial.open()
        fcntl.flock(self.serial, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self._on_open()

    def close(self) -> None:
        self.serial.close()

    @abstractmethod
    def _on_open(self) -> None:
        pass


class PowerSupply(Device, ABC):
    @abstractmethod
    def get_mode(self) -> PowerSupplyMode:
        raise NotImplementedError

    @abstractmethod
    def is_output_on(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def set_output_on(self, is_on: bool) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_target_voltage(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def get_actual_voltage(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def get_target_current(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def get_actual_current(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def set_target_voltage(self, voltage: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_target_current(self, current: float) -> None:
        raise NotImplementedError


class HardwareIOException(Exception):
    pass


def auto_discover_drivers() -> None:
    HW_PATH = Path(__file__).parent.parent
    for f in HW_PATH.glob("**/*.py"):
        if "__" in f.stem or "test" in f.stem or f.parent.stem == "hw":
            continue
        import_module(f"labby.hw.{f.parent.stem}.{f.stem}", __package__)

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Type


class PSUMode(Enum):
    CONSTANT_VOLTAGE = 0
    CONSTANT_CURRENT = 1


ALL_DRIVERS: Dict[str, Type["Device"]] = {}


class Device(ABC):
    def __init_subclass__(cls):
        ALL_DRIVERS[f"{cls.__module__}.{cls.__name__}"] = cls

    @classmethod
    def create(cls, driver: str, args: Dict[str, Any]) -> "Device":
        return ALL_DRIVERS[driver](**args)


class PSU(Device, ABC):
    @abstractmethod
    def get_mode(self) -> PSUMode:
        raise NotImplementedError

    @abstractmethod
    def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
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

import io
import time
from builtins import open as open_orig
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import timedelta
from time import sleep as sleep_orig
from typing import Callable, Dict, Generator, Iterator, List, Optional, Tuple, TypeVar
from unittest.mock import patch, mock_open, MagicMock, Mock

import freezegun


@contextmanager
def captured_output() -> Iterator[Tuple[io.StringIO, io.StringIO]]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        yield stdout, stderr


@contextmanager
def cli_arguments(arguments: List[str]) -> Iterator[None]:
    with patch("sys.argv", ["labby"] + arguments):
        yield


class _OpenMockFileStore:
    filename_to_mock: Dict[str, MagicMock] = {}

    def register(self, filename: str, contents: Optional[str]) -> None:
        assert filename not in self.filename_to_mock.keys()
        mock = mock_open(read_data=contents)
        self.filename_to_mock[filename] = mock()

    def unregister(self, filename: str) -> None:
        assert filename in self.filename_to_mock.keys()
        del self.filename_to_mock[filename]

    def open(self, filename: str, *args: object, **kwargs: object) -> MagicMock:
        filename = str(filename)
        if filename not in self.filename_to_mock.keys():
            return open_orig(filename, *args, **kwargs)
        return self.filename_to_mock[filename]


OPEN_MOCK_FILE_STORE = _OpenMockFileStore()


@contextmanager
def patch_file_contents(
    filename: str, contents: Optional[str] = None
) -> Iterator[MagicMock]:
    OPEN_MOCK_FILE_STORE.register(filename, contents)
    try:
        with patch("builtins.open", OPEN_MOCK_FILE_STORE.open):
            yield OPEN_MOCK_FILE_STORE.filename_to_mock[filename]
    finally:
        OPEN_MOCK_FILE_STORE.unregister(filename)


@contextmanager
def labby_config(config_contents: str) -> Iterator[None]:
    with patch_file_contents("labby.yml", config_contents):
        yield


TReturn = TypeVar("TReturn")


def fake_serial_port(func: Callable[..., TReturn]) -> Callable[..., TReturn]:
    serial_port_mock: Mock = Mock()

    def wrapper(*args: object, **kwargs: object) -> TReturn:
        with patch("labby.hw.core.serial.fcntl.flock"), patch(
            "labby.hw.core.serial.Serial", return_value=serial_port_mock
        ), patch_time("2020-08-08"):
            ret = func(*args, serial_port_mock, **kwargs)
        return ret

    return wrapper


ENV_VARIABLES: Dict[str, str] = {}


@contextmanager
def environment_variable(name: str, value: str) -> Iterator[None]:
    import os

    ENV_VARIABLES[name] = value
    with patch.dict(os.environ, ENV_VARIABLES):
        yield
    del ENV_VARIABLES[name]


@contextmanager
def patch_time(
    start_time: str,
    ticker: Optional[Generator[float, None, None]] = None,
) -> Iterator[None]:
    def patched_freeze_time(start_time: str) -> freezegun.api._freeze_time:
        # see https://github.com/spulec/freezegun/issues/307
        f = freezegun.freeze_time(start_time)
        # pyre-ignore[16]: `freezegun.api._freeze_time` has no attribute `ignore`.
        f.ignore = tuple(set(f.ignore) - {"threading"})
        return f

    frozen_time: freezegun.api._freeze_time
    with patched_freeze_time(start_time) as frozen_time:

        class Ticker:
            initial_tick_time: float = time.time()
            current_tick_time: float = 0.0

            def tick(self) -> None:
                while ticker and time.time() > self.current_tick_time:
                    try:
                        self.current_tick_time = self.initial_tick_time + next(ticker)
                    except StopIteration:
                        break

        t: Ticker = Ticker()

        def _sleep(seconds: float) -> None:
            sleep_orig(1e-10)
            # pyre-ignore[16]: `freezegun.api._freeze_time` has no attribute `tick`.
            frozen_time.tick(timedelta(seconds=seconds))
            t.tick()

        with patch("time.sleep", _sleep):
            t.tick()
            yield

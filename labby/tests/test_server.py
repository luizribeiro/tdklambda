import time
import unittest
from dataclasses import dataclass
from pathlib import PosixPath
from typing import cast
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

from mashumaro.serializer.msgpack import EncodedData

from labby.client import Client
from labby.config import Config
from labby.experiment import (
    BaseInputParameters,
    BaseOutputData,
    Experiment,
)
from labby.hw.core import DeviceType
from labby.hw.core.power_supply import PowerSupplyMode
from labby.server import Server, ServerRequest
from labby.server.requests.device_info import DeviceInfoResponse, PowerSupplyInfo
from labby.server.requests.halt import HaltRequest
from labby.server.requests.list_devices import DeviceStatus, ListDevicesResponse
from labby.tests.utils import patch_file_contents, patch_time
from labby.utils import auto_discover_drivers


FAKE_PID = 42


LABBY_CONFIG_YAML = """
---
devices:
  - name: "virtual-power-supply"
    type: power_supply
    driver: labby.hw.virtual.power_supply.PowerSupply
    args:
      load_in_ohms: 5
  - name: "broken-power-supply"
    type: power_supply
    driver: labby.hw.virtual.power_supply.BrokenPowerSupply
    args:
      load_in_ohms: 5
"""


class ServerTest(TestCase):
    @patch("os.fork", return_value=FAKE_PID)
    @patch("os.makedirs")
    def test_parent_process_on_start(
        self, makedirs: MagicMock, _fork_mock: MagicMock
    ) -> None:
        config = Config(LABBY_CONFIG_YAML)
        with patch_file_contents(".labby/pid") as pidfile:
            server = Server(config)
            server_info = server.start()
            self.assertFalse(server_info.existing)
            self.assertEqual(server_info.pid, FAKE_PID)
            makedirs.assert_called_with(".labby", exist_ok=True)
            pidfile.write.assert_called_once_with(str(FAKE_PID))

    @patch("os.fork", return_value=0)
    @patch("os.makedirs")
    @patch("os.remove")
    @patch("labby.server.Rep0")
    def test_child_process_on_start(
        self,
        rep0_mock: MagicMock,
        remove_mock: MagicMock,
        _makedirs: MagicMock,
        _fork_mock: MagicMock,
    ) -> None:
        config = Config(LABBY_CONFIG_YAML)
        with patch_file_contents(".labby/pid"):
            rep0_mock.return_value.__enter__.return_value.recv.return_value = (
                b"HaltRequest:" + cast(bytes, HaltRequest().to_msgpack())
            )

            server = Server(config)
            with self.assertRaises(SystemExit):
                server.start()
        remove_mock.assert_called_once_with(".labby/pid")

    def test_existing_pid(self) -> None:
        config = Config(LABBY_CONFIG_YAML)
        with patch_file_contents(".labby/pid", "12345"):
            server = Server(config)
            server_info = server.start()
            self.assertTrue(server_info.existing)
            self.assertEqual(server_info.pid, 12345)


@dataclass(frozen=True)
class OutputData(BaseOutputData):
    voltage: float


@dataclass(frozen=True)
class InputParameters(BaseInputParameters):
    pass


class TestExperiment(Experiment[InputParameters, OutputData]):
    SAMPLING_RATE_IN_HZ: float = 2.0
    DURATION_IN_SECONDS: float = 1.0

    def start(self) -> None:
        power_supply = self.get_power_supply("virtual-power-supply")
        power_supply.set_target_voltage(15)
        power_supply.set_target_current(4)
        power_supply.set_output_on(True)
        power_supply.open()

    def measure(self) -> OutputData:
        power_supply = self.get_power_supply("virtual-power-supply")
        actual_voltage = power_supply.get_actual_voltage()
        return OutputData(voltage=actual_voltage)

    def stop(self) -> None:
        power_supply = self.get_power_supply("virtual-power-supply")
        power_supply.close()


class ClientTest(TestCase):
    # pyre-ignore[24]: Generic type `unittest.mock._patch` expects 1 type parameter
    req_patch: unittest.mock._patch
    req_mock: MagicMock
    client: Client

    def setUp(self) -> None:
        auto_discover_drivers()
        config: Config = Config(LABBY_CONFIG_YAML)
        server: Server = Server(config)

        def _handle(msg: EncodedData) -> None:
            response_bytes = ServerRequest.handle_from_msgpack(server, msg)
            self.req_mock.return_value.recv.return_value = response_bytes

        self.req_patch = patch("labby.client.Req0")
        self.req_mock = self.req_patch.start()
        self.req_mock.return_value.send.side_effect = _handle

        self.client = Client("foobar")

    def tearDown(self) -> None:
        self.req_patch.stop()

    def test_halt(self) -> None:
        with self.assertRaises(SystemExit):
            self.client.halt()

    def test_close(self) -> None:
        self.client.close()
        self.req_mock.return_value.close.assert_called_once()

    def test_hello(self) -> None:
        response = self.client.hello()
        self.assertEqual(response, "Hello world")

    def test_list_devices(self) -> None:
        response = self.client.list_devices()
        self.assertEqual(
            response,
            ListDevicesResponse(
                devices=[
                    DeviceStatus(name="virtual-power-supply", is_available=True),
                    DeviceStatus(
                        name="broken-power-supply",
                        is_available=False,
                        error_type="Exception",
                        error_message="Unavailable device",
                    ),
                ]
            ),
        )

    def test_device_info(self) -> None:
        device_info = self.client.device_info("virtual-power-supply")
        self.assertEqual(
            device_info,
            DeviceInfoResponse(
                device_type=DeviceType.POWER_SUPPLY,
                is_connected=True,
                power_supply_info=PowerSupplyInfo(
                    is_output_on=False,
                    mode=PowerSupplyMode.CONSTANT_VOLTAGE,
                    target_voltage=0.0,
                    target_current=0.0,
                    actual_voltage=0.0,
                    actual_current=0.0,
                ),
            ),
        )

    def test_device_info_for_unavailable_device(self) -> None:
        device_info = self.client.device_info("broken-power-supply")
        self.assertEqual(
            device_info,
            DeviceInfoResponse(
                device_type=DeviceType.POWER_SUPPLY,
                is_connected=False,
                error_type="Exception",
                error_message="Unavailable device",
            ),
        )

    def test_device_info_for_unknown_device(self) -> None:
        device_info = self.client.device_info("foobar")
        self.assertEqual(
            device_info,
            DeviceInfoResponse(device_type=None, is_connected=False),
        )

    def test_run_sequence(self) -> None:
        SEQUENCE_CONTENTS = """
---
sequence:
  - experiment_type: labby.tests.test_server.TestExperiment
  - experiment_type: labby.tests.test_server.TestExperiment
"""
        with patch_file_contents(
            "sequence/test.yml", SEQUENCE_CONTENTS
        ), patch_file_contents("output/test/000.csv") as output_0, patch_file_contents(
            "output/test/001.csv"
        ) as output_1, patch(
            "os.makedirs"
        ) as makedirs, patch_time(
            "2020-08-08"
        ):
            self.client.run_sequence("sequence/test.yml")
            while True:
                sequence_status = self.client.experiment_status().sequence_status
                if sequence_status and sequence_status.is_finished():
                    break
                time.sleep(0)

            makedirs.assert_called_with(PosixPath("output/test/"), exist_ok=True)
            self.assertEqual(len(output_0.write.call_args_list), 4)
            output_0.write.assert_has_calls(
                [
                    call("seconds,voltage\n"),
                    call("0.0,15.0\n"),
                    call("0.5,15.0\n"),
                    call("1.0,15.0\n"),
                ]
            )
            output_1.write.assert_has_calls(
                [
                    call("seconds,voltage\n"),
                    call("0.0,15.0\n"),
                    call("0.5,15.0\n"),
                    call("1.0,15.0\n"),
                ]
            )

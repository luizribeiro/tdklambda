from unittest import TestCase
from unittest.mock import Mock

from labby.hw.core.exceptions import HardwareIOError
from labby.hw.core.power_supply import PowerSupplyMode
from labby.hw.tdklambda import power_supply as tdklambda_power_supply
from labby.tests.utils import fake_serial_port
from serial import EIGHTBITS, PARITY_NONE, STOPBITS_ONE


class ZUPTest(TestCase):
    @fake_serial_port
    def test_serial_port_settings(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600) as power_supply:
            self.assertEqual(power_supply.serial_controller.serial.baudrate, 9600)
            self.assertEqual(power_supply.serial_controller.serial.bytesize, EIGHTBITS)
            self.assertEqual(power_supply.serial_controller.serial.parity, PARITY_NONE)
            self.assertEqual(
                power_supply.serial_controller.serial.stopbits, STOPBITS_ONE
            )
            self.assertTrue(power_supply.serial_controller.serial.xonxoff)
            self.assertAlmostEqual(power_supply.serial_controller.serial.timeout, 2.0)

    @fake_serial_port
    def test_opening_with_default_address(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600):
            serial_port_mock.write.assert_called_once_with(b":ADR01;")

    @fake_serial_port
    def test_opening_with_custom_address(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600, address=42):
            serial_port_mock.write.assert_called_once_with(b":ADR42;")

    @fake_serial_port
    def test_closes_automatically_from_with_block(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600):
            pass
        serial_port_mock.close.assert_called_once()

    @fake_serial_port
    def test_can_be_used_without_with_block(self, serial_port_mock: Mock) -> None:
        power_supply = tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600)
        power_supply.open()
        serial_port_mock.write.assert_called_once_with(b":ADR01;")
        power_supply.close()
        serial_port_mock.close.assert_called_once()

    @fake_serial_port
    def test_setting_target_voltage(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600) as power_supply:
            serial_port_mock.reset_mock()
            power_supply.set_target_voltage(4.25)
            serial_port_mock.write.assert_called_once_with(b":VOL4.250;")

    @fake_serial_port
    def test_setting_target_current(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600) as power_supply:
            serial_port_mock.reset_mock()
            power_supply.set_target_current(1.23)
            serial_port_mock.write.assert_called_once_with(b":CUR001.23;")

    @fake_serial_port
    def test_get_model(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600) as power_supply:
            serial_port_mock.reset_mock()
            serial_port_mock.readline.return_value = b"FOOBAR\r\n"
            returned_model = power_supply.get_model()
            serial_port_mock.write.assert_called_once_with(b":MDL?;")
            self.assertEqual(returned_model, "FOOBAR")

    @fake_serial_port
    def test_get_software_version(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600) as power_supply:
            serial_port_mock.reset_mock()
            serial_port_mock.readline.return_value = b"V4.2.0\r\n"
            returned_version = power_supply.get_software_version()
            serial_port_mock.write.assert_called_once_with(b":REV?;")
            self.assertEqual(returned_version, "V4.2.0")

    @fake_serial_port
    def test_is_output_on(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600) as power_supply:
            serial_port_mock.reset_mock()
            serial_port_mock.readline.return_value = b"OT1\r\n"
            self.assertTrue(power_supply.is_output_on())
            serial_port_mock.write.assert_called_once_with(b":OUT?;")

            serial_port_mock.reset_mock()
            serial_port_mock.readline.return_value = b"OT0\r\n"
            self.assertFalse(power_supply.is_output_on())
            serial_port_mock.write.assert_called_once_with(b":OUT?;")

    @fake_serial_port
    def test_set_output_on(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600) as power_supply:
            serial_port_mock.reset_mock()
            power_supply.set_output_on(True)
            serial_port_mock.write.assert_called_once_with(b":OUT1;")

            serial_port_mock.reset_mock()
            power_supply.set_output_on(False)
            serial_port_mock.write.assert_called_once_with(b":OUT0;")

    @fake_serial_port
    def test_get_target_voltage(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600) as power_supply:
            serial_port_mock.reset_mock()
            serial_port_mock.readline.return_value = b"SV1.42\r\n"
            returned_target_voltage = power_supply.get_target_voltage()
            serial_port_mock.write.assert_called_once_with(b":VOL!;")
            self.assertAlmostEqual(returned_target_voltage, 1.42)

    @fake_serial_port
    def test_get_target_current(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600) as power_supply:
            serial_port_mock.reset_mock()
            serial_port_mock.readline.return_value = b"SA0.01\r\n"
            returned_target_current = power_supply.get_target_current()
            serial_port_mock.write.assert_called_once_with(b":CUR!;")
            self.assertAlmostEqual(returned_target_current, 0.01)

    @fake_serial_port
    def test_get_actual_voltage(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600) as power_supply:
            serial_port_mock.reset_mock()
            serial_port_mock.readline.return_value = b"AV1.33\r\n"
            returned_actual_voltage = power_supply.get_actual_voltage()
            serial_port_mock.write.assert_called_once_with(b":VOL?;")
            self.assertAlmostEqual(returned_actual_voltage, 1.33)

    @fake_serial_port
    def test_get_actual_current(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600) as power_supply:
            serial_port_mock.reset_mock()
            serial_port_mock.readline.return_value = b"AA0.02\r\n"
            returned_actual_current = power_supply.get_actual_current()
            serial_port_mock.write.assert_called_once_with(b":CUR?;")
            self.assertAlmostEqual(returned_actual_current, 0.02)

    @fake_serial_port
    def test_get_mode(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600) as power_supply:
            serial_port_mock.reset_mock()
            serial_port_mock.readline.return_value = b"OS100000000"
            returned_mode = power_supply.get_mode()
            serial_port_mock.write.assert_called_once_with(b":STA?;")
            self.assertEqual(returned_mode, PowerSupplyMode.CONSTANT_CURRENT)

    @fake_serial_port
    def test_invalid_response(self, serial_port_mock: Mock) -> None:
        with tdklambda_power_supply.ZUP("/dev/ttyUSB0", 9600) as power_supply:
            serial_port_mock.readline.return_value = b"foobar\r\n"
            with self.assertRaisesRegex(HardwareIOError, "Could not parse response"):
                power_supply.get_actual_voltage()

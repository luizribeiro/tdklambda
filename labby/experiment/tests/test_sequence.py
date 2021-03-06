from dataclasses import dataclass
from unittest import TestCase

from labby.experiment import (
    BaseInputParameters,
    BaseOutputData,
    Experiment,
)
from labby.experiment.sequence import ExperimentSequence


@dataclass(frozen=True)
class OutputData(BaseOutputData):
    pass


@dataclass(frozen=True)
class InputParameters(BaseInputParameters):
    current_in_amps: float
    voltage_in_volts: float = 6


class TestExperiment(Experiment[InputParameters, OutputData]):
    SAMPLING_RATE_IN_HZ: float = 1.0
    DURATION_IN_SECONDS: float = 3600

    def start(self) -> None:
        pass

    def measure(self) -> OutputData:
        return OutputData()

    def stop(self) -> None:
        pass


class ExperimentSequenceTest(TestCase):
    def test_parsing(self) -> None:
        sequence = ExperimentSequence(
            "sequences/test.yaml",
            """
---
sequence:
  - experiment_type: labby.experiment.tests.test_sequence.TestExperiment
    params:
      current_in_amps: 7
  - experiment_type: labby.experiment.tests.test_sequence.TestExperiment
    params:
      current_in_amps: 3
      voltage_in_volts: 2
""",
        )

        self.assertEqual(len(sequence.experiments), 2)

        first_experiment = sequence.experiments[0]
        assert isinstance(first_experiment, TestExperiment)
        self.assertAlmostEqual(first_experiment.params.current_in_amps, 7)
        self.assertAlmostEqual(first_experiment.params.voltage_in_volts, 6)

        second_experiment = sequence.experiments[1]
        assert isinstance(second_experiment, TestExperiment)
        self.assertAlmostEqual(second_experiment.params.current_in_amps, 3)
        self.assertAlmostEqual(second_experiment.params.voltage_in_volts, 2)

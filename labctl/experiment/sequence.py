import strictyaml
from strictyaml import Any, Map, MapPattern, Optional, Seq, Str
from typing import Sequence

from labctl.experiment import BaseInputParameters, BaseOutputData, Experiment


SCHEMA = Map(
    {
        "sequence": Seq(
            Map(
                {
                    "experiment_type": Str(),
                    Optional("params"): MapPattern(Str(), Any()),
                }
            ),
        ),
    }
)


class ExperimentSequence:
    sequence_config: strictyaml.YAML
    experiments: Sequence[Experiment[BaseInputParameters, BaseOutputData]]

    def __init__(self, yaml_contents: str) -> None:
        self.sequence_config = strictyaml.load(yaml_contents, SCHEMA)
        self.experiments = [
            Experiment.create(
                experiment["experiment_type"],
                f"{index:03d}",
                experiment["params"].data if "params" in experiment else None,
            )
            for index, experiment in enumerate(self.sequence_config["sequence"])
        ]

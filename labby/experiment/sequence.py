from typing import Sequence

import strictyaml
from strictyaml import Any, Map, MapPattern, Optional, Seq, Str

from labby.experiment import BaseInputParameters, BaseOutputData, Experiment


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
    filename: str
    sequence_config: strictyaml.YAML
    experiments: Sequence[Experiment[BaseInputParameters, BaseOutputData]]

    def __init__(self, filename: str, yaml_contents: str) -> None:
        self.filename = filename
        self.sequence_config = strictyaml.load(yaml_contents, SCHEMA)
        self.experiments = [
            Experiment.create(
                experiment["experiment_type"],
                f"{index:03d}",
                experiment["params"].data if "params" in experiment else None,
            )
            for index, experiment in enumerate(self.sequence_config["sequence"])
        ]

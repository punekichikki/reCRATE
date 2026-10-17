"""Execution backends. Every run returns a record that goes into the run crate.

  local    docker run on this machine (needs a Docker daemon)
  hf-jobs  Hugging Face Jobs: any Docker image on CPU or GPU, billed per minute from credits

Owner: Person 2.
"""
from dataclasses import dataclass, field


@dataclass
class RunRecord:
    runner: str                 # "local" | "hf-jobs"
    image: str
    command: list
    hardware: str = "local"
    exit_code: int = None
    job_id: str = None
    image_digest: str = None
    logs: str = ""
    extra: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in (None, "", {})}

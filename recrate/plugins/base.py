"""The interface every data-type plugin implements.

Everything that depends on the kind of data (tables, images, simulations) lives in a
plugin, so the agents and the core stay the same for every paper.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Comparison:
    """Result of comparing observed values with a claim. No verdict yet: the verifier decides that."""
    passed: bool
    near: bool = False          # outside tolerance but within twice the tolerance
    detail: str = ""


@dataclass
class CheckResult:
    """An independent check that does not use the authors' code."""
    check: str                  # e.g. "I1"
    about: str                  # claim identifier, e.g. "C5"
    outcome: str                # "robust" | "fragile" | "contradicted"
    summary: str
    method: str = ""
    environment: dict = field(default_factory=dict)


@dataclass
class Change:
    """A difference between user data and the input contract, with the proposed change."""
    kind: str                   # see core/classify.py CHANGE_RULES
    target: str                 # column, channel or parameter it applies to
    description: str
    change_class: str = ""      # filled by core.classify.classify_change, never by an agent


class DataPlugin:
    name = "base"

    def can_handle(self, path: str) -> bool:
        return False

    def load(self, path: str) -> Any:
        raise NotImplementedError

    def profile(self, data: Any) -> dict:
        raise NotImplementedError

    def extract(self, data: Any, output_key) -> Any:
        raise NotImplementedError

    def compare(self, observed: Any, claim: dict) -> Comparison:
        raise NotImplementedError

    def independent_checks(self, claim: dict, data: Any) -> list:
        return []

    def check_compatibility(self, profile: dict, contract: dict) -> list:
        return []

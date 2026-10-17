"""Plugin registry. The verifier picks a plugin by a claim's rc:dataType."""
from .base import CheckResult, Change, Comparison, DataPlugin
from .image import ImagePlugin
from .tabular import TabularPlugin

REGISTRY = {p.name: p for p in (TabularPlugin(), ImagePlugin())}


def get_plugin(data_type: str = None) -> DataPlugin:
    return REGISTRY.get(data_type or "tabular", REGISTRY["tabular"])


def plugin_for_path(path: str) -> DataPlugin:
    for p in REGISTRY.values():
        if p.can_handle(path):
            return p
    return REGISTRY["tabular"]

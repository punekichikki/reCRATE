"""Deterministic classification of patches and data changes (gates 2 and 3).

Agents propose patches and changes and explain them, but they never choose the class:
these rules do. When a rule does not match, the safer class wins.
"""
import fnmatch
import os

# Files that only describe the environment. Anything else counts as analysis.
ENVIRONMENT_PATTERNS = (
    "Dockerfile", "Dockerfile.*", "*.dockerfile", "docker-compose*.yml",
    "requirements*.txt", "constraints*.txt", "environment.yml", "environment.yaml", "conda-lock*.yml",
    "Pipfile", "Pipfile.lock", "poetry.lock", "uv.lock", "renv.lock", ".Rprofile", "install.R",
    "apt.txt", "runtime.txt", "*.lock",
)


def classify_patch(path: str, analysis_files=()) -> str:
    """Return "environment" or "analysis" for a patched file.

    analysis_files: scripts the resource map links to claims. They are always analysis,
    whatever their name.
    """
    norm = os.path.normpath(path)
    if norm in {os.path.normpath(a) for a in analysis_files}:
        return "analysis"
    name = os.path.basename(norm)
    if any(fnmatch.fnmatch(name, pat) for pat in ENVIRONMENT_PATTERNS):
        return "environment"
    return "analysis"


# Transfer changes (gate 3). "warning" = keep the data, flag it in the record.
CHANGE_RULES = {
    "format-conversion": "routine",
    "unit-conversion": "routine",
    "rescale-pixel-size": "routine",
    "column-rename": "routine",
    "missing-column": "routine",         # a mapping from an existing column; unmatched count logged
    "id-mapping": "routine",
    "type-conversion": "routine",
    "intensity-normalisation": "routine",
    "out-of-range": "warning",
    "missing-values": "meaning-changing",  # dropping or imputing goes beyond the paper's rules
    "parameter-change": "meaning-changing",
    "threshold-change": "meaning-changing",
    "model-change": "meaning-changing",
    "preprocessing-change": "meaning-changing",
    "drop-data": "meaning-changing",
    "impute-data": "meaning-changing",
}


def classify_change(kind: str) -> str:
    """routine | warning | meaning-changing. Unknown kinds are meaning-changing."""
    return CHANGE_RULES.get(kind, "meaning-changing")


def needs_approval(kind: str) -> bool:
    return classify_change(kind) == "meaning-changing"

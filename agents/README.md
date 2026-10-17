# Agents

Each agent is a separate Claude session with its own instructions (`PROMPT.md`) and an allowlist of tools.
The orchestrator (`recrate/orchestrator.py`) starts it, passes only the files it may read, and checks
what it writes against `schemas/` before the next stage runs. **No agent assigns a verdict**: verdicts come
from `recrate/core/verify.py`.

| Agent | Folder | Owner | Reads | Writes | May not |
| --- | --- | --- | --- | --- | --- |
| Paper Analysis | `analysis/` | Person 1 | Paper PDF, supplementary text | Claims with proposed tolerances, gaps, input contract | Run code; set final tolerances |
| Resource Discovery | `discovery/` | Person 2 | Paper, repository, data links | Resource map, file entities with sha256, environment hints, inconsistency gaps | Edit code or data |
| Execution | `execution/` | Person 2 | Repository, resource map, claims **without expected values** | Container, run script, `observed-*.json`, `patches.json` | See expected values; edit claims |
| Verification (explainer) | `verification` (in core) | Person 3 | Claims, observed values, verdicts | Plain-language explanations of mismatches | Edit code, data or verdicts |
| Data Adaptation | `adaptation/` | Person 4 | Input contract, user data profile | Proposed changes (`changes.json`), positive-control request | Apply a meaning-changing change without approval |

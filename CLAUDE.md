# CLAUDE.md: shared rules for every Claude session on this repo

reCRATE turns a paper into an RO-Crate, verifies its claims, reuses its method on new data, and records every run as an RO-Crate. Read `docs/IMPLEMENTATION_PLAN.md` before changing anything structural.

## The one rule that matters most

**Verdicts come only from `recrate/core/verify.py`.** No agent, prompt or script may assign, edit or "fix" a verdict. Agents propose and explain; deterministic code decides.

## Who owns what

| Folder | Owner | Notes |
| --- | --- | --- |
| `agents/analysis/` | Person 1 | Paper → claims, gaps, input contract |
| `agents/discovery/`, `agents/execution/`, `recrate/runners/` | Person 2 | Resource map, environments, runs, patch ledger |
| `recrate/core/`, `recrate/orchestrator.py`, `recrate/plugins/tabular.py`, `schemas/`, `tests/` | Person 3 | Verifier, crates, gates, contracts |
| `agents/adaptation/`, `recrate/plugins/image.py`, `recrate/site.py`, `ui/` | Person 4 | Transfer, image plugin, results page |

Work inside your own folders. To change someone else's file or any file in `schemas/`, open a pull request and get the owner's review.

## Contracts between stages

Stages talk only through files. Each must validate against its schema before the next stage reads it:

| File | Schema | Written by |
| --- | --- | --- |
| Claim entities in `paper-crate/ro-crate-metadata.json` | `schemas/claim.schema.json` | Analysis |
| Gap entities | `schemas/gap.schema.json` | Analysis, Discovery |
| `work/observed-*.json` | `schemas/observed.schema.json` | Execution |
| `work/patches.json` | `schemas/patch.schema.json` | Execution (class filled by `core/classify.py`) |
| `work/independent-*.json` | `schemas/independent-check.schema.json` | Independent checks |
| `transfer/changes.json` | `schemas/change.schema.json` | Adaptation (class filled by `core/classify.py`) |

## Gates (enforced in code)

1. **Tolerance lock:** `recrate verify` refuses unlocked claims unless `--unlocked` is passed, and records which it was.
2. **Patch classification:** `core/classify.py` decides environment vs analysis. Analysis patches downgrade affected claims.
3. **Approval:** meaning-changing transfer changes need a recorded decision (`orchestrator.gate_approvals`).
4. **Positive control:** the paper's own data must reproduce before user results are released.

**The execution agent must never receive expected values.** Pass claims through `orchestrator.withhold_expected_values`.

## Before you push

- `python -m unittest discover -s tests -t .` passes. Never weaken a planted-error test to make it pass.
- Keep `recrate check` clean for every committed crate. If you change a file inside a crate, rebuild its metadata so checksums match.
- No secrets: tokens go in `.env` (git-ignored). No data files over 10 MB: download them at run time and record their sha256.
- Third-party files keep their licence; add them to `THIRD_PARTY.md`.

## Writing style for anything a user reads

Plain words, short sentences, specific numbers. Say "matches recorded outputs" when nothing was re-executed; never call that "reproduced". Say "reproducible", never "correct", unless an independent check supports it.

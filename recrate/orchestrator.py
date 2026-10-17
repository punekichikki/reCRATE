"""Runs the stages in order and enforces the gates in code, not in prompts.

Owner: Person 3. Stage owners fill in their stage functions; the orchestrator only checks
that each stage wrote valid files before the next one starts.

  analyse   (Person 1)  paper PDF -> claims, gaps, input contract in the paper crate
  discover  (Person 2)  repo -> resource map, file entities with sha256, environment hints
  lock      (gate 1)    a person confirms tolerances; claims hash written to claims.lock.json
  run       (Person 2)  environment + execution -> observed-*.json, patches.json
                        The execution agent is never given rc:expectedValue.
  verify    (Person 3)  deterministic verdicts -> run crate          [implemented]
  transfer  (Person 4)  user data -> changes (gate 3 approvals), positive control (gate 4), reuse crate
"""
import json
import os

from .core import crate as cr
from .core.classify import classify_change
from .core.verify import lock, lock_status


def _load_json(path):
    with open(path) as f:
        return json.load(f)


STAGES = ["analyse", "discover", "lock", "run", "verify", "transfer"]


def not_built(stage: str, owner: str):
    raise NotImplementedError(f"Stage '{stage}' is not built yet (owner: {owner}). See agents/{stage}/PROMPT.md "
                              "and docs/IMPLEMENTATION_PLAN.md.")


def analyse(paper_dir: str, pdf: str, repo: str = None, commit: str = None):
    not_built("analysis", "Person 1")


def discover(paper_dir: str):
    not_built("discovery", "Person 2")


def run(paper_dir: str, envs: list, runner: str = "local"):
    not_built("execution", "Person 2")


def transfer(paper_dir: str, data: str, approvals: str = None):
    not_built("adaptation", "Person 4")


# ---------------------------------------------------------------- gates
def gate_lock(crate_dir: str, confirmed_by: str) -> dict:
    """Gate 1. Call only after a person has reviewed every claim's tolerance."""
    return lock(crate_dir, confirmed_by)


def require_lock(crate_dir: str):
    info = lock_status(crate_dir, cr.load(crate_dir))
    if not info["locked"]:
        raise RuntimeError(f"Gate 1 not passed: {info['reason']}")
    return info


def withhold_expected_values(claims: list) -> list:
    """What the execution agent may see: which outputs to produce, never their expected values."""
    hidden = {"rc:expectedValue", "rc:tolerance", "rc:toleranceValue", "rc:decimalPlaces", "rc:condition"}
    return [{k: v for k, v in c.items() if k not in hidden} for c in claims]


def gate_approvals(changes: list, approvals_path: str = None, ask=input) -> list:
    """Gate 3. Routine changes pass; meaning-changing ones need a recorded decision.

    changes: [{"kind", "target", "description"}]. Decisions come from approvals.json
    ({"<kind>:<target>": {"decision": "approve"|"keep-original", "by", "reason"}}) or are asked for.
    """
    decided = _load_json(approvals_path) if approvals_path and os.path.exists(approvals_path) else {}
    out = []
    for ch in changes:
        ch = dict(ch, **{"class": classify_change(ch["kind"])})
        if ch["class"] == "meaning-changing":
            key = f"{ch['kind']}:{ch['target']}"
            d = decided.get(key)
            if d is None:
                answer = ask(f"Approve meaning-changing change [{key}] {ch['description']}? (approve/keep-original) ")
                who = ask("Your name: ")
                why = ask("Reason: ")
                d = {"decision": answer.strip() or "keep-original", "by": who, "reason": why}
            ch["approval"] = d
        out.append(ch)
    return out


def gate_positive_control(control_results: dict) -> bool:
    """Gate 4. The paper's own data must still reproduce in this environment before user results are released."""
    ok = {"reproduced", "independently-checked"}
    return bool(control_results) and all(r["verdict"] in ok for r in control_results.values())

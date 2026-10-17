"""Deterministic verifier: compare observed values with the claims in a paper crate and
write a run crate with one verdict per claim. No LLM is involved.

Owner: Person 3.

Inputs
  paper crate      claims (rc:expectedValue, rc:comparison, ...) and files with sha256
  observed files   JSON, one per run/environment (schemas/observed.schema.json)
  independent      JSON, one per independent check (schemas/independent-check.schema.json)
  patches          JSON list of patches applied during execution (schemas/patch.schema.json)
"""
import json
import operator
import os
import platform
import shutil
from datetime import datetime, timezone

from .. import __version__
from ..plugins import get_plugin
from . import crate as cr
from .classify import classify_patch


def _load_json(path):
    with open(path) as f:
        return json.load(f)


# Verdicts, strongest first.
INDEPENDENTLY_CHECKED = "independently-checked"
REPRODUCED = "reproduced"
REPRODUCED_PATCHED = "reproduced-after-analysis-changes"
MATCHES_RECORDED = "matches-recorded-outputs"
NEAR = "near"
MISMATCH = "mismatch"
INCONSISTENT_RECORDED = "inconsistent-with-recorded-outputs"
COULD_NOT_RUN = "could-not-run"
NOT_RUN = "not-run"

ORDER = [INDEPENDENTLY_CHECKED, REPRODUCED, REPRODUCED_PATCHED, MATCHES_RECORDED, NEAR,
         MISMATCH, INCONSISTENT_RECORDED, COULD_NOT_RUN, NOT_RUN]

LABELS = {
    INDEPENDENTLY_CHECKED: "Independently checked (reproduced, and an independent check agrees)",
    REPRODUCED: "Reproduced (re-executed, matches)",
    REPRODUCED_PATCHED: "Reproduced only after changes to analysis code",
    MATCHES_RECORDED: "Matches authors' recorded outputs (not re-executed)",
    NEAR: "Near (outside tolerance, within twice the tolerance)",
    MISMATCH: "Does not match (re-executed)",
    INCONSISTENT_RECORDED: "Paper disagrees with authors' recorded outputs",
    COULD_NOT_RUN: "Could not run",
    NOT_RUN: "Not run: no run in the required environment",
}

OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le,
       "==": operator.eq, "!=": operator.ne}

LOCK_FILE = "claims.lock.json"


class VerifyError(Exception):
    pass


# ---------------------------------------------------------------- gate 1: tolerance lock
def lock(crate_dir: str, locked_by: str) -> dict:
    doc = cr.load(crate_dir)
    info = {"claimsSha256": cr.claims_hash(doc), "lockedBy": locked_by,
            "lockedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "claims": [c["identifier"] for c in cr.claims(doc)]}
    with open(os.path.join(crate_dir, LOCK_FILE), "w") as f:
        json.dump(info, f, indent=2)
    return info


def lock_status(crate_dir: str, doc: dict) -> dict:
    path = os.path.join(crate_dir, LOCK_FILE)
    if not os.path.exists(path):
        return {"locked": False, "reason": "no claims.lock.json"}
    info = _load_json(path)
    if info.get("claimsSha256") != cr.claims_hash(doc):
        return {"locked": False, "reason": "claims changed after they were locked", **info}
    return {"locked": True, **info}


# ---------------------------------------------------------------- judging
def _env_matches(claim: dict, obs: dict) -> bool:
    req = claim.get("rc:requiresEnvironment") or {}
    env = obs.get("environment", {})
    return all(str(env.get(k)) == str(v) for k, v in req.items())


def _produced_by(claim: dict) -> list:
    p = claim.get("rc:producedBy", [])
    return p if isinstance(p, list) else [p]


def _judge(claim: dict, observations: list) -> dict:
    plugin = get_plugin(claim.get("rc:dataType"))
    key = claim["rc:outputKey"]
    candidates = [(p, o) for p, o in observations if _env_matches(claim, o)]
    usable = [(p, o) for p, o in candidates
              if o.get("status", "ok") == "ok" and plugin.has_outputs(o, key)]
    if not usable:
        blocked = [o for _, o in candidates if o.get("status") == "could-not-run"]
        if blocked:
            return {"verdict": COULD_NOT_RUN, "observed": None, "source": blocked[0].get("source"),
                    "evidence": None, "detail": blocked[0].get("reason", "")}
        return {"verdict": NOT_RUN, "observed": None, "source": None, "evidence": None, "detail": ""}
    usable.sort(key=lambda po: po[1].get("source") != "execution")  # prefer re-execution
    path, obs = usable[0]
    observed = plugin.extract(obs, key)
    cmp = plugin.compare(observed, claim)
    executed = obs.get("source") == "execution"
    if cmp.passed:
        verdict = REPRODUCED if executed else MATCHES_RECORDED
    elif cmp.near:
        verdict = NEAR
    else:
        verdict = MISMATCH if executed else INCONSISTENT_RECORDED
    return {"verdict": verdict, "observed": observed, "source": obs.get("source"),
            "evidence": os.path.basename(path), "detail": cmp.detail}


def _judge_derived(claim: dict, results: dict) -> dict:
    clauses = claim.get("rc:condition", [])
    deps = sorted({c["claim"] for c in clauses})
    dep_res = [results.get(d) for d in deps]
    if any(r is None for r in dep_res):
        raise VerifyError(f"{claim['identifier']} depends on unknown or later claims: {deps}")
    if any(r["observed"] is None for r in dep_res):
        blocked = any(r["verdict"] == COULD_NOT_RUN for r in dep_res)
        return {"verdict": COULD_NOT_RUN if blocked else NOT_RUN, "observed": None, "source": None,
                "evidence": "derived from " + ", ".join(deps), "detail": "an input claim has no observation"}
    parts, holds = [], True
    for c in clauses:
        v = results[c["claim"]]["observed"]
        if "index" in c:
            v = v[c["index"]]
        ok = OPS[c["op"]](v, c["value"])
        holds = holds and ok
        parts.append(f"{c['claim']}{'[' + str(c['index']) + ']' if 'index' in c else ''} = {v:.6g} {c['op']} {c['value']}: {ok}")
    executed = all(r["source"] == "execution" for r in dep_res)
    patched = any(r["verdict"] == REPRODUCED_PATCHED for r in dep_res)
    if holds:
        verdict = (REPRODUCED_PATCHED if patched else REPRODUCED) if executed else MATCHES_RECORDED
    else:
        verdict = MISMATCH if executed else INCONSISTENT_RECORDED
    return {"verdict": verdict, "observed": "; ".join(parts), "source": "execution" if executed else "shipped-outputs",
            "evidence": "derived from " + ", ".join(deps), "detail": "all conditions hold" if holds else "a condition fails"}


def judge_all(doc: dict, observations: list, independent: list = (), patches: list = ()) -> dict:
    claim_list = cr.claims(doc)
    analysis_files = [f for c in claim_list for f in _produced_by(c)]
    for p in patches:
        p["class"] = classify_patch(p["file"], analysis_files)
    analysis_patched = {os.path.normpath(p["file"]) for p in patches if p["class"] == "analysis"}

    results = {}
    for c in claim_list:  # direct claims first
        if c["rc:comparison"] == "derived":
            continue
        r = _judge(c, observations)
        touched = [f for f in _produced_by(c) if os.path.normpath(f) in analysis_patched]
        if r["verdict"] == REPRODUCED and touched:
            r["verdict"] = REPRODUCED_PATCHED
            r["detail"] += f"; analysis patches on {', '.join(touched)}"
        results[c["identifier"]] = r
    for c in claim_list:  # then derived claims
        if c["rc:comparison"] == "derived":
            results[c["identifier"]] = _judge_derived(c, results)

    for _, chk in independent:
        r = results.get(chk["about"])
        if r is None:
            continue
        r.setdefault("checks", []).append(chk)
        if r["verdict"] == REPRODUCED and chk["outcome"] == "robust":
            r["verdict"] = INDEPENDENTLY_CHECKED
    return results


# ---------------------------------------------------------------- run crate
def _read(paths):
    out = []
    for p in paths:
        with open(p) as f:
            out.append((p, json.load(f)))
    return out


def verify(crate_dir: str, run_dir: str, observed_paths, independent_paths=(), patches_path=None,
           allow_unlocked: bool = False, check_integrity: bool = True) -> dict:
    if check_integrity:
        problems = cr.check(crate_dir)
        if problems:
            raise VerifyError("paper crate failed integrity checks: " + "; ".join(problems))
    doc = cr.load(crate_dir)
    lock_info = lock_status(crate_dir, doc)
    if not lock_info["locked"] and not allow_unlocked:
        raise VerifyError(f"claims are not locked ({lock_info['reason']}). Run `recrate lock` first, "
                          "or pass --unlocked to record an unlocked run.")

    observations = _read(observed_paths)
    independent = _read(independent_paths)
    patches = _load_json(patches_path) if patches_path else []
    results = judge_all(doc, observations, independent, patches)
    _write_run_crate(crate_dir, run_dir, doc, results, observations, independent, patches, patches_path, lock_info)
    return results


def _write_run_crate(crate_dir, run_dir, doc, results, observations, independent, patches, patches_path, lock_info):
    os.makedirs(run_dir, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    paper = cr.entities(doc)["./"]
    meta_hash = cr.sha256_file(os.path.join(crate_dir, cr.METADATA))
    graph, files, actions = [], [], []

    copied = [p for p, _ in observations + independent] + ([patches_path] if patches_path else [])
    for p in copied:
        name = os.path.basename(p)
        shutil.copy(p, os.path.join(run_dir, name))
        files.append({"@id": name, "@type": "File", "encodingFormat": "application/json",
                      "sha256": cr.sha256_file(p), "contentSize": str(os.path.getsize(p))})

    for i, (p, o) in enumerate(observations, 1):
        env = o.get("environment", {})
        env_id = "#env-" + "-".join(f"{k}-{v}" for k, v in sorted(env.items())).replace(" ", "_")
        graph.append({"@id": env_id, "@type": "SoftwareApplication",
                      "name": ", ".join(f"{k} {v}" for k, v in sorted(env.items())) or "unrecorded environment"})
        executed = o.get("source") == "execution"
        actions.append({
            "@id": f"#action-{i}", "@type": "CreateAction",
            "name": ("Re-executed the analysis" if executed else "Read authors' recorded outputs") + f" ({graph[-1]['name']})",
            "description": o.get("description", ""),
            "actionStatus": {"@id": "http://schema.org/CompletedActionStatus" if o.get("status", "ok") == "ok"
                             else "http://schema.org/FailedActionStatus"},
            "object": {"@id": "#paper-crate"}, "result": {"@id": os.path.basename(p)},
            "environment": {"@id": env_id}, "endTime": o.get("endTime", now),
            **({"error": o["reason"]} if o.get("status") == "could-not-run" else {}),
            **({"rc:runner": o["runner"]} if "runner" in o else {}),
        })

    for chk_path, chk in independent:
        actions.append({
            "@id": f"#check-{chk['check']}", "@type": "CreateAction", "additionalType": "rc:IndependentCheck",
            "name": f"Independent check {chk['check']} of claim {chk['about']}", "description": chk.get("method", ""),
            "object": {"@id": "#paper-crate"}, "result": {"@id": os.path.basename(chk_path)},
            "rc:outcome": chk["outcome"], "rc:summary": chk.get("summary", ""), "endTime": now})

    for j, pt in enumerate(patches, 1):
        actions.append({"@id": f"#patch-{j}", "@type": "UpdateAction", "additionalType": pt["class"],
                        "name": f"Patch to {pt['file']}", "description": pt.get("reason", ""),
                        "rc:file": pt["file"], **({"rc:diff": pt["diff"]} if "diff" in pt else {})})

    verdicts = []
    for c in cr.claims(doc):
        r = results[c["identifier"]]
        v = {"@id": f"#verdict-{c['identifier']}", "@type": "PropertyValue",
             "name": f"{c['identifier']}: {c['name']}", "about": {"@id": c["@id"]},
             "value": r["verdict"], "description": LABELS[r["verdict"]],
             "rc:expectedValue": c.get("rc:expectedValue"), "rc:observedValue": r["observed"],
             "rc:tolerance": c.get("rc:tolerance"), "rc:evidence": r["evidence"], "rc:detail": r["detail"]}
        if r.get("checks"):
            v["rc:independentCheck"] = [{"@id": f"#check-{x['check']}"} for x in r["checks"]]
        verdicts.append(v)
        graph.append({"@id": c["@id"], "@type": "Claim", "identifier": c["identifier"], "name": c["name"],
                      "isPartOf": {"@id": "#paper-crate"}})

    counts = {}
    for r in results.values():
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    root = {
        "@id": "./", "@type": "Dataset", "name": f"Verification run: {paper.get('name', 'paper crate')}",
        "description": "Per-claim verdicts. " + "; ".join(f"{LABELS[k]}: {n}" for k, n in sorted(counts.items(), key=lambda kv: ORDER.index(kv[0]))),
        "datePublished": now, "license": {"@id": "https://spdx.org/licenses/MIT"},
        "conformsTo": [{"@id": cr.PROCESS_RUN_CRATE_ENTITY["@id"]}, {"@id": "#recrate-profile"}],
        "isBasedOn": {"@id": "#paper-crate"},
        "hasPart": [{"@id": f["@id"]} for f in files],
        "mentions": [{"@id": a["@id"]} for a in actions] + [{"@id": v["@id"]} for v in verdicts],
        "rc:claimsSha256": cr.claims_hash(doc),
        "rc:claimsLocked": lock_info["locked"],
        **({"rc:claimsLockedBy": lock_info["lockedBy"]} if lock_info.get("locked") else
           {"rc:unlockedReason": lock_info.get("reason", "")}),
    }
    graph += [
        cr.PROCESS_RUN_CRATE_ENTITY, cr.PROFILE_ENTITY,
        {"@id": "#paper-crate", "@type": "Dataset", "name": paper.get("name"),
         "description": f"Paper crate checked by this run. sha256 of its {cr.METADATA}: {meta_hash}",
         "isBasedOn": paper.get("isBasedOn")},
        {"@id": "#verifier", "@type": "SoftwareApplication", "name": "recrate.core.verify",
         "softwareVersion": __version__, "description": f"Python {platform.python_version()}"},
    ]
    cr.write(run_dir, root, files + actions + verdicts + graph)


def summary(results: dict, doc: dict) -> str:
    lines = [f"{'Claim':6} {'Verdict':60} Observed"]
    for c in cr.claims(doc):
        r = results[c["identifier"]]
        obs = r["observed"] if r["observed"] is not None else r["detail"]
        lines.append(f"{c['identifier']:6} {LABELS[r['verdict']]:60} {obs}")
        for chk in r.get("checks", []):
            lines.append(f"{'':6} independent check {chk['check']}: {chk['outcome']} - {chk.get('summary', '')[:90]}")
    return "\n".join(lines)

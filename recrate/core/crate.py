"""Read, check and write RO-Crates (paper crates and run crates).

JSON-LD is written directly so there is no runtime dependency on RO-Crate libraries;
tests run structural checks, and `rocrate-validator` can be run where it installs.
"""
import hashlib
import json
import os

from .. import PROCESS_RUN_CRATE, RC_NAMESPACE, RO_CRATE_CONTEXT, WFRUN_CONTEXT

METADATA = "ro-crate-metadata.json"


class CrateError(Exception):
    pass


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(crate_dir: str) -> dict:
    with open(os.path.join(crate_dir, METADATA)) as f:
        return json.load(f)


def entities(doc: dict) -> dict:
    return {e["@id"]: e for e in doc["@graph"]}


def _types(e: dict) -> list:
    t = e.get("@type", [])
    return t if isinstance(t, list) else [t]


def claims(doc: dict) -> list:
    return [e for e in doc["@graph"] if "Claim" in _types(e)]


def claims_hash(doc: dict) -> str:
    """sha256 over the claims as they will be judged (canonical JSON). Recorded by the lock gate."""
    canon = json.dumps(sorted(claims(doc), key=lambda c: c["@id"]), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def check(crate_dir: str, verify_checksums: bool = True) -> list:
    """Structural checks. Returns a list of problems (empty = fine)."""
    problems = []
    try:
        doc = load(crate_dir)
    except (OSError, json.JSONDecodeError) as e:
        return [f"cannot read {METADATA}: {e}"]
    graph = doc.get("@graph", [])
    ids = [e.get("@id") for e in graph]
    if len(ids) != len(set(ids)):
        problems.append("duplicate @id values")
    ents = entities(doc)
    desc = ents.get(METADATA)
    if not desc:
        problems.append("missing metadata descriptor")
        return problems
    root_id = desc.get("about", {}).get("@id")
    root = ents.get(root_id)
    if not root:
        problems.append("metadata descriptor does not point to a root dataset")
        return problems
    for key in ("name", "description", "datePublished", "license"):
        if key not in root:
            problems.append(f"root dataset lacks {key}")
    for part in root.get("hasPart", []):
        pid = part["@id"]
        if pid.startswith(("http://", "https://", "#")):
            continue
        path = os.path.join(crate_dir, pid)
        if not os.path.exists(path):
            problems.append(f"listed file missing: {pid}")
            continue
        want = ents.get(pid, {}).get("sha256")
        if verify_checksums and want and os.path.isfile(path) and sha256_file(path) != want:
            problems.append(f"checksum mismatch: {pid}")

    def walk(v):
        if isinstance(v, dict):
            if set(v) == {"@id"} and v["@id"].startswith("#") and v["@id"] not in ents:
                problems.append(f"dangling reference: {v['@id']}")
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(graph)
    return problems


def context(extra: dict = None) -> list:
    local = {"rc": RC_NAMESPACE, "Claim": "http://schema.org/Claim", "appearance": "http://schema.org/appearance"}
    local.update(extra or {})
    return [RO_CRATE_CONTEXT, WFRUN_CONTEXT, local]


def write(crate_dir: str, root: dict, graph: list) -> str:
    """Write a crate. `root` is the root dataset entity; `graph` holds every other entity."""
    os.makedirs(crate_dir, exist_ok=True)
    descriptor = {"@id": METADATA, "@type": "CreativeWork",
                  "conformsTo": {"@id": "https://w3id.org/ro/crate/1.2"}, "about": {"@id": "./"}}
    seen, out = set(), []
    for e in [descriptor, root] + graph:
        if e["@id"] in seen:
            continue
        seen.add(e["@id"])
        out.append(e)
    doc = {"@context": context(), "@graph": out}
    path = os.path.join(crate_dir, METADATA)
    with open(path, "w") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    return path


PROCESS_RUN_CRATE_ENTITY = {"@id": PROCESS_RUN_CRATE, "@type": "CreativeWork", "name": "Process Run Crate", "version": "0.5"}
PROFILE_ENTITY = {"@id": "#recrate-profile", "@type": ["CreativeWork", "Profile"],
                  "name": "reCRATE profile (draft 0.1): claims, gaps, input contract, verdicts"}

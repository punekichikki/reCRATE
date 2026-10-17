"""Build the static results site: ui/index.html plus data.js holding real paper and run crates.

data.js is a plain script (window.RECRATE_DATA = {...}), so the page also opens straight from
disk without a web server. The page only displays verdicts; it never computes them.

Owner: Person 4.
"""
import glob
import json
import os
import shutil
from datetime import datetime, timezone

from .core import crate as cr

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(REPO_ROOT, "ui", "index.html")


def collect(roots) -> list:
    """Find <root>/<paper-id>/paper-crate and its <root>/<paper-id>/runs/*/ run crates."""
    papers = []
    for root in roots:
        for paper_dir in sorted(glob.glob(os.path.join(root, "*", ""))):
            pc = os.path.join(paper_dir, "paper-crate")
            if not os.path.exists(os.path.join(pc, cr.METADATA)):
                continue
            problems = cr.check(pc)
            if problems:
                raise ValueError(f"{pc} failed checks: {'; '.join(problems)}")
            runs = []
            for run_meta in sorted(glob.glob(os.path.join(paper_dir, "runs", "*", cr.METADATA))):
                run_dir = os.path.dirname(run_meta)
                problems = cr.check(run_dir)
                if problems:
                    raise ValueError(f"{run_dir} failed checks: {'; '.join(problems)}")
                runs.append({"id": os.path.basename(run_dir), "crate": cr.load(run_dir)})
            papers.append({"id": os.path.basename(os.path.normpath(paper_dir)), "paperCrate": cr.load(pc),
                           "runs": list(reversed(runs))})  # newest run first
    return papers


def build(out_dir: str = "site", roots=("examples",), template: str = TEMPLATE) -> dict:
    if not os.path.exists(template):
        raise FileNotFoundError(f"page template not found: {template} (run from a clone of the repository)")
    papers = collect(roots)
    os.makedirs(out_dir, exist_ok=True)
    shutil.copy(template, os.path.join(out_dir, "index.html"))
    data = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "papers": papers}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")  # safe inside a script
    with open(os.path.join(out_dir, "data.js"), "w") as f:
        f.write("window.RECRATE_DATA = " + payload + ";\n")
    return {"papers": len(papers), "runs": sum(len(p["runs"]) for p in papers), "out": out_dir}

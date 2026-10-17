"""`recrate` command line. Stages that are not built yet say who owns them."""
import argparse
import json
import sys

from . import orchestrator
from .core import crate as cr
from .core.verify import LABELS, VerifyError, summary, verify


def cmd_verify(a):
    try:
        results = verify(a.crate, a.out, a.observed, a.independent or [], a.patches,
                         allow_unlocked=a.unlocked, check_integrity=not a.skip_integrity)
    except VerifyError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(summary(results, cr.load(a.crate)))
    print(f"\nRun crate written to {a.out}/{cr.METADATA}")
    return 0


def cmd_lock(a):
    info = orchestrator.gate_lock(a.crate, a.by)
    print(f"Locked {len(info['claims'])} claims (sha256 {info['claimsSha256'][:12]}...) by {info['lockedBy']}")
    return 0


def cmd_check(a):
    problems = cr.check(a.crate)
    for p in problems:
        print("problem:", p)
    print("ok" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


def cmd_report(a):
    doc = cr.load(a.run)
    rows = [e for e in doc["@graph"] if e.get("@id", "").startswith("#verdict-")]
    print(cr.entities(doc)["./"]["description"])
    for v in rows:
        print(f"- {v['name']}\n    {v['description']}; observed: {json.dumps(v.get('rc:observedValue'))}")
    return 0


def cmd_site(a):
    from .site import build
    try:
        info = build(a.out, a.roots)
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"Built {info['out']}/index.html with {info['papers']} paper(s) and {info['runs']} run(s). "
          f"Open it in a browser; no server needed.")
    return 0


def cmd_stub(stage):
    def run(a):
        try:
            {"analyse": lambda: orchestrator.analyse(a.paper, None),
             "discover": lambda: orchestrator.discover(a.paper),
             "run": lambda: orchestrator.run(a.paper, []),
             "transfer": lambda: orchestrator.transfer(a.paper, None)}[stage]()
        except NotImplementedError as e:
            print(e, file=sys.stderr)
            return 2
        return 0
    return run


def main(argv=None):
    p = argparse.ArgumentParser(prog="recrate", description="Verify a paper's claims and record every run as an RO-Crate.")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="compare observed values with the paper crate's claims; write a run crate")
    v.add_argument("crate", help="paper crate directory")
    v.add_argument("--observed", nargs="+", required=True, help="observed-value JSON files")
    v.add_argument("--independent", nargs="*", help="independent-check JSON files")
    v.add_argument("--patches", help="patches.json applied during execution")
    v.add_argument("--out", required=True, help="run crate directory to write")
    v.add_argument("--unlocked", action="store_true", help="allow claims that were never locked (recorded in the run crate)")
    v.add_argument("--skip-integrity", action="store_true", help="skip file and checksum checks (not recommended)")
    v.set_defaults(func=cmd_verify)

    lk = sub.add_parser("lock", help="gate 1: record that a person confirmed every tolerance")
    lk.add_argument("crate")
    lk.add_argument("--by", required=True, help="name of the person confirming")
    lk.set_defaults(func=cmd_lock)

    ck = sub.add_parser("check", help="structural and checksum checks on a crate")
    ck.add_argument("crate")
    ck.set_defaults(func=cmd_check)

    rp = sub.add_parser("report", help="print the verdicts in a run crate")
    rp.add_argument("run")
    rp.set_defaults(func=cmd_report)

    st = sub.add_parser("site", help="build the results page from paper and run crates")
    st.add_argument("--roots", nargs="+", default=["examples"], help="folders holding <paper-id>/paper-crate and runs/")
    st.add_argument("--out", default="site", help="output folder (default: site)")
    st.set_defaults(func=cmd_site)

    for stage, helptext in [("analyse", "paper -> claims, gaps, input contract (Person 1)"),
                            ("discover", "repo -> resource map, files, environment hints (Person 2)"),
                            ("run", "build environment and execute (Person 2)"),
                            ("transfer", "apply the method to new data (Person 4)")]:
        s = sub.add_parser(stage, help=helptext)
        s.add_argument("paper", help="working folder for the paper")
        s.set_defaults(func=cmd_stub(stage))

    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())

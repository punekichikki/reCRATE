"""Read the outputs the authors recorded in their repository (no re-execution).

Writes one observed-*.json per R version, in the same format repro/run_claims.R writes,
so the verifier treats both the same way but labels these 'shipped outputs'.
Usage (from this folder): python scripts/observed_from_shipped.py paper-crate work
"""
import csv, json, os, re, sys

crate, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

for tag, version in (("35", "3.5.0"), ("36", "3.6.1")):
    md = open(os.path.join(crate, f"R/random{tag}.md")).read()
    draws = [int(v) for v in re.search(r"\[1\]\s+([\d\s]+)\n", md).group(1).split()]
    rows = list(csv.DictReader(open(os.path.join(crate, f"data/bcis-{version}.csv"))))
    seed2 = next(r for r in rows if r["seed"] == "2")
    obs = {
        "source": "shipped-outputs",
        "status": "ok",
        "description": f"Authors' recorded outputs: R/random{tag}.md and data/bcis-{version}.csv (seed 2). Not re-executed.",
        "environment": {"r_version": version},
        "outputs": {"random_draws": draws, "boot_ci_lower": float(seed2["lower"]),
                    "boot_ci_upper": float(seed2["upper"])},
        "evidenceFiles": [f"R/random{tag}.md", f"data/bcis-{version}.csv"],
    }
    path = os.path.join(out, f"observed-shipped-{version}.json")
    json.dump(obs, open(path, "w"), indent=2)
    print("Wrote", path)

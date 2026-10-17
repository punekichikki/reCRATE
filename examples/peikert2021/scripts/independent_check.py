"""Independent check of claim C5 without the authors' code or R.

Re-implements the analysis in Python (OLS slope, BCa bootstrap via SciPy) and asks:
does the CI exclude zero consistently, or does it depend on the random seed?
Usage (from this folder): python scripts/independent_check.py paper-crate work [n_seeds]   (needs numpy, scipy)
"""
import csv, json, os, platform, sys
import numpy as np
import scipy
from scipy import stats

crate, out = sys.argv[1], sys.argv[2]
n_seeds = int(sys.argv[3]) if len(sys.argv) > 3 else 200
os.makedirs(out, exist_ok=True)

d = np.genfromtxt(os.path.join(crate, "data/pathological-example2.csv"), delimiter=",", names=True)
x, y = d["x"], d["y"]
fit = stats.linregress(x, y)
t = stats.t.ppf(0.975, len(x) - 2)


def slope(xs, ys, axis=-1):
    xm, ym = xs.mean(axis=axis, keepdims=True), ys.mean(axis=axis, keepdims=True)
    return ((xs - xm) * (ys - ym)).sum(axis=axis) / ((xs - xm) ** 2).sum(axis=axis)


lows = []
for s in range(n_seeds):
    r = stats.bootstrap((x, y), slope, paired=True, vectorized=True, n_resamples=1000,
                        method="BCa", confidence_level=0.95, random_state=np.random.default_rng(s))
    lows.append(float(r.confidence_interval.low))
lows = np.array(lows)

shipped = {}
for v in ("3.5.0", "3.6.1"):
    rows = list(csv.DictReader(open(os.path.join(crate, f"data/bcis-{v}.csv"))))
    shipped[v] = {"seeds": len(rows), "excludes_zero": sum(float(r["lower"]) > 0 for r in rows)}

frac = float((lows > 0).mean())
result = {
    "check": "I1",
    "about": "C5",
    "method": f"Python re-implementation: OLS slope; SciPy BCa bootstrap, 1,000 resamples, {n_seeds} seeds",
    "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
    "results": {
        "n": int(len(x)),
        "ols_slope": round(float(fit.slope), 4),
        "ols_p_value": round(float(fit.pvalue), 4),
        "t_ci_95": [round(float(fit.slope - t * fit.stderr), 4), round(float(fit.slope + t * fit.stderr), 4)],
        "bca_runs": n_seeds,
        "bca_runs_excluding_zero": int((lows > 0).sum()),
        "bca_fraction_excluding_zero": round(frac, 3),
        "bca_lower_bound_q05_median_q95": [round(float(q), 4) for q in np.quantile(lows, [0.05, 0.5, 0.95])],
        "authors_csv_seeds_excluding_zero": shipped,
    },
    "outcome": "fragile" if 0.1 < frac < 0.9 else "robust",
    "summary": (
        f"The slope is borderline (p = {fit.pvalue:.3f}; classical CI {fit.slope - t * fit.stderr:.4f} to "
        f"{fit.slope + t * fit.stderr:.4f}). An independent BCa bootstrap excludes zero in "
        f"{frac:.0%} of {n_seeds} seeds. In the authors' own CSVs the CI excludes zero for "
        f"{shipped['3.5.0']['excludes_zero']}/10 seeds under R 3.5.0 and "
        f"{shipped['3.6.1']['excludes_zero']}/10 under R 3.6.1. The numbers do change with the R version, "
        "but whether the CI excludes zero depends on the seed in both versions."
    ),
}
path = os.path.join(out, "independent-I1.json")
json.dump(result, open(path, "w"), indent=2)
print("Wrote", path)
print(result["summary"])

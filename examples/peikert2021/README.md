# Example: Peikert & Brandmaier (2021)

The first paper taken through the pipeline. The paper argues that Git and R Markdown alone do not make an analysis reproducible, and shows seeded R code giving different results in R 3.5.0 and R 3.6.1.

- Paper: Peikert & Brandmaier (2021), *A Reproducible Data Analysis Workflow With R Markdown, Git, Make, and Docker*, Quantitative and Computational Methods in Behavioral Sciences. https://doi.org/10.5964/qcmb.3763
- Code: https://github.com/aaronpeikert/reproducible-research (commit `12d9969`), CC BY 4.0

## What is here

```
paper-crate/          the paper as an RO-Crate: authors' files with sha256, 5 claims, 5 gaps, input contract
  repro/run_claims.R  runner added by reCRATE; re-executes the claim computations, writes observed JSON
work/                 observed values read from the authors' recorded outputs; independent check result
runs/run-01-shipped-outputs/   run crate written by `recrate verify`
scripts/              build_crate.py, observed_from_shipped.py, independent_check.py
```

## Claims

| ID | Claim | Expected | Compared by |
| --- | --- | --- | --- |
| C1 | `set.seed(1234); sample(1:10, 5)` in R 3.5.0 | 2 6 5 8 9 | exact |
| C2 | Same code in R 3.6.1 | 10 6 5 4 1 | exact |
| C3 | Bootstrap BCa 95% CI of the slope, R 3.5.0 | 0.0097 to 0.3842 | rounding to 4 decimals |
| C4 | Same, R 3.6.1 | −0.0005 to 0.3748 | rounding to 4 decimals |
| C5 | CI excludes zero in R 3.5.0 but not in R 3.6.1 | lower(3.5.0) > 0, lower(3.6.1) ≤ 0 | derived from C3, C4 |

Tolerances were proposed from the reported precision and are **not yet confirmed by a person**, so run-01 was recorded with `--unlocked`.

## Results so far (run-01)

- **C1–C5 match the authors' own recorded outputs** (`R/random35.md`, `R/random36.md`, `data/bcis-*.csv`). Nothing has been re-executed yet, so the verdict is "matches recorded outputs", not "reproduced".
- **Independent check I1 on C5: fragile.** A Python re-implementation (SciPy BCa bootstrap, 200 seeds) excludes zero in 46% of runs; the OLS p-value is 0.058. In the authors' CSVs the CI excludes zero for 7 of 10 seeds in R 3.5.0 and 3 of 10 in R 3.6.1. The numbers do change with the R version, which is the paper's point, but the yes/no conclusion depends on the seed in both versions. The seed shown in the paper was chosen by search (gap G2) on deliberately borderline data (G3); the authors did this on purpose to illustrate the effect.
- **Gaps:** G1 the Dockerfile uses Microsoft MRAN, retired in 2023 · G2 seed selected by search · G3 borderline simulated data · G4 Windows path in the Makefile · G5 crate built from the latest commit, the paper cites `c4213f6`.

## Reproduce run-01

From the repository root:

```bash
python examples/peikert2021/scripts/build_crate.py
cd examples/peikert2021
python scripts/observed_from_shipped.py paper-crate work
python scripts/independent_check.py paper-crate work 200      # needs numpy, scipy
cd ../..
recrate verify examples/peikert2021/paper-crate \
  --observed examples/peikert2021/work/observed-shipped-3.5.0.json examples/peikert2021/work/observed-shipped-3.6.1.json \
  --independent examples/peikert2021/work/independent-I1.json \
  --out examples/peikert2021/runs/run-01-shipped-outputs --unlocked
```

## Next: re-execute in real R (run-02)

**Lock the tolerances first** (gate 1), after a person has read every claim:

```bash
recrate lock examples/peikert2021/paper-crate --by "Your Name"
```

**With local Docker**, from `examples/peikert2021/`:

```bash
docker run --rm -v "$PWD":/w -w /w/paper-crate rocker/r-ver:3.5.0 Rscript repro/run_claims.R /w/work/obs-3.5.0.json
docker run --rm -v "$PWD":/w -w /w/paper-crate rocker/r-ver:3.6.1 Rscript repro/run_claims.R /w/work/obs-3.6.1.json
```

**With Hugging Face Jobs** (no local Docker needed; costs about a cent on `cpu-basic`). A Job cannot see local files, so it downloads this repository and prints the observed JSON to its logs. Untested sketch:

```bash
hf jobs run rocker/r-ver:3.5.0 Rscript -e "download.file('https://github.com/punekichikki/reCRATE/archive/refs/heads/main.tar.gz', 'r.tgz'); untar('r.tgz'); setwd('reCRATE-main/examples/peikert2021/paper-crate'); source('repro/run_claims.R')" 
```

`run_claims.R` reads its output path from the command line; when sourced as above it writes `observed.json` in the job's working folder. Have it print the file (or upload it to a dataset repo) and save it as `work/obs-3.5.0.json`.

Then verify (no `--unlocked` needed once locked):

```bash
recrate verify examples/peikert2021/paper-crate --observed examples/peikert2021/work/obs-3.5.0.json examples/peikert2021/work/obs-3.6.1.json \
  --independent examples/peikert2021/work/independent-I1.json --out examples/peikert2021/runs/run-02-r-executed
```

If both match, C1–C5 move to "Reproduced". Two more runs worth recording:

- **A later R version** (`rocker/r-ver:4.4.1`): the sampling change persists, so it should match the 3.6.1 values. It needs its own claims or an environment note, since C2/C4 require exactly 3.6.1.
- **Old sampling restored**: `Rscript repro/run_claims.R out.json rounding` in R ≥ 3.6. If it recovers the 3.5.0 numbers, record it as an environment setting, not an analysis change.

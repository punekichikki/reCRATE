# run_claims.R — added by reCRATE (not part of the authors' repository).
# Re-executes the computations behind claims C1–C4 using the authors' own code
# logic (R/random.R and R/bootstrap.R) and writes the observed values as JSON.
#
# Usage (from the crate root):
#   Rscript repro/run_claims.R observed.json            # default RNG settings
#   Rscript repro/run_claims.R observed.json rounding   # R >= 3.6: restore pre-3.6 sampling
#
# Suggested environments:
#   docker run --rm -v "$PWD":/crate -w /crate rocker/r-ver:3.5.0 Rscript repro/run_claims.R obs-3.5.0.json
#   docker run --rm -v "$PWD":/crate -w /crate rocker/r-ver:3.6.1 Rscript repro/run_claims.R obs-3.6.1.json
# The boot package ships with R as a recommended package, so nothing else is installed.

args <- commandArgs(trailingOnly = TRUE)
out <- if (length(args) >= 1) args[1] else "observed.json"
rounding <- length(args) >= 2 && args[2] == "rounding"
if (rounding) suppressWarnings(RNGkind(sample.kind = "Rounding"))

suppressMessages(library(boot))
r_version <- paste(R.version$major, R.version$minor, sep = ".")

# C1 / C2 — from R/random.R
set.seed(1234)
draws <- sample(1:10, 5)

# C3 / C4 — from R/bootstrap.R (seed 2 is the seed the authors' script selects)
simdata <- read.csv("data/pathological-example2.csv")
bs <- function(formula, data, indices) coef(lm(formula, data = data[indices, ]))
set.seed(2)
res <- boot(data = simdata, statistic = bs, R = 1000, formula = y ~ 1 + x)
ci <- boot.ci(res, conf = 0.95, type = "bca", index = 2)$bca[4:5]

kinds <- RNGkind()
sample_kind <- if (length(kinds) >= 3) kinds[3] else "Rounding"  # R < 3.6 has only the old behaviour

json <- sprintf(
  '{\n  "source": "execution",\n  "description": "Rscript repro/run_claims.R%s",\n  "environment": {"r_version": "%s", "rng_sample_kind": "%s"},\n  "outputs": {\n    "random_draws": [%s],\n    "boot_ci_lower": %.10f,\n    "boot_ci_upper": %.10f\n  }\n}\n',
  if (rounding) " rounding" else "", r_version, sample_kind,
  paste(draws, collapse = ", "), ci[1], ci[2])
writeLines(json, out)
cat("Wrote", out, "for R", r_version, "\n")

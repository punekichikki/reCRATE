"""Build the paper crate for Peikert & Brandmaier (2021).

Stands in for the Analyse and Discover stages until those agents exist: the claims, gaps and
resource links below were extracted by hand (with Claude) from the paper and repository.
Usage (from the repo root): python examples/peikert2021/scripts/build_crate.py
"""
import os
from datetime import date

from recrate.core import crate as cr

HERE = os.path.dirname(os.path.abspath(__file__))
CRATE = os.path.join(HERE, "..", "paper-crate")
REPO = "https://github.com/aaronpeikert/reproducible-research"
COMMIT = "12d9969c4d8745bb947b9aed765f5451cdaf999b"
PAPER = "https://doi.org/10.5964/qcmb.3763"
CC_BY = {"@id": "https://spdx.org/licenses/CC-BY-4.0"}
MIT = {"@id": "https://spdx.org/licenses/MIT"}

FILES = {
    # path: (description, encodingFormat, origin)
    "Dockerfile": ("Authors' container recipe (rocker/verse:3.6.1 + MRAN snapshot 2020-01-01)", "text/plain", "authors"),
    "Makefile": ("Authors' build recipe: make build, make all DOCKER=TRUE", "text/x-makefile", "authors"),
    "manuscript.Rmd": ("Authors' R Markdown manuscript; claims C1-C5 are in lines 192-233", "text/markdown", "authors"),
    "R/random.R": ("Seeded sample(1:10, 5) example", "text/x-r", "authors"),
    "R/bootstrap.R": ("Bootstrap BCa CI for the regression slope; selects the seed", "text/x-r", "authors"),
    "R/bootstrap-data.R": ("Generates the simulated data set (true slope 0.225, n = 100)", "text/x-r", "authors"),
    "R/random35.md": ("Authors' recorded output of random.R under R 3.5.0", "text/markdown", "authors"),
    "R/random36.md": ("Authors' recorded output of random.R under R 3.6.1", "text/markdown", "authors"),
    "R/bootstrap35.md": ("Authors' recorded output of bootstrap.R under R 3.5.0", "text/markdown", "authors"),
    "R/bootstrap36.md": ("Authors' recorded output of bootstrap.R under R 3.6.1", "text/markdown", "authors"),
    "data/pathological-example2.csv": ("Simulated data: columns x, y; 100 rows", "text/csv", "authors"),
    "data/bcis-3.5.0.csv": ("Authors' precomputed BCa CIs for seeds 1-10 under R 3.5.0", "text/csv", "authors"),
    "data/bcis-3.6.1.csv": ("Authors' precomputed BCa CIs for seeds 1-10 under R 3.6.1", "text/csv", "authors"),
    "repro/run_claims.R": ("Runner added by reCRATE: re-executes the claim computations and writes observed values as JSON", "text/x-r", "tool"),
}

PENDING = "proposed by analysis (manual, with Claude) from reported precision; awaiting confirmation"


def file_entity(rel, desc, fmt, origin):
    p = os.path.join(CRATE, rel)
    e = {"@id": rel, "@type": "File", "name": os.path.basename(rel), "description": desc, "encodingFormat": fmt,
         "contentSize": str(os.path.getsize(p)), "sha256": cr.sha256_file(p)}
    if origin == "authors":
        e.update({"isPartOf": {"@id": REPO}, "license": CC_BY})
    else:
        e.update({"creator": {"@id": "#recrate-agent"}, "license": MIT})
    return e


def claim(cid, text, location, **fields):
    return {"@id": f"#claim-{cid}", "@type": "Claim", "identifier": cid, "name": text,
            "rc:claimLocation": location, "rc:dataType": "tabular", "rc:toleranceSetBy": PENDING,
            "appearance": {"@id": PAPER}, "creator": {"@id": "#recrate-agent"}, **fields}


def gap(gid, text, severity, evidence):
    return {"@id": f"#gap-{gid}", "@type": "rc:Gap", "identifier": gid, "name": text,
            "rc:severity": severity, "rc:evidence": evidence, "creator": {"@id": "#recrate-agent"}}


claims = [
    claim("C1", "set.seed(1234); sample(1:10, 5) returns 2 6 5 8 9 under R 3.5.0",
          "manuscript.Rmd l.196-210 (seed example, R 3.5.0)",
          **{"rc:expectedValue": [2, 6, 5, 8, 9], "rc:comparison": "exact", "rc:tolerance": "exact match",
             "rc:requiresEnvironment": {"r_version": "3.5.0"}, "rc:outputKey": "random_draws",
             "rc:producedBy": "R/random.R"}),
    claim("C2", "set.seed(1234); sample(1:10, 5) returns 10 6 5 4 1 under R 3.6.1",
          "manuscript.Rmd l.210-220 (seed example, R 3.6.1)",
          **{"rc:expectedValue": [10, 6, 5, 4, 1], "rc:comparison": "exact", "rc:tolerance": "exact match",
             "rc:requiresEnvironment": {"r_version": "3.6.1"}, "rc:outputKey": "random_draws",
             "rc:producedBy": "R/random.R"}),
    claim("C3", "Bootstrap 95% BCa CI for the slope is 0.0097 to 0.3842 under R 3.5.0",
          "manuscript.Rmd l.220-227 (bootstrap example, R 3.5.0)",
          **{"rc:expectedValue": [0.0097, 0.3842], "rc:comparison": "rounded", "rc:decimalPlaces": 4,
             "rc:tolerance": "equal after rounding to 4 decimals (as reported)",
             "rc:requiresEnvironment": {"r_version": "3.5.0"}, "rc:outputKey": ["boot_ci_lower", "boot_ci_upper"],
             "rc:producedBy": "R/bootstrap.R"}),
    claim("C4", "Bootstrap 95% BCa CI for the slope is -0.0005 to 0.3748 under R 3.6.1",
          "manuscript.Rmd l.228-233 (bootstrap example, R 3.6.1)",
          **{"rc:expectedValue": [-0.0005, 0.3748], "rc:comparison": "rounded", "rc:decimalPlaces": 4,
             "rc:tolerance": "equal after rounding to 4 decimals (as reported)",
             "rc:requiresEnvironment": {"r_version": "3.6.1"}, "rc:outputKey": ["boot_ci_lower", "boot_ci_upper"],
             "rc:producedBy": "R/bootstrap.R"}),
    claim("C5", "The CI excludes zero under R 3.5.0 but includes zero under R 3.6.1, so the conclusion changes with the R version",
          "manuscript.Rmd l.220-233 (text around the bootstrap example)",
          **{"rc:expectedValue": "lower(R 3.5.0) > 0 and lower(R 3.6.1) <= 0", "rc:comparison": "derived",
             "rc:tolerance": "logical condition on C3 and C4",
             "rc:condition": [{"claim": "C3", "index": 0, "op": ">", "value": 0},
                              {"claim": "C4", "index": 0, "op": "<=", "value": 0}]}),
]

gaps = [
    gap("G1", "Dockerfile installs packages from Microsoft MRAN (mran.microsoft.com/snapshot/2020-01-01). MRAN was retired in 2023, so 'make build' is expected to fail as written.",
        "environment", "Dockerfile line 3; not yet confirmed by a build"),
    gap("G2", "The bootstrap seed is selected by search: bootstrap.R picks the first seed whose CI excludes zero in R 3.5.0 but not in R 3.6.1 (seed 2). The reported pair is a chosen illustration.",
        "interpretation", "R/bootstrap.R, section find-seed"),
    gap("G3", "The data are simulated to be borderline (file named pathological-example2; true slope 0.225, n = 100).",
        "interpretation", "R/bootstrap-data.R"),
    gap("G4", "Makefile hard-codes a Windows path when WINDOWS=TRUE.", "portability", "Makefile line 5"),
    gap("G5", "Crate built from the repository's latest commit; the paper cites commit c4213f6.", "provenance",
        f"{REPO}/commit/{COMMIT}"),
]

root = {
    "@id": "./", "@type": "Dataset",
    "name": "Paper crate: Peikert & Brandmaier (2021), reproducible R workflow",
    "description": "Inputs, code, recorded outputs, claims and gaps for verifying the R-version examples in Peikert & Brandmaier (2021).",
    "datePublished": date.today().isoformat(),
    "license": CC_BY,
    "conformsTo": {"@id": "#recrate-profile"},
    "isBasedOn": [{"@id": PAPER}, {"@id": REPO}],
    "hasPart": [{"@id": p} for p in FILES],
    "mentions": [{"@id": c["@id"]} for c in claims] + [{"@id": g["@id"]} for g in gaps] + [{"@id": "#input-contract"}],
    "mainEntity": {"@id": "R/bootstrap.R"},
}

graph = [file_entity(p, *v) for p, v in FILES.items()] + claims + gaps + [
    {"@id": PAPER, "@type": "ScholarlyArticle",
     "name": "A Reproducible Data Analysis Workflow With R Markdown, Git, Make, and Docker",
     "author": [{"@id": "https://orcid.org/0000-0001-7813-818X"}, {"@id": "https://orcid.org/0000-0001-8765-6982"}],
     "datePublished": "2021-05-11", "isPartOf": "Quantitative and Computational Methods in Behavioral Sciences 1(1)",
     "license": CC_BY},
    {"@id": "https://orcid.org/0000-0001-7813-818X", "@type": "Person", "name": "Aaron Peikert"},
    {"@id": "https://orcid.org/0000-0001-8765-6982", "@type": "Person", "name": "Andreas M. Brandmaier"},
    {"@id": REPO, "@type": "SoftwareSourceCode", "name": "reproducible-research", "codeRepository": REPO,
     "version": COMMIT, "license": CC_BY, "programmingLanguage": {"@id": "#lang-r"}},
    {"@id": "#lang-r", "@type": "ComputerLanguage", "name": "R", "url": {"@id": "https://www.r-project.org/"}},
    {"@id": "#image-rocker-verse-3.6.1", "@type": "ContainerImage", "name": "rocker/verse", "tag": "3.6.1",
     "registry": "docker.io", "description": "Base image named in the authors' Dockerfile"},
    {"@id": "#input-contract", "@type": "rc:InputContract", "name": "Data accepted for reuse",
     "description": "CSV with numeric columns x (predictor) and y (outcome), one row per observation, no missing values. Method: OLS slope of y on x with a 95% BCa bootstrap CI (1,000 resamples).",
     "rc:requiredColumns": ["x", "y"], "rc:columnTypes": {"x": "numeric", "y": "numeric"}},
    {"@id": "#recrate-agent", "@type": "SoftwareApplication", "name": "reCRATE analysis (manual, with Claude)",
     "description": "Extracted claims and gaps from the paper and repository; added repro/run_claims.R"},
    cr.PROFILE_ENTITY,
]

print("Wrote", cr.write(CRATE, root, graph), f"- {len(FILES)} files, {len(claims)} claims, {len(gaps)} gaps")

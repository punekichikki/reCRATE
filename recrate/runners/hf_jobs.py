"""Run a container on Hugging Face Jobs.

Jobs run any Docker image on CPU or GPU hardware and are billed per minute from the
account's credit balance (https://huggingface.co/docs/hub/jobs-pricing). The default
timeout is 30 minutes, so long runs (U-Net training for Caicedo et al.) must set one.

A Job cannot see local files. Its command has to fetch the crate first (for example from
this GitHub repo or a Hugging Face dataset repo) and upload observed outputs at the end.
TODO(Person 2): settle that fetch/upload step and pre-build images with git + the hf CLI.

Install: pip install -e ".[hf]"; set HF_TOKEN in .env (never commit it).
The calls below follow huggingface_hub's run_job / inspect_job / fetch_job_logs; check them
against the installed version, since the Jobs API is recent.
"""
import os

from . import RunRecord

# Per-run budget guard (USD). Hourly prices from the Jobs pricing page; update if they change.
HOURLY_USD = {"cpu-basic": 0.01, "cpu-upgrade": 0.03, "t4-small": 0.40, "t4-medium": 0.60,
              "l4x1": 0.80, "a10g-small": 1.00, "a10g-large": 1.50, "a100-large": 2.50}


def estimated_cost(flavor: str, timeout_s: int) -> float:
    return HOURLY_USD.get(flavor, 5.0) * timeout_s / 3600


def run(image: str, command: list, flavor: str = "cpu-basic", timeout_s: int = 1800,
        namespace: str = None, max_usd: float = None, env: dict = None) -> RunRecord:
    if max_usd is None:
        max_usd = float(os.environ.get("RECRATE_MAX_USD_PER_RUN", "3"))
    cost = estimated_cost(flavor, timeout_s)
    if cost > max_usd:
        raise RuntimeError(f"worst-case cost ${cost:.2f} exceeds the ${max_usd:.2f} budget for one run")
    try:
        from huggingface_hub import run_job
    except ImportError as e:
        raise RuntimeError('huggingface_hub is not installed: pip install -e ".[hf]"') from e

    job = run_job(image=image, command=command, flavor=flavor, timeout=timeout_s,
                  namespace=namespace or os.environ.get("HF_NAMESPACE"),
                  env=env or {}, secrets={"HF_TOKEN": os.environ["HF_TOKEN"]} if "HF_TOKEN" in os.environ else None)
    return RunRecord(runner="hf-jobs", image=image, command=command, hardware=flavor,
                     job_id=getattr(job, "id", None), extra={"max_usd": max_usd, "timeout_s": timeout_s})

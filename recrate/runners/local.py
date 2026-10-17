"""Run a container with the local Docker daemon."""
import shutil
import subprocess

from . import RunRecord


def run(image: str, command: list, mount: str, workdir: str = "/w", timeout_s: int = 1800) -> RunRecord:
    """docker run --rm -v <mount>:<workdir> -w <workdir> <image> <command...>"""
    if not shutil.which("docker"):
        raise RuntimeError("docker is not installed; use the hf-jobs runner instead")
    args = ["docker", "run", "--rm", "-v", f"{mount}:{workdir}", "-w", workdir, image, *command]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout_s)
    digest = subprocess.run(["docker", "image", "inspect", "--format", "{{index .RepoDigests 0}}", image],
                            capture_output=True, text=True).stdout.strip() or None
    return RunRecord(runner="local", image=image, command=command, exit_code=proc.returncode,
                     image_digest=digest, logs=(proc.stdout + proc.stderr)[-20000:])

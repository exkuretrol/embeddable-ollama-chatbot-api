#!/usr/bin/env python3
"""
gpu_watchdog — Check GPU availability in a remote K8s pod via SSH.
If nvidia-smi fails, scale the deployment down to 0 and back to 1.

Usage:
    python scripts/gpu_watchdog.py                            # single check
    crontab: */30 * * * * python /path/to/gpu_watchdog.py     # every 30 min

Config loaded from .env (or environment variables):
    GPU_WATCHDOG_SSH_HOST, GPU_WATCHDOG_K8S_NAMESPACE,
    GPU_WATCHDOG_K8S_DEPLOYMENT, GPU_WATCHDOG_SCALE_DOWN_WAIT
"""

import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path

import paramiko
from dotenv import load_dotenv

# --- Load .env ---
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# --- Config ---
SSH_HOST = os.environ.get("GPU_WATCHDOG_SSH_HOST", "")
NAMESPACE = os.environ.get("GPU_WATCHDOG_K8S_NAMESPACE", "default")
DEPLOYMENT = os.environ.get("GPU_WATCHDOG_K8S_DEPLOYMENT", "")
SCALE_DOWN_WAIT = int(os.environ.get("GPU_WATCHDOG_SCALE_DOWN_WAIT", "10"))

# --- Logging ---
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

_file_handler = logging.handlers.TimedRotatingFileHandler(
    LOG_DIR / "gpu-watchdog.log",
    when="midnight",
    backupCount=30,
    utc=True,
)
_file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

log = logging.getLogger("gpu-watchdog")
log.setLevel(logging.INFO)
log.addHandler(_file_handler)
log.addHandler(_console_handler)


def create_ssh_client() -> paramiko.SSHClient:
    """Create an SSH client using ~/.ssh/config."""
    ssh_config = paramiko.SSHConfig.from_path(str(Path.home() / ".ssh" / "config"))
    host_config = ssh_config.lookup(SSH_HOST)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host_config.get("hostname", SSH_HOST),
        port=int(host_config.get("port", 22)),
        username=host_config.get("user"),
        key_filename=host_config.get("identityfile"),
    )
    return client


def ssh_run(client: paramiko.SSHClient, cmd: str) -> tuple[int, str, str]:
    """Run a command on the remote host. Returns (exit_code, stdout, stderr)."""
    log.debug("ssh_run: %s", cmd)
    _, stdout, stderr = client.exec_command(cmd)
    exit_code = stdout.channel.recv_exit_status()
    out, err = stdout.read().decode().strip(), stderr.read().decode().strip()
    if exit_code != 0:
        log.debug("ssh_run exit=%d stderr=%s", exit_code, err)
    return exit_code, out, err


def get_pod_name(client: paramiko.SSHClient) -> str | None:
    """Find the running pod name for the deployment."""
    exit_code, stdout, _ = ssh_run(
        client,
        f"kubectl get pod -n {NAMESPACE} "
        f"-l app={DEPLOYMENT} "
        f"-o jsonpath='{{.items[0].metadata.name}}'",
    )
    name = stdout.strip("'")
    return name if exit_code == 0 and name else None


def check_gpu(client: paramiko.SSHClient, pod: str) -> bool:
    """Return True if nvidia-smi succeeds on the pod."""
    exit_code, _, _ = ssh_run(
        client,
        f"kubectl exec -n {NAMESPACE} {pod} -- nvidia-smi",
    )
    return exit_code == 0


def restart_deployment(client: paramiko.SSHClient) -> None:
    """Scale deployment to 0, wait, then scale back to 1."""
    log.info("Scaling deployment to 0...")
    ssh_run(client, f"kubectl scale deployment/{DEPLOYMENT} -n {NAMESPACE} --replicas=0")

    log.info("Waiting %ds before scaling back up...", SCALE_DOWN_WAIT)
    time.sleep(SCALE_DOWN_WAIT)

    log.info("Scaling deployment to 1...")
    ssh_run(client, f"kubectl scale deployment/{DEPLOYMENT} -n {NAMESPACE} --replicas=1")
    log.info("Deployment restarted successfully")


def main() -> int:
    if not SSH_HOST:
        log.error("GPU_WATCHDOG_SSH_HOST is not set")
        return 1
    if not DEPLOYMENT:
        log.error("GPU_WATCHDOG_K8S_DEPLOYMENT is not set")
        return 1

    try:
        client = create_ssh_client()
    except Exception:
        log.exception("SSH connection to %s failed", SSH_HOST)
        return 1

    try:
        pod = get_pod_name(client)
        if not pod:
            log.error("Could not find pod for deployment=%s namespace=%s", DEPLOYMENT, NAMESPACE)
            return 1

        log.info("Checking GPU on pod=%s", pod)

        if check_gpu(client, pod):
            log.info("GPU check passed")
            return 0

        log.warning("GPU check FAILED on pod=%s — restarting deployment", pod)
        restart_deployment(client)
        return 0
    except Exception:
        log.exception("Unexpected error during watchdog run")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())

import asyncio
import datetime
import shutil
import subprocess
from pathlib import Path

from ..config import APPS_SCRIPT_AUTO_UPDATE, CLASP_DEPLOYMENT_ID, CLASP_WORKDIR, TIMEZONE


def _run(command: list[str], cwd: Path):
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return {
        "ok": proc.returncode == 0,
        "code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "cmd": " ".join(command),
    }


def _deploy_sync():
    if not APPS_SCRIPT_AUTO_UPDATE:
        return {"ok": True, "skipped": True, "message": "APPS_SCRIPT_AUTO_UPDATE is disabled."}

    if not shutil.which("clasp"):
        return {"ok": False, "skipped": True, "message": "clasp CLI is not installed or not in PATH."}

    cwd = Path(CLASP_WORKDIR).resolve()
    if not cwd.exists():
        return {"ok": False, "skipped": True, "message": f"CLASP_WORKDIR does not exist: {cwd}"}
    if not (cwd / ".clasp.json").exists():
        return {
            "ok": False,
            "skipped": True,
            "message": f".clasp.json not found in CLASP_WORKDIR: {cwd}. Run 'clasp create' or copy your Apps Script clasp config.",
        }

    stamp = datetime.datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M")
    steps = []

    for cmd in (["clasp", "status"], ["clasp", "push", "-f"]):
        res = _run(cmd, cwd)
        steps.append(res)
        if not res["ok"]:
            return {"ok": False, "steps": steps, "message": f"Failed: {res['cmd']}"}

    version_desc = f"auto-update {stamp}"
    version_res = _run(["clasp", "version", version_desc], cwd)
    steps.append(version_res)
    if not version_res["ok"]:
        return {"ok": False, "steps": steps, "message": "Failed to create Apps Script version."}

    deploy_cmd = ["clasp", "deploy", "--description", version_desc]
    if CLASP_DEPLOYMENT_ID:
        deploy_cmd.extend(["--deploymentId", CLASP_DEPLOYMENT_ID])
    deploy_res = _run(deploy_cmd, cwd)
    steps.append(deploy_res)
    if not deploy_res["ok"]:
        return {"ok": False, "steps": steps, "message": "Failed to deploy Apps Script Web App."}

    return {"ok": True, "steps": steps, "message": "Apps Script updated successfully."}


async def update_web_app():
    return await asyncio.to_thread(_deploy_sync)

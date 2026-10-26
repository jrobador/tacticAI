"""Launch the job for a queued job_id: a local docker run, or an Azure Container Apps Job start."""
import os
import subprocess
import threading

from . import jobs

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
COMMAND = "xvfb-run -a -s '-screen 0 1280x720x24' python3 -m tacticai.orchestration start "


def _docker(job_id):
    out = os.path.abspath(jobs.data_dir())
    env_file = os.path.join(REPO, ".env")
    cmd = ["docker", "run", "--rm", "-v", f"{out}:/data", "-v", f"{os.path.join(REPO, 'src')}:/app/src"]
    cmd += (["--env-file", env_file] if os.path.exists(env_file) else [])
    cmd += ["-e", "TAI_OUTPUT_DIR=/data", "tai-job", "sh", "-c", COMMAND + job_id]
    log = open(os.path.join(jobs.job_dir(job_id), "pipeline.log"), "wb")
    try:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    except OSError:
        log.close()
        raise

    def wait():
        code = proc.wait()
        log.close()
        status = jobs.read(job_id)
        if code != 0 and status and not jobs.is_terminal(status):
            jobs.write(job_id, state="failed", message=f"docker exited with code {code}; see jobs/{job_id}/pipeline.log")
    threading.Thread(target=wait, daemon=True).start()


def _aca(job_id):
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.appcontainers import ContainerAppsAPIClient
    client = ContainerAppsAPIClient(DefaultAzureCredential(), os.environ["AZURE_SUBSCRIPTION_ID"])
    poller = client.jobs.begin_start(os.environ["AZURE_RESOURCE_GROUP"], os.environ["TAI_JOB_NAME"])  # the job takes the only queued job

    def wait():
        try:
            poller.result()
        except Exception as err:
            jobs.write(job_id, state="failed", message=f"could not start the job: {err}")
    threading.Thread(target=wait, daemon=True).start()


def launch(job_id):
    """Raises if the job cannot start; the caller marks it failed."""
    (_aca if os.environ.get("TAI_RUNNER", "docker") == "aca" else _docker)(job_id)

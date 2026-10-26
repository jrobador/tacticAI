# Deploy

tacticAI runs in Azure for the evaluators as two containers sharing one folder: a Container App `api` (FastAPI plus the built UI, public URL) and a Container Apps Job `job` (the C++ engine and the Interpret pipeline, started manually by the API, 4 vCPU / 8 GiB, one run at a time). Both mount the Azure Files share `tai-data` at `/data`, so the code reads and writes plain disk. There is no queue, database or blob storage.

Files: `azure.yaml` (azd project), `deploy/infra/` (Bicep, subscription scope, creates `rg-<env>` in `brazilsouth`), `deploy/api.Dockerfile`, `deploy/job.Dockerfile`, `deploy/postprovision.sh` and `.ps1` (build and push the job image after provisioning). Nothing here deploys by itself: `azd up` is run by hand.

The job image extends `tai-engine`, which exists only on a machine where `docker build -t tai-engine engine` was run, so `azd up` must run from that machine. The API image is built by azd from `deploy/api.Dockerfile` and needs `ui/dist`.

## Steps (by hand)

Log in to the subscription you will deploy to; the `postprovision` hook aborts if the CLI subscription is not the one set in the azd environment.

Foundry is not created by the Bicep: create a Foundry resource and a model deployment by hand (any subscription and region; the API and the job only use its endpoint), check the model quota (Foundry portal, Management > Quota), lower the deployment's tokens-per-minute limit (step 4 below), and pass endpoint, deployment name and key with `azd env set` (step 1 below).

```sh
# 0. Prerequisites: tai-engine built locally, UI built, azd installed
docker build -t tai-engine engine
(cd ui && npm install && npm run build)

# 1. Log in and pin the subscription
az login --tenant <tenant-id>
az account set --subscription <subscription-id>
az account show --query "[name,id]"   # if it is not the deploy subscription, stop here
azd auth login --tenant-id <tenant-id>
azd env new tacticai
azd env set AZURE_SUBSCRIPTION_ID <subscription-id>
azd env set AZURE_LOCATION brazilsouth
azd env set FOUNDRY_ENDPOINT <endpoint>
azd env set FOUNDRY_DEPLOYMENT <deployment>
azd env set FOUNDRY_API_KEY <key>
azd env set TAI_ACCESS_KEY <a long random key>
azd env set TAI_BUDGET_EMAIL <email>

# 2. Provision and deploy (also builds and pushes the job image)
azd up

# 3. Upload the library and the sample matches generated locally
az storage file upload-batch --account-name <AZURE_STORAGE_ACCOUNT> --destination tai-data --source data --pattern "library/*"
az storage file upload-batch --account-name <AZURE_STORAGE_ACCOUNT> --destination tai-data --source data --pattern "matches/*"

# 4. In the Foundry portal, lower the tokens-per-minute limit of the deployment (the real cap on model spend)

# 5. After the evaluation, delete everything
azd down
```

`<AZURE_STORAGE_ACCOUNT>` is printed by `azd env get-values`. Do not write the Foundry key in any file; it lives only in the azd environment and in the Container Apps secret `foundry-api-key`.

`/scenario`, `/ask` and `POST /jobs` need the access key: send it in the header `X-Access-Key`, or open the UI once with `?key=<TAI_ACCESS_KEY>` (the UI stores it and removes it from the URL). Reading is open. The budget (`TAI_BUDGET_EMAIL`, 10 per month by default, alerts at 50% and 90%) only sends emails, it does not stop anything; the tokens-per-minute limit in Foundry is the real cap. Run `azd down` as soon as the evaluation ends. Do not deploy a new API version while a job is running (the one-job lock lives in the API process).

## Post-deploy checklist

- `GET <API_URI>/catalog` responds and `/` shows the UI.
- `/library` lists the uploaded library and the 5 sample videos play.
- A `POST /jobs` with a recipe known to win ends in `done` and the video plays from `/matches/{id}/files/video.mp4`.
- Azure Files check: while a job runs, `GET /jobs/{id}` reads without errors or half-written files, and the publish step (`os.rename` from `staging/` to `matches/`) works over SMB. If the rename fails, report it; do not replace it with copy and delete.
- Measure how long one situation takes in the job (software rendering, no GPU).
- Force a stuck job (stop the execution from the portal) and confirm the API marks it `failed` after 20 minutes.

## Logs

Log Analytics, queries not run against a deployment: the table and column names are [UNVERIFIED].

API errors:

```kusto
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "api" and (Log_s contains "error" or Log_s contains "Traceback")
| order by TimeGenerated desc
```

Failed job executions:

```kusto
ContainerAppSystemLogs_CL
| where JobName_s == "job" and Reason_s contains "Failed"
| order by TimeGenerated desc
```

Application Insights (`APPLICATIONINSIGHTS_CONNECTION_STRING`, api app only) also receives the API requests and exceptions.

## [UNVERIFIED]

None of the Azure behavior below has been run; `az bicep build` only checks syntax and types.

- That the Consumption workload profile accepts 4 vCPU / 8 GiB per replica in `brazilsouth`. If Azure rejects it, set the job to 2 vCPU / 4 GiB in `resources.bicep` and `TAI_WORKERS=2`.
- That the custom role actions `Microsoft.App/jobs/start/action`, `Microsoft.App/jobs/read` and `Microsoft.App/jobs/executions/read` are the exact names. If a built-in role covers it, use that.
- That the first `azd up` is not blocked by the placeholder image (`mcr.microsoft.com/k8se/quickstart`, which listens on port 80, not the ingress port 8000). If it is, provision with the port of the placeholder and fix it in the deploy.
- That re-running `azd provision` keeps the real images: `apiImage` comes from `SERVICE_API_IMAGE_NAME` and `jobImage` from `TAI_JOB_IMAGE` (set by the hook), both empty on the first run. Whether azd stores `SERVICE_API_IMAGE_NAME` after `azd deploy` is not confirmed.
- That azd has no native deployment for Container Apps Jobs (hence the hook).
- That the identity pull from ACR works at first creation (the `AcrPull` assignment is declared as a dependency of both resources) and that a role assignment on the job scope with `principalType: ServicePrincipal` for the system identity propagates in time.
- That the SMB mount supports the file operations the pipeline uses (see the Azure Files check above).

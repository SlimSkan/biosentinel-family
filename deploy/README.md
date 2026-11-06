# Deploying BioSentinel Family to Azure

The hackathon demo runs on **Azure Container Apps**, with Gemma 4 on a **serverless T4 GPU**.
Everything is created by one script, using the team's Azure credits.

```
 Judge's browser ──HTTPS──► bsf-web   FastAPI + web pages · CPU · exactly 1 replica
                               │       (public; counsellor inbox needs a key)
                               │  private network inside the environment
                               ▼
                            bsf-gemma  Ollama + Gemma 4 e4b · NVIDIA T4 · 0-1 replica
                                       (no public address at all)
 Both images are built in Azure Container Registry (no Docker needed on your laptop).
```

## Why these choices

| Choice | Why |
|---|---|
| **Container Apps**, not VMs or Kubernetes | HTTPS, scaling and logs are built in; nothing to patch. Scales to zero, so the GPU is billed by the second only while it runs. |
| **Two apps** in one environment | The web app needs a small CPU and must always be on; Gemma needs a GPU and can sleep. Separating them lets each scale on its own. |
| **Gemma on internal ingress** | The web app calls it at `http://bsf-gemma` over the environment's private network. It has no public address, so no password to leak. Microsoft's sample puts Gemma behind a public proxy with a password; we don't need that. |
| **Model baked into the image** | Microsoft's sample downloads the ~10 GB model each time a container starts. Ours is in the image, so start-up doesn't depend on a download. |
| **Web app: exactly 1 replica** | Match sessions, invites and cases live in the server's memory. Two replicas would each have their own memory, and a couple could land on different ones. Scaling to zero would wipe it. A database removes this limit later. |
| **Sweden Central** | Serverless GPUs are **not available in UAE North**. Sweden Central has both T4 and A100 and is where Microsoft benchmarked Gemma 4 (e4b on T4: ~51 tokens/s). Central India is closer but offers T4 only; use `LOCATION=centralindia` to try it. |
| **The demo leaving the UAE is acceptable** | The demo uses fictional people only, and the explainer only ever receives one gene name with no identity. The production plan below keeps real data in the UAE. |

## Timeline (today is 5 Nov)

| When | What | Who |
|---|---|---|
| **Now, before 10 Nov** | Register the team on Hack2skill; claim the Azure credits | Team lead |
| **As soon as credits arrive** | Check GPU quota (step 2); request it **the same day** if missing. Quota requests can take days. | Whoever owns the subscription |
| Same day | Set a **budget alert** (step 3) | Same |
| Next day | Run `deploy.sh`, then the smoke test | Anyone, ~45 min |
| Before 20 Nov | Put the URL in the deck (slide 11) and submission; `demo_mode.sh off` | Team |
| Judging / GITEX (7-11 Dec) | `demo_mode.sh on` before each session, `off` after | Presenter |
| After GITEX | Delete the resource group | Team |

## Steps

**1. Install the Azure CLI and sign in** (Windows):
```bash
winget install -e --id Microsoft.AzureCLI
```
```bash
az login
```
```bash
az account set -s "<subscription with the challenge credits>"
```

**2. Check GPU quota.** Microsoft enables serverless GPU quota by default only for pay-as-you-go
and Enterprise Agreement subscriptions. A credits or sponsorship subscription may have none.
The quota page belongs to a Container Apps *environment*, so the simplest path is to run the
script (step 4). If the GPU step fails, it stops and says so. Then, in the portal: the
environment → **Quota** → request **Managed Environment Consumption T4 GPUs** = 1.
While you wait, deploy without the AI:
```bash
SKIP_GEMMA=1 bash deploy/deploy.sh
```
The app is fully usable this way: every screen shows the reviewed texts.

**3. Set a budget alert.** Portal → Cost Management → Budgets → for the subscription, with
alerts at 50% and 80% of the credits. Billing is per second, but a GPU left "on" for weeks is
the one way to burn the credits.

**4. Deploy** (from Git Bash, in the project folder):
```bash
bash deploy/deploy.sh
```
It prints the public URL and a **counsellor key**. Save the key in your password manager; it
is shown only once. The first run takes 30-45 minutes, mostly building the Gemma image. Later
runs reuse that image and take a few minutes.

**5. Check it:**
```bash
python deploy/smoke_test.py https://<the printed URL>
```
It runs the real journeys (Arabic explanation, couple 25/50/25, family invite at 12.5%,
protected inbox, a Gemma rewrite through the guardrails). The first Gemma call after a
cold start can fail on time; run `demo_mode.sh on` first, then test again.

**6. Demo days:**
```bash
bash deploy/demo_mode.sh on
```
```bash
bash deploy/demo_mode.sh off
```

**Clean up** (deletes everything, irreversible):
```bash
az group delete -n rg-bsf-demo
```

## If something goes wrong: the fallback ladder

1. **No GPU quota yet:** `SKIP_GEMMA=1`. Reviewed texts only; every safety property still holds.
   Show the Gemma rewrite from a laptop running Ollama.
2. **GPU slow to start:** the explainer times out at 200 s and shows the reviewed text. Nothing
   breaks; that is the design (graceful degradation).
3. **Smaller model:** `MODEL=gemma4:e2b bash deploy/deploy.sh` (~7 GB, ~81 tokens/s on a T4).
4. **Logs:** `az containerapp logs show -n bsf-gemma -g rg-bsf-demo --follow`.

## What was tested, and what was not

- Tested here: the web app runs with the production settings (counsellor key, timeout, one
  worker), and the smoke test passes with Gemma on and with Gemma unreachable. The shell
  scripts pass a syntax check. The base image versions exist.
- **Not tested:** the scripts have not run against Azure yet (no subscription here), and the
  images have not been built (no Docker here). Expect to fix small things on the first run.

## Production architecture (for the pitch, not built)

| Part | Demo | Production |
|---|---|---|
| Region | Sweden Central | **UAE North** for everything holding personal data. UAE law (Federal Law No. 2 of 2019 on ICT in health fields) generally requires health data to stay in the UAE. |
| AI | Gemma on a cloud GPU | Gemma **on the phone** (e2b) so results never leave it; cloud GPU in the UAE only as an option |
| State | Server memory, 1 replica | Azure Database for PostgreSQL, encrypted; several replicas |
| Secrets | Container Apps secret | Azure Key Vault with managed identity |
| Counsellor login | Shared key | Microsoft Entra ID with roles; audit log |
| Monitoring | Container Apps logs | Application Insights; alerts on guardrail fallback rate |
| Lab results | Demo personas | FHIR import from the screening labs, digitally signed (also stops PSI set inflation) |

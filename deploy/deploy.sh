#!/usr/bin/env bash
# Deploy the BioSentinel Family demo to Azure Container Apps.
#
#   Browser ──HTTPS──► bsf-web (FastAPI, always 1 replica, CPU)
#                         │  internal network only (never on the internet)
#                         ▼
#                      bsf-gemma (Ollama + Gemma 4, serverless T4 GPU, 0-1 replica)
#
# Prerequisites: Azure CLI (`az login` done) and the team's subscription selected
# (`az account set -s <id>`). No Docker needed: images are built in Azure.
# Safe to run again: existing resources are updated, not duplicated.
#
# Usage (Git Bash):   bash deploy/deploy.sh
# Options, as environment variables:
#   LOCATION=swedencentral   a region WITH serverless T4 GPUs (UAE North has none yet)
#   MODEL=gemma4:e4b         or gemma4:e2b (smaller, faster)
#   SKIP_GEMMA=1             deploy the web app only (reviewed texts, no AI)
set -euo pipefail
cd "$(dirname "$0")/.."

PREFIX="${PREFIX:-bsf}"
LOCATION="${LOCATION:-swedencentral}"
RG="${RG:-rg-${PREFIX}-demo}"
SUB_ID="$(az account show --query id -o tsv)"
ACR="${ACR:-${PREFIX}acr$(echo "$SUB_ID" | tr -d - | cut -c1-10)}"   # globally unique, stable per subscription
ENV_NAME="${PREFIX}-env"
WEB="${PREFIX}-web"
LLM="${PREFIX}-gemma"
MODEL="${MODEL:-gemma4:e4b}"
MODEL_TAG="$(echo "$MODEL" | tr ':' '-')"
GPU_PROFILE="NC8as-T4"
GPU_TYPE="Consumption-GPU-NC8as-T4"
TAG="$(date +%Y%m%d-%H%M%S)"
SKIP_GEMMA="${SKIP_GEMMA:-0}"

step() { printf '\n==> %s\n' "$*"; }
exists() { "$@" -o none >/dev/null 2>&1; }

step "Subscription $(az account show --query name -o tsv) · region $LOCATION · group $RG"

step "1/6 Register providers and the Container Apps CLI extension"
az extension add --name containerapp --upgrade -y --only-show-errors
for p in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry; do
  az provider register -n "$p" --wait
done

step "2/6 Resource group and container registry"
az group create -n "$RG" -l "$LOCATION" -o none --tags project=biosentinel-family purpose=hackathon-demo
exists az acr show -n "$ACR" -g "$RG" || az acr create -n "$ACR" -g "$RG" -l "$LOCATION" --sku Standard -o none

step "3/6 Build images in Azure (web: ~1 min; Gemma: ~15-30 min, the model is ~10 GB)"
az acr build -r "$ACR" -t "bsf-web:$TAG" . --only-show-errors -o none
if [ "$SKIP_GEMMA" != "1" ]; then
  if exists az acr repository show -n "$ACR" --image "bsf-gemma:$MODEL_TAG"; then
    echo "Gemma image bsf-gemma:$MODEL_TAG already built, reusing it."
  else
    az acr build -r "$ACR" -t "bsf-gemma:$MODEL_TAG" --build-arg MODEL="$MODEL" \
      --timeout 7200 deploy/ollama --only-show-errors -o none
  fi
fi

step "4/6 Container Apps environment (+ serverless T4 GPU profile)"
exists az containerapp env show -n "$ENV_NAME" -g "$RG" || \
  az containerapp env create -n "$ENV_NAME" -g "$RG" -l "$LOCATION" --enable-workload-profiles -o none
if [ "$SKIP_GEMMA" != "1" ]; then
  if ! az containerapp env workload-profile list -n "$ENV_NAME" -g "$RG" --query "[].name" -o tsv | grep -qx "$GPU_PROFILE"; then
    az containerapp env workload-profile add -n "$ENV_NAME" -g "$RG" \
      --workload-profile-name "$GPU_PROFILE" --workload-profile-type "$GPU_TYPE" -o none || {
      echo "!! Could not add the T4 GPU profile. Most likely: no serverless GPU quota on this subscription."
      echo "!! Request 'Managed Environment Consumption T4 GPUs' on the environment's Quota page, or rerun with SKIP_GEMMA=1."
      exit 1; }
  fi
fi

step "5/6 Gemma app: GPU, internal ingress only, scales to zero when idle"
if [ "$SKIP_GEMMA" != "1" ]; then
  IMG="$ACR.azurecr.io/bsf-gemma:$MODEL_TAG"
  if exists az containerapp show -n "$LLM" -g "$RG"; then
    az containerapp update -n "$LLM" -g "$RG" --image "$IMG" -o none
  else
    az containerapp create -n "$LLM" -g "$RG" --environment "$ENV_NAME" \
      --image "$IMG" --registry-server "$ACR.azurecr.io" --registry-identity system \
      --workload-profile-name "$GPU_PROFILE" --cpu 8 --memory 56Gi \
      --ingress internal --target-port 11434 \
      --min-replicas 0 --max-replicas 1 \
      --env-vars OLLAMA_KEEP_ALIVE=-1 -o none
  fi
fi

step "6/6 Web app: public HTTPS, exactly 1 replica (state lives in memory)"
IMG="$ACR.azurecr.io/bsf-web:$TAG"
if exists az containerapp show -n "$WEB" -g "$RG"; then
  az containerapp update -n "$WEB" -g "$RG" --image "$IMG" -o none
else
  COUNSELLOR_KEY="${COUNSELLOR_KEY:-$(python -c 'import secrets; print(secrets.token_urlsafe(12))')}"
  az containerapp create -n "$WEB" -g "$RG" --environment "$ENV_NAME" \
    --image "$IMG" --registry-server "$ACR.azurecr.io" --registry-identity system \
    --workload-profile-name Consumption --cpu 0.5 --memory 1Gi \
    --ingress external --target-port 8000 \
    --min-replicas 1 --max-replicas 1 \
    --secrets counsellor-key="$COUNSELLOR_KEY" \
    --env-vars OLLAMA_URL="http://$LLM" BSF_MODEL="$MODEL" BSF_LLM_TIMEOUT=200 \
               BSF_COUNSELLOR_KEY=secretref:counsellor-key -o none
  echo "Counsellor key (save it now; it is not shown again): $COUNSELLOR_KEY"
fi

URL="https://$(az containerapp show -n "$WEB" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)"
step "Done: $URL"
echo "Next:  python deploy/smoke_test.py $URL"
echo "Before a demo:  bash deploy/demo_mode.sh on     (keeps Gemma warm)"
echo "After:          bash deploy/demo_mode.sh off    (GPU scales to zero, stops billing)"

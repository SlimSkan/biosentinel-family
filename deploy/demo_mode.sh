#!/usr/bin/env bash
# Keep the Gemma GPU warm for a demo, or let it scale to zero to save credits.
#   bash deploy/demo_mode.sh on    # 1 GPU replica always running (billed every second)
#   bash deploy/demo_mode.sh off   # 0 replicas when idle; first AI request then waits for a cold start
set -euo pipefail
PREFIX="${PREFIX:-bsf}"; RG="${RG:-rg-${PREFIX}-demo}"; LLM="${PREFIX}-gemma"; WEB="${PREFIX}-web"

case "${1:-}" in
  on)
    az containerapp update -n "$LLM" -g "$RG" --min-replicas 1 -o none
    URL="https://$(az containerapp show -n "$WEB" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)"
    echo "Gemma set to stay on. Waiting for it to answer (first start can take several minutes)..."
    for i in $(seq 1 40); do
      if curl -s "$URL/api/health" | grep -q '"model_present":true'; then echo "Gemma is ready: $URL"; exit 0; fi
      sleep 15
    done
    echo "Gemma not ready after 10 minutes. Check: az containerapp logs show -n $LLM -g $RG"; exit 1 ;;
  off)
    az containerapp update -n "$LLM" -g "$RG" --min-replicas 0 -o none
    echo "Gemma will scale to zero when idle. The app still works with reviewed texts." ;;
  *) echo "usage: $0 on|off"; exit 2 ;;
esac

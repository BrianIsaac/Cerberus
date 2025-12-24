#!/bin/bash
# Deploy the main Ops Assistant application to Cloud Run.
#
# This must be run after the MCP server is deployed and IAM is configured.
#
# Usage: ./infra/cloudrun/deploy.sh
#
# Prerequisites:
# - GOOGLE_CLOUD_PROJECT environment variable set
# - MCP server deployed via deploy_mcp_server.sh
# - IAM configured via configure_iam.sh
# - Secrets created via setup_secrets.sh

set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT}
REGION=${VERTEX_LOCATION:-us-central1}
SERVICE_NAME="ops-assistant"
MCP_SERVICE_NAME="datadog-mcp-server"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

if [ -z "${PROJECT_ID}" ]; then
    echo "ERROR: GOOGLE_CLOUD_PROJECT environment variable is not set"
    exit 1
fi

echo "=== Deploying Ops Assistant to Cloud Run ==="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Check if MCP server is deployed and get its URL
echo "Checking MCP server deployment..."
MCP_SERVER_URL=$(gcloud run services describe ${MCP_SERVICE_NAME} \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --format 'value(status.url)' 2>/dev/null) || {
    echo "ERROR: MCP server not deployed. Run deploy_mcp_server.sh first."
    exit 1
}

echo "Using MCP server at: ${MCP_SERVER_URL}"
echo ""

# Build and push image using Cloud Build
echo "Building main application image..."
gcloud builds submit \
    --tag ${IMAGE} \
    --project ${PROJECT_ID} \
    --dockerfile Dockerfile-ops-triage-agent \
    .

# Deploy to Cloud Run with LLM-optimised settings
echo ""
echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE} \
    --region ${REGION} \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300 \
    --concurrency 20 \
    --max-instances 5 \
    --min-instances 0 \
    --set-env-vars "DD_SERVICE=${SERVICE_NAME}" \
    --set-env-vars "DD_ENV=production" \
    --set-env-vars "DD_VERSION=0.1.0" \
    --set-env-vars "DD_LLMOBS_ENABLED=1" \
    --set-env-vars "DD_LLMOBS_ML_APP=${SERVICE_NAME}" \
    --set-env-vars "DD_LLMOBS_AGENTLESS_ENABLED=1" \
    --set-env-vars "DD_SITE=${DD_SITE:-ap1.datadoghq.com}" \
    --set-env-vars "DD_LLMOBS_EVALUATORS=ragas_faithfulness,ragas_context_precision,ragas_answer_relevancy" \
    --set-secrets "DD_API_KEY=DD_API_KEY:latest" \
    --set-secrets "DD_APP_KEY=DD_APP_KEY:latest" \
    --set-secrets "OPENAI_API_KEY=OPENAI_API_KEY:latest" \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
    --set-env-vars "VERTEX_LOCATION=${REGION}" \
    --set-env-vars "GEMINI_MODEL=gemini-2.0-flash" \
    --set-env-vars "MCP_SERVER_URL=${MCP_SERVER_URL}/mcp" \
    --set-env-vars "AGENT_MAX_STEPS=8" \
    --set-env-vars "AGENT_MAX_MODEL_CALLS=5" \
    --set-env-vars "AGENT_MAX_TOOL_CALLS=6" \
    --project ${PROJECT_ID}

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --format 'value(status.url)')

echo ""
echo "=== Ops Assistant Deployment Complete ==="
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Verify deployment:"
echo "  curl ${SERVICE_URL}/health"
echo ""
echo "Test the API:"
echo "  curl -X POST ${SERVICE_URL}/ask \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"question\": \"What is the current status of the ops-assistant service?\"}'"
echo ""
echo "Run traffic generator against deployed service:"
echo "  uv run python scripts/traffic_gen.py --mode normal --rps 0.5 --duration 30 --base-url ${SERVICE_URL}"
echo ""
echo "Next step: Apply Datadog configuration with ./infra/datadog/apply_config.sh"

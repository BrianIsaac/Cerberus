#!/bin/bash
# Deploy the MCP server to Cloud Run.
#
# This must be run before deploying the main application, as the main app
# depends on the MCP server URL.
#
# Usage: ./infra/cloudrun/deploy_mcp_server.sh
#
# Prerequisites:
# - GOOGLE_CLOUD_PROJECT environment variable set
# - Secrets created via setup_secrets.sh
# - gcloud authenticated with appropriate permissions

set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT}
REGION=${VERTEX_LOCATION:-us-central1}
SERVICE_NAME="datadog-mcp-server"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

if [ -z "${PROJECT_ID}" ]; then
    echo "ERROR: GOOGLE_CLOUD_PROJECT environment variable is not set"
    exit 1
fi

echo "=== Deploying MCP Server to Cloud Run ==="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable run.googleapis.com --project ${PROJECT_ID}
gcloud services enable cloudbuild.googleapis.com --project ${PROJECT_ID}
gcloud services enable secretmanager.googleapis.com --project ${PROJECT_ID}

# Build the image using Cloud Build
echo ""
echo "Building MCP server image..."
gcloud builds submit \
    --tag ${IMAGE} \
    --project ${PROJECT_ID} \
    --dockerfile Dockerfile-mcp \
    .

# Deploy to Cloud Run
echo ""
echo "Deploying MCP server to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE} \
    --region ${REGION} \
    --platform managed \
    --no-allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 60 \
    --concurrency 50 \
    --max-instances 5 \
    --min-instances 1 \
    --set-env-vars "DD_SITE=${DD_SITE:-ap1.datadoghq.com}" \
    --set-secrets "DD_API_KEY=DD_API_KEY:latest" \
    --set-secrets "DD_APP_KEY=DD_APP_KEY:latest" \
    --project ${PROJECT_ID}

# Get the service URL
MCP_SERVER_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --format 'value(status.url)')

echo ""
echo "=== MCP Server Deployment Complete ==="
echo "Service URL: ${MCP_SERVER_URL}"
echo ""
echo "IMPORTANT: Save this URL for the main app deployment:"
echo "  export MCP_SERVER_URL=${MCP_SERVER_URL}/mcp"
echo ""
echo "Next steps:"
echo "  1. Run ./infra/cloudrun/configure_iam.sh to set up service-to-service auth"
echo "  2. Run ./infra/cloudrun/deploy.sh to deploy the main application"

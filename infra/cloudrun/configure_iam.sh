#!/bin/bash
# Configure IAM for service-to-service authentication.
#
# This grants the main application's service account permission to invoke
# the MCP server. Run this after deploying the MCP server but before
# deploying the main application.
#
# Usage: ./infra/cloudrun/configure_iam.sh
#
# Prerequisites:
# - GOOGLE_CLOUD_PROJECT environment variable set
# - MCP server deployed via deploy_mcp_server.sh

set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT}
REGION=${VERTEX_LOCATION:-us-central1}
MAIN_SERVICE="ops-assistant"
MCP_SERVICE="datadog-mcp-server"

if [ -z "${PROJECT_ID}" ]; then
    echo "ERROR: GOOGLE_CLOUD_PROJECT environment variable is not set"
    exit 1
fi

echo "=== Configuring IAM for Service-to-Service Authentication ==="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo ""

# Check if MCP server is deployed
if ! gcloud run services describe ${MCP_SERVICE} \
    --region ${REGION} \
    --project ${PROJECT_ID} &>/dev/null; then
    echo "ERROR: MCP server '${MCP_SERVICE}' not deployed. Run deploy_mcp_server.sh first."
    exit 1
fi

# Get project number for default compute service account
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
DEFAULT_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Using service account: ${DEFAULT_SA}"
echo ""

# Grant the default compute service account permission to invoke the MCP server
echo "Granting Cloud Run Invoker role on ${MCP_SERVICE}..."
gcloud run services add-iam-policy-binding ${MCP_SERVICE} \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --member "serviceAccount:${DEFAULT_SA}" \
    --role "roles/run.invoker"

# Grant Vertex AI permissions if not already present
echo ""
echo "Granting Vertex AI User role to service account..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member "serviceAccount:${DEFAULT_SA}" \
    --role "roles/aiplatform.user" \
    --condition=None \
    2>/dev/null || echo "Vertex AI User role already granted or binding exists"

# Grant Secret Manager access
echo ""
echo "Granting Secret Manager Secret Accessor role to service account..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member "serviceAccount:${DEFAULT_SA}" \
    --role "roles/secretmanager.secretAccessor" \
    --condition=None \
    2>/dev/null || echo "Secret Manager role already granted or binding exists"

echo ""
echo "=== IAM Configuration Complete ==="
echo ""
echo "The main application (${MAIN_SERVICE}) can now:"
echo "  - Invoke the MCP server (${MCP_SERVICE})"
echo "  - Access Vertex AI for Gemini"
echo "  - Read secrets from Secret Manager"
echo ""
echo "Next step: Run ./infra/cloudrun/deploy.sh to deploy the main application"

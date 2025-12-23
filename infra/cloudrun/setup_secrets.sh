#!/bin/bash
# Setup secrets in Google Secret Manager for Cloud Run deployment.
#
# Usage: ./infra/cloudrun/setup_secrets.sh

set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT}

if [ -z "${PROJECT_ID}" ]; then
    echo "ERROR: GOOGLE_CLOUD_PROJECT environment variable is not set"
    exit 1
fi

echo "Setting up secrets in Google Secret Manager for project: ${PROJECT_ID}"
echo "Note: You will be prompted to enter secret values for any new secrets"
echo ""

create_or_update_secret() {
    local secret_name=$1
    local env_var_name=$2

    if gcloud secrets describe ${secret_name} --project ${PROJECT_ID} &>/dev/null; then
        echo "Secret ${secret_name} already exists"
        read -p "Do you want to update it? [y/N]: " update_choice
        if [[ "${update_choice}" =~ ^[Yy]$ ]]; then
            echo -n "Enter new value for ${secret_name}: "
            read -s secret_value
            echo
            echo -n "${secret_value}" | gcloud secrets versions add ${secret_name} \
                --project ${PROJECT_ID} \
                --data-file=-
            echo "Secret ${secret_name} updated"
        fi
    else
        echo "Creating secret: ${secret_name}"

        # Check if value is available in environment
        local env_value="${!env_var_name}"
        if [ -n "${env_value}" ]; then
            read -p "Use value from ${env_var_name} environment variable? [Y/n]: " use_env
            if [[ ! "${use_env}" =~ ^[Nn]$ ]]; then
                echo -n "${env_value}" | gcloud secrets create ${secret_name} \
                    --project ${PROJECT_ID} \
                    --replication-policy="automatic" \
                    --data-file=-
                echo "Secret ${secret_name} created from environment variable"
                return
            fi
        fi

        echo -n "Enter value for ${secret_name}: "
        read -s secret_value
        echo
        echo -n "${secret_value}" | gcloud secrets create ${secret_name} \
            --project ${PROJECT_ID} \
            --replication-policy="automatic" \
            --data-file=-
        echo "Secret ${secret_name} created"
    fi
}

# Create required secrets
echo "=== Datadog API Keys ==="
create_or_update_secret "DD_API_KEY" "DD_API_KEY"
create_or_update_secret "DD_APP_KEY" "DD_APP_KEY"

echo ""
echo "=== OpenAI API Key (for RAGAS evaluations) ==="
create_or_update_secret "OPENAI_API_KEY" "OPENAI_API_KEY"

echo ""
echo "Secrets configuration complete."
echo ""
echo "To verify secrets were created:"
echo "  gcloud secrets list --project ${PROJECT_ID}"

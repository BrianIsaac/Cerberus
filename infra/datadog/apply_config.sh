#!/bin/bash
# Apply Datadog configuration using the API
# Requires DD_API_KEY and DD_APP_KEY environment variables

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Load .env file if it exists (strips comments and empty lines)
load_env() {
    local env_file="${PROJECT_ROOT}/.env"
    if [ -f "$env_file" ]; then
        # Export variables from .env, handling quotes and comments
        set -a
        while IFS='=' read -r key value; do
            # Skip empty lines and comments
            [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
            # Remove leading/trailing whitespace from key
            key=$(echo "$key" | xargs)
            # Remove surrounding quotes from value and inline comments
            value=$(echo "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*#.*//' -e 's/^["'"'"']//' -e 's/["'"'"']$//')
            # Only export if not already set (env vars take precedence)
            if [ -z "${!key}" ]; then
                export "$key=$value"
            fi
        done < "$env_file"
        set +a
        return 0
    fi
    return 1
}

# Load environment variables from .env
if load_env; then
    echo "[INFO] Loaded environment from ${PROJECT_ROOT}/.env"
fi

DD_SITE="${DD_SITE:-ap1.datadoghq.com}"

# Colour output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Colour

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    if [ -z "${DD_API_KEY}" ]; then
        log_error "DD_API_KEY environment variable is not set"
        exit 1
    fi

    if [ -z "${DD_APP_KEY}" ]; then
        log_error "DD_APP_KEY environment variable is not set"
        exit 1
    fi

    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not installed. Install with: sudo apt-get install jq"
        exit 1
    fi

    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        exit 1
    fi
}

create_dashboard() {
    log_info "Creating dashboard..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "https://api.${DD_SITE}/api/v1/dashboard" \
        -H "Content-Type: application/json" \
        -H "DD-API-KEY: ${DD_API_KEY}" \
        -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
        -d @"${SCRIPT_DIR}/dashboard.json")

    local http_code
    http_code=$(echo "$response" | tail -n1)
    local body
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        local dashboard_id
        dashboard_id=$(echo "$body" | jq -r '.id // .dashboard.id // "unknown"')
        log_info "Dashboard created successfully. ID: ${dashboard_id}"
        log_info "View at: https://app.${DD_SITE}/dashboard/${dashboard_id}"
    else
        log_error "Failed to create dashboard. HTTP ${http_code}"
        log_error "Response: ${body}"
        return 1
    fi
}

update_dashboard() {
    local dashboard_id="${1:-k3b-pcm-45c}"
    log_info "Updating dashboard ${dashboard_id}..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X PUT "https://api.${DD_SITE}/api/v1/dashboard/${dashboard_id}" \
        -H "Content-Type: application/json" \
        -H "DD-API-KEY: ${DD_API_KEY}" \
        -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
        -d @"${SCRIPT_DIR}/dashboard.json")

    local http_code
    http_code=$(echo "$response" | tail -n1)
    local body
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        log_info "Dashboard updated successfully. ID: ${dashboard_id}"
        log_info "View at: https://${DD_SITE}/dashboard/${dashboard_id}"
    else
        log_error "Failed to update dashboard. HTTP ${http_code}"
        log_error "Response: ${body}"
        return 1
    fi
}

create_monitors() {
    log_info "Creating monitors..."

    local monitor_count
    monitor_count=$(jq '.monitors | length' "${SCRIPT_DIR}/monitors.json")
    local created=0
    local failed=0

    jq -c '.monitors[]' "${SCRIPT_DIR}/monitors.json" | while read -r monitor; do
        local monitor_name
        monitor_name=$(echo "$monitor" | jq -r '.name')

        local response
        response=$(curl -s -w "\n%{http_code}" -X POST "https://api.${DD_SITE}/api/v1/monitor" \
            -H "Content-Type: application/json" \
            -H "DD-API-KEY: ${DD_API_KEY}" \
            -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
            -d "${monitor}")

        local http_code
        http_code=$(echo "$response" | tail -n1)
        local body
        body=$(echo "$response" | sed '$d')

        if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
            local monitor_id
            monitor_id=$(echo "$body" | jq -r '.id // "unknown"')
            log_info "  Created: ${monitor_name} (ID: ${monitor_id})"
        else
            log_error "  Failed: ${monitor_name} - HTTP ${http_code}"
            log_error "  Response: ${body}"
        fi
    done

    log_info "Monitor creation complete."
}

create_slos() {
    log_info "Creating SLOs..."

    local slo_count
    slo_count=$(jq '.slos | length' "${SCRIPT_DIR}/slos.json")

    jq -c '.slos[]' "${SCRIPT_DIR}/slos.json" | while read -r slo; do
        local slo_name
        slo_name=$(echo "$slo" | jq -r '.name')

        local response
        response=$(curl -s -w "\n%{http_code}" -X POST "https://api.${DD_SITE}/api/v1/slo" \
            -H "Content-Type: application/json" \
            -H "DD-API-KEY: ${DD_API_KEY}" \
            -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
            -d "${slo}")

        local http_code
        http_code=$(echo "$response" | tail -n1)
        local body
        body=$(echo "$response" | sed '$d')

        if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
            local slo_id
            slo_id=$(echo "$body" | jq -r '.data[0].id // .id // "unknown"')
            log_info "  Created: ${slo_name} (ID: ${slo_id})"
        else
            log_error "  Failed: ${slo_name} - HTTP ${http_code}"
            log_error "  Response: ${body}"
        fi
    done

    log_info "SLO creation complete."
}

validate_json() {
    log_info "Validating JSON files..."

    local valid=true

    if jq empty "${SCRIPT_DIR}/dashboard.json" 2>/dev/null; then
        log_info "  dashboard.json: Valid"
    else
        log_error "  dashboard.json: Invalid JSON"
        valid=false
    fi

    if jq empty "${SCRIPT_DIR}/monitors.json" 2>/dev/null; then
        log_info "  monitors.json: Valid"
    else
        log_error "  monitors.json: Invalid JSON"
        valid=false
    fi

    if jq empty "${SCRIPT_DIR}/slos.json" 2>/dev/null; then
        log_info "  slos.json: Valid"
    else
        log_error "  slos.json: Invalid JSON"
        valid=false
    fi

    if [ "$valid" = false ]; then
        log_error "JSON validation failed"
        exit 1
    fi

    log_info "All JSON files valid."
}

print_summary() {
    echo ""
    log_info "=========================================="
    log_info "Datadog Configuration Summary"
    log_info "=========================================="
    log_info "Site: ${DD_SITE}"
    log_info "Dashboard: 1 (6 widget groups)"
    log_info "Monitors: $(jq '.monitors | length' "${SCRIPT_DIR}/monitors.json")"
    log_info "SLOs: $(jq '.slos | length' "${SCRIPT_DIR}/slos.json")"
    echo ""
    log_info "Links:"
    log_info "  Dashboard: https://app.${DD_SITE}/dashboard/lists"
    log_info "  Monitors: https://app.${DD_SITE}/monitors/manage"
    log_info "  SLOs: https://app.${DD_SITE}/slo"
    log_info "=========================================="
}

main() {
    echo ""
    log_info "Applying Datadog configuration to ${DD_SITE}..."
    echo ""

    check_requirements
    validate_json

    echo ""
    create_dashboard
    echo ""
    create_monitors
    echo ""
    create_slos

    print_summary

    log_info "Datadog configuration applied successfully."
}

# Allow running individual functions for testing
case "${1:-}" in
    validate)
        check_requirements
        validate_json
        ;;
    dashboard)
        check_requirements
        create_dashboard
        ;;
    update-dashboard)
        check_requirements
        update_dashboard "${2:-k3b-pcm-45c}"
        ;;
    monitors)
        check_requirements
        create_monitors
        ;;
    slos)
        check_requirements
        create_slos
        ;;
    *)
        main
        ;;
esac

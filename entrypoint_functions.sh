#!/bin/bash
#######################################
# Validates that required environment variables are defined
# Arguments:
#   Space-separated string of variable names
# Example usage:
#   ensure_required_variables "USER HOME PASSWORD API_TOKEN"
# Returns:
#   0 if all variables are defined
#   3 if any variables are missing
#######################################
function ensure_required_variables() {
    local vars_as_string="${1}"
    local -a sensitive_vars=("USERNAME" "PASSWORD" "DATABASE_URI")
    local -a vars
    local var
    local missing_variable=false
    local is_sensitive=false

    # Parse the space-separated variable names
    IFS=' ' read -ra vars <<<"${vars_as_string}"

    echo "Checking required environment variables..."
    echo "----------------------------------------"

    # Check each variable
    for var in "${vars[@]}"; do
        is_sensitive=false

        # Check if variable name contains any sensitive keywords
        for sensitive_keyword in "${sensitive_vars[@]}"; do
            if [[ "${var}" == *"${sensitive_keyword}"* ]]; then
                is_sensitive=true
                break
            fi
        done

        # Verify if variable is defined
        if [[ -v "${var}" ]]; then
            if ${is_sensitive}; then
                echo "  ${var} is defined (value redacted)"
            else
                echo "  ${var} is defined: ${!var}"
            fi
        else
            echo "  XXX ${var} is NOT defined"
            missing_variable=true
        fi
    done

    echo "----------------------------------------"

    # Exit if any variables are missing
    if ${missing_variable}; then
        echo "ERROR: One or more required environment variables are undefined" >&2
        echo "Please define the missing variables and try again" >&2
        exit 3
    fi

    return 0
}
